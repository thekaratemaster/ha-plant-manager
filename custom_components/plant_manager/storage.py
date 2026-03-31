from __future__ import annotations

from typing import Any

from homeassistant.core import HomeAssistant
from homeassistant.helpers.storage import Store

from .const import STORAGE_KEY, STORAGE_VERSION


class PlantManagerStore:
    """Persists runtime plant state (watering history, moisture readings, pending detections)."""

    def __init__(self, hass: HomeAssistant) -> None:
        self._store: Store[dict[str, Any]] = Store(hass, STORAGE_VERSION, STORAGE_KEY)
        self._data: dict[str, Any] = {}

    async def async_load(self) -> None:
        data = await self._store.async_load()
        self._data = data or {}

    async def async_save(self) -> None:
        await self._store.async_save(self._data)

    def get_plant_state(self, plant_id: str) -> dict[str, Any]:
        return dict(self._data.get("plant_states", {}).get(plant_id, {}))

    def set_plant_state(self, plant_id: str, state: dict[str, Any]) -> None:
        self._data.setdefault("plant_states", {})[plant_id] = state

    def remove_plant_state(self, plant_id: str) -> None:
        self._data.get("plant_states", {}).pop(plant_id, None)

    def get_digest_markers(self) -> dict[str, str]:
        return dict(self._data.get("digest_markers", {}))

    def set_digest_marker(self, slot: str, date_str: str) -> None:
        self._data.setdefault("digest_markers", {})[slot] = date_str
