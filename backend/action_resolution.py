from __future__ import annotations

import re
from dataclasses import dataclass
from enum import Enum
from typing import Any

from backend.game_state import (
    MAX_FOX_HUNGER,
    TOTAL_DAY_UNITS,
    DayOutcome,
    GameState,
    evaluate_day,
)


MAX_EFFECTS = 8
MAX_FACTS = 6
MAX_FACT_LENGTH = 240
MAX_TARGET_LENGTH = 80
MAX_ITEM_DESCRIPTION_LENGTH = 80
MAX_HUNGER_REDUCTION = 50
MAX_TRUST_CHANGE = 2
ID_PATTERN = re.compile(r"^[a-z][a-z0-9_]{0,63}$")


class ResolutionValidationError(ValueError):
    pass


class ActionType(str, Enum):
    MOVE = "move"
    SEARCH_FOOD = "search_food"
    EAT = "eat"
    TALK = "talk"
    GIVE = "give"
    TAKE = "take"
    WAIT = "wait"
    OTHER = "other"


class ResolutionOutcome(str, Enum):
    SUCCESS = "success"
    PARTIAL = "partial"
    FAILURE = "failure"
    INVALID = "invalid"


@dataclass(frozen=True)
class ActionIntent:
    action_type: ActionType
    target: str | None


@dataclass(frozen=True)
class MoveFoxEffect:
    location: str


@dataclass(frozen=True)
class MoveCrowEffect:
    location: str


@dataclass(frozen=True)
class AdjustFoxHungerEffect:
    amount: int


@dataclass(frozen=True)
class AdjustCrowTrustEffect:
    amount: int


@dataclass(frozen=True)
class RecordSupportiveActionEffect:
    pass


@dataclass(frozen=True)
class RecordReciprocalActionEffect:
    pass


@dataclass(frozen=True)
class SetBetrayalEffect:
    active: bool


@dataclass(frozen=True)
class FindFoodEffect:
    location: str
    item_id: str
    description: str


@dataclass(frozen=True)
class TransferItemEffect:
    item_id: str
    new_owner: str


@dataclass(frozen=True)
class ConsumeFoodEffect:
    item_id: str


ResolutionEffect = (
    MoveFoxEffect
    | MoveCrowEffect
    | AdjustFoxHungerEffect
    | AdjustCrowTrustEffect
    | RecordSupportiveActionEffect
    | RecordReciprocalActionEffect
    | SetBetrayalEffect
    | FindFoodEffect
    | TransferItemEffect
    | ConsumeFoodEffect
)


@dataclass(frozen=True)
class AgentResolutionProposal:
    intent: ActionIntent
    outcome: ResolutionOutcome
    time_cost: int
    effects: tuple[ResolutionEffect, ...]
    facts: tuple[str, ...]


def parse_resolution_proposal(payload: Any, state: GameState) -> AgentResolutionProposal:
    if evaluate_day(state) is not DayOutcome.ACTIVE:
        raise ResolutionValidationError("A finished day cannot accept an agent proposal.")
    root = _require_object(payload, "Resolution proposal")
    _require_exact_keys(root, {"intent", "outcome", "timeCost", "effects", "facts"})

    intent = _parse_intent(root["intent"])
    outcome = _parse_enum(ResolutionOutcome, root["outcome"], "outcome")
    time_cost = _require_int(root["timeCost"], "timeCost")
    if not 1 <= time_cost <= min(TOTAL_DAY_UNITS, state.day.world.remaining_time_units):
        raise ResolutionValidationError(
            "timeCost must consume between one unit and the time remaining today."
        )

    raw_effects = root["effects"]
    if not isinstance(raw_effects, list):
        raise ResolutionValidationError("effects must be an array.")
    if len(raw_effects) > MAX_EFFECTS:
        raise ResolutionValidationError(f"effects may contain at most {MAX_EFFECTS} entries.")
    effects = _parse_effects(raw_effects, state)

    raw_facts = root["facts"]
    if not isinstance(raw_facts, list) or not 1 <= len(raw_facts) <= MAX_FACTS:
        raise ResolutionValidationError(f"facts must contain between one and {MAX_FACTS} entries.")
    facts = tuple(_require_text(fact, "fact", MAX_FACT_LENGTH) for fact in raw_facts)

    proposal = AgentResolutionProposal(
        intent=intent,
        outcome=outcome,
        time_cost=time_cost,
        effects=effects,
        facts=facts,
    )
    _validate_intent_contract(proposal)
    return proposal


