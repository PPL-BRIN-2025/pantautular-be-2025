from datetime import datetime, timedelta, timezone as datetime_timezone
from types import SimpleNamespace
from unittest import mock
import uuid
import pytz

from django.http import HttpRequest, QueryDict
from django.db.models import Q, QuerySet
from django.test import SimpleTestCase, TestCase, override_settings
from django.utils import timezone
from rest_framework.test import APIRequestFactory
from rest_framework.response import Response
from django.db.utils import OperationalError
from django.core.exceptions import ObjectDoesNotExist

from pt_backend.filter.date_range_filter import DateRangeFilter, TimeWindowError
from pt_backend.filter.location_filter import LocationFilter
from pt_backend.filter.service import CaseFilterService, CaseFilterValidationError
from pt_backend.payload_scanner import SQLInjectionDetector
from pt_backend.prome_metrics import (
    ACTIVE_REQUESTS,
    measure_time,
    count_calls,
    track_data_count,
    database_timer,
    track_active_requests,
    setup_grafana_metrics,
    collect_system_metrics,
    start_metrics_collection,
)
from pt_backend.services import (
    ClimateService,
    AverageSeverityByProvince,
    CaseService,
    CaseDetailService,
    CasesFilterService,
)
from pt_backend.views import (
    WeightedSeverityAnalysisView,
    build_default_climate_response,
    AllCaseLocationsView,
    SeverityFilteringStatsView,
    StatisticsView,
    ProvinceHumidityView,
    ProvincePrecipitationView,
    ProvinceTemperatureView,
    health_check,
)
from pt_backend.serializers import ProvinceHumiditySerializer
import pt_backend as backend_init
from pt_backend.models import User, CaseUploadBatch
from pt_backend.constants import (
    CLIMATE_ERROR_INVALID_FORMAT,
    CLIMATE_ERROR_INVALID_VALUE,
    PROVINCE_TO_CODE,
)
from pt_backend.repositories import LocationRepository, NewsRepository


