import unittest

from backend.story_runtime.state import (
    STORY_CONTEXT_TURNS,
    TOTAL_TIME_UNITS,
    advance_after_story,
    initial_story_state,
    player_view,
    story_agent_context,
)


class StoryRuntimeTests(unittest.TestCase):
    def test_initial_player_view_contains_only_loop_and_time(self):
        view = player_view(initial_story_state(loop_count=3))
        self.assertEqual(
            view,
            {
                "loopCount": 3,
                "elapsedUnits": 0,
                "remainingUnits": TOTAL_TIME_UNITS,
                "totalUnits": TOTAL_TIME_UNITS,
                "timePhase": "morning",
            },
        )

    def test_successful_story_advances_exactly_one_unit(self):
        before = initial_story_state()
        after, outcome = advance_after_story(
            before,
            "say",
            "Are you afraid?",
            "I ask the question. The crow goes still.",
        )
        self.assertEqual(outcome, "continue")
        self.assertEqual(after.elapsed_units, 1)
        self.assertEqual(after.remaining_units, TOTAL_TIME_UNITS - 1)
        self.assertEqual(before.elapsed_units, 0)

    def test_time_exhaustion_unconditionally_starts_next_loop(self):
        state = initial_story_state(loop_count=2)
        for index in range(TOTAL_TIME_UNITS):
            state, outcome = advance_after_story(
                state,
                "do",
                f"wait {index}",
                f"I wait {index}.",
            )
        self.assertEqual(outcome, "loop_advanced")
        self.assertEqual(state.loop_count, 3)
        self.assertEqual(state.elapsed_units, 0)

    def test_story_context_keeps_only_five_visible_turns(self):
        state = initial_story_state()
        for index in range(STORY_CONTEXT_TURNS + 2):
            state, _ = advance_after_story(
                state,
                "do",
                f"action {index}",
                f"result {index}",
            )
        context = story_agent_context(state, "say", "Hello.")
        history = context["recentVisibleTurns"]
        self.assertEqual(len(history), STORY_CONTEXT_TURNS)
        self.assertEqual(history[0]["playerInput"], "action 2")
        self.assertEqual(context["input"], {"type": "say", "text": "Hello."})


if __name__ == "__main__":
    unittest.main()
