from __future__ import annotations

from homeassistant.const import Platform

DOMAIN = "plant_manager"

# Settings keys (stored in config entry options)
CONF_NOTIFY_SERVICE = "notify_service"
CONF_DIGEST_TIMES = "digest_times"
CONF_PLANTS = "plants"

# Per-plant config field keys
CONF_PLANT_NAME = "name"
CONF_PLANT_ZONE = "zone"
CONF_PLANT_LOCATION = "location_label"
CONF_MOISTURE_ENTITY = "moisture_sensor_entity_id"
CONF_BATTERY_ENTITY = "battery_sensor_entity_id"
CONF_LOW_THRESHOLD = "low_threshold"
CONF_MIN_INCREASE = "min_increase"
CONF_MIN_INTERVAL_DAYS = "min_interval_days"
CONF_ALERTS_ENABLED = "alerts_enabled"
CONF_PLANT_NOTES = "notes"

# Defaults
DEFAULT_NOTIFY_SERVICE = ""
DEFAULT_DIGEST_TIMES = "07:00"
DEFAULT_LOW_THRESHOLD = 30.0
DEFAULT_MIN_INCREASE = 15.0
DEFAULT_MIN_INTERVAL_DAYS = 3

# Services
SERVICE_MARK_WATERED = "mark_watered"
SERVICE_SEND_DIGEST_NOW = "send_digest_now"

ATTR_PLANT_ID = "plant_id"

# Storage
STORAGE_KEY = "plant_manager"
STORAGE_VERSION = 1

PLATFORMS: list[Platform] = [
    Platform.SENSOR,
    Platform.BINARY_SENSOR,
    Platform.BUTTON,
]
