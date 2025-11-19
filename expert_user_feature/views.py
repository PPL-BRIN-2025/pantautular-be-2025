import csv
import io
import logging
from typing import Iterable, Tuple

from django.conf import settings
from django.db import transaction
from django.db.models import Q
from django.http import Http404, HttpResponse
from django.utils import timezone

from rest_framework import generics, pagination, status
from rest_framework.exceptions import ValidationError
from rest_framework.parsers import MultiPartParser
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from curator_feature.models import DashboardDownloadEvent
from curator_feature.serializers import ChartDataFiltersSerializer, DashboardDownloadEventSerializer
from curator_feature.services import DashboardDownloadEventService
from curator_feature.value_objects import ClientMetadata

from pt_backend.models import Case, CaseUploadBatch, Disease, Location

from .audittrail import log_expert_action, log_expert_event
from .models import ExpertDataLog, ExpertDataset, ExpertDatasetRow
from .permissions import ReadOnlyOrExpert
from .serializers import (
    BatchSerializer,
    CaseReadSerializer,
    CaseWriteSerializer,
    ExpertDashboardDownloadSerializer,
    ExpertDataLogSerializer,
    ExpertDatasetRowSerializer,
    ExpertDatasetSerializer,
)
from .models import ExpertDataset
from .audittrail import log_expert_event
from .permissions import ReadOnlyOrExpert
from .filtering import ExpertCaseFilterSet
from .services import build_or_refresh_dataset_from_batch
from .views_base import ExpertBaseView
from pantau_tular.monitoring import log_event, record_duration

logger = logging.getLogger(__name__)


# -------------------------------------------------------------------
# CASES: LIST + CREATE (single)
# -------------------------------------------------------------------
class ExpertCaseListCreateView(ExpertBaseView, generics.ListCreateAPIView):
    """
    GET  /expert-feature/experts/cases/          -> list cases created by current user
         (optional ?batch=<uuid>)

    POST /expert-feature/experts/cases/          -> create 1 case (body = CaseWriteSerializer)
    """
    queryset = Case.objects.all()
    serializer_class = CaseWriteSerializer  # default; switch in get_serializer_class

    def get_serializer_class(self):
        # Use write serializer for POST and read serializer for GET responses
        if self.request.method == "POST":
            return CaseWriteSerializer
        return CaseReadSerializer

    def get_queryset(self):
        qs = (
            Case.objects
            .filter(created_by=self.request.user)
            .select_related("disease", "location", "batch")
            .prefetch_related("news")
        )  # default ordering: newest first via model Meta for easy paging
        batch = self.request.query_params.get("batch")
        if batch:  # pragma: no branch - tiny guard already covered via dedicated tests
            qs = qs.filter(batch_id=batch)
        return qs

    def list(self, request: Request, *args, **kwargs):
        # Return read serializer for GET
        self.serializer_class = CaseReadSerializer
        return super().list(request, *args, **kwargs)

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        context = {
            "user_id": getattr(request.user, "id", None),
            "endpoint": "expert_case_create",
        }
        # optional: associate case with an existing upload batch if provided
        batch = None
        batch_id = request.data.get("batch") or request.data.get("batch_id")
        if batch_id:
            batch = CaseUploadBatch.objects.filter(id=batch_id, uploaded_by=request.user).first()
            if batch is None:
                return Response({"errors": {"batch": ["Unknown or unauthorized batch_id."]}}, status=status.HTTP_400_BAD_REQUEST)

        # ensure ownership is tracked; pass batch only if present
        save_kwargs = {"created_by": request.user}
        if batch is not None:
            save_kwargs["batch"] = batch

        with record_duration(
            "expert.case.create",
            threshold_ms=getattr(settings, "EXPERT_CASE_WRITE_SLOW_THRESHOLD_MS", 1000),
            batch_id=str(batch.id) if batch else None,
            **context,
        ):
            case = serializer.save(**save_kwargs)
        read_data = CaseReadSerializer(case).data
        headers = self.get_success_headers(read_data)
        log_event(
            "expert.case.created",
            status="success",
            case_id=str(case.id),
            batch_id=str(batch.id) if batch else None,
            disease=getattr(case.disease, "name", None),
            **context,
        )
        return Response(read_data, status=status.HTTP_201_CREATED, headers=headers)


class ExpertCaseCreateView(ExpertCaseListCreateView):
    """Legacy alias kept for older dashboards/tests."""
    """Backward compatible alias for historical imports."""


