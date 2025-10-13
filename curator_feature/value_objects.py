from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from typing import Any, Dict, Iterable, Optional


MAX_USER_AGENT_LENGTH = 512


@dataclass(frozen=True)
class ChartFilters:
    """Value object that normalizes curator filter payloads into service friendly formats."""

    diseases: Iterable[str] = field(default_factory=tuple)
    portals: Iterable[str] = field(default_factory=tuple)
    level_of_alertness: Optional[int] = None
    provinces: Iterable[str] = field(default_factory=tuple)
    cities: Iterable[str] = field(default_factory=tuple)
    start_date: Optional[date] = None
    end_date: Optional[date] = None

    @classmethod
    def from_validated_data(cls, data: Dict[str, Any]) -> "ChartFilters":
        locations = data.get("locations") or {}
        return cls(
            diseases=tuple(data.get("diseases") or ()),
            portals=tuple(data.get("portals") or ()),
            level_of_alertness=data.get("level_of_alertness"),
            provinces=tuple(locations.get("provinces") or ()),
            cities=tuple(locations.get("cities") or ()),
            start_date=data.get("start_date"),
            end_date=data.get("end_date"),
        )

    def to_service_filters(self) -> Dict[str, Any]:
        filters: Dict[str, Any] = {}

        if self.diseases:
            filters["disease"] = list(self.diseases)

        if self.portals:
            filters["portals"] = list(self.portals)

        if self.level_of_alertness:
            filters["disease_alertness"] = self.level_of_alertness

        if self.provinces:
            filters["provinces"] = list(self.provinces)

        if self.cities:
            filters["cities"] = list(self.cities)

        if self.start_date or self.end_date:
            filters["date_range"] = {
                "start": self.start_date.isoformat() if self.start_date else None,
                "end": self.end_date.isoformat() if self.end_date else None,
            }

        return filters


@dataclass(frozen=True)
class ClientMetadata:
    """Connection details that accompany curator dashboard download events."""

    ip_address: Optional[str] = None
    user_agent: str = ""
    max_user_agent_length: int = MAX_USER_AGENT_LENGTH

    @classmethod
    def from_request(cls, request) -> "ClientMetadata":
        forwarded = request.META.get("HTTP_X_FORWARDED_FOR")
        ip_address = None
        if forwarded:
            ip_address = forwarded.split(",")[0].strip()
        else:
            ip_address = request.META.get("REMOTE_ADDR")

        raw_agent = request.META.get("HTTP_USER_AGENT") or ""
        user_agent = raw_agent[:MAX_USER_AGENT_LENGTH]
        return cls(ip_address=ip_address, user_agent=user_agent)
