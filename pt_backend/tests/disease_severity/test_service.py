from django.test import TestCase
from pt_backend.services import DiseaseService
from unittest.mock import MagicMock, patch

class DiseaseServiceTestCase(TestCase):
    def setUp(self):
        self.mock_repository = MagicMock()
        self.service = DiseaseService(repository=self.mock_repository)
        
    def test_get_disease_severity_stats(self):
        """Test that service passes the repository result"""
        # Setup mock repository return value
        expected_result = [
            {
                "name": "Test Disease",
                "severity_counts": {
                    "hospitalisasi": 1,
                    "insiden": 2,
                    "mortalitas": 3
                },
                "total_cases": 6
            }
        ]
        self.mock_repository.get_disease_severity_stats.return_value = expected_result
        
        # Call the service method
        result = self.service.get_disease_severity_stats()
        
        # Assert repository method was called
        self.mock_repository.get_disease_severity_stats.assert_called_once()
        
        # Assert service returns repository result
        self.assertEqual(result, expected_result)
        
    def test_get_disease_severity_stats_with_default_repository(self):
        """Test that service works with default repository"""
        with patch('pt_backend.services.DiseaseRepository') as mock_repo_class:
            # Setup mock repository instance and class
            mock_repo_instance = MagicMock()
            mock_repo_class.return_value = mock_repo_instance
            
            expected_result = [{"name": "Test Disease"}]
            mock_repo_instance.get_disease_severity_stats.return_value = expected_result
            
            # Create service with default repository
            service = DiseaseService()
            result = service.get_disease_severity_stats()
            
            # Assert default repository was used
            mock_repo_class.assert_called_once()
            mock_repo_instance.get_disease_severity_stats.assert_called_once()
            
            # Assert result is as expected
            self.assertEqual(result, expected_result)