from unittest import TestCase
from unittest.mock import Mock, patch
from django.db.models import Q
from .filters import (
    DiseaseFilter,
    LocationFilter,
    AlertnessFilter,
    PortalFilter,
    DateRangeFilter
)

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