import copy
import hashlib
import json
import logging
from typing import Any, Dict, Optional

from django.conf import settings
from django.core.cache import cache as default_cache
from django.db import DatabaseError, transaction
from django.utils import timezone

from curator_feature.models import DashboardDownloadEvent, DownloadLog
from curator_feature.value_objects import ClientMetadata
from pt_backend.repositories import CaseRepository
from pt_backend.services import CacheService, CaseService, CasesFilterService
from pt_backend.statistics.coordinator import StatisticsCoordinator
from .models import CuratorDataLog

logger = logging.getLogger(__name__)


class DownloadLogService:
    """Encapsulate persistence logic for download logs."""

    def log_download(self, *, username: str, chart_type: str, timestamp: Any) -> DownloadLog:
        try:
            with transaction.atomic():
                return DownloadLog.objects.create(
                    username=username,
                    chart_type=chart_type,
                    timestamp=timestamp,
                )
        except DatabaseError:
            logger.exception("Failed to persist download log for user=%s chart=%s", username, chart_type)
            raise


class DashboardDownloadEventService:
    """Persist curated dashboard download events while isolating metadata assembly."""

    def __init__(self, *, model=DashboardDownloadEvent):
        self.model = model

    def log_event(
        self,
        *,
        metric: str,
        file_format: str,
        filters: Optional[Dict[str, Any]] = None,
        source: Optional[str] = None,
        client: Optional[ClientMetadata] = None,
    ) -> DashboardDownloadEvent:
        metadata = self._build_metadata(filters=filters, source=source)
        client_details = client or ClientMetadata()

        try:
            with transaction.atomic():
                return self.model.objects.create(
                    metric=metric,
                    file_format=file_format,
                    metadata=metadata,
                    client_ip=client_details.ip_address,
                    user_agent=(client_details.user_agent or "")[: client_details.max_user_agent_length],
                )
        except DatabaseError:
            logger.exception(
                "Failed to persist dashboard download event metric=%s format=%s",
                metric,
                file_format,
            )
            raise

    def _build_metadata(
        self, *, filters: Optional[Dict[str, Any]], source: Optional[str]
    ) -> Optional[Dict[str, Any]]:
        metadata: Dict[str, Any] = {}
        if filters:
            metadata["filters"] = filters
        if source:
            metadata["source"] = source

        return metadata or None


