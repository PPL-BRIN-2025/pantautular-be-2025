from dataclasses import dataclass, field
from typing import Dict, Iterable, Optional, Set

from pantau_tular.security.exceptions import InvalidFlowTransition


@dataclass
class InputStateTransitionMachine:
    """Simple Input–State–Transition state machine for sensitive workflows."""

    transitions: Dict[str, Set[str]]
    terminal_states: Set[str] = field(default_factory=set)
    required_fields: Dict[str, Set[str]] = field(default_factory=dict)

    def validate(self, *, current_state: str, new_state: str, metadata: Optional[dict] = None) -> None:
        metadata = metadata or {}
        allowed_targets = self.transitions.get(current_state, set())
        if new_state not in allowed_targets:
            raise InvalidFlowTransition(
                f"Transition {current_state!r}->{new_state!r} is not permitted by the workflow policy."
            )

        for field in self.required_fields.get(new_state, set()):
            value = metadata.get(field)
            if value in (None, "", [], {}):
                raise InvalidFlowTransition(
                    f"Transition to {new_state} requires populated field '{field}'."
                )

        if new_state in self.terminal_states and not metadata.get("allow_terminal_transition", True):
            raise InvalidFlowTransition(f"Terminal state {new_state} cannot be reached from this context.")

    def allowed_transitions(self, state: str) -> Set[str]:
        return set(self.transitions.get(state, set()))

    @classmethod
    def from_pairs(
        cls,
        pairs: Iterable[tuple],
        *,
        terminal_states: Optional[Iterable[str]] = None,
        required_fields: Optional[Dict[str, Iterable[str]]] = None,
    ) -> "InputStateTransitionMachine":
        transitions: Dict[str, Set[str]] = {}
        for source, target in pairs:
            transitions.setdefault(source, set()).add(target)
        terminal = set(terminal_states or [])
        required = {k: set(v) for k, v in (required_fields or {}).items()}
        return cls(transitions=transitions, terminal_states=terminal, required_fields=required)
