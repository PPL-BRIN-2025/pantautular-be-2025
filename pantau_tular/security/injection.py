import logging
import re
from typing import Any, Iterable, Optional, Sequence

from django.core.exceptions import ValidationError
from django.db import DEFAULT_DB_ALIAS, connections


class InputValidator:
    """Centralized validation logic for all untrusted input that reaches the backend."""

    KEYWORD_PATTERN = re.compile(r"^[A-Za-z0-9._-]+$")
    SAFE_TEXT_PATTERN = re.compile(r"^[A-Za-z0-9\s@#'\",.!?/:;+()_-]+$")
    CONTROL_CHARS = re.compile(r"[\x00-\x08\x0B\x0C\x0E-\x1F]")
    PATH_TRAVERSAL_PATTERN = re.compile(r"(\.\./|%2e%2e/|\.{2}\\|%2e%2e\\)")

    SQLI_PATTERNS = [
        re.compile(r"(?i)(\bor\b\s+1=1)"),
        re.compile(r"(?i)(\bor\b\s+'1'='1')"),
        re.compile(r"(?i)(union\s+all?\s+select)"),
        re.compile(r"(?i)(waitfor\s+delay)"),
        re.compile(r"(?i)(sleep\s*\()"),
        re.compile(r"(?i)(benchmark\s*\()"),
        re.compile(r"(?i)(;+\s*drop\s+table)"),
        re.compile(r"(?i)(;+\s*delete\s+from)"),
        re.compile(r"(?i)(;+\s*shutdown)"),
        re.compile(r"(?i)(;+\s*insert\s+into)"),
        re.compile(r"(?i)(;+\s*update\s+\w+\s+set)"),
        re.compile(r"(?i)(;+\s*exec(\s+|\())"),
        re.compile(r"(?i)(;+\s*execute(\s+|\())"),
        re.compile(r"(?i)(\bxp_cmdshell\b)"),
        re.compile(r"(?i)(/\*.+\*/)"),
        re.compile(r"(?i)(<script>.*</script>)"),
        re.compile(r"(?i)(\bldap\b|\bldaps\b)"),
        re.compile(r"(?i)(\bSELECT\b.+\bFROM\b.+\bWHERE\b.+\=.+\bSELECT\b)"),
    ]
    DANGEROUS_SUBSTRINGS = [
        "' or '1'='1",
        "\" or \"1\"=\"1",
        "' or '",
        "\" or \"",
        ") or (",
        " or 1=1",
        " or 'x'='x",
        "union select",
        "union all select",
        " waitfor delay",
        " sleep(",
        " benchmark(",
        ";drop ",
        ";drop",
        "; delete",
        "; insert",
        "; update",
        "; shutdown",
        "; exec",
        "; execute",
        "xp_cmdshell",
        "information_schema",
        "sysobjects",
        "../",
        "..\\",
        "ldap://",
        "ldaps://",
    ]

    SQL_META_TOKENS = ["--", ";--", ";", "/*", "*/", "\\", "%00", "#"]
    LDAP_META_TOKENS = ["&", "|", "!"]

    @classmethod
    def _coerce(cls, value: Any) -> str:
        if value is None:
            return ""
        return str(value).strip()

    @classmethod
    def _assert_no_patterns(cls, value: str) -> None:
        normalized = value.lower()
        if cls.PATH_TRAVERSAL_PATTERN.search(normalized):
            raise ValidationError("Path traversal sequences are not permitted.")
        for needle in cls.DANGEROUS_SUBSTRINGS:
            if needle in normalized:
                raise ValidationError("Input matches a known injection payload.")
        for pattern in cls.SQLI_PATTERNS:
            if pattern.search(value):
                raise ValidationError("Input matches a known injection payload.")

    @classmethod
    def _assert_no_meta_tokens(cls, value: str) -> None:
        lowered = value.lower()
        for token in cls.SQL_META_TOKENS + cls.LDAP_META_TOKENS:
            if token in lowered:
                raise ValidationError("Input contains forbidden control tokens.")

    @classmethod
    def validate_keyword(cls, value: Any) -> str:
        """Whitelist for short keyword/identifier style parameters."""
        text = cls._coerce(value)
        if not text:
            raise ValidationError("Keyword cannot be empty.")
        cls._assert_no_patterns(text)
        if not cls.KEYWORD_PATTERN.fullmatch(text):
            raise ValidationError("Keyword may only contain alphanumeric characters, dot, dash, and underscore.")
        cls._assert_no_meta_tokens(text)
        return text

    @classmethod
    def validate_safe_text(cls, value: Any) -> str:
        """Whitelist-based validation for longer free-form text parameters."""
        text = cls._coerce(value)
        if not text:
            return text
        cls._assert_no_patterns(text)
        cls._assert_no_meta_tokens(text)
        if not cls.SAFE_TEXT_PATTERN.fullmatch(text):
            raise ValidationError("Input contains unsupported characters.")
        return text

    @classmethod
    def validate_no_sql_meta(cls, value: Any) -> str:
        """Ensure a value does not include SQL meta characters or control bytes."""
        text = cls._coerce(value)
        if not text:
            return text
        cls._assert_no_patterns(text)
        cls._assert_no_meta_tokens(text)
        if cls.CONTROL_CHARS.search(text):
            raise ValidationError("Input contains control characters.")
        return text

    @classmethod
    def sanitize_for_logging(cls, value: Any) -> str:
        """Strip CR/LF/control characters before writing to logs."""
        text = cls._coerce(value)
        if not text:
            return ""
        text = text.replace("\r", " ").replace("\n", " ")
        text = cls.CONTROL_CHARS.sub("", text)
        text = re.sub(r"\s{2,}", " ", text)
        return text.strip()


