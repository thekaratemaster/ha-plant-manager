# ha-plant-manager

Plant Manager is a Home Assistant custom integration for monitoring plant soil moisture, detecting watering events, and sending scheduled digest notifications.

## Architecture

This is a **standalone custom integration** — no Docker addon, no separate process. Everything runs inside Home Assistant's event loop.

```
custom_components/plant_manager/   ← copy this to /config/custom_components/
tests/plant_manager/               ← unit tests
```

## How it works

- Subscribes to `state_changed` events for each plant's moisture (and optionally battery) sensor
- Watering is auto-detected when moisture rises by `min_increase` % and stays elevated for 5 minutes
- Daily digest notifications sent via any HA notify service at configured times
- Optional Google Calendar event created when a plant needs water
- All plant config and runtime state persisted in HA's `.storage/plant_manager` store

## Installing on Home Assistant

```bash
# In Studio Code Server terminal:
cd /config/ha-plant-manager && git pull
cp -r custom_components/plant_manager /config/custom_components/
```

Then restart HA, go to **Settings → Integrations → + Add Integration → Plant Manager**.

## Updating

```bash
cd /config/ha-plant-manager && git pull
cp -r custom_components/plant_manager /config/custom_components/
```

Then **Settings → Integrations → Plant Manager → ⋮ → Reload**.

## Managing plants

**Settings → Integrations → Plant Manager → Configure**

- **Add a plant** — name, zone, moisture sensor, optional battery + calendar
- **Edit a plant** — update any field including adding a calendar after the fact
- **Remove a plant** — removes the plant and cleans up all its HA entities/devices
- **Notification settings** — notify service + digest times

## Entities per plant

| Entity | Type | Description |
|--------|------|-------------|
| `sensor.*_status` | Sensor | ok / dry / recently_watered / sensor_unavailable / battery_low / alerts_disabled |
| `sensor.*_last_watered` | Sensor (timestamp) | When last watered |
| `sensor.*_days_since_watered` | Sensor (days) | Days since last watering |
| `binary_sensor.*_needs_water` | Binary sensor | True when dry and due for notification |
| `button.*_mark_watered` | Button | Manually log a watering event |

## Services

| Service | Description |
|---------|-------------|
| `plant_manager.mark_watered` | Mark a plant watered by plant_id |
| `plant_manager.send_digest_now` | Send digest notification immediately |

## Known issues / TODO

- Battery threshold is hardcoded as a percentage (15%). Plants with **voltage-based battery sensors** (e.g. 1.3V AA) always show `battery_low`. Fix planned: configurable threshold per plant.
- Digest not confirmed working in production yet — needs testing with a dry plant at scheduled time.

## Running tests

```bash
python -m pytest tests/ -v
```
