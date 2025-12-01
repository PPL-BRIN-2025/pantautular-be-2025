from __future__ import annotations

import logging
from typing import Optional, Protocol

import requests
from django.conf import settings

logger = logging.getLogger(__name__)


class NewsProvider(Protocol):
    def fetch(self, provider: str = "default") -> list:  # pragma: no cover - Protocol contract
        ...


class ExternalNewsClient:
    """
    Small HTTP client wrapper that keeps provider communication isolated.
    """

    def __init__(self, session: Optional[requests.Session] = None):
        self.session = session or requests.Session()
        self.base_url = getattr(settings, "NEWS_API_BASE_URL", "")
        self.api_key = getattr(settings, "NEWS_API_KEY", "")
        self.timeout = getattr(settings, "NEWS_API_TIMEOUT", 10)

    def fetch(self, provider: str = "default") -> list:
        if not self.base_url:
            logger.warning("NEWS_API_BASE_URL is not configured; skipping fetch.")
            return []

        headers = {}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"

        params = {"provider": provider} if provider else {}

        response = self.session.get(
            self.base_url,
            params=params,
            headers=headers,
            timeout=self.timeout,
        )
        response.raise_for_status()
        payload = response.json()

        if isinstance(payload, list):
            return payload

        if isinstance(payload, dict):
            for key in ("articles", "data", "results"):
                value = payload.get(key)
                if isinstance(value, list):
                    return value

        logger.warning("Unexpected payload from news API: %s", type(payload))
        return []