class DateRangeFilterTests(SimpleTestCase):
    def setUp(self):
        self.filter = DateRangeFilter()

    def test_parse_time_params_period_alias(self):
        params = {"period": "1h"}
        parsed = self.filter.parse_time_params(params, now=timezone.now())
        self.assertIn("start_date", parsed)
        self.assertIn("end_date", parsed)

    def test_resolve_time_range_invalid_order(self):
        data = {
            "start_date": "2024-01-02T00:00:00",
            "end_date": "2024-01-01T00:00:00",
        }
        with self.assertRaises(TimeWindowError):
            self.filter.resolve_time_range(data)

    def test_build_time_window_returns_predicate(self):
        now = timezone.now()
        data = {
            "start_date": (now - timedelta(days=1)).isoformat(),
            "end_date": now.isoformat(),
        }
        predicate = self.filter.build_time_window(field="news__date_published", data=data, null_guard_field="news")
        self.assertIsNotNone(predicate)

    def test_custom_alias_merging(self):
        custom = DateRangeFilter(period_aliases={"2h": (2, "hours")})
        self.assertIn("2h", custom.period_aliases)

    def test_parse_time_params_preserves_timezone(self):
        params = {"period": "1h", "timezone": "Asia/Jakarta"}
        payload = self.filter.parse_time_params(params, now=timezone.now())
        self.assertEqual(payload["timezone"], "Asia/Jakarta")

    def test_resolve_time_range_callable_alias(self):
        now = timezone.now()

        def alias(now_local, tz):
            del tz
            return (now_local - timedelta(hours=2), now_local)

        custom = DateRangeFilter(period_aliases={"window": alias})
        start, end = custom.resolve_time_range({"period": "window"}, now=now)
        self.assertLess(start, end)

    def test_resolve_time_range_start_only_alias(self):
        now = timezone.now()

        def alias(now_local, tz):
            del tz
            return (now_local - timedelta(hours=1), None)

        custom = DateRangeFilter(period_aliases={"start-only": alias})
        start, end = custom.resolve_time_range({"period": "start-only"}, now=now)
        self.assertIsNotNone(start)
        self.assertIsNone(end)

    def test_resolve_time_range_end_only_alias(self):
        now = timezone.now()

        def alias(now_local, tz):
            del tz
            return (None, now_local)

        custom = DateRangeFilter(period_aliases={"end-only": alias})
        start, end = custom.resolve_time_range({"period": "end-only"}, now=now)
        self.assertIsNone(start)
        self.assertIsNotNone(end)

    def test_parse_period_returns_none_for_invalid_string(self):
        """Ensure the fallback branch for malformed string periods is covered."""
        self.assertIsNone(self.filter.parse_period("   invalid-unit"))

    def test_build_time_predicate_adds_null_guard(self):
        now = timezone.now()
        predicate = self.filter.build_time_predicate(
            "news__date_published",
            now - timedelta(hours=2),
            now,
            null_guard_field="news",
        )
        self.assertIn(("news__isnull", False), predicate.children)

    def test_validate_span_limit(self):
        start = timezone.now() - timedelta(days=5)
        end = timezone.now()
        with self.assertRaises(TimeWindowError):
            self.filter.validate(
                start=start,
                end=end,
                start_key="start_date",
                end_key="end_date",
                max_span_days=1,
                now=None,
            )

    def test_validate_future_start_raises(self):
        now = timezone.now()
        with self.assertRaises(TimeWindowError):
            self.filter.validate(
                start=now + timedelta(days=1),
                end=now + timedelta(days=2),
                start_key="start_date",
                end_key="end_date",
                max_span_days=None,
                now=now,
            )

    def test_validate_span_within_limit(self):
        start = timezone.now() - timedelta(days=1)
        end = timezone.now()
        self.filter.validate(
            start=start,
            end=end,
            start_key="start_date",
            end_key="end_date",
            max_span_days=7,
            now=None,
        )

    def test_extract_value_from_getlist_and_get(self):
        class Dummy:
            def getlist(self, key):
                return ["", "  ", "2024-01-01"] if key == "date" else []

        self.assertEqual(self.filter._extract_value(Dummy(), "date"), "2024-01-01")
        self.assertEqual(self.filter._extract_value({"date": ["", "now"]}, "date"), "now")

    def test_extract_value_from_attr(self):
        class Dummy:
            date = "2024-01-02"

        self.assertEqual(self.filter._extract_value(Dummy(), "date"), "2024-01-02")

    def test_normalize_period_alias_result_variants(self):
        start = timezone.now()
        result = self.filter._normalize_period_alias_result((start, start + timedelta(hours=1)), pytz.UTC, "period")
        self.assertIsNotNone(result.start)
        delta_result = self.filter._normalize_period_alias_result(timedelta(minutes=5), pytz.UTC, "period")
        self.assertEqual(delta_result.delta, timedelta(minutes=5))
        with self.assertRaises(TimeWindowError):
            self.filter._normalize_period_alias_result("bad", pytz.UTC, "period")

    def test_resolve_timezone_prefers_tzinfo_object(self):
        tz = datetime_timezone.utc
        resolved = self.filter.resolve_timezone(tz, pytz.UTC)
        self.assertIs(resolved, tz)

    def test_parse_datetime_helpers(self):
        self.assertIsNone(self.filter.parse_datetime(None, pytz.UTC))
        parsed = self.filter.parse_datetime("2024-05-01", pytz.UTC)
        self.assertEqual(parsed.year, 2024)
        naive = self.filter.parse_datetime("2024-05-01T00:00:00", datetime_timezone.utc)
        self.assertEqual(naive.tzinfo, datetime_timezone.utc)

    @mock.patch("pt_backend.filter.date_range_filter.django_parse_datetime", return_value=None)
    def test_parse_datetime_uses_fallback_formats(self, _):
        parsed = self.filter.parse_datetime("2024-05-01T00:00:00Z", pytz.UTC)
        self.assertEqual(parsed.year, 2024)

    def test_apply_period_variants(self):
        start = timezone.now()
        end = start + timedelta(hours=1)
        result = self.filter.apply_period(
            start_date=start,
            end_date=end,
            period=timedelta(0),
            tz=pytz.UTC,
            now=None,
        )
        self.assertEqual(result, (start, end))
        only_start = self.filter.apply_period(
            start_date=start,
            end_date=None,
            period=timedelta(hours=2),
            tz=pytz.UTC,
            now=None,
        )
        self.assertIsNotNone(only_start[1])
        only_end = self.filter.apply_period(
            start_date=None,
            end_date=end,
            period=timedelta(hours=2),
            tz=pytz.UTC,
            now=None,
        )
        self.assertIsNotNone(only_end[0])
        inferred = self.filter.apply_period(
            start_date=None,
            end_date=None,
            period=timedelta(hours=2),
            tz=pytz.UTC,
            now=start,
        )
        self.assertIsNotNone(inferred[0])

    def test_ensure_timezone_variants(self):
        naive = datetime(2024, 1, 1, 0, 0, 0)
        localized = self.filter.ensure_timezone(naive, pytz.UTC)
        self.assertEqual(localized.tzinfo, pytz.UTC)
        dummy = datetime_timezone.utc
        applied = self.filter.ensure_timezone(naive, dummy)
        self.assertEqual(applied.tzinfo, dummy)

    def test_parse_period_variants(self):
        self.assertEqual(self.filter.parse_period({"value": 5, "unit": "days"}), timedelta(days=5))
        self.assertIsNone(self.filter.parse_period({"value": "bad"}))
        self.assertIsNone(self.filter.parse_period({"value": 2, "unit": "unknown"}))
        self.assertEqual(self.filter.parse_period("7"), timedelta(days=7))
        self.assertEqual(self.filter.parse_period("2hours"), timedelta(hours=2))
        self.assertIsNone(self.filter.parse_period("   "))
        self.assertIsNone(self.filter.parse_period("unknownunit"))
        self.assertIsNone(self.filter.parse_period("xxhours"))

    def test_apply_period_infers_when_missing(self):
        now = timezone.now()
        start, end = self.filter.apply_period(
            start_date=None,
            end_date=None,
            period=timedelta(hours=1),
            tz=pytz.UTC,
            now=now,
        )
        self.assertIsNotNone(start)
        self.assertIsNotNone(end)

    def test_apply_period_without_now(self):
        start, end = self.filter.apply_period(
            start_date=None,
            end_date=None,
            period=timedelta(hours=1),
            tz=pytz.UTC,
        )
        self.assertIsNotNone(start)
        self.assertIsNotNone(end)

    def test_apply_period_returns_existing_bounds(self):
        end = timezone.now()
        start = end - timedelta(hours=1)
        result = self.filter.apply_period(
            start_date=start,
            end_date=end,
            period=timedelta(hours=2),
            tz=pytz.UTC,
        )
        self.assertEqual(result, (start, end))

    def test_first_non_empty_helpers(self):
        self.assertIsNone(self.filter._first_non_empty("   "))
        self.assertEqual(self.filter._first_non_empty(["", None, "x"]), "x")
        self.assertIsNone(self.filter._first_non_empty([None, ""]))


