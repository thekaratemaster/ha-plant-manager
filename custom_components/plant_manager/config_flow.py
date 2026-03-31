from __future__ import annotations

from typing import Any
from uuid import uuid4

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.core import callback
import homeassistant.helpers.selector as selector

from .const import (
    CONF_ALERTS_ENABLED,
    CONF_BATTERY_ENTITY,
    CONF_PLANT_CALENDAR,
    CONF_DIGEST_TIMES,
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
    DEFAULT_DIGEST_TIMES,
    DEFAULT_LOW_THRESHOLD,
    DEFAULT_MIN_INCREASE,
    DEFAULT_MIN_INTERVAL_DAYS,
    DEFAULT_NOTIFY_SERVICE,
    DOMAIN,
)


class PlantManagerConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    VERSION = 1

    async def async_step_user(self, user_input: dict[str, Any] | None = None):
        if user_input is not None:
            await self.async_set_unique_id(DOMAIN)
            self._abort_if_unique_id_configured()
            return self.async_create_entry(
                title="Plant Manager",
                data={},
                options={
                    CONF_NOTIFY_SERVICE: user_input.get(CONF_NOTIFY_SERVICE, ""),
                    CONF_DIGEST_TIMES: user_input.get(CONF_DIGEST_TIMES, DEFAULT_DIGEST_TIMES),
                    CONF_PLANTS: [],
                },
            )

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Optional(CONF_NOTIFY_SERVICE, default=DEFAULT_NOTIFY_SERVICE): selector.TextSelector(),
                    vol.Optional(CONF_DIGEST_TIMES, default=DEFAULT_DIGEST_TIMES): selector.TextSelector(),
                }
            ),
        )

    @staticmethod
    @callback
    def async_get_options_flow(_config_entry: config_entries.ConfigEntry):
        return PlantManagerOptionsFlow()


