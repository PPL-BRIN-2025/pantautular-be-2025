import csv
import io
import logging
from datetime import datetime, time
from typing import Iterable, Optional, Tuple

from django.conf import settings
from django.http import HttpResponse
from django.utils import timezone
from rest_framework import generics, status
from rest_framework.exceptions import ValidationError
from rest_framework.response import Response
from rest_framework.views import APIView

from curator_feature.models import DashboardDownloadEvent
from curator_feature.serializers import ChartDataFiltersSerializer, DashboardDownloadEventSerializer
from curator_feature.services import DashboardDownloadEventService
from curator_feature.value_objects import ClientMetadata
from pt_backend.models import Case

from .views_base import ExpertBaseView
from .serializers import (
    CaseWriteSerializer,
    CaseReadSerializer,
    ExpertDashboardDownloadSerializer,
)

logger = logging.getLogger(__name__)


class ExpertCaseCreateView(ExpertBaseView, generics.CreateAPIView):
    queryset = Case.objects.all()

    def get_serializer_class(self):
        return CaseWriteSerializer if self.request.method == "POST" else CaseReadSerializer


class ExpertDownloadMixin:
    """Shared helpers for expert dashboard download related endpoints."""

    filters_serializer_class = ChartDataFiltersSerializer
    event_service_class = DashboardDownloadEventService
    default_serializer_class = DashboardDownloadEventSerializer

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.event_service = self.event_service_class()

    def _should_log(self) -> bool:
        return bool(getattr(settings, "ENABLE_DOWNLOAD_LOGGING", False))

    def _validate_payload(self, data) -> Tuple[dict, dict]:
        serializer_class = getattr(self, "download_serializer_class", self.default_serializer_class)
        serializer = serializer_class(data=data)
        try:
            serializer.is_valid(raise_exception=True)
        except ValidationError as exc:
            raise ValidationError(exc.detail) from exc

        payload = serializer.validated_data
        filters_payload = payload.get("filters") or {}
        if filters_payload:
            filters_serializer = self.filters_serializer_class(data=filters_payload)
            try:
                filters_serializer.is_valid(raise_exception=True)
            except ValidationError as exc:
                raise ValidationError({"filters": exc.detail}) from exc
            filters_data = filters_serializer.validated_data
        else:
            filters_data = {}

        return payload, filters_data

    def _log_event(self, request, payload: dict):
        if not self._should_log():
            return False, None

        client_metadata = ClientMetadata.from_request(request)
        try:
            event = self.event_service.log_event(
                metric=payload["metric"],
                file_format=payload["file_format"],
                filters=payload.get("filters"),
                source=payload.get("source"),
                client=client_metadata,
            )
        except Exception:
            logger.exception(
                "Failed to persist expert download event metric=%s format=%s",
                payload.get("metric"),
                payload.get("file_format"),
            )
            raise

        return True, event

    def _date_range_bounds(self, filters: dict) -> Tuple[Optional[datetime], Optional[datetime]]:
        start = filters.get("start_date")
        end = filters.get("end_date")
        tz = timezone.get_current_timezone()

        start_bound = None
        if start:
            start_bound = timezone.make_aware(datetime.combine(start, time.min), timezone=tz)

        end_bound = None
        if end:
            end_bound = timezone.make_aware(datetime.combine(end, time.max), timezone=tz)

        return start_bound, end_bound

    def _filtered_cases(self, filters: dict) -> Iterable[Case]:
        qs = Case.objects.select_related("disease", "location").prefetch_related("news")

        diseases = filters.get("diseases")
        if diseases:
            qs = qs.filter(disease__name__in=diseases)

        portals = filters.get("portals")
        if portals:
            qs = qs.filter(news__portal__in=portals)

        alertness = filters.get("level_of_alertness")
        if alertness:
            qs = qs.filter(disease__level_of_alertness=alertness)

        locations = filters.get("locations") or {}

        provinces = locations.get("provinces")
        if provinces:
            qs = qs.filter(location__province__in=provinces)

        cities = locations.get("cities")
        if cities:
            qs = qs.filter(location__city__in=cities)

        start_bound, end_bound = self._date_range_bounds(filters)
        if start_bound:
            qs = qs.filter(news__date_published__gte=start_bound)
        if end_bound:
            qs = qs.filter(news__date_published__lte=end_bound)

        return qs.distinct()

    def _render_cases_csv(self, cases: Iterable[Case]) -> str:
        header = [
            "case_id",
            "disease",
            "level_of_alertness",
            "severity",
            "status",
            "gender",
            "age",
            "city",
            "province",
            "news_portal",
            "news_title",
            "news_type",
            "news_author",
            "news_date_published",
            "news_url",
            "news_img_url",
        ]

        buffer = io.StringIO()
        writer = csv.writer(buffer)
        writer.writerow(header)

        for case in cases:
            news_items = list(case.news.all())
            if not news_items:
                writer.writerow(self._case_row(case))
                continue

            for article in news_items:
                writer.writerow(self._case_row(case, article))

        return buffer.getvalue()

    def _case_row(self, case: Case, article=None):
        disease_name = getattr(case.disease, "name", "")
        alertness = getattr(case.disease, "level_of_alertness", "")
        location = getattr(case, "location", None)
        province = getattr(location, "province", "") if location else ""

        base = [
            str(case.id),
            disease_name,
            alertness,
            case.severity,
            case.status,
            case.gender,
            case.age,
            case.city,
            province,
        ]

        if not article:
            base.extend(["", "", "", "", "", "", ""])
            return base

        base.extend(
            [
                article.portal,
                article.title,
                article.type,
                article.author,
                article.date_published.isoformat(),
                article.url,
                article.img_url,
            ]
        )
        return base


class ExpertDashboardDownloadLogAPIView(ExpertBaseView, ExpertDownloadMixin, APIView):
    """Mirror curator download logging workflow for expert users."""

    def post(self, request, *args, **kwargs):
        try:
            payload, _ = self._validate_payload(request.data)
        except ValidationError as exc:
            return Response({"errors": exc.detail}, status=status.HTTP_400_BAD_REQUEST)

        try:
            logged, event = self._log_event(request, payload)
        except Exception:
            return Response(
                {"message": "Download logging failed"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

        if not logged:
            return Response(
                {"logged": False, "detail": "Download logging disabled"},
                status=status.HTTP_202_ACCEPTED,
            )

        return Response({"id": event.id, "logged": True}, status=status.HTTP_201_CREATED)


class ExpertDashboardCSVDownloadAPIView(ExpertBaseView, ExpertDownloadMixin, APIView):
    """Provide CSV downloads for expert dashboard while logging the event."""

    download_serializer_class = ExpertDashboardDownloadSerializer

    def post(self, request, *args, **kwargs):
        data = request.data.copy()
        if "file_format" not in data:
            data["file_format"] = "csv"

        try:
            payload, filters = self._validate_payload(data)
        except ValidationError as exc:
            return Response({"errors": exc.detail}, status=status.HTTP_400_BAD_REQUEST)

        if payload["file_format"] != "csv":
            return Response(
                {"message": "Only CSV downloads are supported by this endpoint."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            logged, _ = self._log_event(request, payload)
        except Exception:
            return Response(
                {"message": "Download logging failed"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

        cases = self._filtered_cases(filters)
        csv_content = self._render_cases_csv(cases)

        response = HttpResponse(csv_content, content_type="text/csv")
        filename = f"{payload.get('metric') or 'dashboard'}-export.csv"
        response["Content-Disposition"] = f'attachment; filename=\"{filename}\"'
        response["X-Download-Logged"] = "true" if logged else "false"
        return response
