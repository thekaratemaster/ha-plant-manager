from __future__ import annotations

from datetime import timedelta
import importlib.util
from pathlib import Path
import sys
import types
import unittest

ROOT = Path(__file__).resolve().parents[2]
PKG_DIR = ROOT / "custom_components" / "plant_manager"
PKG_NAME = "test_plant_manager_addon"


def _load_module(module_name: str, path: Path):
    spec = importlib.util.spec_from_file_location(module_name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def load_addon_modules():
    if PKG_NAME not in sys.modules:
        package = types.ModuleType(PKG_NAME)
        package.__path__ = [str(PKG_DIR)]
        sys.modules[PKG_NAME] = package

    models = _load_module(f"{PKG_NAME}.models", PKG_DIR / "models.py")
    engine = _load_module(f"{PKG_NAME}.engine", PKG_DIR / "engine.py")
    return models, engine


models, engine = load_addon_modules()


class PlantManagerEngineTests(unittest.TestCase):
    def _make_plant(self, **overrides):
        now = engine.to_iso(engine.now_utc())
        payload = {
            "id": "plant-1",
            "name": "Spider Plant",
            "zone": "indoor",
            "location_label": "Office",
            "moisture_sensor_entity_id": "sensor.office_plant_moisture",
            "battery_sensor_entity_id": "sensor.office_plant_battery",
            "low_threshold": 25.0,
            "min_increase": 5.0,
            "min_interval_days": 1,
            "alerts_enabled": True,
            "notes": None,
            "last_watered_at": None,
            "last_notified_at": None,
            "created_at": now,
            "updated_at": now,
            "last_moisture": None,
            "last_moisture_at": None,
            "pending_watering_since": None,
            "pending_previous_moisture": None,
            "current_status": None,
            "current_moisture": None,
            "current_battery": None,
            "needs_water": False,
        }
        payload.update(overrides)
        return models.Plant(**payload)

    def test_evaluate_status_prefers_dry_when_below_threshold(self) -> None:
        plant = self._make_plant()
        snapshot = engine.evaluate_status(plant, moisture=18.0, battery=10.0, now=engine.now_utc())

        self.assertEqual(snapshot.status, models.STATUS_DRY)
        self.assertTrue(snapshot.needs_water)

    def test_evaluate_status_marks_recently_watered_within_interval(self) -> None:
        watered_at = engine.to_iso(engine.now_utc() - timedelta(hours=4))
        plant = self._make_plant(last_watered_at=watered_at, min_interval_days=2)

        snapshot = engine.evaluate_status(plant, moisture=10.0, battery=80.0, now=engine.now_utc())

        self.assertEqual(snapshot.status, models.STATUS_RECENTLY_WATERED)
        self.assertFalse(snapshot.needs_water)

    def test_evaluate_status_handles_disabled_alerts(self) -> None:
        plant = self._make_plant(alerts_enabled=False)

        snapshot = engine.evaluate_status(plant, moisture=10.0, battery=80.0, now=engine.now_utc())

        self.assertEqual(snapshot.status, models.STATUS_ALERTS_DISABLED)
        self.assertFalse(snapshot.needs_water)

    def test_update_watering_detection_confirms_sustained_increase(self) -> None:
        plant = self._make_plant(last_moisture=20.0)
        started_at = engine.now_utc()
        first_updates, first_event = engine.update_watering_detection(plant, moisture=27.0, now=started_at)

        self.assertIsNone(first_event)
        self.assertIsNotNone(first_updates["pending_watering_since"])

        confirmed_plant = self._make_plant(
            last_moisture=27.0,
            pending_watering_since=first_updates["pending_watering_since"],
            pending_previous_moisture=20.0,
        )
        second_updates, second_event = engine.update_watering_detection(
            confirmed_plant,
            moisture=28.0,
            now=started_at + timedelta(minutes=6),
        )

        self.assertEqual(second_event["event_type"], "auto_watered")
        self.assertIsNotNone(second_updates["last_watered_at"])
        self.assertIsNone(second_updates["last_notified_at"])

    def test_digest_message_groups_indoor_and_outdoor(self) -> None:
        indoor = engine.evaluate_status(self._make_plant(name="Fern", zone="indoor"), moisture=12.0, battery=90.0, now=engine.now_utc())
        outdoor = engine.evaluate_status(self._make_plant(id="plant-2", name="Rosemary", zone="outdoor"), moisture=9.0, battery=90.0, now=engine.now_utc())

        message = engine.format_digest_message([indoor, outdoor])

        self.assertIn("Indoor:", message)
        self.assertIn("Outdoor:", message)
        self.assertIn("Fern", message)
        self.assertIn("Rosemary", message)


if __name__ == "__main__":
    unittest.main()
