class SecureDesignError(Exception):
    """Base exception for secure design violations."""


class InvalidFlowTransition(SecureDesignError):
    """Raised when workflow transitions violate the Input–State–Transition policy."""


class BusinessLogicViolation(SecureDesignError):
    """Raised when paved-road business rules are violated."""