class LocationFilterTests(SimpleTestCase):
    def setUp(self):
        self.filter = LocationFilter()

    def test_build_query_with_nested_mapping(self):
        values = {
            "provinces": {"value": "DKI"},
            "cities": [{"label": "Jakarta"}, None, "Jakarta"],
        }
        query = self.filter.build_query(values)
        self.assertTrue(query)

    def test_build_query_with_iterable(self):
        query = self.filter.build_query(["Bandung", "Bandung", "Surabaya"])
        self.assertTrue(query)

    def test_mapping_without_specific_keys(self):
        query = self.filter.build_query({"other": "DKI"})
        self.assertTrue(query)

    def test_empty_values_returns_empty_q(self):
        self.assertEqual(self.filter.build_query([None, ""]), Q())

    def test_query_with_only_provinces(self):
        request = {"provinces": ["DKI"], "cities": []}
        query = self.filter.build_query(request)
        self.assertTrue(query)

    def test_query_with_only_cities(self):
        request = {"cities": ["Jakarta"]}
        query = self.filter.build_query(request)
        self.assertTrue(query)

    def test_normalize_skips_none_values(self):
        normalized = self.filter._normalize({"value": None})
        self.assertEqual(normalized, [])

    def test_collect_values_nested_mapping_and_scalar(self):
        nested = {"a": {"b": "City"}}
        self.assertEqual(self.filter._collect_values(nested), ["City"])
        self.assertEqual(self.filter._collect_values(123), [123])


class CaseFilterServiceTests(SimpleTestCase):
    def setUp(self):
        self.service = CaseFilterService(time_filter=DateRangeFilter())

    def test_extract_batch_id_invalid(self):
        with self.assertRaises(CaseFilterValidationError):
            self.service._extract_batch_id({"batch_id": "not-a-uuid"})

    def test_store_time_window_eviction(self):
        self.service._time_window_cache_size = 1
        self.service._store_time_window(("a", None), None)
        self.service._store_time_window(("b", None), None)
        self.assertEqual(list(self.service._time_window_cache.keys()), [("b", None)])

    def test_get_time_window_q_uses_cache(self):
        data = {
            "start_date": timezone.now().isoformat(),
            "end_date": timezone.now().isoformat(),
        }
        q1 = self.service._get_time_window_q(data)
        q2 = self.service._get_time_window_q(data)
        self.assertEqual(q1, q2)

    def test_extract_batch_id_from_dict(self):
        batch_id = uuid.uuid4()
        data = {"batch": {"data_id": str(batch_id)}}
        self.assertEqual(self.service._extract_batch_id(data), str(batch_id))

    def test_extract_batch_id_from_iterable(self):
        batch_id = uuid.uuid4()
        data = {"dataset": ["", str(batch_id)]}
        self.assertEqual(self.service._extract_batch_id(data), str(batch_id))

    def test_extract_batch_id_returns_none_when_all_empty(self):
        self.assertIsNone(self.service._extract_batch_id({"dataset": ["", None]}))

    def test_time_window_classmethod(self):
        now = timezone.now()
        data = {
            "start_date": (now - timedelta(hours=1)).isoformat(),
            "end_date": now.isoformat(),
        }
        predicate = CaseFilterService.time_window(data, field="news__date_published")
        self.assertIsNotNone(predicate)

    def test_resolve_time_window_classmethod(self):
        now = timezone.now()
        data = {
            "start_date": (now - timedelta(hours=1)).isoformat(),
            "end_date": now.isoformat(),
        }
        start, end = CaseFilterService.resolve_time_window(data)
        self.assertLess(start, end)


class CaseFilterValidationErrorTests(SimpleTestCase):
    def test_as_payload_includes_fields(self):
        error = CaseFilterValidationError("boom", fields={"start_date": ["bad"]})
        payload = error.as_payload()
        self.assertEqual(payload["error"]["fields"]["start_date"], ["bad"])

    def test_as_payload_without_fields(self):
        error = CaseFilterValidationError("boom")
        payload = error.as_payload()
        self.assertNotIn("fields", payload["error"])


class PayloadScannerTests(SimpleTestCase):
    def test_detects_suspicious_patterns(self):
        request = SimpleNamespace(
            query_params={"q": "SELECT * FROM users"},
            data={"notes": ["safe", "DROP TABLE reports"]},
        )
        with self.assertRaises(Exception):
            SQLInjectionDetector.check(request)

    def test_ignores_non_strings(self):
        request = SimpleNamespace(query_params={"q": 123}, data={"numbers": [1, 2, 3]})
        SQLInjectionDetector.check(request)

    def test_is_suspicious_false_branch(self):
        self.assertFalse(SQLInjectionDetector._is_suspicious("status = safe"))

    def test_check_without_data_attribute(self):
        request = SimpleNamespace(query_params={"q": "safe"})
        SQLInjectionDetector.check(request)

    def test_check_ignores_non_string_list_items(self):
        request = SimpleNamespace(query_params={}, data={"values": [1, 2, 3]})
        SQLInjectionDetector.check(request)

    def test_detects_in_request_body_string(self):
        request = SimpleNamespace(query_params={}, data={"payload": "DROP TABLE x"})
        with self.assertRaises(Exception):
            SQLInjectionDetector.check(request)

    def test_detects_in_request_body_list(self):
        request = SimpleNamespace(query_params={}, data={"notes": ["ok", "SELECT * FROM users"]})
        with self.assertRaises(Exception):
            SQLInjectionDetector.check(request)

    def test_check_allows_safe_string_list(self):
        request = SimpleNamespace(query_params={}, data={"notes": ["safe"]})
        SQLInjectionDetector.check(request)

    def test_direct_data_check_with_list(self):
        SQLInjectionDetector._check_data_for_injection({"notes": ["safe"]})

    def test_direct_data_check_with_non_list_branch(self):
        """Cover the branch where list handling is skipped entirely."""
        SQLInjectionDetector._check_data_for_injection({"meta": {"page": 1}})


