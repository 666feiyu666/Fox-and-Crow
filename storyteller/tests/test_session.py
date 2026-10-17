import tempfile
import unittest
from pathlib import Path

from backend.case import Case
from backend.session import (
    Narration,
    Ruling,
    RulingError,
    apply_turn,
    ending_allowed,
    initial_state,
)
from tests.test_case import CASE_ROOT, write_case

FOX = Case.load(CASE_ROOT / "fox-and-crow")


def ruling(case, **overrides):
    payload = {
        "outcome": "partial",
        "time_cost": 1,
        "meters": {},
        "facts": [],
        "scene": "A private plan.",
        "ending": "none",
    }
    payload.update(overrides)
    return Ruling.from_dict(payload, case)


def narration(text="a line"):
    return Narration.from_dict({"narration": f"You act: {text}", "hints": ["Wait."]})


def say(state, case=FOX, text="a line", **overrides):
    return apply_turn(state, case, "say", text, ruling(case, **overrides), narration(text))


class RulingParsingTests(unittest.TestCase):
    def test_accepts_well_formed_ruling(self):
        parsed = ruling(FOX, facts=["The crow blinked."], meters={"trust": 1})
        self.assertEqual(parsed.outcome, "partial")
        self.assertEqual(parsed.facts, ("The crow blinked.",))
        self.assertEqual(dict(parsed.meters), {"trust": 1})

    def test_rejects_unknown_outcome_and_ending(self):
        with self.assertRaises(RulingError):
            ruling(FOX, outcome="triumph")
        with self.assertRaises(RulingError):
            ruling(FOX, ending="loop_broken")

    def test_rejects_non_integer_numbers(self):
        with self.assertRaises(RulingError):
            ruling(FOX, time_cost="2")
        with self.assertRaises(RulingError):
            ruling(FOX, meters={"trust": True})

    def test_clamps_time_and_meter_deltas(self):
        parsed = ruling(FOX, time_cost=99, meters={"trust": 9, "insight": -9})
        self.assertEqual(parsed.time_cost, 3)
        self.assertEqual(dict(parsed.meters), {"trust": 2, "insight": -2})

    def test_ignores_meters_the_case_does_not_keep(self):
        parsed = ruling(FOX, meters={"trust": 1, "courage": 2})
        self.assertEqual(dict(parsed.meters), {"trust": 1})

    def test_requires_a_scene(self):
        with self.assertRaises(RulingError):
            ruling(FOX, scene="   ")


class ClocklessCaseTests(unittest.TestCase):
    def setUp(self):
        with tempfile.TemporaryDirectory() as directory:
            self.case = Case.load(write_case(Path(directory)))
        self.state = initial_state(self.case)

    def test_time_cost_is_forced_to_zero(self):
        self.assertEqual(ruling(self.case, time_cost=3).time_cost, 0)

    def test_turns_never_advance_elapsed_time(self):
        state, events = say(self.state, self.case, time_cost=3)
        self.assertEqual(events, ())
        self.assertEqual(state.elapsed, 0)
        self.assertEqual(state.day, 1)
        self.assertEqual(state.turn, 1)

    def test_wire_has_no_clock(self):
        wire = self.state.to_wire(self.case)
        self.assertFalse(wire["hasClock"])
        self.assertNotIn("remainingUnits", wire)


class TurnTests(unittest.TestCase):
    def setUp(self):
        self.state = initial_state(FOX)

    def test_turn_records_action_and_narration(self):
        state, events = say(self.state, text="You look well fed.")
        self.assertEqual(events, ())
        self.assertEqual(state.turn, 1)
        self.assertEqual(state.turns[0].player_input, "You look well fed.")
        self.assertEqual(state.turns[0].narration, "You act: You look well fed.")

    def test_meters_accumulate_within_case_bounds(self):
        state = self.state
        for _ in range(5):
            state, _ = say(state, time_cost=0, meters={"trust": 2, "insight": 2})
        self.assertEqual(state.meters["trust"], 6)
        self.assertEqual(state.meters["insight"], 6)

    def test_day_reset_restores_reset_meters_only(self):
        state, _ = say(self.state, time_cost=3, meters={"trust": 2, "insight": 2}, facts=["A chain."])
        state, events = say(state, time_cost=3)
        self.assertEqual(events, ("day_reset",))
        self.assertEqual(state.day, 2)
        self.assertEqual(state.elapsed, 0)
        self.assertEqual(state.meters["trust"], 0)
        self.assertEqual(state.meters["insight"], 2)
        self.assertEqual(state.facts, ("A chain.",))

    def test_elapsed_stays_inside_the_day(self):
        state = self.state
        for _ in range(6):
            state, _ = say(state, time_cost=3)
        self.assertLess(state.elapsed, 6)

    def test_facts_are_deduplicated(self):
        state = self.state
        for _ in range(2):
            state, _ = say(state, time_cost=0, facts=["The bridge is down."])
        self.assertEqual(state.facts, ("The bridge is down.",))

    def test_rejects_unknown_input_type(self):
        with self.assertRaises(ValueError):
            apply_turn(
                self.state,
                FOX,
                "shout",
                "hey",
                ruling(FOX),
                narration(),
            )


class EndingTests(unittest.TestCase):
    def _earned_turns(self):
        state = initial_state(FOX)
        for _ in range(FOX.ending.min_turns - 1):
            state, _ = say(state, time_cost=0, meters={"trust": 1, "insight": 1})
        return state

    def test_ending_requires_the_declared_thresholds(self):
        self.assertFalse(ending_allowed(FOX, 1, {"trust": 6, "insight": 6}))
        self.assertFalse(ending_allowed(FOX, 20, {"trust": 0, "insight": 0}))

    def test_declared_ending_is_refused_before_it_is_earned(self):
        state, events = say(initial_state(FOX), ending="end")
        self.assertEqual(events, ("ending_refused",))
        self.assertFalse(state.ended)

    def test_earned_ending_is_accepted_and_blocks_further_turns(self):
        state = self._earned_turns()
        state, events = say(state, ending="end")
        self.assertEqual(events, ("story_ended",))
        self.assertTrue(state.ended)
        with self.assertRaises(RulingError):
            say(state)

    def test_clockless_case_still_requires_min_turns(self):
        with tempfile.TemporaryDirectory() as directory:
            case = Case.load(write_case(Path(directory)))
        state = initial_state(case)
        state, events = say(state, case, ending="end")
        self.assertEqual(events, ("ending_refused",))
        for _ in range(case.ending.min_turns - 1):
            state, _ = say(state, case)
        state, events = say(state, case, ending="end")
        self.assertEqual(events, ("story_ended",))


if __name__ == "__main__":
    unittest.main()
