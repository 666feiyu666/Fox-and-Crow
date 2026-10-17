import json
import tempfile
import unittest
from pathlib import Path

from backend.case import Case, CaseError
from backend.understanding import Understanding
from tests.fixtures import understanding_payload

CASE_ROOT = Path(__file__).resolve().parents[2] / "cases"

DERIVED = Understanding.from_dict(understanding_payload(player="the fox"))


def write_case(directory: Path, *, title=None, skip=None) -> Path:
    directory.mkdir(parents=True, exist_ok=True)
    (directory / "case.json").write_text(
        json.dumps(
            {
                "id": "test-case",
                "title": title or {"en": "Test Story", "zh": "测试故事"},
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    for language in ("en", "zh"):
        if skip == f"source.{language}":
            continue
        (directory / f"source.{language}.md").write_text(
            f"a tale in {language}.", encoding="utf-8"
        )
    return directory


class FoxAndCrowCaseTests(unittest.TestCase):
    def setUp(self):
        self.case = Case.load(CASE_ROOT / "fox-and-crow")

    def test_reads_the_tale_in_both_languages(self):
        self.assertEqual(self.case.id, "fox-and-crow")
        self.assertEqual(self.case.title("en"), "The Fox and the Crow")
        self.assertEqual(self.case.title("zh"), "狐狸与乌鸦")
        self.assertIn("crow", self.case.source("en").lower())
        self.assertIn("乌鸦", self.case.source("zh"))

    def test_each_agent_skill_declares_name_and_description(self):
        for skill in (self.case.understand, self.case.judge, self.case.writer, self.case.reader_review):
            self.assertTrue(skill.startswith("---"), "skill must open with front matter")
            front_matter = skill.split("---")[1]
            self.assertIn("name:", front_matter)
            self.assertIn("description:", front_matter)

    def test_four_agent_skills_are_shared_by_every_case(self):
        self.assertIn("understander", self.case.understand.lower())
        self.assertIn("judge", self.case.judge.lower())
        self.assertIn("writer", self.case.writer.lower())
        self.assertIn("content editor", self.case.reader_review.lower())
        skills = (self.case.understand + self.case.judge + self.case.writer
                  + self.case.reader_review).lower()
        self.assertNotIn("fox", skills)
        self.assertNotIn("cinderella", skills)

    def test_understand_prompt_carries_the_tale(self):
        prompt = self.case.understand_prompt("zh")
        self.assertIn(self.case.source("zh"), prompt)
        self.assertIn("The story language is zh", prompt)

    def test_judge_gets_private_space_while_writer_gets_only_voice(self):
        english = self.case.judge_prompt("en", DERIVED)
        chinese = self.case.writer_prompt("zh", DERIVED)
        self.assertIn(DERIVED.canon, english)
        self.assertNotIn(DERIVED.canon, chinese)
        self.assertNotIn("hidden-password", chinese)
        self.assertNotIn("negotiate", chinese)
        self.assertIn(DERIVED.space.style, chinese)
        self.assertIn("Writing craft for playable passages", chinese)
        self.assertIn("the fox", english)
        self.assertIn("The story language is zh", chinese)
        review = self.case.review_prompt("en", DERIVED)
        self.assertIn(DERIVED.canon, review)
        self.assertIn("hidden-password", review)

    def test_unknown_language_falls_back_to_english(self):
        self.assertEqual(self.case.source("fr"), self.case.source("en"))


class CinderellaCaseTests(unittest.TestCase):
    def setUp(self):
        self.case = Case.load(CASE_ROOT / "cinderella")

    def test_is_its_own_story(self):
        self.assertEqual(self.case.id, "cinderella")
        self.assertEqual(self.case.title("zh"), "灰姑娘")
        self.assertIn("slipper", self.case.source("en").lower())
        self.assertIn("玻璃鞋", self.case.source("zh"))


class CaseValidationTests(unittest.TestCase):
    def test_accepts_a_minimal_case(self):
        with tempfile.TemporaryDirectory() as directory:
            case = Case.load(write_case(Path(directory)))
        self.assertEqual(case.id, "test-case")
        self.assertEqual(case.source("zh"), "a tale in zh.")
        self.assertEqual(case.directory, Path(directory))

    def test_missing_language_file_is_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            write_case(Path(directory), skip="source.zh")
            with self.assertRaises(CaseError):
                Case.load(Path(directory))

    def test_missing_translation_is_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            write_case(Path(directory), title={"en": "Only English"})
            with self.assertRaises(CaseError):
                Case.load(Path(directory))

    def test_empty_tale_is_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            write_case(Path(directory))
            (Path(directory) / "source.en.md").write_text("   ", encoding="utf-8")
            with self.assertRaises(CaseError):
                Case.load(Path(directory))


if __name__ == "__main__":
    unittest.main()
