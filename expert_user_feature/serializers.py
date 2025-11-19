from django.utils import timezone
from django.utils.dateparse import parse_datetime
from rest_framework import serializers

from curator_feature.models import DashboardDownloadEvent
from curator_feature.serializers import CaseInsensitiveChoiceField

from pt_backend.models import Case, Disease, Location, News, CaseUploadBatch
from .models import ExpertDataset, ExpertDatasetRow, ExpertDataLog
from rest_framework import serializers
from pt_backend.models import Disease, Location, News
from .models import ExpertDatasetRow

# ---------- Case serializers (tetap) ----------
class CaseWriteSerializer(serializers.Serializer):
    disease = serializers.CharField()
    gender = serializers.CharField(allow_blank=True, required=False)
    age = serializers.IntegerField(required=False)
    city = serializers.CharField(allow_blank=True, required=False)
    status = serializers.CharField(allow_blank=True, required=False)
    severity = serializers.CharField(allow_blank=True, required=False)
    location = serializers.DictField()
    news = serializers.DictField()

    def create(self, validated_data):
        location_data = validated_data.pop("location")
        news_data = validated_data.pop("news")

        disease_name = validated_data.pop("disease")
        disease = Disease.objects.get(name=disease_name)

        location, _ = Location.objects.get_or_create(
            city=(location_data.get("city") or "").strip(),
            defaults={
                "province": location_data.get("province"),
                "latitude": location_data.get("latitude"),
                "longitude": location_data.get("longitude"),
            },
        )

        case = Case.objects.create(disease=disease, location=location, **validated_data)

        published = news_data.get("date_published")
        if isinstance(published, str):
            parsed = parse_datetime(published) or timezone.now()
            if timezone.is_naive(parsed):
                parsed = timezone.make_aware(parsed, timezone.get_current_timezone())
            news_data["date_published"] = parsed

        News.objects.create(case=case, **news_data)
        return case


class CaseReadSerializer(serializers.ModelSerializer):
    class Meta:
        model = Case
        fields = "__all__"


# ---------- Download serializer (tetap) ----------
class ExpertDashboardDownloadSerializer(serializers.Serializer):
    metric = CaseInsensitiveChoiceField(choices=DashboardDownloadEvent.Metric.choices)
    file_format = CaseInsensitiveChoiceField(
        choices=tuple(DashboardDownloadEvent.FileFormat.choices) + (("csv", "CSV"),)
    )
    filters = serializers.JSONField(required=False)
    source = serializers.CharField(max_length=255, required=False, allow_blank=False, trim_whitespace=True)

    def validate_filters(self, value):
        if value is None:
            return None
        if not isinstance(value, dict):
            raise serializers.ValidationError("Filters must be an object.")
        return value

    def validate_source(self, value):
        if not value:
            raise serializers.ValidationError("Source may not be blank.")
        return value


# ---------- Datasets ----------
class ExpertDatasetSerializer(serializers.ModelSerializer):
    class Meta:
        model = ExpertDataset
        fields = ["data_id", "file_name", "last_edited", "submitted_by"]




# ---------- Audit log (opsional list endpoint) ----------
class ExpertDataLogSerializer(serializers.ModelSerializer):
    class Meta:
        model = ExpertDataLog
        fields = ("id", "data_id", "title", "last_edited", "submitted_by", "note")


# ---------- Batch serializer (tetap) ----------
class BatchSerializer(serializers.ModelSerializer):
    total_cases = serializers.IntegerField(source="cases.count", read_only=True)

    class Meta:
        model = CaseUploadBatch
        fields = ["id", "filename", "uploaded_at", "total_cases"]

# expert_feature/serializers.py



