from datetime import timedelta

from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APIClient

from authentication.token_security import rate_limiter


TEST_TOKENS = {
    "standard-token": {
        "name": "Standard Token",
        "permissions": ["read"],
        "allowed_ips": ["203.0.113.10"],
        "rate_limit": {"requests": 100, "window": 60},
    },
    "cooldown-token": {
        "name": "Cooldown Token",
        "permissions": ["read"],
        "allowed_ips": ["198.51.100.7"],
        "rate_limit": {"requests": 2, "window": 10},
    },
}


@override_settings(
    API_TOKENS=TEST_TOKENS,
    API_TOKEN_DEFAULT_RATE_LIMIT={"requests": 100, "window": 60},
    API_TOKEN_BLOCK_DURATION=300,
)
class SecureAccessControlsTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.url = reverse("secure-audit-log")
        rate_limiter.reset()
        rate_limiter.clear_time_provider()
        self.addCleanup(rate_limiter.reset)
        self.addCleanup(rate_limiter.clear_time_provider)

    def _get(self, token: str, ip: str):
        return self.client.get(
            self.url,
            HTTP_X_API_TOKEN=token,
            REMOTE_ADDR=ip,
        )

    def test_rate_limit_attack_blocks_after_100_requests(self):
        """Simulates a burst attack with 110 requests from one IP within a minute."""
        ip = "203.0.113.10"
        token = "standard-token"

        for _ in range(100):
            resp = self._get(token, ip)
            self.assertEqual(resp.status_code, status.HTTP_200_OK)

        for _ in range(10):
            resp = self._get(token, ip)
            self.assertEqual(resp.status_code, status.HTTP_429_TOO_MANY_REQUESTS)
            self.assertIn("Rate limit exceeded", resp.data["detail"])

    def test_ip_whitelist_violation(self):
        """Simulates an attacker pivoting from an unauthorized address."""
        resp = self._get("standard-token", "203.0.113.99")
        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)
        self.assertEqual(resp.data["detail"], "IP not authorized")

    def test_combined_attack_logs_and_rejects_immediately(self):
        """Simulates repeated abuse from a forbidden IP to verify logging and blocking."""
        with self.assertLogs("pantau_tular.access_control", level="WARNING") as captured:
            for _ in range(3):
                resp = self._get("standard-token", "198.51.100.200")
                self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)
                self.assertEqual(resp.data["detail"], "IP not authorized")
        self.assertTrue(
            any("IP whitelist violation" in line for line in captured.output),
            "Expected whitelist violation logs for repeated attack",
        )

    def test_block_cooldown_behavior(self):
        """Simulates an adversary being blocked for 5 minutes and retrying after cooldown."""
        token = "cooldown-token"
        ip = "198.51.100.7"
        clock = {"now": timezone.now()}
        rate_limiter.set_time_provider(lambda: clock["now"])

        # Two legitimate requests succeed
        for _ in range(2):
            resp = self._get(token, ip)
            self.assertEqual(resp.status_code, status.HTTP_200_OK)

        # Third request trips the limiter and starts the block timer
        resp = self._get(token, ip)
        self.assertEqual(resp.status_code, status.HTTP_429_TOO_MANY_REQUESTS)
        self.assertEqual(resp.data["detail"], "Rate limit exceeded. Maximum 2 requests allowed.")
        self.assertEqual(resp.data["retry_after"], 300)

        # Attacker keeps hammering; cooldown decreases as time advances
        clock["now"] += timedelta(seconds=30)
        resp = self._get(token, ip)
        self.assertEqual(resp.status_code, status.HTTP_429_TOO_MANY_REQUESTS)
        self.assertLess(resp.data["retry_after"], 300)

        # After cooldown expires, requests are accepted again
        clock["now"] += timedelta(seconds=271)
        resp = self._get(token, ip)
        self.assertEqual(resp.status_code, status.HTTP_200_OK)

    def test_token_missing_or_invalid(self):
        """Simulates requests with no or forged credentials."""
        resp = self.client.get(self.url, REMOTE_ADDR="203.0.113.10")
        self.assertEqual(resp.status_code, status.HTTP_401_UNAUTHORIZED)
        self.assertEqual(resp.data["detail"], "API token required")

        resp = self._get("malicious-token", "203.0.113.10")
        self.assertEqual(resp.status_code, status.HTTP_401_UNAUTHORIZED)
        self.assertEqual(resp.data["detail"], "API token required")
