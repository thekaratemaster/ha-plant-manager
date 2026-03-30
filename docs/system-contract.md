# System Contract

## Add-on to integration API

Base behavior expected by the integration:
- `GET /health`
- `GET /plants`
- `GET /summary`
- `POST /plants/{plant_id}/mark_watered`
- `POST /digest/send`

## Home Assistant side

The companion integration mirrors plant state into Home Assistant entities and exposes actions based on the add-on API.

Expected entity groups include:
- per-plant status sensors
- per-plant last-watered sensors
- per-plant needs-water binary sensors
- mark-watered buttons
- aggregate summary sensors

## Compatibility expectations

- API endpoints above are treated as the internal contract used by the companion integration
- plant payload shape and summary data should only change with coordinated updates and migration notes
- add-on and integration releases should stay aligned
