import os

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "pantau_tular.test_settings")

import django
django.setup()

from django.test import TestCase
from rest_framework import serializers as drf_serializers

from curator_feature.serializers import LocationByNameSerializer, CaseWriteSerializer
from curator_feature.services import ChartDataService, log_curator_edit
from curator_feature.models import DownloadLog, DashboardDownloadEvent, CuratorDataLog, BackendCase
from curator_feature.permissions import IsCuratorRole, ReadOnlyOrCurator
from curator_feature.views import (
    CuratorCaseListCreateView,
    CuratorCaseDetailView,
    DiseaseListCreateView,
    CuratorDiseaseListCreateView,
    CuratorDataLogListCreateAPIView,
)
from curator_feature.admin import CuratorDataLogAdmin
from pt_backend.models import Location, Disease
from pt_backend.models import Case, News, User as PtUser
from django.utils import timezone
from django.test import override_settings
from rest_framework.test import APIRequestFactory, force_authenticate
from django.contrib.admin.sites import AdminSite
from types import SimpleNamespace
from unittest.mock import patch
from uuid import uuid4
from curator_feature.tests import _create_case_table_no_fk, _drop_case_table
from datetime import timedelta
from decimal import Decimal


class SerializerAndServiceExtraTests(TestCase):
    def test_location_resolve_multiple_without_province_raises(self):
        Location.objects.create(city='Springfield', province='X', latitude=1.0, longitude=1.0)
        Location.objects.create(city='Springfield', province='Y', latitude=2.0, longitude=2.0)

        ser = LocationByNameSerializer(data={'city': 'springfield'})
        self.assertTrue(ser.is_valid())
        with self.assertRaises(drf_serializers.ValidationError) as cm:
            ser.resolve()
        self.assertIn("Multiple locations named", str(cm.exception))

    def test_location_resolve_missing_fields_raises(self):
        # no existing location
        ser = LocationByNameSerializer(data={'city': 'NoTown'})
        self.assertTrue(ser.is_valid())
        with self.assertRaises(drf_serializers.ValidationError) as cm:
            ser.resolve()
        self.assertIn("Provide province", str(cm.exception))

    def test_location_resolve_create_success(self):
        ser = LocationByNameSerializer(data={
            'city': 'NewCity',
            'province': 'Prov',
            'latitude': '1.234567',
            'longitude': '2.345678',
        })
        self.assertTrue(ser.is_valid(), msg=str(ser.errors))
        loc = ser.resolve()
        self.assertIsInstance(loc, Location)
        self.assertEqual(loc.province, 'Prov')

    def test_resolve_disease_id_raises_when_missing(self):
        cw = CaseWriteSerializer()
        with self.assertRaises(drf_serializers.ValidationError) as cm:
            cw._resolve_disease_id('this-does-not-exist')
        self.assertIn("Disease 'this-does-not-exist' not found", str(cm.exception))

    def test_chartdataservice_helpers_and_formatters(self):
        svc = ChartDataService(statistics_coordinator=object())

        # _json_serializer handles sets
        out = svc._json_serializer({3, 1, 2})
        self.assertEqual(out, [1, 2, 3])

        # build cache key with non-empty filters (uses json serialization)
        key = svc._build_cache_key({'s': {3, 1}})
        self.assertTrue(key.startswith(svc.CACHE_NAMESPACE))

        # _safe_int allow_null
        self.assertIsNone(svc._safe_int(None, allow_null=True))
        self.assertEqual(svc._safe_int('not-int', default=7), 7)

        # _format_trend: non-list items and points missing date should be skipped
        payload = {
            'insiden': [
                {'date': '2021-01-01', 'count': '5'},
                {'count': 3},  # missing date
            ],
            'badseverity': 'notalist'
        }
        trend = svc._format_trend(payload)
        self.assertIn('series', trend)
        self.assertEqual(trend['meta']['seriesCount'], 1)

        # _normalize_news_section: non-dict returns error meta
        sec = svc._normalize_news_section(None, 'top', 'all')
        self.assertIn('error', sec['meta'])

        # normalize with entries using different field names
        payload = {
            'top_national': [{'portal': 'X', 'count': '2'}, {'portal': None}],
            'all_national': [{'portal': 'A', 'news_count': '3', 'disease_count': '1'}, {'portal': 'B'}],
        }
        section = svc._normalize_news_section(payload, 'top_national', 'all_national')
        self.assertEqual(section['meta']['uniquePortals'], 2)

    def test_dashboard_download_event_serializer_validations_and_case_insensitive_choices(self):
        from curator_feature.serializers import DashboardDownloadEventSerializer

        # filters must be dict or None
        ser = DashboardDownloadEventSerializer(data={
            'metric': 'jumlah_kasus',
            'file_format': 'png',
            'filters': 'not-a-dict',
            'source': 'web',
        })
        self.assertFalse(ser.is_valid())
        self.assertIn('filters', ser.errors)

        # source blank rejected
        ser = DashboardDownloadEventSerializer(data={
            'metric': 'jumlah_kasus',
            'file_format': 'png',
            'filters': None,
            'source': '',
        })
        self.assertFalse(ser.is_valid())
        self.assertIn('source', ser.errors)

        # case-insensitive choices accepted (omit filters key)
        ser = DashboardDownloadEventSerializer(data={
            'metric': 'JUMLAH_KASUS',
            'file_format': 'Png',
            'source': 'app',
        })
        self.assertTrue(ser.is_valid(), msg=str(ser.errors))

    def test_format_severity_branches(self):
        svc = ChartDataService(statistics_coordinator=object(), cache_backend=None, cache_timeout=0)

        # non-dict payload
        res = svc._format_severity(None)
        self.assertIn('error', res['meta'])

        # payload with error
        res = svc._format_severity({'error': 'boom'})
        self.assertEqual(res['meta']['error'], 'boom')

        # payload with counts and extra keys and explicit total_cases
        payload = {
            'severity_counts': {'hospitalisasi': '2', 'other': '3'},
            'total_cases': '10'
        }
        res = svc._format_severity(payload)
        # should include hospitalisasi first then other
        self.assertEqual(res['meta']['totalCases'], 10)
        self.assertTrue(any(d['severity'] == 'hospitalisasi' for d in res['data']))

    def test_casewrite_update_upserts_news_and_changes_fields(self):
        # prepare disease and locations
        d1 = Disease.objects.create(name='OldDisease', level_of_alertness=1)
        d2 = Disease.objects.create(name='NewDisease', level_of_alertness=2)
        loc1 = Location.objects.create(city='CityA', province='P', latitude=1.0, longitude=1.0)

        case = Case.objects.create(gender='male', age=30, city='CityA', status='biasa', severity='insiden', disease=d1, location=loc1)
        # create an existing news (older)
        News.objects.create(
            portal='X', title='old', type='t', content='c', url='http://x', author='a', date_published=timezone.now() - timedelta(days=2), case=case
        )

        # update with new disease name and news
        validated_data = {
            'disease': 'NewDisease',
            'news': {'portal': 'Y', 'title': 'new', 'type': 't', 'content': 'newc', 'url': 'http://y', 'author': 'b', 'date_published': timezone.now()},
        }

        ser = CaseWriteSerializer()
        updated = ser.update(case, validated_data)
        self.assertEqual(updated.disease_id, d2.id)
        latest = updated.news.order_by('date_published', 'id').last()
        self.assertEqual(latest.title, 'new')

    def test_casewrite_update_creates_news_when_none(self):
        d1 = Disease.objects.create(name='OnlyDisease', level_of_alertness=1)
        loc1 = Location.objects.create(city='CityB', province='P', latitude=1.0, longitude=1.0)
        case = Case.objects.create(gender='female', age=25, city='CityB', status='biasa', severity='insiden', disease=d1, location=loc1)

        validated_data = {
            'news': {'portal': 'Z', 'title': 'first', 'type': 't', 'content': 'c', 'url': 'http://z', 'author': 'a', 'date_published': timezone.now()},
        }
        ser = CaseWriteSerializer()
        updated = ser.update(case, validated_data)
        self.assertTrue(updated.news.exists())

    def test_casewrite_update_with_location_and_field_changes(self):
        # prepare disease and locations
        d1 = Disease.objects.create(name='DL', level_of_alertness=1)
        loc_old = Location.objects.create(city='OldCity', province='P', latitude=1.0, longitude=1.0)

        case = Case.objects.create(gender='male', age=40, city='OldCity', status='biasa', severity='insiden', disease=d1, location=loc_old)

        # create another existing location to resolve to
        Location.objects.create(city='TargetCity', province='TargetProv', latitude=3.0, longitude=3.0)

        validated_data = {
            'location': {'city': 'TargetCity'},
            'city': 'RenamedCity',
            'news': {'portal': 'N', 'title': 't', 'type': 't', 'content': 'c', 'url': 'http://n', 'author': 'a', 'date_published': timezone.now()},
        }
        ser = CaseWriteSerializer()
        updated = ser.update(case, validated_data)
        self.assertEqual(updated.city, 'RenamedCity')
        self.assertEqual(updated.location.city.lower(), 'targetcity')

    def test_chartdataservice_cache_and_exceptions(self):
        # cache get returns a payload -> _fetch_statistics should return it
        class FakeCacheHit:
            def get(self, k):
                return {'cached': True}
            def set(self, k, v, timeout=None):
                pass

        svc = ChartDataService(statistics_coordinator=object(), cache_backend=FakeCacheHit(), cache_timeout=10)
        out = svc._fetch_statistics({})
        self.assertEqual(out, {'cached': True})
        # cache.set should be a no-op but still executed
        svc._cache_set('another', {'value': 1})

        # cache.get raises -> _cache_get returns None
        class BadCacheGet:
            def get(self, k):
                raise RuntimeError('boom')
            def set(self, k, v, timeout=None):
                pass

        svc2 = ChartDataService(statistics_coordinator=object(), cache_backend=BadCacheGet(), cache_timeout=10)
        self.assertIsNone(svc2._cache_get('key'))
        svc2._cache_set('key', {'value': 2})

        # cache.set raises -> _cache_set should handle and not raise
        class BadCacheSet:
            def get(self, k):
                return None
            def set(self, k, v, timeout=None):
                raise RuntimeError('boom')

        svc3 = ChartDataService(statistics_coordinator=object(), cache_backend=BadCacheSet(), cache_timeout=10)
        # Should not raise
        svc3._cache_set('k', {'a': 1})
        self.assertIsNone(svc3._cache_get('missing'))

        # when cache disabled we should still call coordinator
        class DummyCoordinator:
            def __init__(self):
                self.called = False
                self.received = None

            def generate_comprehensive_report(self, **filters):
                self.called = True
                self.received = filters
                return {'fresh': True}

        dummy = DummyCoordinator()
        svc4 = ChartDataService(statistics_coordinator=dummy, cache_backend=None, cache_timeout=0)
        result = svc4._fetch_statistics({'foo': 'bar'})
        self.assertTrue(dummy.called)
        self.assertEqual(dummy.received, {'foo': 'bar'})
        self.assertEqual(result, {'fresh': True})

        # cache enabled but miss triggers write-through
        class CacheSpy:
            def __init__(self):
                self.stored = None

            def get(self, k):
                return None

            def set(self, k, v, timeout=None):
                self.stored = v

        cache_spy = CacheSpy()

        class PayloadCoordinator:
            def generate_comprehensive_report(self, **filters):
                return {'computed': filters}

        svc5 = ChartDataService(statistics_coordinator=PayloadCoordinator(), cache_backend=cache_spy, cache_timeout=5)
        computed = svc5._fetch_statistics({'x': 1})
        self.assertEqual(computed, {'computed': {'x': 1}})
        self.assertEqual(cache_spy.stored, {'computed': {'x': 1}})

        # _json_serializer should stringify non-set values
        self.assertEqual(svc5._json_serializer(Decimal('1.5')), '1.5')


