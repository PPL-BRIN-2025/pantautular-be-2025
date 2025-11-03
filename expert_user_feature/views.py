import csv
import io
import logging
from datetime import datetime, time
from typing import Iterable, Optional, Tuple

from django.conf import settings
from django.db import transaction
from django.http import Http404, HttpResponse
from django.utils import timezone

from rest_framework import generics, status, pagination
from rest_framework.exceptions import ValidationError
from rest_framework.parsers import MultiPartParser
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from django.db.models import Q

from authentication.permissions import IsTokenAuthenticated
from authentication.security import CustomJWTAuthentication

from curator_feature.models import DashboardDownloadEvent
from curator_feature.serializers import (
    CaseReadSerializer,
    CaseWriteSerializer,
    ChartDataFiltersSerializer,
    DashboardDownloadEventSerializer,
)
from curator_feature.services import DashboardDownloadEventService
from curator_feature.value_objects import ClientMetadata

from pt_backend.models import Case, Disease, Location, CaseUploadBatch

from .models import ExpertDataset
from .serializers import (
    ExpertDatasetSerializer,
    ExpertDashboardDownloadSerializer,
    BatchSerializer,
)
from .audittrail import log_expert_event
from .permissions import ReadOnlyOrExpert, IsExpertUserRole

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------
# 🔹 AUTH BASE (FOR UPLOAD / BATCH / CASE LIST FEATURES)
# ---------------------------------------------------------------------
class _ExpertBaseView(generics.GenericAPIView):
    authentication_classes = [CustomJWTAuthentication]
    permission_classes = [IsTokenAuthenticated, IsExpertUserRole]


# ---------------------------------------------------------------------
# ✅ EXPERT CASE CREATE / EDIT / DELETE (STAY PUBLIC LIKE BEFORE)
# ---------------------------------------------------------------------
class ExpertBaseView(generics.GenericAPIView):
    """Base used for public expert-facing endpoints (unchanged)."""
    pass


class ExpertCaseCreateView(ExpertBaseView, generics.CreateAPIView):
    queryset = Case.objects.all()

    def get_serializer_class(self):
        return CaseWriteSerializer if self.request.method == "POST" else CaseReadSerializer

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        case = serializer.save()
        return Response(CaseReadSerializer(case).data, status=201)


class ExpertCaseDetailView(ExpertBaseView, APIView):
    """PATCH/DELETE for individual cases."""

    def _get_case(self, pk):
        try:
            return Case.objects.select_related("location", "disease").get(pk=pk)
        except Case.DoesNotExist as exc:
            raise Http404("Case not found.") from exc

    def patch(self, request, pk, *args, **kwargs):
        case = self._get_case(pk)
        payload = request.data

        if "disease" in payload:
            try:
                case.disease = Disease.objects.get(name=payload["disease"])
            except Disease.DoesNotExist:
                return Response({"errors": {"disease": ["Unknown disease."]}}, 400)

        if "location" in payload:
            loc = payload["location"]
            city = loc.get("city")
            if not city:
                return Response({"errors": {"location": ["city is required."]}}, 400)

            defaults = {
                "province": loc.get("province") or "",
                "latitude": loc.get("latitude") or None,
                "longitude": loc.get("longitude") or None,
            }
            location, created = Location.objects.get_or_create(city=city, defaults=defaults)
            case.location = location

        for attr in ("gender", "age", "city", "status", "severity"):
            if attr in payload:
                setattr(case, attr, payload[attr])

        case.save()
        return Response(CaseReadSerializer(case).data, 200)

    def delete(self, request, pk, *args, **kwargs):
        case = self._get_case(pk)
        case.delete()
        return Response(status=204)


