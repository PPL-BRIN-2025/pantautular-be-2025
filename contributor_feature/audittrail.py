from typing import Any, Dict, Optional
import logging

from pt_backend.models import User
from contributor_feature.models import ContributorCaseSubmission

logger = logging.getLogger("audittrail")


def log_action(
    *,
    user: Optional[User],
    scope: str,
    action: str,
    payload: Dict[str, Any],
) -> None:
    try:
        user_id = getattr(user, "id", None)
        logger.info(
            "[audittrail] scope=%s action=%s user_id=%s payload=%s",
            scope,
            action,
            user_id,
            payload,
        )
    except Exception:

        pass


def log_contributor_submission_action(
    user: Optional[User],
    submission: ContributorCaseSubmission,
    action: str,
    note: str = "",
    extra: Optional[Dict[str, Any]] = None,
) -> None:

    payload: Dict[str, Any] = {
        "submission_id": str(submission.id),
        "state": submission.state,
        "note": note,
        "disease": getattr(submission.disease, "name", ""),
        "city": submission.city,
        "created_by_id": submission.created_by_id,
    }
    if extra:
        payload.update(extra)

    log_action(
        user=user,
        scope="contributor_submission",
        action=action,
        payload=payload,
    )