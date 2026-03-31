from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any


STATUS_OK = "ok"
STATUS_DRY = "dry"
STATUS_RECENTLY_WATERED = "recently_watered"
STATUS_SENSOR_UNAVAILABLE = "sensor_unavailable"
STATUS_BATTERY_LOW = "battery_low"
STATUS_ALERTS_DISABLED = "alerts_disabled"


@dataclass(slots=True)
class Plant:
    id: str
    name: str
    zone: str
    location_label: str
    moisture_sensor_entity_id: str
    battery_sensor_entity_id: str | None
    low_threshold: float
    battery_low_threshold: float
    min_increase: float
    min_interval_days: int
    alerts_enabled: bool
    notes: str | None
    last_watered_at: str | None
    last_notified_at: str | None
    created_at: str
    updated_at: str
    last_moisture: float | None = None
    last_moisture_at: str | None = None
    pending_watering_since: str | None = None
    pending_previous_moisture: float | None = None
    current_status: str | None = None
    current_moisture: float | None = None
    current_battery: float | None = None
    needs_water: bool = False

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class PlantSnapshot:
    plant: Plant
    status: str
    needs_water: bool
    moisture: float | None
    battery: float | None
    days_since_watered: int | None

    def to_dict(self) -> dict[str, Any]:
        payload = self.plant.to_dict()
        payload.update(
            {
                "status": self.status,
                "needs_water": self.needs_water,
                "current_moisture": self.moisture,
                "current_battery": self.battery,
                "days_since_watered": self.days_since_watered,
            }
        )
        return payload