class PlantManagerOptionsFlow(config_entries.OptionsFlow):
    def __init__(self) -> None:
        self._plants: list[dict[str, Any]] | None = None

    def _get_plants(self) -> list[dict[str, Any]]:
        if self._plants is None:
            self._plants = list(self.config_entry.options.get(CONF_PLANTS, []))
        return self._plants

    async def async_step_init(self, _user_input: dict[str, Any] | None = None):
        return self.async_show_menu(
            step_id="init",
            menu_options=["add_plant", "remove_plant", "settings"],
        )

    async def async_step_settings(self, user_input: dict[str, Any] | None = None):
        if user_input is not None:
            return self.async_create_entry(
                title="",
                data={
                    **self.config_entry.options,
                    CONF_NOTIFY_SERVICE: user_input.get(CONF_NOTIFY_SERVICE, ""),
                    CONF_DIGEST_TIMES: user_input.get(CONF_DIGEST_TIMES, DEFAULT_DIGEST_TIMES),
                    CONF_PLANTS: self._get_plants(),
                },
            )

        current_notify = self.config_entry.options.get(CONF_NOTIFY_SERVICE, DEFAULT_NOTIFY_SERVICE)
        current_times = self.config_entry.options.get(CONF_DIGEST_TIMES, DEFAULT_DIGEST_TIMES)

        return self.async_show_form(
            step_id="settings",
            data_schema=vol.Schema(
                {
                    vol.Optional(CONF_NOTIFY_SERVICE, default=current_notify): selector.TextSelector(),
                    vol.Optional(CONF_DIGEST_TIMES, default=current_times): selector.TextSelector(),
                }
            ),
        )

    async def async_step_add_plant(self, user_input: dict[str, Any] | None = None):
        if user_input is not None:
            new_plant = {
                "id": str(uuid4()),
                "created_at": _now_iso(),
                CONF_PLANT_NAME: user_input[CONF_PLANT_NAME],
                CONF_PLANT_ZONE: user_input[CONF_PLANT_ZONE],
                CONF_PLANT_LOCATION: user_input.get(CONF_PLANT_LOCATION, ""),
                CONF_MOISTURE_ENTITY: user_input[CONF_MOISTURE_ENTITY],
                CONF_BATTERY_ENTITY: user_input.get(CONF_BATTERY_ENTITY) or None,
                CONF_PLANT_CALENDAR: user_input.get(CONF_PLANT_CALENDAR) or None,
                CONF_LOW_THRESHOLD: float(user_input[CONF_LOW_THRESHOLD]),
                CONF_MIN_INCREASE: float(user_input[CONF_MIN_INCREASE]),
                CONF_MIN_INTERVAL_DAYS: int(user_input[CONF_MIN_INTERVAL_DAYS]),
                CONF_ALERTS_ENABLED: bool(user_input.get(CONF_ALERTS_ENABLED, True)),
                CONF_PLANT_NOTES: user_input.get(CONF_PLANT_NOTES) or None,
            }
            self._get_plants().append(new_plant)
            return self.async_create_entry(
                title="",
                data={**self.config_entry.options, CONF_PLANTS: self._get_plants()},
            )

        return self.async_show_form(
            step_id="add_plant",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_PLANT_NAME): selector.TextSelector(),
                    vol.Required(CONF_PLANT_ZONE): selector.SelectSelector(
                        selector.SelectSelectorConfig(options=["indoor", "outdoor"])
                    ),
                    vol.Optional(CONF_PLANT_LOCATION, default=""): selector.TextSelector(),
                    vol.Required(CONF_MOISTURE_ENTITY): selector.EntitySelector(
                        selector.EntitySelectorConfig(domain="sensor")
                    ),
                    vol.Optional(CONF_BATTERY_ENTITY): selector.EntitySelector(
                        selector.EntitySelectorConfig(domain="sensor")
                    ),
                    vol.Optional(CONF_PLANT_CALENDAR): selector.EntitySelector(
                        selector.EntitySelectorConfig(domain="calendar")
                    ),
                    vol.Required(CONF_LOW_THRESHOLD, default=DEFAULT_LOW_THRESHOLD): selector.NumberSelector(
                        selector.NumberSelectorConfig(min=0, max=100, step=1, unit_of_measurement="%")
                    ),
                    vol.Required(CONF_MIN_INCREASE, default=DEFAULT_MIN_INCREASE): selector.NumberSelector(
                        selector.NumberSelectorConfig(min=1, max=100, step=1, unit_of_measurement="%")
                    ),
                    vol.Required(CONF_MIN_INTERVAL_DAYS, default=DEFAULT_MIN_INTERVAL_DAYS): selector.NumberSelector(
                        selector.NumberSelectorConfig(min=1, max=90, step=1)
                    ),
                    vol.Optional(CONF_ALERTS_ENABLED, default=True): selector.BooleanSelector(),
                    vol.Optional(CONF_PLANT_NOTES, default=""): selector.TextSelector(
                        selector.TextSelectorConfig(multiline=True)
                    ),
                }
            ),
        )

    async def async_step_remove_plant(self, user_input: dict[str, Any] | None = None):
        plants = self._get_plants()
        if not plants:
            return self.async_abort(reason="no_plants")

        if user_input is not None:
            ids_to_remove: list[str] = user_input.get("plant_ids", [])
            self._plants = [p for p in plants if p["id"] not in ids_to_remove]
            return self.async_create_entry(
                title="",
                data={**self.config_entry.options, CONF_PLANTS: self._plants},
            )

        plant_options = [
            selector.SelectOptionDict(value=p["id"], label=p[CONF_PLANT_NAME])
            for p in plants
        ]
        return self.async_show_form(
            step_id="remove_plant",
            data_schema=vol.Schema(
                {
                    vol.Required("plant_ids"): selector.SelectSelector(
                        selector.SelectSelectorConfig(
                            options=plant_options,
                            multiple=True,
                        )
                    ),
                }
            ),
        )


def _now_iso() -> str:
    from datetime import datetime, timezone
    return datetime.now(timezone.utc).isoformat()
