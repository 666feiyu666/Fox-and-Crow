from __future__ import annotations

from dataclasses import dataclass, replace
from enum import Enum


TOTAL_DAY_UNITS = 6
INITIAL_FOX_HUNGER = 70
MAX_FOX_HUNGER = 100
FRIENDSHIP_TRUST_THRESHOLD = 3
WORLD_SEED = "fox-crow-loop-v1"


class StateTransitionError(ValueError):
    pass


class DayOutcome(str, Enum):
    ACTIVE = "active"
    FOX_STARVED = "fox_starved"
    LOOP_RESET = "loop_reset"
    LOOP_ESCAPED = "loop_escaped"


@dataclass(frozen=True)
class FoxState:
    hunger: int = INITIAL_FOX_HUNGER
    alive: bool = True
    location: str = "clearing"
    inventory: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if not 0 <= self.hunger <= MAX_FOX_HUNGER:
            raise ValueError("Fox hunger must stay between 0 and 100.")


@dataclass(frozen=True)
class CrowState:
    trust: int = 0
    location: str = "tree"
    inventory: tuple[str, ...] = ("crow_cheese",)

    def __post_init__(self) -> None:
        if not -5 <= self.trust <= 5:
            raise ValueError("Crow trust must stay between -5 and 5.")


@dataclass(frozen=True)
class RelationshipState:
    supportive_actions: int = 0
    reciprocal_actions: int = 0
    unresolved_betrayal: bool = False

    def __post_init__(self) -> None:
        if self.supportive_actions < 0 or self.reciprocal_actions < 0:
            raise ValueError("Relationship action counts cannot be negative.")


@dataclass(frozen=True)
class LocationState:
    id: str
    food_opportunities_remaining: int

    def __post_init__(self) -> None:
        if self.food_opportunities_remaining < 0:
            raise ValueError("Food opportunities cannot be negative.")


@dataclass(frozen=True)
class ItemState:
    id: str
    kind: str
    location: str
    owner: str | None


@dataclass(frozen=True)
class WorldState:
    elapsed_time_units: int = 0
    locations: tuple[LocationState, ...] = (
        LocationState("clearing", 0),
        LocationState("tree", 0),
        LocationState("forest_edge", 1),
        LocationState("stream_bank", 1),
    )
    items: tuple[ItemState, ...] = (
        ItemState("crow_cheese", "food", "tree", "crow"),
    )

    def __post_init__(self) -> None:
        if not 0 <= self.elapsed_time_units <= TOTAL_DAY_UNITS:
            raise ValueError(f"Elapsed time must stay between 0 and {TOTAL_DAY_UNITS}.")
        location_ids = [location.id for location in self.locations]
        item_ids = [item.id for item in self.items]
        if len(location_ids) != len(set(location_ids)):
            raise ValueError("World location IDs must be unique.")
        if len(item_ids) != len(set(item_ids)):
            raise ValueError("World item IDs must be unique.")

    @property
    def remaining_time_units(self) -> int:
        return TOTAL_DAY_UNITS - self.elapsed_time_units


@dataclass(frozen=True)
class DayState:
    fox: FoxState = FoxState()
    crow: CrowState = CrowState()
    relationship: RelationshipState = RelationshipState()
    world: WorldState = WorldState()

    def __post_init__(self) -> None:
        locations = {location.id for location in self.world.locations}
        items = {item.id: item for item in self.world.items}
        if self.fox.location not in locations or self.crow.location not in locations:
            raise ValueError("Every character must occupy a known world location.")
        if any(item.location not in locations for item in self.world.items):
            raise ValueError("Every item must occupy a known world location.")

        fox_items = set(self.fox.inventory)
        crow_items = set(self.crow.inventory)
        if fox_items & crow_items:
            raise ValueError("An item cannot be held by both characters.")
        if not (fox_items | crow_items) <= items.keys():
            raise ValueError("Character inventories may only reference known world items.")

        for item in self.world.items:
            expected_owner = (
                "fox" if item.id in fox_items else "crow" if item.id in crow_items else None
            )
            if item.owner != expected_owner:
                raise ValueError("Item ownership must match character inventories.")
            if item.owner == "fox" and item.location != self.fox.location:
                raise ValueError("A fox-owned item must share the fox's location.")
            if item.owner == "crow" and item.location != self.crow.location:
                raise ValueError("A crow-owned item must share the crow's location.")


