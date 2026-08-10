from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol


@dataclass(frozen=True)
class FreeActionOutcome:
    narration: str
    promoted: bool
    choice_label: str | None = None


@dataclass(frozen=True)
class NarrationAudit:
    grounded: bool
    feedback: str | None = None


class StoryAgent(Protocol):
    """Turn confirmed public events into player-facing prose."""

    def narrate(
        self,
        before_perspective: dict[str, Any],
        after_perspective: dict[str, Any],
        action: str,
        public_events: list[dict[str, str]],
        grounding_feedback: str | None = None,
    ) -> str: ...


class NarrativeGrounder(Protocol):
    """Check narration against the same public evidence used by the Story Agent."""

    def audit_narration(
        self,
        before_perspective: dict[str, Any],
        after_perspective: dict[str, Any],
        action: str,
        public_events: list[dict[str, str]],
        narration: str,
    ) -> NarrationAudit: ...
