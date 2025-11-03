from django.test import TestCase
from django.db.models import Q
from unittest.mock import Mock, patch
from typing import Dict, Optional, Any
from pt_backend.filter.strategy import FilterStrategy
from pt_backend.filter.disease_filter import DiseaseFilter
from pt_backend.filter.location_filter import LocationFilter
from pt_backend.filter.alertness_filter import AlertnessFilter
from pt_backend.filter.portal_filter import PortalFilter
from pt_backend.filter.date_range_filter import DateRangeFilter, TimeWindowError
from pt_backend.filter.service import CaseFilterService, CaseFilterValidationError
from pt_backend.models import Case, Disease, Location, News
from datetime import datetime, timedelta
import pytz
import uuid
from django.utils.dateparse import parse_datetime


class FilterTestCase(TestCase):
    def setUp(self):
        self.disease_filter = DiseaseFilter()
        self.location_filter = LocationFilter()
        self.alertness_filter = AlertnessFilter()
        self.portal_filter = PortalFilter()
        self.date_range_filter = DateRangeFilter()

    def test_disease_filter_with_valid_data(self):
        data = {'diseases': ['COVID-19', 'SARS']}
        expected_q = Q(disease__name__in=['COVID-19', 'SARS'])
        result = self.disease_filter.apply(data)
        self.assertEqual(str(result), str(expected_q))

    def test_disease_filter_with_empty_data(self):
        data = {}
        result = self.disease_filter.apply(data)
        self.assertIsNone(result)

    def test_location_filter_with_valid_data(self):
        data = {'locations': ['Jakarta', 'Bandung']}
        expected_q = (
            Q(location__city__in=['Jakarta', 'Bandung']) |
            Q(city__in=['Jakarta', 'Bandung']) |
            Q(location__province__in=['Jakarta', 'Bandung'])
        )
        result = self.location_filter.apply(data)
        self.assertEqual(str(result), str(expected_q))

    def test_location_filter_with_nested_location_dict(self):
        data = {'locations': {'provinces': ['DKI Jakarta'], 'cities': ['Jakarta']}}
        expected_q = (
            Q(location__city__in=['Jakarta']) |
            Q(city__in=['Jakarta']) |
            Q(location__province__in=['DKI Jakarta'])
        )
        result = self.location_filter.apply(data)
        self.assertEqual(str(result), str(expected_q))

    def test_location_filter_with_value_label_entries(self):
        data = {'locations': [{'value': 'Jakarta', 'label': 'DKI Jakarta'}]}
        expected_q = (
            Q(location__city__in=['Jakarta']) |
            Q(city__in=['Jakarta']) |
            Q(location__province__in=['Jakarta'])
        )
        result = self.location_filter.apply(data)
        self.assertEqual(str(result), str(expected_q))

    def test_location_filter_with_empty_data(self):
        data = {}
        result = self.location_filter.apply(data)
        self.assertIsNone(result)

    def test_alertness_filter_with_valid_data(self):
        data = {'level_of_alertness': 'HIGH'}
        expected_q = Q(disease__level_of_alertness='HIGH')
        result = self.alertness_filter.apply(data)
        self.assertEqual(str(result), str(expected_q))

    def test_alertness_filter_with_empty_data(self):
        data = {}
        result = self.alertness_filter.apply(data)
        self.assertIsNone(result)

    def test_portal_filter_with_valid_data(self):
        data = {'portals': ['BBC', 'CNN']}
        expected_q = Q(news__portal__in=['BBC', 'CNN'])
        result = self.portal_filter.apply(data)
        self.assertEqual(str(result), str(expected_q))

    def test_portal_filter_with_empty_data(self):
        data = {}
        result = self.portal_filter.apply(data)
        self.assertIsNone(result)

    def test_date_range_filter_with_valid_data(self):
        data = {
            'start_date': '2024-01-01T00:00:00Z',
            'end_date': '2024-12-31T23:59:59Z'
        }
        utc = pytz.UTC
        expected_q = Q(news__date_published__range=[
            datetime(2024, 1, 1, 0, 0, 0, tzinfo=utc),
            datetime(2024, 12, 31, 23, 59, 59, tzinfo=utc)
        ]) & Q(news__isnull=False)
        
        result = self.date_range_filter.apply(data)
        self.assertEqual(str(result), str(expected_q))

    def test_date_range_filter_with_missing_dates(self):
        data = {'start_date': '2024-01-01T00:00:00Z'}  # Only start_date
        result = self.date_range_filter.apply(data)
        expected_q = Q(news__date_published__gte=datetime(2024, 1, 1, 0, 0, tzinfo=pytz.UTC)) & Q(news__isnull=False)
        self.assertEqual(str(result), str(expected_q))
        
    def test_date_range_filter_with_only_end_date(self):
        data = {'end_date': '2024-12-31T23:59:59Z'}  # Only end_date
        result = self.date_range_filter.apply(data)
        expected_q = Q(news__date_published__lte=datetime(2024, 12, 31, 23, 59, 59, tzinfo=pytz.UTC)) & Q(news__isnull=False)
        self.assertEqual(str(result), str(expected_q))

    def test_date_range_filter_with_timezone_normalization(self):
        data = {
            'start_date': '2024-01-01T00:00:00',
            'timezone': 'Asia/Jakarta',
        }
        result = self.date_range_filter.apply(data)
        localized = pytz.timezone('Asia/Jakarta').localize(datetime(2024, 1, 1, 0, 0))
        expected_start = localized.astimezone(pytz.UTC)
        expected_q = Q(news__date_published__gte=expected_start) & Q(news__isnull=False)
        self.assertEqual(str(result), str(expected_q))

    def test_date_range_filter_with_invalid_format(self):
        data = {'start_date': 'invalid-date', 'end_date': 'invalid-date'}
        with self.assertRaises(TimeWindowError):
            self.date_range_filter.apply(data)

    def test_date_range_filter_with_empty_data(self):
        data = {}
        result = self.date_range_filter.apply(data)
        self.assertEqual(str(result), str(Q()))

    def test_build_time_window_helper_with_null_guard(self):
        data = {'start_date': '2024-01-01T00:00:00Z'}
        result = DateRangeFilter.build_time_window(
            field="news__date_published",
            data=data,
            null_guard_field="news",
        )
        expected_q = Q(news__date_published__gte=datetime(2024, 1, 1, 0, 0, tzinfo=pytz.UTC)) & Q(news__isnull=False)
        self.assertEqual(str(result), str(expected_q))

    def test_build_time_window_helper_without_dates_returns_none(self):
        result = DateRangeFilter.build_time_window(field="created_at", data={})
        self.assertIsNone(result)

    def test_resolve_time_window_with_period_string(self):
        fixed_now = datetime(2024, 1, 8, 12, 0, tzinfo=pytz.UTC)
        data = {'period': '7d'}
        start, end = DateRangeFilter.resolve_time_window(data, now=fixed_now)
        self.assertEqual(start, (fixed_now - timedelta(days=7)))
        self.assertEqual(end, fixed_now)

    def test_resolve_time_window_with_period_and_timezone(self):
        fixed_now = datetime(2024, 1, 8, 12, 0, tzinfo=pytz.UTC)
        data = {'period': '24h', 'timezone': 'Asia/Jakarta'}
        start, end = DateRangeFilter.resolve_time_window(data, now=fixed_now)
        self.assertEqual(end, fixed_now)
        self.assertEqual(start, fixed_now - timedelta(hours=24))

    def test_resolve_time_window_with_invalid_timezone_falls_back_to_utc(self):
        data = {'start_date': '2024-01-01T00:00:00', 'timezone': 'Invalid/TZ'}
        start, _ = DateRangeFilter.resolve_time_window(data)
        self.assertEqual(start, datetime(2024, 1, 1, 0, 0, tzinfo=pytz.UTC))

    def test_resolve_time_window_with_period_dict(self):
        fixed_now = datetime(2024, 1, 8, 12, 0, tzinfo=pytz.UTC)
        data = {'period': {'value': 2, 'unit': 'weeks'}}
        start, end = DateRangeFilter.resolve_time_window(data, now=fixed_now)
        self.assertEqual(end, fixed_now)
        self.assertEqual(start, fixed_now - timedelta(weeks=2))



