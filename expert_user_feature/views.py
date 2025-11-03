import csv
import io
import logging
from datetime import datetime, time
from typing import Iterable, Optional, Tuple

from django.conf import settings
from django.http import Http404, HttpResponse
from django.utils import timezone
from rest_framework import generics, status
from rest_framework.exceptions import ValidationError
from rest_framework.parsers import MultiPartParser
from rest_framework.response import Response
from rest_framework.views import APIView

from curator_feature.models import DashboardDownloadEvent
from curator_feature.serializers import ChartDataFiltersSerializer, DashboardDownloadEventSerializer
from curator_feature.services import DashboardDownloadEventService
from curator_feature.value_objects import ClientMetadata
from pt_backend.models import Case, Disease, Location

from .views_base import ExpertBaseView
from .serializers import (
    CaseReadSerializer,
    CaseWriteSerializer,
    ExpertDashboardDownloadSerializer,
)

logger = logging.getLogger(__name__)


class ExpertCaseCreateView(ExpertBaseView, generics.CreateAPIView):
    queryset = Case.objects.all()
    serializer_class = CaseWriteSerializer

    def get_serializer_class(self):
        if self.request.method == "POST":
            return CaseWriteSerializer
        return CaseReadSerializer

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        case = serializer.save()
        read_data = CaseReadSerializer(case).data
        headers = self.get_success_headers(read_data)
        return Response(read_data, status=status.HTTP_201_CREATED, headers=headers)


class ExpertCaseDetailView(ExpertBaseView, APIView):
    """Handle expert case update and delete operations."""

    def _get_case(self, pk):
        try:
            return Case.objects.select_related("location", "disease").get(pk=pk)
        except Case.DoesNotExist as exc:
            raise Http404("Case not found.") from exc

    def patch(self, request, pk, *args, **kwargs):
        case = self._get_case(pk)
        payload = request.data

        if "disease" in payload:
            disease_name = payload.get("disease")
            try:
                case.disease = Disease.objects.get(name=disease_name)
            except Disease.DoesNotExist:
                return Response(
                    {"errors": {"disease": ["Unknown disease."]}},
                    status=status.HTTP_400_BAD_REQUEST,
                )

        if "location" in payload:
            location_data = payload.get("location") or {}
            city = location_data.get("city")
            if not city:
                return Response(
                    {"errors": {"location": ["city is required."]}},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            defaults = {
                "province": location_data.get("province") or "",
                "latitude": location_data.get("latitude") or None,
                "longitude": location_data.get("longitude") or None,
            }
            location, created = Location.objects.get_or_create(city=city, defaults=defaults)
            if not created:
                updated = False
                for attr in ("province", "latitude", "longitude"):
                    value = defaults.get(attr)
                    if value not in (None, "") and getattr(location, attr) != value:
                        setattr(location, attr, value)
                        updated = True
                if updated:
                    location.save()

            case.location = location
            case.city = city

        for attr in ("gender", "age", "city", "status", "severity"):
            if attr in payload:
                setattr(case, attr, payload[attr])

        case.save()
        return Response(CaseReadSerializer(case).data, status=status.HTTP_200_OK)

    def delete(self, request, pk, *args, **kwargs):
        case = self._get_case(pk)
        case.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


class ExpertCaseCSVUploadAPIView(ExpertBaseView, APIView):
    """Bulk create cases from CSV uploads."""

    parser_classes = [MultiPartParser]

    def post(self, request, *args, **kwargs):
        upload = request.FILES.get("file")
        if not upload:
            return Response({"errors": {"file": ["This field is required."]}}, status=status.HTTP_400_BAD_REQUEST)

        try:
            decoded = upload.read().decode("utf-8")
        except UnicodeDecodeError:
            return Response(
                {"errors": {"file": ["Unable to decode CSV file using UTF-8."]}},
                status=status.HTTP_400_BAD_REQUEST,
            )

        reader = csv.DictReader(io.StringIO(decoded))
        if reader.fieldnames is None:
            return Response({"errors": {"file": ["CSV file must include a header row."]}}, status=status.HTTP_400_BAD_REQUEST)

        created = 0
        errors = []
        rows = list(reader)
        for index, row in enumerate(rows, start=1):
            payload = self._row_to_payload(row)
            serializer = CaseWriteSerializer(data=payload)
            if serializer.is_valid():
                serializer.save()
                created += 1
            else:
                errors.append({"row": index, "errors": serializer.errors})

        if errors:
            return Response({"errors": errors}, status=status.HTTP_400_BAD_REQUEST)

        return Response({"created": created}, status=status.HTTP_201_CREATED)

    def _row_to_payload(self, row):
        clean = lambda value: value.strip() if isinstance(value, str) else value

        location = {
            "city": clean(row.get("location_city") or ""),
            "province": clean(row.get("location_province") or ""),
            "latitude": self._clean_decimal(row.get("location_latitude")),
            "longitude": self._clean_decimal(row.get("location_longitude")),
        }

        news = {
            "portal": clean(row.get("news_portal")),
            "title": clean(row.get("news_title")),
            "type": clean(row.get("news_type")),
            "content": clean(row.get("news_content")),
            "url": clean(row.get("news_url")),
            "author": clean(row.get("news_author")),
            "date_published": clean(row.get("news_date_published")),
            "img_url": clean(row.get("news_img_url") or ""),
        }

        payload = {
            "disease": clean(row.get("disease")),
            "gender": clean(row.get("gender")),
            "age": clean(row.get("age")),
            "city": clean(row.get("city")),
            "status": clean(row.get("status")),
            "severity": clean(row.get("severity")),
            "location": location,
            "news": news,
        }

        return payload

    @staticmethod
    def _clean_decimal(value):
        if value is None:
            return None
        value = value.strip() if isinstance(value, str) else value
        if value in ("", " "):
            return None
        return value


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
