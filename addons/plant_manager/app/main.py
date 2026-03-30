from __future__ import annotations

from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, Field

from .ha_client import HomeAssistantApiClient
from .service import PlantManagerService
from .storage import PlantManagerStorage

DB_PATH = Path("/data/plant_manager.db")


class PlantCreateRequest(BaseModel):
    name: str = Field(min_length=1)
    zone: str = Field(regex="^(indoor|outdoor)$")
    location_label: str = ""
    moisture_sensor_entity_id: str = Field(min_length=1)
    battery_sensor_entity_id: str | None = None
    low_threshold: float = Field(ge=0, le=100)
    min_increase: float = Field(ge=1, le=100)
    min_interval_days: int = Field(ge=1, le=90)
    alerts_enabled: bool = True
    notes: str | None = None


class PlantUpdateRequest(BaseModel):
    name: str | None = None
    zone: str | None = Field(default=None, regex="^(indoor|outdoor)$")
    location_label: str | None = None
    moisture_sensor_entity_id: str | None = None
    battery_sensor_entity_id: str | None = None
    low_threshold: float | None = Field(default=None, ge=0, le=100)
    min_increase: float | None = Field(default=None, ge=1, le=100)
    min_interval_days: int | None = Field(default=None, ge=1, le=90)
    alerts_enabled: bool | None = None
    notes: str | None = None


class SettingsUpdateRequest(BaseModel):
    default_notify_service: str | None = None
    digest_schedule_times: list[str] | str | None = None
    poll_interval: int | None = Field(default=None, ge=15, le=3600)
    timezone: str | None = None


app = FastAPI(title="Plant Manager")


@app.on_event("startup")
async def _startup() -> None:
    storage = PlantManagerStorage(DB_PATH)
    service = PlantManagerService(storage=storage, ha_client=HomeAssistantApiClient())
    await service.start()
    app.state.service = service


@app.on_event("shutdown")
async def _shutdown() -> None:
    service: PlantManagerService = app.state.service
    await service.stop()


def get_service(request: Request) -> PlantManagerService:
    return request.app.state.service


@app.get("/", response_class=HTMLResponse)
async def index() -> str:
    return INDEX_HTML


@app.get("/health")
async def health(request: Request) -> dict[str, Any]:
    service = get_service(request)
    return {"ok": True, "summary": await service.get_summary()}


@app.get("/settings")
async def get_settings(request: Request) -> dict[str, Any]:
    return get_service(request).get_settings()


@app.patch("/settings")
async def update_settings(request: Request, payload: SettingsUpdateRequest) -> dict[str, Any]:
    return get_service(request).set_settings(payload.dict(exclude_none=True))


@app.get("/plants")
async def list_plants(request: Request) -> list[dict[str, Any]]:
    return await get_service(request).list_plants()


@app.get("/plants/{plant_id}")
async def get_plant(request: Request, plant_id: str) -> dict[str, Any]:
    plant = await get_service(request).get_plant(plant_id)
    if plant is None:
        raise HTTPException(status_code=404, detail="Plant not found")
    return plant


@app.post("/plants")
async def create_plant(request: Request, payload: PlantCreateRequest) -> dict[str, Any]:
    return get_service(request).create_plant(payload.dict())


@app.patch("/plants/{plant_id}")
async def update_plant(request: Request, plant_id: str, payload: PlantUpdateRequest) -> dict[str, Any]:
    plant = get_service(request).update_plant(plant_id, payload.dict(exclude_none=True))
    if plant is None:
        raise HTTPException(status_code=404, detail="Plant not found")
    return plant


@app.post("/plants/{plant_id}/mark_watered")
async def mark_watered(request: Request, plant_id: str) -> dict[str, Any]:
    plant = get_service(request).mark_watered(plant_id)
    if plant is None:
        raise HTTPException(status_code=404, detail="Plant not found")
    return plant


@app.post("/digest/send")
async def send_digest(request: Request) -> dict[str, Any]:
    return await get_service(request).send_digest_now()


@app.get("/summary")
async def summary(request: Request) -> dict[str, Any]:
    return await get_service(request).get_summary()


@app.get("/history")
async def history(request: Request, plant_id: str | None = None) -> list[dict[str, Any]]:
    return get_service(request).list_history(plant_id)


