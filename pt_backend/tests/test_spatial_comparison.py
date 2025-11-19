import os
import uuid
from datetime import timedelta
from unittest.mock import patch

from django.test import TestCase
from django.urls import reverse
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APIClient

from pt_backend.filter.service import CaseFilterValidationError
from pt_backend.models import Case, Disease, Location, News


class SpatialComparisonViewTest(TestCase):
    def setUp(self):
        os.environ["SECRET_API_KEY"] = "test-api-key"
        self.client = APIClient()
        self.client.credentials(HTTP_X_API_KEY="test-api-key")

        self.disease = Disease.objects.create(name="Flu", level_of_alertness=1)
        self.location_jakarta = Location.objects.create(
            latitude=-6.2,
            longitude=106.8,
            city="Jakarta",
            province="DKI Jakarta",
        )
        self.location_bandung = Location.objects.create(
            latitude=-6.9,
            longitude=107.6,
            city="Bandung",
            province="Jawa Barat",
        )
        self.case_jakarta = Case.objects.create(
            id=uuid.uuid4(),
            gender="Male",
            age=30,
            city="Jakarta",
            status="minimal",
            severity="insiden",
            disease=self.disease,
            location=self.location_jakarta,
        )
        self.case_bandung = Case.objects.create(
            id=uuid.uuid4(),
            gender="Female",
            age=25,
            city="Bandung",
            status="biasa",
            severity="mortalitas",
            disease=self.disease,
            location=self.location_bandung,
        )

    def tearDown(self):
        os.environ.pop("SECRET_API_KEY", None)

    def test_spatial_comparison_returns_grouped_locations(self):
        url = reverse("spatial-comparisons")
        payload = {
            "regions": [
                "DKI Jakarta",
                {
                    "label": "Jawa Barat Only",
                    "filters": {"locations": {"provinces": ["Jawa Barat"]}},
                },
            ]
        }

        response = self.client.post(url, data=payload, format="json")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        comparisons = response.data["comparisons"]
        self.assertEqual(len(comparisons), 2)
        self.assertEqual(comparisons[0]["label"], "DKI Jakarta")
        self.assertEqual(comparisons[0]["count"], 1)
        self.assertEqual(
            {c["city"] for c in comparisons[0]["locations"]},
            {"Jakarta"},
        )
        self.assertEqual(comparisons[1]["label"], "Jawa Barat Only")
        self.assertEqual(comparisons[1]["count"], 1)
        self.assertEqual(
            {c["city"] for c in comparisons[1]["locations"]},
            {"Bandung"},
        )

    def test_spatial_comparison_builds_filters_from_province_and_time_params(self):
        News.objects.create(
            id=uuid.uuid4(),
            portal="Portal",
            title="T",
            type="A",
            content="c",
            url="https://example.com/a",
            author="author",
            date_published=timezone.now(),
            case=self.case_jakarta,
            img_url="https://example.com/i.png",
        )
        url = reverse("spatial-comparisons")
        payload = {
            "regions": [
                {
                    "province": "DKI Jakarta",
                    "start_date": (timezone.now() - timedelta(days=1)).isoformat(),
                    "end_date": (timezone.now() + timedelta(days=1)).isoformat(),
                }
            ]
        }

        response = self.client.post(url, data=payload, format="json")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        comparison = response.data["comparisons"][0]
        self.assertEqual(comparison["label"], "DKI Jakarta")
        self.assertIn("locations", comparison["filters"])
        self.assertIn("start_date", comparison["filters"])
        self.assertEqual(comparison["count"], 1)

    def test_spatial_comparison_builds_filters_from_city(self):
        url = reverse("spatial-comparisons")
        response = self.client.post(
            url,
            data={"regions": [{"city": "Bandung"}]},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        comparison = response.data["comparisons"][0]
        self.assertEqual(comparison["label"], "Bandung")
        self.assertEqual(comparison["count"], 1)
        self.assertIn("locations", comparison["filters"])

    def test_spatial_comparison_requires_regions_list(self):
        url = reverse("spatial-comparisons")
        response_missing = self.client.post(url, data={}, format="json")
        response_empty = self.client.post(url, data={"regions": []}, format="json")
        response_wrong_type = self.client.post(
            url, data={"regions": "Jakarta"}, format="json"
        )

        self.assertEqual(response_missing.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(response_empty.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(response_wrong_type.status_code, status.HTTP_400_BAD_REQUEST)

    def test_spatial_comparison_rejects_invalid_region_entry(self):
        url = reverse("spatial-comparisons")
        response = self.client.post(
            url, data={"regions": [123]}, format="json"
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(response.data["region_index"], 0)

    def test_spatial_comparison_rejects_invalid_filter_mapping(self):
        url = reverse("spatial-comparisons")
        response = self.client.post(
            url,
            data={"regions": [{"label": "Bad", "filters": "oops"}]},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(response.data["region_index"], 0)

    def test_spatial_comparison_handles_filter_error(self):
        url = reverse("spatial-comparisons")
        error = CaseFilterValidationError("invalid", fields={"start_date": ["bad"]})
        with patch(
            "pt_backend.views.CaseFilterService.filter_cases",
            side_effect=error,
        ):
            response = self.client.post(
                url, data={"regions": ["DKI Jakarta"]}, format="json"
            )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(response.data["error"]["fields"]["start_date"], ["bad"])
        self.assertEqual(response.data["error"]["region_index"], 0)

    def test_spatial_comparison_handles_time_filter_error(self):
        url = reverse("spatial-comparisons")
        error = CaseFilterValidationError("time-wrong", fields={"start_date": ["bad"]})
        with patch(
            "pt_backend.views.CaseFilterService.parse_time_params",
            side_effect=error,
        ):
            response = self.client.post(
                url, data={"regions": [{"label": "Jakarta"}]}, format="json"
            )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(response.data["error"]["fields"]["start_date"], ["bad"])
        self.assertEqual(response.data["error"]["region_index"], 0)