class AdminAndModelCoverageTests(TestCase):
    def test_admin_disables_mutations_and_model_str(self):
        log = CuratorDataLog.objects.create(
            data_id=uuid4(),
            title="sample",
            submitted_by="tester",
            note="n",
            last_edited=timezone.now(),
        )
        admin_site = AdminSite()
        admin_obj = CuratorDataLogAdmin(CuratorDataLog, admin_site)
        request = SimpleNamespace()
        self.assertFalse(admin_obj.has_change_permission(request, obj=log))
        self.assertFalse(admin_obj.has_delete_permission(request, obj=log))
        self.assertIn("sample", str(log))

    def test_log_curator_edit_creates_entry(self):
        data_id = uuid4()
        user = SimpleNamespace(username="coverage", email="coverage@example.com")
        log_curator_edit(user=user, data_id=data_id, title="Edited", note="done")
        entry = CuratorDataLog.objects.get(data_id=data_id)
        self.assertEqual(entry.title, "Edited")
        self.assertEqual(entry.submitted_by, "coverage")


class PermissionsCoverageTests(TestCase):
    def test_is_curator_role_no_user(self):
        request = SimpleNamespace(user=None)
        self.assertFalse(IsCuratorRole().has_permission(request, None))

    @override_settings(CURATOR_ROLE_CHECKS=("role",))
    def test_role_strategy_matches(self):
        request = SimpleNamespace(user=SimpleNamespace(role="curator"))
        self.assertTrue(IsCuratorRole().has_permission(request, None))

    @override_settings(CURATOR_ROLE_CHECKS=("group",))
    def test_group_strategy_queryset_success(self):
        class HappyGroups:
            def filter(self, **kwargs):
                return self

            def exists(self):
                return True

        request = SimpleNamespace(user=SimpleNamespace(groups=HappyGroups()))
        self.assertTrue(IsCuratorRole().has_permission(request, None))

    @override_settings(CURATOR_ROLE_CHECKS=("group",))
    def test_group_strategy_iterable_fallback(self):
        class FaultyGroups(list):
            def filter(self, *args, **kwargs):
                raise RuntimeError("boom")

        request = SimpleNamespace(
            user=SimpleNamespace(groups=FaultyGroups([SimpleNamespace(name="CURATOR")]))
        )
        self.assertTrue(IsCuratorRole().has_permission(request, None))

    @override_settings(CURATOR_ROLE_CHECKS=("group",))
    def test_group_strategy_iterable_exception(self):
        class BadGroups:
            def filter(self, *args, **kwargs):
                raise RuntimeError("boom")

            def __iter__(self):
                raise RuntimeError("iter fail")

        request = SimpleNamespace(user=SimpleNamespace(groups=BadGroups()))
        self.assertFalse(IsCuratorRole().has_permission(request, None))

    @override_settings(CURATOR_ROLE_CHECKS=("group",))
    def test_group_strategy_iterable_no_match(self):
        request = SimpleNamespace(
            user=SimpleNamespace(groups=[SimpleNamespace(name="VIEWER")])
        )
        self.assertFalse(IsCuratorRole().has_permission(request, None))

    @override_settings(CURATOR_ROLE_CHECKS=("unknown",))
    def test_unknown_strategy_denies(self):
        request = SimpleNamespace(user=SimpleNamespace(role="CURATOR"))
        self.assertFalse(IsCuratorRole().has_permission(request, None))

    def test_read_only_or_curator_safe_methods(self):
        request = SimpleNamespace(method="GET")
        self.assertTrue(ReadOnlyOrCurator().has_permission(request, None))

    def test_read_only_or_curator_requires_token_and_role(self):
        allowed_request = SimpleNamespace(method="POST", user=SimpleNamespace(id=1, role="CURATOR"))
        denied_request = SimpleNamespace(method="POST", user=SimpleNamespace(id=None, role="CURATOR"))
        self.assertTrue(ReadOnlyOrCurator().has_permission(allowed_request, None))
        self.assertFalse(ReadOnlyOrCurator().has_permission(denied_request, None))


