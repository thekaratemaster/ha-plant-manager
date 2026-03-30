from __future__ import annotations

import voluptuous as vol

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.exceptions import ConfigEntryNotReady, HomeAssistantError
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers import config_validation as cv

from .api import PlantManagerApiClient, PlantManagerApiError
from .const import (
    ATTR_ENTRY_ID,
    ATTR_PLANT_ID,
    CONF_BASE_URL,
    CONF_SCAN_INTERVAL,
    DEFAULT_BASE_URL,
    DEFAULT_SCAN_INTERVAL,
    DOMAIN,
    PLATFORMS,
    SERVICE_MARK_WATERED,
    SERVICE_REFRESH,
    SERVICE_SEND_DIGEST_NOW,
)
from .coordinator import PlantManagerCoordinator


async def async_setup(hass: HomeAssistant, config: dict) -> bool:
    hass.data.setdefault(DOMAIN, {})
    await _async_ensure_services(hass)
    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    hass.data.setdefault(DOMAIN, {})
    base_url = (entry.options.get(CONF_BASE_URL) or entry.data.get(CONF_BASE_URL) or DEFAULT_BASE_URL).strip()
    scan_interval = int(entry.options.get(CONF_SCAN_INTERVAL, entry.data.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL)))

    api = PlantManagerApiClient(async_get_clientsession(hass), base_url)
    try:
        await api.health()
    except PlantManagerApiError as exc:
        raise ConfigEntryNotReady(str(exc)) from exc

    coordinator = PlantManagerCoordinator(hass, api=api, scan_interval=scan_interval)
    await coordinator.async_config_entry_first_refresh()

    hass.data[DOMAIN][entry.entry_id] = {
        "api": api,
        "coordinator": coordinator,
        "update_listener": entry.add_update_listener(_async_reload_entry),
    }

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    await _async_ensure_services(hass)
    return True


async def _async_reload_entry(hass: HomeAssistant, entry: ConfigEntry) -> None:
    await hass.config_entries.async_reload(entry.entry_id)


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    data = hass.data[DOMAIN].get(entry.entry_id, {})
    unsub = data.get("update_listener")
    if unsub:
        unsub()

    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id, None)
        if not hass.data[DOMAIN]:
            for service_name in (SERVICE_MARK_WATERED, SERVICE_REFRESH, SERVICE_SEND_DIGEST_NOW):
                if hass.services.has_service(DOMAIN, service_name):
                    hass.services.async_remove(DOMAIN, service_name)
    return unload_ok


async def _async_ensure_services(hass: HomeAssistant) -> None:
    if hass.services.has_service(DOMAIN, SERVICE_MARK_WATERED):
        return

    async def handle_mark_watered(call: ServiceCall) -> None:
        runtime = _select_runtime(hass, call.data.get(ATTR_ENTRY_ID))
        if runtime is None:
            raise HomeAssistantError("Plant Manager is not configured")
        try:
            await runtime["api"].mark_watered(call.data[ATTR_PLANT_ID])
            await runtime["coordinator"].async_request_refresh()
        except PlantManagerApiError as exc:
            raise HomeAssistantError(str(exc)) from exc

    async def handle_refresh(call: ServiceCall) -> None:
        runtime = _select_runtime(hass, call.data.get(ATTR_ENTRY_ID))
        if runtime is None:
            raise HomeAssistantError("Plant Manager is not configured")
        await runtime["coordinator"].async_request_refresh()

    async def handle_send_digest(call: ServiceCall) -> None:
        runtime = _select_runtime(hass, call.data.get(ATTR_ENTRY_ID))
        if runtime is None:
            raise HomeAssistantError("Plant Manager is not configured")
        try:
            await runtime["api"].send_digest_now()
            await runtime["coordinator"].async_request_refresh()
        except PlantManagerApiError as exc:
            raise HomeAssistantError(str(exc)) from exc

    hass.services.async_register(
        DOMAIN,
        SERVICE_MARK_WATERED,
        handle_mark_watered,
        schema=vol.Schema(
            {
                vol.Required(ATTR_PLANT_ID): cv.string,
                vol.Optional(ATTR_ENTRY_ID): cv.string,
            }
        ),
    )
    hass.services.async_register(
        DOMAIN,
        SERVICE_REFRESH,
        handle_refresh,
        schema=vol.Schema({vol.Optional(ATTR_ENTRY_ID): cv.string}),
    )
    hass.services.async_register(
        DOMAIN,
        SERVICE_SEND_DIGEST_NOW,
        handle_send_digest,
        schema=vol.Schema({vol.Optional(ATTR_ENTRY_ID): cv.string}),
    )


def _select_runtime(hass: HomeAssistant, entry_id: str | None) -> dict | None:
    runtimes = hass.data.get(DOMAIN, {})
    if entry_id:
        return runtimes.get(entry_id)
    return next(iter(runtimes.values()), None)
