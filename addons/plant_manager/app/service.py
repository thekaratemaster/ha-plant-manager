from __future__ import annotations

import asyncio
import json
from datetime import datetime
from pathlib import Path
from typing import Any

from .engine import (
    choose_timezone,
    due_for_digest,
    evaluate_status,
    format_digest_message,
    now_utc,
    parse_float,
    reset_notification_suppression,
    to_iso,
    update_watering_detection,
)
from .ha_client import HomeAssistantApiClient
from .models import PlantSnapshot
from .storage import PlantManagerStorage

DEFAULT_SETTINGS = {
    "default_notify_service": "",
    "digest_schedule_times": ["07:00"],
    "poll_interval": 60,
    "timezone": "",
}


class PlantManagerService:
    def __init__(
        self,
        *,
        storage: PlantManagerStorage,
        ha_client: HomeAssistantApiClient,
        options_path: str | Path = "/data/options.json",
    ) -> None:
        self._storage = storage
        self._ha_client = ha_client
        self._options_path = Path(options_path)
        self._loop_task: asyncio.Task[None] | None = None
        self._refresh_lock = asyncio.Lock()

    async def start(self) -> None:
        self._storage.initialize()
        self._seed_settings()
        if self._loop_task is None:
            self._loop_task = asyncio.create_task(self._run_loop(), name="plant_manager_loop")

    async def stop(self) -> None:
        if self._loop_task:
            self._loop_task.cancel()
            try:
                await self._loop_task
            except asyncio.CancelledError:
                pass
            self._loop_task = None
        await self._ha_client.close()

    def get_settings(self) -> dict[str, Any]:
        settings = DEFAULT_SETTINGS | self._storage.get_settings()
        digest_times = settings.get("digest_schedule_times") or ["07:00"]
        if isinstance(digest_times, str):
            digest_times = [part.strip() for part in digest_times.split(",") if part.strip()]
        settings["digest_schedule_times"] = digest_times
        settings["poll_interval"] = int(settings.get("poll_interval", DEFAULT_SETTINGS["poll_interval"]))
        return settings

    def set_settings(self, values: dict[str, Any]) -> dict[str, Any]:
        normalized: dict[str, Any] = {}
        if "default_notify_service" in values:
            normalized["default_notify_service"] = str(values["default_notify_service"] or "").strip()
        if "digest_schedule_times" in values:
            raw = values["digest_schedule_times"]
            if isinstance(raw, str):
                normalized["digest_schedule_times"] = [part.strip() for part in raw.split(",") if part.strip()]
            else:
                normalized["digest_schedule_times"] = [str(part).strip() for part in raw if str(part).strip()]
        if "poll_interval" in values:
            normalized["poll_interval"] = int(values["poll_interval"])
        if "timezone" in values:
            normalized["timezone"] = str(values["timezone"] or "").strip()
        return self._storage.set_settings(normalized)

    async def list_plants(self) -> list[dict[str, Any]]:
        snapshots = await self.refresh()
        return [snapshot.to_dict() for snapshot in snapshots]

    async def get_plant(self, plant_id: str) -> dict[str, Any] | None:
        await self.refresh()
        plant = self._storage.get_plant(plant_id)
        if plant is None:
            return None
        snapshot = evaluate_status(
            plant,
            moisture=plant.current_moisture,
            battery=plant.current_battery,
            now=now_utc(),
        )
        return snapshot.to_dict()

    def create_plant(self, payload: dict[str, Any]) -> dict[str, Any]:
        now = to_iso(now_utc())
        plant = self._storage.create_plant(
            {
                **payload,
                "created_at": now,
                "updated_at": now,
            }
        )
        self._storage.append_history(
            plant_id=plant.id,
            event_type="plant_created",
            created_at=now,
            details={"name": plant.name, "zone": plant.zone},
        )
        return plant.to_dict()

    def update_plant(self, plant_id: str, payload: dict[str, Any]) -> dict[str, Any] | None:
        changes = {**payload, "updated_at": to_iso(now_utc())}
        plant = self._storage.update_plant(plant_id, changes)
        if plant is None:
            return None
        self._storage.append_history(
            plant_id=plant_id,
            event_type="plant_updated",
            created_at=changes["updated_at"],
            details={"fields": sorted(payload.keys())},
        )
        return plant.to_dict()

    def mark_watered(self, plant_id: str, *, source: str = "manual") -> dict[str, Any] | None:
        now = to_iso(now_utc())
        plant = self._storage.update_plant(
            plant_id,
            {
                "last_watered_at": now,
                "last_notified_at": None,
                "pending_watering_since": None,
                "pending_previous_moisture": None,
                "updated_at": now,
            },
        )
        if plant is None:
            return None
        self._storage.append_history(
            plant_id=plant_id,
            event_type=f"{source}_watered",
            created_at=now,
            details={"source": source},
        )
        return plant.to_dict()

    def list_history(self, plant_id: str | None = None) -> list[dict[str, Any]]:
        return [event.to_dict() for event in self._storage.list_history(plant_id)]

    async def get_summary(self) -> dict[str, Any]:
        snapshots = await self.refresh()
        return self._summarize(snapshots)

    async def send_digest_now(self) -> dict[str, Any]:
        snapshots = await self.refresh()
        sent = await self._send_digest(snapshots, scheduled=False)
        return {"sent": sent, "summary": self._summarize(snapshots)}

    async def refresh(self) -> list[PlantSnapshot]:
        async with self._refresh_lock:
            plants = self._storage.list_plants()
            if not plants:
                return []

            states = {
                item.get("entity_id"): item
                for item in await self._ha_client.get_all_states()
                if item.get("entity_id")
            }
            now = now_utc()
            snapshots: list[PlantSnapshot] = []

            for plant in plants:
                moisture_state = states.get(plant.moisture_sensor_entity_id)
                battery_state = states.get(plant.battery_sensor_entity_id) if plant.battery_sensor_entity_id else None
                moisture = parse_float(moisture_state["state"]) if moisture_state else None
                battery = parse_float(battery_state["state"]) if battery_state else None

                detection_updates, detection_event = update_watering_detection(
                    plant,
                    moisture=moisture,
                    now=now,
                )
                if detection_updates:
                    plant = self._storage.update_plant(
                        plant.id,
                        {**detection_updates, "updated_at": to_iso(now)},
                    ) or plant

                snapshot = evaluate_status(plant, moisture=moisture, battery=battery, now=now)
                reset_updates = reset_notification_suppression(plant, snapshot)
                plant = self._storage.update_plant(
                    plant.id,
                    {
                        "current_status": snapshot.status,
                        "current_moisture": moisture,
                        "current_battery": battery,
                        "needs_water": snapshot.needs_water,
                        "updated_at": to_iso(now),
                        **reset_updates,
                    },
                ) or plant
                snapshot = evaluate_status(plant, moisture=moisture, battery=battery, now=now)
                snapshots.append(snapshot)

                if detection_event:
                    self._storage.append_history(
                        plant_id=plant.id,
                        event_type=detection_event["event_type"],
                        created_at=to_iso(now),
                        details=detection_event["details"],
                    )

            return snapshots

    async def _run_loop(self) -> None:
        while True:
            settings = self.get_settings()
            try:
                snapshots = await self.refresh()
                await self._maybe_send_scheduled_digest(snapshots, settings=settings)
            except Exception as exc:  # pragma: no cover
                self._storage.append_history(
                    plant_id=None,
                    event_type="background_error",
                    created_at=to_iso(now_utc()),
                    details={"error": str(exc)},
                )

            await asyncio.sleep(max(15, int(settings["poll_interval"])))

    async def _maybe_send_scheduled_digest(
        self,
        snapshots: list[PlantSnapshot],
        *,
        settings: dict[str, Any],
    ) -> None:
        if not settings.get("default_notify_service"):
            return

        timezone_name = settings.get("timezone") or None
        ha_timezone = None
        try:
            config = await self._ha_client.get_config()
            ha_timezone = config.get("time_zone")
        except Exception:
            ha_timezone = None

        tz = choose_timezone(timezone_name, ha_timezone)
        now_local = now_utc().astimezone(tz)
        persisted_settings = self._storage.get_settings()

        for time_slot in settings.get("digest_schedule_times", []):
            marker_key = f"digest_marker_{time_slot}"
            today = now_local.date().isoformat()
            if persisted_settings.get(marker_key) == today:
                continue
            if not self._slot_due(time_slot, now_local):
                continue
            await self._send_digest(snapshots, scheduled=True)
            self._storage.set_settings({marker_key: today})

    async def _send_digest(self, snapshots: list[PlantSnapshot], *, scheduled: bool) -> bool:
        dry_snapshots = [snapshot for snapshot in snapshots if due_for_digest(snapshot)]
        if not dry_snapshots:
            return False

        settings = self.get_settings()
        notify_service = settings.get("default_notify_service", "").strip()
        if not notify_service:
            return False

        message = format_digest_message(dry_snapshots)
        await self._ha_client.call_action(
            notify_service,
            {
                "title": "Plant Manager",
                "message": message,
            },
        )

        now = to_iso(now_utc())
        for snapshot in dry_snapshots:
            self._storage.update_plant(
                snapshot.plant.id,
                {
                    "last_notified_at": now,
                    "updated_at": now,
                },
            )
            self._storage.append_history(
                plant_id=snapshot.plant.id,
                event_type="digest_notified",
                created_at=now,
                details={"scheduled": scheduled, "status": snapshot.status},
            )
        return True

    def _seed_settings(self) -> None:
        current = self._storage.get_settings()
        merged = {**DEFAULT_SETTINGS, **self._load_boot_options(), **current}
        self._storage.set_settings(merged)

    def _load_boot_options(self) -> dict[str, Any]:
        if not self._options_path.exists():
            return {}
        try:
            return json.loads(self._options_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return {}

    def _summarize(self, snapshots: list[PlantSnapshot]) -> dict[str, Any]:
        return {
            "total_plants": len(snapshots),
            "plants_needing_water": sum(1 for snapshot in snapshots if snapshot.needs_water),
            "indoor_needing_water": sum(
                1 for snapshot in snapshots if snapshot.plant.zone == "indoor" and snapshot.needs_water
            ),
            "outdoor_needing_water": sum(
                1 for snapshot in snapshots if snapshot.plant.zone == "outdoor" and snapshot.needs_water
            ),
            "indoor_total": sum(1 for snapshot in snapshots if snapshot.plant.zone == "indoor"),
            "outdoor_total": sum(1 for snapshot in snapshots if snapshot.plant.zone == "outdoor"),
            "statuses": {snapshot.plant.id: snapshot.status for snapshot in snapshots},
        }

    @staticmethod
    def _slot_due(slot: str, now_local: datetime) -> bool:
        try:
            hour_text, minute_text = slot.split(":", 1)
            hour = int(hour_text)
            minute = int(minute_text)
        except (ValueError, AttributeError):
            return False
        return (now_local.hour, now_local.minute) >= (hour, minute)
