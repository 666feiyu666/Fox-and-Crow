"""Authoritative story state and the rules that apply a Storyteller ruling.

The model decides consequences; this module decides what those consequences are
allowed to do to the session. Clock, meters, and the ending condition all come
from the case, so the same rules drive every story.
"""

from __future__ import annotations

from dataclasses import dataclass, field, replace
from typing import Any, Literal, Mapping

from backend.case import MAX_TIME_COST, Case, Meter

InputType = Literal["say", "do"]
OUTCOMES = frozenset({"success", "partial", "failure", "blocked"})
ENDINGS = frozenset({"none", "end"})

MEMORY_TURNS = 8
MAX_FACTS = 40


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
    meters: Mapping[str, int]
    facts: tuple[str, ...]
    scene: str
    ending: str

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any], case: Case) -> "Ruling":
        if not isinstance(payload, Mapping):
            raise RulingError("Ruling must be a JSON object.")
        outcome = payload.get("outcome")
        if outcome not in OUTCOMES:
            raise RulingError(f"Unknown outcome: {outcome!r}.")
        ending = payload.get("ending", "none")
        if ending not in ENDINGS:
            raise RulingError(f"Unknown ending: {ending!r}.")

        time_cost = _int(payload.get("time_cost", 0), "time_cost", 0, MAX_TIME_COST)
        if case.clock is None:
            time_cost = 0

        raw_meters = payload.get("meters", {})
        if not isinstance(raw_meters, Mapping):
            raise RulingError("meters must be an object of meter names to integers.")
        meters: dict[str, int] = {}
        for meter_id, delta in raw_meters.items():
            if case.meter(str(meter_id)) is None:
                continue  # A meter this story does not keep is ignored, not invented.
            meters[str(meter_id)] = _int(delta, f"meters.{meter_id}", -2, 2)

        return cls(
            outcome=str(outcome),
            time_cost=time_cost,
            meters=meters,
            facts=_texts(payload.get("facts", []), "facts", limit=200, count=5),
            scene=_text(payload.get("scene"), "scene", limit=800),
            ending=str(ending),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "outcome": self.outcome,
            "time_cost": self.time_cost,
            "meters": dict(self.meters),
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
    day: int
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
    language: str = "en"
    turn: int = 0
    day: int = 1
    elapsed: int = 0
    meters: Mapping[str, int] = field(default_factory=dict)
    facts: tuple[str, ...] = ()
    turns: tuple[Turn, ...] = ()
    ending: str | None = None

    @property
    def ended(self) -> bool:
        return self.ending is not None

    def phase(self, case: Case) -> str:
        if case.clock is None:
            return ""
        share = self.elapsed / case.clock.units_per_day
        if share < 1 / 3:
            return "morning"
        if share < 2 / 3:
            return "afternoon"
        return "evening"

    def remaining(self, case: Case) -> int:
        if case.clock is None:
            return 0
        return max(case.clock.units_per_day - self.elapsed, 0)

    def to_wire(self, case: Case) -> dict[str, Any]:
        wire: dict[str, Any] = {
            "language": self.language,
            "turn": self.turn,
            "day": self.day,
            "hasClock": case.clock is not None,
            "ended": self.ended,
        }
        if case.clock is not None:
            wire.update(
                {
                    "elapsedUnits": self.elapsed,
                    "remainingUnits": self.remaining(case),
                    "totalUnits": case.clock.units_per_day,
                    "phase": self.phase(case),
                    "loops": case.clock.loops,
                }
            )
        return wire

    def to_agent_context(self, case: Case, input_type: InputType, text: str) -> dict[str, Any]:
        clock = None
        if case.clock is not None:
            clock = {
                "totalUnits": case.clock.units_per_day,
                "remainingUnits": self.remaining(case),
                "phase": self.phase(case),
                "loops": case.clock.loops,
            }
        return {
            "case": {"id": case.id, "player_character": case.character_name("en")},
            "state": {
                "language": self.language,
                "turn": self.turn,
                "day": self.day,
                "clock": clock,
                "meters": dict(self.meters),
                "ended": self.ended,
            },
            "established_facts": list(self.facts),
            "recent_turns": [turn.to_dict() for turn in self.turns],
            "action": {"type": input_type, "text": text},
        }


def initial_state(case: Case, language: str = "en") -> StoryState:
    return StoryState(
        language=language,
        meters={meter.id: meter.start for meter in case.meters},
    )


def ending_allowed(case: Case, turn_count: int, meters: Mapping[str, int]) -> bool:
    """Whether the turn now being resolved has earned the ending it claims."""
    if turn_count < case.ending.min_turns:
        return False
    return all(meters.get(meter_id, 0) >= threshold for meter_id, threshold in case.ending.requires.items())


def _merge_facts(known: tuple[str, ...], new: tuple[str, ...]) -> tuple[str, ...]:
    merged = list(known)
    for fact in new:
        if fact not in merged:
            merged.append(fact)
    return tuple(merged[-MAX_FACTS:])


def _apply_meters(
    case: Case,
    current: Mapping[str, int],
    deltas: Mapping[str, int],
) -> dict[str, int]:
    updated = dict(current)
    for meter in case.meters:
        updated[meter.id] = _clamp(
            current.get(meter.id, meter.start) + deltas.get(meter.id, 0),
            meter.minimum,
            meter.maximum,
        )
    return updated


def _reset_meters(case: Case, meters: Mapping[str, int]) -> dict[str, int]:
    if case.clock is None:
        return dict(meters)
    reset = {}
    for meter in case.meters:
        reset[meter.id] = meter.start if meter.id in case.clock.reset_on_loop else meters.get(
            meter.id, meter.start
        )
    return reset


def apply_turn(
    state: StoryState,
    case: Case,
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
    meters = _apply_meters(case, state.meters, ruling.meters)
    facts = _merge_facts(state.facts, ruling.facts)
    turns = (
        *state.turns,
        Turn(
            number=state.turn + 1,
            day=state.day,
            input_type=input_type,
            player_input=player_input,
            narration=narration.text,
            outcome=ruling.outcome,
            time_cost=ruling.time_cost,
        ),
    )[-MEMORY_TURNS:]

    ending: str | None = None
    if ruling.ending == "end":
        if ending_allowed(case, state.turn + 1, meters):
            ending = "end"
            events.append("story_ended")
        else:
            events.append("ending_refused")

    elapsed = state.elapsed + ruling.time_cost
    day = state.day
    if ending is None and case.clock is not None and elapsed >= case.clock.units_per_day:
        if case.clock.loops:
            elapsed -= case.clock.units_per_day
            day += 1
            meters = _reset_meters(case, meters)
            events.append("day_reset")
        else:
            elapsed = case.clock.units_per_day
            events.append("day_closed")

    next_state = replace(
        state,
        turn=state.turn + 1,
        day=day,
        elapsed=elapsed,
        meters=meters,
        facts=facts,
        turns=turns,
        ending=ending,
    )
    return next_state, tuple(events)
