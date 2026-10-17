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
    OPENING, NARRATION, review_payload, ruling_payload, understand_reply, understanding_payload,
)
from tests.test_case import write_case

CASE_ROOT = Path(__file__).resolve().parents[2] / "cases"
FOX = Case.load(CASE_ROOT / "fox-and-crow")
CINDERELLA = Case.load(CASE_ROOT / "cinderella")


class StubModel:
    configured = True

    def __init__(self, replies, reviews=None):
        self.replies = list(replies)
        self.calls = []
        self.reviews = None if reviews is None else list(reviews)

    def complete_json(self, system, user, **kwargs):
        self.calls.append({"system": system, "user": user, **kwargs})
        if user.startswith("Review input:"):
            return review_payload() if self.reviews is None else self.reviews.pop(0)
        reply = self.replies.pop(0)
        return reply(system, user) if callable(reply) else reply


def systems(model):
    return [call["system"] for call in model.calls]


def non_review_calls(model):
    return [call for call in model.calls if not call["user"].startswith("Review input:")]


class StorytellerTestBase(unittest.TestCase):
    def setUp(self):
        self.tempdir = tempfile.TemporaryDirectory()
        self.addCleanup(self.tempdir.cleanup)
        self.model = StubModel(
            [understand_reply, OPENING, ruling_payload(), NARRATION, ruling_payload(), NARRATION]
        )
        self.storyteller = Storyteller(FOX, model=self.model)
        self.storyteller.cache = UnderstandingCache(Path(self.tempdir.name))


class StorytellerTests(StorytellerTestBase):
    def test_opening_and_turn_are_reviewed_before_publication(self):
        ruling, narration = self.storyteller.resolve(initial_state("zh"), "say", "hello")
        prompts = systems(self.model)
        self.assertEqual(len(prompts), 6)
        self.assertIn("case object only", prompts[0])
        self.assertIn("task opening", prompts[1])
        self.assertTrue(self.model.calls[2]["user"].startswith("Review input:"))
        self.assertIn("judge for this turn", prompts[3])
        self.assertIn("writer for this turn", prompts[4])
        self.assertTrue(self.model.calls[5]["user"].startswith("Review input:"))
        self.assertEqual(ruling.outcome, "partial")
        self.assertEqual(narration.text, NARRATION["narration"])

    def test_preparation_and_its_written_opening_are_reused_across_turns(self):
        self.storyteller.resolve(initial_state(), "do", "climb")
        self.storyteller.resolve(initial_state(), "do", "climb again")
        self.assertEqual(len(self.model.calls), 9)
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
        for field in ("understand", "writer", "reader_review"):
            changed = replace(FOX, **{field: getattr(FOX, field) + "\nChanged guidance."})
            model = StubModel([understand_reply, OPENING])
            later = Storyteller(changed, model=model)
            later.cache = UnderstandingCache(Path(self.tempdir.name))
            _, origin = later.understanding_with_source("en")
            self.assertEqual(origin, UNDERSTANDING_DERIVED)
            self.assertEqual(len(model.calls), 3)

    def test_the_opening_is_rendered_by_writer_craft(self):
        self.assertEqual(self.storyteller.opening("en"), OPENING["narration"])
        self.assertIn("Writing craft for playable passages", self.model.calls[1]["system"])
        opening_input = json.loads(self.model.calls[1]["user"].split("\n", 1)[1])
        self.assertNotIn("hidden-password", str(opening_input))
        self.assertNotIn("negotiate", str(opening_input))

    def test_judge_gets_the_space_writer_gets_only_player_visible_results(self):
        self.storyteller.resolve(initial_state("zh"), "do", "look")
        calls = non_review_calls(self.model)
        self.assertIn("hidden-password", calls[2]["system"])
        for index in (1, 3):
            self.assertNotIn("hidden-password", str(calls[index]))
            self.assertNotIn("negotiate", str(calls[index]))
            self.assertIn("The story language is zh", calls[index]["system"])
        payload = json.loads(calls[3]["user"].split("\n", 1)[1])
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
                    self.assertEqual(len(model.calls), 6)

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
            next_input = json.loads(non_review_calls(model)[4]["user"].split("\n", 1)[1])
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
        self.assertEqual(len(self.storyteller.model.calls), 4)

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