@dataclass(frozen=True)
class LoopState:
    loop_count: int = 0
    fox_memories: tuple[str, ...] = ()
    learned_actions: tuple[str, ...] = ()
    world_seed: str = WORLD_SEED

    def __post_init__(self) -> None:
        if self.loop_count < 0:
            raise ValueError("Loop count cannot be negative.")


@dataclass(frozen=True)
class GameState:
    day: DayState = DayState()
    loop: LoopState = LoopState()


@dataclass(frozen=True)
class TurnResult:
    state: GameState
    outcome: DayOutcome


def initial_game_state() -> GameState:
    return GameState()


def friendship_established(day: DayState) -> bool:
    relationship = day.relationship
    return (
        day.crow.trust >= FRIENDSHIP_TRUST_THRESHOLD
        and relationship.supportive_actions >= 1
        and relationship.reciprocal_actions >= 1
        and not relationship.unresolved_betrayal
    )


def evaluate_day(state: GameState) -> DayOutcome:
    if not state.day.fox.alive or state.day.fox.hunger >= MAX_FOX_HUNGER:
        return DayOutcome.FOX_STARVED
    if state.day.world.remaining_time_units == 0:
        if friendship_established(state.day):
            return DayOutcome.LOOP_ESCAPED
        return DayOutcome.LOOP_RESET
    return DayOutcome.ACTIVE


def advance_time(
    state: GameState,
    *,
    time_cost: int,
    hunger_increase: int,
) -> TurnResult:
    if evaluate_day(state) is not DayOutcome.ACTIVE:
        raise StateTransitionError("A finished day cannot accept another action.")
    if isinstance(time_cost, bool) or not isinstance(time_cost, int) or time_cost < 1:
        raise StateTransitionError("Every action must consume at least one time unit.")
    if (
        isinstance(hunger_increase, bool)
        or not isinstance(hunger_increase, int)
        or hunger_increase < 0
    ):
        raise StateTransitionError("Hunger increase must be a non-negative integer.")

    elapsed_time = min(
        TOTAL_DAY_UNITS,
        state.day.world.elapsed_time_units + time_cost,
    )
    hunger = min(MAX_FOX_HUNGER, state.day.fox.hunger + hunger_increase)
    fox = replace(state.day.fox, hunger=hunger, alive=hunger < MAX_FOX_HUNGER)
    world = replace(state.day.world, elapsed_time_units=elapsed_time)
    next_state = replace(state, day=replace(state.day, fox=fox, world=world))
    return TurnResult(state=next_state, outcome=evaluate_day(next_state))


def remember_fox(state: GameState, memory: str) -> GameState:
    normalized = " ".join(memory.split())
    if not normalized:
        raise StateTransitionError("A fox memory cannot be empty.")
    if normalized in state.loop.fox_memories:
        return state
    loop = replace(state.loop, fox_memories=state.loop.fox_memories + (normalized,))
    return replace(state, loop=loop)


def learn_action(state: GameState, action_key: str) -> GameState:
    normalized = " ".join(action_key.split()).casefold()
    if not normalized:
        raise StateTransitionError("A learned action key cannot be empty.")
    if normalized in state.loop.learned_actions:
        return state
    loop = replace(state.loop, learned_actions=state.loop.learned_actions + (normalized,))
    return replace(state, loop=loop)


def reset_for_next_loop(state: GameState) -> GameState:
    outcome = evaluate_day(state)
    if outcome not in {DayOutcome.FOX_STARVED, DayOutcome.LOOP_RESET}:
        raise StateTransitionError("Only a failed or expired day can reset the loop.")
    loop = replace(state.loop, loop_count=state.loop.loop_count + 1)
    return GameState(day=DayState(), loop=loop)
