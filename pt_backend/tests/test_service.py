import unittest
from unittest.mock import patch, MagicMock
from django.test import TestCase
from pt_backend.services import NewsService

class TestNewsService(TestCase):
    def setUp(self):
        self.news_service = NewsService()
        
    @patch('pt_backend.services.NewsRepository')
    def test_get_severities_dates_happy_case(self, mock_repository):
        # Arrange
        mock_repo_instance = MagicMock()
        mock_repository.return_value = mock_repo_instance
        
        expected_data = {
            "hospitalisasi": [
                {"date": "2023-06-01", "count": 5},
                {"date": "2023-06-02", "count": 8}
            ],
            "mortalitas": [
                {"date": "2023-06-01", "count": 2}
            ]
        }
        
        mock_repo_instance.get_all_severities_dates.return_value = expected_data
        
        # Act
        result = self.news_service.get_severities_dates()
        
        # Assert
        mock_repo_instance.get_all_severities_dates.assert_called_once()
        self.assertEqual(result, expected_data)
    
    @patch('pt_backend.services.NewsRepository')
    def test_get_severities_dates_error_case(self, mock_repository):
        # Arrange
        mock_repo_instance = MagicMock()
        mock_repository.return_value = mock_repo_instance
        
        expected_error = {"error": "Database error"}
        mock_repo_instance.get_all_severities_dates.return_value = expected_error
        
        # Act
        result = self.news_service.get_severities_dates()
        
        # Assert
        mock_repo_instance.get_all_severities_dates.assert_called_once()
        self.assertEqual(result, expected_error)
        self.assertIn("error", result)
    
    @patch('pt_backend.services.NewsRepository')
    def test_get_severities_dates_empty_case(self, mock_repository):
        # Arrange
        mock_repo_instance = MagicMock()
        mock_repository.return_value = mock_repo_instance
        
        # Empty result but still with severity keys
        expected_empty_data = {
            "hospitalisasi": [],
            "mortalitas": []
        }
        
        mock_repo_instance.get_all_severities_dates.return_value = expected_empty_data
        
        # Act
        result = self.news_service.get_severities_dates()
        
        # Assert
        mock_repo_instance.get_all_severities_dates.assert_called_once()
        self.assertEqual(result, expected_empty_data)
        self.assertEqual(len(result["hospitalisasi"]), 0)
        self.assertEqual(len(result["mortalitas"]), 0)

    @patch('pt_backend.services.NewsRepository')
    def test_get_severities_dates_no_severities_case(self, mock_repository):
        # Arrange
        mock_repo_instance = MagicMock()
        mock_repository.return_value = mock_repo_instance
        
        # Completely empty result - edge case
        expected_empty_data = {}
        
        mock_repo_instance.get_all_severities_dates.return_value = expected_empty_data
        
        # Act
        result = self.news_service.get_severities_dates()
        
        # Assert
        mock_repo_instance.get_all_severities_dates.assert_called_once()
        self.assertEqual(result, expected_empty_data)
        self.assertEqual(len(result), 0)