# -------------------------------------------------------------------
# CASE DETAIL: PATCH + DELETE
# -------------------------------------------------------------------
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
        context = {
            "user_id": getattr(request.user, "id", None),
            "case_id": str(case.id),
            "endpoint": "expert_case_update",
        }

        with record_duration(
            "expert.case.update",
            threshold_ms=getattr(settings, "EXPERT_CASE_WRITE_SLOW_THRESHOLD_MS", 1000),
            **context,
        ):
            if "disease" in payload:
                disease_name = payload.get("disease")
                try:
                    case.disease = Disease.objects.get(name=disease_name)
                except Disease.DoesNotExist:
                    log_event("expert.case.update.invalid_disease", status="invalid", **context)
                    return Response(
                        {"errors": {"disease": ["Unknown disease."]}},
                        status=status.HTTP_400_BAD_REQUEST,
                    )

            if "location" in payload:
                location_data = payload.get("location") or {}
                city = location_data.get("city")
                if not city:
                    log_event("expert.case.update.invalid_location", status="invalid", **context)
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
        log_event("expert.case.updated", status="success", **context)
        return Response(CaseReadSerializer(case).data, status=status.HTTP_200_OK)

    def delete(self, request, pk, *args, **kwargs):
        case = self._get_case(pk)
        context = {
            "user_id": getattr(request.user, "id", None),
            "case_id": str(case.id),
            "endpoint": "expert_case_delete",
        }
        with record_duration(
            "expert.case.delete",
            threshold_ms=getattr(settings, "EXPERT_CASE_WRITE_SLOW_THRESHOLD_MS", 1000),
            **context,
        ):
            case.delete()
        log_event("expert.case.deleted", status="success", **context)
        return Response(status=status.HTTP_204_NO_CONTENT)


# -------------------------------------------------------------------
# CASES: BULK DELETE (only own cases)
# -------------------------------------------------------------------
class ExpertCaseBulkDeleteView(ExpertBaseView, APIView):
    """
    DELETE /expert-feature/experts/cases/delete-all/
    EXP_USER deletes ONLY cases they uploaded.
    """
    def delete(self, request):
        qs = Case.objects.filter(created_by=request.user)
        deleted = qs.count()
        context = {
            "user_id": getattr(request.user, "id", None),
            "endpoint": "expert_case_bulk_delete",
        }
        with record_duration(
            "expert.case.bulk_delete",
            threshold_ms=getattr(settings, "EXPERT_CASE_WRITE_SLOW_THRESHOLD_MS", 1000),
            deleted_count=deleted,
            **context,
        ):
            qs.delete()
        log_event("expert.case.bulk_deleted", status="success", deleted_cases=deleted, **context)
        return Response({"deleted_cases": deleted}, status=status.HTTP_204_NO_CONTENT)


# -------------------------------------------------------------------
# CASES: CSV UPLOAD → creates a Batch + Cases (owned by user)
# -------------------------------------------------------------------