class PrometheusHelpersTests(SimpleTestCase):
    def test_measure_time_decorator(self):
        histogram = mock.Mock()

        @measure_time(histogram)
        def sample():
            return "ok"

        sample()
        histogram.observe.assert_called()

    def test_count_calls_decorator(self):
        counter = mock.Mock()

        @count_calls(counter)
        def sample():
            return "ok"

        sample()
        counter.inc.assert_called()

    def test_track_data_count(self):
        histogram = mock.Mock()

        class Resp:
            data = {"data": [1, 2, 3]}

        @track_data_count(histogram)
        def sample():
            return Resp()

        sample()
        histogram.observe.assert_called_with(3)

    def test_database_timer(self):
        histogram = mock.Mock()
        with mock.patch("pt_backend.prome_metrics.DB_QUERY_TIME", histogram):
            with database_timer():
                pass
        histogram.observe.assert_called()

    def test_track_active_requests(self):
        gauge = mock.Mock()
        with mock.patch("pt_backend.prome_metrics.ACTIVE_REQUESTS", gauge):
            @track_active_requests
            def sample():
                return "ok"

            sample()
        gauge.inc.assert_called_once()
        gauge.dec.assert_called_once()

    def test_setup_grafana_metrics_handles_error(self):
        with mock.patch("pt_backend.prome_metrics.start_http_server", side_effect=Exception("boom")):
            setup_grafana_metrics(port=9999)

    @mock.patch("pt_backend.prome_metrics.start_http_server")
    def test_setup_grafana_metrics_success(self, mock_server):
        with mock.patch("builtins.print") as mock_print:
            setup_grafana_metrics(port=9100)
        mock_server.assert_called_once_with(9100)
        mock_print.assert_called()

    def test_track_data_count_handles_exception(self):
        histogram = mock.Mock()

        class Resp:
            @property
            def data(self):
                raise RuntimeError("boom")

        @track_data_count(histogram)
        def sample():
            return Resp()

        sample()
        histogram.observe.assert_not_called()

    @mock.patch("pt_backend.prome_metrics.threading.Thread")
    def test_start_metrics_collection_spawns_thread(self, mock_thread):
        start_metrics_collection()
        mock_thread.assert_called_once()
        mock_thread.return_value.start.assert_called_once()


class SystemMetricsTests(SimpleTestCase):
    def test_collect_system_metrics_handles_exception(self):
        process = mock.Mock()
        process.cpu_percent.side_effect = RuntimeError("boom")
        with mock.patch("pt_backend.prome_metrics.psutil.Process", return_value=process), \
            mock.patch("pt_backend.prome_metrics.os.getpid", return_value=1), \
            mock.patch("pt_backend.prome_metrics.time.sleep") as mock_sleep:
            collect_system_metrics(iterations=1)
        mock_sleep.assert_called_with(15)

    def test_collect_system_metrics_success_iteration(self):
        process = mock.Mock()
        process.cpu_percent.return_value = 1
        process.memory_info.return_value = SimpleNamespace(rss=1)
        with mock.patch("pt_backend.prome_metrics.psutil.Process", return_value=process), \
            mock.patch("pt_backend.prome_metrics.os.getpid", return_value=1), \
            mock.patch("pt_backend.prome_metrics.time.sleep") as mock_sleep:
            collect_system_metrics(iterations=1)
        mock_sleep.assert_any_call(5)

    def test_collect_system_metrics_handles_none_iterations_branch(self):
        process = mock.Mock()
        process.cpu_percent.side_effect = SystemExit("stop")
        per_core = mock.Mock()
        per_core.labels.return_value = mock.Mock()
        with mock.patch("pt_backend.prome_metrics.psutil.Process", return_value=process), \
            mock.patch("pt_backend.prome_metrics.psutil.cpu_percent", return_value=[0.5]), \
            mock.patch("pt_backend.prome_metrics.CPU_USAGE"), \
            mock.patch("pt_backend.prome_metrics.CPU_USAGE_PER_CORE", per_core), \
            mock.patch("pt_backend.prome_metrics.MEMORY_USAGE"), \
            mock.patch("pt_backend.prome_metrics.os.getpid", return_value=1):
            with self.assertRaises(SystemExit):
                collect_system_metrics()

    def test_collect_system_metrics_multiple_iterations(self):
        process = mock.Mock()
        process.cpu_percent.return_value = 1
        process.memory_info.return_value = SimpleNamespace(rss=1)
        per_core = mock.Mock()
        per_core.labels.return_value = mock.Mock()
        with mock.patch("pt_backend.prome_metrics.psutil.Process", return_value=process), \
            mock.patch("pt_backend.prome_metrics.psutil.cpu_percent", return_value=[0.5]), \
            mock.patch("pt_backend.prome_metrics.CPU_USAGE"), \
            mock.patch("pt_backend.prome_metrics.CPU_USAGE_PER_CORE", per_core), \
            mock.patch("pt_backend.prome_metrics.MEMORY_USAGE"), \
            mock.patch("pt_backend.prome_metrics.os.getpid", return_value=1), \
            mock.patch("pt_backend.prome_metrics.time.sleep", return_value=None) as mock_sleep:
            collect_system_metrics(iterations=2)
        self.assertGreaterEqual(mock_sleep.call_count, 2)


class ClimateViewsTests(SimpleTestCase):
    def setUp(self):
        self.factory = APIRequestFactory()

    def test_build_default_climate_response_invalid_serializer(self):
        class BadSerializer:
            def __init__(self, *_, **__):
                self.data = []

            def is_valid(self):
                return False

        response = build_default_climate_response(BadSerializer)
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.data["error"], CLIMATE_ERROR_INVALID_FORMAT)

    def test_build_default_climate_response_success(self):
        response = build_default_climate_response(ProvinceHumiditySerializer)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data), len(PROVINCE_TO_CODE))

    @mock.patch("pt_backend.views.build_default_climate_response", return_value=Response({"default": True}))
    def test_humidity_view_returns_default_on_no_data(self, mock_default):
        view = ProvinceHumidityView()
        view.climate_service = mock.Mock()
        view.climate_service.get_province_humidity.return_value = {"error": "No data available"}
        request = self.factory.get("/climate")
        response = view.get(request)
        mock_default.assert_called_once()
        self.assertEqual(response.data, {"default": True})

    @mock.patch("pt_backend.views.build_default_climate_response", return_value=Response({"default": True}))
    def test_precipitation_view_returns_default_on_no_data(self, mock_default):
        view = ProvincePrecipitationView()
        view.climate_service = mock.Mock()
        view.climate_service.get_province_precipitation.return_value = {"error": "No data available"}
        request = self.factory.get("/climate")
        response = view.get(request)
        mock_default.assert_called_once()
        self.assertEqual(response.data, {"default": True})

    @mock.patch("pt_backend.views.build_default_climate_response", return_value=Response({"default": True}))
    def test_temperature_view_returns_default_on_no_data(self, mock_default):
        view = ProvinceTemperatureView()
        view.climate_service = mock.Mock()
        view.climate_service.get_province_temperature.return_value = {"error": "No data available"}
        request = self.factory.get("/climate")
        response = view.get(request)
        mock_default.assert_called_once()
        self.assertEqual(response.data, {"default": True})


