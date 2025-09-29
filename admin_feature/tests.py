from datetime import timedelta
from django.test import TestCase
from django.utils import timezone
from django.urls import reverse
from rest_framework.test import APIClient

from admin_feature.models import AdminUserLog


class AdminUserLogsTableTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.url = reverse("admin_user_logs")

    def _mk(self, **kw):
        defaults = dict(
            username="user",
            email="user@example.com",
            detail="Login success",
            action="LOGIN_SUCCESS",
            timestamp=timezone.now(),
        )
        defaults.update(kw)
        return AdminUserLog.objects.create(**defaults)

    def test_get_returns_empty_table_initially(self):
        res = self.client.get(self.url)
        self.assertEqual(res.status_code, 200)
        body = res.json()
        self.assertEqual(body["total"], 0)
        self.assertEqual(body["data"], [])

    def test_post_creates_log_entry_without_action_and_triggers_201(self):
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

    def test_post_invalid_payload_returns_400_and_errors_branch(self):
        bad = {"username": "no-email", "detail": "Login success"}
        res = self.client.post(self.url, bad, format="json")
        self.assertEqual(res.status_code, 400)
        data = res.json()
        self.assertIn("errors", data)

    def test_invalid_page_param_triggers_valueerror_branch(self):
        for i in range(3):
            self._mk(username=f"user{i}", email=f"user{i}@x.com")

        res = self.client.get(self.url, {"page": "abc"})
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.json()["page"], 1)

    def test_invalid_page_size_triggers_valueerror_branch(self):
        for i in range(3):
            self._mk(username=f"user{i}", email=f"user{i}@x.com")

        res = self.client.get(self.url, {"pageSize": "NaN"})
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.json()["pageSize"], 10)

    def test_pagination_defaults_when_params_invalid(self):
        for i in range(12):
            self._mk(
                username=f"user{i}",
                email=f"user{i}@x.com",
                timestamp=timezone.now() + timedelta(minutes=i),
            )

        res = self.client.get(self.url, {"page": "not-int", "pageSize": "NaN"})
        self.assertEqual(res.status_code, 200)
        body = res.json()
        self.assertEqual(body["page"], 1)
        self.assertEqual(body["pageSize"], 10)
        self.assertEqual(body["total"], 12)
        self.assertEqual(len(body["data"]), 10)

    def test_sort_asc_orders_by_oldest_first(self):
        self._mk(username="old", timestamp=timezone.now() - timedelta(days=1))
        self._mk(username="new", timestamp=timezone.now())

        res = self.client.get(self.url, {"sort": "timestamp:asc"})
        self.assertEqual(res.status_code, 200)
        rows = res.json()["data"]
        self.assertGreaterEqual(len(rows), 2)
        self.assertEqual(rows[0]["username"], "old")

        res2 = self.client.get(self.url, {"sort": "timestamp:desc"})
        rows2 = res2.json()["data"]
        self.assertEqual(rows2[0]["username"], "new")

    def test_search_filters_username_email_detail(self):
        self._mk(username="alice", email="alice@example.com", detail="Login success")
        self._mk(username="bob", email="bob@example.com", detail="Change Role")
        self._mk(username="charlie", email="c@example.com", detail="Login Failed")

        res = self.client.get(self.url, {"search": "bob"})
        self.assertEqual(res.status_code, 200)
        body = res.json()
        self.assertEqual(body["total"], 1)
        self.assertEqual(len(body["data"]), 1)
        self.assertEqual(body["data"][0]["username"], "bob")

        res2 = self.client.get(self.url, {"search": "Login Failed"})
        self.assertEqual(res2.status_code, 200)
        body2 = res2.json()
        self.assertEqual(body2["total"], 1)
        self.assertEqual(body2["data"][0]["detail"], "Login Failed")

    def test_start_end_filters_cover_fromisoformat_success_and_exception(self):
        base = timezone.now().replace(microsecond=0)
        self._mk(username="a", timestamp=base - timedelta(days=2))
        self._mk(username="b", timestamp=base - timedelta(days=1))
        self._mk(username="c", timestamp=base)

        start_str_fromiso = (base - timedelta(days=1, hours=12)).strftime("%Y-%m-%d %H:%M:%S")
        end_invalid = "not-a-date"

        res = self.client.get(self.url, {"start": start_str_fromiso, "end": end_invalid})
        self.assertEqual(res.status_code, 200)
        self.assertIn("data", res.json())

        end_valid = (base - timedelta(hours=12)).isoformat()
        res2 = self.client.get(self.url, {"start": start_str_fromiso, "end": end_valid})
        self.assertEqual(res2.status_code, 200)
        usernames2 = [r["username"] for r in res2.json()["data"]]
        self.assertIn("b", usernames2)
        self.assertNotIn("c", usernames2)

    def test_start_end_filters_cover_fromisoformat_exception_branch(self):
        """Force a string that parse_datetime can't handle but looks like datetime → hits fromisoformat except."""
        self._mk(username="z", timestamp=timezone.now())
        bad_date = "2025-09-29T99:99:99"  # invalid, triggers ValueError inside fromisoformat
        res = self.client.get(self.url, {"start": bad_date})
        self.assertEqual(res.status_code, 200)
        self.assertIn("data", res.json())

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


class UserLogDetailAPITest(TestCase):
    def test_get_log_detail_returns_expected_fields(self):
        log = AdminUserLog.objects.create(
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


class AdminUserLogModelTest(TestCase):
    def test_str_method_returns_expected_format(self):
        log = AdminUserLog.objects.create(
            username="tester",
            email="tester@example.com",
            action="LOGIN_SUCCESS",
            detail="Login detail",
        )
        s = str(log)
        self.assertIn("tester", s)
        self.assertIn("LOGIN_SUCCESS", s)
        self.assertIn(str(log.created_at.date()), s)
