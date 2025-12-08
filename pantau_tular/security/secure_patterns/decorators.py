from functools import wraps

from pantau_tular.security.secure_design import BusinessLogicViolation


def enforce_business_rule(rule_name: str):
    """Decorator enforcing explicit business rule helpers.

    The wrapped function must return True-y value to signal the rule passed.
    """

    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            outcome = func(*args, **kwargs)
            if not outcome:
                raise BusinessLogicViolation(f"Business rule '{rule_name}' rejected the operation.")
            return outcome

        return wrapper

    return decorator