# ---------------------------------------------------------------------
# ✅ EXPERT DASHBOARD DOWNLOAD HELPERS
# ---------------------------------------------------------------------
class ExpertDownloadMixin:
    filters_serializer_class = ChartDataFiltersSerializer
    event_service_class = DashboardDownloadEventService
    default_serializer_class = DashboardDownloadEventSerializer

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.event_service = self.event_service_class()

    def _should_log(self):
        return bool(getattr(settings, "ENABLE_DOWNLOAD_LOGGING", False))

    def _validate_payload(self, data):
        serializer_class = getattr(self, "download_serializer_class", self.default_serializer_class)
        serializer = serializer_class(data=data)
        serializer.is_valid(raise_exception=True)
        payload = serializer.validated_data

        filters_data = {}
        if payload.get("filters"):
            fs = self.filters_serializer_class(data=payload["filters"])
            fs.is_valid(raise_exception=True)
            filters_data = fs.validated_data

        return payload, filters_data

    def _log_event(self, request, payload):
        if not self._should_log():
            return False, None

        event = self.event_service.log_event(
            metric=payload["metric"],
            file_format=payload["file_format"],
            filters=payload.get("filters"),
            source=payload.get("source"),
            client=ClientMetadata.from_request(request)
        )
        return True, event

    def _date_range_bounds(self, filters):
        tz = timezone.get_current_timezone()
        start = filters.get("start_date")
        end = filters.get("end_date")
        start = timezone.make_aware(datetime.combine(start, time.min), tz) if start else None
        end = timezone.make_aware(datetime.combine(end, time.max), tz) if end else None
        return start, end

    def _filtered_cases(self, filters):
        qs = Case.objects.select_related("disease", "location").prefetch_related("news")

        if filters.get("diseases"):
            qs = qs.filter(disease__name__in=filters["diseases"])

        start, end = self._date_range_bounds(filters)
        if start:
            qs = qs.filter(news__date_published__gte=start)
        if end:
            qs = qs.filter(news__date_published__lte=end)

        return qs.distinct()

    def _render_cases_csv(self, cases):
        header = [
            "case_id", "disease", "level_of_alertness", "severity", "status",
            "gender", "age", "city", "province",
            "news_portal", "news_title", "news_type",
            "news_author", "news_date_published", "news_url", "news_img_url",
        ]

        buf = io.StringIO()
        writer = csv.writer(buf)
        writer.writerow(header)

        for case in cases:
            for article in case.news.all():
                writer.writerow([
                    str(case.id),
                    case.disease.name if case.disease else "",
                    case.disease.level_of_alertness if case.disease else "",
                    case.severity,
                    case.status,
                    case.gender,
                    case.age,
                    case.city,
                    case.location.province if case.location else "",
                    article.portal,
                    article.title,
                    article.type,
                    article.author,
                    article.date_published.isoformat(),
                    article.url,
                    article.img_url,
                ])
        return buf.getvalue()


class ExpertDashboardCSVDownloadAPIView(ExpertBaseView, ExpertDownloadMixin, APIView):
    download_serializer_class = ExpertDashboardDownloadSerializer

    def post(self, request):
        payload, filters = self._validate_payload(request.data)
        csv_content = self._render_cases_csv(self._filtered_cases(filters))
        response = HttpResponse(csv_content, content_type="text/csv")
        response["Content-Disposition"] = 'attachment; filename="dashboard-export.csv"'
        return response


# ---------------------------------------------------------------------
# ✅ NEW: BATCH SYSTEM + EXPERT CASE LIST
# ---------------------------------------------------------------------
class ExpertBatchListView(_ExpertBaseView, generics.ListAPIView):
    serializer_class = BatchSerializer

    def get_queryset(self):
        return CaseUploadBatch.objects.filter(uploaded_by=self.request.user)


class ExpertBatchDeleteView(_ExpertBaseView, APIView):
    def delete(self, request, batch_id):
        batch = CaseUploadBatch.objects.filter(uploaded_by=request.user, id=batch_id).first()
        if not batch:
            return Response({"message": "Batch not found"}, 404)

        deleted = batch.cases.count()
        batch.cases.all().delete()
        batch.delete()
        return Response({"deleted_cases": deleted}, 204)


class ExpertCaseListView(_ExpertBaseView, generics.ListAPIView):
    serializer_class = CaseReadSerializer

    def get_queryset(self):
        qs = Case.objects.filter(created_by=self.request.user).select_related("disease", "location", "batch").prefetch_related("news")
        if batch := self.request.query_params.get("batch"):
            qs = qs.filter(batch_id=batch)
        return qs.order_by("-id")


