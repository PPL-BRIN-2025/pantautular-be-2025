from django.urls import reverse
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APIClient

from django.test import TestCase

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