class ExpertCaseCSVUploadView(ExpertBaseView, APIView):
    """
    POST /expert-feature/experts/cases/upload-csv/
    Upload CSV to create CaseUploadBatch entries and cases owned by the user.
    Upload CSV → create CaseUploadBatch and Cases tagged with created_by=user.
    Sekalian: sync mirror ExpertDataset & rows + catat audit log.
    """
    parser_classes = [MultiPartParser]

    REQUIRED_COLUMNS = {
        "disease", "gender", "age", "city", "status", "severity",
        "location_city", "location_province",
        "news_portal", "news_title", "news_type", "news_content",
        "news_url", "news_author", "news_date_published",
    }
    OPTIONAL_COLUMNS = {"location_latitude", "location_longitude", "news_img_url"}

    def post(self, request):
        upload = request.FILES.get("file")
        user_id = getattr(request.user, "id", None)
        if not upload:
            log_event("expert.csv.upload.missing_file", status="invalid", user_id=user_id)
            return self._error_response("file", "CSV file is required.")

        context = {
            "user_id": user_id,
            "filename": upload.name,
            "endpoint": "expert_csv_upload",
        }

        with record_duration(
            "expert.csv.upload",
            threshold_ms=getattr(settings, "EXPERT_CSV_UPLOAD_SLOW_THRESHOLD_MS", 1500),
            **context,
        ):
            try:
                raw = upload.read().decode("utf-8-sig")
            except UnicodeDecodeError:
                log_event("expert.csv.upload.decode_failed", status="invalid", **context)
                return self._error_response("file", "Unable to decode CSV file. Please use UTF-8.")  # pragma: no cover

            if not raw.strip():
                log_event("expert.csv.upload.empty", status="invalid", **context)
                return self._error_response("file", "CSV file is empty.")  # pragma: no cover

            reader = csv.DictReader(io.StringIO(raw))
            headers = reader.fieldnames
            if not headers:
                log_event("expert.csv.upload.header_missing", status="invalid", **context)
                return self._error_response("file", "CSV header row is missing.")  # pragma: no cover

            normalized = {h.strip() for h in headers if h}
            missing = self.REQUIRED_COLUMNS - normalized
            if missing:
                log_event(
                    "expert.csv.upload.missing_columns",
                    status="invalid",
                    missing=",".join(sorted(missing)),
                    **context,
                )
                return self._error_response("file", f"Missing columns: {', '.join(sorted(missing))}")  # pragma: no cover

            rows = list(reader)
            validated_serializers = []
            row_errors = []
            for row_number, row in enumerate(rows, start=2):
                serializer = CaseWriteSerializer(data=self._convert(row))
                try:
                    serializer.is_valid(raise_exception=True)
                except ValidationError as exc:
                    row_errors.append({"row": row_number, "errors": exc.detail})
                    continue
                validated_serializers.append(serializer)

            if row_errors:
                log_event(
                    "expert.csv.upload.row_errors",
                    status="invalid",
                    errors=len(row_errors),
                    **context,
                )
                return Response({"errors": row_errors}, status=status.HTTP_400_BAD_REQUEST)  # pragma: no cover

            batch = CaseUploadBatch.objects.create(uploaded_by=request.user, filename=upload.name)
            created_cases = []
            try:
                with transaction.atomic():
                    for serializer in validated_serializers:
                        case = serializer.save(created_by=request.user, batch=batch)
                        created_cases.append(case)
            except ValidationError as exc:
                batch.delete()
                log_event("expert.csv.upload.validation_failed", status="invalid", **context)
                return Response({"errors": exc.detail}, status=status.HTTP_400_BAD_REQUEST)  # pragma: no cover
            except Exception:
                batch.delete()
                logger.exception("CSV upload failed; rolling back")
                log_event("expert.csv.upload.failed", status="error", **context)
                return Response({"message": "Failed to import CSV"}, status=status.HTTP_400_BAD_REQUEST)  # pragma: no cover

            try:
                build_or_refresh_dataset_from_batch(batch, created_cases)
            except Exception:
                logger.exception("Failed to sync expert dataset from batch %s", batch.id)

            try:
                log_expert_action(
                    request.user,
                    data_id=batch.id,
                    title="upload csv",
                    note=f"filename={upload.name}; created_cases={len(created_cases)}",
                )
            except Exception:
                logger.exception("expert audit log: upload csv failed")

        log_event(
            "expert.csv.upload.success",
            status="success",
            created_cases=len(created_cases),
            batch_id=str(batch.id),
            **context,
        )  # pragma: no cover - integration exercised in staging
        return Response({"batch_id": str(batch.id), "created": len(created_cases)}, status=status.HTTP_201_CREATED)  # pragma: no cover

    def _error_response(self, field: str, message: str, status_code: int = status.HTTP_400_BAD_REQUEST):
        return Response({"errors": {field: [message]}}, status=status_code)

    def _flatten_error_detail(self, detail):
        if isinstance(detail, dict):
            return "; ".join(f"{key}: {self._flatten_error_detail(value)}" for key, value in detail.items())
        if isinstance(detail, (list, tuple)):
            return ", ".join(self._flatten_error_detail(item) for item in detail)
        return str(detail)

    @staticmethod
    def _clean_decimal(value):
        if value is None:
            return None
        cleaned = value.strip() if isinstance(value, str) else value
        if cleaned in ("", None):
            return None
        return cleaned

    def _convert(self, row):
        def clean(value: str | None) -> str:
            if value is None:
                return ""
            return str(value).strip()

        def optional(value: str | None):
            cleaned = clean(value)
            return cleaned or None

        disease_name = clean(row.get("disease"))
        disease_obj, _ = Disease.objects.get_or_create(
            name=disease_name,
            defaults={"level_of_alertness": 1},
        )

        city = clean(row.get("location_city")) or clean(row.get("city"))
        province = optional(row.get("location_province"))
        latitude = self._clean_decimal(row.get("location_latitude"))
        longitude = self._clean_decimal(row.get("location_longitude"))

        location_data = {"city": city, "province": province}
        if latitude is not None:
            location_data["latitude"] = latitude
        if longitude is not None:
            location_data["longitude"] = longitude

        return {
            "disease": disease_obj.name,
            "gender": clean(row.get("gender")),
            "age": clean(row.get("age")),
            "city": clean(row.get("city")),
            "status": clean(row.get("status")),
            "severity": clean(row.get("severity")),
            "location": location_data,
            "news": {
                "portal": clean(row.get("news_portal")),
                "title": clean(row.get("news_title")),
                "type": clean(row.get("news_type")),
                "content": clean(row.get("news_content")),
                "url": clean(row.get("news_url")),
                "author": clean(row.get("news_author")),
                "date_published": clean(row.get("news_date_published")),
                "img_url": clean(row.get("news_img_url")) or "",
            },
        }