def _parse_intent(payload: Any) -> ActionIntent:
    intent = _require_object(payload, "intent")
    _require_exact_keys(intent, {"actionType", "target"})
    action_type = _parse_enum(ActionType, intent["actionType"], "actionType")
    target = intent["target"]
    if target is not None:
        target = _require_text(target, "target", MAX_TARGET_LENGTH)
    return ActionIntent(action_type=action_type, target=target)


def _parse_effects(raw_effects: list[Any], state: GameState) -> tuple[ResolutionEffect, ...]:
    locations = {
        location.id: location.food_opportunities_remaining
        for location in state.day.world.locations
    }
    items = {
        item.id: {"kind": item.kind, "owner": item.owner}
        for item in state.day.world.items
    }
    fox_location = state.day.fox.location
    fox_hunger = state.day.fox.hunger
    crow_trust = state.day.crow.trust
    effect_types: set[str] = set()
    parsed: list[ResolutionEffect] = []

    for raw_effect in raw_effects:
        effect = _require_object(raw_effect, "effect")
        effect_type = effect.get("type")
        if not isinstance(effect_type, str):
            raise ResolutionValidationError("Every effect must include a string type.")
        if effect_type in effect_types:
            raise ResolutionValidationError(f"Effect type may appear only once: {effect_type}.")
        effect_types.add(effect_type)

        if effect_type == "move_fox":
            _require_exact_keys(effect, {"type", "location"})
            location = _require_identifier(effect["location"], "location")
            if location not in locations:
                raise ResolutionValidationError(f"Unknown world location: {location}.")
            fox_location = location
            parsed.append(MoveFoxEffect(location=location))
        elif effect_type == "move_crow":
            _require_exact_keys(effect, {"type", "location"})
            location = _require_identifier(effect["location"], "location")
            if location not in locations:
                raise ResolutionValidationError(f"Unknown world location: {location}.")
            parsed.append(MoveCrowEffect(location=location))
        elif effect_type == "adjust_fox_hunger":
            _require_exact_keys(effect, {"type", "amount"})
            amount = _require_int(effect["amount"], "amount")
            if not -MAX_HUNGER_REDUCTION <= amount <= -1:
                raise ResolutionValidationError(
                    "adjust_fox_hunger may only reduce hunger by 1 to "
                    f"{MAX_HUNGER_REDUCTION}; time-based hunger is controlled by code."
                )
            fox_hunger += amount
            if not 0 <= fox_hunger <= MAX_FOX_HUNGER:
                raise ResolutionValidationError("The proposed hunger change leaves valid bounds.")
            parsed.append(AdjustFoxHungerEffect(amount=amount))
        elif effect_type == "adjust_crow_trust":
            _require_exact_keys(effect, {"type", "amount"})
            amount = _require_int(effect["amount"], "amount")
            if amount == 0 or not -MAX_TRUST_CHANGE <= amount <= MAX_TRUST_CHANGE:
                raise ResolutionValidationError(
                    f"Crow trust may change by at most {MAX_TRUST_CHANGE} per action."
                )
            crow_trust += amount
            if not -5 <= crow_trust <= 5:
                raise ResolutionValidationError("The proposed crow trust change leaves valid bounds.")
            parsed.append(AdjustCrowTrustEffect(amount=amount))
        elif effect_type == "record_supportive_action":
            _require_exact_keys(effect, {"type"})
            parsed.append(RecordSupportiveActionEffect())
        elif effect_type == "record_reciprocal_action":
            _require_exact_keys(effect, {"type"})
            parsed.append(RecordReciprocalActionEffect())
        elif effect_type == "set_betrayal":
            _require_exact_keys(effect, {"type", "active"})
            if not isinstance(effect["active"], bool):
                raise ResolutionValidationError("set_betrayal.active must be a boolean.")
            parsed.append(SetBetrayalEffect(active=effect["active"]))
        elif effect_type == "find_food":
            _require_exact_keys(effect, {"type", "location", "itemId", "description"})
            location = _require_identifier(effect["location"], "location")
            item_id = _require_identifier(effect["itemId"], "itemId")
            description = _require_text(
                effect["description"], "description", MAX_ITEM_DESCRIPTION_LENGTH
            )
            if location not in locations:
                raise ResolutionValidationError(f"Unknown world location: {location}.")
            if fox_location != location:
                raise ResolutionValidationError("The fox must be at a location before finding food there.")
            if locations[location] < 1:
                raise ResolutionValidationError(f"No food opportunities remain at {location}.")
            if item_id in items:
                raise ResolutionValidationError(f"World item ID already exists: {item_id}.")
            locations[location] -= 1
            items[item_id] = {"kind": "food", "owner": "fox"}
            parsed.append(
                FindFoodEffect(location=location, item_id=item_id, description=description)
            )
        elif effect_type == "transfer_item":
            _require_exact_keys(effect, {"type", "itemId", "newOwner"})
            item_id = _require_identifier(effect["itemId"], "itemId")
            new_owner = effect["newOwner"]
            if new_owner not in {"fox", "crow"}:
                raise ResolutionValidationError("newOwner must be fox or crow.")
            if item_id not in items:
                raise ResolutionValidationError(f"Unknown world item: {item_id}.")
            if items[item_id]["owner"] == new_owner:
                raise ResolutionValidationError(f"{item_id} is already owned by {new_owner}.")
            items[item_id]["owner"] = new_owner
            parsed.append(TransferItemEffect(item_id=item_id, new_owner=new_owner))
        elif effect_type == "consume_food":
            _require_exact_keys(effect, {"type", "itemId"})
            item_id = _require_identifier(effect["itemId"], "itemId")
            item = items.get(item_id)
            if item is None:
                raise ResolutionValidationError(f"Unknown world item: {item_id}.")
            if item["kind"] != "food" or item["owner"] != "fox":
                raise ResolutionValidationError("The fox may consume only food it currently owns.")
            del items[item_id]
            parsed.append(ConsumeFoodEffect(item_id=item_id))
        else:
            raise ResolutionValidationError(f"Unsupported effect type: {effect_type}.")

    return tuple(parsed)


