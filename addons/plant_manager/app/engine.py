from __future__ import annotations

from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from .models import (
    STATUS_ALERTS_DISABLED,
    STATUS_BATTERY_LOW,
    STATUS_DRY,
    STATUS_OK,
    STATUS_RECENTLY_WATERED,
    STATUS_SENSOR_UNAVAILABLE,
    Plant,
    PlantSnapshot,
)

BATTERY_LOW_THRESHOLD = 15.0
WATERING_CONFIRMATION_SECONDS = 300
PENDING_WATERING_TIMEOUT_SECONDS = 900


def now_utc() -> datetime:
    return datetime.now(timezone.utc)


def parse_float(value: object) -> float | None:
    if value in (None, "", "unknown", "unavailable"):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def parse_timestamp(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value)
    except ValueError:
        return None


def to_iso(dt: datetime | None) -> str | None:
    if dt is None:
        return None
    return dt.astimezone(timezone.utc).isoformat()


def days_since(value: str | None, *, now: datetime) -> int | None:
    parsed = parse_timestamp(value)
    if parsed is None:
        return None
    return max(0, int((now - parsed).total_seconds() // 86400))


def is_recently_watered(plant: Plant, *, now: datetime) -> bool:
    last_watered = parse_timestamp(plant.last_watered_at)
    if last_watered is None:
        return False
    minimum_window = max(1, plant.min_interval_days)
    return now - last_watered < timedelta(days=minimum_window)


def evaluate_status(
    plant: Plant,
    *,
    moisture: float | None,
    battery: float | None,
    now: datetime,
) -> PlantSnapshot:
    if not plant.alerts_enabled:
        status = STATUS_ALERTS_DISABLED
        needs_water = False
    elif moisture is None:
        status = STATUS_SENSOR_UNAVAILABLE
        needs_water = False
    elif is_recently_watered(plant, now=now):
        status = STATUS_RECENTLY_WATERED
        needs_water = False
    elif moisture < plant.low_threshold:
        status = STATUS_DRY
        needs_water = True
    elif battery is not None and battery <= BATTERY_LOW_THRESHOLD:
        status = STATUS_BATTERY_LOW
        needs_water = False
    else:
        status = STATUS_OK
        needs_water = False

    return PlantSnapshot(
        plant=plant,
        status=status,
        needs_water=needs_water,
        moisture=moisture,
        battery=battery,
        days_since_watered=days_since(plant.last_watered_at, now=now),
    )


def update_watering_detection(
    plant: Plant,
    *,
    moisture: float | None,
    now: datetime,
) -> tuple[dict[str, object], dict[str, object] | None]:
    updates: dict[str, object] = {}
    event: dict[str, object] | None = None

    pending_since = parse_timestamp(plant.pending_watering_since)
    previous_pending = plant.pending_previous_moisture

    if moisture is None:
        return updates, None

    if pending_since and previous_pending is not None:
        sustained = moisture - previous_pending >= plant.min_increase
        if sustained and (now - pending_since).total_seconds() >= WATERING_CONFIRMATION_SECONDS:
            updates.update(
                {
                    "last_watered_at": to_iso(now),
                    "last_notified_at": None,
                    "pending_watering_since": None,
                    "pending_previous_moisture": None,
                }
            )
            event = {
                "event_type": "auto_watered",
                "details": {
                    "previous_moisture": previous_pending,
                    "current_moisture": moisture,
                    "delta": round(moisture - previous_pending, 2),
                },
            }
        elif (now - pending_since).total_seconds() >= PENDING_WATERING_TIMEOUT_SECONDS:
            updates.update(
                {
                    "pending_watering_since": None,
                    "pending_previous_moisture": None,
                }
            )
    elif plant.last_moisture is not None and moisture - plant.last_moisture >= plant.min_increase:
        updates.update(
            {
                "pending_watering_since": to_iso(now),
                "pending_previous_moisture": plant.last_moisture,
            }
        )

    updates.update({"last_moisture": moisture, "last_moisture_at": to_iso(now)})
    return updates, event


def format_digest_message(snapshots: list[PlantSnapshot]) -> str:
    indoor = [snapshot for snapshot in snapshots if snapshot.plant.zone == "indoor"]
    outdoor = [snapshot for snapshot in snapshots if snapshot.plant.zone == "outdoor"]

    lines = ["Plants needing water:"]
    if indoor:
        lines.append("")
        lines.append("Indoor:")
        for snapshot in indoor:
            location = snapshot.plant.location_label or "Unassigned"
            lines.append(f"- {snapshot.plant.name} ({location}): {snapshot.moisture:.0f}%")
    if outdoor:
        lines.append("")
        lines.append("Outdoor:")
        for snapshot in outdoor:
            location = snapshot.plant.location_label or "Unassigned"
            lines.append(f"- {snapshot.plant.name} ({location}): {snapshot.moisture:.0f}%")
    return "\n".join(lines)


def due_for_digest(snapshot: PlantSnapshot) -> bool:
    if not snapshot.needs_water:
        return False
    if snapshot.plant.last_notified_at is None:
        return True

    last_notified = parse_timestamp(snapshot.plant.last_notified_at)
    last_watered = parse_timestamp(snapshot.plant.last_watered_at)
    if last_notified is None:
        return True
    if last_watered and last_watered > last_notified:
        return True
    return False


def reset_notification_suppression(plant: Plant, snapshot: PlantSnapshot) -> dict[str, object]:
    if snapshot.status == STATUS_DRY:
        return {}
    if plant.last_notified_at is None:
        return {}
    return {"last_notified_at": None}


def choose_timezone(configured_timezone: str | None, ha_timezone: str | None) -> timezone | ZoneInfo:
    name = configured_timezone or ha_timezone
    if not name:
        return timezone.utc
    try:
        return ZoneInfo(name)
    except ZoneInfoNotFoundError:
        return timezone.utc
