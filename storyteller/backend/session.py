"""Transactional story updates, player knowledge and inspectable turn history."""

from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Any, Literal

from backend.case import Case
from backend.space import (
    ContractError, Event, Fact, Observation, WritingBrief, array, flag, obj, text, texts, unique,
)
from backend.understanding import Understanding

InputType = Literal["say", "do"]
OUTCOMES = frozenset({"success", "partial", "failure", "blocked"})
MEMORY_TURNS = 8


class RulingError(ContractError):
    """A ruling the runtime cannot accept."""


@dataclass(frozen=True)
class Ruling:
    intent: str
    outcome: str
    events: tuple[Event, ...]
    expansions: tuple[Fact, ...]
    changes: tuple[Fact, ...]
    observations: tuple[Observation, ...]
    memories: tuple[str, ...]
    brief: WritingBrief
    restart: bool = False
    ending: bool = False

    @classmethod
    def from_dict(cls, payload: Any) -> "Ruling":
        try:
            payload = obj(payload, "ruling")
            outcome = payload.get("outcome")
            if not isinstance(outcome, str) or outcome not in OUTCOMES:
                raise ContractError(f"Unknown outcome: {outcome!r}.")
            restart = flag(payload.get("restart", False), "restart")
            ending = flag(payload.get("ending", False), "ending")
            if restart and ending:
                raise ContractError("A turn cannot both restart the loop and end it.")
            brief = WritingBrief.from_dict(payload.get("brief"))
            if (brief.mode == "return") != restart or (brief.mode == "ending") != ending:
                raise ContractError("The writing mode must agree with restart and ending.")
            events = tuple(Event.from_dict(item) for item in
                           array(payload.get("events"), "events", 8))
            if not any("player" in event.observers for event in events):
                raise ContractError("A ruling needs a player-perceptible event.")
            return cls(
                intent=text(payload.get("intent"), "intent"),
                outcome=outcome, events=events,
                expansions=unique((Fact.from_dict(item) for item in
                                   array(payload.get("expansions", []), "expansions", 6)),
                                  "expansions"),
                changes=unique((Fact.from_dict(item) for item in
                                array(payload.get("changes", []), "changes", 8)), "changes"),
                observations=tuple(Observation.from_dict(item) for item in
                                   array(payload.get("observations", []), "observations", 16)),
                memories=texts(payload.get("memories", []), "memories", 3),
                brief=brief, restart=restart, ending=ending,
            )
        except ContractError as error:
            raise RulingError(str(error)) from error

    def to_dict(self) -> dict:
        return {"intent": self.intent, "outcome": self.outcome,
                "events": [item.to_dict() for item in self.events],
                "expansions": [item.to_dict() for item in self.expansions],
                "changes": [item.to_dict() for item in self.changes],
                "observations": [item.to_dict() for item in self.observations],
                "memories": list(self.memories), "brief": self.brief.to_dict(),
                "restart": self.restart, "ending": self.ending}


@dataclass(frozen=True)
class Narration:
    text: str
    hints: tuple[str, ...] = ()

    @classmethod
    def from_dict(cls, payload: Any) -> "Narration":
        try:
            payload = obj(payload, "narration")
            # Suggestions are optional; do not pad a quiet or final turn with choices.
            hints = array(payload.get("hints", []), "hints")[:3]
            return cls(text(payload.get("narration"), "narration", 3000),
                       texts(hints, "hints", 3))
        except ContractError as error:
            raise RulingError(str(error)) from error


def merge_facts(*groups: tuple[Fact, ...]) -> tuple[Fact, ...]:
    """A stable key names one current property; later values replace earlier ones."""
    merged = {}
    for group in groups:
        for fact in group:
            merged[fact.key] = fact
    return tuple(merged.values())


def project_facts(
    current: tuple[Fact, ...], fixed_keys: tuple[str, ...], ruling: Ruling,
) -> tuple[Fact, ...]:
    """Validate a proposal before any prose or state mutation."""
    known = {fact.key: fact for fact in current}
    for addition in ruling.expansions:
        if addition.key in known:
            raise RulingError(f"Expansion redefines an established property: {addition.key}.")
        if addition.known_by:
            raise RulingError("Expansions establish world detail; grant knowledge through observations.")
    additions = {fact.key: fact for fact in ruling.expansions}
    if additions.keys() & {fact.key for fact in ruling.changes}:
        raise RulingError("Expand a property or change it in a turn, not both.")
    for change in ruling.changes:
        if change.key in fixed_keys and (
            change.key not in known or change.value != known[change.key].value
        ):
            raise RulingError(f"A fixed property cannot change: {change.key}.")
    projected = {fact.key: fact for fact in merge_facts(current, ruling.expansions, ruling.changes)}
    for observation in ruling.observations:
        if observation.fact_key not in projected:
            raise RulingError(f"Observation refers to an absent fact: {observation.fact_key}.")
        fact = projected[observation.fact_key]
        projected[fact.key] = replace(
            fact, known_by=tuple(dict.fromkeys((*fact.known_by, observation.observer)))
        )
    return tuple(projected.values())


@dataclass(frozen=True)
class Memory:
    loop: int
    text: str

    def to_dict(self) -> dict:
        return {"loop": self.loop, "text": self.text}


