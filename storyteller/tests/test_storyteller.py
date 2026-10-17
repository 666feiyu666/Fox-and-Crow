import json
import tempfile
import unittest
from dataclasses import replace
from pathlib import Path

from backend.case import Case
from backend.session import Narration, Ruling, RulingError, apply_turn, initial_state
from backend.storyteller import Storyteller, UNDERSTANDING_DERIVED, UNDERSTANDING_REUSED
from backend.understanding import UnderstandingCache
from tests.fixtures import (
    OPENING, NARRATION, ruling_payload, understand_reply, understanding_payload,
)
from tests.test_case import write_case

CASE_ROOT = Path(__file__).resolve().parents[2] / "cases"
FOX = Case.load(CASE_ROOT / "fox-and-crow")
CINDERELLA = Case.load(CASE_ROOT / "cinderella")


class StubModel:
    configured = True

    def __init__(self, replies):
        self.replies = list(replies)
        self.calls = []

    def complete_json(self, system, user, **kwargs):
        self.calls.append({"system": system, "user": user, **kwargs})
        reply = self.replies.pop(0)
        return reply(system, user) if callable(reply) else reply


def systems(model):
    return [call["system"] for call in model.calls]


class StorytellerTests(unittest.TestCase):
    def setUp(self):
        self.tempdir = tempfile.TemporaryDirectory()
        self.addCleanup(self.tempdir.cleanup)
        self.model = StubModel(
            [understand_reply, OPENING, ruling_payload(), NARRATION, ruling_payload(), NARRATION]
        )
        self.storyteller = Storyteller(FOX, model=self.model)
        self.storyteller.cache = UnderstandingCache(Path(self.tempdir.name))

    def test_prepare_then_opening_writer_then_judge_then_turn_writer(self):
        ruling, narration = self.storyteller.resolve(initial_state("zh"), "say", "hello")
        prompts = systems(self.model)
        self.assertEqual(len(prompts), 4)
        self.assertIn("case object only", prompts[0])
        self.assertIn("task opening", prompts[1])
        self.assertIn("judge for this turn", prompts[2])
        self.assertIn("writer for this turn", prompts[3])
        self.assertEqual(ruling.outcome, "partial")
        self.assertEqual(narration.text, NARRATION["narration"])

    def test_preparation_and_its_written_opening_are_reused_across_turns(self):
        self.storyteller.resolve(initial_state(), "do", "climb")
        self.storyteller.resolve(initial_state(), "do", "climb again")
        self.assertEqual(len(self.model.calls), 6)
        self.assertEqual(sum("case object only" in p for p in systems(self.model)), 1)

    def test_the_understanding_is_written_beside_the_case(self):
        self.storyteller.understanding("en")
        cached = list(Path(self.tempdir.name).rglob("understanding.en.json"))
        self.assertEqual(len(cached), 1)
        payload = json.loads(cached[0].read_text(encoding="utf-8"))
        self.assertEqual(payload["understanding"]["opening"], OPENING["narration"])
        self.assertIn("possibilities", payload["understanding"]["space"])

    def test_the_understanding_says_whether_the_model_was_used(self):
        _, first = self.storyteller.understanding_with_source("en")
        self.assertEqual(first, UNDERSTANDING_DERIVED)
        _, again = self.storyteller.understanding_with_source("en")
        self.assertEqual(again, UNDERSTANDING_REUSED)

    def test_a_derivation_beside_the_case_is_reused_without_the_model(self):
        self.storyteller.understanding("en")
        later = Storyteller(FOX, model=StubModel([]))
        later.cache = UnderstandingCache(Path(self.tempdir.name))
        understanding, origin = later.understanding_with_source("en")
        self.assertEqual(origin, UNDERSTANDING_REUSED)
        self.assertEqual(understanding.opening, OPENING["narration"])

    def test_changing_preparation_or_craft_invalidates_the_cache(self):
        self.storyteller.understanding("en")
        for field in ("understand", "writer"):
            changed = replace(FOX, **{field: getattr(FOX, field) + "\nChanged guidance."})
            model = StubModel([understand_reply, OPENING])
            later = Storyteller(changed, model=model)
            later.cache = UnderstandingCache(Path(self.tempdir.name))
            _, origin = later.understanding_with_source("en")
            self.assertEqual(origin, UNDERSTANDING_DERIVED)
            self.assertEqual(len(model.calls), 2)

    def test_the_opening_is_rendered_by_writer_craft(self):
        self.assertEqual(self.storyteller.opening("en"), OPENING["narration"])
        self.assertIn("Writing craft for playable passages", self.model.calls[1]["system"])
        opening_input = json.loads(self.model.calls[1]["user"].split("\n", 1)[1])
        self.assertNotIn("hidden-password", str(opening_input))
        self.assertNotIn("negotiate", str(opening_input))

    def test_judge_gets_the_space_writer_gets_only_player_visible_results(self):
        self.storyteller.resolve(initial_state("zh"), "do", "look")
        self.assertIn("hidden-password", self.model.calls[2]["system"])
        for index in (1, 3):
            self.assertNotIn("hidden-password", str(self.model.calls[index]))
            self.assertNotIn("negotiate", str(self.model.calls[index]))
            self.assertIn("The story language is zh", self.model.calls[index]["system"])
        payload = json.loads(self.model.calls[3]["user"].split("\n", 1)[1])
        self.assertEqual(payload["ruling"]["outcome"], "partial")
        self.assertEqual(payload["action"], {"type": "do", "text": "look"})
        self.assertEqual(payload["opening"], OPENING["narration"])

    def test_both_existing_cases_use_their_own_tale_in_both_languages(self):
        for case in (FOX, CINDERELLA):
            for language in ("en", "zh"):
                with self.subTest(case=case.id, language=language):
                    model = StubModel([understand_reply, OPENING, ruling_payload(), NARRATION])
                    engine = Storyteller(case, model=model)
                    with tempfile.TemporaryDirectory() as directory:
                        engine.cache = UnderstandingCache(Path(directory))
                        engine.resolve(initial_state(language), "do", "wait")
                    self.assertIn(case.source(language), model.calls[0]["user"])
                    self.assertEqual(len(model.calls), 4)

    def test_a_new_case_can_expand_and_continue_without_engine_changes(self):
        with tempfile.TemporaryDirectory() as directory:
            case = Case.load(write_case(Path(directory) / "workshop"))
            prepared = understanding_payload(case.source("en"), player="the apprentice")
            discovery = ruling_payload(
                expansions=[{"key": "workshop.shelf", "value": "A low shelf.", "known_by": []}],
                observations=[{"observer": "player", "fact_key": "workshop.shelf"}],
                memories=["You discovered the shelf."],
            )
            model = StubModel([prepared, OPENING, discovery, NARRATION,
                               ruling_payload(), NARRATION])
            engine = Storyteller(case, model=model)
            state = initial_state("en", engine.understanding("en"))
            judged, narrated = engine.resolve(state, "do", "look along the wall")
            state = apply_turn(state, "do", "look along the wall", judged, narrated)
            engine.resolve(state, "do", "inspect the shelf")
            next_input = json.loads(model.calls[4]["user"].split("\n", 1)[1])
            self.assertEqual(next_input["case"]["player"], "the apprentice")
            self.assertIn("workshop.shelf", str(next_input["state"]["facts"]))
            self.assertNotIn("negotiate", str(next_input["state"]["facts"]))
            self.assertEqual(state.turns[0].ruling.expansions[0].key, "workshop.shelf")

    def test_made_up_source_evidence_is_rejected_before_opening_or_caching(self):
        self.storyteller.model = StubModel([understanding_payload("not in the supplied tale")])
        with self.assertRaises(RulingError):
            self.storyteller.understanding("en")
        self.assertEqual(len(self.storyteller.model.calls), 1)
        self.assertFalse(self.storyteller.cache.path("en").exists())

    def test_invalid_opening_does_not_cache_a_half_prepared_story(self):
        self.storyteller.model = StubModel([understand_reply, {"narration": ""}])
        with self.assertRaises(RulingError):
            self.storyteller.understanding("en")
        self.assertFalse(self.storyteller.cache.path("en").exists())

    def test_invalid_state_change_stops_before_writer(self):
        self.storyteller.model = StubModel([
            understand_reply, OPENING,
            ruling_payload(changes=[{"key": "world.limit", "value": "Flight.", "known_by": []}]),
        ])
        with self.assertRaises(RulingError):
            self.storyteller.resolve(initial_state(), "do", "fly")
        self.assertEqual(len(self.storyteller.model.calls), 3)

    def test_an_unusable_understanding_is_rejected(self):
        self.storyteller.model = StubModel([{"player": "someone"}])
        with self.assertRaises(RulingError):
            self.storyteller.understanding("en")

    def test_an_unusable_ruling_is_rejected(self):
        self.storyteller.model = StubModel([{"outcome": "bogus"}])
        with self.assertRaises(RulingError):
            self.storyteller.judge("system", {})

    def test_an_unusable_narration_is_rejected(self):
        understanding = self.storyteller.understanding("en")
        context = initial_state("en", understanding).to_agent_context(
            FOX, understanding.player, "do", "wait", understanding
        )
        self.storyteller.model = StubModel([{"narration": ""}])
        with self.assertRaises(RulingError):
            self.storyteller.write("system", context, Ruling.from_dict(ruling_payload()))


if __name__ == "__main__":
    unittest.main()
