import json
import tempfile
import unittest
from pathlib import Path

from backend.understanding import (
    Understanding,
    UnderstandingCache,
    UnderstandingError,
    source_digest,
)
from tests.fixtures import understanding_payload


def payload(**overrides):
    return understanding_payload(**{"player": "the fox", **overrides})


class UnderstandingTests(unittest.TestCase):
    def test_parses_a_complete_derivation(self):
        understanding = Understanding.from_dict(payload())
        self.assertEqual(understanding.player, "the fox")
        self.assertIn("Premise", understanding.canon)
        self.assertEqual(set(understanding.to_dict()), {"player", "canon", "opening", "space"})

    def test_source_evidence_must_actually_exist(self):
        understanding = Understanding.from_dict(payload())
        understanding.validate_source("a tale")
        with self.assertRaises(UnderstandingError):
            understanding.validate_source("another source")

    def test_source_evidence_may_rejoin_a_wrapped_line(self):
        data = payload()
        data["space"]["anchors"] = [
            {"fact": "The crow settled in a tree.", "quote": "settled on a high branch to eat it in peace"}
        ]
        understanding = Understanding.from_dict(data)
        understanding.validate_source(
            "A crow, having found a piece of cheese, settled on a high branch to eat it in\npeace."
        )
        with self.assertRaises(UnderstandingError):
            understanding.validate_source("A crow settled on a branch and ate quietly.")

    def test_source_evidence_cannot_span_two_paragraphs(self):
        data = payload()
        data["space"]["anchors"] = [{"fact": "Two passages.", "quote": "first line and second part"}]
        understanding = Understanding.from_dict(data)
        with self.assertRaises(UnderstandingError):
            understanding.validate_source("first line\n\nsecond part")

    def test_space_rejects_ambiguous_or_incomplete_structure(self):
        for field, value in (("anchors", []), ("fixed_keys", ["unknown"]),
                             ("possibilities", "not an array"), ("style", "")):
            data = payload()
            data["space"][field] = value
            with self.subTest(field=field), self.assertRaises(UnderstandingError):
                Understanding.from_dict(data)

    def test_duplicate_initial_property_keys_are_rejected(self):
        data = payload()
        data["space"]["initial_facts"].append(data["space"]["initial_facts"][0])
        with self.assertRaises(UnderstandingError):
            Understanding.from_dict(data)

    def test_possibilities_do_not_become_initial_facts(self):
        understanding = Understanding.from_dict(payload())
        self.assertNotIn("negotiate", str(understanding.space.initial_facts))
        self.assertIn("negotiate", str(understanding.space.possibilities))

    def test_rejects_missing_or_blank_fields(self):
        for field in ("player", "canon", "opening"):
            with self.assertRaises(UnderstandingError):
                Understanding.from_dict(payload(**{field: "   "}))
        with self.assertRaises(UnderstandingError):
            Understanding.from_dict({"player": "x"})
        with self.assertRaises(UnderstandingError):
            Understanding.from_dict("not an object")

    def test_keeps_multi_line_canon(self):
        canon = "# World\n\n## Cast\n\n- the fox\n- the crow"
        self.assertEqual(Understanding.from_dict(payload(canon=canon)).canon, canon)


class SourceDigestTests(unittest.TestCase):
    def test_digest_ignores_surrounding_whitespace(self):
        self.assertEqual(source_digest("a tale\n"), source_digest("  a tale  "))

    def test_digest_changes_when_the_tale_changes(self):
        self.assertNotEqual(source_digest("a tale"), source_digest("a tale, edited"))


class CacheTests(unittest.TestCase):
    def setUp(self):
        self.tempdir = tempfile.TemporaryDirectory()
        self.addCleanup(self.tempdir.cleanup)
        self.cache = UnderstandingCache(Path(self.tempdir.name))

    def test_round_trip(self):
        understanding = Understanding.from_dict(payload())
        digest = source_digest("a tale")
        path = self.cache.write("en", digest, understanding)
        self.assertTrue(path.is_file())
        self.assertEqual(self.cache.read("en", digest), understanding)

    def test_missing_cache_is_none(self):
        self.assertIsNone(self.cache.read("zh", source_digest("a tale")))

    def test_an_edited_source_invalidates_the_cache(self):
        understanding = Understanding.from_dict(payload())
        self.cache.write("en", source_digest("a tale"), understanding)
        self.assertIsNone(self.cache.read("en", source_digest("a tale, edited")))

    def test_languages_are_cached_separately(self):
        english = Understanding.from_dict(payload())
        chinese = Understanding.from_dict(
            payload(player="狐狸", canon="# 世界\n\n## 设定\n一座森林。", opening="湿苔藓。")
        )
        digest = source_digest("a tale")
        self.cache.write("en", digest, english)
        self.cache.write("zh", digest, chinese)
        self.assertEqual(self.cache.read("en", digest).player, "the fox")
        self.assertEqual(self.cache.read("zh", digest).player, "狐狸")

    def test_a_corrupt_cache_file_is_ignored(self):
        digest = source_digest("a tale")
        path = self.cache.path("en")
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("{not json", encoding="utf-8")
        self.assertIsNone(self.cache.read("en", digest))

    def test_an_older_cache_version_is_ignored(self):
        digest = source_digest("a tale")
        path = self.cache.path("en")
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps({"version": 0, "source_digest": digest, "understanding": payload()}),
            encoding="utf-8",
        )
        self.assertIsNone(self.cache.read("en", digest))


if __name__ == "__main__":
    unittest.main()