class ChartDataService:
    """Provide normalized chart payloads for the curator dashboard."""

    CACHE_NAMESPACE = "curator_feature.chart_statistics"
    DEFAULT_CACHE_TIMEOUT = 300
    SEVERITY_ORDER = ("hospitalisasi", "insiden", "mortalitas")
    AGE_BUCKETS = ("under_12", "12_25", "26_45", "above_45")

    def __init__(
        self,
        statistics_coordinator: Optional[StatisticsCoordinator] = None,
        *,
        cache_backend=None,
        cache_timeout: Optional[int] = None,
    ):
        if statistics_coordinator is None:
            cache_service = CacheService()
            case_service = CaseService(repository=CaseRepository(), cache_service=cache_service)
            filter_service = CasesFilterService(case_service)
            statistics_coordinator = StatisticsCoordinator(case_filter_service=filter_service)

        self.statistics_coordinator = statistics_coordinator
        self._cache = cache_backend or default_cache
        if cache_timeout is None:
            cache_timeout = getattr(settings, "CURATOR_CHART_CACHE_TIMEOUT", self.DEFAULT_CACHE_TIMEOUT)
        self._cache_timeout = cache_timeout
        self._cache_enabled = bool(self._cache_timeout and self._cache_timeout > 0)

    def get_chart_data(self, *, filters: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        filters = filters or {}

        statistics = self._fetch_statistics(filters)

        charts = self._build_charts(statistics or {})
        meta = {
            "filtersApplied": bool(filters),
            "generatedAt": timezone.now().isoformat(),
            "source": "curator-dashboard",
        }

        return {"charts": charts, "meta": meta}

    def _fetch_statistics(self, filters: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        cache_key = self._build_cache_key(filters)
        if self._cache_enabled:
            cached_payload = self._cache_get(cache_key)
            if cached_payload is not None:
                return cached_payload

        try:
            statistics = self.statistics_coordinator.generate_comprehensive_report(**filters)
        except Exception:
            logger.exception("Failed to generate curator chart statistics")
            raise

        if self._cache_enabled and statistics is not None:
            self._cache_set(cache_key, statistics)

        return statistics

    def _cache_get(self, cache_key: str) -> Optional[Dict[str, Any]]:
        try:
            cached_value = self._cache.get(cache_key)
        except Exception:
            logger.warning("Failed to read curator chart cache key=%s", cache_key, exc_info=True)
            return None

        if cached_value is None:
            logger.debug("Chart statistics cache miss key=%s", cache_key)
            return None

        logger.debug("Chart statistics cache hit key=%s", cache_key)
        return copy.deepcopy(cached_value)

    def _cache_set(self, cache_key: str, value: Dict[str, Any]) -> None:
        try:
            self._cache.set(cache_key, copy.deepcopy(value), timeout=self._cache_timeout)
        except Exception:
            logger.warning("Failed to store curator chart cache key=%s", cache_key, exc_info=True)
            return

        logger.debug(
            "Stored curator chart statistics cache key=%s timeout=%s",
            cache_key,
            self._cache_timeout,
        )

    def _build_cache_key(self, filters: Dict[str, Any]) -> str:
        if not filters:
            return f"{self.CACHE_NAMESPACE}:default"
        serialized = json.dumps(filters, sort_keys=True, default=self._json_serializer)
        digest = hashlib.sha256(serialized.encode("utf-8")).hexdigest()
        return f"{self.CACHE_NAMESPACE}:{digest}"

    @staticmethod
    def _json_serializer(value: Any) -> Any:
        if isinstance(value, set):
            return sorted(value)
        return str(value)

    def _build_charts(self, statistics: Dict[str, Any]) -> Dict[str, Any]:
        return {
            "severityDistribution": self._format_severity(statistics.get("severity_statistics")),
            "ageDistribution": self._format_age(statistics.get("age_statistics")),
            "genderDistribution": self._format_gender(statistics.get("gender_statistics")),
            "severityTrendByDate": self._format_trend(statistics.get("severity_dates_count_statistics")),
            "prevalence": self._format_prevalence(statistics.get("prevalence_statistics")),
            "newsCoverage": self._format_news_sections(
                national=statistics.get("national_news_statistics"),
                local=statistics.get("local_portal_statistics"),
                healthcare=statistics.get("healthcare_news_statistics"),
            ),
        }

    def _format_severity(self, payload: Optional[Dict[str, Any]]) -> Dict[str, Any]:
        chart = {
            "chartType": "bar",
            "data": [],
            "meta": {"totalCases": 0, "order": list(self.SEVERITY_ORDER)},
        }
        if not isinstance(payload, dict):
            chart["meta"]["error"] = "DATA_UNAVAILABLE"
            return chart

        if payload.get("error"):
            chart["meta"]["error"] = payload["error"]
            return chart

        counts = payload.get("severity_counts") or {}
        ordered = []
        for key in self.SEVERITY_ORDER:
            if key in counts:
                ordered.append({"severity": key, "count": self._safe_int(counts.get(key, 0))})

        for key, value in counts.items():
            if key not in self.SEVERITY_ORDER:
                ordered.append({"severity": key, "count": self._safe_int(value)})

        total_cases = payload.get("total_cases")
        if total_cases is None:
            total_cases = sum(item["count"] for item in ordered)

        chart["data"] = ordered
        chart["meta"]["totalCases"] = self._safe_int(total_cases)
        return chart

    def _format_age(self, payload: Optional[Dict[str, Any]]) -> Dict[str, Any]:
        chart = {
            "chartType": "bar",
            "data": [],
            "meta": {"totalResponses": 0, "order": list(self.AGE_BUCKETS)},
        }
        if not isinstance(payload, dict):
            chart["meta"]["error"] = "DATA_UNAVAILABLE"
            return chart

        if payload.get("error"):
            chart["meta"]["error"] = payload["error"]
            return chart

        data = []
        for bucket in self.AGE_BUCKETS:
            count = self._safe_int(payload.get(bucket, 0))
            data.append({"group": bucket, "count": count})

        total = sum(item["count"] for item in data)
        chart["data"] = data
        chart["meta"]["totalResponses"] = total
        return chart

    def _format_gender(self, payload: Optional[Dict[str, Any]]) -> Dict[str, Any]:
        chart = {
            "chartType": "pie",
            "data": [],
            "meta": {"totalCases": 0, "order": ["male", "female"]},
        }
        if not isinstance(payload, dict):
            chart["meta"]["error"] = "DATA_UNAVAILABLE"
            return chart

        if payload.get("error"):
            chart["meta"]["error"] = payload["error"]
            return chart

        male = self._safe_int(payload.get("male", 0))
        female = self._safe_int(payload.get("female", 0))

        chart["data"] = [
            {"gender": "male", "count": male},
            {"gender": "female", "count": female},
        ]
        chart["meta"]["totalCases"] = male + female
        return chart

    def _format_trend(self, payload: Optional[Dict[str, Any]]) -> Dict[str, Any]:
        chart = {"chartType": "line", "series": [], "meta": {"seriesCount": 0}}
        if not isinstance(payload, dict):
            chart["meta"]["error"] = "DATA_UNAVAILABLE"
            return chart

        if payload.get("error"):
            chart["meta"]["error"] = payload["error"]
            return chart

        series = []
        for severity, points in payload.items():
            if not isinstance(points, list):
                continue
            normalized_points = []
            for point in points:
                date = point.get("date")
                if not date:
                    continue
                normalized_points.append(
                    {"date": date, "count": self._safe_int(point.get("count", 0))}
                )
            if normalized_points:
                series.append({"severity": severity, "points": normalized_points})

        chart["series"] = series
        chart["meta"]["seriesCount"] = len(series)
        return chart

    def _format_prevalence(self, payload: Optional[Dict[str, Any]]) -> Dict[str, Any]:
        chart = {
            "chartType": "stat",
            "data": {"year": None, "totalCases": 0, "population": None, "prevalence": None},
        }
        if not isinstance(payload, dict):
            chart["meta"] = {"error": "DATA_UNAVAILABLE"}
            return chart

        if payload.get("error"):
            chart["meta"] = {"error": payload["error"]}
            return chart

        chart["data"] = {
            "year": payload.get("year"),
            "totalCases": self._safe_int(payload.get("total_cases", 0)),
            "population": self._safe_int(payload.get("population", 0), allow_null=True),
            "prevalence": payload.get("prevalence"),
        }
        return chart

    def _format_news_sections(
        self,
        *,
        national: Optional[Dict[str, Any]],
        local: Optional[Dict[str, Any]],
        healthcare: Optional[Dict[str, Any]],
    ) -> Dict[str, Any]:
        return {
            "chartType": "bar",
            "national": self._normalize_news_section(national, "top_national", "all_national"),
            "local": self._normalize_news_section(local, "top_local", "all_local"),
            "healthcare": self._normalize_news_section(healthcare, "top_healthcare", "all_healthcare"),
        }

    def _normalize_news_section(self, payload: Optional[Dict[str, Any]], top_key: str, all_key: str) -> Dict[str, Any]:
        section = {"top": [], "all": [], "meta": {"uniquePortals": 0}}
        if not isinstance(payload, dict):
            section["meta"]["error"] = "DATA_UNAVAILABLE"
            return section

        if payload.get("error"):
            section["meta"]["error"] = payload["error"]
            return section

        top_entries = payload.get(top_key) or []
        all_entries = payload.get(all_key) or []

        section["top"] = [
            {
                "portal": entry.get("portal"),
                "newsCount": self._safe_int(entry.get("count", entry.get("news_count", 0))),
            }
            for entry in top_entries
            if entry.get("portal")
        ]

        section["all"] = [
            {
                "portal": entry.get("portal"),
                "newsCount": self._safe_int(entry.get("news_count", entry.get("count", 0))),
                "diseaseCount": self._safe_int(entry.get("disease_count", 0)),
            }
            for entry in all_entries
            if entry.get("portal")
        ]

        section["meta"]["uniquePortals"] = len(section["all"])
        return section

    @staticmethod
    def _safe_int(value: Any, default: int = 0, *, allow_null: bool = False) -> Optional[int]:
        if allow_null and value is None:
            return None
        try:
            return int(value)
        except (TypeError, ValueError):
            return default


def log_curator_edit(*, user, data_id, title=None, note=None):
    CuratorDataLog.objects.create(
        data_id=data_id,
        title=title or "N/A",
        submitted_by=(getattr(user, "username", "") or getattr(user, "email", ""))[:150],
        last_edited=timezone.now(),
        note=note or "",
    )