class HealthCheckTests(SimpleTestCase):
    def setUp(self):
        self.factory = APIRequestFactory()

    def test_health_check_handles_db_error(self):
        request = self.factory.get("/health")
        with mock.patch("pt_backend.views.connections") as mock_connections:
            mock_conn = mock.Mock()
            mock_conn.cursor.side_effect = OperationalError("boom")
            mock_connections.__getitem__.return_value = mock_conn
            response = health_check(request)
        self.assertEqual(response.status_code, 500)


class RepositoryTests(SimpleTestCase):
    @mock.patch("pt_backend.repositories.Location")
    def test_location_repository_province_empty(self, mock_location):
        repo = LocationRepository()
        values = mock_location.objects.values_list.return_value
        distinct = values.distinct.return_value
        distinct.exists.return_value = False
        self.assertEqual(repo.get_all_locations_province(), [])

    @mock.patch("pt_backend.repositories.Location")
    def test_location_repository_province_populated(self, mock_location):
        repo = LocationRepository()
        class FakeQuery(list):
            def exists(self):
                return bool(self)

        values = mock_location.objects.values_list.return_value
        values.distinct.return_value = FakeQuery(["DKI"])
        self.assertEqual(repo.get_all_locations_province(), ["DKI"])

    @mock.patch("pt_backend.repositories.News.objects")
    def test_news_repository_severity_dates_filters_none(self, mock_news):
        repo = NewsRepository()
        mock_news.annotate.return_value = mock_news
        mock_news.values.return_value = mock_news
        mock_news.annotate.return_value = mock_news
        mock_news.order_by.return_value = [
            {"case__severity": "High", "date": datetime(2024, 1, 1), "count": 2},
            {"case__severity": None, "date": datetime(2024, 1, 2), "count": 1},
        ]
        result = repo.get_all_severities_dates()
        self.assertIn("High", result)

    @mock.patch("pt_backend.repositories.Location")
    def test_location_repository_handles_object_does_not_exist(self, mock_location):
        repo = LocationRepository()
        mock_location.objects.values_list.side_effect = ObjectDoesNotExist
        self.assertEqual(
            repo.get_all_locations_province(),
            {"error": "Error retrieving locations"},
        )


class CaseDetailServiceTests(SimpleTestCase):
    def setUp(self):
        self.repository = mock.Mock()
        self.cache_service = mock.Mock()
        self.cache_service.get.return_value = None
        self.news_formatter = mock.Mock()
        self.protocol_formatter = mock.Mock()
        self.gender_formatter = mock.Mock()
        self.service = CaseDetailService(
            repository=self.repository,
            cache_service=self.cache_service,
            news_formatter=self.news_formatter,
            protocol_formatter=self.protocol_formatter,
            gender_formatter=self.gender_formatter,
        )

    def _make_case(self):
        return SimpleNamespace(
            id=1,
            location=SimpleNamespace(province="DKI"),
            gender="male",
            age=30,
            disease=SimpleNamespace(
                level_of_alertness="HIGH",
                name="Flu",
                protocols=SimpleNamespace(all=lambda: []),
            ),
            news=SimpleNamespace(all=lambda: []),
        )

    def test_get_case_detail_handles_processing_exception(self):
        case = self._make_case()
        self.repository.get_case_detail_by_id.return_value = case
        self.gender_formatter.format.side_effect = RuntimeError("boom")
        with self.assertRaises(RuntimeError):
            self.service.get_case_detail(1)

    def test_format_news_returns_empty_on_error(self):
        self.news_formatter.format.side_effect = RuntimeError("fail")
        result = self.service._format_news([SimpleNamespace()])
        self.assertEqual(result, [])

    def test_format_health_protocols_returns_empty_on_error(self):
        def failing():
            raise RuntimeError("boom")

        disease = SimpleNamespace(protocols=SimpleNamespace(all=failing))
        result = self.service._format_health_protocols(disease)
        self.assertEqual(result, [])


