import json
import unittest
from pathlib import Path

from backend.case import Case
from backend.session import Ruling, RulingError, initial_state
from backend.storyteller import Storyteller

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
        return self.replies.pop(0)


def ruling_payload(**overrides):
    payload = {
        "outcome": "failure",
        "facts": ["The crow refused to look down."],
        "scene": "She keeps the cheese and turns away.",
    }
    payload.update(overrides)
    return payload


class StorytellerTests(unittest.TestCase):
    def setUp(self):
        self.model = StubModel(
            [ruling_payload(), {"narration": "She turns her back.", "hints": ["Try the thorns."]}]
        )
        self.storyteller = Storyteller(FOX, model=self.model)

    def test_resolve_makes_one_call_per_phase(self):
        ruling, narration = self.storyteller.resolve(initial_state("zh"), "say", "喂，乌鸦")
        self.assertEqual(len(self.model.calls), 2)
        self.assertEqual(ruling.outcome, "failure")
        self.assertEqual(narration.text, "She turns her back.")
        self.assertIn("judge for this turn", self.model.calls[0]["system"])
        self.assertIn("writer for this turn", self.model.calls[1]["system"])

    def test_the_prompt_carries_the_world_in_the_session_language(self):
        self.storyteller.resolve(initial_state("zh"), "do", "拨开荆棘")
        for call in self.model.calls:
            self.assertIn(FOX.world("zh"), call["system"])
            self.assertIn("狐狸", call["system"])
            self.assertIn("The story language is zh", call["system"])

    def test_the_ruling_is_handed_to_the_narration_phase(self):
        self.storyteller.resolve(initial_state(), "do", "climb the tree")
        payload = json.loads(self.model.calls[1]["user"].split("\n", 1)[1])
        self.assertEqual(payload["ruling"]["outcome"], "failure")
        self.assertEqual(payload["action"], {"type": "do", "text": "climb the tree"})

    def test_another_case_uses_its_own_world(self):
        model = StubModel([ruling_payload(), {"narration": "You wait."}])
        Storyteller(CINDERELLA, model=model).resolve(initial_state("en"), "do", "wait")
        self.assertIn(CINDERELLA.world("en"), model.calls[0]["system"])
        self.assertIn("Cinderella", model.calls[0]["system"])

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

    def test_the_opening_comes_from_the_case(self):
        self.assertEqual(self.storyteller.opening("zh"), FOX.opening("zh"))


if __name__ == "__main__":
    unittest.main()
