import json
import tempfile
import unittest
from pathlib import Path

from backend.case import Case
from backend.session import Ruling, RulingError, initial_state
from backend.storyteller import Storyteller
from backend.understanding import UnderstandingCache

CASE_ROOT = Path(__file__).resolve().parents[2] / "cases"
FOX = Case.load(CASE_ROOT / "fox-and-crow")
CINDERELLA = Case.load(CASE_ROOT / "cinderella")

UNDERSTANDING = {
    "player": "the fox",
    "canon": "# World\n\n## Premise\nA forest.",
    "opening": "Cold moss under your paws.",
}
NARRATION = {"narration": "She turns her back.", "hints": ["Try the thorns."]}


class StubModel:
    configured = True

    def __init__(self, replies):
        self.replies = list(replies)
        self.calls = []

    def complete_json(self, system, user, **kwargs):
        self.calls.append({"system": system, "user": user, **kwargs})
        return self.replies.pop(0)


def ruling_payload(**overrides):
    payload = {
        "outcome": "failure",
        "facts": ["The crow refused to look down."],
        "scene": "She keeps the cheese and turns away.",
    }
    payload.update(overrides)
    return payload


def systems(model):
    return [call["system"] for call in model.calls]


class StorytellerTests(unittest.TestCase):
    def setUp(self):
        self.tempdir = tempfile.TemporaryDirectory()
        self.addCleanup(self.tempdir.cleanup)
        self.model = StubModel(
            [UNDERSTANDING, ruling_payload(), NARRATION, ruling_payload(), NARRATION]
        )
        self.storyteller = Storyteller(FOX, model=self.model)
        self.storyteller.cache = UnderstandingCache(Path(self.tempdir.name))

    def test_the_tale_is_understood_before_anything_is_judged(self):
        ruling, narration = self.storyteller.resolve(initial_state("zh"), "say", "喂，乌鸦")
        prompts = systems(self.model)
        self.assertEqual(len(prompts), 3)
        self.assertIn("case object only", prompts[0])
        self.assertIn("judge for this turn", prompts[1])
        self.assertIn("writer for this turn", prompts[2])
        self.assertEqual(ruling.outcome, "failure")
        self.assertEqual(narration.text, NARRATION["narration"])

    def test_the_understanding_is_reused_across_turns(self):
        self.storyteller.resolve(initial_state(), "do", "climb")
        self.storyteller.resolve(initial_state(), "do", "climb again")
        prompts = systems(self.model)
        self.assertEqual(len(prompts), 5)
        self.assertEqual(sum("case object only" in prompt for prompt in prompts), 1)

    def test_the_understanding_is_written_beside_the_case(self):
        self.storyteller.understanding("en")
        cached = list(Path(self.tempdir.name).rglob("understanding.en.json"))
        self.assertEqual(len(cached), 1)
        payload = json.loads(cached[0].read_text(encoding="utf-8"))
        self.assertEqual(payload["understanding"]["opening"], UNDERSTANDING["opening"])

    def test_the_opening_comes_from_the_understanding(self):
        self.assertEqual(self.storyteller.opening("en"), UNDERSTANDING["opening"])

    def test_prompts_carry_the_derived_canon(self):
        self.storyteller.resolve(initial_state("zh"), "do", "拨开荆棘")
        for prompt in systems(self.model)[1:]:
            self.assertIn(UNDERSTANDING["canon"], prompt)
            self.assertIn("The story language is zh", prompt)

    def test_the_ruling_is_handed_to_the_writer(self):
        self.storyteller.resolve(initial_state(), "do", "climb the tree")
        payload = json.loads(self.model.calls[2]["user"].split("\n", 1)[1])
        self.assertEqual(payload["ruling"]["outcome"], "failure")
        self.assertEqual(payload["action"], {"type": "do", "text": "climb the tree"})

    def test_another_case_is_understood_from_its_own_tale(self):
        model = StubModel([UNDERSTANDING, ruling_payload(), NARRATION])
        storyteller = Storyteller(CINDERELLA, model=model)
        storyteller.cache = UnderstandingCache(Path(self.tempdir.name))
        storyteller.resolve(initial_state("en"), "do", "wait")
        self.assertIn("slipper", model.calls[0]["user"].lower())

    def test_an_unusable_understanding_is_rejected(self):
        model = StubModel([{"player": "the fox"}])
        storyteller = Storyteller(FOX, model=model)
        storyteller.cache = UnderstandingCache(Path(self.tempdir.name))
        with self.assertRaises(RulingError):
            storyteller.understanding("en")

    def test_an_unusable_ruling_is_rejected(self):
        model = StubModel([{"outcome": "bogus", "scene": "x"}])
        storyteller = Storyteller(FOX, model=model)
        with self.assertRaises(RulingError):
            storyteller.judge("system", {"action": {"type": "do", "text": "x"}})

    def test_an_unusable_narration_is_rejected(self):
        model = StubModel([{"narration": ""}])
        storyteller = Storyteller(FOX, model=model)
        with self.assertRaises(RulingError):
            storyteller.write(
                "system",
                {"action": {"type": "do", "text": "x"}},
                Ruling.from_dict(ruling_payload()),
            )


if __name__ == "__main__":
    unittest.main()
