from collections.abc import Iterable, Mapping
from typing import List, Set

from django.db.models import Q

from .strategy import FilterStrategy


class LocationFilter(FilterStrategy):
    @property
    def field_name(self) -> str:
        return "locations"

    def build_query(self, values):
        provinces: List[str] = []
        cities: List[str] = []

        if isinstance(values, Mapping):
            if "provinces" in values or "cities" in values:
                provinces = self._normalize(values.get("provinces"))
                cities = self._normalize(values.get("cities"))
            else:
                normalized = self._normalize(values)
                provinces = normalized
                cities = normalized
        else:
            normalized = self._normalize(values)
            provinces = normalized
            cities = normalized

        if not provinces and not cities:
            return Q()

        query = Q()
        if cities:
            city_query = Q(location__city__in=cities) | Q(city__in=cities)
            query |= city_query
        if provinces:
            query |= Q(location__province__in=provinces)

        return query

    def _normalize(self, value) -> List[str]:
        collected = self._collect_values(value)

        seen: Set[str] = set()
        normalized: List[str] = []
        for item in collected:
            if item is None:
                continue
            text = str(item).strip()
            if not text or text in seen:
                continue
            normalized.append(text)
            seen.add(text)
        return normalized

    def _collect_values(self, value):
        if not value:
            return []

        if isinstance(value, str):
            return [value]

        if isinstance(value, Mapping):
            if "value" in value:
                return [value["value"]]
            if "label" in value:
                return [value["label"]]
            items = []
            for item in value.values():
                items.extend(self._collect_values(item))
            return items

        if isinstance(value, Iterable):
            items = []
            for item in value:
                items.extend(self._collect_values(item))
            return items

        return [value]
