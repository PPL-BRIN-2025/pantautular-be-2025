from rest_framework import serializers
from django.db import transaction

from pt_backend.models import Disease, Role
from curator_feature.serializers import (
    LocationByNameSerializer,
    LocationSerializer,
    NewsInlineWriteSerializer,
)
from .models import ContributorCaseSubmission


class ContributorCaseWriteSerializer(serializers.ModelSerializer):
    disease = serializers.CharField(write_only=True, required=False)
    location = LocationByNameSerializer(write_only=True, required=False)
    news = NewsInlineWriteSerializer(write_only=True, required=False)

    class Meta:
        model = ContributorCaseSubmission
        fields = [
            "id",
            "gender",
            "age",
            "city",
            "status",
            "severity",
            "disease",
            "location",
            "news",
            "state",
        ]
        read_only_fields = ["id", "state"]

    def _resolve_disease_id(self, name: str):
        if not name:
            raise serializers.ValidationError({"disease": "This field is required."})

        cleaned = name.strip()
        if not cleaned:
            raise serializers.ValidationError({"disease": "Disease name may not be blank."})

        disease = Disease.objects.filter(name__iexact=cleaned).first()
        if disease:
            return disease.id

        new_disease = Disease.objects.create(name=cleaned, level_of_alertness=1)
        return new_disease.id

    def _resolve_location(self, payload: dict):
        if not payload:
            raise serializers.ValidationError({"location": "This field is required."})
        location_serializer = LocationByNameSerializer(data=payload)
        location_serializer.is_valid(raise_exception=True)
        return location_serializer.resolve()

    def _normalize_news_payload(self, payload: dict):
        if not payload:
            raise serializers.ValidationError({"news": "This field is required."})
        news_serializer = NewsInlineWriteSerializer(data=payload)
        news_serializer.is_valid(raise_exception=True)
        return news_serializer.validated_data

    @transaction.atomic
    def create(self, validated_data):
        disease_name = validated_data.pop("disease", None)
        location_payload = validated_data.pop("location", None)
        news_payload = validated_data.pop("news", None)

        location = self._resolve_location(location_payload)
        news_data = self._normalize_news_payload(news_payload)

        instance = ContributorCaseSubmission.objects.create(
            disease_id=self._resolve_disease_id(disease_name),
            location=location,
            **validated_data,
        )
        instance.set_news_payload(news_data)
        instance.save(update_fields=["news_payload"])
        return instance

    @transaction.atomic
    def update(self, instance, validated_data):
        if "disease" in validated_data:
            instance.disease_id = self._resolve_disease_id(validated_data.pop("disease"))

        if "location" in validated_data:
            instance.location = self._resolve_location(validated_data.pop("location"))

        if "news" in validated_data:
            news_data = self._normalize_news_payload(validated_data.pop("news"))
            instance.set_news_payload(news_data)

        for attr, value in validated_data.items():
            setattr(instance, attr, value)

        instance.save()
        return instance


class ContributorCaseReadSerializer(serializers.ModelSerializer):
    disease_name = serializers.CharField(source="disease.name", read_only=True)
    location = LocationSerializer(read_only=True)
    news = serializers.SerializerMethodField()
    reviewed_by = serializers.SerializerMethodField()
    created_by = serializers.SerializerMethodField()

    class Meta:
        model = ContributorCaseSubmission
        fields = [
            "id",
            "gender",
            "age",
            "city",
            "status",
            "severity",
            "disease_name",
            "location",
            "news",
            "state",
            "review_note",
            "reviewed_at",
            "reviewed_by",
            "created_by",
            "created_at",
            "updated_at",
            "approved_case",
        ]
        read_only_fields = fields

    def get_news(self, obj: ContributorCaseSubmission):
        payload = obj.get_news_payload()
        return payload or None

    def _serialize_user(self, user):
        if not user:
            return None
        return {
            "id": user.id,
            "name": getattr(user, "name", ""),
            "email": getattr(user, "email", ""),
            "role": getattr(user, "role", ""),
        }

    def get_reviewed_by(self, obj):
        return self._serialize_user(obj.reviewed_by)

    def get_created_by(self, obj):
        return self._serialize_user(obj.created_by)


class ContributorCaseReviewSerializer(serializers.Serializer):
    ACTION_CHOICES = ("approve", "reject")

    action = serializers.ChoiceField(choices=ACTION_CHOICES)
    note = serializers.CharField(required=False, allow_blank=True, max_length=1000)

    def validate(self, attrs):
        action = attrs.get("action")
        note = attrs.get("note", "")
        if action == "reject" and not note:
            raise serializers.ValidationError(
                {"note": "A note is required when rejecting a submission."}
            )
        return attrs


class ContributorApprovalRoleUpdateSerializer(serializers.Serializer):
    roles = serializers.ListField(
        child=serializers.CharField(max_length=150),
        allow_empty=False,
    )

    def validate_roles(self, values):
        cleaned = []
        seen = set()
        for raw in values:
            name = str(raw or "").strip()
            if not name:
                raise serializers.ValidationError("Role names may not be blank.")
            key = name.upper()
            if key in seen:
                continue
            try:
                role = Role.objects.get(name__iexact=name)
            except Role.DoesNotExist as exc:
                raise serializers.ValidationError(f"Role '{name}' not found.") from exc
            cleaned.append(role)
            seen.add(key)
        if not cleaned:
            raise serializers.ValidationError("Provide at least one valid role.")
        self.role_objects = cleaned
        return [role.name for role in cleaned]