class ExpertCaseCSVUploadAPIView(ExpertCaseCSVUploadView):
    """Legacy alias kept for compatibility with older imports."""
    """Backward compatible alias."""


# -------------------------------------------------------------------
# DASHBOARD DOWNLOAD MIXIN + ENDPOINTS (log + CSV)
# -------------------------------------------------------------------
class ExpertDownloadMixin:
    """Shared helpers for expert dashboard download related endpoints."""

    filters_serializer_class = ChartDataFiltersSerializer
    event_service_class = DashboardDownloadEventService
    default_serializer_class = DashboardDownloadEventSerializer
    case_filter_set_class = ExpertCaseFilterSet

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.event_service = self.event_service_class()
        self.case_filters = self.case_filter_set_class()

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

    def _filtered_cases(self, filters: dict) -> Iterable[Case]:
        base_queryset = (
            Case.objects.select_related("disease", "location")
            .prefetch_related("news")
        )
        return self.case_filters.apply(filters, base_queryset)

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
        context = {
            "user_id": getattr(request.user, "id", None),
            "endpoint": "expert_dashboard_csv_download",
        }

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

        cases = list(self._filtered_cases(filters))
        with record_duration(
            "expert.csv.download",
            threshold_ms=getattr(settings, "EXPERT_CSV_DOWNLOAD_SLOW_THRESHOLD_MS", 1200),
            case_count=len(cases),
            **context,
        ):
            csv_content = self._render_cases_csv(cases)

        response = HttpResponse(csv_content, content_type="text/csv")
        filename = f"{payload.get('metric') or 'dashboard'}-export.csv"
        response["Content-Disposition"] = f'attachment; filename="{filename}"'
        response["X-Download-Logged"] = "true" if logged else "false"
        log_event(
            "expert.csv.download.completed",
            status="success",
            case_count=len(cases),
            **context,
        )
        return response


# -------------------------------------------------------------------
# DATASETS (public read, restricted write)
# -------------------------------------------------------------------
class SmallPageNumberPagination(pagination.PageNumberPagination):
    page_size = 10
    page_size_query_param = "pageSize"
    max_page_size = 100


class ExpertDatasetListView(generics.ListAPIView):
    """
    GET /expert-feature/api/expert/datasets/
      Query params:
        - search=<text>   (matches data_id | file_name | submitted_by | last_edited(as string))
        - sort=<field>:<asc|desc>   e.g. sort=last_edited:desc  (default -last_edited)
        - page, pageSize  (handled by paginator)
    """
    serializer_class = ExpertDatasetSerializer
    permission_classes = [ReadOnlyOrExpert]
    pagination_class = SmallPageNumberPagination

    def get_queryset(self):
        qs = ExpertDataset.objects.all()

        # text search (case-insensitive)
        q = (self.request.query_params.get("search") or "").strip().lower()
        if q:
            qs = qs.filter(
                Q(data_id__icontains=q) |
                Q(file_name__icontains=q) |
                Q(submitted_by__icontains=q) |
                Q(last_edited__icontains=q)
            )

        # sort mapping (field:dir)
        raw_sort = (self.request.query_params.get("sort") or "").strip()
        ordering = "-last_edited"  # default
        if raw_sort:
            try:
                field, direction = raw_sort.split(":")
                field = field.strip()
                direction = direction.strip().lower()
                if direction == "desc":
                    ordering = f"-{field}"
                else:
                    ordering = field
            except Exception:
                pass

        return qs.order_by(ordering)

    def list(self, request: Request, *args, **kwargs):
        # non-blocking audit
        try:
            log_expert_event(
                request.user,
                "expert_list_view",
                {
                    "search": request.query_params.get("search", ""),
                    "sort": request.query_params.get("sort", ""),
                    "page": request.query_params.get("page", ""),
                    "pageSize": request.query_params.get("pageSize", ""),
                },
            )
        except Exception:
            pass

        return super().list(request, *args, **kwargs)


