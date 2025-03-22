from django.test import TestCase
from django.db.models import Q
from unittest.mock import Mock, patch
from typing import Dict, Optional, Any
from pt_backend.filter.strategy import FilterStrategy
from pt_backend.filter.disease_filter import DiseaseFilter
from pt_backend.filter.location_filter import LocationFilter
from pt_backend.filter.alertness_filter import AlertnessFilter
from pt_backend.filter.portal_filter import PortalFilter
from pt_backend.filter.date_range_filter import DateRangeFilter
from pt_backend.filter.service import CaseFilterService
from pt_backend.models import Case, Disease, Location, News
from datetime import timezone
from datetime import datetime
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
        expected_q = Q(location__name__in=['Jakarta', 'Bandung'])
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

    def test_date_range_filter_with_invalid_format(self):
        data = {'start_date': 'invalid-date', 'end_date': 'invalid-date'}
        result = self.date_range_filter.apply(data)
        self.assertEqual(str(result), str(Q()))

    def test_date_range_filter_with_empty_data(self):
        data = {}
        result = self.date_range_filter.apply(data)
        self.assertEqual(str(result), str(Q()))



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
        
        self.patcher = patch('pt_backend.filter.service.Case')
        self.mock_case = self.patcher.start()
        
        self.mock_queryset = Mock()
        self.mock_case.objects.filter.return_value = self.mock_queryset
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
            'level_of_alertness': 3,
            'portals': ['BBC'],
            'date_range': {
                'start_date': '2024-01-01',
                'end_date': '2024-12-31'
            }
        }

        result = self.filter_service.filter_cases(data)

        self.mock_case.objects.filter.assert_called_once()
        self.mock_queryset.values.assert_called_once_with(
            'id', 'location__longitude', 'location__latitude', 'city'
        )
        self.mock_queryset.distinct.assert_called_once()
        self.assertEqual(result, ['mocked_result'])

    def test_filter_cases_empty_data(self):
        data = {}
        result = self.filter_service.filter_cases(data)

        self.mock_case.objects.filter.assert_called_once()
        self.mock_queryset.values.assert_called_once_with(
            'id', 'location__longitude', 'location__latitude', 'city'
        )
        self.mock_queryset.distinct.assert_called_once()
        self.assertEqual(result, ['mocked_result'])

    def test_filter_cases_partial_filters(self):
        data = {
            'diseases': ['COVID-19'],
            'locations': ['Jakarta']
        }

        result = self.filter_service.filter_cases(data)

        self.mock_case.objects.filter.assert_called_once()
        self.mock_queryset.values.assert_called_once_with(
            'id', 'location__longitude', 'location__latitude', 'city'
        )
        self.mock_queryset.distinct.assert_called_once()
        self.assertEqual(result, ['mocked_result'])

    def test_filter_cases_invalid_filter_data(self):
        data = {
            'diseases': [], 
            'locations': None,  
            'level_of_alertness': 'invalid' 
        }

        result = self.filter_service.filter_cases(data)

        self.mock_case.objects.filter.assert_called_once()
        self.mock_queryset.values.assert_called_once_with(
            'id', 'location__longitude', 'location__latitude', 'city'
        )
        self.mock_queryset.distinct.assert_called_once()
        self.assertEqual(result, ['mocked_result'])

    def test_filter_cases_with_none_returning_filter(self):
        mock_filter = Mock()
        mock_filter.apply.return_value = None
        
        original_filters = self.filter_service.filters
        self.filter_service.filters = [mock_filter] + original_filters[1:]
        
        data = {'some_key': 'some_value'}
        result = self.filter_service.filter_cases(data)
        
        mock_filter.apply.assert_called_once_with(data)
        
        self.mock_case.objects.filter.assert_called_once()
        self.mock_queryset.values.assert_called_once_with(
            'id', 'location__longitude', 'location__latitude', 'city'
        )
        self.mock_queryset.distinct.assert_called_once()
        self.assertEqual(result, ['mocked_result'])
        
        self.filter_service.filters = original_filters