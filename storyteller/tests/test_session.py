import unittest
from pathlib import Path

from backend.case import Case
from backend.session import (
    MEMORY_TURNS, Narration, Ruling, RulingError, apply_turn, initial_state, writer_context,
)
from backend.understanding import Understanding
from tests.fixtures import NARRATION, ruling_payload, understanding_payload

FOX = Case.load(Path(__file__).resolve().parents[2] / "cases" / "fox-and-crow")
PREPARED = Understanding.from_dict(understanding_payload())


def ruling(**overrides):
    return Ruling.from_dict(ruling_payload(**overrides))


def take(state, text="a line", **overrides):
    return apply_turn(state, "do", text, ruling(**overrides), Narration.from_dict(NARRATION))


class RulingTests(unittest.TestCase):
    def test_round_trip_preserves_events_and_brief(self):
        parsed = ruling()
        self.assertEqual(Ruling.from_dict(parsed.to_dict()), parsed)

    def test_rejects_malformed_or_incomplete_proposals(self):
        invalid = [
            {"outcome": "triumph"}, {"outcome": []}, {"brief": {}},
            {"events": []}, {"events": [{"text": "Secret", "observers": ["keeper"]}]},
            {"restart": "yes"}, {"restart": True, "ending": True},
            {"changes": [{"key": "x", "value": "a"}, {"key": "x", "value": "b"}]},
            {"expansions": [{"key": "x", "value": "x"}] * 7},
        ]
        for payload in invalid:
            with self.subTest(payload=payload), self.assertRaises(RulingError):
                ruling(**payload)

    def test_writing_mode_cannot_disagree_with_ending(self):
        payload = ruling_payload()
        payload["brief"]["mode"] = "ending"
        with self.assertRaises(RulingError):
            Ruling.from_dict(payload)


class NarrationTests(unittest.TestCase):
    def test_text_is_required_but_hints_are_optional(self):
        self.assertEqual(Narration.from_dict({"narration": "You wait."}).hints, ())
        with self.assertRaises(RulingError):
            Narration.from_dict({"narration": " "})
        self.assertEqual(len(Narration.from_dict(
            {"narration": "You wait.", "hints": ["a", "b", "c", "d"]}
        ).hints), 3)


class TurnTests(unittest.TestCase):
    def setUp(self):
        self.state = initial_state("en", PREPARED)

    def test_current_values_replace_previous_values_by_key(self):
        state = take(self.state, changes=[
            {"key": "parcel.holder", "value": "player", "known_by": ["player"]}
        ])
        facts = {fact.key: fact for fact in state.facts}
        self.assertEqual(facts["parcel.holder"].value, "player")
        self.assertNotIn("keeper", facts["parcel.holder"].known_by)
        self.assertEqual(self.state.facts[0].value, "keeper")

    def test_expansion_is_persistent_but_discovery_and_action_reset(self):
        state = take(self.state,
                     expansions=[{"key": "place.ledge", "value": "A low ledge.", "known_by": []}],
                     observations=[{"observer": "keeper", "fact_key": "place.ledge"},
                                   {"observer": "player", "fact_key": "place.ledge"}],
                     changes=[{"key": "parcel.holder", "value": "player", "known_by": ["player"]}],
                     memories=["You found a ledge."])
        state = take(state, restart=True)
        facts = {fact.key: fact for fact in state.facts}
        self.assertEqual((state.loop, state.turn), (2, 0))
        self.assertEqual(facts["parcel.holder"].value, "keeper")
        self.assertEqual(facts["place.ledge"].known_by, ())
        self.assertIn({"loop": 1, "text": "You found a ledge."},
                      [memory.to_dict() for memory in state.memories])

    def test_experienced_events_survive_even_without_model_memory_notes(self):
        state = take(self.state, events=[
            {"text": "The keeper refuses.", "observers": ["player"]},
            {"text": "A secret signal goes out.", "observers": ["keeper"]},
        ])
        state = take(state, restart=True)
        self.assertIn("The keeper refuses.", str(state.memories))
        self.assertNotIn("secret signal", str(state.memories))

    def test_private_knowledge_is_withheld_until_observed(self):
        context = self.state.to_agent_context(FOX, PREPARED.player, "do", "look", PREPARED)
        before = writer_context(context, ruling())
        self.assertNotIn("hidden-password", str(before))
        after = writer_context(context, ruling(observations=[
            {"observer": "player", "fact_key": "keeper.secret"}
        ]))
        self.assertIn("hidden-password", str(after))
        self.assertNotIn("hidden-password", str(self.state.to_wire()))

    def test_offscreen_events_stay_in_private_audit(self):
        judged = ruling(events=[
            {"text": "The keeper turns away.", "observers": ["player"]},
            {"text": "A hidden signal goes out.", "observers": ["keeper"]},
        ])
        context = self.state.to_agent_context(FOX, PREPARED.player, "do", "wait", PREPARED)
        self.assertNotIn("hidden signal", str(writer_context(context, judged)))
        state = apply_turn(self.state, "do", "wait", judged, Narration("The keeper turns."))
        self.assertIn("hidden signal", str(state.turns[0].to_dict(private=True)))
        self.assertNotIn("hidden signal", str(state.turns[0].to_dict()))

    def test_invalid_updates_never_change_state(self):
        invalid = [
            {"expansions": [{"key": "parcel.holder", "value": "new", "known_by": []}]},
            {"expansions": [{"key": "new", "value": "new", "known_by": ["player"]}]},
            {"changes": [{"key": "world.limit", "value": "Flight", "known_by": []}]},
            {"observations": [{"observer": "player", "fact_key": "absent"}]},
        ]
        for payload in invalid:
            with self.subTest(payload=payload), self.assertRaises(RulingError):
                take(self.state, **payload)
        self.assertEqual(self.state.turn, 0)

    def test_return_writer_sees_reset_values_and_new_memory(self):
        state = take(self.state, changes=[
            {"key": "parcel.holder", "value": "player", "known_by": ["player"]}
        ])
        context = state.to_agent_context(FOX, PREPARED.player, "do", "wait", PREPARED)
        view = writer_context(context, ruling(restart=True, memories=["You held the parcel."]))
        holder = next(item for item in view["visible_facts"] if item["key"] == "parcel.holder")
        self.assertEqual(holder["value"], "keeper")
        self.assertEqual(view["memories"][-1]["text"], "You held the parcel.")

    def test_full_turn_audit_outlives_recent_context_window(self):
        state = self.state
        for index in range(MEMORY_TURNS + 3):
            state = take(state, text=str(index))
        self.assertEqual(len(state.turns), MEMORY_TURNS + 3)
        context = state.to_agent_context(FOX, PREPARED.player, "do", "wait")
        self.assertEqual(len(context["recent_turns"]), MEMORY_TURNS)
        self.assertEqual(context["recent_turns"][0]["text"], "3")
        self.assertNotIn("ruling", context["recent_turns"][0])

    def test_wire_contract_is_unchanged(self):
        self.assertEqual(take(self.state).to_wire(),
                         {"language": "en", "loop": 1, "turn": 1, "ended": False})

    def test_ending_stops_play_and_unknown_input_is_rejected(self):
        with self.assertRaises(RulingError):
            take(take(self.state, ending=True))
        with self.assertRaises(ValueError):
            apply_turn(self.state, "shout", "hey", ruling(), Narration("You act."))


if __name__ == "__main__":
    unittest.main()