INDEX_HTML = """
<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Plant Manager</title>
  <style>
    :root {
      color-scheme: light;
      --bg: #eef4ea;
      --panel: #ffffff;
      --ink: #203126;
      --muted: #597062;
      --accent: #356845;
      --accent-soft: #dcebdc;
      --border: #c8d9cb;
      --danger: #b74d3c;
    }
    * { box-sizing: border-box; }
    body {
      margin: 0;
      font-family: "Segoe UI", sans-serif;
      background: linear-gradient(180deg, #f6faf3 0%, var(--bg) 100%);
      color: var(--ink);
    }
    main {
      max-width: 1100px;
      margin: 0 auto;
      padding: 24px;
      display: grid;
      gap: 20px;
    }
    .hero, .panel {
      background: var(--panel);
      border: 1px solid var(--border);
      border-radius: 18px;
      padding: 20px;
      box-shadow: 0 12px 30px rgba(32, 49, 38, 0.06);
    }
    .hero h1 { margin: 0 0 8px; font-size: 2rem; }
    .hero p { margin: 0; color: var(--muted); }
    .stats {
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(150px, 1fr));
      gap: 12px;
      margin-top: 18px;
    }
    .stat { background: var(--accent-soft); border-radius: 14px; padding: 14px; }
    .stat strong { display: block; font-size: 1.6rem; }
    .grid { display: grid; grid-template-columns: 1.2fr 0.8fr; gap: 20px; }
    table { width: 100%; border-collapse: collapse; }
    th, td {
      text-align: left;
      padding: 10px 8px;
      border-bottom: 1px solid var(--border);
      vertical-align: top;
    }
    th { color: var(--muted); font-size: 0.9rem; font-weight: 600; }
    .actions { display: flex; gap: 8px; flex-wrap: wrap; }
    button {
      border: 0;
      border-radius: 999px;
      padding: 10px 14px;
      background: var(--accent);
      color: white;
      cursor: pointer;
      font-weight: 600;
    }
    button.secondary { background: #e6eee6; color: var(--ink); }
    form { display: grid; gap: 12px; }
    label { display: grid; gap: 6px; font-size: 0.95rem; }
    input, select, textarea {
      border: 1px solid var(--border);
      border-radius: 10px;
      padding: 10px 12px;
      font: inherit;
      width: 100%;
      background: #fff;
    }
    textarea { min-height: 90px; resize: vertical; }
    .tag {
      display: inline-flex;
      border-radius: 999px;
      padding: 4px 10px;
      background: #e7f0e7;
      color: var(--ink);
      font-size: 0.82rem;
      font-weight: 600;
    }
    .tag.dry { background: #fbe6df; color: #8c3a2d; }
    .tag.recently_watered { background: #ddeef9; color: #24506f; }
    .tag.sensor_unavailable { background: #f2ece2; color: #7a6540; }
    .tag.battery_low { background: #f7efd2; color: #7b6200; }
    .muted { color: var(--muted); }
    .wide { grid-column: 1 / -1; }
    @media (max-width: 900px) { .grid { grid-template-columns: 1fr; } }
  </style>
</head>
<body>
  <main>
    <section class="hero">
      <h1>Plant Manager</h1>
      <p>Track all plants, review moisture at a glance, and keep watering reminders in one place.</p>
      <div class="stats" id="summary"></div>
    </section>
    <section class="grid">
      <article class="panel">
        <div class="actions" style="justify-content: space-between; margin-bottom: 12px;">
          <strong>Plants</strong>
          <div class="actions">
            <button type="button" onclick="sendDigest()">Send Digest Now</button>
            <button type="button" class="secondary" onclick="refreshAll()">Refresh</button>
          </div>
        </div>
        <table>
          <thead>
            <tr><th>Plant</th><th>Status</th><th>Moisture</th><th>Last Watered</th><th>Actions</th></tr>
          </thead>
          <tbody id="plants"></tbody>
        </table>
      </article>
      <aside class="panel">
        <strong id="form-title">Add Plant</strong>
        <form id="plant-form">
          <input type="hidden" id="plant-id">
          <label>Name <input id="name" required></label>
          <label>Zone
            <select id="zone"><option value="indoor">Indoor</option><option value="outdoor">Outdoor</option></select>
          </label>
          <label>Location <input id="location_label"></label>
          <label>Moisture Sensor Entity <input id="moisture_sensor_entity_id" required></label>
          <label>Battery Sensor Entity <input id="battery_sensor_entity_id"></label>
          <label>Low Threshold <input id="low_threshold" type="number" min="0" max="100" value="25"></label>
          <label>Min Increase <input id="min_increase" type="number" min="1" max="100" value="5"></label>
          <label>Min Interval Days <input id="min_interval_days" type="number" min="1" max="90" value="1"></label>
          <label>Notes <textarea id="notes"></textarea></label>
          <label><input id="alerts_enabled" type="checkbox" checked> Alerts enabled</label>
          <div class="actions">
            <button type="submit">Save Plant</button>
            <button type="button" class="secondary" onclick="resetForm()">Clear</button>
          </div>
        </form>
      </aside>
      <article class="panel wide">
        <strong>Settings</strong>
        <form id="settings-form" style="margin-top: 12px;">
          <label>Default Notify Service <input id="default_notify_service" placeholder="notify.mobile_app_phone"></label>
          <label>Digest Schedule Times <input id="digest_schedule_times" placeholder="07:00,19:00"></label>
          <label>Poll Interval (seconds) <input id="poll_interval" type="number" min="15" max="3600"></label>
          <label>Timezone Override <input id="timezone" placeholder="America/New_York"></label>
          <div class="actions"><button type="submit">Save Settings</button></div>
        </form>
      </article>
    </section>
  </main>
  <script>
    const state = { plants: [] };
    const statusTag = (status) => `<span class="tag ${status}">${status.replaceAll('_', ' ')}</span>`;
    const formatDate = (value) => !value ? '<span class="muted">Never</span>' : new Date(value).toLocaleString();
    async function fetchJson(url, options = {}) {
      const response = await fetch(url, { headers: { 'Content-Type': 'application/json' }, ...options });
      if (!response.ok) {
        const text = await response.text();
        alert(text || `Request failed: ${response.status}`);
        throw new Error(text || 'Request failed');
      }
      return response.json();
    }
    function resetForm() {
      document.getElementById('form-title').textContent = 'Add Plant';
      document.getElementById('plant-form').reset();
      document.getElementById('plant-id').value = '';
      document.getElementById('alerts_enabled').checked = true;
      document.getElementById('zone').value = 'indoor';
      document.getElementById('low_threshold').value = 25;
      document.getElementById('min_increase').value = 5;
      document.getElementById('min_interval_days').value = 1;
    }
    function editPlant(id) {
      const plant = state.plants.find((item) => item.id === id);
      if (!plant) return;
      document.getElementById('form-title').textContent = `Edit ${plant.name}`;
      for (const field of ['name', 'zone', 'location_label', 'moisture_sensor_entity_id', 'battery_sensor_entity_id', 'low_threshold', 'min_increase', 'min_interval_days', 'notes']) {
        document.getElementById(field).value = plant[field] ?? '';
      }
      document.getElementById('plant-id').value = plant.id;
      document.getElementById('alerts_enabled').checked = !!plant.alerts_enabled;
    }
    async function markWatered(id) {
      await fetchJson(`/plants/${id}/mark_watered`, { method: 'POST' });
      await refreshAll();
    }
    async function sendDigest() {
      await fetchJson('/digest/send', { method: 'POST' });
      await refreshAll();
      alert('Digest processed.');
    }
    async function refreshSummary() {
      const summary = await fetchJson('/summary');
      document.getElementById('summary').innerHTML = [
        ['Total Plants', summary.total_plants],
        ['Need Water', summary.plants_needing_water],
        ['Indoor Dry', summary.indoor_needing_water],
        ['Outdoor Dry', summary.outdoor_needing_water],
      ].map(([label, value]) => `<div class="stat"><span class="muted">${label}</span><strong>${value}</strong></div>`).join('');
    }
    async function refreshPlants() {
      state.plants = await fetchJson('/plants');
      document.getElementById('plants').innerHTML = state.plants.map((plant) => {
        const moisture = plant.current_moisture == null ? '<span class="muted">n/a</span>' : `${plant.current_moisture}%`;
        return `<tr>
          <td><strong>${plant.name}</strong><br><span class="muted">${plant.zone} · ${plant.location_label || 'Unassigned location'}</span></td>
          <td>${statusTag(plant.status)}</td>
          <td>${moisture}</td>
          <td>${formatDate(plant.last_watered_at)}</td>
          <td><div class="actions"><button type="button" class="secondary" onclick="editPlant('${plant.id}')">Edit</button><button type="button" onclick="markWatered('${plant.id}')">Mark Watered</button></div></td>
        </tr>`;
      }).join('');
    }
    async function refreshSettings() {
      const settings = await fetchJson('/settings');
      document.getElementById('default_notify_service').value = settings.default_notify_service || '';
      document.getElementById('digest_schedule_times').value = (settings.digest_schedule_times || []).join(',');
      document.getElementById('poll_interval').value = settings.poll_interval || 60;
      document.getElementById('timezone').value = settings.timezone || '';
    }
    async function refreshAll() {
      await Promise.all([refreshSummary(), refreshPlants(), refreshSettings()]);
    }
    document.getElementById('plant-form').addEventListener('submit', async (event) => {
      event.preventDefault();
      const id = document.getElementById('plant-id').value;
      const payload = {
        name: document.getElementById('name').value,
        zone: document.getElementById('zone').value,
        location_label: document.getElementById('location_label').value,
        moisture_sensor_entity_id: document.getElementById('moisture_sensor_entity_id').value,
        battery_sensor_entity_id: document.getElementById('battery_sensor_entity_id').value || null,
        low_threshold: Number(document.getElementById('low_threshold').value),
        min_increase: Number(document.getElementById('min_increase').value),
        min_interval_days: Number(document.getElementById('min_interval_days').value),
        alerts_enabled: document.getElementById('alerts_enabled').checked,
        notes: document.getElementById('notes').value || null,
      };
      await fetchJson(id ? `/plants/${id}` : '/plants', { method: id ? 'PATCH' : 'POST', body: JSON.stringify(payload) });
      resetForm();
      await refreshAll();
    });
    document.getElementById('settings-form').addEventListener('submit', async (event) => {
      event.preventDefault();
      await fetchJson('/settings', {
        method: 'PATCH',
        body: JSON.stringify({
          default_notify_service: document.getElementById('default_notify_service').value,
          digest_schedule_times: document.getElementById('digest_schedule_times').value,
          poll_interval: Number(document.getElementById('poll_interval').value),
          timezone: document.getElementById('timezone').value,
        }),
      });
      await refreshSettings();
      alert('Settings saved.');
    });
    refreshAll();
  </script>
</body>
</html>
"""