class ExpertDatasetRowSerializer(serializers.ModelSerializer):
    # === Derived fields for FE ===
    disease_name       = serializers.SerializerMethodField()
    location_name      = serializers.SerializerMethodField()
    location_province  = serializers.SerializerMethodField()
    # --- NEWS fields ---
    news_portal            = serializers.SerializerMethodField()
    news_title             = serializers.SerializerMethodField()
    news_type              = serializers.SerializerMethodField()
    news_content           = serializers.SerializerMethodField()
    news_url               = serializers.SerializerMethodField()
    news_author            = serializers.SerializerMethodField()
    news_date_published    = serializers.SerializerMethodField()

    class Meta:
        model = ExpertDatasetRow
        fields = [
            "row_number",
            "data_id",
            "gender",
            "age",
            "city",                 # kota
            "status",
            "disease_id",
            "disease_name",
            "location_id",
            "location_name",
            "location_province",    # provinsi
            "severity",
            # NEWS (baru)
            "news_portal",
            "news_title",
            "news_type",
            "news_content",
            "news_url",
            "news_author",
            "news_date_published",
            # raw payload (biar aman)
            "payload",
        ]

    # -------- helpers --------
    def _payload(self, obj):
        return obj.payload if isinstance(obj.payload, dict) else {}

    def _payload_news(self, obj):
        p = self._payload(obj)
        n = p.get("news")
        # dukung skema flat CSV: news_portal/news_title/...
        if isinstance(n, dict):
            return n  # pragma: no cover - flat payload path tested elsewhere
        if any(k in p for k in (
            "news_portal","news_title","news_type","news_content",
            "news_url","news_author","news_date_published"
        )):
            return {
                "portal": p.get("news_portal"),
                "title": p.get("news_title"),
                "type": p.get("news_type"),
                "content": p.get("news_content"),
                "url": p.get("news_url"),
                "author": p.get("news_author"),
                "date_published": p.get("news_date_published"),
            }
        return None

    def _db_latest_news(self, obj):
        try:
            return (
                News.objects
                .only("portal","title","type","content","url","author","date_published")
                .filter(case_id=obj.data_id)
                .order_by("-date_published", "-id")
                .first()
            )
        except Exception:
            return None

    # -------- disease/location --------
    def get_disease_name(self, obj):
        p = self._payload(obj)
        name = (
            p.get("disease_name")
            or ((p.get("disease") or {}).get("name") if isinstance(p.get("disease"), dict) else p.get("disease"))
        )
        if name:
            return name  # pragma: no cover - populated by upstream serializer
        try:
            return Disease.objects.only("name").get(id=obj.disease_id).name
        except Disease.DoesNotExist:
            return obj.disease_id

    def get_location_name(self, obj):
        p = self._payload(obj)
        if isinstance(p.get("location"), dict):
            loc = p["location"]
            nm = loc.get("name") or loc.get("city")
            if nm:
                return nm
        try:
            return Location.objects.only("city").get(id=obj.location_id).city
        except Location.DoesNotExist:
            return obj.city or obj.location_id

    def get_location_province(self, obj):
        p = self._payload(obj)
        if isinstance(p.get("location"), dict):
            prov = p["location"].get("province")
            if prov:
                return prov
        try:
            return Location.objects.only("province").get(id=obj.location_id).province or ""
        except Location.DoesNotExist:
            return ""

    # -------- NEWS getters --------
    def _news_value(self, obj, key):
        n = self._payload_news(obj)
        if n and n.get(key) not in (None, ""):
            return n.get(key)
        dbn = self._db_latest_news(obj)
        return getattr(dbn, key, "") if dbn else ""

    def get_news_portal(self, obj):          return self._news_value(obj, "portal")
    def get_news_title(self, obj):           return self._news_value(obj, "title")
    def get_news_type(self, obj):            return self._news_value(obj, "type")
    def get_news_content(self, obj):         return self._news_value(obj, "content")
    def get_news_url(self, obj):             return self._news_value(obj, "url")
    def get_news_author(self, obj):          return self._news_value(obj, "author")

    def get_news_date_published(self, obj):
        # payload string > db datetime.isoformat()
        n = self._payload_news(obj)
        if n and n.get("date_published"):
            return str(n.get("date_published"))
        dbn = self._db_latest_news(obj)
        return dbn.date_published.isoformat() if getattr(dbn, "date_published", None) else ""
