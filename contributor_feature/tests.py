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