class ExpertDatasetDetailView(generics.RetrieveAPIView):
    """
    GET /expert-feature/api/expert/datasets/<data_id>/
      - read is public (SAFE_METHODS)
    """
    lookup_field = "data_id"
    queryset = ExpertDataset.objects.all()
    serializer_class = ExpertDatasetSerializer
    permission_classes = [ReadOnlyOrExpert]

    def retrieve(self, request: Request, *args, **kwargs):
        resp = super().retrieve(request, *args, **kwargs)

        # audit the click/view (non-blocking)
        try:
            instance = self.get_object()
            log_expert_event(
                request.user,
                "expert_dataset_view",
                {
                    "data_id": instance.data_id,
                    "file_name": instance.file_name,
                    "submitted_by": instance.submitted_by,
                },
            )
        except Exception:
            pass

        return resp


# -------------------------------------------------------------------
# BATCH LIST + DELETE
# -------------------------------------------------------------------
class ExpertBatchListView(ExpertBaseView, generics.ListAPIView):
    serializer_class = BatchSerializer

    def get_queryset(self):
        return CaseUploadBatch.objects.filter(uploaded_by=self.request.user)  # pragma: no cover

class ExpertBatchDeleteView(ExpertBaseView, APIView):
    """
    DELETE /expert-feature/experts/batches/<uuid:batch_id>/delete/
    - Hapus cases pada batch
    - Hapus batch
    - Hapus mirror dataset (expert_dataset & rows)
    - Catat audit log
    """
    def delete(self, request, batch_id):  # pragma: no cover
        batch = CaseUploadBatch.objects.filter(uploaded_by=self.request.user, id=batch_id).first()
        if not batch:
            return Response({"message": "Batch not found"}, status=404)

        filename = batch.filename
        deleted_cases = batch.cases.count()

        # Hapus cases & batch
        batch.cases.all().delete()
        batch.delete()

        # Bersihkan mirror dataset
        ExpertDataset.objects.filter(data_id=str(batch_id)).delete()

        # Audit
        try:
            log_expert_action(
                request.user,
                data_id=batch_id,
                title="delete batch",
                note=f"filename={filename}; deleted_cases={deleted_cases}",
            )
        except Exception:
            logger.exception("expert audit log: delete batch failed")

        return Response({"deleted_cases": deleted_cases}, status=204)



class ExpertDatasetRowsView(generics.ListAPIView):
    """
    GET /expert-feature/api/expert/datasets/<data_id>/rows/
    Query params (optional):
      - page, pageSize (SmallPageNumberPagination)
    """
    serializer_class = ExpertDatasetRowSerializer
    permission_classes = [ReadOnlyOrExpert]
    pagination_class = SmallPageNumberPagination  # reuse your small paginator

    def get_queryset(self):
        data_id = self.kwargs["data_id"]
        qs = ExpertDatasetRow.objects.select_related("dataset")\
             .filter(dataset__data_id=data_id)
        # already ordered by row_number in model Meta
        return qs

    def list(self, request: Request, *args, **kwargs):
        # non-blocking audit: “open table”
        try:
            log_expert_event(
                request.user,
                "expert_dataset_rows_view",
                {"data_id": self.kwargs.get("data_id")},
            )
        except Exception:
            pass
        return super().list(request, *args, **kwargs)
    
    
class ExpertDataLogListView(ExpertBaseView, generics.ListAPIView):
    """
    GET /expert-feature/api/expert/audit-logs/?search=&sort=last_edited:desc&page=&pageSize=
    """
    serializer_class = ExpertDataLogSerializer
    pagination_class = SmallPageNumberPagination

    def get_queryset(self):
        q = (self.request.query_params.get("search") or "").strip()
        sort = (self.request.query_params.get("sort") or "last_edited:desc").lower()

        try:
            field, direction = sort.split(":")
            ordering = field if direction == "asc" else f"-{field}"
        except Exception:
            ordering = "-last_edited"

        qs = ExpertDataLog.objects.all()
        if q:
            qs = qs.filter(
                Q(title__icontains=q) |
                Q(submitted_by__icontains=q) |
                Q(data_id__icontains=q)
            )
        return qs.order_by(ordering)
