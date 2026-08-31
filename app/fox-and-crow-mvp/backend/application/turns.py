from __future__ import annotations

from dataclasses import dataclass

from backend.infrastructure.session_store import InMemoryStorySessionStore
from backend.story_agent.ports import StoryAgent
from backend.story_runtime.state import (
    InputType,
    advance_after_story,
    player_view,
    story_agent_context,
)


@dataclass(frozen=True)
class TurnResponse:
    session_id: str
    narration: str
    input_type: InputType
    player_input: str
    outcome: str
    player_state: dict[str, object]


class TurnCoordinator:
    """Generate one story continuation, then atomically advance deterministic time."""

    def __init__(
        self,
        *,
        story_agent: StoryAgent,
        session_store: InMemoryStorySessionStore,
    ) -> None:
        self.story_agent = story_agent
        self.session_store = session_store

    def resolve_turn(
        self,
        session_id: str,
        input_type: InputType,
        player_input: str,
    ) -> TurnResponse:
        before = self.session_store.get(session_id)
        narration = self.story_agent.narrate(
            story_agent_context(before, input_type, player_input)
        )
        after, outcome = advance_after_story(
            before,
            input_type,
            player_input,
            narration,
        )
        self.session_store.commit(session_id, before, after)
        return TurnResponse(
            session_id=session_id,
            narration=narration,
            input_type=input_type,
            player_input=player_input,
            outcome=outcome,
            player_state=player_view(after),
        )
