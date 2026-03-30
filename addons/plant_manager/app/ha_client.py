from __future__ import annotations

import os
from typing import Any

import aiohttp


class HomeAssistantApiError(RuntimeError):
    """Raised when the add-on cannot reach the Home Assistant API."""


class HomeAssistantApiClient:
    def __init__(
        self,
        *,
        base_url: str | None = None,
        token: str | None = None,
        timeout_seconds: int = 10,
    ) -> None:
        self._base_url = (base_url or os.getenv("HA_API_BASE_URL") or "http://supervisor/core/api").rstrip("/")
        self._token = token or os.getenv("SUPERVISOR_TOKEN") or os.getenv("HASSIO_TOKEN")
        self._timeout = aiohttp.ClientTimeout(total=timeout_seconds)
        self._session: aiohttp.ClientSession | None = None

    async def async_get_session(self) -> aiohttp.ClientSession:
        if self._session is None or self._session.closed:
            headers = {}
            if self._token:
                headers["Authorization"] = f"Bearer {self._token}"
            self._session = aiohttp.ClientSession(timeout=self._timeout, headers=headers)
        return self._session

    async def close(self) -> None:
        if self._session and not self._session.closed:
            await self._session.close()

    async def get_all_states(self) -> list[dict[str, Any]]:
        return await self._request("GET", "/states")

    async def get_config(self) -> dict[str, Any]:
        return await self._request("GET", "/config")

    async def call_action(self, action: str, data: dict[str, Any]) -> list[dict[str, Any]] | dict[str, Any]:
        if "." not in action:
            raise HomeAssistantApiError(f"Invalid action format: {action}")
        domain, service = action.split(".", 1)
        return await self._request("POST", f"/services/{domain}/{service}", json=data)

    async def _request(self, method: str, path: str, **kwargs: Any) -> Any:
        session = await self.async_get_session()
        async with session.request(method, f"{self._base_url}{path}", **kwargs) as response:
            if response.status >= 400:
                text = await response.text()
                raise HomeAssistantApiError(f"Home Assistant API {response.status}: {text}")
            if response.content_type == "application/json":
                return await response.json()
            text = await response.text()
            return text
