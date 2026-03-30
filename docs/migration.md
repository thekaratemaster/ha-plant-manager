# Migration

Plant Manager is intended to replace the older one-blueprint-per-plant workflow.

Recommended migration path:

1. Install the add-on and companion integration.
2. Add plants manually in Plant Manager.
3. Verify Plant Manager entities in Home Assistant.
4. Keep old `plant_watering_revised.yaml` automations active during overlap.
5. Retire old blueprint instances one plant at a time after validation.
