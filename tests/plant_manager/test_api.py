from __future__ import annotations

import asyncio
import importlib.util
from pathlib import Path
import sys
import types
import unittest

try:
    from aiohttp import web
except ModuleNotFoundError:  # pragma: no cover
    web = None

ROOT = Path(__file__).resolve().parents[2]
PKG_DIR = ROOT / "custom_components" / "plant_manager"
PKG_NAME = "test_plant_manager_component"


def _load_module(module_name: str, path: Path):
    spec = importlib.util.spec_from_file_location(module_name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def load_api_module():
    if PKG_NAME not in sys.modules:
        package = types.ModuleType(PKG_NAME)
        package.__path__ = [str(PKG_DIR)]
        sys.modules[PKG_NAME] = package
    return _load_module(f"{PKG_NAME}.api", PKG_DIR / "api.py")


@unittest.skipIf(web is None, "aiohttp is not installed")
class PlantManagerApiClientTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self) -> None:
        self.api_module = load_api_module()
        self.app = web.Application()
        self.app.router.add_get("/health", self._health)
        self.app.router.add_get("/plants", self._plants)
        self.app.router.add_get("/summary", self._summary)
        self.app.router.add_post("/plants/{plant_id}/mark_watered", self._mark_watered)
        self.app.router.add_post("/digest/send", self._send_digest)
        self.runner = web.AppRunner(self.app)
        await self.runner.setup()
        self.site = web.TCPSite(self.runner, "127.0.0.1", 0)
        await self.site.start()
        sockets = self.site._server.sockets
        self.port = sockets[0].getsockname()[1]
        self.session = self.api_module.ClientSession()
        self.client = self.api_module.PlantManagerApiClient(self.session, f"http://127.0.0.1:{self.port}")

    async def asyncTearDown(self) -> None:
        await self.session.close()
        await self.runner.cleanup()

    async def _health(self, request):
        return web.json_response({"ok": True})

    async def _plants(self, request):
        return web.json_response([{"id": "plant-1", "name": "Fern"}])

    async def _summary(self, request):
        return web.json_response({"plants_needing_water": 1})

    async def _mark_watered(self, request):
        return web.json_response({"id": request.match_info["plant_id"], "last_watered_at": "now"})

    async def _send_digest(self, request):
        return web.json_response({"sent": True})

    async def test_client_reads_and_posts_against_mock_api(self) -> None:
        health = await self.client.health()
        plants = await self.client.list_plants()
        summary = await self.client.get_summary()
        watered = await self.client.mark_watered("plant-1")
        digest = await self.client.send_digest_now()

        self.assertTrue(health["ok"])
        self.assertEqual(plants[0]["name"], "Fern")
        self.assertEqual(summary["plants_needing_water"], 1)
        self.assertEqual(watered["id"], "plant-1")
        self.assertTrue(digest["sent"])


if __name__ == "__main__":
    unittest.main()
