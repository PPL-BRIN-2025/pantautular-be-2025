from __future__ import annotations

import uuid

from django.contrib.auth.hashers import make_password
from django.core.management.base import BaseCommand
from django.utils import timezone

from pt_backend.models import Case, Disease, Location, News, User


SAMPLE_NEWS = [
    {
        "portal": "Kompas",
        "title": "Kompas: Vaksinasi Flu Burung Dimulai",
        "type": "Kurasi",
        "content": "Program vaksinasi nasional dimulai untuk mencegah potensi wabah flu burung.",
        "url": "https://news.example.com/kompas/vaksinasi-flu-burung",
        "author": "Redaksi Kompas",
        "date_published": timezone.now() - timezone.timedelta(days=2),
        "img_url": "https://cdn.pantautular.com/news/kompas-flu-burung.jpg",
    },
    {
        "portal": "Detik",
        "title": "Detik: Update Kasus DBD di Jakarta",
        "type": "Nasional",
        "content": "Kasus demam berdarah menunjukkan tren penurunan setelah kampanye fogging.",
        "url": "https://news.example.com/detik/update-dbd",
        "author": "Detik Health",
        "date_published": timezone.now() - timezone.timedelta(days=5),
        "img_url": "",
    },
    {
        "portal": "Antara",
        "title": "Antara: Kesiapsiagaan Zoonosis Nasional",
        "type": "Kurasi",
        "content": "Pemerintah mengumumkan rencana kesiapsiagaan nasional terhadap zoonosis.",
        "url": "https://news.example.com/antara/zoonosis-plan",
        "author": "ANTARA",
        "date_published": timezone.now() - timezone.timedelta(days=10),
        "img_url": "",
    },
]

SEED_USER_EMAIL = "news.seed@pantautular.local"
SEED_CASE_ID = uuid.UUID("00000000-0000-0000-0000-00000000feed")


class Command(BaseCommand):
    help = "Seeds a small curated set of news articles for local testing."

    def handle(self, *args, **options):
        case = self._ensure_case()
        created = 0

        for payload in SAMPLE_NEWS:
            defaults = {**payload, "case": case}
            article, was_created = News.objects.get_or_create(
                url=payload["url"],
                defaults=defaults,
            )
            if was_created:
                created += 1

        self.stdout.write(
            self.style.SUCCESS(f"Seeded {created} Supabase-backed news article(s).")
        )

    def _ensure_case(self) -> Case:
        user, _ = User.objects.get_or_create(
            email=SEED_USER_EMAIL,
            defaults={
                "name": "News Seeder",
                "password": make_password("news-seed"),
                "role": "CURATOR",
            },
        )

        location = (
            Location.objects.filter(city="Jakarta", province="DKI Jakarta").first()
            or Location.objects.create(
                city="Jakarta",
                province="DKI Jakarta",
                latitude=-6.2088,
                longitude=106.8456,
            )
        )

        disease, _ = Disease.objects.get_or_create(
            name="Flu Burung",
            defaults={"level_of_alertness": 1},
        )

        case, _ = Case.objects.get_or_create(
            id=SEED_CASE_ID,
            defaults={
                "gender": "unknown",
                "age": 30,
                "city": "Jakarta",
                "status": Case.STATUS_CHOICES[0][0],
                "severity": Case.SEVERITY_CHOICES[0][0],
                "disease": disease,
                "location": location,
                "created_by": user,
            },
        )
        return case