class ViewHelpersCoverageTests(TestCase):
    def test_disease_list_get_permissions(self):
        view = DiseaseListCreateView()
        view.request = SimpleNamespace(method="GET")
        self.assertEqual(view.get_permissions(), [])

        view.request = SimpleNamespace(method="POST")
        perms = view.get_permissions()
        self.assertEqual(len(perms), 1)
        self.assertIsInstance(perms[0], ReadOnlyOrCurator)
        self.assertTrue(hasattr(view.get_queryset(), "order_by"))

    def test_curator_disease_list_get_queryset(self):
        view = CuratorDiseaseListCreateView()
        queryset = view.get_queryset()
        self.assertTrue(hasattr(queryset, "order_by"))

    def test_parse_positive_int_invalid(self):
        view = CuratorCaseListCreateView()
        self.assertEqual(view._parse_positive_int("abc", default=7), 7)
        self.assertEqual(view._parse_positive_int(-3, default=5), 5)

    def test_case_view_logging_exceptions_suppressed(self):
        view = CuratorCaseListCreateView()
        view.request = SimpleNamespace(user=SimpleNamespace(username="tester"))

        class DummySerializer:
            def save(self):
                return SimpleNamespace(id=uuid4(), severity=None, status="active")

        with patch("curator_feature.views.log_curator_action", side_effect=RuntimeError("boom")):
            view.perform_create(DummySerializer())

        detail_view = CuratorCaseDetailView()
        detail_view.request = SimpleNamespace(user=SimpleNamespace(username="tester"))

        class UpdateSerializer:
            def save(self):
                return SimpleNamespace(id=uuid4(), severity="high", status="active")

        with patch("curator_feature.views.log_curator_action", side_effect=RuntimeError("boom")):
            detail_view.perform_update(UpdateSerializer())

        disease = Disease.objects.create(name="D", level_of_alertness=1)
        location = Location.objects.create(city="C", province="P", latitude=0, longitude=0)
        case = Case.objects.create(
            disease=disease,
            location=location,
            gender="P",
            age=10,
            city="C",
            status="minimal",
            severity="insiden",
        )
        with patch("curator_feature.views.log_curator_action", side_effect=RuntimeError("boom")):
            detail_view.perform_destroy(case)

    def test_case_list_backend_branch_for_pt_user(self):
        _drop_case_table()
        _create_case_table_no_fk()
        BackendCase.objects.create(
            id=uuid4(),
            gender="P",
            age=21,
            city="Bandung",
            status="active",
            disease_id=uuid4(),
            location_id=uuid4(),
            severity="high",
        )
        user = PtUser.objects.create(name="Cur", email="cur@example.com", password="x", role="CURATOR")
        factory = APIRequestFactory()
        request = factory.get("/curator/cases/")
        force_authenticate(request, user=user)
        response = CuratorCaseListCreateView.as_view()(request)
        self.assertEqual(response.status_code, 200)
        self.assertGreaterEqual(response.data["total"], 1)

    def test_curator_datalog_filters_with_dates(self):
        now = timezone.now()
        CuratorDataLog.objects.create(
            data_id=uuid4(),
            title="alpha",
            submitted_by="alice",
            note="n1",
            last_edited=now - timedelta(days=2),
        )
        CuratorDataLog.objects.create(
            data_id=uuid4(),
            title="beta",
            submitted_by="bob",
            note="n2",
            last_edited=now - timedelta(hours=6),
        )
        start = (now - timedelta(days=1)).isoformat()
        end = now.isoformat()
        request = SimpleNamespace(query_params={"start": start, "end": end})
        view = CuratorDataLogListCreateAPIView()
        response = view.get(request)
        self.assertEqual(response.status_code, 200)
        self.assertIn("data", response.data)


