# Plant Manager Add-on

Plant Manager is a Home Assistant add-on and companion integration for managing all indoor and outdoor plants from one place.

## What it does

- Tracks all plants in a single list
- Polls Home Assistant moisture and battery entities
- Detects watering from sustained moisture increases
- Records manual and automatic watering history
- Sends grouped digest notifications for dry plants
- Exposes plant state to Home Assistant through the companion `plant_manager` integration

## Home Assistant pairing

The add-on provides the UI and storage. The custom component in `custom_components/plant_manager/` mirrors plant status into Home Assistant entities and services.

## Default boot options

- Digest time: `07:00`
- Poll interval: `60` seconds
- Notify service: unset until configured

## Migration

Keep the existing `plant_watering_revised.yaml` blueprint automations during setup, add plants manually in Plant Manager, verify results, then retire the old per-plant blueprint instances one by one.
