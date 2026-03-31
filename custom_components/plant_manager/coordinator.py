from __future__ import annotations

import logging
from datetime import date, timedelta
from typing import Any, Callable

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import Event, HomeAssistant, callback
from homeassistant.helpers.event import async_call_later, async_track_state_change_event
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from .const import (
    CONF_ALERTS_ENABLED,
    CONF_BATTERY_LOW_THRESHOLD,
    CONF_PLANT_CALENDAR,
    CONF_BATTERY_ENTITY,
    CONF_LOW_THRESHOLD,
    CONF_MIN_INCREASE,
    CONF_MIN_INTERVAL_DAYS,
    CONF_MOISTURE_ENTITY,
    CONF_NOTIFY_SERVICE,
    CONF_PLANT_LOCATION,
    CONF_PLANT_NAME,
    CONF_PLANT_NOTES,
    CONF_PLANT_ZONE,
    CONF_PLANTS,
    DEFAULT_BATTERY_LOW_THRESHOLD,
    DOMAIN,
)
from .engine import (
    due_for_digest,
    evaluate_status,
    format_digest_message,
    now_utc,
    parse_float,
    reset_notification_suppression,
    to_iso,
    update_watering_detection,
    WATERING_CONFIRMATION_SECONDS,
)
from .models import Plant, PlantSnapshot
from .storage import PlantManagerStore

_LOGGER = logging.getLogger(__name__)


class PlantManagerCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    def __init__(
        self,
        hass: HomeAssistant,
        entry: ConfigEntry,
        store: PlantManagerStore,
    ) -> None:
        super().__init__(hass, _LOGGER, name=DOMAIN, update_interval=None)
        self._entry = entry
        self._store = store
        self._unsub_listeners: list[Callable[[], None]] = []
        self._pending_cancel: dict[str, Callable[[], None]] = {}

    async def async_setup(self) -> None:
        await self._store.async_load()
        self._subscribe_state_listeners()
        self.async_set_updated_data(self._build_data())

    def _subscribe_state_listeners(self) -> None:
        for unsub in self._unsub_listeners:
            unsub()
        self._unsub_listeners.clear()

        tracked: set[str] = set()
        for plant_config in self._entry.options.get(CONF_PLANTS, []):
            for entity_id in (
                plant_config.get(CONF_MOISTURE_ENTITY),
                plant_config.get(CONF_BATTERY_ENTITY),
            ):
                if entity_id and entity_id not in tracked:
                    tracked.add(entity_id)
                    self._unsub_listeners.append(
                        async_track_state_change_event(
                            self.hass, entity_id, self._handle_state_change
                        )
                    )

    @callback
    def _handle_state_change(self, event: Event) -> None:
        entity_id: str = event.data["entity_id"]
        new_state = event.data.get("new_state")
        if new_state is None:
            return

        for plant_config in self._entry.options.get(CONF_PLANTS, []):
            plant_id: str = plant_config["id"]
            is_moisture = plant_config.get(CONF_MOISTURE_ENTITY) == entity_id
            is_battery = plant_config.get(CONF_BATTERY_ENTITY) == entity_id
            if not (is_moisture or is_battery):
                continue

            if is_moisture:
                moisture = parse_float(new_state.state)
                battery = self._current_battery(plant_config)
            else:
                moisture = self._current_moisture(plant_config)
                battery = parse_float(new_state.state)

            self._process_sensor_change(plant_id, plant_config, moisture, battery)
            break

    def _process_sensor_change(
        self,
        plant_id: str,
        plant_config: dict[str, Any],
        moisture: float | None,
        battery: float | None,
    ) -> None:
        plant_state = self._store.get_plant_state(plant_id)
        plant = self._build_plant(plant_config, plant_state)
        now = now_utc()

        detection_updates, _event = update_watering_detection(plant, moisture=moisture, now=now)
        if detection_updates:
            plant_state.update(detection_updates)
            if plant_id in self._pending_cancel:
                self._pending_cancel.pop(plant_id)()
            if plant_state.get("pending_watering_since"):
                self._pending_cancel[plant_id] = async_call_later(
                    self.hass,
                    WATERING_CONFIRMATION_SECONDS,
                    lambda _now, pid=plant_id: self._check_pending(pid),
                )

        plant = self._build_plant(plant_config, plant_state)
        snapshot = evaluate_status(plant, moisture=moisture, battery=battery, now=now)
        reset_updates = reset_notification_suppression(plant, snapshot)

        plant_state.update(
            {
                "current_status": snapshot.status,
                "current_moisture": moisture,
                "current_battery": battery,
                "needs_water": snapshot.needs_water,
                **reset_updates,
            }
        )
        self._store.set_plant_state(plant_id, plant_state)
        self.hass.async_create_task(self._store.async_save())
        self.async_set_updated_data(self._build_data())

    @callback
    def _check_pending(self, plant_id: str) -> None:
        self._pending_cancel.pop(plant_id, None)
        plant_config = next(
            (p for p in self._entry.options.get(CONF_PLANTS, []) if p["id"] == plant_id),
            None,
        )
        if not plant_config:
            return
        moisture = self._current_moisture(plant_config)
        battery = self._current_battery(plant_config)
        self._process_sensor_change(plant_id, plant_config, moisture, battery)

    def mark_watered(self, plant_id: str) -> None:
        now_str = to_iso(now_utc())
        plant_state = self._store.get_plant_state(plant_id)
        plant_state.update(
            {
                "last_watered_at": now_str,
                "last_notified_at": None,
                "pending_watering_since": None,
                "pending_previous_moisture": None,
            }
        )
        self._store.set_plant_state(plant_id, plant_state)
        self.hass.async_create_task(self._store.async_save())
        self.async_set_updated_data(self._build_data())

    async def async_send_digest(self) -> bool:
        notify_service = self._entry.options.get(CONF_NOTIFY_SERVICE, "").strip()
        if not notify_service or "." not in notify_service:
            return False

        now = now_utc()
        dry_snapshots: list[PlantSnapshot] = []

        for plant_config in self._entry.options.get(CONF_PLANTS, []):
            plant_id = plant_config["id"]
            plant_state = self._store.get_plant_state(plant_id)
            plant = self._build_plant(plant_config, plant_state)
            moisture = plant_state.get("current_moisture")
            battery = plant_state.get("current_battery")
            snapshot = evaluate_status(plant, moisture=moisture, battery=battery, now=now)
            if due_for_digest(snapshot):
                dry_snapshots.append(snapshot)

        if not dry_snapshots:
            return False

        message = format_digest_message(dry_snapshots)
        domain, service = notify_service.split(".", 1)
        await self.hass.services.async_call(
            domain,
            service,
            {"title": "Plant Manager", "message": message},
        )

        now_str = to_iso(now)
        today = now.date().isoformat()
        tomorrow = (now.date() + timedelta(days=1)).isoformat()

        for snapshot in dry_snapshots:
            plant_state = self._store.get_plant_state(snapshot.plant.id)
            plant_state["last_notified_at"] = now_str
            self._store.set_plant_state(snapshot.plant.id, plant_state)

            plant_config = next(
                (p for p in self._entry.options.get(CONF_PLANTS, []) if p["id"] == snapshot.plant.id),
                None,
            )
            if plant_config:
                calendar_entity = plant_config.get(CONF_PLANT_CALENDAR)
                if calendar_entity:
                    moisture = plant_state.get("current_moisture")
                    moisture_str = f"{moisture:.0f}%" if moisture is not None else "N/A"
                    location = plant_config.get(CONF_PLANT_LOCATION) or "unspecified"
                    try:
                        await self.hass.services.async_call(
                            "calendar",
                            "create_event",
                            {
                                "summary": f"Water {plant_config[CONF_PLANT_NAME]}",
                                "description": f"Moisture: {moisture_str}. Location: {location}",
                                "start_date": today,
                                "end_date": tomorrow,
                            },
                            target={"entity_id": calendar_entity},
                        )
                    except Exception as err:
                        _LOGGER.warning("Failed to create calendar event for %s: %s", plant_config[CONF_PLANT_NAME], err)

        await self._store.async_save()
        self.async_set_updated_data(self._build_data())
        return True

    async def async_send_scheduled_digest(self, slot: str) -> None:
        today = date.today().isoformat()
        markers = self._store.get_digest_markers()
        if markers.get(slot) == today:
            return
        sent = await self.async_send_digest()
        if sent:
            self._store.set_digest_marker(slot, today)
            await self._store.async_save()

    def _build_data(self) -> dict[str, Any]:
        plants: dict[str, Any] = {}
        for plant_config in self._entry.options.get(CONF_PLANTS, []):
            plant_id = plant_config["id"]
            plant_state = self._store.get_plant_state(plant_id)
            plant = self._build_plant(plant_config, plant_state)
            now = now_utc()
            moisture = plant_state.get("current_moisture")
            battery = plant_state.get("current_battery")
            snapshot = evaluate_status(plant, moisture=moisture, battery=battery, now=now)
            merged = plant.to_dict()
            merged.update(
                {
                    "status": snapshot.status,
                    "needs_water": snapshot.needs_water,
                    "days_since_watered": snapshot.days_since_watered,
                }
            )
            plants[plant_id] = merged

        all_plants = list(plants.values())
        summary = {
            "total_plants": len(all_plants),
            "plants_needing_water": sum(1 for p in all_plants if p.get("needs_water")),
            "indoor_needing_water": sum(
                1 for p in all_plants if p.get("zone") == "indoor" and p.get("needs_water")
            ),
            "outdoor_needing_water": sum(
                1 for p in all_plants if p.get("zone") == "outdoor" and p.get("needs_water")
            ),
            "indoor_total": sum(1 for p in all_plants if p.get("zone") == "indoor"),
            "outdoor_total": sum(1 for p in all_plants if p.get("zone") == "outdoor"),
        }
        return {"plants": plants, "summary": summary}

    def _build_plant(self, plant_config: dict[str, Any], plant_state: dict[str, Any]) -> Plant:
        now_str = to_iso(now_utc())
        return Plant(
            id=plant_config["id"],
            name=plant_config[CONF_PLANT_NAME],
            zone=plant_config[CONF_PLANT_ZONE],
            location_label=plant_config.get(CONF_PLANT_LOCATION, ""),
            moisture_sensor_entity_id=plant_config[CONF_MOISTURE_ENTITY],
            battery_sensor_entity_id=plant_config.get(CONF_BATTERY_ENTITY) or None,
            low_threshold=float(plant_config[CONF_LOW_THRESHOLD]),
            battery_low_threshold=float(plant_config.get(CONF_BATTERY_LOW_THRESHOLD, DEFAULT_BATTERY_LOW_THRESHOLD)),
            min_increase=float(plant_config[CONF_MIN_INCREASE]),
            min_interval_days=int(plant_config[CONF_MIN_INTERVAL_DAYS]),
            alerts_enabled=bool(plant_config.get(CONF_ALERTS_ENABLED, True)),
            notes=plant_config.get(CONF_PLANT_NOTES) or None,
            last_watered_at=plant_state.get("last_watered_at"),
            last_notified_at=plant_state.get("last_notified_at"),
            created_at=plant_config.get("created_at", now_str),
            updated_at=now_str,
            last_moisture=plant_state.get("last_moisture"),
            last_moisture_at=plant_state.get("last_moisture_at"),
            pending_watering_since=plant_state.get("pending_watering_since"),
            pending_previous_moisture=plant_state.get("pending_previous_moisture"),
            current_status=plant_state.get("current_status"),
            current_moisture=plant_state.get("current_moisture"),
            current_battery=plant_state.get("current_battery"),
            needs_water=bool(plant_state.get("needs_water", False)),
        )

    def _current_moisture(self, plant_config: dict[str, Any]) -> float | None:
        entity_id = plant_config.get(CONF_MOISTURE_ENTITY)
        if not entity_id:
            return None
        state = self.hass.states.get(entity_id)
        return parse_float(state.state) if state else None

    def _current_battery(self, plant_config: dict[str, Any]) -> float | None:
        entity_id = plant_config.get(CONF_BATTERY_ENTITY)
        if not entity_id:
            return None
        state = self.hass.states.get(entity_id)
        return parse_float(state.state) if state else None

    async def async_teardown(self) -> None:
        for unsub in self._unsub_listeners:
            unsub()
        self._unsub_listeners.clear()
        for cancel in self._pending_cancel.values():
            cancel()
        self._pending_cancel.clear()
