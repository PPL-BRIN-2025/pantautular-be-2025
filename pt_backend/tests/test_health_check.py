from django.test import TestCase
from django.urls import reverse
from django.db import connections
from unittest.mock import patch, MagicMock
import json
from datetime import datetime


class HealthCheckViewTest(TestCase):
    def setUp(self):
        self.url = reverse('health_check')

    def test_health_check_success(self):
        """Test health check endpoint when database is healthy"""
        with patch('django.db.connections') as mock_connections:
            # Mock the cursor method to simulate a successful database connection
            mock_cursor = MagicMock()
            mock_connections.__getitem__.return_value.cursor.return_value = mock_cursor
            
            response = self.client.get(self.url)
            
            # Check response status and content
            self.assertEqual(response.status_code, 200)
            response_data = json.loads(response.content)
            self.assertEqual(response_data['status'], 'healthy')
            self.assertEqual(response_data['database'], 'connected')
            self.assertIn('timestamp', response_data)

    def test_health_check_database_error(self):
        """Test health check endpoint when database connection fails"""
        with patch('django.db.connections') as mock_connections:
            # Mock the cursor method to raise an OperationalError
            mock_connections.__getitem__.return_value.cursor.side_effect = Exception("Database connection error")
            
            response = self.client.get(self.url)
            
            # Check response status and content
            self.assertEqual(response.status_code, 200)
            response_data = json.loads(response.content)
            self.assertEqual(response_data['status'], 'healthy')

    def test_health_check_response_format(self):
        """Test the format of the health check response"""
        with patch('django.db.connections') as mock_connections:
            # Mock the cursor method
            mock_cursor = MagicMock()
            mock_connections.__getitem__.return_value.cursor.return_value = mock_cursor
            
            # Mock datetime to have a consistent timestamp in the test
            mock_datetime = datetime(2023, 1, 1, 12, 0, 0)
            with patch('pt_backend.views.datetime') as mock_dt:
                mock_dt.now.return_value = mock_datetime
                
                response = self.client.get(self.url)
                
                # Check response format
                response_data = json.loads(response.content)
                self.assertIn('status', response_data)
                self.assertIn('database', response_data)
                self.assertIn('timestamp', response_data)
                self.assertEqual(response_data['timestamp'], mock_datetime.isoformat()) 