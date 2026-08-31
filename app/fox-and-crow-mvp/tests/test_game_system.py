import unittest
from dataclasses import replace

from backend.game_system.state import (
    FRIENDSHIP_TRUST_THRESHOLD,
    MAX_FOX_HUNGER,
    TOTAL_DAY_UNITS,
    DayOutcome,
    DayState,
    FoxState,
    RelationshipState,
    StateTransitionError,
    advance_time,
    evaluate_day,
    friendship_established,
    initial_game_state,
    learn_action,
    remember_fox,
    reset_for_next_loop,
)


class GameStateTests(unittest.TestCase):
    def test_initial_state_separates_day_and_loop_data(self):
        state = initial_game_state()

        self.assertEqual(state.day.world.remaining_time_units, TOTAL_DAY_UNITS)
        self.assertEqual(state.day.crow.inventory, ("crow_cheese",))
        self.assertEqual(state.loop.loop_count, 0)
        self.assertEqual(state.loop.fox_memories, ())

    def test_every_action_must_consume_time(self):
        with self.assertRaisesRegex(StateTransitionError, "at least one time unit"):
            advance_time(initial_game_state(), time_cost=0, hunger_increase=0)

    def test_characters_and_items_must_reference_known_world_objects(self):
        with self.assertRaisesRegex(ValueError, "known world location"):
            DayState(fox=FoxState(location="outside_the_world"))

    def test_time_and_hunger_progress_deterministically(self):
        state = initial_game_state()

        first = advance_time(state, time_cost=2, hunger_increase=5)
        second = advance_time(state, time_cost=2, hunger_increase=5)

        self.assertEqual(first, second)
        self.assertEqual(first.state.day.world.remaining_time_units, TOTAL_DAY_UNITS - 2)
        self.assertEqual(first.state.day.fox.hunger, state.day.fox.hunger + 5)
        self.assertEqual(first.outcome, DayOutcome.ACTIVE)

    def test_trust_alone_does_not_create_friendship(self):
        state = initial_game_state()
        trusted_crow = replace(state.day.crow, trust=FRIENDSHIP_TRUST_THRESHOLD)
        day = replace(state.day, crow=trusted_crow)

        self.assertFalse(friendship_established(day))

    def test_friendship_requires_trust_support_reciprocity_and_no_betrayal(self):
        state = initial_game_state()
        trusted_crow = replace(state.day.crow, trust=FRIENDSHIP_TRUST_THRESHOLD)
        relationship = RelationshipState(supportive_actions=1, reciprocal_actions=1)
        day = replace(state.day, crow=trusted_crow, relationship=relationship)

        self.assertTrue(friendship_established(day))
        self.assertFalse(
            friendship_established(
                replace(
                    day,
                    relationship=replace(relationship, unresolved_betrayal=True),
                )
            )
        )

    def test_day_end_without_friendship_requires_loop_reset(self):
        result = advance_time(
            initial_game_state(),
            time_cost=TOTAL_DAY_UNITS,
            hunger_increase=0,
        )

        self.assertEqual(result.outcome, DayOutcome.LOOP_RESET)

    def test_friendship_escapes_only_when_the_day_ends(self):
        state = initial_game_state()
        crow = replace(state.day.crow, trust=FRIENDSHIP_TRUST_THRESHOLD)
        relationship = RelationshipState(supportive_actions=1, reciprocal_actions=1)
        friends = replace(state, day=replace(state.day, crow=crow, relationship=relationship))

        self.assertEqual(evaluate_day(friends), DayOutcome.ACTIVE)
        result = advance_time(friends, time_cost=TOTAL_DAY_UNITS, hunger_increase=0)
        self.assertEqual(result.outcome, DayOutcome.LOOP_ESCAPED)

    def test_starvation_takes_precedence_over_the_end_of_day(self):
        state = initial_game_state()
        hunger_increase = MAX_FOX_HUNGER - state.day.fox.hunger

        result = advance_time(
            state,
            time_cost=TOTAL_DAY_UNITS,
            hunger_increase=hunger_increase,
        )

        self.assertEqual(result.outcome, DayOutcome.FOX_STARVED)
        self.assertFalse(result.state.day.fox.alive)

    def test_reset_preserves_only_loop_memory_and_learned_actions(self):
        state = remember_fox(initial_game_state(), "The stream bank may contain food.")
        state = learn_action(state, "Search Stream Bank")
        expired = advance_time(state, time_cost=TOTAL_DAY_UNITS, hunger_increase=0).state
        reset = reset_for_next_loop(expired)

        self.assertEqual(reset.loop.loop_count, 1)
        self.assertEqual(reset.loop.fox_memories, ("The stream bank may contain food.",))
        self.assertEqual(reset.loop.learned_actions, ("search stream bank",))
        self.assertEqual(reset.loop.world_seed, state.loop.world_seed)
        self.assertEqual(reset.day, initial_game_state().day)

    def test_finished_or_escaped_day_cannot_accept_more_actions_or_reset(self):
        expired = advance_time(
            initial_game_state(),
            time_cost=TOTAL_DAY_UNITS,
            hunger_increase=0,
        ).state
        reset = reset_for_next_loop(expired)

        with self.assertRaisesRegex(StateTransitionError, "finished day"):
            advance_time(expired, time_cost=1, hunger_increase=0)
        with self.assertRaisesRegex(StateTransitionError, "failed or expired day"):
            reset_for_next_loop(reset)


if __name__ == "__main__":
    unittest.main()
