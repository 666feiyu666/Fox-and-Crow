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
        self.assertIn('button.textContent = "Day " + dayRecord.day;', self.source)
        self.assertIn('title.textContent = "Day " + selected.day;', self.source)
        self.assertNotIn('State.variables.storyFirstActive ? "Loop " : "Day "', self.source)
        self.assertIn("width: min(64rem, calc(100% - 2rem));", self.source)
        self.assertIn("height: min(82vh, 48rem);", self.source)
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
        self.assertIn(
            '["127.0.0.1", "localhost"].includes(window.location.hostname)',
            self.source,
        )
        self.assertIn('"https://fox-and-crow-story-api.onrender.com"', self.source)
        self.assertIn("function storyApiUrl(path)", self.source)
        self.assertIn("fetch(storyApiUrl(path)", self.source)

    def test_node_25_starts_at_a_welcome_page_with_direct_and_prologue_entries(self):
        self.assertIn('"start": "Welcome"', self.source)
        self.assertIn("Start the Story-first experience", self.source)
        self.assertIn("Play the complete fable prologue first", self.source)
        self.assertIn("STORY-FIRST · NODE 2.5", self.source)

    def test_say_do_controls_send_the_declared_contract(self):
        self.assertIn('name="story-input-type" value="say"', self.source)
        self.assertIn('name="story-input-type" value="do"', self.source)
        self.assertIn("inputType: inputType", self.source)
        self.assertIn("content: action", self.source)
        self.assertIn('entry.inputType === "say" ? "YOU SAID" : "YOU DID"', self.source)

    def test_story_first_ui_keeps_runtime_counters_internal(self):
        self.assertIn("If a request fails, your input stays here so you can retry.", self.source)
        self.assertIn("min-width: 0;", self.source)
        self.assertIn("max-width: 100%;", self.source)
        self.assertIn("State.variables.remainingUnits = playerState.remainingUnits;", self.source)
        self.assertNotIn('class="time-card"', self.source)
        self.assertNotIn("time-status", self.source)
        self.assertNotIn("Units left", self.source)
        self.assertNotIn("time units remain in this loop", self.source)
        self.assertNotIn("A successful response costs one time unit", self.source)
        self.assertNotIn("fox-memory-list", self.source)

    def test_storybook_theme_uses_warm_paper_and_graphite_instead_of_dark_ui(self):
        self.assertIn("color-scheme: light;", self.source)
        self.assertIn("--paper: #f1ecda;", self.source)
        self.assertIn("--ink: #38372f;", self.source)
        self.assertIn('"Cormorant Garamond"', self.source)
        self.assertNotIn("color-scheme: dark;", self.source)
        self.assertNotIn("#151915", self.source)
        self.assertNotIn("rgba(8, 10, 8", self.source)

    def test_story_input_keeps_an_opaque_light_surface_in_embedded_browsers(self):
        self.assertIn("color-scheme: only light;", self.source)
        self.assertIn("background: var(--paper-clear);", self.source)
        self.assertIn("-webkit-text-fill-color: var(--ink);", self.source)
        self.assertIn("-webkit-text-fill-color: rgba(86, 82, 71, 0.65);", self.source)
        self.assertIn("opacity: 1;", self.source)
        self.assertIn(".ai-action-input:not(:disabled):hover,", self.source)
        self.assertIn(".ai-action-input:not(:disabled):focus {", self.source)
        self.assertIn("background-color: var(--paper-clear);", self.source)

    def test_second_day_repeats_the_fable_to_test_the_crows_memory(self):
        self.assertIn("Another piece? So soon?", self.source)
        self.assertIn("Has she truly forgotten?", self.source)
        self.assertIn("Test her with the same compliment", self.source)
        self.assertIn("Whether the crow forgot—or was made to forget", self.source)

    def test_third_day_offers_two_authored_scripts_and_free_action(self):
        self.assertIn("Repeat the familiar story", self.source)
        self.assertIn("Explore the world beyond the tree", self.source)
        self.assertIn("SAY or DO something else", self.source)
        self.assertIn('<<goto "Explore the Clearing">>', self.source)
        self.assertIn("Follow the path between the pines", self.source)
        self.assertIn("Walk downstream and study the water", self.source)
        self.assertIn("Circle the edge of the clearing", self.source)

    def test_exploration_script_stays_about_world_exploration(self):
        self.assertIn(":: A Mark for Tomorrow", self.source)
        self.assertIn(":: The World's Shape", self.source)
        self.assertIn("Carry your map of the world into another morning", self.source)
        self.assertIn("setup.activateFreeStory(4)", self.source)
        self.assertNotIn("looking toward the bushes", self.source)
        self.assertNotIn("thorn bush", self.source)
        self.assertNotIn("anxious glances", self.source)


if __name__ == "__main__":
    unittest.main()
