from django.test import TestCase
from pt_backend.models import User
from authentication.repository import UserRepository

class UserRepositoryTest(TestCase):

    def test_get_user_by_email_success(self):
        user = User.objects.create(name="Alice", email="alice@example.com", password="secret", role="USER")
        result = UserRepository.get_user_by_email("alice@example.com")
        self.assertIsNotNone(result)
        self.assertEqual(result.email, "alice@example.com")

    def test_get_user_by_email_not_found(self):
        result = UserRepository.get_user_by_email("unknown@example.com")
        self.assertIsNone(result)

    def test_save_user_persists_data(self):
        user = User(name="Bob", email="bob@example.com", password="init", role="USER")
        UserRepository.save_user(user)
        saved = User.objects.get(email="bob@example.com")
        self.assertEqual(saved.name, "Bob")
