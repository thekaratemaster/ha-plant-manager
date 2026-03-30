from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Any
from uuid import uuid4

from .models import HistoryEvent, Plant


class PlantManagerStorage:
    _UPDATEABLE_COLUMNS = {
        "name",
        "zone",
        "location_label",
        "moisture_sensor_entity_id",
        "battery_sensor_entity_id",
        "low_threshold",
        "min_increase",
        "min_interval_days",
        "alerts_enabled",
        "notes",
        "last_watered_at",
        "last_notified_at",
        "updated_at",
        "last_moisture",
        "last_moisture_at",
        "pending_watering_since",
        "pending_previous_moisture",
        "current_status",
        "current_moisture",
        "current_battery",
        "needs_water",
    }

    def __init__(self, db_path: str | Path) -> None:
        self._db_path = str(db_path)

    def initialize(self) -> None:
        with self._connect() as conn:
            conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS plants (
                    id TEXT PRIMARY KEY,
                    name TEXT NOT NULL,
                    zone TEXT NOT NULL,
                    location_label TEXT NOT NULL,
                    moisture_sensor_entity_id TEXT NOT NULL,
                    battery_sensor_entity_id TEXT,
                    low_threshold REAL NOT NULL,
                    min_increase REAL NOT NULL,
                    min_interval_days INTEGER NOT NULL,
                    alerts_enabled INTEGER NOT NULL DEFAULT 1,
                    notes TEXT,
                    last_watered_at TEXT,
                    last_notified_at TEXT,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    last_moisture REAL,
                    last_moisture_at TEXT,
                    pending_watering_since TEXT,
                    pending_previous_moisture REAL,
                    current_status TEXT,
                    current_moisture REAL,
                    current_battery REAL,
                    needs_water INTEGER NOT NULL DEFAULT 0
                );

                CREATE TABLE IF NOT EXISTS history_events (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    plant_id TEXT,
                    event_type TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    details TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS settings (
                    key TEXT PRIMARY KEY,
                    value TEXT NOT NULL
                );
                """
            )

    def list_plants(self) -> list[Plant]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT * FROM plants ORDER BY zone ASC, name COLLATE NOCASE ASC"
            ).fetchall()
        return [self._row_to_plant(row) for row in rows]

    def get_plant(self, plant_id: str) -> Plant | None:
        with self._connect() as conn:
            row = conn.execute("SELECT * FROM plants WHERE id = ?", (plant_id,)).fetchone()
        return self._row_to_plant(row) if row else None

    def create_plant(self, payload: dict[str, Any]) -> Plant:
        plant_id = payload.get("id") or str(uuid4())
        values = {
            "id": plant_id,
            "name": payload["name"].strip(),
            "zone": payload["zone"],
            "location_label": payload.get("location_label", "").strip(),
            "moisture_sensor_entity_id": payload["moisture_sensor_entity_id"].strip(),
            "battery_sensor_entity_id": self._optional_str(payload.get("battery_sensor_entity_id")),
            "low_threshold": float(payload["low_threshold"]),
            "min_increase": float(payload["min_increase"]),
            "min_interval_days": int(payload["min_interval_days"]),
            "alerts_enabled": 1 if payload.get("alerts_enabled", True) else 0,
            "notes": self._optional_str(payload.get("notes")),
            "last_watered_at": payload.get("last_watered_at"),
            "last_notified_at": payload.get("last_notified_at"),
            "created_at": payload["created_at"],
            "updated_at": payload["updated_at"],
        }

        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO plants (
                    id, name, zone, location_label, moisture_sensor_entity_id,
                    battery_sensor_entity_id, low_threshold, min_increase,
                    min_interval_days, alerts_enabled, notes, last_watered_at,
                    last_notified_at, created_at, updated_at
                ) VALUES (
                    :id, :name, :zone, :location_label, :moisture_sensor_entity_id,
                    :battery_sensor_entity_id, :low_threshold, :min_increase,
                    :min_interval_days, :alerts_enabled, :notes, :last_watered_at,
                    :last_notified_at, :created_at, :updated_at
                )
                """,
                values,
            )
        plant = self.get_plant(plant_id)
        assert plant is not None
        return plant

    def update_plant(self, plant_id: str, changes: dict[str, Any]) -> Plant | None:
        if not changes:
            return self.get_plant(plant_id)

        normalized = self._normalize_changes(changes)
        assignments = [f"{key} = ?" for key in normalized]
        values = list(normalized.values()) + [plant_id]

        with self._connect() as conn:
            conn.execute(
                f"UPDATE plants SET {', '.join(assignments)} WHERE id = ?",
                tuple(values),
            )
        return self.get_plant(plant_id)

    def append_history(
        self,
        *,
        plant_id: str | None,
        event_type: str,
        created_at: str,
        details: dict[str, Any],
    ) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO history_events (plant_id, event_type, created_at, details)
                VALUES (?, ?, ?, ?)
                """,
                (plant_id, event_type, created_at, json.dumps(details, sort_keys=True)),
            )

    def list_history(self, plant_id: str | None = None) -> list[HistoryEvent]:
        sql = (
            "SELECT id, plant_id, event_type, created_at, details FROM history_events "
            "ORDER BY created_at DESC, id DESC"
        )
        params: tuple[Any, ...] = ()
        if plant_id:
            sql = (
                "SELECT id, plant_id, event_type, created_at, details FROM history_events "
                "WHERE plant_id = ? ORDER BY created_at DESC, id DESC"
            )
            params = (plant_id,)

        with self._connect() as conn:
            rows = conn.execute(sql, params).fetchall()
        return [
            HistoryEvent(
                id=row["id"],
                plant_id=row["plant_id"],
                event_type=row["event_type"],
                created_at=row["created_at"],
                details=json.loads(row["details"]),
            )
            for row in rows
        ]

    def get_settings(self) -> dict[str, Any]:
        with self._connect() as conn:
            rows = conn.execute("SELECT key, value FROM settings").fetchall()
        settings: dict[str, Any] = {}
        for row in rows:
            try:
                settings[row["key"]] = json.loads(row["value"])
            except json.JSONDecodeError:
                settings[row["key"]] = row["value"]
        return settings

    def set_settings(self, values: dict[str, Any]) -> dict[str, Any]:
        with self._connect() as conn:
            for key, value in values.items():
                conn.execute(
                    """
                    INSERT INTO settings (key, value)
                    VALUES (?, ?)
                    ON CONFLICT(key) DO UPDATE SET value = excluded.value
                    """,
                    (key, json.dumps(value)),
                )
        return self.get_settings()

    def _normalize_changes(self, changes: dict[str, Any]) -> dict[str, Any]:
        normalized: dict[str, Any] = {}
        for key, value in changes.items():
            if key not in self._UPDATEABLE_COLUMNS:
                continue
            if key in {"alerts_enabled", "needs_water"} and value is not None:
                normalized[key] = 1 if value else 0
            elif key in {"battery_sensor_entity_id", "notes"}:
                normalized[key] = self._optional_str(value)
            else:
                normalized[key] = value
        return normalized

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self._db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _row_to_plant(self, row: sqlite3.Row) -> Plant:
        return Plant(
            id=row["id"],
            name=row["name"],
            zone=row["zone"],
            location_label=row["location_label"],
            moisture_sensor_entity_id=row["moisture_sensor_entity_id"],
            battery_sensor_entity_id=row["battery_sensor_entity_id"],
            low_threshold=float(row["low_threshold"]),
            min_increase=float(row["min_increase"]),
            min_interval_days=int(row["min_interval_days"]),
            alerts_enabled=bool(row["alerts_enabled"]),
            notes=row["notes"],
            last_watered_at=row["last_watered_at"],
            last_notified_at=row["last_notified_at"],
            created_at=row["created_at"],
            updated_at=row["updated_at"],
            last_moisture=row["last_moisture"],
            last_moisture_at=row["last_moisture_at"],
            pending_watering_since=row["pending_watering_since"],
            pending_previous_moisture=row["pending_previous_moisture"],
            current_status=row["current_status"],
            current_moisture=row["current_moisture"],
            current_battery=row["current_battery"],
            needs_water=bool(row["needs_water"]),
        )

    @staticmethod
    def _optional_str(value: Any) -> str | None:
        if value is None:
            return None
        text = str(value).strip()
        return text or None
