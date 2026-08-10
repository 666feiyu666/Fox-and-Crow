from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

from backend.game_agent.ports import GameAgent
from backend.game_system.fox_crow import (
    game_agent_view,
    parse_game_agent_decision,
    player_view,
    public_event_view,
    resolve_fox_crow_turn,
    story_agent_view,
)
from backend.infrastructure.session_store import InMemoryGameSessionStore
from backend.story_agent.ports import NarrativeGrounder, StoryAgent


@dataclass(frozen=True)
class TurnResponse:
    session_id: str
    narration: str
    outcome: str
    player_state: dict[str, object]


class TurnCoordinator:
    """Run one transactional turn without owning story-specific rules or prompts."""

    def __init__(
        self,
        *,
        game_agent: GameAgent,
        story_agent: StoryAgent,
        narrative_grounder: NarrativeGrounder,
        session_store: InMemoryGameSessionStore,
        log_fallback: Callable[[str], None] | None = None,
    ) -> None:
        self.game_agent = game_agent
        self.story_agent = story_agent
        self.narrative_grounder = narrative_grounder
        self.session_store = session_store
        self.log_fallback = log_fallback or (lambda _message: None)

    def resolve_turn(self, session_id: str, action: str) -> TurnResponse:
        before = self.session_store.get(session_id)
        decision_payload = self.game_agent.interpret_action(
            game_agent_view(before),
            action,
        )
        decision = parse_game_agent_decision(decision_payload, before)
        resolution = resolve_fox_crow_turn(before, decision)
        before_perspective = story_agent_view(before)
        after_perspective = story_agent_view(resolution.state)
        public_events = public_event_view(resolution)

        grounding_feedback = None
        for _ in range(2):
            narration = self.story_agent.narrate(
                before_perspective,
                after_perspective,
                action,
                public_events,
                grounding_feedback,
            )
            audit = self.narrative_grounder.audit_narration(
                before_perspective,
                after_perspective,
                action,
                public_events,
                narration,
            )
            if audit.grounded:
                break
            grounding_feedback = audit.feedback
        else:
            narration = " ".join(event["description"] for event in public_events)
            self.log_fallback(
                "Story narration failed grounding twice; using public-event fallback."
            )

        self.session_store.commit(session_id, before, resolution.state)
        return TurnResponse(
            session_id=session_id,
            narration=narration,
            outcome=resolution.outcome.value,
            player_state=player_view(resolution.state),
        )
