from django.test import TestCase
from django.utils import timezone
from django.urls import reverse
from rest_framework.test import APIClient


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
        self.assertIn("timestamp", body)  # auto-filled by view


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
