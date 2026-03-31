# ha-plant-manager

Plant Manager is a Home Assistant custom integration for monitoring plant soil moisture, detecting watering events, and sending scheduled digest notifications.

## Architecture

This is a **standalone custom integration** — no Docker addon, no separate process. Everything runs inside Home Assistant's event loop.

```
custom_components/plant_manager/   ← the integration
dashboard/plant_manager.yaml       ← optional auto-populating dashboard
tests/plant_manager/               ← unit tests
```

## How it works

- Subscribes to `state_changed` events for each plant's moisture (and optionally battery) sensor
- Watering is auto-detected when moisture rises by `min_increase` % and stays elevated for 5 minutes
- Daily digest notifications sent via any HA notify service at configured times
- Optional Google Calendar event created (all-day "Water {plant}") when a plant is included in a digest
- All plant config and runtime state persisted in HA's `.storage/plant_manager` store

## Installing via HACS

1. In HA: **HACS** → 3-dot menu → **Custom repositories**
2. URL: `https://github.com/thekaratemaster/ha-plant-manager` — Category: **Integration** → Add
3. Search "Plant Manager" in HACS → **Download**
4. Restart HA
5. **Settings → Integrations → + Add Integration → Plant Manager**

## Updating via HACS

When a new release is published on GitHub, HACS will show an update badge. Click it → **Update** → restart HA.

## Manual install (without HACS)

Copy `custom_components/plant_manager/` into your HA config's `custom_components/` folder, then restart HA and add the integration.

## Setting up

Go to **Settings → Integrations → Plant Manager → Configure**

- **Add a plant** — name, zone (indoor/outdoor), location, moisture sensor, optional battery sensor + Google Calendar
- **Edit a plant** — update any field at any time including thresholds and calendar
- **Remove a plant** — removes the plant and all its HA entities/devices
- **Notification settings** — notify service + digest times

## Entities per plant

Each plant appears as a device in HA with the following entities:

| Entity | Type | Description |
|--------|------|-------------|
| `sensor.*_status` | Sensor | ok / dry / recently_watered / sensor_unavailable / battery_low / alerts_disabled |
| `sensor.*_moisture` | Sensor (%) | Current soil moisture reading |
| `sensor.*_last_watered` | Sensor (timestamp) | When the plant was last watered |
| `sensor.*_days_since_watered` | Sensor (days) | Days since last watering |
| `binary_sensor.*_needs_water` | Binary sensor | True when dry and due for a notification |
| `button.*_mark_watered` | Button | Manually log a watering event |

## Aggregate sensors (hub device)

| Entity | Description |
|--------|-------------|
| `sensor.plant_manager_plants_needing_water` | Total plants currently needing water |
| `sensor.plant_manager_indoor_needing_water` | Indoor plants needing water |
| `sensor.plant_manager_outdoor_needing_water` | Outdoor plants needing water |

## Services

| Service | Fields | Description |
|---------|--------|-------------|
| `plant_manager.mark_watered` | `plant_id` | Mark a specific plant as watered |
| `plant_manager.send_digest_now` | — | Send a digest notification immediately (only fires if plants are dry) |

## Dashboard

An auto-populating dashboard is included at `dashboard/plant_manager.yaml`. It requires the [auto-entities](https://github.com/thomasloven/lovelace-auto-entities) card from HACS (Frontend).

Plants appear and disappear automatically as you add or remove them from the integration — no manual dashboard edits needed.

To add it in HA: **Settings → Dashboards → Add Dashboard** → open it → 3-dot menu → Edit → Raw config editor → paste the contents of `dashboard/plant_manager.yaml`.

## Battery threshold

Supports both percentage-based and voltage-based battery sensors:
- **Percentage sensors** (most): enter e.g. `15` (%)
- **Voltage sensors** (e.g. Ecowitt WH51 AA battery): enter e.g. `1.1` (volts)

The threshold is configured per plant in the Add/Edit plant form.

## Notification format

Digest notifications list all dry plants grouped by zone:

```
Plant Manager — 2 plants need water

Indoor:
• Spider Plant (Office) — 18% moisture, 8 days since watered

Outdoor:
• Rosemary (Back Garden) — 9% moisture, 14 days since watered
```

## Running tests

```bash
python -m pytest tests/ -v
```
