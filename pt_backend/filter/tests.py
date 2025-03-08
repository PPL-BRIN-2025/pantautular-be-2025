import unittest
from unittest.mock import Mock, patch
from django.db.models import Q
from typing import Dict, Optional, Any
from .filters import (
    DiseaseFilter,
    LocationFilter,
    AlertnessFilter,
    PortalFilter,
    DateRangeFilter
)
from .service import CaseFilterService
from .strategy import FilterStrategy

class FilterTestCase(unittest.TestCase):
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
            'date_range': {
                'start_date': '2024-01-01',
                'end_date': '2024-12-31'
            }
        }
        expected_q = Q(date_published__range=['2024-01-01', '2024-12-31'])
        result = self.date_range_filter.apply(data)
        self.assertEqual(str(result), str(expected_q))

    def test_date_range_filter_with_empty_data(self):
        data = {}
        result = self.date_range_filter.apply(data)
        self.assertIsNone(result)

    def test_date_range_filter_with_partial_data(self):
        data = {'date_range': {'start_date': '2024-01-01'}}
        result = self.date_range_filter.apply(data)
        self.assertIsNone(result)



class TestFilterStrategy(unittest.TestCase):
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