class CasesFilterServiceUtilityTests(SimpleTestCase):
    def setUp(self):
        self.service = CasesFilterService(case_service=mock.Mock())

    def test_clean_list_normalizes_entries(self):
        cleaned = self.service._clean_list([None, {"value": "Jakarta"}, 123, "  "])
        self.assertEqual(cleaned, ["Jakarta", "123"])

    def test_extract_locations_variants(self):
        mapping = {"foo": {"value": "DKI"}}
        result = self.service._extract_locations(mapping)
        self.assertEqual(result["provinces"], ["DKI"])
        explicit = {"provinces": ["DKI"], "cities": ["Jakarta"]}
        result = self.service._extract_locations(explicit)
        self.assertEqual(result["cities"], ["Jakarta"])
        iterable = ["Jakarta"]
        result = self.service._extract_locations(iterable)
        self.assertEqual(result["cities"], ["Jakarta"])
        scalar = self.service._extract_locations("Solo")
        self.assertEqual(scalar["cities"], ["Solo"])

    def test_collect_location_values_nested(self):
        nested = {"a": {"label": "City"}}
        self.assertEqual(self.service._collect_location_values(nested), ["City"])
        self.assertEqual(self.service._collect_location_values(7), [7])
        self.assertEqual(self.service._collect_location_values(None), [])

    def test_normalize_batch_id_variants(self):
        uid = uuid.uuid4()
        self.assertEqual(self.service._normalize_batch_id({"data_id": str(uid)}), str(uid))
        self.assertEqual(self.service._normalize_batch_id([None, str(uid)]), str(uid))
        self.assertIsNone(self.service._normalize_batch_id([]))
        with self.assertRaises(CaseFilterValidationError):
            self.service._normalize_batch_id("not-a-uuid")

    def test_normalize_batch_id_all_blank_iterable(self):
        """Ensure the branch that returns None after scanning iterables is covered."""
        self.assertIsNone(self.service._normalize_batch_id([None, ""]))

    def test_filter_by_locations_non_queryset(self):
        class Dummy:
            def __init__(self):
                self.last = None

            def filter(self, q):
                self.last = q
                return self

        cases = Dummy()
        result = self.service._filter_by_locations(cases, ["DKI"], ["Jakarta"])
        self.assertIs(result, cases)
        self.assertIsNotNone(cases.last)
        cases_only_cities = Dummy()
        result = self.service._filter_by_locations(cases_only_cities, None, ["Jakarta"])
        self.assertIs(result, cases_only_cities)
        self.assertIsNotNone(cases_only_cities.last)
        cases_only_provinces = Dummy()
        result = self.service._filter_by_locations(cases_only_provinces, ["DKI"], None)
        self.assertIs(result, cases_only_provinces)
        self.assertIsNotNone(cases_only_provinces.last)

        cases_no_filters = Dummy()
        result = self.service._filter_by_locations(cases_no_filters, [], [])
        self.assertIs(result, cases_no_filters)
        self.assertIsNone(cases_no_filters.last)

    def test_filter_by_locations_queryset_branch(self):
        qs = mock.Mock(spec=QuerySet)
        qs.filter.return_value = qs
        result = self.service._filter_by_locations(qs, ["DKI"], ["Jakarta"])
        self.assertIs(result, qs)
        self.assertTrue(qs.filter.called)

    def test_filter_by_locations_queryset_without_filters(self):
        qs = mock.Mock(spec=QuerySet)
        result = self.service._filter_by_locations(qs, None, None)
        self.assertIs(result, qs)
        qs.filter.assert_not_called()

    def test_filter_by_news_date_range_variants(self):
        cases = mock.Mock()
        cases.filter.return_value = cases
        start = datetime(2024, 1, 1)
        end = datetime(2024, 1, 2)
        self.service._filter_by_news_date_range(cases, (start, end))
        cases.filter.assert_called_with(news__date_published__range=[start, end])
        cases.filter.reset_mock()
        self.service._filter_by_news_date_range(cases, {"start": start, "end": None})
        cases.filter.assert_called_with(news__date_published__gte=start)
        cases.filter.reset_mock()
        self.service._filter_by_news_date_range(cases, {"start": None, "end": end})
        cases.filter.assert_called_with(news__date_published__lte=end)
        self.assertIs(self.service._filter_by_news_date_range(cases, None), cases)
        cases.filter.reset_mock()
        self.assertIs(self.service._filter_by_news_date_range(cases, "oops"), cases)
        cases.filter.assert_not_called()


class BackendInitTests(SimpleTestCase):
    def test_initialize_metrics_handles_all_labels(self):
        counter = mock.Mock(return_value=mock.Mock())
        with mock.patch.object(backend_init, "API_ERRORS", counter), \
            mock.patch.object(backend_init, "API_SUCCESS", counter), \
            mock.patch.object(backend_init, "DB_ERRORS", counter), \
            mock.patch.object(backend_init, "start_metrics_collection"):
            backend_init.initialize_metrics()

    def test_initialize_metrics_handles_failure(self):
        counter = mock.Mock()
        counter.labels.side_effect = RuntimeError("boom")
        with mock.patch.object(backend_init, "API_ERRORS", counter), \
            mock.patch.object(backend_init, "API_SUCCESS", counter), \
            mock.patch.object(backend_init, "DB_ERRORS", counter), \
            mock.patch.object(backend_init, "start_metrics_collection"), \
            mock.patch("builtins.print") as mock_print:
            backend_init.initialize_metrics()
        mock_print.assert_called()


class ModelStrTests(SimpleTestCase):
    def test_user_str(self):
        user = User(name="Tester", email="x@example.com", password="pw", role="ADMIN")
        self.assertEqual(str(user), "Tester")

    def test_batch_str(self):
        uploader = User(name="Owner", email="owner@example.com", password="pw", role="CURATOR")
        batch = CaseUploadBatch(filename="file.csv", uploaded_by=uploader)
        self.assertIn("file.csv", str(batch))

    def test_get_username_returns_email(self):
        user = User(name="Tester", email="x@example.com", password="pw", role="ADMIN")
        self.assertEqual(user.get_username(), "x@example.com")