class ExpertCaseBulkDeleteView(_ExpertBaseView, APIView):
    def delete(self, request):
        qs = Case.objects.filter(created_by=request.user)
        deleted = qs.count()
        qs.delete()
        return Response({"deleted_cases": deleted}, 204)


class ExpertCaseCSVUploadView(_ExpertBaseView, APIView):
    parser_classes = [MultiPartParser]

    def post(self, request):
        upload = request.FILES.get("file")
        if not upload:
            return Response({"message": "CSV file missing"}, 400)

        batch = CaseUploadBatch.objects.create(uploaded_by=request.user, filename=upload.name)
        reader = csv.DictReader(io.StringIO(upload.read().decode("utf-8-sig")))

        created = 0
        with transaction.atomic():
            for row in reader:
                payload = self._convert(row)
                serializer = CaseWriteSerializer(data=payload)
                serializer.is_valid(raise_exception=True)
                serializer.save(created_by=request.user, batch=batch)
                created += 1

        return Response({"batch_id": batch.id, "created": created}, 201)

    def _convert(self, row):
        c = lambda v: v.strip() if isinstance(v, str) else v
        disease_name = c(row.get("disease"))
        disease_obj, _ = Disease.objects.get_or_create(name=disease_name, defaults={"level_of_alertness": 1})

        return {
            "disease": disease_obj.name,
            "gender": c(row.get("gender")),
            "age": c(row.get("age")),
            "city": c(row.get("city")),
            "status": c(row.get("status")),
            "severity": c(row.get("severity")),
            "location": {
                "city": c(row.get("location_city")) or c(row.get("city")),
                "province": c(row.get("location_province")),
                **({"latitude": c(row.get("location_latitude"))} if c(row.get("location_latitude")) else {}),
                **({"longitude": c(row.get("location_longitude"))} if c(row.get("location_longitude")) else {}),
            },
            "news": {
                "portal": c(row.get("news_portal")),
                "title": c(row.get("news_title")),
                "type": c(row.get("news_type")),
                "content": c(row.get("news_content")),
                "url": c(row.get("news_url")),
                "author": c(row.get("news_author")),
                "date_published": c(row.get("news_date_published")),
                "img_url": c(row.get("news_img_url")) or "",
            },
        }


# ---------------------------------------------------------------------
# ✅ EXPERT DATASET LIST + DETAIL (UNCHANGED)
# ---------------------------------------------------------------------
class SmallPageNumberPagination(pagination.PageNumberPagination):
    page_size = 10
    page_size_query_param = "pageSize"
    max_page_size = 100


class ExpertDatasetListView(generics.ListAPIView):
    serializer_class = ExpertDatasetSerializer
    permission_classes = [ReadOnlyOrExpert]
    pagination_class = SmallPageNumberPagination

    def get_queryset(self):
        qs = ExpertDataset.objects.all()
        q = (self.request.query_params.get("search") or "").lower()
        if q:
            qs = qs.filter(
                Q(data_id__icontains=q) |
                Q(file_name__icontains=q) |
                Q(submitted_by__icontains=q) |
                Q(last_edited__icontains=q)
            )

        sort = (self.request.query_params.get("sort") or "")
        ordering = "-last_edited"
        if ":" in sort:
            field, direction = sort.split(":")
            ordering = f"-{field}" if direction.lower() == "desc" else field
        return qs.order_by(ordering)

    def list(self, request, *args, **kwargs):
        try:
            log_expert_event(request.user, "expert_list_view", dict(request.query_params))
        except Exception:
            pass
        return super().list(request, *args, **kwargs)


class ExpertDatasetDetailView(generics.RetrieveAPIView):
    lookup_field = "data_id"
    queryset = ExpertDataset.objects.all()
    serializer_class = ExpertDatasetSerializer
    permission_classes = [ReadOnlyOrExpert]

    def retrieve(self, request, *args, **kwargs):
        resp = super().retrieve(request, *args, **kwargs)
        try:
            obj = self.get_object()
            log_expert_event(request.user, "expert_dataset_view", {"data_id": obj.data_id})
        except Exception:
            pass
        return resp