"""Authoritative story state and the rules that apply a Storyteller ruling.

The model decides consequences; this module decides what those consequences are
allowed to do to the session. Every state change passes through ``apply_turn``,
so a session can be replayed and tested without a model.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Any, Literal, Mapping

InputType = Literal["say", "do"]
Language = Literal["en", "zh"]
OUTCOMES = frozenset({"success", "partial", "failure", "blocked"})
ENDINGS = frozenset({"none", "loop_broken"})
LANGUAGES = frozenset({"en", "zh"})

DAY_UNITS = 6
MAX_TIME_COST = 3
MEMORY_TURNS = 8
MAX_FACTS = 40

TRUST_MIN, TRUST_MAX = -3, 6
INSIGHT_MIN, INSIGHT_MAX = 0, 6

# The Storyteller declares the ending; these thresholds are the floor it must
# have earned first. They are deliberately low: they stop a single turn from
# skipping the story, not the Storyteller's judgement.
LOOP_BREAK_MIN_TURNS = 8
LOOP_BREAK_MIN_INSIGHT = 3
LOOP_BREAK_MIN_TRUST = 3

PHASES = ("morning", "morning", "afternoon", "afternoon", "evening", "evening")


class RulingError(ValueError):
    """A ruling the runtime cannot accept."""


def _clamp(value: int, low: int, high: int) -> int:
    return max(low, min(high, value))


def _int(value: Any, label: str, low: int, high: int) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise RulingError(f"{label} must be an integer.")
    return _clamp(value, low, high)


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


@dataclass(frozen=True)
class Ruling:
    """Phase 1 of a turn: the Storyteller's judgement, before any prose."""

    outcome: str
    time_cost: int
    trust: int
    insight: int
    facts: tuple[str, ...]
    scene: str
    ending: str

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> "Ruling":
        if not isinstance(payload, Mapping):
            raise RulingError("Ruling must be a JSON object.")
        outcome = payload.get("outcome")
        if outcome not in OUTCOMES:
            raise RulingError(f"Unknown outcome: {outcome!r}.")
        ending = payload.get("ending", "none")
        if ending not in ENDINGS:
            raise RulingError(f"Unknown ending: {ending!r}.")
        return cls(
            outcome=str(outcome),
            time_cost=_int(payload.get("time_cost"), "time_cost", 0, MAX_TIME_COST),
            trust=_int(payload.get("trust"), "trust", -2, 2),
            insight=_int(payload.get("insight"), "insight", -1, 2),
            facts=_texts(payload.get("facts", []), "facts", limit=200, count=5),
            scene=_text(payload.get("scene"), "scene", limit=800),
            ending=str(ending),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "outcome": self.outcome,
            "time_cost": self.time_cost,
            "trust": self.trust,
            "insight": self.insight,
            "facts": list(self.facts),
            "scene": self.scene,
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
            text=_text(payload.get("narration"), "narration", limit=1600),
            hints=_texts(payload.get("hints", []), "hints", limit=120, count=3),
        )


@dataclass(frozen=True)
class Turn:
    number: int
    loop: int
    input_type: InputType
    player_input: str
    narration: str
    outcome: str
    time_cost: int

    def to_dict(self) -> dict[str, Any]:
        return {
            "type": self.input_type,
            "text": self.player_input,
            "narration": self.narration,
            "outcome": self.outcome,
        }


@dataclass(frozen=True)
class StoryState:
    language: Language = "en"
    loop: int = 1
    elapsed: int = 0
    trust: int = 0
    insight: int = 0
    facts: tuple[str, ...] = ()
    turns: tuple[Turn, ...] = ()
    ending: str | None = None

    @property
    def phase(self) -> str:
        return PHASES[min(self.elapsed, DAY_UNITS - 1)]

    @property
    def remaining(self) -> int:
        return max(DAY_UNITS - self.elapsed, 0)

    @property
    def ended(self) -> bool:
        return self.ending is not None

    def to_wire(self) -> dict[str, Any]:
        return {
            "language": self.language,
            "loop": self.loop,
            "elapsedUnits": self.elapsed,
            "remainingUnits": self.remaining,
            "totalUnits": DAY_UNITS,
            "phase": self.phase,
            "ended": self.ended,
        }

    def to_agent_context(self, input_type: InputType, text: str) -> dict[str, Any]:
        return {
            "state": {
                "language": self.language,
                "loop": self.loop,
                "elapsedUnits": self.elapsed,
                "remainingUnits": self.remaining,
                "phase": self.phase,
                "crowTrust": self.trust,
                "foxInsight": self.insight,
                "loopBroken": self.ended,
            },
            "established_facts": list(self.facts),
            "recent_turns": [turn.to_dict() for turn in self.turns],
            "action": {"type": input_type, "text": text},
        }


def initial_state(language: Language = "en") -> StoryState:
    if language not in LANGUAGES:
        raise ValueError(f"Unsupported language: {language!r}.")
    return StoryState(language=language)


def loop_break_allowed(turn_count: int, insight: int, trust: int) -> bool:
    """Whether the turn now being resolved has earned the ending it claims."""
    return (
        turn_count >= LOOP_BREAK_MIN_TURNS
        and insight >= LOOP_BREAK_MIN_INSIGHT
        and trust >= LOOP_BREAK_MIN_TRUST
    )


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
) -> tuple[StoryState, tuple[str, ...]]:
    """Fold one judged turn into the session and report what happened to it."""
    if state.ended:
        raise RulingError("The story has already ended.")
    if input_type not in ("say", "do"):
        raise ValueError(f"Unsupported input type: {input_type!r}.")

    events: list[str] = []
    trust = _clamp(state.trust + ruling.trust, TRUST_MIN, TRUST_MAX)
    insight = _clamp(state.insight + ruling.insight, INSIGHT_MIN, INSIGHT_MAX)
    facts = _merge_facts(state.facts, ruling.facts)
    turns = (
        *state.turns,
        Turn(
            number=len(state.turns) + 1,
            loop=state.loop,
            input_type=input_type,
            player_input=player_input,
            narration=narration.text,
            outcome=ruling.outcome,
            time_cost=ruling.time_cost,
        ),
    )[-MEMORY_TURNS:]

    ending: str | None = None
    if ruling.ending == "loop_broken":
        if loop_break_allowed(len(state.turns) + 1, insight, trust):
            ending = "loop_broken"
            events.append("loop_broken")
        else:
            events.append("loop_break_refused")

    elapsed = state.elapsed + ruling.time_cost
    loop = state.loop
    if ending is None and elapsed >= DAY_UNITS:
        elapsed -= DAY_UNITS
        loop += 1
        trust = 0  # The crow keeps no memory of the day that just ended.
        events.append("day_reset")

    next_state = replace(
        state,
        loop=loop,
        elapsed=elapsed,
        trust=trust,
        insight=insight,
        facts=facts,
        turns=turns,
        ending=ending,
    )
    return next_state, tuple(events)
