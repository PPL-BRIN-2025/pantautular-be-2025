from django.test import TestCase
from django.contrib.auth.hashers import check_password, make_password
from pt_backend.models import (
    User, Role, Permission, Disease, Location, Case, News,
    HealthProtocol, Climate
)
from decimal import Decimal
import uuid
import secrets
import string
from datetime import datetime
from django.utils import timezone

# Define test constants at module level
TEST_PASSWORD = "test_password_123"  # Only used for testing
NEW_TEST_PASSWORD = "new_test_password_456"  # Only used for testing

class UserModelTest(TestCase):
    def setUp(self):
        # Generate random password for testing
        self.test_password = secrets.token_urlsafe(32)
        self.user = User.objects.create(
            name="Test User",
            email="test@example.com",
            password=make_password(self.test_password),
            role="admin"
        )

    def test_has_role(self):
        self.assertTrue(self.user.has_role("admin"))
        self.assertFalse(self.user.has_role("user"))

    def test_update_password(self):
        # Generate new random password for testing
        new_password = secrets.token_urlsafe(32)
        self.user.update_password(new_password)
        self.assertTrue(check_password(new_password, self.user.password))

    def test_str_representation(self):
        self.assertEqual(str(self.user), "Test User")

class RoleModelTest(TestCase):
    def setUp(self):
        self.role = Role.objects.create(name="Test Role")

    def test_str_representation(self):
        self.assertEqual(str(self.role), "Test Role")

class PermissionModelTest(TestCase):
    def setUp(self):
        self.permission = Permission.objects.create(
            name="Test Permission",
            description="Test Description"
        )

    def test_str_representation(self):
        self.assertEqual(str(self.permission), "Test Permission")

class HealthProtocolModelTest(TestCase):
    def setUp(self):
        self.protocol = HealthProtocol.objects.create(
            title="Test Protocol",
            url="https://example.com"
        )

    def test_str_representation(self):
        self.assertEqual(str(self.protocol), "Test Protocol")

class DiseaseModelTest(TestCase):
    def setUp(self):
        self.disease = Disease.objects.create(
            name="Test Disease",
            level_of_alertness=1
        )
        self.location = Location.objects.create(
            latitude=Decimal("1.234567"),
            longitude=Decimal("123.456789"),
            city="Test Location"
        )
        self.case = Case.objects.create(
            gender="M",
            age=25,
            city="Test City",
            status="minimal",
            disease=self.disease,
            location=self.location
        )

    def test_get_disease_by_id(self):
        found_disease = Disease.get_disease_by_id(self.disease.id)
        self.assertEqual(found_disease, self.disease)

    def test_get_disease_by_id_not_found(self):
        not_found = Disease.get_disease_by_id(uuid.uuid4())
        self.assertIsNone(not_found)

    def test_get_disease_cases(self):
        cases = Disease.get_disease_cases(self.disease)
        self.assertEqual(len(cases), 1)
        self.assertEqual(cases[0], self.case)

    def test_str_representation(self):
        self.assertEqual(str(self.disease), "Test Disease")

class LocationModelTest(TestCase):
    def setUp(self):
        self.location = Location.objects.create(
            latitude=Decimal("1.234567"),
            longitude=Decimal("123.456789"),
            city="Test Location"
        )

    def test_get_location_by_city(self):
        found_location = Location.get_location_by_city("Test Location")
        self.assertEqual(found_location, self.location)

    def test_get_location_by_city_not_found(self):
        not_found = Location.get_location_by_city("Nonexistent")
        self.assertIsNone(not_found)

    def test_get_all_locations(self):
        locations = Location.get_all_locations()
        self.assertEqual(list(locations), [self.location])

    def test_str_representation(self):
        # Test str method
        self.assertEqual(str(self.location), "Test Location")

    def test_str_representation_duplicate(self):
        # Test the duplicate str method
        location = Location.objects.create(
            latitude=Decimal("2.345678"),
            longitude=Decimal("123.456789"),
            city="Another Location"
        )
        self.assertEqual(str(location), "Another Location")

class CaseModelTest(TestCase):
    def setUp(self):
        self.disease = Disease.objects.create(
            name="Test Disease",
            level_of_alertness=1
        )
        self.location = Location.objects.create(
            latitude=Decimal("1.234567"),
            longitude=Decimal("123.456789"),
            city="Test Location"
        )
        self.case = Case.objects.create(
            gender="M",
            age=25,
            city="Test City",
            status="minimal",
            disease=self.disease,
            location=self.location
        )

    def test_get_all_locations(self):
        locations = Case.get_all_locations()
        self.assertEqual(len(locations), 1)
        location = locations[0]
        self.assertEqual(location["city"], "Test City")
        self.assertEqual(location["location__longitude"], self.location.longitude)
        self.assertEqual(location["location__latitude"], self.location.latitude)

    def test_str_representation(self):
        expected = f"Case {self.case.id} - Test City"
        self.assertEqual(str(self.case), expected)

class NewsModelTest(TestCase):
    def setUp(self):
        self.disease = Disease.objects.create(
            name="Test Disease",
            level_of_alertness=1
        )
        self.location = Location.objects.create(
            latitude=Decimal("1.234567"),
            longitude=Decimal("123.456789"),
            city="Test Location"
        )
        self.case = Case.objects.create(
            gender="M",
            age=25,
            city="Test City",
            status="minimal",
            disease=self.disease,
            location=self.location
        )
        self.news = News.objects.create(
            portal="Test Portal",
            title="Test News",
            type="article",
            content="Test Content",
            url="https://example.com",
            author="Test Author",
            date_published=timezone.now(),
            case=self.case
        )

    def test_str_representation(self):
        self.assertEqual(str(self.news), "Test News")

class ClimateModelTest(TestCase):
    def setUp(self):
        self.climate = Climate.objects.create(
            province="Test Province",
            temperature=Decimal("25.5"),
            precipitation=Decimal("100.0"),
            humidity=Decimal("80.0"),
            year=2024,
            month=1
        )

    def test_str_representation(self):
        self.assertEqual(str(self.climate), "Test Province")

    def test_get_climate_for_location(self):
        # Create a test location
        location = Location.objects.create(
            latitude=Decimal("1.234567"),
            longitude=Decimal("123.456789"),
            city="Test City",
            province="Test Province"
        )
        
        # Test with year only
        climates = Climate.get_climate_for_location(location, 2024)
        self.assertEqual(len(climates), 1)
        self.assertEqual(climates[0], self.climate)
        
        # Test with year and month
        climates = Climate.get_climate_for_location(location, 2024, 1)
        self.assertEqual(len(climates), 1)
        self.assertEqual(climates[0], self.climate)

    def test_get_climate_for_location_different_province(self):
        # Create a test location with different province
        location = Location.objects.create(
            latitude=Decimal("1.234567"),
            longitude=Decimal("123.456789"),
            city="Test City",
            province="Different Province"
        )
        
        # Test with year only
        climates = Climate.get_climate_for_location(location, 2024)
        self.assertEqual(len(climates), 0)
        
        # Test with year and month
        climates = Climate.get_climate_for_location(location, 2024, 1)
        self.assertEqual(len(climates), 0)