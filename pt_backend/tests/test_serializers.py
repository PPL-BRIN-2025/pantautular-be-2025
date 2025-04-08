from django.test import TestCase
from pt_backend.serializers import MonthlyCountSerializer, SeverityCountSerializer

class MonthlyCountSerializerTestCase(TestCase):
    def test_valid_data(self):
        """Test serializer with valid data (happy case)"""
        data = {
            'year': 2023,
            'month': 6,
            'count': 42
        }
        serializer = MonthlyCountSerializer(data=data)
        self.assertTrue(serializer.is_valid())
        self.assertEqual(serializer.data['year'], 2023)
        self.assertEqual(serializer.data['month'], 6)
        self.assertEqual(serializer.data['count'], 42)
    
    def test_invalid_types(self):
        """Test serializer with invalid data types (unhappy case)"""
        # Invalid year (string)
        data = {
            'year': 'two thousand',
            'month': 6,
            'count': 42
        }
        serializer = MonthlyCountSerializer(data=data)
        self.assertFalse(serializer.is_valid())
        self.assertIn('year', serializer.errors)
        
        # Invalid month (string)
        data = {
            'year': 2023,
            'month': 'June',
            'count': 42
        }
        serializer = MonthlyCountSerializer(data=data)
        self.assertFalse(serializer.is_valid())
        self.assertIn('month', serializer.errors)
        
        # Invalid count (string)
        data = {
            'year': 2023,
            'month': 6,
            'count': 'forty-two'
        }
        serializer = MonthlyCountSerializer(data=data)
        self.assertFalse(serializer.is_valid())
        self.assertIn('count', serializer.errors)
    
    def test_missing_fields(self):
        """Test serializer with missing fields (unhappy case)"""
        # Missing year
        data = {
            'month': 6,
            'count': 42
        }
        serializer = MonthlyCountSerializer(data=data)
        self.assertFalse(serializer.is_valid())
        self.assertIn('year', serializer.errors)
        
        # Missing month
        data = {
            'year': 2023,
            'count': 42
        }
        serializer = MonthlyCountSerializer(data=data)
        self.assertFalse(serializer.is_valid())
        self.assertIn('month', serializer.errors)
        
        # Missing count
        data = {
            'year': 2023,
            'month': 6
        }
        serializer = MonthlyCountSerializer(data=data)
        self.assertFalse(serializer.is_valid())
        self.assertIn('count', serializer.errors)
    
    def test_edge_cases(self):
        """Test serializer with edge case values"""
        # Minimum valid month
        data = {
            'year': 2023,
            'month': 1,
            'count': 42
        }
        serializer = MonthlyCountSerializer(data=data)
        self.assertTrue(serializer.is_valid())
        
        # Maximum valid month
        data = {
            'year': 2023,
            'month': 12,
            'count': 42
        }
        serializer = MonthlyCountSerializer(data=data)
        self.assertTrue(serializer.is_valid())
        
        # Zero count
        data = {
            'year': 2023,
            'month': 6,
            'count': 0
        }
        serializer = MonthlyCountSerializer(data=data)
        self.assertTrue(serializer.is_valid())
        
        # Negative count
        data = {
            'year': 2023,
            'month': 6,
            'count': -5
        }
        serializer = MonthlyCountSerializer(data=data)
        self.assertTrue(serializer.is_valid())
        
        # Very large numbers
        data = {
            'year': 9999,
            'month': 12,
            'count': 1000000
        }
        serializer = MonthlyCountSerializer(data=data)
        self.assertTrue(serializer.is_valid())


class SeverityCountSerializerTestCase(TestCase):
    def test_valid_data(self):
        """Test serializer with valid data (happy case)"""
        input_data = {
            'LOW': [
                {'year': 2023, 'month': 5, 'count': 10},
                {'year': 2023, 'month': 6, 'count': 15}
            ],
            'MEDIUM': [
                {'year': 2023, 'month': 5, 'count': 5},
                {'year': 2023, 'month': 6, 'count': 8}
            ],
            'HIGH': [
                {'year': 2023, 'month': 5, 'count': 2},
                {'year': 2023, 'month': 6, 'count': 3}
            ]
        }
        
        serializer = SeverityCountSerializer(input_data)
        result = serializer.data
        
        # Check that all keys are present
        self.assertIn('LOW', result)
        self.assertIn('MEDIUM', result)
        self.assertIn('HIGH', result)
        
        # Check that each severity key has the correct number of items
        self.assertEqual(len(result['LOW']), 2)
        self.assertEqual(len(result['MEDIUM']), 2)
        self.assertEqual(len(result['HIGH']), 2)
        
        # Check specific values
        self.assertEqual(result['LOW'][0]['year'], 2023)
        self.assertEqual(result['LOW'][0]['month'], 5)
        self.assertEqual(result['LOW'][0]['count'], 10)
    
    def test_malformed_data(self):
        """Test serializer with malformed data (unhappy case)"""
        # Data where one of the monthly entries is not a dict but a string
        input_data = {
            'LOW': [
                {'year': 2023, 'month': 5, 'count': 10},
                'not a valid month entry'  # This should cause issues
            ]
        }
        
        serializer = SeverityCountSerializer(input_data)
        
        # Since the serializer uses MonthlyCountSerializer internally,
        # we expect an error when trying to serialize a string
        with self.assertRaises(AttributeError):
            _ = serializer.data
    
    def test_empty_data(self):
        """Test serializer with empty data (edge case)"""
        input_data = {}
        
        serializer = SeverityCountSerializer(input_data)
        self.assertEqual(serializer.data, {})
    
    def test_empty_severity_data(self):
        """Test serializer with empty data for some severity levels (edge case)"""
        input_data = {
            'LOW': [
                {'year': 2023, 'month': 5, 'count': 10},
                {'year': 2023, 'month': 6, 'count': 15}
            ],
            'MEDIUM': [],  # Empty data for MEDIUM severity
            'HIGH': [
                {'year': 2023, 'month': 5, 'count': 2}
            ]
        }
        
        serializer = SeverityCountSerializer(input_data)
        result = serializer.data
        
        # Check that all keys are present
        self.assertIn('LOW', result)
        self.assertIn('MEDIUM', result)
        self.assertIn('HIGH', result)
        
        # Check that MEDIUM has no items
        self.assertEqual(len(result['MEDIUM']), 0)
        
        # Check that other severity levels have the correct data
        self.assertEqual(len(result['LOW']), 2)
        self.assertEqual(len(result['HIGH']), 1)
