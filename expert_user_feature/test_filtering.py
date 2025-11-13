import os

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "pantau_tular.test_settings")

import django

django.setup()

from datetime import date, datetime

from django.test import TestCase
from django.utils import timezone

from expert_user_feature.filtering import ExpertCaseFilterSet
from pt_backend.models import Case, Disease, Location, News


class ExpertCaseFilterSetTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.disease_dbd = Disease.objects.create(name="DBD", level_of_alertness=3)
        cls.disease_hb = Disease.objects.create(name="Hepatitis B", level_of_alertness=2)
        cls.disease_ckg = Disease.objects.create(name="Chikungunya", level_of_alertness=1)

        cls.loc_jakarta = Location.objects.create(city="Jakarta", province="DKI Jakarta")
        cls.loc_bandung = Location.objects.create(city="Bandung", province="Jawa Barat")
        cls.loc_surabaya = Location.objects.create(city="Surabaya", province="Jawa Timur")

        cls.case_jakarta = Case.objects.create(
            disease=cls.disease_dbd,
            location=cls.loc_jakarta,
            gender="L",
            age=30,
            city="Jakarta",
            status="bahaya",
            severity="insiden",
        )
        cls.case_bandung = Case.objects.create(
            disease=cls.disease_hb,
            location=cls.loc_bandung,
            gender="P",
            age=28,
            city="Bandung",
            status="biasa",
            severity="hospitalisasi",
        )
        cls.case_surabaya = Case.objects.create(
            disease=cls.disease_ckg,
            location=cls.loc_surabaya,
            gender="L",
            age=33,
            city="Surabaya",
            status="minimal",
            severity="insiden",
        )

        cls._attach_news(cls.case_jakarta, "Portal-A", cls._aware(2024, 1, 10))
        cls._attach_news(cls.case_bandung, "Portal-B", cls._aware(2024, 2, 5))
        cls._attach_news(cls.case_surabaya, "Portal-C", cls._aware(2024, 3, 15))
        cls._attach_news(cls.case_surabaya, "Portal-D", cls._aware(2024, 3, 16))

    def setUp(self):
        self.filter_set = ExpertCaseFilterSet()

    @staticmethod
    def _aware(year: int, month: int, day: int):
        tz = timezone.get_current_timezone()
        return timezone.make_aware(datetime(year, month, day), timezone=tz)

    @staticmethod
    def _attach_news(case: Case, portal: str, published_at):
        News.objects.create(
            case=case,
            portal=portal,
            title=f"{portal} headline",
            type="artikel",
            content="content",
            url=f"https://{portal.lower()}.example.com",
            author="Reporter",
            date_published=published_at,
            img_url="",
        )

    def test_filters_disease_and_city(self):
        qs = self.filter_set.apply(
            {"diseases": ["DBD"], "locations": {"cities": ["Jakarta"]}},
            Case.objects.all(),
        )
        self.assertEqual(list(qs), [self.case_jakarta])

    def test_filters_by_date_range(self):
        qs = self.filter_set.apply(
            {"start_date": date(2024, 2, 1), "end_date": date(2024, 3, 1)},
            Case.objects.all(),
        )
        self.assertEqual(list(qs), [self.case_bandung])

    def test_filters_with_alertness_and_province(self):
        qs = self.filter_set.apply(
            {
                "level_of_alertness": 3,
                "locations": {"provinces": ["DKI Jakarta"]},
                "portals": ["Portal-A", "Portal-Z"],
            },
            Case.objects.all(),
        )
        self.assertEqual(list(qs), [self.case_jakarta])

    def test_portal_filter_returns_distinct_cases(self):
        qs = self.filter_set.apply(
            {"portals": ["Portal-C", "Portal-D"]},
            Case.objects.all(),
        )
        self.assertEqual(qs.count(), 1)
        self.assertEqual(qs.first(), self.case_surabaya)