class TestFilterStrategy(TestCase):
    def setUp(self):
        class ConcreteFilter:
            @property
            def field_name(self) -> str:
                return "test_field"
            
            def build_query(self, value: any) -> Q:
                return Q(test_field=value)
            
            def should_apply(self, data: dict) -> bool:
                return super().should_apply(data)
                
            def apply(self, data: dict) -> Q:
                return super().apply(data)
        
        self.filter = type('TestFilter', (ConcreteFilter, FilterStrategy), {})()

    def test_field_name_property(self):
        self.assertEqual(self.filter.field_name, "test_field")

    def test_should_apply_with_data(self):
        data = {"test_field": "value"}
        self.assertTrue(self.filter.should_apply(data))

    def test_should_apply_without_data(self):
        data = {"other_field": "value"}
        self.assertFalse(self.filter.should_apply(data))

    def test_should_apply_with_empty_value(self):
        data = {"test_field": ""}
        self.assertFalse(self.filter.should_apply(data))

    def test_apply_with_valid_data(self):
        data = {"test_field": "value"}
        result = self.filter.apply(data)
        self.assertIsInstance(result, Q)
        self.assertEqual(str(result), str(Q(test_field="value")))

    def test_apply_with_invalid_data(self):
        data = {"other_field": "value"}
        result = self.filter.apply(data)
        self.assertIsNone(result)