@dataclass(frozen=True)
class Turn:
    number: int
    loop: int
    input_type: InputType
    player_input: str
    narration: str
    ruling: Ruling

    def to_dict(self, *, private: bool = False) -> dict:
        value = {"number": self.number, "loop": self.loop, "type": self.input_type,
                 "text": self.player_input, "narration": self.narration}
        if private:
            value["ruling"] = self.ruling.to_dict()
        return value


@dataclass(frozen=True)
class StoryState:
    language: str = "en"
    loop: int = 1
    turn: int = 0
    initial_facts: tuple[Fact, ...] = ()
    fixed_keys: tuple[str, ...] = ()
    world_facts: tuple[Fact, ...] = ()
    loop_facts: tuple[Fact, ...] = ()
    memories: tuple[Memory, ...] = ()
    turns: tuple[Turn, ...] = ()
    ended: bool = False

    @property
    def facts(self) -> tuple[Fact, ...]:
        return merge_facts(self.initial_facts, self.world_facts, self.loop_facts)

    def to_wire(self) -> dict:
        return {"language": self.language, "loop": self.loop,
                "turn": self.turn, "ended": self.ended}

    def to_agent_context(
        self, case: Case, player: str, input_type: InputType, action: str,
        understanding: Understanding | None = None,
    ) -> dict[str, Any]:
        baseline = self.initial_facts
        fixed = self.fixed_keys
        if understanding is not None:
            baseline = understanding.space.initial_facts
            fixed = understanding.space.fixed_keys
        return {
            "case": {"id": case.id, "title": case.title(self.language), "player": player},
            "state": {**self.to_wire(),
                      "initial_facts": [fact.to_dict() for fact in baseline],
                      "world_facts": [fact.to_dict() for fact in self.world_facts],
                      "facts": [fact.to_dict() for fact in
                                merge_facts(baseline, self.world_facts, self.loop_facts)],
                      "fixed_keys": list(fixed),
                      "memories": [item.to_dict() for item in self.memories]},
            "recent_turns": [turn.to_dict() for turn in self.turns[-MEMORY_TURNS:]],
            "opening": understanding.opening if understanding is not None else "",
            "action": {"type": input_type, "text": action},
        }


def initial_state(language: str = "en", understanding: Understanding | None = None) -> StoryState:
    if understanding is None:
        return StoryState(language=language)
    return StoryState(language=language, initial_facts=understanding.space.initial_facts,
                      fixed_keys=understanding.space.fixed_keys)


def validate_ruling(context: dict, ruling: Ruling) -> tuple[Fact, ...]:
    state = context["state"]
    return project_facts(tuple(Fact.from_dict(item) for item in state["facts"]),
                         tuple(state["fixed_keys"]), ruling)


def writer_context(context: dict, ruling: Ruling) -> dict:
    """A staged, player-visible view. Private facts and offscreen events stay out."""
    projected = validate_ruling(context, ruling)
    if ruling.restart:
        projected = merge_facts(
            tuple(Fact.from_dict(item) for item in context["state"]["initial_facts"]),
            tuple(Fact.from_dict(item) for item in context["state"]["world_facts"]),
            ruling.expansions,
        )
    return {
        "case": context["case"],
        "state": {key: context["state"][key] for key in ("language", "loop", "turn")},
        "visible_facts": [fact.to_dict() for fact in projected if "player" in fact.known_by],
        "memories": [*context["state"]["memories"],
                     *({"loop": context["state"]["loop"], "text": item}
                       for item in ruling.memories)],
        "recent_turns": context["recent_turns"],
        "opening": context["opening"],
        "action": context["action"],
        "ruling": {"outcome": ruling.outcome, "restart": ruling.restart, "ending": ruling.ending,
                   "events": [event.text for event in ruling.events if "player" in event.observers],
                   "brief": ruling.brief.to_dict()},
    }


def apply_turn(
    state: StoryState, input_type: InputType, player_input: str,
    ruling: Ruling, narration: Narration,
) -> StoryState:
    """Commit one complete turn. A writer failure never reaches this function."""
    if state.ended:
        raise RulingError("The story has already ended.")
    if input_type not in ("say", "do"):
        raise ValueError(f"Unsupported input type: {input_type!r}.")
    projected = project_facts(state.facts, state.fixed_keys, ruling)
    world = merge_facts(state.world_facts, ruling.expansions)
    baseline_keys = {fact.key for fact in (*state.initial_facts, *world)}
    changed_keys = {fact.key for fact in (*state.loop_facts, *ruling.changes)}
    observed_keys = {item.fact_key for item in ruling.observations}
    # Observations are loop-local overlays; a hidden discovery does not teach an NPC
    # in the next loop. Completing world detail persists, actions and knowledge reset.
    overlays = tuple(fact for fact in projected if
                     fact.key in changed_keys | observed_keys or fact.key not in baseline_keys)
    # Preserve experienced events even when the model omits its optional summary.
    # Keeping the loop number prevents history being mistaken for current truth.
    remembered = [event.text for event in ruling.events if "player" in event.observers]
    remembered.extend(ruling.memories)
    memories = tuple(dict.fromkeys(
        (*state.memories, *(Memory(state.loop, item) for item in remembered))
    ))
    return replace(
        state, loop=state.loop + 1 if ruling.restart else state.loop,
        turn=0 if ruling.restart else state.turn + 1,
        world_facts=world, loop_facts=() if ruling.restart else overlays,
        memories=memories,
        turns=(*state.turns, Turn(state.turn + 1, state.loop, input_type,
                                 player_input, narration.text, ruling)),
        ended=ruling.ending,
    )
