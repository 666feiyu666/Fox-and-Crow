import unittest
from pathlib import Path

from backend.case import Case
from backend.session import (
    MEMORY_TURNS,
    Narration,
    Ruling,
    RulingError,
    apply_turn,
    initial_state,
)

CASE_ROOT = Path(__file__).resolve().parents[2] / "cases"
FOX = Case.load(CASE_ROOT / "fox-and-crow")


def ruling(**overrides):
    payload = {'outcome': "partial", "facts": [], "scene": "A private plan."}
    payload.update(overrides)
    return Ruling.from_dict(payload)


def narration(text="a line"):
    return Narration.from_dict({"narration": f"You act: {text}", "hints": ["Wait."]})


def take(state, kind="say", text="a line", **overrides):
    return apply_turn(state, kind, text, ruling(**overrides), narration(text))


class RulingTests(unittest.TestCase):
    def test_accepts_a_well_formed_ruling(self):
        parsed = ruling(facts=["The crow blinked."])
        self.assertEqual(parsed.outcome, "partial")
        self.assertEqual(parsed.facts, ("The crow blinked.",))
        self.assertEqual(
            set(parsed.to_dict()), {"outcome", "facts", "scene", "restart", "ending"}
        )

    def test_rejects_an_unknown_outcome(self):
        with self.assertRaises(RulingError):
            ruling(outcome="triumph")

    def test_requires_a_scene(self):
        with self.assertRaises(RulingError):
            ruling(scene="   ")

    def test_keeps_at_most_three_facts(self):
        parsed = ruling(facts=["a", "b", "c", "d"])
        self.assertEqual(len(parsed.facts), 3)

    def test_ignores_unrelated_numbers(self):
        parsed = Ruling.from_dict(
            {"outcome": "success", "scene": "x", "meters": {"trust": 2}, "time_cost": 3}
        )
        self.assertEqual(parsed.outcome, "success")


class NarrationTests(unittest.TestCase):
    def test_requires_text_and_limits_hints(self):
        self.assertEqual(Narration.from_dict({"narration": "You wait."}).hints, ())
        with self.assertRaises(RulingError):
            Narration.from_dict({"narration": "   "})
        hints = Narration.from_dict(
            {"narration": "You wait.", "hints": ["a", "b", "c", "d"]}
        ).hints
        self.assertEqual(len(hints), 3)


class TurnTests(unittest.TestCase):
    def test_a_turn_records_what_the_player_and_the_story_said(self):
        state = take(initial_state("zh"), text="你看着乌鸦。")
        self.assertEqual(state.turn, 1)
        self.assertEqual(state.language, "zh")
        self.assertEqual(state.turns[0].player_input, "你看着乌鸦。")
        self.assertEqual(state.turns[0].narration, "You act: 你看着乌鸦。")

    def test_facts_accumulate_without_duplicates(self):
        state = initial_state()
        for _ in range(2):
            state = take(state, facts=["The bridge is down."])
        self.assertEqual(state.facts, ("The bridge is down.",))

    def test_only_recent_turns_are_kept(self):
        state = initial_state()
        for index in range(MEMORY_TURNS + 3):
            state = take(state, text=f"line {index}")
        self.assertEqual(len(state.turns), MEMORY_TURNS)
        self.assertEqual(state.turn, MEMORY_TURNS + 3)
        self.assertEqual(state.turns[-1].player_input, f"line {MEMORY_TURNS + 2}")

    def test_rejects_an_unknown_input_type(self):
        with self.assertRaises(ValueError):
            apply_turn(initial_state(), "shout", "hey", ruling(), narration())

    def test_wire_carries_the_language_the_loop_and_the_turn(self):
        wire = take(initial_state("en")).to_wire()
        self.assertEqual(wire, {"language": "en", "loop": 1, "turn": 1, "ended": False})


class ContextTests(unittest.TestCase):
    def test_context_gives_the_model_the_case_the_state_and_the_action(self):
        state = take(initial_state("zh"), text="走开")
        context = state.to_agent_context(FOX, "say", "走开")
        self.assertEqual(context["case"]["player"], "狐狸")
        self.assertEqual(context["state"]["language"], "zh")
        self.assertEqual(context["state"]["facts"], [])
        self.assertEqual(context["action"], {"type": "say", "text": "走开"})
        self.assertEqual(len(context["recent_turns"]), 1)
        self.assertNotIn("meters", context["state"])
        self.assertNotIn("clock", context["state"])


class LoopTests(unittest.TestCase):
    def test_a_restart_returns_to_the_same_morning_but_keeps_memory(self):
        state = take(initial_state(), text="first")
        state = take(state, text="second")
        state = take(state, text="third", restart=True)
        self.assertEqual(state.loop, 2)
        self.assertEqual(state.turn, 0)
        self.assertEqual(len(state.turns), 3)
        self.assertEqual(state.turns[-1].loop, 1)

    def test_an_ending_closes_the_story(self):
        state = take(initial_state(), ending=True)
        self.assertTrue(state.ended)
        with self.assertRaises(RulingError):
            take(state)

    def test_restart_and_ending_cannot_both_be_true(self):
        with self.assertRaises(RulingError):
            ruling(restart=True, ending=True)

    def test_flags_must_be_booleans(self):
        with self.assertRaises(RulingError):
            Ruling.from_dict({"outcome": "partial", "scene": "x", "restart": "yes"})

    def test_a_plain_turn_is_neither(self):
        state = take(initial_state())
        self.assertFalse(state.ended)
        self.assertEqual((state.loop, state.turn), (1, 1))


if __name__ == "__main__":
    unittest.main()
