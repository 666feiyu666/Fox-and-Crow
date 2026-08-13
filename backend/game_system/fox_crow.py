from __future__ import annotations

from dataclasses import dataclass, replace
from enum import Enum
from typing import Any

try:
    from backend.game_system.state import (
        DayOutcome,
        GameState,
        ItemState,
        MAX_FOX_HUNGER,
        RelationshipState,
        advance_time,
        remember_fox,
        reset_for_next_loop,
    )
except ModuleNotFoundError:  # Support direct execution through backend/server.py.
    from game_system.state import (  # type: ignore[no-redef]
        DayOutcome,
        GameState,
        ItemState,
        MAX_FOX_HUNGER,
        RelationshipState,
        advance_time,
        remember_fox,
        reset_for_next_loop,
    )


CROW_PROBLEM_MEMORY = "The crow lost a treasured necklace in the bushes."
CROW_GAZE_KNOWLEDGE = "The crow repeatedly glances anxiously toward the bushes."
NECKLACE_FOUND_MEMORY = "You found the crow's necklace in the bushes."
NECKLACE_RETURNED_MEMORY = "You returned the necklace, and the crow answered your help with friendship."


class FoxCrowRuleError(ValueError):
    pass


class FoxCrowIntent(str, Enum):
    ASK_PROBLEM = "ask_problem"
    SEARCH_NECKLACE = "search_necklace"
    RETURN_NECKLACE = "return_necklace"
    OTHER = "other"


class FoxCrowEvent(str, Enum):
    CROW_REVEALS_PROBLEM = "crow_reveals_problem"
    FOX_LEARNS_SEARCH_LOCATION = "fox_learns_search_location"
    NECKLACE_ALREADY_HELD = "necklace_already_held"
    NECKLACE_ALREADY_RETURNED = "necklace_already_returned"
    FOX_SEARCHES_BUSHES = "fox_searches_bushes"
    SEARCH_INCONCLUSIVE = "search_inconclusive"
    FOX_FINDS_NECKLACE = "fox_finds_necklace"
    FOX_CARRIES_NECKLACE = "fox_carries_necklace"
    RETURN_REQUIRES_POSSESSION = "return_requires_possession"
    FOX_RETURNS_NECKLACE = "fox_returns_necklace"
    CROW_RECIPROCATES_FRIENDSHIP = "crow_reciprocates_friendship"
    DAY_ENDS_WITHOUT_REWIND = "day_ends_without_rewind"
    TIME_PASSES_HUNGRIER = "time_passes_hungrier"
    DAY_REWINDS = "day_rewinds"


FOX_CROW_EVENT_DESCRIPTION = {
    FoxCrowEvent.CROW_REVEALS_PROBLEM: (
        "The crow admits that a treasured necklace fell into the bushes."
    ),
    FoxCrowEvent.FOX_LEARNS_SEARCH_LOCATION: "You now know where to search.",
    FoxCrowEvent.NECKLACE_ALREADY_HELD: (
        "The necklace is already safe in your possession."
    ),
    FoxCrowEvent.NECKLACE_ALREADY_RETURNED: (
        "The necklace has already been returned to the crow."
    ),
    FoxCrowEvent.FOX_SEARCHES_BUSHES: "You search through the bushes.",
    FoxCrowEvent.SEARCH_INCONCLUSIVE: "The search turns up nothing conclusive.",
    FoxCrowEvent.FOX_FINDS_NECKLACE: (
        "You follow the clue into the bushes and find the crow's necklace."
    ),
    FoxCrowEvent.FOX_CARRIES_NECKLACE: "You now carry the necklace.",
    FoxCrowEvent.RETURN_REQUIRES_POSSESSION: (
        "You cannot return something you do not possess."
    ),
    FoxCrowEvent.FOX_RETURNS_NECKLACE: "You return the necklace to the crow.",
    FoxCrowEvent.CROW_RECIPROCATES_FRIENDSHIP: (
        "The crow shares her food in return, and your mutual trust becomes friendship."
    ),
    FoxCrowEvent.DAY_ENDS_WITHOUT_REWIND: (
        "The day reaches its end without rewinding."
    ),
    FoxCrowEvent.TIME_PASSES_HUNGRIER: "Time passes, and you feel hungrier.",
    FoxCrowEvent.DAY_REWINDS: (
        "The day rewinds to the same morning, while you keep what you learned."
    ),
}


@dataclass(frozen=True)
class GameAgentDecision:
    intent: FoxCrowIntent
    time_cost: int


@dataclass(frozen=True)
class FoxCrowResolution:
    state: GameState
    outcome: DayOutcome
    intent: FoxCrowIntent
    events: tuple[FoxCrowEvent, ...]


