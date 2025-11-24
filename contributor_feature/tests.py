from datetime import datetime

from django.urls import reverse
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APIClient

from django.test import TestCase
from contributor_feature.views import ContributorCaseDetailView, ContributorCaseListCreateView

from contributor_feature.models import ContributorApprovalRole, ContributorCaseSubmission
from pt_backend.models import Case, Disease, Location, News, Role, User


class ContributorFeatureAPITests(TestCase):
    def setUp(self):
        self.client = APIClient()

        self.role_contributor = Role.objects.create(name="CONTRIBUTOR")
        self.role_curator = Role.objects.create(name="CURATOR")
        self.role_admin = Role.objects.create(name="ADMIN")

        ContributorApprovalRole.objects.create(role=self.role_curator)

        self.contributor = User.objects.create(
            name="Contributor",
            email="contributor@example.com",
            password="pwd",
            role="CONTRIBUTOR",
        )
        self.curator = User.objects.create(
            name="Curator",
            email="curator@example.com",
            password="pwd",
            role="CURATOR",
        )
        self.admin = User.objects.create(
            name="Admin",
            email="admin@example.com",
            password="pwd",
            role="ADMIN",
        )

        self.disease = Disease.objects.create(name="Flu", level_of_alertness=1)
        self.location = Location.objects.create(
            city="Jakarta",
            province="DKI Jakarta",
            latitude=1.0,
            longitude=106.0,
        )

        self.base_payload = {
            "gender": "male",
            "age": 30,
            "city": "Jakarta",
            "status": "biasa",
            "severity": "insiden",
            "disease": self.disease.name,
            "location": {"city": "Jakarta"},
            "news": {
                "portal": "Portal",
                "title": "Case News",
                "type": "Article",
                "content": "Content",
                "url": "https://example.com/news",
                "author": "Reporter",
                "date_published": timezone.now().isoformat(),
                "img_url": "https://example.com/img.jpg",
            },
        }

    def _auth(self, user):
        self.client.force_authenticate(user=user)

    def _create_submission(self):
        self._auth(self.contributor)
        response = self.client.post(
            reverse("contributor-case-list"),
            data=self.base_payload,
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        submission_id = response.data["id"]
        return ContributorCaseSubmission.objects.get(id=submission_id)

    def test_contributor_can_submit_case(self):
        self._auth(self.contributor)
        response = self.client.post(
            reverse("contributor-case-list"),
            data=self.base_payload,
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data["state"], "PENDING")
        self.assertEqual(ContributorCaseSubmission.objects.count(), 1)
        self.assertEqual(Case.objects.count(), 0, "Cases should not be created before approval.")

    def test_curator_can_approve_submission(self):
        submission = self._create_submission()
        self._auth(self.curator)

        response = self.client.post(
            reverse("contributor-case-review", args=[submission.id]),
            data={"action": "approve", "note": "Looks good"},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        submission.refresh_from_db()
        self.assertEqual(submission.state, ContributorCaseSubmission.ReviewState.APPROVED)
        self.assertTrue(submission.approved_case_id)
        self.assertEqual(Case.objects.count(), 1)
        self.assertEqual(News.objects.count(), 1)

    def test_role_configuration_limits_reviewers(self):
        submission = self._create_submission()

        self._auth(self.admin)
        response = self.client.put(
            reverse("contributor-approver-roles"),
            data={"roles": ["ADMIN"]},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        self._auth(self.curator)
        response = self.client.post(
            reverse("contributor-case-review", args=[submission.id]),
            data={"action": "approve", "note": "Trying to approve"},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

        self._auth(self.admin)
        response = self.client.post(
            reverse("contributor-case-review", args=[submission.id]),
            data={"action": "reject", "note": "Admin review"},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        submission.refresh_from_db()
        self.assertEqual(submission.state, ContributorCaseSubmission.ReviewState.REJECTED)

    def test_submission_creates_new_disease_and_location(self):
        payload = {
            **self.base_payload,
            "city": "Newtown",
            "disease": "Mystery Virus",
            "location": {"city": "Newtown", "province": "New Province"},
        }
        self._auth(self.contributor)
        response = self.client.post(
            reverse("contributor-case-list"),
            data=payload,
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

        submission = ContributorCaseSubmission.objects.get(id=response.data["id"])
        disease = Disease.objects.get(name="Mystery Virus")
        self.assertEqual(submission.disease_id, disease.id)

        location = Location.objects.get(
            city__iexact="Newtown", province__iexact="New Province"
        )
        self.assertEqual(submission.location_id, location.id)

class ContributorCaseModelMethodTests(TestCase):
    def setUp(self):
        self.role = Role.objects.create(name="CONTRIBUTOR")
        self.user = User.objects.create(
            name="Contributor",
            email="test@example.com",
            password="pwd",
            role="CONTRIBUTOR",
        )
        self.disease = Disease.objects.create(name="Flu", level_of_alertness=1)
        self.location = Location.objects.create(
            city="Jakarta",
            province="DKI Jakarta",
            latitude=1.0,
            longitude=106.0,
        )

        self.obj = ContributorCaseSubmission.objects.create(
            gender="male",
            age=20,
            city="Jakarta",
            status="biasa",
            severity="insiden",
            disease=self.disease,
            location=self.location,
            created_by=self.user,
        )

    # ---------------------------------------------------------
    # serialize_news_payload()
    # ---------------------------------------------------------
    def test_serialize_skips_none(self):
        out = self.obj.serialize_news_payload({"a": None})
        self.assertEqual(out, {})

    def test_serialize_datetime_aware(self):
        aware = timezone.now()
        out = self.obj.serialize_news_payload({"dt": aware})
        self.assertTrue(out["dt"].endswith("Z"))

    def test_serialize_datetime_naive(self):
        naive = datetime(2024, 1, 1, 8, 30, 0)
        out = self.obj.serialize_news_payload({"dt": naive})
        self.assertEqual(out["dt"], naive.isoformat())

    def test_serialize_non_datetime(self):
        out = self.obj.serialize_news_payload({"title": "Hello"})
        self.assertEqual(out["title"], "Hello")

    # ---------------------------------------------------------
    # news_payload_for_case()
    # ---------------------------------------------------------
    def test_news_payload_empty(self):
        self.obj.set_news_payload({})
        self.assertEqual(self.obj.news_payload_for_case(), {})

    def test_news_payload_skips_none_and_empty(self):
        self.obj.set_news_payload({"x": None, "y": ""})
        self.assertEqual(self.obj.news_payload_for_case(), {})

    def test_news_payload_parses_date(self):
        self.obj.set_news_payload({"date_published": "2024-02-01T10:00:00"})
        out = self.obj.news_payload_for_case()
        self.assertIsInstance(out.get("date_published"), datetime)

    def test_news_payload_non_date_key(self):
        self.obj.set_news_payload({"title": "Breaking News"})
        out = self.obj.news_payload_for_case()
        self.assertEqual(out["title"], "Breaking News")

    # ---------------------------------------------------------
    # _parse_date()
    # ---------------------------------------------------------
    def test_parse_date_none(self):
        self.assertIsNone(self.obj._parse_date(None))

    def test_parse_date_datetime_aware(self):
        aware = timezone.now()
        parsed = self.obj._parse_date(aware)
        self.assertEqual(parsed, aware)

    def test_parse_date_datetime_naive(self):
        naive = datetime(2024, 1, 1, 10, 0, 0)
        parsed = self.obj._parse_date(naive)
        self.assertTrue(timezone.is_aware(parsed))

    def test_parse_date_valid_string(self):
        parsed = self.obj._parse_date("2024-02-02T12:00:00")
        self.assertTrue(timezone.is_aware(parsed))

    def test_parse_date_invalid_string_returns_now(self):
        before = timezone.now()
        parsed = self.obj._parse_date("not-a-date")
        after = timezone.now()
        self.assertTrue(before <= parsed <= after)

class ContributorApprovalRoleLogicTests(TestCase):
    def setUp(self):
        self.role_contrib = Role.objects.create(name="CONTRIBUTOR")
        self.role_curator = Role.objects.create(name="CURATOR")
        self.role_admin = Role.objects.create(name="ADMIN")

        self.user_no_role = User.objects.create(
            name="NoRole",
            email="norole@example.com",
            password="pwd",
            role=""
        )
        self.user_curator = User.objects.create(
            name="Curator",
            email="curator@example.com",
            password="pwd",
            role="CURATOR"
        )
        self.user_admin = User.objects.create(
            name="Admin",
            email="admin@example.com",
            password="pwd",
            role="ADMIN"
        )

    # ---------------------------------------------------------------
    # __str__ of ContributorCaseSubmission (red highlight)
    # ---------------------------------------------------------------
    def test_case_submission_str(self):
        disease = Disease.objects.create(name="Malaria", level_of_alertness=1)
        loc = Location.objects.create(
            city="Depok",
            province="Jawa Barat",
            latitude=0,
            longitude=0
        )
        submission = ContributorCaseSubmission.objects.create(
            gender="M",
            age=22,
            city="Depok",
            status="biasa",
            severity="insiden",
            disease=disease,
            location=loc,
            created_by=self.user_admin
        )
        self.assertEqual(
            str(submission),
            "Malaria - Depok (PENDING)"
        )

    # ---------------------------------------------------------------
    # __str__ of ContributorApprovalRole (red highlight)
    # ---------------------------------------------------------------
    def test_approval_role_str(self):
        ar = ContributorApprovalRole.objects.create(role=self.role_curator)
        self.assertEqual(str(ar), "CURATOR approver")

    # ---------------------------------------------------------------
    # allowed_role_names() - both branches (yellow + red)
    # ---------------------------------------------------------------
    def test_allowed_role_names_when_records_exist(self):
        ContributorApprovalRole.objects.create(role=self.role_curator)
        ContributorApprovalRole.objects.create(role=self.role_admin)

        allowed = ContributorApprovalRole.allowed_role_names()
        self.assertEqual(allowed, {"CURATOR", "ADMIN"})

    def test_allowed_role_names_when_no_records(self):
        ContributorApprovalRole.objects.all().delete()

        allowed = ContributorApprovalRole.allowed_role_names()
        # DEFAULT_ROLE_NAMES = ("CURATOR", "ADMIN")
        self.assertEqual(allowed, {"CURATOR", "ADMIN"})

    # ---------------------------------------------------------------
    # user_is_approver() - both branches
    # ---------------------------------------------------------------
    def test_user_is_approver_when_no_role(self):
        self.assertFalse(ContributorApprovalRole.user_is_approver(self.user_no_role))

    def test_user_is_approver_when_role_not_allowed(self):
        # contributor role is not by default allowed
        self.assertFalse(ContributorApprovalRole.user_is_approver(
            User.objects.create(
                name="X",
                email="x@example.com",
                password="pwd",
                role="CONTRIBUTOR"
            )
        ))

    def test_user_is_approver_when_role_allowed(self):
        ContributorApprovalRole.objects.create(role=self.role_curator)
        self.assertTrue(ContributorApprovalRole.user_is_approver(self.user_curator))

    # ---------------------------------------------------------------
    # set_allowed_roles() - tests entry + deletion logic (yellow zone)
    # ---------------------------------------------------------------
    def test_set_allowed_roles_creates_and_removes_roles(self):
        # Initially only CURATOR is stored
        ContributorApprovalRole.objects.create(role=self.role_curator)

        # Set allowed roles to only ADMIN
        ContributorApprovalRole.set_allowed_roles([self.role_admin])

        # Only ADMIN should remain
        result = list(
            ContributorApprovalRole.objects.values_list("role__name", flat=True)
        )
        self.assertEqual(result, ["ADMIN"])

    def test_set_allowed_roles_adds_missing_roles(self):
        ContributorApprovalRole.objects.all().delete()

        ContributorApprovalRole.set_allowed_roles([self.role_curator, self.role_admin])

        names = set(
            ContributorApprovalRole.objects.values_list("role__name", flat=True)
        )
        self.assertEqual(names, {"CURATOR", "ADMIN"})

    def test_set_allowed_roles_only_creates_missing(self):
        """
        Ensure that set_allowed_roles() only creates ContributorApprovalRole
        entries for roles NOT already present in 'existing'.
        """

        # Existing record: CURATOR is already in DB
        ContributorApprovalRole.objects.create(role=self.role_curator)

        # Now call set_allowed_roles with 2 roles:
        # - CURATOR  (already exists -> SHOULD NOT create)
        # - ADMIN    (missing -> SHOULD create)
        ContributorApprovalRole.set_allowed_roles([self.role_curator, self.role_admin])

        # Fetch results
        saved_roles = list(
            ContributorApprovalRole.objects.values_list("role__name", flat=True)
        )

        # Expected:
        # CURATOR stays (not recreated)
        # ADMIN is newly created
        self.assertCountEqual(saved_roles, ["CURATOR", "ADMIN"])

from django.test import TestCase
from django.utils import timezone
from rest_framework import serializers

from contributor_feature.serializers import (
    ContributorCaseReadSerializer,
    ContributorCaseWriteSerializer,
    ContributorCaseReviewSerializer,
    ContributorApprovalRoleUpdateSerializer,
)
from contributor_feature.models import ContributorCaseSubmission
from pt_backend.models import Disease, Location, Role, User
from curator_feature.serializers import LocationByNameSerializer, NewsInlineWriteSerializer

from datetime import datetime


class ContributorSerializerLogicTests(TestCase):
    def setUp(self):
        self.role1 = Role.objects.create(name="CURATOR")
        self.role2 = Role.objects.create(name="ADMIN")

        self.user = User.objects.create(
            name="tester",
            email="t@example.com",
            password="pwd",
            role="CURATOR",
        )

        Location.objects.create(
            city="Jakarta",
            province="DKI",
            latitude=0.0,
            longitude=0.0,
        )

        self.write_base = {
            "gender": "M",
            "age": 22,
            "city": "Jakarta",
            "status": "biasa",
            "severity": "insiden",
        }

    # ---------------------------------------------------------
    # _resolve_disease_id Tests
    # ---------------------------------------------------------
    def test_resolve_disease_missing(self):
        ser = ContributorCaseWriteSerializer()
        with self.assertRaises(serializers.ValidationError):
            ser._resolve_disease_id(None)

    def test_resolve_disease_blank(self):
        ser = ContributorCaseWriteSerializer()
        with self.assertRaises(serializers.ValidationError):
            ser._resolve_disease_id("   ")

    def test_resolve_disease_existing(self):
        d = Disease.objects.create(name="Flu", level_of_alertness=1)
        ser = ContributorCaseWriteSerializer()
        result = ser._resolve_disease_id("flu")
        self.assertEqual(result, d.id)

    def test_resolve_disease_create_new(self):
        ser = ContributorCaseWriteSerializer()
        result = ser._resolve_disease_id("NewVirus")
        self.assertTrue(Disease.objects.filter(name="NewVirus").exists())

    # ---------------------------------------------------------
    # _resolve_location tests
    # ---------------------------------------------------------
    def test_resolve_location_missing_payload(self):
        ser = ContributorCaseWriteSerializer()
        with self.assertRaises(serializers.ValidationError):
            ser._resolve_location(None)

    def test_resolve_location_valid(self):
        ser = ContributorCaseWriteSerializer()
        data = {"city": "Jakarta"}
        loc = ser._resolve_location(data)
        self.assertIsInstance(loc, Location)

    # ---------------------------------------------------------
    # _normalize_news_payload tests
    # ---------------------------------------------------------
    def test_normalize_news_missing(self):
        ser = ContributorCaseWriteSerializer()
        with self.assertRaises(serializers.ValidationError):
            ser._normalize_news_payload(None)

    def test_normalize_news_valid(self):
        ser = ContributorCaseWriteSerializer()
        data = {
            "portal": "Portal",
            "title": "News",
            "type": "Article",
            "content": "Body",
            "url": "https://example.com",
            "author": "John",
            "date_published": timezone.now(),
            "img_url": "https://example.com/img.jpg",
        }
        result = ser._normalize_news_payload(data)
        self.assertIn("title", result)

    # ---------------------------------------------------------
    # update() tests
    # ---------------------------------------------------------
    def test_update_disease_location_news(self):
        old_disease = Disease.objects.create(name="OldX", level_of_alertness=1)
        loc = Location.objects.get(city="Jakarta")

        instance = ContributorCaseSubmission.objects.create(
            gender="M",
            age=22,
            city="Jakarta",
            status="biasa",
            severity="insiden",
            disease=old_disease,
            location=loc,
            created_by=self.user,
        )

        new_loc_payload = {"city": "Jakarta"}  # valid LocationByNameSerializer input
        new_news_payload = {
            "portal": "Portal",
            "title": "Updated",
            "type": "Article",
            "content": "Content",
            "url": "https://news.com",
            "author": "A",
            "date_published": timezone.now(),
            "img_url": "https://img.com",
        }

        ser = ContributorCaseWriteSerializer()
        validated = {
            "disease": "NewDisease",
            "location": new_loc_payload,
            "news": new_news_payload,
            "city": "Depok",
        }

        updated = ser.update(instance, validated)

        # disease updated
        self.assertEqual(updated.disease.name, "NewDisease")
        # location updated
        self.assertEqual(updated.location.city.lower(), "jakarta")
        # news updated
        self.assertIn("title", updated.get_news_payload())
        # normal field updated
        self.assertEqual(updated.city, "Depok")

    # ---------------------------------------------------------
    # ContributorCaseReviewSerializer.validate
    # ---------------------------------------------------------
    def test_review_reject_without_note(self):
        ser = ContributorCaseReviewSerializer(data={"action": "reject", "note": ""})
        with self.assertRaises(serializers.ValidationError):
            ser.is_valid(raise_exception=True)

    def test_review_approve_without_note(self):
        ser = ContributorCaseReviewSerializer(data={"action": "approve", "note": ""})
        self.assertTrue(ser.is_valid())

    def test_review_reject_with_note(self):
        ser = ContributorCaseReviewSerializer(data={"action": "reject", "note": "ok"})
        self.assertTrue(ser.is_valid())

    # ---------------------------------------------------------
    # ContributorApprovalRoleUpdateSerializer.validate_roles
    # ---------------------------------------------------------
    def test_validate_roles_blank(self):
        ser = ContributorApprovalRoleUpdateSerializer()
        with self.assertRaises(serializers.ValidationError):
            ser.validate_roles([" "])

    def test_validate_roles_duplicate(self):
        ser = ContributorApprovalRoleUpdateSerializer()
        Role.objects.create(name="Tester")
        result = ser.validate_roles(["Tester", "tester"])
        self.assertEqual(result, ["Tester"])

    def test_validate_roles_not_found(self):
        ser = ContributorApprovalRoleUpdateSerializer()
        with self.assertRaises(serializers.ValidationError):
            ser.validate_roles(["DoesNotExist"])

    def test_validate_roles_success(self):
        ser = ContributorApprovalRoleUpdateSerializer()
        Role.objects.create(name="A")
        Role.objects.create(name="B")
        result = ser.validate_roles(["A", "B"])
        self.assertEqual(set(result), {"A", "B"})

    def test_update_only_disease(self):
        instance = ContributorCaseSubmission.objects.create(
            gender="M", age=20, city="A", status="biasa",
            severity="insiden", disease=Disease.objects.create(name="Old", level_of_alertness=1), 
            location=Location.objects.first(), created_by=self.user
        )

        ser = ContributorCaseWriteSerializer()
        updated = ser.update(instance, {"disease": "NewX"})

        self.assertEqual(updated.disease.name, "NewX")


    def test_update_only_location(self):
        old = Location.objects.get(city="Jakarta")
        instance = ContributorCaseSubmission.objects.create(
            gender="M", age=20, city="A", status="biasa",
            severity="insiden", disease=Disease.objects.create(name="Old", level_of_alertness=1),
            location=old, created_by=self.user
        )

        ser = ContributorCaseWriteSerializer()
        updated = ser.update(instance, {"location": {"city": "Jakarta"}})

        self.assertEqual(updated.location.city.lower(), "jakarta")


    def test_update_only_news(self):
        instance = ContributorCaseSubmission.objects.create(
            gender="M", age=20, city="A", status="biasa",
            severity="insiden", disease=Disease.objects.create(name="Old", level_of_alertness=1),
            location=Location.objects.first(), created_by=self.user
        )

        news = {
            "portal": "P",
            "title": "T",
            "type": "Article",
            "content": "C",
            "url": "https://x.com",
            "author": "A",
            "date_published": timezone.now(),
            "img_url": "https://img.com"
        }

        ser = ContributorCaseWriteSerializer()
        updated = ser.update(instance, {"news": news})

        self.assertIn("title", updated.get_news_payload())

    def test_validate_roles_cleaned_empty_final_branch(self):
        """
        Directly call the validator with an empty list to cover:
        if not cleaned: raise ValidationError("Provide at least one valid role.")
        """
        ser = ContributorApprovalRoleUpdateSerializer()
        with self.assertRaises(serializers.ValidationError):
            ser.validate_roles([])

class ContributorViewLogicTests(TestCase):
    def setUp(self):
        self.client = APIClient()

        self.role_contributor = Role.objects.create(name="CONTRIBUTOR")
        self.role_curator = Role.objects.create(name="CURATOR")
        self.role_admin = Role.objects.create(name="ADMIN")
        ContributorApprovalRole.objects.create(role=self.role_curator)

        self.contributor = User.objects.create(
            name="Contributor",
            email="contrib@example.com",
            password="pwd",
            role="CONTRIBUTOR",
        )
        self.curator = User.objects.create(
            name="Curator",
            email="curator@example.com",
            password="pwd",
            role="CURATOR",
        )
        self.admin = User.objects.create(
            name="Admin",
            email="admin@example.com",
            password="pwd",
            role="ADMIN",
        )

        self.disease = Disease.objects.create(name="Flu", level_of_alertness=1)
        self.location = Location.objects.create(
            city="Jakarta",
            province="DKI",
            latitude=1.0,
            longitude=100.0,
        )

    def _auth(self, user):
        self.client.force_authenticate(user=user)

    # ----------------------------------------------------------------------
    # get_serializer_class()
    # ----------------------------------------------------------------------

    def test_list_uses_read_serializer(self):
        self._auth(self.contributor)
        url = reverse("contributor-case-list")
        request = self.client.get(url)
        view = ContributorCaseListCreateView()
        view.request = request.wsgi_request
        self.assertEqual(view.get_serializer_class(), ContributorCaseReadSerializer)

    def test_create_uses_write_serializer(self):
        self._auth(self.contributor)
        url = reverse("contributor-case-list")
        request = self.client.post(url, {}, format="json")
        view = ContributorCaseListCreateView()
        view.request = request.wsgi_request
        self.assertEqual(view.get_serializer_class(), ContributorCaseWriteSerializer)

    # ----------------------------------------------------------------------
    # get_queryset()
    # ----------------------------------------------------------------------

    def test_queryset_filters_created_by_for_non_approver(self):
        # Created by curator (not visible to contributor)
        ContributorCaseSubmission.objects.create(
            gender="m", age=1, city="A", status="x", severity="x",
            disease=self.disease, location=self.location,
            created_by=self.curator, updated_by=self.curator
        )
        # Created by contributor (visible)
        visible = ContributorCaseSubmission.objects.create(
            gender="m", age=2, city="B", status="y", severity="y",
            disease=self.disease, location=self.location,
            created_by=self.contributor, updated_by=self.contributor
        )

        self._auth(self.contributor)
        url = reverse("contributor-case-list")
        response = self.client.get(url)

        ids = [obj["id"] for obj in response.data]
        self.assertEqual(ids, [str(visible.id)])


    def test_queryset_state_filter(self):
        sub = ContributorCaseSubmission.objects.create(
            gender="m", age=1, city="A", status="x", severity="x",
            disease=self.disease, location=self.location,
            created_by=self.contributor, updated_by=self.contributor,
            state="PENDING"
        )

        self._auth(self.curator)
        url = reverse("contributor-case-list") + "?state=pending"
        response = self.client.get(url)

        ids = [obj["id"] for obj in response.data]
        self.assertIn(str(sub.id), ids)


    # ----------------------------------------------------------------------
    # get_object() access control
    # ----------------------------------------------------------------------

    def test_get_object_denied_for_non_author_non_approver(self):
        other = User.objects.create(
            name="X", email="x@x.com", password="pwd", role="CONTRIBUTOR"
        )

        sub = ContributorCaseSubmission.objects.create(
            gender="m", age=1, city="A", status="x", severity="x",
            disease=self.disease, location=self.location,
            created_by=self.contributor, updated_by=self.contributor
        )

        self._auth(other)
        url = reverse("contributor-case-detail", args=[sub.id])
        response = self.client.get(url)
        self.assertEqual(response.status_code, 403)

    # ----------------------------------------------------------------------
    # perform_update()
    # ----------------------------------------------------------------------

    def test_update_rejected_for_non_approver_on_processed(self):
        sub = ContributorCaseSubmission.objects.create(
            gender="m", age=1, city="A", status="x", severity="x",
            disease=self.disease, location=self.location,
            created_by=self.contributor, updated_by=self.contributor,
            state="APPROVED"
        )

        self._auth(self.contributor)
        url = reverse("contributor-case-detail", args=[sub.id])
        response = self.client.patch(url, {"city": "New"}, format="json")
        self.assertEqual(response.status_code, 403)

    def test_update_rejected_for_non_author_non_approver(self):
        sub = ContributorCaseSubmission.objects.create(
            gender="m", age=1, city="A", status="x", severity="x",
            disease=self.disease, location=self.location,
            created_by=self.contributor, updated_by=self.contributor,
            state="PENDING"
        )

        self._auth(self.admin)  # admin is NOT approver unless configured
        url = reverse("contributor-case-detail", args=[sub.id])
        response = self.client.patch(url, {"city": "X"}, format="json")
        self.assertEqual(response.status_code, 403)

    def test_update_success_by_author(self):
        sub = ContributorCaseSubmission.objects.create(
            gender="m", age=1, city="A", status="x", severity="x",
            disease=self.disease, location=self.location,
            created_by=self.contributor, updated_by=self.contributor,
            state="PENDING"
        )

        self._auth(self.contributor)
        url = reverse("contributor-case-detail", args=[sub.id])
        response = self.client.patch(url, {"city": "NewCity"}, format="json")

        self.assertEqual(response.status_code, 200)
        sub.refresh_from_db()
        self.assertEqual(sub.city, "NewCity")

    # ----------------------------------------------------------------------
    # perform_destroy()
    # ----------------------------------------------------------------------

    def test_delete_denied_non_author(self):
        sub = ContributorCaseSubmission.objects.create(
            gender="m", age=1, city="A", status="x", severity="x",
            disease=self.disease, location=self.location,
            created_by=self.contributor, updated_by=self.contributor,
            state="PENDING"
        )

        self._auth(self.admin)
        url = reverse("contributor-case-detail", args=[sub.id])
        response = self.client.delete(url)
        self.assertEqual(response.status_code, 403)

    def test_delete_denied_if_not_pending(self):
        sub = ContributorCaseSubmission.objects.create(
            gender="m", age=1, city="A", status="x", severity="x",
            disease=self.disease, location=self.location,
            created_by=self.contributor, updated_by=self.contributor,
            state="APPROVED"
        )

        self._auth(self.contributor)
        url = reverse("contributor-case-detail", args=[sub.id])
        response = self.client.delete(url)
        self.assertEqual(response.status_code, 403)

    def test_delete_success(self):
        sub = ContributorCaseSubmission.objects.create(
            gender="m", age=1, city="A", status="x", severity="x",
            disease=self.disease, location=self.location,
            created_by=self.contributor, updated_by=self.contributor,
            state="PENDING"
        )

        self._auth(self.contributor)
        url = reverse("contributor-case-detail", args=[sub.id])
        response = self.client.delete(url)
        self.assertEqual(response.status_code, 204)

    # ----------------------------------------------------------------------
    # ReviewView — pending check
    # ----------------------------------------------------------------------

    def test_review_denied_if_not_pending(self):
        sub = ContributorCaseSubmission.objects.create(
            gender="m", age=1, city="A", status="x", severity="x",
            disease=self.disease, location=self.location,
            created_by=self.contributor, updated_by=self.contributor,
            state="APPROVED"
        )

        self._auth(self.curator)
        url = reverse("contributor-case-review", args=[sub.id])
        response = self.client.post(url, {"action": "approve"}, format="json")

        self.assertEqual(response.status_code, 400)
        self.assertIn("already been reviewed", response.data["detail"])

    # ----------------------------------------------------------------------
    # Approve_submission() — news or no news
    # ----------------------------------------------------------------------

    def test_approve_without_news_does_not_create_news(self):
        sub = ContributorCaseSubmission.objects.create(
            gender="m", age=1, city="A", status="x", severity="x",
            disease=self.disease, location=self.location,
            created_by=self.contributor, updated_by=self.contributor,
            news_payload={},
            state="PENDING"
        )

        self._auth(self.curator)
        url = reverse("contributor-case-review", args=[sub.id])
        response = self.client.post(url, {"action": "approve", "note": "ok"}, format="json")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(News.objects.count(), 0)

    def test_approve_with_news_creates_news(self):
        payload = {
            "portal": "X",
            "title": "Y",
            "type": "Z",
            "content": "C",
            "url": "http://x.com",
            "author": "A",
            "date_published": timezone.now().isoformat(),
            "img_url": "http://x.com/i.jpg"
        }

        sub = ContributorCaseSubmission.objects.create(
            gender="m", age=1, city="A", status="x", severity="x",
            disease=self.disease, location=self.location,
            created_by=self.contributor, updated_by=self.contributor,
            news_payload=payload,
            state="PENDING"
        )

        self._auth(self.curator)
        url = reverse("contributor-case-review", args=[sub.id])
        response = self.client.post(url, {"action": "approve", "note": "ok"}, format="json")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(News.objects.count(), 1)

    # ----------------------------------------------------------------------
    # Approver roles GET
    # ----------------------------------------------------------------------

    def test_get_approver_roles(self):
        self._auth(self.admin)
        url = reverse("contributor-approver-roles")
        response = self.client.get(url)

        self.assertEqual(response.status_code, 200)
        self.assertIn("roles", response.data)
        



