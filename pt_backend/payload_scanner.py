import re
import unicodedata
from rest_framework.exceptions import ValidationError

class SQLInjectionDetector:
    """
    Stronger SQL Injection Detector with input normalization.
    """

    SUSPICIOUS_PATTERNS = [
        r"(?i)(select\s.+\sfrom)",             # SELECT ... FROM
        r"(?i)(union\s+select)",                # UNION SELECT
        r"(?i)(insert\s+into)",                 # INSERT INTO
        r"(?i)(update\s+\w+\s+set)",             # UPDATE table SET
        r"(?i)(delete\s+from)",                 # DELETE FROM
        r"(?i)(drop\s+table|drop\s+database)",   # DROP TABLE or DATABASE
        r"(?i)(create\s+table|create\s+database)", # CREATE TABLE or DATABASE
        r"(?i)(exec\s+\()",                     # EXEC(
        r"(?i)(--|#)",                          # Comment injections
        r"(?i)(;)",                             # Multiple queries
    ]

    @classmethod
    def normalize(cls, value: str) -> str:
        # Convert special unicode to ascii
        value = unicodedata.normalize('NFKD', value).encode('ascii', 'ignore').decode('ascii')
        # Remove extra spaces and lower the string
        value = re.sub(r'\s+', ' ', value)
        return value.lower()

    @classmethod
    def _is_suspicious(cls, value: str) -> bool:
        if not isinstance(value, str):
            return False
        
        normalized_value = cls.normalize(value)

        for pattern in cls.SUSPICIOUS_PATTERNS:
            if re.search(pattern, normalized_value):
                return True
        return False

    @classmethod
    def check(cls, request):
        """
        Check request.query_params (GET) and request.data (POST/PUT) for SQL injection attempts.
        """
        for key, value in request.query_params.items():
            if cls._is_suspicious(value):
                raise ValidationError(f"Input for '{key}' contains suspicious SQL injection pattern.")

        if hasattr(request, "data"):
            for key, value in request.data.items():
                if isinstance(value, str) and cls._is_suspicious(value):
                    raise ValidationError(f"Input for '{key}' contains suspicious SQL injection pattern.")
                if isinstance(value, list):
                    for item in value:
                        if isinstance(item, str) and cls._is_suspicious(item):
                            raise ValidationError(f"Input list for '{key}' contains suspicious SQL injection pattern.")
