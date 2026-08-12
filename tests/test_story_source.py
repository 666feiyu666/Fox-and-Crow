import unittest
from pathlib import Path


STORY_SOURCE = Path(__file__).parents[1] / "src" / "story.twee"


class StorySourceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.source = STORY_SOURCE.read_text(encoding="utf-8")

    def test_story_log_is_rendered_from_a_real_passage_header(self):
        self.assertIn(":: PassageHeader [nobr]", self.source)
        self.assertIn('class="story-log-open"', self.source)
        self.assertNotIn(":: StoryDisplay [nobr]", self.source)

    def test_fixed_choices_call_the_sugarcube_setup_function(self):
        self.assertIn(
            '<<run setup.setPendingStoryAction("Watch the crow in the tree")>>',
            self.source,
        )
        self.assertNotIn("<<run setPendingStoryAction(", self.source)

    def test_restart_has_confirmation_and_server_cleanup(self):
        self.assertIn('class="story-restart-confirmation"', self.source)
        self.assertIn('postStoryJson("/api/session/reset"', self.source)
        self.assertIn("Engine.restart();", self.source)

    def test_api_origin_is_configured_once_and_applied_to_every_api_path(self):
        self.assertIn('var storyApiBaseUrl = "";', self.source)
        self.assertIn("function storyApiUrl(path)", self.source)
        self.assertIn("fetch(storyApiUrl(path)", self.source)


if __name__ == "__main__":
    unittest.main()
