from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Literal


InputType = Literal["say", "do"]
TOTAL_TIME_UNITS = 6
STORY_CONTEXT_TURNS = 5


@dataclass(frozen=True)
class VisibleTurn:
    loop_count: int
    input_type: InputType
    player_input: str
    narration: str


@dataclass(frozen=True)
class StorySessionState:
    loop_count: int = 1
    elapsed_units: int = 0
    recent_turns: tuple[VisibleTurn, ...] = ()

    def __post_init__(self) -> None:
        if self.loop_count < 1:
            raise ValueError("Loop count must be at least 1.")
        if not 0 <= self.elapsed_units < TOTAL_TIME_UNITS:
            raise ValueError("Elapsed time must stay within the active loop.")
        if len(self.recent_turns) > STORY_CONTEXT_TURNS:
            raise ValueError("Story context exceeds the configured turn window.")

    @property
    def remaining_units(self) -> int:
        return TOTAL_TIME_UNITS - self.elapsed_units

    @property
    def time_phase(self) -> str:
        if self.elapsed_units < 2:
            return "morning"
        if self.elapsed_units < 4:
            return "afternoon"
        return "evening"


def initial_story_state(loop_count: int = 1) -> StorySessionState:
    return StorySessionState(loop_count=loop_count)


def story_agent_context(
    state: StorySessionState,
    input_type: InputType,
    player_input: str,
) -> dict[str, object]:
    return {
        "storyConfig": {
            "title": "The Fox and the Crow: A Day in Loop",
            "premise": (
                "I am the fox in a repeating day beneath the crow's tree. "
                "The visible story may develop freely, but time alone is authoritative."
            ),
            "pointOfView": "first-person limited",
            "tense": "present",
            "tone": "literary, clear, restrained",
            "length": "2-4 concise sentences",
            "stopPosition": "after immediate perceptible consequences and reactions",
        },
        "playerCharacter": {
            "role": "the fox",
            "agencyRule": (
                "Do not add unspoken dialogue, major actions, promises, goals, or decisions "
                "for the player character."
            ),
        },
        "time": player_view(state),
        "recentVisibleTurns": [
            {
                "loopCount": turn.loop_count,
                "inputType": turn.input_type,
                "playerInput": turn.player_input,
                "narration": turn.narration,
            }
            for turn in state.recent_turns
        ],
        "input": {"type": input_type, "text": player_input},
    }


def advance_after_story(
    state: StorySessionState,
    input_type: InputType,
    player_input: str,
    narration: str,
) -> tuple[StorySessionState, str]:
    """Advance exactly one unit after usable narration has been generated."""
    visible_turn = VisibleTurn(
        loop_count=state.loop_count,
        input_type=input_type,
        player_input=player_input,
        narration=narration,
    )
    recent_turns = (*state.recent_turns, visible_turn)[-STORY_CONTEXT_TURNS:]
    elapsed_units = state.elapsed_units + 1
    if elapsed_units == TOTAL_TIME_UNITS:
        return (
            StorySessionState(
                loop_count=state.loop_count + 1,
                elapsed_units=0,
                recent_turns=recent_turns,
            ),
            "loop_advanced",
        )
    return (
        replace(
            state,
            elapsed_units=elapsed_units,
            recent_turns=recent_turns,
        ),
        "continue",
    )


def player_view(state: StorySessionState) -> dict[str, object]:
    return {
        "loopCount": state.loop_count,
        "elapsedUnits": state.elapsed_units,
        "remainingUnits": state.remaining_units,
        "totalUnits": TOTAL_TIME_UNITS,
        "timePhase": state.time_phase,
    }
