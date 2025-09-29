from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Callable, Dict, Iterable, List, Optional

from django.core.cache import cache as django_cache
from django.utils import timezone

from pt_backend.models import Role, User
from pt_backend.repositories import CaseRepository

EMPTY_DATA_MESSAGE = "Data tidak ditemukan"
NO_ACTIVITY_MESSAGE = "Tidak ada aktivitas"


@dataclass(frozen=True)
class RolesSummary:
    count: int
    roles: List[str]

    def to_dict(self) -> Dict[str, object]:
        return {"count": self.count, "roles": self.roles}


@dataclass(frozen=True)
class FailedLoginStats:
    total_failed: int
    total_unique_emails: int
    last_24h: int
    logs_url: str

    def to_dict(self) -> Dict[str, object]:
        return {
            "total_failed": self.total_failed,
            "total_unique_emails": self.total_unique_emails,
            "last_24h": self.last_24h,
            "logs_url": self.logs_url,
        }


@dataclass(frozen=True)
class FailedLoginEvents:
    events: List[Dict[str, object]]

    def to_dict(self) -> Dict[str, object]:
        return {"count": len(self.events), "events": self.events}


@dataclass(frozen=True)
class UsersSummary:
    total_users: int
    active_users: int

    def to_dict(self) -> Dict[str, int]:
        return {
            "total_users": self.total_users,
            "active_users": self.active_users,
        }


@dataclass(frozen=True)
class DatasetsSummary:
    total_datasets: int

    def to_dict(self) -> Dict[str, int]:
        return {"total_datasets": self.total_datasets}


@dataclass
class StatsSummary:
    total_users: int
    active_users: int
    datasets: int
    failed_logins: int
    roles: List[str]
    empty: bool = False
    is_empty: bool = False
    message: Optional[str] = None
    messages: Dict[str, str] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, object]:
        payload: Dict[str, object] = {
            "totalUsers": self.total_users,
            "activeUsers": self.active_users,
            "datasets": self.datasets,
            "failedLogins": self.failed_logins,
            "roles": self.roles,
        }

        if self.empty:
            payload["empty"] = True
        if self.is_empty:
            payload["isEmpty"] = True
        if self.message:
            payload["message"] = self.message
        if self.messages:
            payload["messages"] = self.messages

        return payload


class DatasetsService:
    """
    Encapsulates business logic for dataset (case) metrics:
    - Caches the total count for a short TTL to reduce DB load
    - Delegates data access to the CaseRepository
    """

    def __init__(self, repository=None, cache_backend=None, cache_key: str = 'admin:datasets:count', ttl: int = 60):
        self.repository = repository or CaseRepository()
        self.cache = cache_backend or django_cache
        self.cache_key = cache_key
        self.ttl = ttl

    def get_total_datasets(self) -> int:
        value = self.cache.get(self.cache_key)
        if value is None:
            value = int(self.repository.count_cases())
            self.cache.set(self.cache_key, value, self.ttl)
        return value