class SafeLogger:
    """Logging wrapper that sanitizes message and arguments to prevent log forging."""

    def __init__(self, logger: Optional[logging.Logger] = None) -> None:
        self._logger = logger or logging.getLogger("pantau_tular.safe_logger")

    def _sanitize(self, value: Any) -> Any:
        if isinstance(value, str):
            return InputValidator.sanitize_for_logging(value)
        if isinstance(value, (list, tuple)):
            return type(value)(self._sanitize(item) for item in value)
        if isinstance(value, dict):
            return {key: self._sanitize(val) for key, val in value.items()}
        return value

    def log(self, level: int, msg: str, *args: Any, **kwargs: Any) -> None:
        self._logger.log(level, self._sanitize(msg), *self._sanitize(args), **self._sanitize(kwargs))

    def info(self, msg: str, *args: Any, **kwargs: Any) -> None:
        self.log(logging.INFO, msg, *args, **kwargs)

    def warning(self, msg: str, *args: Any, **kwargs: Any) -> None:
        self.log(logging.WARNING, msg, *args, **kwargs)

    def error(self, msg: str, *args: Any, **kwargs: Any) -> None:
        self.log(logging.ERROR, msg, *args, **kwargs)

    def debug(self, msg: str, *args: Any, **kwargs: Any) -> None:
        self.log(logging.DEBUG, msg, *args, **kwargs)


class SafeQueryExecutor:
    """Executes database queries using either the ORM or parameterized SQL."""

    def __init__(
        self,
        using: str = DEFAULT_DB_ALIAS,
        validator: Optional[InputValidator] = None,
        logger: Optional[SafeLogger] = None,
    ) -> None:
        self.connection = connections[using]
        self.validator = validator or InputValidator
        self.logger = logger or SafeLogger(logging.getLogger("pantau_tular.safe_query"))

    def fetchone(self, query: str, params: Optional[Sequence[Any]] = None):
        rows = self._execute(query, params, many=False)
        return rows

    def fetchall(self, query: str, params: Optional[Sequence[Any]] = None):
        return self._execute(query, params, many=True)

    def _sanitize_params(self, params: Optional[Sequence[Any]]) -> Iterable[Any]:
        if not params:
            return []
        sanitized = []
        for value in params:
            if isinstance(value, str):
                sanitized.append(self.validator.validate_no_sql_meta(value))
            else:
                sanitized.append(value)
        return sanitized

    def _execute(self, query: str, params: Optional[Sequence[Any]], many: bool):
        if not isinstance(query, str) or not query.strip():
            raise ValueError("Query must be a non-empty string.")
        cleaned_query = " ".join(query.split())
        sanitized_params = self._sanitize_params(params)
        with self.connection.cursor() as cursor:
            cursor.execute(cleaned_query, sanitized_params)
            return cursor.fetchall() if many else cursor.fetchone()


__all__ = ["InputValidator", "SafeLogger", "SafeQueryExecutor"]