def parse_game_agent_decision(payload: Any, state: GameState) -> GameAgentDecision:
    if not isinstance(payload, dict) or set(payload) != {"intent", "timeCost"}:
        raise FoxCrowRuleError("Game Agent decision must contain only intent and timeCost.")

    try:
        intent = FoxCrowIntent(payload["intent"])
    except (TypeError, ValueError) as error:
        supported = ", ".join(intent.value for intent in FoxCrowIntent)
        raise FoxCrowRuleError(
            f"Unsupported Game Agent intent; expected one of: {supported}."
        ) from error

    time_cost = payload["timeCost"]
    remaining = state.day.world.remaining_time_units
    if isinstance(time_cost, bool) or not isinstance(time_cost, int):
        raise FoxCrowRuleError("timeCost must be an integer.")
    if not 1 <= time_cost <= remaining:
        raise FoxCrowRuleError("timeCost must fit within the time remaining today.")
    return GameAgentDecision(intent=intent, time_cost=time_cost)


def resolve_fox_crow_turn(
    state: GameState,
    decision: GameAgentDecision,
) -> FoxCrowResolution:
    if decision.intent is FoxCrowIntent.ASK_PROBLEM:
        return _ask_about_problem(state, decision)
    if decision.intent is FoxCrowIntent.SEARCH_NECKLACE:
        return _search_for_necklace(state, decision)
    if decision.intent is FoxCrowIntent.RETURN_NECKLACE:
        return _return_necklace(state, decision)
    return _other_action(state, decision)


def game_agent_view(state: GameState) -> dict[str, Any]:
    necklace = _world_item(state, "crow_necklace")
    if necklace.owner == "fox":
        necklace_status = "found"
    elif necklace.owner == "crow":
        necklace_status = "returned"
    else:
        necklace_status = "lost"

    return {
        "loopCount": state.loop.loop_count,
        "remainingTime": state.day.world.remaining_time_units,
        "fox": {
            "hunger": state.day.fox.hunger,
            "location": state.day.fox.location,
            "inventory": list(state.day.fox.inventory),
        },
        "crow": {
            "trust": state.day.crow.trust,
            "location": state.day.crow.location,
            "problemRevealed": state.day.crow.problem_revealed,
            "inventory": list(state.day.crow.inventory),
        },
        "relationship": {
            "supportiveActions": state.day.relationship.supportive_actions,
            "reciprocalActions": state.day.relationship.reciprocal_actions,
            "unresolvedBetrayal": state.day.relationship.unresolved_betrayal,
        },
        "necklace": {
            "status": necklace_status,
            "location": necklace.location,
            "owner": necklace.owner,
        },
        "memories": list(state.loop.fox_memories),
    }


def player_view(state: GameState) -> dict[str, Any]:
    """Return only information the fox can already perceive or remember."""
    return {
        "loopCount": state.loop.loop_count,
        "memories": list(state.loop.fox_memories),
    }


def story_agent_view(state: GameState) -> dict[str, Any]:
    """Describe only the scene, condition, and knowledge available to the fox."""
    hunger = state.day.fox.hunger
    if hunger >= 90:
        condition = "very hungry"
    elif hunger >= 60:
        condition = "hungry"
    else:
        condition = "not very hungry"

    return {
        "visibleScene": {
            "foxLocation": state.day.fox.location.replace("_", " "),
            "surroundings": [
                "The crow is perched on a high branch with a piece of cheese.",
                CROW_GAZE_KNOWLEDGE,
            ],
        },
        "foxCondition": condition,
        "foxKnowledge": list(state.loop.fox_memories),
    }


def public_event_view(resolution: FoxCrowResolution) -> list[dict[str, str]]:
    """Expose confirmed public events from the historical Node 2 rules."""
    return [
        {
            "event": event.value,
            "description": FOX_CROW_EVENT_DESCRIPTION[event],
        }
        for event in resolution.events
    ]


def _ask_about_problem(
    state: GameState,
    decision: GameAgentDecision,
) -> FoxCrowResolution:
    first_reveal = not state.day.crow.problem_revealed
    trust_gain = 1 if first_reveal else 0
    crow = replace(
        state.day.crow,
        problem_revealed=True,
        trust=min(5, state.day.crow.trust + trust_gain),
    )
    next_state = replace(state, day=replace(state.day, crow=crow))
    next_state = remember_fox(next_state, CROW_PROBLEM_MEMORY)
    events = (
        FoxCrowEvent.CROW_REVEALS_PROBLEM,
        FoxCrowEvent.FOX_LEARNS_SEARCH_LOCATION,
    )
    return _advance_and_finish(next_state, decision, events, hunger_per_unit=5)