class AdminDashboardService:
    FAILED_TOTAL_KEY = "auth:failed_login_total"
    FAILED_EVENTS_KEY = "auth:failed_login_events"
    FAILED_UNIQUE_KEY = "auth:failed_login_unique_emails_count"
    LOGS_URL = "/admin-feature/failed-logins/logs"

    def __init__(
        self,
        role_model=Role,
        user_model=User,
        cache_backend=django_cache,
        dataset_service: Optional[DatasetsService] = None,
        now_provider: Optional[Callable[[], datetime]] = None,
    ) -> None:
        self.role_model = role_model
        self.user_model = user_model
        self.cache = cache_backend
        self.dataset_service = dataset_service or DatasetsService()
        self.now_provider = now_provider or timezone.now

    # --- Roles ---
    def get_roles_summary(self) -> RolesSummary:
        names = list(
            self.role_model.objects.values_list("name", flat=True).order_by("name")
        )
        return RolesSummary(count=len(names), roles=names)

    # --- Failed logins ---
    def get_failed_login_stats(self) -> FailedLoginStats:
        events = self.cache.get(self.FAILED_EVENTS_KEY, []) or []
        total_failed = int(self.cache.get(self.FAILED_TOTAL_KEY, 0))
        unique = self.cache.get(self.FAILED_UNIQUE_KEY)
        if unique is None:
            unique = self._calculate_unique_emails(events)

        last_24h = self._count_events_last_24h(events)
        return FailedLoginStats(
            total_failed=total_failed,
            total_unique_emails=unique,
            last_24h=last_24h,
            logs_url=self.LOGS_URL,
        )

    def get_failed_login_events(self, limit: int = 200) -> FailedLoginEvents:
        events = self.cache.get(self.FAILED_EVENTS_KEY, []) or []
        recent = list(reversed(events[-limit:]))
        return FailedLoginEvents(events=recent)

    @staticmethod
    def _calculate_unique_emails(events: Iterable[Dict[str, object]]) -> int:
        emails = {
            str(event.get("email", "")).lower()
            for event in events
            if event.get("email")
        }
        return len(emails)

    def _count_events_last_24h(self, events: Iterable[Dict[str, object]]) -> int:
        threshold = self.now_provider() - timedelta(hours=24)
        count = 0
        for event in events:
            timestamp = event.get("timestamp")
            if not timestamp:
                continue
            dt = self._parse_iso_timestamp(timestamp)
            if dt and dt >= threshold:
                count += 1
        return count

    @staticmethod
    def _parse_iso_timestamp(value: str) -> Optional[datetime]:
        try:
            dt = datetime.fromisoformat(value)
        except (TypeError, ValueError):
            return None
        if dt.tzinfo is None:
            return dt.replace(tzinfo=timezone.utc)
        return dt

    # --- Users ---
    def get_users_summary(self) -> UsersSummary:
        total_users = int(self.user_model.objects.count())
        active_users = int(
            self.user_model.objects.filter(last_login__isnull=False).count()
        )
        return UsersSummary(total_users=total_users, active_users=active_users)

    # --- Datasets ---
    def get_datasets_summary(self) -> DatasetsSummary:
        total = int(self.dataset_service.get_total_datasets())
        return DatasetsSummary(total_datasets=total)

    # --- Aggregate stats ---
    def get_stats(self) -> StatsSummary:
        users_summary = self.get_users_summary()
        datasets_total = self.dataset_service.get_total_datasets()
        roles_summary = self.get_roles_summary()
        failed_logins = int(self.cache.get(self.FAILED_TOTAL_KEY, 0))

        summary = StatsSummary(
            total_users=users_summary.total_users,
            active_users=users_summary.active_users,
            datasets=datasets_total,
            failed_logins=failed_logins,
            roles=roles_summary.roles,
        )

        self._enrich_stats_messages(summary)
        return summary

    @staticmethod
    def _enrich_stats_messages(summary: StatsSummary) -> None:
        primary_all_zero = (
            summary.total_users == 0
            and summary.active_users == 0
            and summary.datasets == 0
            and summary.failed_logins == 0
        )

        if primary_all_zero:
            summary.empty = True
            summary.is_empty = True
            summary.message = EMPTY_DATA_MESSAGE
            summary.messages = {
                "usersMessage": EMPTY_DATA_MESSAGE,
                "activityMessage": NO_ACTIVITY_MESSAGE,
                "datasetsMessage": EMPTY_DATA_MESSAGE,
            }
            return

        messages: Dict[str, str] = {}
        if summary.total_users == 0:
            messages["usersMessage"] = EMPTY_DATA_MESSAGE
        if summary.active_users == 0:
            messages["activityMessage"] = NO_ACTIVITY_MESSAGE
        if summary.datasets == 0:
            messages["datasetsMessage"] = EMPTY_DATA_MESSAGE

        if messages:
            summary.messages = messages
