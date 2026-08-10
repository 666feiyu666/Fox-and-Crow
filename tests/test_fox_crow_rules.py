import unittest
from dataclasses import replace

from backend.game_system.state import DayOutcome, initial_game_state
from backend.game_system.fox_crow import (
    CROW_PROBLEM_MEMORY,
    FoxCrowEvent,
    FoxCrowIntent,
    FoxCrowRuleError,
    GameAgentDecision,
    story_agent_view,
    game_agent_view,
    parse_game_agent_decision,
    public_event_view,
    resolve_fox_crow_turn,
)
from backend.infrastructure.session_store import (
    InMemoryGameSessionStore,
    SessionStoreError,
)


def fox_crow_state():
    state = initial_game_state()
    return replace(state, loop=replace(state.loop, loop_count=3))


class FoxCrowFlowTests(unittest.TestCase):
    def test_golden_path_reveals_finds_returns_and_escapes(self):
        asked = resolve_fox_crow_turn(
            fox_crow_state(),
            GameAgentDecision(FoxCrowIntent.ASK_PROBLEM, 1),
        )

        self.assertEqual(asked.outcome, DayOutcome.ACTIVE)
        self.assertTrue(asked.state.day.crow.problem_revealed)
        self.assertEqual(asked.state.day.crow.trust, 1)
        self.assertIn(CROW_PROBLEM_MEMORY, asked.state.loop.fox_memories)

        found = resolve_fox_crow_turn(
            asked.state,
            GameAgentDecision(FoxCrowIntent.SEARCH_NECKLACE, 2),
        )
        self.assertEqual(found.outcome, DayOutcome.ACTIVE)
        self.assertEqual(game_agent_view(found.state)["necklace"]["status"], "found")
        self.assertIn("crow_necklace", found.state.day.fox.inventory)

        returned = resolve_fox_crow_turn(
            found.state,
            GameAgentDecision(FoxCrowIntent.RETURN_NECKLACE, 1),
        )
        view = game_agent_view(returned.state)
        self.assertEqual(returned.outcome, DayOutcome.LOOP_ESCAPED)
        self.assertEqual(view["necklace"]["status"], "returned")
        self.assertEqual(view["crow"]["trust"], 3)
        self.assertEqual(view["relationship"]["supportiveActions"], 1)
        self.assertEqual(view["relationship"]["reciprocalActions"], 1)
        self.assertEqual(view["remainingTime"], 0)

    def test_search_without_learning_the_problem_does_not_find_necklace(self):
        result = resolve_fox_crow_turn(
            fox_crow_state(),
            GameAgentDecision(FoxCrowIntent.SEARCH_NECKLACE, 2),
        )

        self.assertEqual(game_agent_view(result.state)["necklace"]["status"], "lost")
        self.assertNotIn("crow_necklace", result.state.day.fox.inventory)
        self.assertEqual(
            result.events,
            (
                FoxCrowEvent.FOX_SEARCHES_BUSHES,
                FoxCrowEvent.SEARCH_INCONCLUSIVE,
            ),
        )
        public_events = public_event_view(result)
        serialized = " ".join(event["description"] for event in public_events)
        self.assertNotIn("necklace", serialized.casefold())
        self.assertIn("nothing conclusive", serialized)

    def test_other_action_exposes_only_its_confirmed_public_event(self):
        result = resolve_fox_crow_turn(
            fox_crow_state(),
            GameAgentDecision(FoxCrowIntent.OTHER, 1),
        )

        self.assertEqual(result.events, (FoxCrowEvent.TIME_PASSES_HUNGRIER,))
        self.assertEqual(
            public_event_view(result),
            [
                {
                    "event": "time_passes_hungrier",
                    "description": "Time passes, and you feel hungrier.",
                }
            ],
        )
        self.assertNotIn("necklace", str(story_agent_view(result.state)).casefold())

    def test_failed_day_resets_world_but_preserves_fox_memory(self):
        asked = resolve_fox_crow_turn(
            fox_crow_state(),
            GameAgentDecision(FoxCrowIntent.ASK_PROBLEM, 1),
        )
        reset = resolve_fox_crow_turn(
            asked.state,
            GameAgentDecision(FoxCrowIntent.OTHER, 5),
        )

        self.assertEqual(reset.outcome, DayOutcome.FOX_STARVED)
        self.assertEqual(reset.state.loop.loop_count, 4)
        self.assertIn(CROW_PROBLEM_MEMORY, reset.state.loop.fox_memories)
        self.assertFalse(reset.state.day.crow.problem_revealed)
        self.assertEqual(game_agent_view(reset.state)["necklace"]["status"], "lost")

    def test_game_agent_payload_is_strict_and_time_bounded(self):
        state = fox_crow_state()
        decision = parse_game_agent_decision(
            {"intent": "ask_problem", "timeCost": 1},
            state,
        )
        self.assertEqual(decision.intent, FoxCrowIntent.ASK_PROBLEM)

        with self.assertRaisesRegex(FoxCrowRuleError, "only intent and timeCost"):
            parse_game_agent_decision(
                {"intent": "ask_problem", "timeCost": 1, "friendship": True},
                state,
            )
        with self.assertRaisesRegex(FoxCrowRuleError, "time remaining"):
            parse_game_agent_decision(
                {"intent": "other", "timeCost": 7},
                state,
            )

    def test_session_commit_detects_stale_turn(self):
        store = InMemoryGameSessionStore()
        session_id, original = store.create(loop_count=3)
        updated = resolve_fox_crow_turn(
            original,
            GameAgentDecision(FoxCrowIntent.ASK_PROBLEM, 1),
        ).state

        store.commit(session_id, original, updated)
        with self.assertRaisesRegex(SessionStoreError, "story changed"):
            store.commit(session_id, original, updated)

    def test_discarded_session_cannot_be_read_or_committed(self):
        store = InMemoryGameSessionStore()
        session_id, original = store.create(loop_count=3)

        store.discard(session_id)
        store.discard(session_id)

        with self.assertRaisesRegex(SessionStoreError, "Unknown or expired"):
            store.get(session_id)
        with self.assertRaisesRegex(SessionStoreError, "Unknown or expired"):
            store.commit(session_id, original, original)


if __name__ == "__main__":
    unittest.main()
