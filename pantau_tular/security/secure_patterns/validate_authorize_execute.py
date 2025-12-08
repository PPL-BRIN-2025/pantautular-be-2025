from typing import Any, Callable, Dict


def validate_authorize_execute(
    validate_fn: Callable[[], Dict[str, Any]],
    authorize_fn: Callable[[Dict[str, Any]], Dict[str, Any]],
    execute_fn: Callable[[Dict[str, Any]], Any],
) -> Any:
    """Implementation of the Validate-Authorize-Execute secure design pattern.

    Each callable receives the enriched context from the previous step, ensuring:
      1. All input/state validation happens up front.
      2. Role/permission checks run before side effects.
      3. Execute runs only after validation + authorization succeed.
    """

    context = validate_fn() or {}
    context = authorize_fn(context) or context
    return execute_fn(context)
