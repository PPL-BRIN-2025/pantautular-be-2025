import uuid
from datetime import datetime, timezone as dt_timezone
from django.db import models, transaction
from django.utils import timezone
from django.utils.dateparse import parse_datetime

from pt_backend.models import Case, Disease, Location, Role, User


def _default_news_payload():
    return {}


class ContributorCaseSubmission(models.Model):
    class ReviewState(models.TextChoices):
        PENDING = "PENDING", "Pending"
        APPROVED = "APPROVED", "Approved"
        REJECTED = "REJECTED", "Rejected"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    gender = models.CharField(max_length=10)
    age = models.PositiveIntegerField()
    city = models.CharField(max_length=255)
    status = models.CharField(max_length=20, choices=Case.STATUS_CHOICES)
    severity = models.CharField(max_length=255, choices=Case.SEVERITY_CHOICES)
    disease = models.ForeignKey(
        Disease,
        on_delete=models.PROTECT,
        related_name="contributor_submissions",
    )
    location = models.ForeignKey(
        Location,
        on_delete=models.PROTECT,
        related_name="contributor_submissions",
    )
    news_payload = models.JSONField(default=_default_news_payload, blank=True)
    state = models.CharField(
        max_length=20,
        choices=ReviewState.choices,
        default=ReviewState.PENDING,
        db_index=True,
    )
    review_note = models.TextField(blank=True, default="")
    reviewed_by = models.ForeignKey(
        User,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="reviewed_contributor_submissions",
    )
    reviewed_at = models.DateTimeField(null=True, blank=True)
    approved_case = models.ForeignKey(
        Case,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="source_contributor_submissions",
    )
    created_by = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="contributor_submissions",
    )
    updated_by = models.ForeignKey(
        User,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="contributor_submissions_updated",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("-created_at", "-id")
        indexes = [
            models.Index(fields=["state", "-created_at"]),
            models.Index(fields=["created_by", "-created_at"]),
        ]

    def __str__(self):
        disease_name = getattr(self.disease, "name", "Unknown Disease")
        return f"{disease_name} - {self.city} ({self.state})"

    @property
    def is_pending(self) -> bool:
        return self.state == self.ReviewState.PENDING

    def serialize_news_payload(self, payload: dict) -> dict:
        """Ensure datetime values are serialized to ISO strings before saving."""
        serialized = {}
        for key, value in (payload or {}).items():
            if value is None:
                continue
            if isinstance(value, datetime):
                as_dt = value
                if timezone.is_aware(as_dt):
                    as_dt = timezone.make_naive(as_dt, timezone=dt_timezone.utc)
                    serialized[key] = f"{as_dt.isoformat()}Z"
                else:
                    serialized[key] = as_dt.isoformat()
            else:
                serialized[key] = value
        return serialized

    def set_news_payload(self, payload: dict | None):
        self.news_payload = self.serialize_news_payload(payload or {})

    def get_news_payload(self) -> dict:
        return self.news_payload or {}

    def news_payload_for_case(self) -> dict:
        """Return payload ready to be used for pt_backend.models.News creation."""
        payload = self.get_news_payload()
        if not payload:
            return {}

        cleaned = {}
        for key, value in payload.items():
            if value in (None, ""):
                continue
            if key == "date_published":
                cleaned[key] = self._parse_date(value)
            else:
                cleaned[key] = value
        return cleaned

    def _parse_date(self, value):
        if not value:
            return None
        if isinstance(value, datetime):
            if timezone.is_aware(value):
                return value
            return timezone.make_aware(value, timezone.get_current_timezone())
        parsed = parse_datetime(str(value))
        if parsed is None:
            return timezone.now()
        if timezone.is_naive(parsed):
            parsed = timezone.make_aware(parsed, timezone.get_current_timezone())
        return parsed


class ContributorApprovalRole(models.Model): 
    DEFAULT_ROLE_NAMES = ("CURATOR", "ADMIN")

    role = models.OneToOneField(
        Role,
        on_delete=models.CASCADE,
        related_name="contributor_approval_role",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "contributor_feature_approval_roles"
        ordering = ("role__name",)
        verbose_name = "Contributor approval role"
        verbose_name_plural = "Contributor approval roles"

    def __str__(self):
        return f"{self.role.name} approver"

    @classmethod
    def allowed_role_names(cls) -> set[str]:
        names = list(
            cls.objects.select_related("role").values_list("role__name", flat=True)
        )
        if names:
            return {str(name).upper() for name in names}
        return {name.upper() for name in cls.DEFAULT_ROLE_NAMES}

    @classmethod
    def user_is_approver(cls, user: User | None) -> bool:
        role = getattr(user, "role", None)
        if not role:
            return False
        return str(role).upper() in cls.allowed_role_names()

    @classmethod
    def set_allowed_roles(cls, roles: list[Role]):
        role_ids = {role.id for role in roles}
        with transaction.atomic():
            cls.objects.exclude(role_id__in=role_ids).delete()
            existing = set(
                cls.objects.filter(role_id__in=role_ids).values_list("role_id", flat=True)
            )
            for role in roles:
                if role.id not in existing:
                    cls.objects.create(role=role)
