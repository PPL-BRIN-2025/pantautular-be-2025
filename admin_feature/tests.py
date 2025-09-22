from django.test import TestCase
from django.utils import timezone
from django.urls import reverse
from rest_framework.test import APIClient
from admin_feature.models import UserLog


class AdminUserLogsTableTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.url = reverse("admin_user_logs") 

    def test_get_returns_empty_table_initially(self):
        res = self.client.get(self.url)
        self.assertEqual(res.status_code, 200)
        body = res.json()
        self.assertEqual(body["total"], 0)
        self.assertEqual(body["data"], [])

    def test_post_creates_log_entry_without_action(self):
        payload = {
            "username": "user1",
            "email": "user1@gmail.com",
            "detail": "Login success",
        }
        res = self.client.post(self.url, payload, format="json")
        self.assertEqual(res.status_code, 201)
        body = res.json()
        self.assertEqual(body["username"], "user1")
        self.assertEqual(body["email"], "user1@gmail.com")
        self.assertIn("timestamp", body)

        res2 = self.client.get(self.url)
        self.assertEqual(res2.status_code, 200)
        body2 = res2.json()
        self.assertEqual(body2["total"], 1)
        self.assertEqual(len(body2["data"]), 1)
        self.assertEqual(body2["data"][0]["username"], "user1")
        self.assertEqual(body2["data"][0]["email"], "user1@gmail.com")
        self.assertEqual(body2["data"][0]["detail"], "Login success")

    def test_get_returns_multiple_rows_matching_table_example(self):
        seed = [
            {"username": "user1", "email": "user1@gmail.com", "detail": "Login success"},
            {"username": "user2", "email": "user2@gmail.com", "detail": "Change Role"},
            {"username": "user3", "email": "user3@gmail.com", "detail": "Login Failed"},
            {"username": "user1", "email": "user1@gmail.com", "detail": "Login success"},
            {"username": "user2", "email": "user2@gmail.com", "detail": "Change Role"},
        ]
        now_iso = timezone.now().isoformat()
        for p in seed:
            payload = {**p, "timestamp": now_iso}
            self.client.post(self.url, payload, format="json")

        res = self.client.get(self.url)
        self.assertEqual(res.status_code, 200)
        body = res.json()
        self.assertEqual(body["total"], 5)
        self.assertEqual(len(body["data"]), 5)

        row0 = body["data"][0]
        self.assertIn(row0["detail"], ["Login success", "Change Role", "Login Failed"])
        self.assertIn("username", row0)
        self.assertIn("email", row0)
        self.assertIn("timestamp", row0)

    def test_post_without_timestamp_sets_default(self):
        payload = {
            "username": "userX",
            "email": "userx@gmail.com",
            "detail": "Change Role",
        }
        res = self.client.post(self.url, payload, format="json")
        self.assertEqual(res.status_code, 201)
        body = res.json()
        self.assertIn("timestamp", body)


class UserLogDetailAPITest(TestCase):
    def test_get_log_detail_returns_expected_fields(self):
        log = UserLog.objects.create(
            username="user",
            email="user@example.com",
            action="LOGIN_SUCCESS",
            detail="User successfully logged in",
        )

        client = APIClient()
        url = reverse("log-detail", args=[log.id])
        response = client.get(url)

        self.assertEqual(response.status_code, 200)
        data = response.json()

        self.assertEqual(data["id"], log.id)
        self.assertEqual(data["username"], "user")
        self.assertEqual(data["email"], "user@example.com")
        self.assertEqual(data["action"], "LOGIN_SUCCESS")
        self.assertIn("detail", data)


class UserLogModelTest(TestCase):
    def test_str_method_returns_expected_format(self):
        log = UserLog.objects.create(
            username="tester",
            email="tester@example.com",
            action="LOGIN_SUCCESS",
            detail="Login detail"
        )

        string_output = str(log)

        self.assertIn("tester", string_output)
        self.assertIn("LOGIN_SUCCESS", string_output)
        self.assertIn(str(log.created_at.date()), string_output)
