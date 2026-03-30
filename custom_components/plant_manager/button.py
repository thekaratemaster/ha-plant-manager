from __future__ import annotations

from homeassistant.components.button import ButtonEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from .coordinator import PlantManagerCoordinator
from .entity import PlantManagerPlantEntity


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    runtime = hass.data[DOMAIN][entry.entry_id]
    coordinator: PlantManagerCoordinator = runtime["coordinator"]
    known_ids: set[str] = set()

    def build_entities():
        entities = []
        for plant_id in coordinator.data.get("plants", {}):
            if plant_id in known_ids:
                continue
            known_ids.add(plant_id)
            entities.append(PlantMarkWateredButton(runtime["api"], coordinator, entry.entry_id, plant_id))
        return entities

    async_add_entities(build_entities())

    @callback
    def _handle_update() -> None:
        new_entities = build_entities()
        if new_entities:
            async_add_entities(new_entities)

    entry.async_on_unload(coordinator.async_add_listener(_handle_update))


class PlantMarkWateredButton(PlantManagerPlantEntity, ButtonEntity):
    def __init__(self, api, coordinator: PlantManagerCoordinator, entry_id: str, plant_id: str) -> None:
        super().__init__(coordinator, entry_id, plant_id, "mark_watered")
        self._api = api
        self._attr_name = "Mark watered"

    async def async_press(self) -> None:
        await self._api.mark_watered(self._plant_id)
        await self.coordinator.async_request_refresh()
