import unittest
from dataclasses import replace

from backend.game_agent.effects import (
    ActionType,
    AdjustFoxHungerEffect,
    ConsumeFoodEffect,
    FindFoodEffect,
    MoveCrowEffect,
    MoveFoxEffect,
    ResolutionOutcome,
    ResolutionValidationError,
    parse_resolution_proposal,
)
from backend.game_system.state import (
    TOTAL_DAY_UNITS,
    DayState,
    FoxState,
    WorldState,
    advance_time,
    initial_game_state,
)


def proposal(**overrides):
    payload = {
        "intent": {"actionType": "wait", "target": None},
        "outcome": "success",
        "timeCost": 1,
        "effects": [],
        "facts": ["The fox waits while the day moves forward."],
    }
    payload.update(overrides)
    return payload


class ActionResolutionTests(unittest.TestCase):
    def test_valid_search_can_move_then_find_one_world_item(self):
        payload = proposal(
            intent={"actionType": "search_food", "target": "forest_edge"},
            timeCost=2,
            effects=[
                {"type": "move_fox", "location": "forest_edge"},
                {
                    "type": "find_food",
                    "location": "forest_edge",
                    "itemId": "forest_berries",
                    "description": "a handful of ripe berries",
                },
            ],
            facts=["The fox reaches the forest edge and finds ripe berries."],
        )

        parsed = parse_resolution_proposal(payload, initial_game_state())

        self.assertEqual(parsed.intent.action_type, ActionType.SEARCH_FOOD)
        self.assertEqual(parsed.outcome, ResolutionOutcome.SUCCESS)
        self.assertEqual(parsed.time_cost, 2)
        self.assertEqual(parsed.effects[0], MoveFoxEffect(location="forest_edge"))
        self.assertIsInstance(parsed.effects[1], FindFoodEffect)

    def test_wait_is_valid_without_state_effects(self):
        parsed = parse_resolution_proposal(proposal(), initial_game_state())

        self.assertEqual(parsed.intent.action_type, ActionType.WAIT)
        self.assertEqual(parsed.effects, ())

    def test_agent_may_move_the_crow_to_a_known_location(self):
        payload = proposal(
            intent={"actionType": "talk", "target": "crow"},
            effects=[{"type": "move_crow", "location": "clearing"}],
            facts=["The crow glides down into the clearing."],
        )

        parsed = parse_resolution_proposal(payload, initial_game_state())

        self.assertEqual(parsed.effects, (MoveCrowEffect(location="clearing"),))

    def test_extra_terminal_or_friendship_fields_are_rejected(self):
        payload = proposal(friendship=True)

        with self.assertRaisesRegex(ResolutionValidationError, "unsupported friendship"):
            parse_resolution_proposal(payload, initial_game_state())

        payload = proposal(effects=[{"type": "set_friendship", "active": True}])
        with self.assertRaisesRegex(ResolutionValidationError, "Unsupported effect type"):
            parse_resolution_proposal(payload, initial_game_state())

    def test_action_must_consume_available_time(self):
        with self.assertRaisesRegex(ResolutionValidationError, "time remaining"):
            parse_resolution_proposal(proposal(timeCost=0), initial_game_state())

        expired = advance_time(
            initial_game_state(),
            time_cost=TOTAL_DAY_UNITS,
            hunger_increase=0,
        ).state
        with self.assertRaisesRegex(ResolutionValidationError, "finished day"):
            parse_resolution_proposal(proposal(), expired)

    def test_unknown_or_depleted_search_location_is_rejected(self):
        unknown = proposal(
            intent={"actionType": "search_food", "target": "moon"},
            effects=[
                {"type": "move_fox", "location": "moon"},
                {
                    "type": "find_food",
                    "location": "moon",
                    "itemId": "moon_food",
                    "description": "impossible food",
                },
            ],
        )
        with self.assertRaisesRegex(ResolutionValidationError, "Unknown world location"):
            parse_resolution_proposal(unknown, initial_game_state())

        depleted = proposal(
            intent={"actionType": "search_food", "target": "clearing"},
            effects=[
                {
                    "type": "find_food",
                    "location": "clearing",
                    "itemId": "clearing_food",
                    "description": "food that is not there",
                }
            ],
        )
        with self.assertRaisesRegex(ResolutionValidationError, "No food opportunities"):
            parse_resolution_proposal(depleted, initial_game_state())

    def test_existing_item_id_cannot_be_created_twice(self):
        payload = proposal(
            intent={"actionType": "search_food", "target": "forest_edge"},
            effects=[
                {"type": "move_fox", "location": "forest_edge"},
                {
                    "type": "find_food",
                    "location": "forest_edge",
                    "itemId": "crow_cheese",
                    "description": "another cheese",
                },
            ],
        )

        with self.assertRaisesRegex(ResolutionValidationError, "already exists"):
            parse_resolution_proposal(payload, initial_game_state())

    def test_agent_cannot_change_trust_by_more_than_two(self):
        payload = proposal(
            intent={"actionType": "talk", "target": "crow"},
            effects=[{"type": "adjust_crow_trust", "amount": 3}],
        )

        with self.assertRaisesRegex(ResolutionValidationError, "at most 2"):
            parse_resolution_proposal(payload, initial_game_state())

    def test_invalid_or_waiting_action_cannot_submit_effects(self):
        effect = {"type": "adjust_crow_trust", "amount": -1}
        with self.assertRaisesRegex(ResolutionValidationError, "invalid action"):
            parse_resolution_proposal(
                proposal(outcome="invalid", effects=[effect]),
                initial_game_state(),
            )
        with self.assertRaisesRegex(ResolutionValidationError, "Waiting"):
            parse_resolution_proposal(proposal(effects=[effect]), initial_game_state())

    def test_successful_eating_requires_owned_food_and_hunger_reduction(self):
        state = initial_game_state()
        cheese = replace(
            state.day.world.items[0],
            owner="fox",
            location=state.day.fox.location,
        )
        day = DayState(
            fox=FoxState(inventory=("crow_cheese",)),
            crow=replace(state.day.crow, inventory=()),
            relationship=state.day.relationship,
            world=WorldState(items=(cheese,)),
        )
        state = replace(state, day=day)
        payload = proposal(
            intent={"actionType": "eat", "target": "crow_cheese"},
            effects=[
                {"type": "consume_food", "itemId": "crow_cheese"},
                {"type": "adjust_fox_hunger", "amount": -30},
            ],
            facts=["The fox eats the cheese and its hunger eases."],
        )

        parsed = parse_resolution_proposal(payload, state)

        self.assertIsInstance(parsed.effects[0], ConsumeFoodEffect)
        self.assertEqual(parsed.effects[1], AdjustFoxHungerEffect(amount=-30))

    def test_fox_cannot_consume_food_owned_by_the_crow(self):
        payload = proposal(
            intent={"actionType": "eat", "target": "crow_cheese"},
            effects=[
                {"type": "consume_food", "itemId": "crow_cheese"},
                {"type": "adjust_fox_hunger", "amount": -30},
            ],
        )

        with self.assertRaisesRegex(ResolutionValidationError, "currently owns"):
            parse_resolution_proposal(payload, initial_game_state())

    def test_duplicate_effect_types_are_rejected(self):
        payload = proposal(
            intent={"actionType": "talk", "target": "crow"},
            effects=[
                {"type": "adjust_crow_trust", "amount": 1},
                {"type": "adjust_crow_trust", "amount": 1},
            ],
        )

        with self.assertRaisesRegex(ResolutionValidationError, "only once"):
            parse_resolution_proposal(payload, initial_game_state())


if __name__ == "__main__":
    unittest.main()