def _search_for_necklace(
    state: GameState,
    decision: GameAgentDecision,
) -> FoxCrowResolution:
    necklace = _world_item(state, "crow_necklace")
    knows_location = (
        state.day.crow.problem_revealed
        or CROW_PROBLEM_MEMORY in state.loop.fox_memories
    )

    if necklace.owner == "fox":
        events = (FoxCrowEvent.NECKLACE_ALREADY_HELD,)
        return _advance_and_finish(state, decision, events, hunger_per_unit=5)
    if necklace.owner == "crow":
        events = (FoxCrowEvent.NECKLACE_ALREADY_RETURNED,)
        return _advance_and_finish(state, decision, events, hunger_per_unit=5)
    if not knows_location:
        events = (
            FoxCrowEvent.FOX_SEARCHES_BUSHES,
            FoxCrowEvent.SEARCH_INCONCLUSIVE,
        )
        return _advance_and_finish(state, decision, events, hunger_per_unit=5)

    fox_inventory = _append_unique(state.day.fox.inventory, necklace.id)
    fox = replace(state.day.fox, location="bushes", inventory=fox_inventory)
    found_necklace = replace(necklace, owner="fox", location="bushes")
    world = replace(
        state.day.world,
        items=_replace_item(state.day.world.items, found_necklace),
    )
    next_state = replace(state, day=replace(state.day, fox=fox, world=world))
    next_state = remember_fox(next_state, NECKLACE_FOUND_MEMORY)
    events = (
        FoxCrowEvent.FOX_FINDS_NECKLACE,
        FoxCrowEvent.FOX_CARRIES_NECKLACE,
    )
    return _advance_and_finish(next_state, decision, events, hunger_per_unit=5)


def _return_necklace(
    state: GameState,
    decision: GameAgentDecision,
) -> FoxCrowResolution:
    necklace = _world_item(state, "crow_necklace")
    if necklace.owner != "fox" or necklace.id not in state.day.fox.inventory:
        events = (FoxCrowEvent.RETURN_REQUIRES_POSSESSION,)
        return _advance_and_finish(state, decision, events, hunger_per_unit=5)

    fox = replace(
        state.day.fox,
        location="tree",
        inventory=tuple(item for item in state.day.fox.inventory if item != necklace.id),
    )
    crow = replace(
        state.day.crow,
        trust=min(5, state.day.crow.trust + 2),
        inventory=_append_unique(state.day.crow.inventory, necklace.id),
    )
    relationship = RelationshipState(
        supportive_actions=state.day.relationship.supportive_actions + 1,
        reciprocal_actions=state.day.relationship.reciprocal_actions + 1,
        unresolved_betrayal=False,
    )
    returned_necklace = replace(necklace, owner="crow", location="tree")
    world = replace(
        state.day.world,
        items=_replace_item(state.day.world.items, returned_necklace),
    )
    next_state = replace(
        state,
        day=replace(
            state.day,
            fox=fox,
            crow=crow,
            relationship=relationship,
            world=world,
        ),
    )
    next_state = remember_fox(next_state, NECKLACE_RETURNED_MEMORY)
    final_decision = replace(
        decision,
        time_cost=next_state.day.world.remaining_time_units,
    )
    events = (
        FoxCrowEvent.FOX_RETURNS_NECKLACE,
        FoxCrowEvent.CROW_RECIPROCATES_FRIENDSHIP,
        FoxCrowEvent.DAY_ENDS_WITHOUT_REWIND,
    )
    return _advance_and_finish(next_state, final_decision, events, hunger_per_unit=0)


def _other_action(state: GameState, decision: GameAgentDecision) -> FoxCrowResolution:
    events = (FoxCrowEvent.TIME_PASSES_HUNGRIER,)
    return _advance_and_finish(state, decision, events, hunger_per_unit=5)


def _advance_and_finish(
    state: GameState,
    decision: GameAgentDecision,
    events: tuple[FoxCrowEvent, ...],
    *,
    hunger_per_unit: int,
) -> FoxCrowResolution:
    result = advance_time(
        state,
        time_cost=decision.time_cost,
        hunger_increase=min(
            MAX_FOX_HUNGER - state.day.fox.hunger,
            hunger_per_unit * decision.time_cost,
        ),
    )
    next_state = result.state
    next_events = events
    if result.outcome in {DayOutcome.FOX_STARVED, DayOutcome.LOOP_RESET}:
        next_state = reset_for_next_loop(next_state)
        next_events += (FoxCrowEvent.DAY_REWINDS,)
    return FoxCrowResolution(
        state=next_state,
        outcome=result.outcome,
        intent=decision.intent,
        events=next_events,
    )


def _world_item(state: GameState, item_id: str) -> ItemState:
    for item in state.day.world.items:
        if item.id == item_id:
            return item
    raise FoxCrowRuleError(f"Required world item is missing: {item_id}.")


def _replace_item(items: tuple[ItemState, ...], updated: ItemState) -> tuple[ItemState, ...]:
    return tuple(updated if item.id == updated.id else item for item in items)


def _append_unique(items: tuple[str, ...], item_id: str) -> tuple[str, ...]:
    return items if item_id in items else items + (item_id,)