class ClimateServiceTests(SimpleTestCase):
    def _make_service(self, cached=None, latest=None):
        cache_service = mock.Mock()
        cache_service.get.return_value = cached
        repository = mock.Mock()
        repository.get_latest_climate_data.return_value = latest or []
        service = ClimateService(repository=repository, cache_service=cache_service)
        return service, cache_service, repository

    def test_get_province_data_uses_cache(self):
        service, cache_service, _ = self._make_service(cached=[{"province": "A"}])
        data = service._get_province_climate_data("key", "humidity")
        self.assertEqual(data, [{"province": "A"}])
        cache_service.get.assert_called_with("key")

    def test_validation_error_returns_payload(self):
        latest = [SimpleNamespace(province="A", humidity=10.0)]
        service, cache_service, _ = self._make_service(cached=None, latest=latest)
        with mock.patch.object(service, "validate_humidity_data", return_value="bad"):
            data = service._get_province_climate_data("key", "humidity")
            self.assertEqual(data, {"error": "bad"})

    def test_normalize_province_name_variants(self):
        service, _, _ = self._make_service()
        self.assertIsNone(service._normalize_province_name(None))
        self.assertIsNone(service._normalize_province_name("   "))
        normalized = service._normalize_province_name("Provinsi DKI Jakarta")
        self.assertEqual(normalized, "DKI Jakarta")
        first = next(iter(PROVINCE_TO_CODE.keys()))
        self.assertEqual(service._normalize_province_name(first), first)
        self.assertEqual(service._normalize_province_name("Aceh"), "Aceh")

    def test_normalize_province_name_falls_back_to_known_code(self):
        service, _, _ = self._make_service()
        target = next(iter(PROVINCE_TO_CODE.keys()))
        with mock.patch.dict("pt_backend.services.PROVINCE_ALIASES", {}, clear=True):
            self.assertEqual(service._normalize_province_name(target), target)

    def test_validate_province_detects_duplicates(self):
        service, _, _ = self._make_service()
        seen = set()
        province, error = service._validate_province("Provinsi DKI Jakarta", seen)
        self.assertIsNone(error)
        province, error = service._validate_province("Provinsi DKI Jakarta", seen)
        self.assertIn("Duplicate", error)

    def test_validate_value_errors_on_strings(self):
        service, _, _ = self._make_service()
        self.assertEqual(service._validate_value("bad"), CLIMATE_ERROR_INVALID_VALUE)

    def test_validate_none_data_fallback(self):
        service, _, _ = self._make_service()
        error = service.validate_None_data([])
        self.assertEqual(error, "No climate data available.")

    def test_get_province_climate_data_handles_exception(self):
        repository = mock.Mock()
        repository.get_latest_climate_data.side_effect = RuntimeError("boom")
        service = ClimateService(repository=repository, cache_service=mock.Mock())
        result = service._get_province_climate_data("key", "humidity")
        self.assertIn("error", result)


class AverageSeverityTests(SimpleTestCase):
    def test_compute_assigns_all_statuses(self):
        case_service = mock.Mock()
        case_service.get_status_and_province.return_value = [
            {"status": "minimal", "location__province": "Aceh"},
            {"status": "biasa", "location__province": "Bali"},
            {"status": "bahaya", "location__province": "Jakarta"},
            {"status": "katastropik", "location__province": "Papua"},
            {"status": "bahaya", "location__province": "Papua"},
        ]
        analyzer = AverageSeverityByProvince(case_service)
        results = analyzer.compute()
        self.assertTrue(any(item["status"] == "katastropik" for item in results))


class AllCaseLocationsViewUtilityTests(SimpleTestCase):
    def setUp(self):
        self.view = AllCaseLocationsView()
        self.view.service = mock.Mock()
        self.view.filter_service = mock.Mock()

    def test_prepare_filter_payload_merges_time_params(self):
        self.view.filter_service.parse_time_params.return_value = {"start_date": "now"}
        payload = self.view._prepare_filter_payload({"city": "Jakarta"})
        self.assertIn("start_date", payload)

    def test_flatten_request_data_querydict(self):
        payload = QueryDict(mutable=True)
        payload.setlist("city", ["Jakarta", "Jakarta"])
        payload.setlist("province", ["Bali"])
        flattened = AllCaseLocationsView._flatten_request_data(payload)
        self.assertEqual(flattened["province"], "Bali")
        self.assertEqual(flattened["city"], ["Jakarta", "Jakarta"])

    def test_flatten_request_data_dict(self):
        data = {"city": "Bandung"}
        self.assertEqual(AllCaseLocationsView._flatten_request_data(data), data)

    def test_flatten_request_data_iterable(self):
        data = [("city", "Medan")]
        self.assertEqual(AllCaseLocationsView._flatten_request_data(data), {"city": "Medan"})


class FiltersViewUtilityTests(SimpleTestCase):
    def setUp(self):
        self.view = FiltersView()

    def _make_request(self, payload):
        return SimpleNamespace(data=payload)

    def test_add_locations_populates_fields(self):
        params = {}
        request = self._make_request({"locations": {"provinces": ["DKI"], "cities": ["Jakarta"]}})
        self.view._add_locations(request, params)
        self.assertEqual(params["provinces"], ["DKI"])
        self.assertEqual(params["cities"], ["Jakarta"])

    def test_add_locations_handles_missing_values(self):
        params = {}
        request = self._make_request({"locations": {"provinces": [], "cities": []}})
        self.view._add_locations(request, params)
        self.assertFalse(params)

    def test_add_locations_partial_payload(self):
        params = {}
        request = self._make_request({"locations": {"cities": ["Jakarta"]}})
        self.view._add_locations(request, params)
        self.assertIn("cities", params)
        self.assertNotIn("provinces", params)

    def test_add_batch_handles_dict_and_iterable(self):
        params = {}
        request = self._make_request({"batch": {"value": "123"}, "dataset": ["", "456"]})
        self.view._add_batch(request, params)
        self.assertEqual(params["batch"], "123")

        params = {}
        request = self._make_request({"dataset": ["", "456"]})
        self.view._add_batch(request, params)
        self.assertEqual(params["batch"], "456")


