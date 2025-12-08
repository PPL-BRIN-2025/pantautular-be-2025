import logging
from typing import Any, Dict, Optional

from django.db.models import QuerySet

from pantau_tular.security import InputValidator, SafeLogger, SafeQueryExecutor
from pt_backend.models import Case


class SafeCaseQueryService:
    """Example service that enforces validated input and parameterized SQL."""

    def __init__(
        self,
        validator: InputValidator = InputValidator,
        executor: Optional[SafeQueryExecutor] = None,
        logger: Optional[SafeLogger] = None,
    ) -> None:
        self.validator = validator
        self.executor = executor or SafeQueryExecutor()
        self.logger = logger or SafeLogger(logging.getLogger(__name__))

    def lookup_case(self, keyword: str = "", status_filter: str = "") -> Dict[str, Any]:
        keyword = self.validator.validate_safe_text(keyword)
        status_filter = self.validator.validate_keyword(status_filter) if status_filter else ""
        queryset = Case.objects.all()
        if status_filter:
            queryset = queryset.filter(status=status_filter)
        if keyword:
            queryset = queryset.filter(city__icontains=keyword)

        latest_case = queryset.order_by("-created_at").values("id", "city", "status", "severity").first()
        count = self._count_cases(status_filter)
        result = {
            "case": latest_case,
            "matching_case_count": count,
        }
        if not latest_case:
            self.logger.info("Lookup returned no cases for keyword=%s status=%s", keyword, status_filter)
        return result

    def _count_cases(self, status_filter: str) -> int:
        table = Case._meta.db_table
        query = f"SELECT COUNT(*) FROM {table}"
        params = []
        if status_filter:
            query += " WHERE status = %s"
            params.append(status_filter)
        row = self.executor.fetchone(query, params)
        return int(row[0]) if row else 0
