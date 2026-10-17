import json
import tempfile
import unittest
from pathlib import Path

from backend.case import Case, CaseError

CASE_ROOT = Path(__file__).resolve().parents[2] / "cases"


def write_case(directory: Path, *, title=None, player=None, skip=None) -> Path:
    directory.mkdir(parents=True, exist_ok=True)
    (directory / "case.json").write_text(
        json.dumps(
            {
                "id": "test-case",
                "title": title or {"en": "Test Story", "zh": "测试故事"},
                "player": player or {"en": "the tester", "zh": "测试者"},
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    for language in ("en", "zh"):
        for kind in ("world", "opening"):
            if skip == f"{kind}.{language}":
                continue
            (directory / f"{kind}.{language}.md").write_text(
                f"{kind} in {language}.", encoding="utf-8"
            )
    return directory


class FoxAndCrowCaseTests(unittest.TestCase):
    def setUp(self):
        self.case = Case.load(CASE_ROOT / "fox-and-crow")

    def test_reads_the_story_in_both_languages(self):
        self.assertEqual(self.case.id, "fox-and-crow")
        self.assertEqual(self.case.title("en"), "The Fox and the Crow")
        self.assertEqual(self.case.title("zh"), "狐狸与乌鸦")
        self.assertEqual(self.case.player("en"), "the fox")
        self.assertEqual(self.case.player("zh"), "狐狸")
        self.assertIn("the crow", self.case.world("en").lower())
        self.assertIn("乌鸦", self.case.world("zh"))
        self.assertIn("moss", self.case.opening("en"))
        self.assertIn("苔藓", self.case.opening("zh"))

    def test_both_agent_skills_are_shared_by_every_case(self):
        self.assertIn("judge", self.case.judge.lower())
        self.assertIn("writer", self.case.writer.lower())
        skills = (self.case.judge + self.case.writer).lower()
        self.assertNotIn("fox", skills)
        self.assertNotIn("cinderella", skills)

    def test_prompts_follow_the_session_language(self):
        english = self.case.judge_prompt("en")
        chinese = self.case.writer_prompt("zh")
        self.assertIn(self.case.world("en"), english)
        self.assertIn(self.case.world("zh"), chinese)
        self.assertIn("the fox", english)
        self.assertIn("狐狸", chinese)
        self.assertIn("The story language is zh", chinese)

    def test_unknown_language_falls_back_to_english(self):
        self.assertEqual(self.case.world("fr"), self.case.world("en"))
        self.assertEqual(self.case.opening("fr"), self.case.opening("en"))


class CinderellaCaseTests(unittest.TestCase):
    def setUp(self):
        self.case = Case.load(CASE_ROOT / "cinderella")

    def test_is_its_own_story(self):
        self.assertEqual(self.case.id, "cinderella")
        self.assertEqual(self.case.player("zh"), "灰姑娘")
        self.assertIn("stepmother", self.case.world("en"))
        self.assertIn("继母", self.case.world("zh"))

    def test_opening_is_unnarrated_setting(self):
        self.assertIn("Ash", self.case.opening("en"))
        self.assertIn("灰", self.case.opening("zh"))


class CaseValidationTests(unittest.TestCase):
    def test_accepts_a_minimal_case(self):
        with tempfile.TemporaryDirectory() as directory:
            case = Case.load(write_case(Path(directory)))
        self.assertEqual(case.id, "test-case")
        self.assertEqual(case.world("zh"), "world in zh.")

    def test_missing_language_file_is_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            write_case(Path(directory), skip="world.zh")
            with self.assertRaises(CaseError):
                Case.load(Path(directory))

    def test_missing_translation_is_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            write_case(Path(directory), title={"en": "Only English"})
            with self.assertRaises(CaseError):
                Case.load(Path(directory))

    def test_empty_document_is_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            write_case(Path(directory))
            (Path(directory) / "opening.en.md").write_text("   ", encoding="utf-8")
            with self.assertRaises(CaseError):
                Case.load(Path(directory))


if __name__ == "__main__":
    unittest.main()
