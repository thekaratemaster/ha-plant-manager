from __future__ import annotations

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.core import callback
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api import PlantManagerApiClient, PlantManagerApiError
from .const import (
    CONF_BASE_URL,
    CONF_SCAN_INTERVAL,
    DEFAULT_BASE_URL,
    DEFAULT_SCAN_INTERVAL,
    DOMAIN,
)


class PlantManagerConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    VERSION = 1

    async def async_step_user(self, user_input=None):
        errors = {}
        if user_input is not None:
            api = PlantManagerApiClient(
                async_get_clientsession(self.hass),
                user_input[CONF_BASE_URL],
            )
            try:
                await api.health()
            except PlantManagerApiError:
                errors["base"] = "cannot_connect"
            else:
                await self.async_set_unique_id(user_input[CONF_BASE_URL].rstrip("/"))
                self._abort_if_unique_id_configured()
                return self.async_create_entry(title="Plant Manager", data=user_input)

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_BASE_URL, default=DEFAULT_BASE_URL): cv.string,
                    vol.Required(CONF_SCAN_INTERVAL, default=DEFAULT_SCAN_INTERVAL): vol.All(
                        int, vol.Range(min=15, max=3600)
                    ),
                }
            ),
            errors=errors,
        )

    @staticmethod
    @callback
    def async_get_options_flow(config_entry):
        return PlantManagerOptionsFlow(config_entry)


class PlantManagerOptionsFlow(config_entries.OptionsFlow):
    def __init__(self, entry):
        self.entry = entry

    async def async_step_init(self, user_input=None):
        errors = {}
        if user_input is not None:
            api = PlantManagerApiClient(
                async_get_clientsession(self.hass),
                user_input[CONF_BASE_URL],
            )
            try:
                await api.health()
            except PlantManagerApiError:
                errors["base"] = "cannot_connect"
            else:
                return self.async_create_entry(title="", data=user_input)

        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema(
                {
                    vol.Required(
                        CONF_BASE_URL,
                        default=self.entry.options.get(CONF_BASE_URL, self.entry.data.get(CONF_BASE_URL, DEFAULT_BASE_URL)),
                    ): cv.string,
                    vol.Required(
                        CONF_SCAN_INTERVAL,
                        default=self.entry.options.get(
                            CONF_SCAN_INTERVAL,
                            self.entry.data.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL),
                        ),
                    ): vol.All(int, vol.Range(min=15, max=3600)),
                }
            ),
            errors=errors,
        )
