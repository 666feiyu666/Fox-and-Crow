from __future__ import annotations

from typing import Any, Protocol


class StoryAgent(Protocol):
    """Continue the visible story without owning authoritative game state."""

    def narrate(self, context: dict[str, Any]) -> str: ...
