import csv
import io
import logging
from django.db import transaction
from rest_framework import generics, status
from rest_framework.exceptions import ValidationError
from rest_framework.parsers import MultiPartParser
from rest_framework.response import Response
from rest_framework.views import APIView
from authentication.permissions import IsTokenAuthenticated
from authentication.security import CustomJWTAuthentication
from curator_feature.serializers import CaseReadSerializer, CaseWriteSerializer
from pt_backend.models import Case
from .permissions import IsExpertUserRole
from pt_backend.models import Disease, Location, CaseUploadBatch
from curator_feature.serializers import CaseReadSerializer, CaseWriteSerializer
from curator_feature.serializers import CaseReadSerializer, CaseWriteSerializer
from .serializers import BatchSerializer

logger = logging.getLogger(__name__)


class _ExpertBaseView(generics.GenericAPIView):
    authentication_classes = [CustomJWTAuthentication]
    permission_classes = [IsTokenAuthenticated, IsExpertUserRole]

class ExpertBatchListView(_ExpertBaseView, generics.ListAPIView):
    serializer_class = BatchSerializer

    def get_queryset(self):
        return CaseUploadBatch.objects.filter(uploaded_by=self.request.user)

class ExpertBatchDeleteView(_ExpertBaseView, APIView):
    def delete(self, request, batch_id):
        batch = CaseUploadBatch.objects.filter(uploaded_by=request.user, id=batch_id).first()
        if not batch:
            return Response({"message": "Batch not found"}, status=404)

        deleted = batch.cases.count()
        batch.cases.all().delete()
        batch.delete()
        return Response({"deleted_cases": deleted}, status=204)

class ExpertCaseListView(_ExpertBaseView, generics.ListAPIView):
    serializer_class = CaseReadSerializer

    def get_queryset(self):
        qs = Case.objects.filter(created_by=self.request.user).select_related("disease", "location", "batch").prefetch_related("news")
        batch = self.request.query_params.get("batch")
        if batch:
            qs = qs.filter(batch_id=batch)
        return qs.order_by("-id")


class ExpertCaseBulkDeleteView(_ExpertBaseView, APIView):
    """
    EXP_USER deletes ONLY cases they uploaded.
    """
    def delete(self, request):
        qs = Case.objects.filter(created_by=request.user)
        deleted = qs.count()
        qs.delete()
        return Response({"deleted_cases": deleted}, status=status.HTTP_204_NO_CONTENT)


class ExpertCaseCSVUploadView(_ExpertBaseView, APIView):
    """
    Upload CSV → create batch of Cases tagged with created_by=user.
    """
    parser_classes = [MultiPartParser]

    REQUIRED_COLUMNS = {
    "disease","gender","age","city","status","severity",
    "location_city","location_province",   # ✅ Now required
    "news_portal","news_title","news_type","news_content",
    "news_url","news_author","news_date_published"
    }

    OPTIONAL_COLUMNS = {
    "location_latitude","location_longitude",
    "news_img_url",
    }

    def post(self, request):
        upload = request.FILES.get("file")
        if not upload:
            return Response({"message": "CSV file missing."}, 400)

        batch = CaseUploadBatch.objects.create(uploaded_by=request.user, filename=upload.name)

        raw = upload.read().decode("utf-8-sig")
        reader = csv.DictReader(io.StringIO(raw))

        created_cases = []
        with transaction.atomic():
            for row in reader:
                payload = self._convert(row)
                serializer = CaseWriteSerializer(data=payload)
                serializer.is_valid(raise_exception=True)
                case = serializer.save(created_by=request.user, batch=batch)
                created_cases.append(case)

        return Response({"batch_id": batch.id, "created": len(created_cases)}, status=201)


    def _convert(self, row):
        def c(v):
            return v.strip() if isinstance(v, str) else v

        def maybe(v):
            v = c(v)
            return None if v in ("", None) else v

        # ✅ CREATE DISEASE IF NOT EXISTS
        disease_name = c(row.get("disease"))
        disease_obj, _ = Disease.objects.get_or_create(
            name=disease_name,
            defaults={"level_of_alertness": 1},
        )

        # ✅ LOCATION (get or create)
        city = c(row.get("location_city")) or c(row.get("city"))
        province = c(row.get("location_province"))
        latitude = maybe(row.get("location_latitude"))
        longitude = maybe(row.get("location_longitude"))

        location_data = {
            "city": city,
            "province": province,
        }

        # ✅ Only include lat/long if provided
        if latitude is not None:
            location_data["latitude"] = latitude
        if longitude is not None:
            location_data["longitude"] = longitude

        return {
            "disease": disease_obj.name,  # ✅ CaseWriteSerializer expects name, not ID
            "gender": c(row.get("gender")),
            "age": c(row.get("age")),
            "city": c(row.get("city")),
            "status": c(row.get("status")),
            "severity": c(row.get("severity")),
            "location": location_data,
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



