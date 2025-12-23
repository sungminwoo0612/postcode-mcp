from __future__ import annotations

import logging
from typing import Any

import httpx

from postcode_mcp.core.errors import UpstreamError

log = logging.getLogger(__name__)


class HttpClient:
    def __init__(self, *, timeout_seconds: float, user_agent: str) -> None:
        self._client = httpx.Client(timeout=timeout_seconds, headers={"User-Agent": user_agent})

    def get_json(self, url: str, *, params: dict[str, Any]) -> dict[str, Any]:
        try:
            r = self._client.get(url, params=params)
            r.raise_for_status()
            return r.json()
        except httpx.HTTPError as e:
            log.warning("HTTP error: %s", e)
            raise UpstreamError(f"Upstream HTTP error: {e}") from e

    def close(self) -> None:
        try:
            self._client.close()
        except Exception:
            # close 실패는 무시(프로세스 종료 시점)
            pass