def _validate_intent_contract(proposal: AgentResolutionProposal) -> None:
    effect_types = {type(effect) for effect in proposal.effects}
    if proposal.outcome is ResolutionOutcome.INVALID and proposal.effects:
        raise ResolutionValidationError("An invalid action cannot change world state.")
    if proposal.intent.action_type is ActionType.WAIT and proposal.effects:
        raise ResolutionValidationError("Waiting may advance time but cannot submit state effects.")
    if proposal.outcome is not ResolutionOutcome.SUCCESS:
        return

    required_effects: dict[ActionType, set[type[Any]]] = {
        ActionType.MOVE: {MoveFoxEffect},
        ActionType.SEARCH_FOOD: {FindFoodEffect},
        ActionType.EAT: {ConsumeFoodEffect, AdjustFoxHungerEffect},
        ActionType.GIVE: {TransferItemEffect},
        ActionType.TAKE: {TransferItemEffect},
    }
    required = required_effects.get(proposal.intent.action_type, set())
    if not required <= effect_types:
        missing = ", ".join(sorted(effect.__name__ for effect in required - effect_types))
        raise ResolutionValidationError(
            f"A successful {proposal.intent.action_type.value} action is missing: {missing}."
        )


def _require_object(value: Any, label: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ResolutionValidationError(f"{label} must be an object.")
    return value


def _require_exact_keys(value: dict[str, Any], expected: set[str]) -> None:
    actual = set(value)
    if actual != expected:
        missing = sorted(expected - actual)
        extra = sorted(actual - expected)
        details = []
        if missing:
            details.append("missing " + ", ".join(missing))
        if extra:
            details.append("unsupported " + ", ".join(extra))
        raise ResolutionValidationError("Object keys are invalid: " + "; ".join(details) + ".")


def _require_int(value: Any, label: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise ResolutionValidationError(f"{label} must be an integer.")
    return value


def _require_text(value: Any, label: str, maximum_length: int) -> str:
    if not isinstance(value, str):
        raise ResolutionValidationError(f"{label} must be a string.")
    normalized = " ".join(value.split())
    if not normalized or len(normalized) > maximum_length:
        raise ResolutionValidationError(
            f"{label} must contain between 1 and {maximum_length} characters."
        )
    return normalized


def _require_identifier(value: Any, label: str) -> str:
    if not isinstance(value, str) or ID_PATTERN.fullmatch(value) is None:
        raise ResolutionValidationError(
            f"{label} must be a lowercase identifier using letters, numbers, and underscores."
        )
    return value


def _parse_enum(enum_type: type[Enum], value: Any, label: str) -> Any:
    if not isinstance(value, str):
        raise ResolutionValidationError(f"{label} must be a string.")
    try:
        return enum_type(value)
    except ValueError as error:
        supported = ", ".join(member.value for member in enum_type)
        raise ResolutionValidationError(f"Unsupported {label}; expected one of: {supported}.") from error
