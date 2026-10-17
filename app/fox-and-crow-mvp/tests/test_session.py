import unittest

from backend.session import (
    DAY_UNITS,
    LOOP_BREAK_MIN_INSIGHT,
    LOOP_BREAK_MIN_TRUST,
    LOOP_BREAK_MIN_TURNS,
    Narration,
    Ruling,
    RulingError,
    apply_turn,
    initial_state,
    loop_break_allowed,
)


def ruling(**overrides):
    payload = {
        "outcome": "partial",
        "time_cost": 1,
        "trust": 0,
        "insight": 0,
        "facts": [],
        "scene": "A private plan.",
        "ending": "none",
    }
    payload.update(overrides)
    return Ruling.from_dict(payload)


def narration(text="You wait.", hints=()):
    return Narration.from_dict({"narration": text, "hints": list(hints)})


class RulingParsingTests(unittest.TestCase):
    def test_accepts_well_formed_ruling(self):
        parsed = ruling(facts=["The crow blinked."])
        self.assertEqual(parsed.outcome, "partial")
        self.assertEqual(parsed.facts, ("The crow blinked.",))

    def test_rejects_unknown_outcome_and_ending(self):
        with self.assertRaises(RulingError):
            ruling(outcome="triumph")
        with self.assertRaises(RulingError):
            ruling(ending="loop_ended")

    def test_rejects_non_integer_numbers(self):
        with self.assertRaises(RulingError):
            ruling(time_cost="2")
        with self.assertRaises(RulingError):
            ruling(trust=True)

    def test_clamps_out_of_range_numbers(self):
        parsed = ruling(time_cost=99, trust=9, insight=9)
        self.assertEqual((parsed.time_cost, parsed.trust, parsed.insight), (3, 2, 2))

    def test_requires_a_scene(self):
        with self.assertRaises(RulingError):
            ruling(scene="   ")

    def test_narration_requires_text_and_limits_hints(self):
        self.assertEqual(Narration.from_dict({"narration": "You wait."}).hints, ())
        with self.assertRaises(RulingError):
            Narration.from_dict({"narration": ""})
        hints = Narration.from_dict(
            {"narration": "You wait.", "hints": ["a", "b", "c", "d"]}
        ).hints
        self.assertEqual(len(hints), 3)


class ApplyTurnTests(unittest.TestCase):
    def test_turn_records_action_and_narration(self):
        state, events = apply_turn(
            initial_state("en"), "say", "You look well fed.", ruling(), narration("She shifts.")
        )
        self.assertEqual(events, ())
        self.assertEqual(state.elapsed, 1)
        self.assertEqual(state.turns[0].player_input, "You look well fed.")
        self.assertEqual(state.turns[0].narration, "She shifts.")

    def test_deltas_accumulate_and_are_clamped(self):
        state = initial_state()
        for _ in range(5):
            state, _ = apply_turn(
                state, "do", "dig", ruling(time_cost=0, trust=2, insight=2), narration()
            )
        self.assertEqual(state.trust, 6)
        self.assertEqual(state.insight, 6)

    def test_day_reset_clears_trust_but_keeps_insight_and_facts(self):
        state = initial_state()
        state, _ = apply_turn(
            state,
            "do",
            "dig",
            ruling(time_cost=3, trust=2, insight=2, facts=["The thorns hold a chain."]),
            narration(),
        )
        state, events = apply_turn(state, "do", "dig", ruling(time_cost=3), narration())
        self.assertEqual(events, ("day_reset",))
        self.assertEqual(state.loop, 2)
        self.assertEqual(state.elapsed, 0)
        self.assertEqual(state.trust, 0)
        self.assertEqual(state.insight, 2)
        self.assertEqual(state.facts, ("The thorns hold a chain.",))

    def test_elapsed_never_exceeds_a_day(self):
        state = initial_state()
        for _ in range(6):
            state, _ = apply_turn(state, "do", "walk", ruling(time_cost=3), narration())
        self.assertLess(state.elapsed, DAY_UNITS)

    def test_facts_are_deduplicated(self):
        state = initial_state()
        for _ in range(2):
            state, _ = apply_turn(
                state, "do", "dig", ruling(time_cost=0, facts=["The bridge is down."]), narration()
            )
        self.assertEqual(state.facts, ("The bridge is down.",))

    def test_rejects_unknown_input_type(self):
        with self.assertRaises(ValueError):
            apply_turn(initial_state(), "shout", "hey", ruling(), narration())


class LoopBreakTests(unittest.TestCase):
    def _earned_state(self):
        state = initial_state()
        for _ in range(LOOP_BREAK_MIN_TURNS - 1):
            state, _ = apply_turn(
                state,
                "say",
                "I am still here.",
                ruling(time_cost=0, trust=1, insight=1),
                narration(),
            )
        return state

    def test_end_requires_enough_turns_insight_and_trust(self):
        self.assertFalse(loop_break_allowed(0, 6, 6))
        self.assertFalse(loop_break_allowed(20, 0, 6))
        self.assertFalse(loop_break_allowed(20, 6, 0))

    def test_declared_end_is_refused_before_it_is_earned(self):
        state, events = apply_turn(
            initial_state(),
            "say",
            "I told you the truth.",
            ruling(ending="loop_broken"),
            narration(),
        )
        self.assertEqual(events, ("loop_break_refused",))
        self.assertFalse(state.ended)

    def test_earned_end_is_accepted_and_blocks_further_turns(self):
        state = self._earned_state()
        self.assertGreaterEqual(state.insight, LOOP_BREAK_MIN_INSIGHT)
        self.assertGreaterEqual(state.trust, LOOP_BREAK_MIN_TRUST)
        state, events = apply_turn(
            state,
            "say",
            "There is no way to say this twice.",
            ruling(ending="loop_broken"),
            narration(),
        )
        self.assertEqual(events, ("loop_broken",))
        self.assertTrue(state.ended)
        with self.assertRaises(RulingError):
            apply_turn(state, "do", "wait", ruling(), narration())


if __name__ == "__main__":
    unittest.main()