class CaseFilterServiceTest(TestCase):
    def setUp(self):
        self.filter_service = CaseFilterService()
        
        # Mock the Case model and its methods
        self.patcher = patch('pt_backend.filter.service.Case')
        self.mock_case = self.patcher.start()
        
        # Create a mock queryset chain
        self.mock_queryset = Mock()
        self.mock_case.objects.select_related.return_value = self.mock_queryset
        self.mock_queryset.prefetch_related.return_value = self.mock_queryset
        self.mock_queryset.filter.return_value = self.mock_queryset
        self.mock_queryset.values.return_value = self.mock_queryset
        self.mock_queryset.distinct.return_value = ['mocked_result']

    def tearDown(self):
        self.patcher.stop()

    def test_filter_cases_initialization(self):
        self.assertEqual(len(self.filter_service.filters), 5)
        self.assertIsInstance(self.filter_service.filters[0], DiseaseFilter)
        self.assertIsInstance(self.filter_service.filters[1], LocationFilter)
        self.assertIsInstance(self.filter_service.filters[2], AlertnessFilter)
        self.assertIsInstance(self.filter_service.filters[3], PortalFilter)
        self.assertIsInstance(self.filter_service.filters[4], DateRangeFilter)

    def test_filter_cases_with_all_filters(self):
        data = {
            'diseases': ['COVID-19'],
            'locations': ['Jakarta'],
            'level_of_alertness': 'HIGH',
            'portals': ['BBC'],
            'start_date': '2024-01-01T00:00:00Z',
            'end_date': '2024-12-31T23:59:59Z'
        }

        result = self.filter_service.filter_cases(data)

        self.mock_case.objects.select_related.assert_called_once_with('location', 'disease')
        self.mock_queryset.prefetch_related.assert_called_once_with('news_set')
        self.assertEqual(self.mock_queryset.filter.call_count, 2)
        self.mock_queryset.values.assert_called_once_with(
            'id', 'location__longitude', 'location__latitude', 'city', 'location__province', 'severity'
        )
        self.mock_queryset.distinct.assert_called_once()
        self.assertEqual(result, ['mocked_result'])

    def test_filter_cases_empty_data(self):
        data = {}
        result = self.filter_service.filter_cases(data)

        self.mock_case.objects.select_related.assert_called_once_with('location', 'disease')
        self.mock_queryset.prefetch_related.assert_called_once_with('news_set')
        self.mock_queryset.filter.assert_not_called()
        self.mock_queryset.values.assert_called_once_with(
            'id', 'location__longitude', 'location__latitude', 'city', 'location__province', 'severity'
        )
        self.mock_queryset.distinct.assert_called_once()
        self.assertEqual(result, ['mocked_result'])

    def test_filter_cases_partial_filters(self):
        data = {
            'diseases': ['COVID-19'],
            'locations': ['Jakarta']
        }

        result = self.filter_service.filter_cases(data)

        self.mock_case.objects.select_related.assert_called_once_with('location', 'disease')
        self.mock_queryset.prefetch_related.assert_called_once_with('news_set')
        self.mock_queryset.filter.assert_called_once()
        self.mock_queryset.values.assert_called_once_with(
            'id', 'location__longitude', 'location__latitude', 'city', 'location__province', 'severity'
        )
        self.mock_queryset.distinct.assert_called_once()
        self.assertEqual(result, ['mocked_result'])

    def test_filter_cases_invalid_filter_data(self):
        data = {
            'diseases': [], 
            'locations': None,  
            'level_of_alertness': 'invalid',
            'portals': [],
            'start_date': 'invalid-date'
        }

        with self.assertRaises(CaseFilterValidationError):
            self.filter_service.filter_cases(data)

        self.mock_case.objects.select_related.assert_called_once_with('location', 'disease')
        self.mock_queryset.prefetch_related.assert_called_once_with('news_set')
        self.mock_queryset.filter.assert_not_called()
        self.mock_queryset.values.assert_not_called()
        self.mock_queryset.distinct.assert_not_called()

    def test_time_window_helper_exposure_matches_date_range_filter(self):
        data = {
            'start_date': '2024-01-01T00:00:00Z',
            'end_date': '2024-01-02T23:59:59Z',
        }
        result = CaseFilterService.time_window(
            data,
            field="news__date_published",
            null_guard_field="news",
        )
        expected_q = (
            Q(news__date_published__range=[
                datetime(2024, 1, 1, 0, 0, tzinfo=pytz.UTC),
                datetime(2024, 1, 2, 23, 59, 59, tzinfo=pytz.UTC),
            ])
            & Q(news__isnull=False)
        )
        self.assertEqual(str(result), str(expected_q))

    def test_time_window_helper_returns_none_without_bounds(self):
        result = CaseFilterService.time_window(data={}, field="news__date_published")
        self.assertIsNone(result)

    def test_get_time_window_uses_cache(self):
        service = CaseFilterService()
        data = {'start_date': '2024-01-01T00:00:00Z'}
        start = datetime(2024, 1, 1, tzinfo=pytz.UTC)
        with patch.object(
            CaseFilterService,
            'resolve_time_window',
            return_value=(start, None)
        ) as mock_resolve:
            first = service._get_time_window_q(data)
            second = service._get_time_window_q(data)
            self.assertEqual(mock_resolve.call_count, 1)
            self.assertIs(second, first)

    def test_time_window_helper_with_period(self):
        fixed_now = datetime(2024, 1, 8, 12, 0, tzinfo=pytz.UTC)
        data = {'period': '1d'}
        result = CaseFilterService.time_window(
            data,
            field="news__date_published",
            null_guard_field="news",
            now=fixed_now,
        )
        expected_q = (
            Q(
                news__date_published__range=[
                    fixed_now - timedelta(days=1),
                    fixed_now,
                ]
            )
            & Q(news__isnull=False)
        )
        self.assertEqual(str(result), str(expected_q))

    def test_resolve_time_window_proxy(self):
        fixed_now = datetime(2024, 1, 8, 12, 0, tzinfo=pytz.UTC)
        data = {'period': '1d'}
        start, end = CaseFilterService.resolve_time_window(data, now=fixed_now)
        self.assertEqual(start, fixed_now - timedelta(days=1))
        self.assertEqual(end, fixed_now)

    def test_parse_time_params_with_period(self):
        fixed_now = datetime(2024, 1, 8, 12, 0, tzinfo=pytz.UTC)
        data = {'period': '1d'}
        result = CaseFilterService.parse_time_params(data, now=fixed_now)
        self.assertEqual(
            result['start_date'],
            (fixed_now - timedelta(days=1)).isoformat()
        )
        self.assertEqual(result['end_date'], fixed_now.isoformat())
        self.assertEqual(result['period'], '1d')

    def test_parse_time_range_as_tuple(self):
        data = {'start_date': '2024-01-01T00:00:00', 'timezone': 'Asia/Jakarta'}
        start, end = CaseFilterService.parse_time_range(data, return_type="tuple")
        expected_start = pytz.timezone('Asia/Jakarta').localize(datetime(2024, 1, 1)).astimezone(pytz.UTC)
        self.assertEqual(start, expected_start)
        self.assertIsNone(end)

    def test_parse_time_range_invalid_start_raises(self):
        with self.assertRaises(CaseFilterValidationError) as ctx:
            CaseFilterService.parse_time_range({'start_date': 'invalid-date'}, return_type="dict")
        payload = ctx.exception.as_payload()
        self.assertEqual(payload['error']['code'], 'invalid_time_window')
        self.assertIn('start_date', payload['error'].get('fields', {}))

    def test_time_window_invalid_period_raises(self):
        with self.assertRaises(CaseFilterValidationError) as ctx:
            CaseFilterService.time_window({'period': 'bad-period'}, field='news__date_published')
        payload = ctx.exception.as_payload()
        self.assertEqual(payload['error']['code'], 'invalid_time_window')
        self.assertIn('period', payload['error'].get('fields', {}))

    def test_filter_cases_with_none_returning_filter(self):
        mock_filter = Mock()
        mock_filter.apply.return_value = None
        mock_filter.field_name = "test_field"
        
        original_filters = self.filter_service.filters
        self.filter_service.filters = [mock_filter] + original_filters[1:]
        
        data = {'test_field': 'some_value'}
        
        result = self.filter_service.filter_cases(data)
        
        mock_filter.apply.assert_called_once_with(data)

        self.mock_case.objects.select_related.assert_called_once_with('location', 'disease')
        self.mock_queryset.prefetch_related.assert_called_once_with('news_set')
        self.mock_queryset.filter.assert_not_called()
        self.mock_queryset.values.assert_called_once_with(
            'id', 'location__longitude', 'location__latitude', 'city', 'location__province', 'severity'
        )
        self.mock_queryset.distinct.assert_called_once()
        self.assertEqual(result, ['mocked_result'])
        
        self.filter_service.filters = original_filters

