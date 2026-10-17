"""Story state: what has been said, what is fixed, and which loop we are in.

There are no meters or clocks here. The storyteller decides what happens, whether
a turn only repeats the story and the world comes round again (`restart`), and
whether the loop has finally been broken (`ending`). This module only remembers.
"""

from __future__ import annotations

from dataclasses import dataclass, field, replace
from typing import Any, Literal, Mapping

from backend.case import Case

InputType = Literal["say", "do"]
OUTCOMES = frozenset({"success", "partial", "failure", "blocked"})

MEMORY_TURNS = 8
MAX_FACTS = 40


class RulingError(ValueError):
    """A ruling the runtime cannot accept."""


def _text(value: Any, label: str, *, limit: int) -> str:
    if not isinstance(value, str):
        raise RulingError(f"{label} must be a string.")
    normalized = " ".join(value.split())
    if not normalized:
        raise RulingError(f"{label} must not be empty.")
    return normalized[:limit]


def _texts(value: Any, label: str, *, limit: int, count: int) -> tuple[str, ...]:
    if not isinstance(value, list):
        raise RulingError(f"{label} must be an array of strings.")
    return tuple(_text(item, label, limit=limit) for item in value[:count])


def _flag(value: Any, label: str) -> bool:
    if not isinstance(value, bool):
        raise RulingError(f"{label} must be true or false.")
    return value


@dataclass(frozen=True)
class Ruling:
    """Phase 1 of a turn: what the storyteller decided, before any prose."""

    outcome: str
    facts: tuple[str, ...]
    scene: str
    restart: bool = False
    ending: bool = False

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> "Ruling":
        if not isinstance(payload, Mapping):
            raise RulingError("Ruling must be a JSON object.")
        outcome = payload.get("outcome")
        if outcome not in OUTCOMES:
            raise RulingError(f"Unknown outcome: {outcome!r}.")
        restart = _flag(payload.get("restart", False), "restart")
        ending = _flag(payload.get("ending", False), "ending")
        if restart and ending:
            raise RulingError("A turn cannot both restart the loop and end it.")
        return cls(
            outcome=str(outcome),
            facts=_texts(payload.get("facts", []), "facts", limit=300, count=3),
            scene=_text(payload.get("scene"), "scene", limit=1200),
            restart=restart,
            ending=ending,
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "outcome": self.outcome,
            "facts": list(self.facts),
            "scene": self.scene,
            "restart": self.restart,
            "ending": self.ending,
        }


@dataclass(frozen=True)
class Narration:
    """Phase 2 of a turn: the visible passage and its optional next actions."""

    text: str
    hints: tuple[str, ...] = ()

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> "Narration":
        if not isinstance(payload, Mapping):
            raise RulingError("Narration must be a JSON object.")
        return cls(
            text=_text(payload.get("narration"), "narration", limit=2000),
            hints=_texts(payload.get("hints", []), "hints", limit=160, count=3),
        )


@dataclass(frozen=True)
class Turn:
    number: int
    loop: int
    input_type: InputType
    player_input: str
    narration: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "loop": self.loop,
            "type": self.input_type,
            "text": self.player_input,
            "narration": self.narration,
        }


@dataclass(frozen=True)
class StoryState:
    language: str = "en"
    loop: int = 1
    turn: int = 0
    facts: tuple[str, ...] = ()
    turns: tuple[Turn, ...] = field(default_factory=tuple)
    ended: bool = False

    def to_wire(self) -> dict[str, Any]:
        return {
            "language": self.language,
            "loop": self.loop,
            "turn": self.turn,
            "ended": self.ended,
        }

    def to_agent_context(
        self, case: Case, input_type: InputType, text: str
    ) -> dict[str, Any]:
        return {
            "case": {
                "id": case.id,
                "title": case.title(self.language),
                "player": case.player(self.language),
            },
            "state": {
                "language": self.language,
                "loop": self.loop,
                "turn": self.turn,
                "facts": list(self.facts),
                "ended": self.ended,
            },
            "recent_turns": [turn.to_dict() for turn in self.turns],
            "action": {"type": input_type, "text": text},
        }


def initial_state(language: str = "en") -> StoryState:
    return StoryState(language=language)


def _merge_facts(known: tuple[str, ...], new: tuple[str, ...]) -> tuple[str, ...]:
    merged = list(known)
    for fact in new:
        if fact not in merged:
            merged.append(fact)
    return tuple(merged[-MAX_FACTS:])


def apply_turn(
    state: StoryState,
    input_type: InputType,
    player_input: str,
    ruling: Ruling,
    narration: Narration,
) -> StoryState:
    """Fold one judged turn into the session."""
    if state.ended:
        raise RulingError("The story has already ended.")
    if input_type not in ("say", "do"):
        raise ValueError(f"Unsupported input type: {input_type!r}.")

    turns = (
        *state.turns,
        Turn(
            number=state.turn + 1,
            loop=state.loop,
            input_type=input_type,
            player_input=player_input,
            narration=narration.text,
        ),
    )[-MEMORY_TURNS:]

    return replace(
        state,
        # A returned morning counts as a new loop, and the character keeps its memory.
        loop=state.loop + 1 if ruling.restart else state.loop,
        turn=0 if ruling.restart else state.turn + 1,
        facts=_merge_facts(state.facts, ruling.facts),
        turns=turns,
        ended=ruling.ending,
    )
