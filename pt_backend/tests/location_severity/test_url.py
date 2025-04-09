from django.test import TestCase
from django.urls import reverse, resolve
from pt_backend.views import LocationSeverityStatsView, CitySeverityStatsView

class URLsTestCase(TestCase):
    def test_location_severity_stats_url(self):
        """Test the location severity stats URL works correctly"""
        url = reverse('province-severity-stats')
        self.assertEqual(url, '/api/locations/province/severity-stats/')
        
        resolver = resolve('/api/locations/province/severity-stats/')
        self.assertEqual(resolver.func.view_class, LocationSeverityStatsView)
    
    def test_city_severity_stats_url(self):
        """Test the city severity stats URL works correctly"""
        url = reverse('city-severity-stats')
        self.assertEqual(url, '/api/locations/city/severity-stats/')
        
        resolver = resolve('/api/locations/city/severity-stats/')
        self.assertEqual(resolver.func.view_class, CitySeverityStatsView)