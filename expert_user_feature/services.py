import os
import re
from typing import Any, Iterable, Sequence

from django.utils import timezone
from pt_backend.models import Case, CaseUploadBatch

from .models import ExpertDataset, ExpertDatasetRow

_CSV_RISKY_PREFIXES = ("=", "+", "-", "@")
_CONTROL_CHAR_PATTERN = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f]")


def _sanitize_export_string(value: str | None, max_length: int | None = None) -> str:
    """
    Neutralize spreadsheet formula injection vectors per OWASP CSV Injection guidance.
    https://cheatsheetseries.owasp.org/cheatsheets/CSV_Injection_Prevention_Cheat_Sheet.html
    """
    if value is None:
        cleaned = ""
    else:
        cleaned = _CONTROL_CHAR_PATTERN.sub(" ", str(value))
    cleaned = cleaned.replace("\r", " ").replace("\n", " ")
    stripped = cleaned.lstrip()
    if stripped.startswith(_CSV_RISKY_PREFIXES):
        cleaned = f"'{cleaned}"
    if max_length:
        cleaned = cleaned[:max_length]
    return cleaned


def _sanitize_payload_value(value: Any) -> Any:
    if isinstance(value, dict):
        return {k: _sanitize_payload_value(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_sanitize_payload_value(item) for item in value]
    if isinstance(value, tuple):
        return tuple(_sanitize_payload_value(item) for item in value)
    if isinstance(value, str):
        return _sanitize_export_string(value)
    if value is None:
        return ""
    return value


def _safe_filename(filename: str | None, fallback: str) -> str:
    return _sanitize_export_string(os.path.basename(filename) if filename else fallback, max_length=255)


def build_or_refresh_dataset_from_batch(
    batch: CaseUploadBatch,
    cases_in_order: Sequence[Case] | Iterable[Case] | None = None,
) -> ExpertDataset:
    """
    Buat/refresh ExpertDataset + rows berdasarkan CaseUploadBatch.
    - data_id    : batch.id
    - file_name  : batch.filename
    - submitted_by: user email/username
    - last_edited: batch.uploaded_at (fallback now)
    """
    submitted_by_raw = (
        getattr(batch.uploaded_by, "email", None)
        or getattr(batch.uploaded_by, "username", None)
        or "unknown"
    )
    submitted_by = _sanitize_export_string(submitted_by_raw, max_length=150)

    ds, _ = ExpertDataset.objects.update_or_create(
        data_id=str(batch.id),
        defaults={
            "file_name": _safe_filename(batch.filename, f"batch_{batch.id}.csv"),
            "submitted_by": submitted_by,
            "last_edited": batch.uploaded_at or timezone.now(),
        },
    )

    # rebuild rows idempotent
    ExpertDatasetRow.objects.filter(dataset=ds).delete()

    ordered_ids = None
    if cases_in_order:
        ordered_ids = [str(getattr(case, "id", case)) for case in cases_in_order]
        order_map = {case_id: idx for idx, case_id in enumerate(ordered_ids)}
    else:
        order_map = None

    cases_qs = (
        Case.objects.filter(batch=batch)
        .select_related("disease", "location")
        .order_by("created_at", "id")
    )
    cases = list(cases_qs)
    if order_map:
        fallback_start = len(order_map)
        cases.sort(
            key=lambda c: (
                order_map.get(str(c.id), fallback_start),
                c.created_at,
                str(c.id),
            )
        )

    bulk = []
    for idx, c in enumerate(cases, start=1):
        disease = getattr(c, "disease", None)
        location = getattr(c, "location", None)
        news = (
            c.news.only("portal", "title", "type", "content", "url", "author", "date_published", "img_url")
            .order_by("-date_published", "-id")
            .first()
        )
        payload = {
            "disease_name": getattr(disease, "name", "") or "",
            "location": {
                "city": getattr(location, "city", "") or "",
                "province": getattr(location, "province", "") or "",
            },
            "news": {
                "portal": getattr(news, "portal", "") or "",
                "title": getattr(news, "title", "") or "",
                "type": getattr(news, "type", "") or "",
                "content": getattr(news, "content", "") or "",
                "url": getattr(news, "url", "") or "",
                "author": getattr(news, "author", "") or "",
                "date_published": (
                    news.date_published.isoformat() if getattr(news, "date_published", None) else ""
                ),
                "img_url": getattr(news, "img_url", "") or "",
            },
        }
        payload = _sanitize_payload_value(payload)

        bulk.append(
            ExpertDatasetRow(
                dataset=ds,
                row_number=idx,
                data_id=str(c.id),
                gender=_sanitize_export_string(c.gender or ""),
                age=c.age,
                city=_sanitize_export_string(c.city or getattr(c.location, "city", "") or ""),
                status=_sanitize_export_string(c.status or ""),
                disease_id=_sanitize_export_string(str(getattr(c.disease, "id", "") or "")),
                location_id=_sanitize_export_string(str(getattr(c, "location_id", "") or "")),
                severity=_sanitize_export_string(c.severity or ""),
                payload=payload,
            )
        )
    if bulk:
        ExpertDatasetRow.objects.bulk_create(bulk)

    return ds
