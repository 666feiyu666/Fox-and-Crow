import json
import tempfile
import unittest
from pathlib import Path

from backend.case import Case, CaseError

CASE_ROOT = Path(__file__).resolve().parents[2] / "cases"


def write_case(
    directory: Path,
    *,
    clock=None,
    meters=None,
    ending=None,
    title=None,
) -> Path:
    settings = {
        "title": title or {"en": "Test Story", "zh": "测试故事"},
        "player_character": "the test walker",
        "meters": meters if meters is not None else {"trust": {"start": 0, "min": -3, "max": 6}},
        "ending": ending if ending is not None else {"min_turns": 3, "requires": {}},
    }
    if clock is not None:
        settings["clock"] = clock
    (directory / "case.json").write_text(
        json.dumps({"case_id": "test-case", "storyteller": settings}), encoding="utf-8"
    )
    (directory / "world.md").write_text("# World\n\nA quiet room.", encoding="utf-8")
    (directory / "openings.json").write_text(
        json.dumps({"en": {"text": "A room."}, "zh": {"text": "一间屋子。"}}), encoding="utf-8"
    )
    return directory


class FoxAndCrowCaseTests(unittest.TestCase):
    def setUp(self):
        self.case = Case.load(CASE_ROOT / "fox-and-crow")

    def test_reads_case_identity_and_canon(self):
        self.assertEqual(self.case.id, "fox-and-crow-no-deception")
        self.assertEqual(self.case.character_name("en"), "the fox")
        self.assertIn("The crow", self.case.world)
        self.assertIn("dungeon master", self.case.instructions.lower())

    def test_titles_and_openings_are_bilingual(self):
        self.assertEqual(self.case.title("zh"), "狐狸与乌鸦：循环中的一天")
        self.assertIn("moss", self.case.opening("en"))
        self.assertIn("苔藓", self.case.opening("zh"))
        self.assertEqual(self.case.opening("fr"), self.case.opening("en"))

    def test_declares_clock_meters_and_ending(self):
        self.assertIsNotNone(self.case.clock)
        self.assertEqual(self.case.clock.units_per_day, 6)
        self.assertTrue(self.case.clock.loops)
        self.assertEqual(self.case.clock.reset_on_loop, ("trust",))
        self.assertEqual((self.case.meter("trust").minimum, self.case.meter("trust").maximum), (-3, 6))
        self.assertEqual(self.case.ending.min_turns, 8)
        self.assertEqual(dict(self.case.ending.requires), {"trust": 3, "insight": 3})

    def test_system_prompt_carries_skill_canon_and_phase(self):
        prompt = self.case.system_prompt("PHASE-MARKER")
        self.assertIn(self.case.instructions, prompt)
        self.assertIn(self.case.world, prompt)
        self.assertIn("PHASE-MARKER", prompt)


class CinderellaCaseTests(unittest.TestCase):
    def setUp(self):
        self.case = Case.load(CASE_ROOT / "cinderella")

    def test_declares_no_clock(self):
        self.assertIsNone(self.case.clock)

    def test_declares_its_own_meters(self):
        self.assertEqual({meter.id for meter in self.case.meters}, {"resolve", "bond"})
        self.assertEqual(self.case.meter("resolve").start, 1)
        self.assertEqual((self.case.meter("bond").minimum, self.case.meter("bond").maximum), (-3, 6))

    def test_ending_has_no_meter_requirement_but_needs_turns(self):
        self.assertEqual(self.case.ending.min_turns, 6)
        self.assertEqual(dict(self.case.ending.requires), {})

    def test_titles_and_openings_are_bilingual(self):
        self.assertEqual(self.case.title("zh"), "灰姑娘：玻璃鞋之外")
        self.assertIn("Ash", self.case.opening("en"))
        self.assertIn("灰", self.case.opening("zh"))

    def test_player_character_is_cinderella(self):
        self.assertEqual(self.case.character_name("en"), "Cinderella")
        self.assertEqual(self.case.character_name("zh"), "灰姑娘")
        self.assertIn("stepmother", self.case.world)


class CaseValidationTests(unittest.TestCase):
    def test_clock_is_optional(self):
        with tempfile.TemporaryDirectory() as directory:
            case = Case.load(write_case(Path(directory)))
        self.assertIsNone(case.clock)

    def test_rejects_missing_storyteller_block(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)
            (path / "case.json").write_text(json.dumps({"case_id": "x"}), encoding="utf-8")
            (path / "world.md").write_text("w", encoding="utf-8")
            (path / "openings.json").write_text(json.dumps({"en": {"text": "a"}}), encoding="utf-8")
            with self.assertRaises(CaseError):
                Case.load(path)

    def test_rejects_ending_requiring_unknown_meter(self):
        with tempfile.TemporaryDirectory() as directory:
            path = write_case(
                Path(directory),
                ending={"min_turns": 2, "requires": {"courage": 1}},
            )
            with self.assertRaises(CaseError):
                Case.load(path)

    def test_rejects_loop_resetting_unknown_meter(self):
        with tempfile.TemporaryDirectory() as directory:
            path = write_case(
                Path(directory),
                clock={"units_per_day": 4, "loops": True, "reset_meters_on_loop": ["ghost"]},
            )
            with self.assertRaises(CaseError):
                Case.load(path)

    def test_rejects_meter_start_outside_range(self):
        with tempfile.TemporaryDirectory() as directory:
            path = write_case(
                Path(directory),
                meters={"trust": {"start": 9, "min": 0, "max": 5}},
            )
            with self.assertRaises(CaseError):
                Case.load(path)

    def test_missing_english_title_is_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            path = write_case(Path(directory), title={"zh": "测试故事"})
            with self.assertRaises(CaseError):
                Case.load(path)


if __name__ == "__main__":
    unittest.main()
