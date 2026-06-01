Monitor your houseplants using any moisture sensor already in Home Assistant. The integration works with any sensor entity that reports a numeric state — Z-Wave, Zigbee, Wi-Fi, Ecowitt (915 MHz), SDR, Bluetooth, or any other protocol your HA setup uses.

## Features

- Assign any HA sensor entity as a plant's moisture source — no protocol restrictions
- Auto-detects watering events when moisture rises and holds for 5 minutes (configurable threshold)
- Optional battery sensor per plant, supporting both percentage and voltage readings
- Daily digest notifications via any HA notify service at configured times
- Optional Google Calendar logging — creates an all-day "Water {plant}" event when a digest fires
- Auto-populating Lovelace dashboard (requires [auto-entities](https://github.com/thomasloven/lovelace-auto-entities))
- Full UI configuration — no YAML editing required

## Entities per plant

| Entity | Description |
|--------|-------------|
| `sensor.*_status` | ok / dry / recently_watered / sensor_unavailable / battery_low / alerts_disabled |
| `sensor.*_moisture` | Current soil moisture (%) |
| `sensor.*_last_watered` | Timestamp of last watering |
| `sensor.*_days_since_watered` | Days since last watering |
| `binary_sensor.*_needs_water` | True when plant is dry and due for a notification |
| `button.*_mark_watered` | Manually log a watering event |

## Aggregate sensors

| Entity | Description |
|--------|-------------|
| `sensor.plant_manager_plants_needing_water` | Total plants needing water |
| `sensor.plant_manager_indoor_needing_water` | Indoor plants needing water |
| `sensor.plant_manager_outdoor_needing_water` | Outdoor plants needing water |

## Setup

After installing and restarting HA, go to **Settings → Integrations → + Add Integration → Plant Manager**.

Configure a notify service and digest times, then add plants. Each plant is assigned a moisture sensor entity from your existing HA setup — the picker shows all sensor entities so you select whatever you already have.

## Battery sensors

The battery threshold accepts either a percentage (e.g. `15` for most sensors) or a voltage (e.g. `1.1` for sensors like the Ecowitt WH51 that report raw battery voltage). The integration distinguishes between the two based on the value you enter.
