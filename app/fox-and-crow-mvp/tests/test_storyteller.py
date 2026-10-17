import json
import tempfile
import unittest
from pathlib import Path

from backend.session import RulingError, initial_state
from backend.session import Ruling
from backend.storyteller import SKILL_DIR, Skill, Storyteller


class StubModel:
    configured = True

    def __init__(self, replies):
        self.replies = list(replies)
        self.calls = []

    def complete_json(self, system, user, **kwargs):
        self.calls.append({"system": system, "user": user, **kwargs})
        return self.replies.pop(0)


class SkillTests(unittest.TestCase):
    def test_loads_the_authored_skill(self):
        skill = Skill.load()
        self.assertIn("dungeon master", skill.instructions.lower())
        self.assertIn("ruling", skill.instructions)
        self.assertIn("The crow", skill.world)

    def test_system_prompt_carries_skill_world_and_phase(self):
        skill = Skill.load()
        prompt = skill.system_prompt("PHASE-MARKER")
        self.assertIn(skill.instructions, prompt)
        self.assertIn(skill.world, prompt)
        self.assertIn("PHASE-MARKER", prompt)

    def test_opening_is_available_in_both_languages(self):
        skill = Skill.load()
        self.assertTrue(skill.opening("en")["text"])
        self.assertTrue(skill.opening("zh")["text"])

    def test_opening_falls_back_to_english(self):
        skill = Skill.load()
        self.assertEqual(skill.opening("fr")["title"], skill.opening("en")["title"])

    def test_missing_skill_files_raise(self):
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaises(Exception):
                Skill.load(Path(directory))


class StorytellerTests(unittest.TestCase):
    def setUp(self):
        self.model = StubModel(
            [
                {
                    "outcome": "failure",
                    "time_cost": 1,
                    "trust": -1,
                    "insight": 1,
                    "facts": ["The crow refused to look down."],
                    "scene": "She keeps the cheese and turns away.",
                    "ending": "none",
                },
                {"narration": "She turns her back.", "hints": ["Try the thorns."]},
            ]
        )
        self.storyteller = Storyteller(model=self.model)

    def test_resolve_makes_two_calls_one_per_phase(self):
        ruling, narration = self.storyteller.resolve(initial_state("zh"), "say", "喂，乌鸦")
        self.assertEqual(len(self.model.calls), 2)
        self.assertEqual(ruling.outcome, "failure")
        self.assertEqual(narration.text, "She turns her back.")
        self.assertIn("phase 1 (ruling)", self.model.calls[0]["system"])
        self.assertIn("phase 2 (narration)", self.model.calls[1]["system"])

    def test_ruling_is_handed_to_the_narration_phase(self):
        self.storyteller.resolve(initial_state(), "do", "climb the tree")
        payload = json.loads(self.model.calls[1]["user"].split("\n", 1)[1])
        self.assertEqual(payload["ruling"]["outcome"], "failure")
        self.assertEqual(payload["action"], {"type": "do", "text": "climb the tree"})

    def test_language_and_state_reach_the_model(self):
        state = initial_state("zh")
        self.storyteller.resolve(state, "say", "你好")
        payload = json.loads(self.model.calls[0]["user"].split("\n", 1)[1])
        self.assertEqual(payload["state"]["language"], "zh")
        self.assertEqual(payload["state"]["loop"], 1)
        self.assertEqual(payload["state"]["remainingUnits"], 6)

    def test_unusable_ruling_is_rejected(self):
        model = StubModel([{"outcome": "bogus", "time_cost": 1, "scene": "x"}])
        with self.assertRaises(RulingError):
            Storyteller(model=model).rule({"action": {"type": "do", "text": "x"}})

    def test_unusable_narration_is_rejected(self):
        model = StubModel([{"narration": ""}])
        with self.assertRaises(RulingError):
            Storyteller(model=model).narrate(
                {"action": {"type": "do", "text": "x"}},
                Ruling.from_dict(
                    {
                        "outcome": "failure",
                        "time_cost": 1,
                        "trust": 0,
                        "insight": 1,
                        "facts": [],
                        "scene": "She turns away.",
                        "ending": "none",
                    }
                ),
            )


if __name__ == "__main__":
    unittest.main()
