from __future__ import annotations

from typing import Any, Protocol


class GameAgent(Protocol):
    """Interpret player language without directly mutating authoritative state."""

    def interpret_action(self, state: dict[str, Any], action: str) -> dict[str, Any]: ...
