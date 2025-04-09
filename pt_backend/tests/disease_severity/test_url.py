from django.test import TestCase
from django.urls import reverse, resolve
from pt_backend.views import DiseaseSeverityStatsView

class URLsTestCase(TestCase):
    def test_disease_severity_stats_url(self):
        """Test the disease severity stats URL works correctly"""
        url = reverse('disease-severity-stats')
        self.assertEqual(url, '/api/diseases/severity-stats/')
        
        resolver = resolve('/api/diseases/severity-stats/')
        self.assertEqual(resolver.func.view_class, DiseaseSeverityStatsView)