class CaseSerializerCoverageTests(TestCase):
    def setUp(self):
        self.disease = Disease.objects.create(name="DBD", level_of_alertness=2)
        self.other_disease = Disease.objects.create(name="Flu", level_of_alertness=1)
        self.location = Location.objects.create(city="Jakarta", province="DKI", latitude=0.1, longitude=0.2)

    def _news_payload(self, title="Kasus"):
        return {
            "portal": "Portal",
            "title": title,
            "type": "artikel",
            "content": "Konten",
            "url": "https://example.com/news",
            "author": "Reporter",
            "date_published": "2024-01-01T00:00:00Z",
            "img_url": "",
        }

    def test_case_write_create_and_update_flow(self):
        payload = {
            "disease": "DBD",
            "gender": "P",
            "age": 12,
            "city": "Jakarta",
            "status": "bahaya",
            "severity": "insiden",
            "location": {"city": "Jakarta"},
            "news": self._news_payload(),
        }
        serializer = CaseWriteSerializer(data=payload)
        self.assertTrue(serializer.is_valid(), serializer.errors)
        case = serializer.save()
        self.assertEqual(case.disease.name, "DBD")
        self.assertEqual(case.news.count(), 1)

        update_payload = {
            "disease": "Flu",
            "location": {"city": "Jakarta"},
            "severity": "mortalitas",
            "news": self._news_payload(title="Update"),
        }
        update_serializer = CaseWriteSerializer(instance=case, data=update_payload, partial=True)
        self.assertTrue(update_serializer.is_valid(), update_serializer.errors)
        updated_case = update_serializer.save()
        self.assertEqual(updated_case.disease.name, "Flu")
        self.assertEqual(updated_case.severity, "mortalitas")
        self.assertEqual(updated_case.news.order_by("date_published").last().title, "Update")

        # exercise branch creating news when none exist
        updated_case.news.all().delete()
        second_update = CaseWriteSerializer(
            instance=updated_case,
            data={"news": self._news_payload(title="Baru")},
            partial=True,
        )
        self.assertTrue(second_update.is_valid(), second_update.errors)
        second_update.save()
        self.assertEqual(updated_case.news.count(), 1)

    def test_case_write_unknown_disease_raises(self):
        payload = {
            "disease": "Unknown",
            "gender": "L",
            "age": 10,
            "city": "Jakarta",
            "status": "minimal",
            "severity": "insiden",
            "location": {"city": "Jakarta"},
            "news": self._news_payload(),
        }
        serializer = CaseWriteSerializer(data=payload)
        self.assertTrue(serializer.is_valid(), serializer.errors)
        with self.assertRaises(drf_serializers.ValidationError):
            serializer.save()
