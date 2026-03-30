from __future__ import annotations

from typing import Any

from aiohttp import ClientResponseError, ClientSession


class PlantManagerApiError(RuntimeError):
    """Raised when the Plant Manager API request fails."""


class PlantManagerApiClient:
    def __init__(self, session: ClientSession, base_url: str) -> None:
        self._session = session
        self._base_url = base_url.rstrip("/")

    async def health(self) -> dict[str, Any]:
        return await self._request("GET", "/health")

    async def list_plants(self) -> list[dict[str, Any]]:
        return await self._request("GET", "/plants")

    async def get_summary(self) -> dict[str, Any]:
        return await self._request("GET", "/summary")

    async def mark_watered(self, plant_id: str) -> dict[str, Any]:
        return await self._request("POST", f"/plants/{plant_id}/mark_watered")

    async def send_digest_now(self) -> dict[str, Any]:
        return await self._request("POST", "/digest/send")

    async def _request(self, method: str, path: str) -> Any:
        try:
            async with self._session.request(method, f"{self._base_url}{path}") as response:
                response.raise_for_status()
                return await response.json()
        except ClientResponseError as exc:
            raise PlantManagerApiError(
                f"Plant Manager API {exc.status} {exc.message or exc.request_info.real_url}"
            ) from exc
        except Exception as exc:
            raise PlantManagerApiError(str(exc)) from exc
