import logging

from django.core.exceptions import ValidationError
from django.test import TestCase
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APIClient

from pantau_tular.security import InputValidator, SafeLogger, SafeQueryExecutor


class ListHandler(logging.Handler):
    def __init__(self):
        super().__init__()
        self.records = []

    def emit(self, record):
        self.records.append(record)


class SQLInjectionPreventionTests(TestCase):
    SQL_VECTORS = [
        "' OR 1=1 --",
        "' OR '1'='1",
        "1' OR '1'='1",
        "'; DROP TABLE users; --",
        "UNION SELECT username, password FROM users",
        "admin' --",
        "admin' #",
        "admin'/*",
        "1; DELETE FROM accounts",
        "1; UPDATE users SET role='admin'",
        "WAITFOR DELAY '00:00:10'",
        "SLEEP(5)",
        "BENCHMARK(1000000,MD5(1))",
        "1); SHUTDOWN --",
        "1; EXEC xp_cmdshell('dir')",
        "1; EXEC('drop table users')",
        "1; EXECUTE immediate 'drop'",
        "RANDOMTEXT' OR 'x'='x",
        "0 OR 1=1",
        "0' OR '0'='0'#",
        "\" OR \"\" = \"",
        "x' OR '1'='1' ({",
        "1; INSERT INTO admins",
        "1; CREATE TABLE hacked",
        "1/**/OR/**/1=1",
        "1 UNION ALL SELECT NULL,NULL",
        "1; SELECT * FROM sysobjects",
        "1; SELECT * FROM information_schema.tables",
        "<script>alert('xss')' OR '1'='1</script>",
        "../etc/passwd",
        "..\\..\\windows\\system32",
        "|(objectClass=*)",
        "&(mail=*))",
        "!(&(uid=*))",
        "1; DROP DATABASE pantau_tular",
        "1; TRUNCATE TABLE cases",
        "1; ALTER TABLE users DROP COLUMN password",
        "1; UPDATE/**/users SET password='pwned'",
        "1'; WAITFOR DELAY '0:0:5'",
        "\"; EXECUTE('DROP TABLE x')",
    ]

    def setUp(self):
        self.validator = InputValidator
        self.executor = SafeQueryExecutor()

    def test_sql_injection_vectors_rejected(self):
        """Validator must reject classic, boolean, union, stacked, LDAP, and traversal payloads."""
        for payload in self.SQL_VECTORS:
            with self.subTest(payload=payload):
                with self.assertRaises(ValidationError):
                    self.validator.validate_safe_text(payload)
                with self.assertRaises(ValidationError):
                    self.validator.validate_no_sql_meta(payload)

    def test_safe_query_executor_blocks_malicious_params(self):
        """SafeQueryExecutor should refuse dangerous parameters before the DB sees them."""
        query = "SELECT COUNT(*) FROM django_content_type WHERE app_label = %s"
        with self.assertRaises(ValidationError):
            self.executor.fetchone(query, ["auth; DROP TABLE django_content_type"])

    def test_safe_query_executor_allows_valid_inputs(self):
        """Legitimate values must run as parameterized queries without leaking errors."""
        query = "SELECT COUNT(*) FROM django_content_type WHERE app_label = %s"
        row = self.executor.fetchone(query, ["auth"])
        self.assertIsNotNone(row)
        self.assertGreaterEqual(row[0], 1)

    def test_valid_payloads_pass_validation(self):
        """Confirms whitelisted patterns continue to work for real users."""
        keyword = "status_asc"
        city = "Jakarta Selatan 2025"
        self.assertEqual(self.validator.validate_keyword(keyword), keyword)
        self.assertEqual(self.validator.validate_safe_text(city), city)


class LogInjectionPreventionTests(TestCase):
    def setUp(self):
        self.handler = ListHandler()
        self.logger = logging.getLogger("safe_logger_test")
        self.logger.setLevel(logging.INFO)
        self.logger.addHandler(self.handler)
        self.safe_logger = SafeLogger(self.logger)

    def tearDown(self):
        self.logger.removeHandler(self.handler)

    def test_sanitize_for_logging_strips_newlines(self):
        payload = "INFO: Login successful\nHACKED:\r\nTRACE"
        sanitized = InputValidator.sanitize_for_logging(payload)
        self.assertNotIn("\n", sanitized)
        self.assertEqual(sanitized, "INFO: Login successful HACKED: TRACE")

    def test_safe_logger_prevents_log_forging(self):
        self.safe_logger.info("ERROR\nInjected Log Entry")
        self.assertEqual(len(self.handler.records), 1)
        self.assertEqual(self.handler.records[0].getMessage(), "ERROR Injected Log Entry")


class SafeCaseLookupAPITests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.url = reverse("cases-safe-lookup")
        self.headers = {"HTTP_X_API_KEY": "test-api-key"}

    def test_endpoint_rejects_injection_payloads(self):
        """Simulates HTTP attacks that attempt stacked queries and script tags."""
        response = self.client.get(self.url, {"keyword": "1; DROP TABLE users"}, **self.headers)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("Input matches a known injection payload.", str(response.data))

        response = self.client.get(self.url, {"keyword": "<script>alert(1)</script>"}, **self.headers)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_endpoint_allows_legitimate_payloads(self):
        """Valid requests should be processed and return deterministic data."""
        response = self.client.get(self.url, {"keyword": "Bandung", "status": "minimal"}, **self.headers)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("matching_case_count", response.data)
