from __future__ import annotations

import logging

import voluptuous as vol

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import config_validation as cv, device_registry as dr, entity_registry as er
from homeassistant.helpers.event import async_track_time_change

from .const import (
    ATTR_PLANT_ID,
    CONF_DIGEST_TIMES,
    CONF_PLANTS,
    DEFAULT_DIGEST_TIMES,
    DOMAIN,
    PLATFORMS,
    SERVICE_MARK_WATERED,
    SERVICE_SEND_DIGEST_NOW,
)
from .coordinator import PlantManagerCoordinator
from .storage import PlantManagerStore

_LOGGER = logging.getLogger(__name__)


async def async_setup(hass: HomeAssistant, _config: dict) -> bool:
    hass.data.setdefault(DOMAIN, {})
    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    hass.data.setdefault(DOMAIN, {})

    store = PlantManagerStore(hass)
    coordinator = PlantManagerCoordinator(hass, entry, store)
    await coordinator.async_setup()

    unsub_digest = _setup_digest_schedule(hass, entry, coordinator)

    hass.data[DOMAIN][entry.entry_id] = {
        "coordinator": coordinator,
        "unsub_digest": unsub_digest,
        "update_listener": entry.add_update_listener(_async_reload_entry),
    }

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    _async_ensure_services(hass)
    _cleanup_orphaned_devices(hass, entry)
    return True


async def _async_reload_entry(hass: HomeAssistant, entry: ConfigEntry) -> None:
    await hass.config_entries.async_reload(entry.entry_id)


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    runtime = hass.data[DOMAIN].get(entry.entry_id, {})

    unsub = runtime.get("update_listener")
    if unsub:
        unsub()

    for unsub_fn in runtime.get("unsub_digest", []):
        unsub_fn()

    coordinator: PlantManagerCoordinator | None = runtime.get("coordinator")
    if coordinator:
        await coordinator.async_teardown()

    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id, None)
        if not hass.data[DOMAIN]:
            for service_name in (SERVICE_MARK_WATERED, SERVICE_SEND_DIGEST_NOW):
                if hass.services.has_service(DOMAIN, service_name):
                    hass.services.async_remove(DOMAIN, service_name)
    return unload_ok


def _setup_digest_schedule(
    hass: HomeAssistant,
    entry: ConfigEntry,
    coordinator: PlantManagerCoordinator,
) -> list:
    raw = entry.options.get(CONF_DIGEST_TIMES, DEFAULT_DIGEST_TIMES)
    slots = [s.strip() for s in raw.split(",")] if isinstance(raw, str) else list(raw)
    unsubs = []
    for slot in slots:
        try:
            hour, minute = map(int, slot.split(":", 1))
        except (ValueError, AttributeError):
            _LOGGER.warning("Invalid digest time %r — skipping", slot)
            continue

        async def _digest_callback(_now, _slot=slot) -> None:
            await coordinator.async_send_scheduled_digest(_slot)

        unsubs.append(async_track_time_change(hass, _digest_callback, hour=hour, minute=minute, second=0))
    return unsubs


def _async_ensure_services(hass: HomeAssistant) -> None:
    if hass.services.has_service(DOMAIN, SERVICE_MARK_WATERED):
        return

    async def handle_mark_watered(call: ServiceCall) -> None:
        coordinator = _get_coordinator(hass)
        plant_id: str = call.data[ATTR_PLANT_ID]
        if not any(
            p["id"] == plant_id
            for p in coordinator._entry.options.get(CONF_PLANTS, [])
        ):
            raise HomeAssistantError(f"Plant {plant_id!r} not found")
        coordinator.mark_watered(plant_id)

    async def handle_send_digest(_call: ServiceCall) -> None:
        coordinator = _get_coordinator(hass)
        await coordinator.async_send_digest()

    hass.services.async_register(
        DOMAIN,
        SERVICE_MARK_WATERED,
        handle_mark_watered,
        schema=vol.Schema({vol.Required(ATTR_PLANT_ID): cv.string}),
    )
    hass.services.async_register(
        DOMAIN,
        SERVICE_SEND_DIGEST_NOW,
        handle_send_digest,
        schema=vol.Schema({}),
    )


def _cleanup_orphaned_devices(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Remove devices (and their entities) for plants that no longer exist in options."""
    active_plant_ids = {p["id"] for p in entry.options.get(CONF_PLANTS, [])}
    device_registry = dr.async_get(hass)
    for device_entry in dr.async_entries_for_config_entry(device_registry, entry.entry_id):
        for domain, identifier in device_entry.identifiers:
            if domain == DOMAIN and identifier not in (entry.entry_id,) and identifier not in active_plant_ids:
                device_registry.async_remove_device(device_entry.id)
                break


def _get_coordinator(hass: HomeAssistant) -> PlantManagerCoordinator:
    runtimes = hass.data.get(DOMAIN, {})
    runtime = next(iter(runtimes.values()), None)
    if runtime is None:
        raise HomeAssistantError("Plant Manager is not configured")
    return runtime["coordinator"]
