from __future__ import annotations

from datetime import datetime
from typing import Any

from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .coordinator import PlantManagerCoordinator
from .const import DOMAIN


def parse_iso_datetime(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value)
    except ValueError:
        return None


class PlantManagerBaseEntity(CoordinatorEntity[PlantManagerCoordinator]):
    _attr_has_entity_name = True

    def __init__(self, coordinator: PlantManagerCoordinator, entry_id: str) -> None:
        super().__init__(coordinator)
        self._entry_id = entry_id

    @property
    def device_info(self) -> DeviceInfo:
        return DeviceInfo(
            identifiers={(DOMAIN, self._entry_id)},
            name="Plant Manager",
            manufacturer="Custom",
            model="Plant Manager Hub",
        )


class PlantManagerPlantEntity(PlantManagerBaseEntity):
    def __init__(
        self,
        coordinator: PlantManagerCoordinator,
        entry_id: str,
        plant_id: str,
        entity_suffix: str,
    ) -> None:
        super().__init__(coordinator, entry_id)
        self._plant_id = plant_id
        self._attr_unique_id = f"{entry_id}_{plant_id}_{entity_suffix}"

    @property
    def plant(self) -> dict[str, Any] | None:
        return self.coordinator.data.get("plants", {}).get(self._plant_id)

    @property
    def available(self) -> bool:
        return super().available and self.plant is not None

    @property
    def device_info(self) -> DeviceInfo:
        plant = self.plant or {"name": "Plant"}
        return DeviceInfo(
            identifiers={(DOMAIN, self._plant_id)},
            name=plant.get("name", "Plant"),
            manufacturer="Custom",
            model="Plant Manager Plant",
            via_device=(DOMAIN, self._entry_id),
        )

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        plant = self.plant or {}
        return {
            "plant_id": self._plant_id,
            "zone": plant.get("zone"),
            "location_label": plant.get("location_label"),
            "moisture_sensor_entity_id": plant.get("moisture_sensor_entity_id"),
            "battery_sensor_entity_id": plant.get("battery_sensor_entity_id"),
            "low_threshold": plant.get("low_threshold"),
            "min_increase": plant.get("min_increase"),
            "min_interval_days": plant.get("min_interval_days"),
            "current_moisture": plant.get("current_moisture"),
            "current_battery": plant.get("current_battery"),
        }
