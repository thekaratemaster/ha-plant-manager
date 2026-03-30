from __future__ import annotations

from homeassistant.const import Platform

DOMAIN = "plant_manager"

CONF_BASE_URL = "base_url"
CONF_SCAN_INTERVAL = "scan_interval"

DEFAULT_BASE_URL = "http://plant_manager:8099"
DEFAULT_SCAN_INTERVAL = 60

SERVICE_MARK_WATERED = "mark_watered"
SERVICE_REFRESH = "refresh"
SERVICE_SEND_DIGEST_NOW = "send_digest_now"

ATTR_PLANT_ID = "plant_id"
ATTR_ENTRY_ID = "entry_id"

PLATFORMS: list[Platform] = [
    Platform.SENSOR,
    Platform.BINARY_SENSOR,
    Platform.BUTTON,
]
