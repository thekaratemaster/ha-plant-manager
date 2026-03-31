from __future__ import annotations

from homeassistant.components.sensor import SensorDeviceClass, SensorEntity, SensorStateClass
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import PERCENTAGE, UnitOfTime
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .coordinator import PlantManagerCoordinator
from .entity import PlantManagerBaseEntity, PlantManagerPlantEntity, parse_iso_datetime
from .const import DOMAIN


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    runtime = hass.data[DOMAIN][entry.entry_id]
    coordinator: PlantManagerCoordinator = runtime["coordinator"]
    known_ids: set[str] = set()

    def build_entities() -> list[SensorEntity]:
        new_entities: list[SensorEntity] = []
        for plant_id in coordinator.data.get("plants", {}):
            if plant_id in known_ids:
                continue
            known_ids.add(plant_id)
            new_entities.extend(
                [
                    PlantStatusSensor(coordinator, entry.entry_id, plant_id),
                    PlantMoistureSensor(coordinator, entry.entry_id, plant_id),
                    PlantLastWateredSensor(coordinator, entry.entry_id, plant_id),
                    PlantDaysSinceWateredSensor(coordinator, entry.entry_id, plant_id),
                ]
            )
        return new_entities

    async_add_entities(
        [
            PlantManagerAggregateSensor(coordinator, entry.entry_id, "plants_needing_water", "Plants needing water"),
            PlantManagerAggregateSensor(coordinator, entry.entry_id, "indoor_needing_water", "Indoor needing water"),
            PlantManagerAggregateSensor(coordinator, entry.entry_id, "outdoor_needing_water", "Outdoor needing water"),
            *build_entities(),
        ]
    )

    @callback
    def _handle_update() -> None:
        new_entities = build_entities()
        if new_entities:
            async_add_entities(new_entities)

    entry.async_on_unload(coordinator.async_add_listener(_handle_update))


class PlantManagerAggregateSensor(PlantManagerBaseEntity, SensorEntity):
    def __init__(self, coordinator: PlantManagerCoordinator, entry_id: str, key: str, name: str) -> None:
        super().__init__(coordinator, entry_id)
        self._key = key
        self._attr_unique_id = f"{entry_id}_{key}"
        self._attr_name = name
        self._attr_native_unit_of_measurement = None
        self._attr_state_class = SensorStateClass.MEASUREMENT

    @property
    def native_value(self):
        return self.coordinator.data.get("summary", {}).get(self._key, 0)


class PlantStatusSensor(PlantManagerPlantEntity, SensorEntity):
    def __init__(self, coordinator: PlantManagerCoordinator, entry_id: str, plant_id: str) -> None:
        super().__init__(coordinator, entry_id, plant_id, "status")
        self._attr_name = "Status"

    @property
    def native_value(self):
        plant = self.plant or {}
        return plant.get("status") or plant.get("current_status")


class PlantMoistureSensor(PlantManagerPlantEntity, SensorEntity):
    _attr_native_unit_of_measurement = PERCENTAGE
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_suggested_display_precision = 0

    def __init__(self, coordinator: PlantManagerCoordinator, entry_id: str, plant_id: str) -> None:
        super().__init__(coordinator, entry_id, plant_id, "moisture")
        self._attr_name = "Moisture"

    @property
    def native_value(self):
        plant = self.plant or {}
        return plant.get("current_moisture")


class PlantLastWateredSensor(PlantManagerPlantEntity, SensorEntity):
    _attr_device_class = SensorDeviceClass.TIMESTAMP

    def __init__(self, coordinator: PlantManagerCoordinator, entry_id: str, plant_id: str) -> None:
        super().__init__(coordinator, entry_id, plant_id, "last_watered")
        self._attr_name = "Last watered"

    @property
    def native_value(self):
        plant = self.plant or {}
        return parse_iso_datetime(plant.get("last_watered_at"))


class PlantDaysSinceWateredSensor(PlantManagerPlantEntity, SensorEntity):
    _attr_native_unit_of_measurement = UnitOfTime.DAYS
    _attr_state_class = SensorStateClass.MEASUREMENT

    def __init__(self, coordinator: PlantManagerCoordinator, entry_id: str, plant_id: str) -> None:
        super().__init__(coordinator, entry_id, plant_id, "days_since_watered")
        self._attr_name = "Days since watered"

    @property
    def native_value(self):
        plant = self.plant or {}
        return plant.get("days_since_watered")