class ReviewIntegrationTests(StorytellerTestBase):
    def test_reviewer_sees_private_context_but_writer_revision_receives_only_requests(self):
        rejected = review_payload("writer")
        rejected["summary"] = "PRIVATE-SUMMARY"
        rejected["findings"][0]["evidence"] = "hidden-password"
        rejected["findings"][0]["reason"] = "PRIVATE-REASON"
        self.model.replies = [understand_reply, OPENING, ruling_payload(), NARRATION,
                              {"narration": "The keeper gives no answer.", "hints": []}]
        self.model.reviews = [review_payload(), rejected, review_payload()]
        judged, narrated = self.storyteller.resolve(initial_state(), "do", "wait")
        review_call = [call for call in self.model.calls
                       if call["user"].startswith("Review input:")][1]
        self.assertIn("hidden-password", review_call["user"])
        rewrite = json.loads(self.model.calls[-2]["user"].split("\n", 1)[1])
        self.assertIn("revision", rewrite)
        for private in ("PRIVATE-SUMMARY", "PRIVATE-REASON", "hidden-password"):
            self.assertNotIn(private, str(rewrite))
        self.assertEqual(narrated.text, "The keeper gives no answer.")
        self.assertEqual(len(judged.review_history), 2)
        self.assertEqual(judged.review_history[0].narration, NARRATION["narration"])

    def test_judge_repair_replaces_the_uncommitted_proposal(self):
        rejected_change = ruling_payload(changes=[
            {"key": "parcel.holder", "value": "player", "known_by": ["player"]}
        ])
        final_change = ruling_payload(changes=[
            {"key": "parcel.holder", "value": "shelf", "known_by": ["player"]}
        ])
        self.model.replies = [understand_reply, OPENING, rejected_change, NARRATION,
                              final_change, NARRATION]
        self.model.reviews = [review_payload(), review_payload("judge"), review_payload()]
        prepared = self.storyteller.understanding("en")
        before = initial_state("en", prepared)
        judged, narrated = self.storyteller.resolve(before, "do", "wait")
        judge_inputs = [json.loads(call["user"].split("\n", 1)[1])
                        for call in self.model.calls if call["user"].startswith("Turn input:\n")]
        self.assertEqual(judge_inputs[0]["state"], judge_inputs[1]["state"])
        self.assertEqual(judge_inputs[1]["revision"]["previous_ruling"]["changes"][0]["value"], "player")
        after = apply_turn(before, "do", "wait", judged, narrated)
        self.assertEqual((before.turn, after.turn, len(after.turns)), (0, 1, 1))
        holder = next(fact for fact in after.facts if fact.key == "parcel.holder")
        self.assertEqual(holder.value, "shelf")
        self.assertEqual(len(after.turns[0].to_dict(private=True)["reviews"]), 2)
        self.assertNotIn("reviews", after.turns[0].to_dict())

    def test_minor_notes_do_not_trigger_a_rewrite(self):
        self.model.reviews = [review_payload(), review_payload("writer", blocking=False)]
        self.storyteller.resolve(initial_state(), "do", "wait")
        self.assertEqual(len(self.model.calls), 6)

    def test_malformed_turn_review_is_rejected(self):
        self.model.reviews = [review_payload(), {"decision": "pass"}]
        with self.assertRaisesRegex(RulingError, "unusable report"):
            self.storyteller.resolve(initial_state(), "do", "wait")

    def test_opening_is_rewritten_and_rechecked_before_caching(self):
        self.model.replies = [understand_reply, OPENING,
                              {"narration": "Cold air moves through the room.", "hints": []}]
        self.model.reviews = [review_payload("writer"), review_payload()]
        prepared = self.storyteller.understanding("en")
        self.assertEqual(prepared.opening, "Cold air moves through the room.")
        cache = json.loads(self.storyteller.cache.path("en").read_text(encoding="utf-8"))
        self.assertEqual(cache["understanding"]["opening"], prepared.opening)
        revised = json.loads(self.model.calls[3]["user"].split("\n", 1)[1])
        self.assertIn("previous_candidate", revised["revision"])

    def test_rejected_opening_never_enters_the_cache(self):
        for reports in ([review_payload("judge")],
                        [review_payload("writer"), review_payload("writer")]):
            with self.subTest(reports=reports):
                self.storyteller.model = StubModel([understand_reply, OPENING, OPENING], reports)
                with self.assertRaises(RulingError):
                    self.storyteller.understanding("en")
                self.assertFalse(self.storyteller.cache.path("en").exists())

    def test_return_review_projects_reset_facts(self):
        prepared = self.storyteller.understanding("en")
        state = initial_state("en", prepared)
        state = apply_turn(state, "do", "take", Ruling.from_dict(ruling_payload(changes=[
            {"key": "parcel.holder", "value": "player", "known_by": ["player"]}
        ])), Narration("You hold the parcel."))
        self.model.replies = [ruling_payload(restart=True), OPENING]
        self.storyteller.resolve(state, "do", "wait")
        report_input = json.loads(self.model.calls[-1]["user"].split("\n", 1)[1])
        holder = next(fact for fact in report_input["projected_facts"]
                      if fact["key"] == "parcel.holder")
        self.assertEqual(holder["value"], "keeper")


if __name__ == "__main__":
    unittest.main()
