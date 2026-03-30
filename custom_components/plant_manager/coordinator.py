from __future__ import annotations

from datetime import timedelta
import logging
from typing import Any

from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api import PlantManagerApiClient, PlantManagerApiError
from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)


class PlantManagerCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    def __init__(
        self,
        hass: HomeAssistant,
        *,
        api: PlantManagerApiClient,
        scan_interval: int,
    ) -> None:
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=timedelta(seconds=scan_interval),
        )
        self.api = api

    async def _async_update_data(self) -> dict[str, Any]:
        try:
            summary = await self.api.get_summary()
            plants = await self.api.list_plants()
        except PlantManagerApiError as exc:
            raise UpdateFailed(str(exc)) from exc

        return {
            "summary": summary,
            "plants": {plant["id"]: plant for plant in plants},
        }
