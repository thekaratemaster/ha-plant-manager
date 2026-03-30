# ha-plant-manager

Plant Manager is a combined Home Assistant project with a Supervisor add-on and a companion integration.

## Contents

- `addons/plant_manager/` - add-on app, API, storage, and UI
- `custom_components/plant_manager/` - companion integration for Home Assistant entities and services
- `tests/plant_manager/` - tests covering both sides of the system
- `docs/system-contract.md` - API and entity contract between add-on and integration
- `docs/migration.md` - migration guidance from the old blueprint-based workflow

## Notes

This repo is the source of truth for the whole Plant Manager system. The add-on and custom integration are versioned together because they depend on each other.
