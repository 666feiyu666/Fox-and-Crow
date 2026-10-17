import json
import tempfile
import unittest
from pathlib import Path

from backend.case import Case
from backend.session import Ruling, RulingError, initial_state
from backend.storyteller import Storyteller
from tests.test_case import CASE_ROOT, write_case

FOX = Case.load(CASE_ROOT / "fox-and-crow")


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
        "time_cost": 1,
        "meters": {"trust": 0, "insight": 1},
        "facts": ["The crow refused to look down."],
        "scene": "She keeps the cheese and turns away.",
        "ending": "none",
    }
    payload.update(overrides)
    return payload


class StorytellerTests(unittest.TestCase):
    def setUp(self):
        self.model = StubModel(
            [
                ruling_payload(),
                {"narration": "She turns her back.", "hints": ["Try the thorns."]},
            ]
        )
        self.storyteller = Storyteller(FOX, model=self.model)

    def test_resolve_makes_two_calls_one_per_phase(self):
        ruling, narration = self.storyteller.resolve(initial_state(FOX, "zh"), "say", "喂，乌鸦")
        self.assertEqual(len(self.model.calls), 2)
        self.assertEqual(ruling.outcome, "failure")
        self.assertEqual(narration.text, "She turns her back.")
        self.assertIn("phase 1 (ruling)", self.model.calls[0]["system"])
        self.assertIn("phase 2 (narration)", self.model.calls[1]["system"])

    def test_prompts_carry_engine_skill_and_case_canon(self):
        self.storyteller.resolve(initial_state(FOX), "do", "climb the tree")
        system = self.model.calls[0]["system"]
        self.assertIn(FOX.instructions, system)
        self.assertIn(FOX.world, system)

    def test_ruling_is_handed_to_the_narration_phase(self):
        self.storyteller.resolve(initial_state(FOX), "do", "climb the tree")
        payload = json.loads(self.model.calls[1]["user"].split("\n", 1)[1])
        self.assertEqual(payload["ruling"]["outcome"], "failure")
        self.assertEqual(payload["ruling"]["meters"], {"trust": 0, "insight": 1})
        self.assertEqual(payload["action"], {"type": "do", "text": "climb the tree"})

    def test_state_and_case_reach_the_model(self):
        self.storyteller.resolve(initial_state(FOX, "zh"), "say", "你好")
        payload = json.loads(self.model.calls[0]["user"].split("\n", 1)[1])
        self.assertEqual(payload["state"]["language"], "zh")
        self.assertEqual(payload["state"]["clock"]["remainingUnits"], 6)
        self.assertEqual(payload["state"]["meters"], {"trust": 0, "insight": 0})
        self.assertEqual(payload["case"]["player_character"], "the fox")

    def test_clockless_case_sends_null_clock(self):
        with tempfile.TemporaryDirectory() as directory:
            case = Case.load(write_case(Path(directory)))
        model = StubModel([ruling_payload(meters={}), {"narration": "You wait."}])
        Storyteller(case, model=model).resolve(initial_state(case), "do", "wait")
        payload = json.loads(model.calls[0]["user"].split("\n", 1)[1])
        self.assertIsNone(payload["state"]["clock"])

    def test_unusable_ruling_is_rejected(self):
        model = StubModel([{"outcome": "bogus", "time_cost": 1, "scene": "x"}])
        with self.assertRaises(RulingError):
            Storyteller(FOX, model=model).rule({"action": {"type": "do", "text": "x"}})

    def test_unusable_narration_is_rejected(self):
        model = StubModel([{"narration": ""}])
        with self.assertRaises(RulingError):
            Storyteller(FOX, model=model).narrate(
                {"action": {"type": "do", "text": "x"}},
                Ruling.from_dict(ruling_payload(), FOX),
            )

    def test_opening_comes_from_the_case(self):
        self.assertEqual(self.storyteller.opening("zh"), FOX.opening("zh"))


if __name__ == "__main__":
    unittest.main()
