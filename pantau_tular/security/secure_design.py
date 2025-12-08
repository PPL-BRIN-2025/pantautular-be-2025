import logging
from collections import defaultdict, deque
from datetime import datetime, timedelta
from functools import wraps
from typing import Any, Dict, Iterable, Optional

from django.utils import timezone
from rest_framework import status
from rest_framework.response import Response

from pantau_tular.security.exceptions import (
    BusinessLogicViolation,
    InvalidFlowTransition,
    SecureDesignError,
)
from pantau_tular.security.secure_patterns import (
    InputStateTransitionMachine,
    validate_authorize_execute,
)

logger = logging.getLogger(__name__)


class SecureWorkflowValidator:
    """Reusable workflow validator built on the Input–State–Transition state machine."""

    def __init__(self) -> None:
        self._machines: Dict[str, InputStateTransitionMachine] = {}
        self._register_default_flows()

    def _register_default_flows(self) -> None:
        contributor_transitions = InputStateTransitionMachine(
            transitions={
                "WAITING_FOR_APPROVAL": {"NEED_REVISION", "APPROVED", "REJECTED"},
                "NEED_REVISION": {"WAITING_FOR_APPROVAL"},
            },
            terminal_states={"APPROVED", "REJECTED"},
            required_fields={
                "APPROVED": {"review_notes"},
                "REJECTED": {"review_notes"},
            },
        )
        self.register_flow("contributor_submission", contributor_transitions)

    def register_flow(self, flow_name: str, machine: InputStateTransitionMachine) -> None:
        self._machines[flow_name] = machine

    def validate_transition(
        self,
        *,
        flow_name: str,
        current_state: str,
        requested_state: str,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> None:
        if flow_name not in self._machines:
            raise InvalidFlowTransition(f"Flow {flow_name} is not registered for workflow validation.")
        machine = self._machines[flow_name]
        machine.validate(current_state=current_state, new_state=requested_state, metadata=metadata or {})


class BusinessLogicGuard:
    """Reusable guard that centralizes business rule constraints."""

    CHART_DOWNLOAD_LIMIT = 3
    BULK_ACTION_LIMIT = 10
    _GLOBAL_DOWNLOAD_EVENTS: Dict[str, deque] = defaultdict(deque)

    def __init__(self) -> None:
        self._download_events = self._GLOBAL_DOWNLOAD_EVENTS

    def enforce(self, flow_name: str, metadata: Dict[str, Any]) -> None:
        if flow_name == "chart_download":
            self._enforce_chart_download(metadata)
        elif flow_name == "bulk_action":
            self._enforce_bulk_operations(metadata)

    def _enforce_chart_download(self, metadata: Dict[str, Any]) -> None:
        actor = metadata.get("actor") or "anonymous"
        now = metadata.get("timestamp") or timezone.now()
        window = now - timedelta(minutes=1)
        history = self._download_events[actor]
        history.append(now)
        while history and history[0] < window:
            history.popleft()
        if len(history) > self.CHART_DOWNLOAD_LIMIT:
            raise BusinessLogicViolation("Chart download limit exceeded for the current window.")

    def _enforce_bulk_operations(self, metadata: Dict[str, Any]) -> None:
        role = (metadata.get("role") or "").upper()
        bulk_size = int(metadata.get("requested_items") or 0)
        if role not in {"CURATOR", "ADMIN"} and bulk_size > 1:
            raise BusinessLogicViolation("Only privileged roles may perform bulk operations.")
        if bulk_size > self.BULK_ACTION_LIMIT:
            raise BusinessLogicViolation("Bulk operation request exceeds the allowed threshold.")


class AntiAutomationRules:
    """Anti-automation engine that blocks bot-like activity based on timing analysis."""

    MAX_EVENTS = 5
    WINDOW_SECONDS = 5
    _GLOBAL_EVENTS: Dict[str, deque] = defaultdict(deque)

    def __init__(self) -> None:
        self._events = self._GLOBAL_EVENTS

    def check(self, flow_name: str, metadata: Dict[str, Any]) -> None:
        fingerprint = metadata.get("fingerprint")
        if not fingerprint:
            fingerprint = f"{flow_name}:{metadata.get('actor') or 'anon'}"
        now = metadata.get("timestamp") or timezone.now()
        window_start = now - timedelta(seconds=self.WINDOW_SECONDS)
        history = self._events[fingerprint]
        history.append(now)
        while history and history[0] < window_start:
            history.popleft()
        if len(history) > self.MAX_EVENTS:
            raise BusinessLogicViolation("Anti-automation shields detected rapid-fire activity.")


class TierBoundaryEnforcer:
    """Guards tier boundaries and tenant segregation invariants."""

    INTERNAL_FIELDS = {"has_unseen_update", "last_notified_status", "reviewed_at"}

    def assert_clean_payload(self, payload: Dict[str, Any], *, forbidden_fields: Optional[Iterable[str]] = None) -> None:
        forbidden = set(forbidden_fields or set()) | self.INTERNAL_FIELDS
        forged = sorted(set(payload.keys()) & forbidden)
        if forged:
            raise BusinessLogicViolation(f"Client may not set internal fields: {', '.join(forged)}.")

    def extract_actor_tenant(self, request) -> Optional[str]:
        header = request.headers.get("X-Tenant-ID") if hasattr(request, "headers") else None
        if header:
            return header.strip()
        user = getattr(request, "user", None)
        tenant = getattr(user, "tenant_id", None)
        return tenant

    def derive_resource_tenant(self, identifier: str) -> Optional[str]:
        if not identifier:
            return None
        if "::" in identifier:
            return identifier.split("::", 1)[0]
        if "@" in identifier:
            return identifier.split("@", 1)[-1]
        return None

    def ensure_same_tenant(self, *, actor_tenant: Optional[str], resource_tenant: Optional[str], resource_name: str) -> None:
        if actor_tenant and resource_tenant and actor_tenant != resource_tenant:
            raise BusinessLogicViolation(f"Tenant {actor_tenant} cannot access {resource_name} for {resource_tenant}.")


class SecureDesignLayerMixin:
    """Reusable mixin bundling SDL checks, paved-road modules, and threat analysis."""

    workflow_validator_class = SecureWorkflowValidator
    business_guard_class = BusinessLogicGuard
    anti_automation_class = AntiAutomationRules
    tier_enforcer_class = TierBoundaryEnforcer

    def initialize_secure_design(self) -> None:
        if getattr(self, "_secure_design_ready", False):
            return
        self.secure_workflow_validator = self.workflow_validator_class()
        self.business_guard = self.business_guard_class()
        self.anti_automation = self.anti_automation_class()
        self.tier_enforcer = self.tier_enforcer_class()
        self._secure_design_ready = True

    def build_security_payload(self, request, flow_name: str) -> Dict[str, Any]:
        if hasattr(request, "data") and request.data:
            data = request.data
        elif hasattr(request, "query_params"):
            data = request.query_params
        else:
            data = {}
        try:
            return dict(data)
        except Exception:
            return {}

    def build_security_metadata(self, request, flow_name: str, payload: Dict[str, Any], *, actor: Optional[str] = None) -> Dict[str, Any]:
        timestamp = timezone.now()
        actor = actor or getattr(getattr(request, "user", None), "email", None) or "anonymous"
        fingerprint = payload.get("fingerprint") or f"{flow_name}:{actor}"
        tenant = self.tier_enforcer.extract_actor_tenant(request)
        return {
            "actor": actor,
            "timestamp": timestamp,
            "fingerprint": fingerprint,
            "tenant": tenant,
            "payload": payload,
        }

    def apply_secure_checks(
        self,
        *,
        flow_name: str,
        metadata: Dict[str, Any],
        business_context: Optional[Dict[str, Any]] = None,
        anti_automation_context: Optional[Dict[str, Any]] = None,
    ) -> None:
        if not getattr(self, "_secure_design_ready", False):
            self.initialize_secure_design()
        business_payload = (business_context or {}) | metadata
        self.business_guard.enforce(flow_name, business_payload)
        automation_payload = (anti_automation_context or {}) | metadata
        self.anti_automation.check(flow_name, automation_payload)

    def handle_secure_error(self, exc: SecureDesignError, *, flow_name: str) -> Response:
        status_code = status.HTTP_400_BAD_REQUEST
        if isinstance(exc, BusinessLogicViolation):
            status_code = status.HTTP_403_FORBIDDEN if "tenant" in str(exc).lower() else status.HTTP_429_TOO_MANY_REQUESTS
        elif isinstance(exc, InvalidFlowTransition):
            status_code = status.HTTP_400_BAD_REQUEST
        payload = {"detail": str(exc), "flow": flow_name}
        return Response(payload, status=status_code)


def secure_flow(flow_name: str):
    """Decorator to automatically apply SDL controls around DRF view handlers."""

    def decorator(func):
        @wraps(func)
        def wrapper(self, request, *args, **kwargs):
            if not isinstance(self, SecureDesignLayerMixin):
                raise RuntimeError("@secure_flow requires SecureDesignLayerMixin.")
            self.initialize_secure_design()
            payload = self.build_security_payload(request, flow_name)
            metadata = self.build_security_metadata(request, flow_name, payload)
            try:
                self.apply_secure_checks(flow_name=flow_name, metadata=metadata)
            except SecureDesignError as exc:
                return self.handle_secure_error(exc, flow_name=flow_name)
            return func(self, request, *args, **kwargs)

        return wrapper

    return decorator


__all__ = [
    "AntiAutomationRules",
    "BusinessLogicGuard",
    "SecureDesignLayerMixin",
    "SecureWorkflowValidator",
    "TierBoundaryEnforcer",
    "secure_flow",
    "validate_authorize_execute",
]