class WeightedSeverityViewTests(TestCase):
    def setUp(self):
        self.factory = APIRequestFactory()

    @override_settings(SECRET_API_KEYS=["test-key"])
    @mock.patch.object(WeightedSeverityAnalysisView, "authentication_classes", [])
    @mock.patch.object(WeightedSeverityAnalysisView, "permission_classes", [])
    def test_returns_404_when_no_data(self, *_):
        view = WeightedSeverityAnalysisView.as_view()
        request = self.factory.get("/api/province-weighted-severity/")
        with mock.patch("pt_backend.views.AverageSeverityByProvince.compute", return_value={}):
            response = view(request)
        self.assertEqual(response.status_code, 404)

    @override_settings(SECRET_API_KEYS=["test-key"])
    @mock.patch.object(WeightedSeverityAnalysisView, "authentication_classes", [])
    @mock.patch.object(WeightedSeverityAnalysisView, "permission_classes", [])
    def test_handles_exception(self, *_):
        view = WeightedSeverityAnalysisView.as_view()
        request = self.factory.get("/api/province-weighted-severity/")
        with mock.patch("pt_backend.views.AverageSeverityByProvince.compute", side_effect=RuntimeError("boom")):
            response = view(request)
        self.assertEqual(response.status_code, 500)


class AllCaseLocationsViewPostTests(SimpleTestCase):
    def setUp(self):
        self.factory = APIRequestFactory()

    def test_post_handles_generic_exception(self):
        request = self.factory.post("/cases", {"city": "Jakarta"}, format="json")
        with mock.patch("pt_backend.views.CaseFilterService") as mock_filter_cls, \
            mock.patch("pt_backend.views.AllCaseLocationsView._prepare_filter_payload", return_value={"city": "Jakarta"}), \
            mock.patch("pt_backend.views.API_ERRORS") as mock_errors:
            mock_filter_cls.return_value.filter_cases.side_effect = RuntimeError("boom")
            mock_errors.labels.return_value = mock.Mock()
            view = AllCaseLocationsView.as_view()
            response = view(request)
        self.assertEqual(response.status_code, 500)
        self.assertTrue(mock_filter_cls.return_value.filter_cases.called)
        mock_errors.labels.assert_called_with(error_type="case_filter_error")


class SeverityFilteringStatsViewTests(SimpleTestCase):
    def setUp(self):
        self.view = SeverityFilteringStatsView()
        self.view.cache_service = mock.Mock()
        self.factory = APIRequestFactory()
        self.auth_patch = mock.patch.object(SeverityFilteringStatsView, "authentication_classes", [])
        self.perm_patch = mock.patch.object(SeverityFilteringStatsView, "permission_classes", [])
        self.auth_patch.start()
        self.perm_patch.start()
        self.addCleanup(self.auth_patch.stop)
        self.addCleanup(self.perm_patch.stop)

    def test_generate_cache_key_error(self):
        with mock.patch.object(
            SeverityFilteringStatsView, "_normalize_cache_value", side_effect=RuntimeError("boom")
        ):
            with self.assertRaises(RuntimeError):
                self.view._generate_cache_key({"a": 1})
        self.assertIsNone(getattr(self.view, "_current_cache_key", None))

    def test_generate_cache_key_success(self):
        self.view.cache_service.get.return_value = None
        params = {"date": datetime(2024, 1, 1)}
        placeholder = self.view._generate_cache_key(params)
        self.assertIsNone(placeholder)
        self.assertIsNotNone(self.view._current_cache_key)

    def test_normalize_cache_value_handles_nested(self):
        value = {
            "ts": datetime(2024, 1, 1),
            "values": [{"k": 1}, {"k": 2}],
        }
        normalized = self.view._normalize_cache_value(value)
        self.assertIsInstance(normalized, tuple)

    def test_extract_filter_parameters_handles_batch_collections(self):
        data = {
            "diseases": ["flu"],
            "locations": {"provinces": [], "cities": []},
            "batch": {"id": "abc"},
            "dataset": ["", "def"],
        }
        params = self.view._extract_filter_parameters(data)
        self.assertEqual(params["batch"], "abc")

    def test_extract_filter_parameters_uses_dataset_list(self):
        data = {"locations": {}, "dataset": ["", "ghi"]}
        params = self.view._extract_filter_parameters(data)
        self.assertEqual(params["batch"], "ghi")

    def test_extract_filter_parameters_drops_empty_batch(self):
        data = {"locations": {}, "dataset": ["", ""]}
        params = self.view._extract_filter_parameters(data)
        self.assertIsNone(params["batch"])

    def test_extract_filter_parameters_handles_empty_string_batch(self):
        # datasetId is evaluated last in the chain so an empty string survives until the drop step
        data = {"locations": {}, "datasetId": ""}
        params = self.view._extract_filter_parameters(data)
        self.assertIsNone(params["batch"])

    def test_get_severity_service_reuses_existing_instance(self):
        existing_service = mock.Mock(name="existing_service")
        self.view._severity_service = existing_service
        # sanity check that a fresh call does not try to instantiate a new service
        self.view.severity_service_factory = mock.Mock(side_effect=AssertionError("factory should not run"))

        returned = self.view._get_severity_service()

        self.assertIs(returned, existing_service)
        self.view.severity_service_factory.assert_not_called()

    def test_post_returns_cached_payload(self):
        api_request = self.factory.post("/filters", {})
        mock_cache = mock.Mock()
        mock_cache.get.return_value = {"cached": True}
        with mock.patch("pt_backend.views.CacheService", return_value=mock_cache):
            view_callable = SeverityFilteringStatsView.as_view()
        with mock.patch.object(SeverityFilteringStatsView, "_extract_filter_parameters", return_value={}):
            response = view_callable(api_request)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data, {"cached": True})

    def test_post_raises_when_cache_key_missing(self):
        api_request = self.factory.post("/filters", {})
        with mock.patch.object(SeverityFilteringStatsView, "_extract_filter_parameters", return_value={}), \
            mock.patch.object(SeverityFilteringStatsView, "_generate_cache_key", return_value=None):
            view_callable = SeverityFilteringStatsView.as_view()
            with self.assertRaises(ValueError):
                view_callable(api_request)
