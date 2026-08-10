import http.client
import io
import json
import os
import tempfile
import threading
import unittest
from pathlib import Path
from unittest.mock import patch
from urllib.error import HTTPError

from backend.server import create_server
from backend.game_system.fox_crow import game_agent_view
from backend.infrastructure.deepseek import (
    ConfigurationError,
    DeepSeekAgentGateway,
    DeepSeekError,
    load_env_local,
)
from backend.infrastructure.session_store import (
    InMemoryGameSessionStore,
    SessionStoreError,
)
from backend.story_agent.ports import FreeActionOutcome, NarrationAudit


class FakeHTTPResponse:
    def __init__(self, payload):
        self.payload = payload

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        return False

    def read(self):
        return json.dumps(self.payload).encode("utf-8")


class StubAgentGateway:
    def __init__(self, configured=True):
        self.configured = configured
        self.model = "test-model"
        self.calls = []
        self.game_agent_calls = []
        self.narration_calls = []
        self.audit_calls = []
        self.audit_results = []
        self.fail_game_agent = False
        self.game_agent_error = None

    def generate_free_action(self, passage, loop_count, action):
        if not self.configured:
            raise ConfigurationError(
                "DeepSeek is not configured. Set DEEPSEEK_API_KEY before starting the server."
            )
        self.calls.append((passage, loop_count, action))
        return FreeActionOutcome(
            narration="You circle the tree, and the crow watches you with new suspicion.",
            promoted=action == "Offer the crow a trade",
            choice_label="Offer a trade" if action == "Offer the crow a trade" else None,
        )

    def interpret_action(self, state, action):
        if not self.configured:
            raise ConfigurationError(
                "DeepSeek is not configured. Set DEEPSEEK_API_KEY before starting the server."
            )
        if self.game_agent_error is not None:
            raise self.game_agent_error
        if self.fail_game_agent:
            raise DeepSeekError("Resolution failed.")
        self.game_agent_calls.append((state, action))
        normalized = action.casefold()
        if "wrong" in normalized or "problem" in normalized:
            intent = "ask_problem"
            time_cost = 1
        elif "search" in normalized or "look" in normalized:
            intent = "search_necklace"
            time_cost = min(2, state["remainingTime"])
        elif "return" in normalized or "give" in normalized:
            intent = "return_necklace"
            time_cost = 1
        else:
            intent = "other"
            time_cost = 1
        return {"intent": intent, "timeCost": time_cost}

    def narrate(
        self,
        before,
        after,
        action,
        public_events,
        grounding_feedback=None,
    ):
        self.narration_calls.append(
            (before, after, action, public_events, grounding_feedback)
        )
        return " ".join(event["description"] for event in public_events)

    def audit_narration(
        self,
        before,
        after,
        action,
        public_events,
        narration,
    ):
        self.audit_calls.append((before, after, action, public_events, narration))
        if self.audit_results:
            return self.audit_results.pop(0)
        return NarrationAudit(grounded=True)

class StoryServerTests(unittest.TestCase):
    def setUp(self):
        self.client = StubAgentGateway()
        self.session_store = InMemoryGameSessionStore()
        self.server = create_server(
            port=0,
            agent_gateway=self.client,
            session_store=self.session_store,
        )
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.port = self.server.server_address[1]

    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=2)

    def request(self, method, path, payload=None):
        connection = http.client.HTTPConnection("127.0.0.1", self.port, timeout=3)
        body = None if payload is None else json.dumps(payload)
        headers = {} if body is None else {"Content-Type": "application/json"}
        connection.request(method, path, body=body, headers=headers)
        response = connection.getresponse()
        data = json.loads(response.read().decode("utf-8"))
        connection.close()
        return response.status, data

    def test_health_does_not_expose_backend_configuration(self):
        status, data = self.request("GET", "/health")

        self.assertEqual(status, 200)
        self.assertEqual(data, {"status": "ok"})

    def test_action_returns_narration_and_passes_story_state(self):
        status, data = self.request(
            "POST",
            "/api/action",
            {"passage": "Morning", "loopCount": 2, "action": "Climb the tree"},
        )

        self.assertEqual(status, 200)
        self.assertEqual(set(data), {"narration", "passage", "learnedChoice"})
        self.assertIn("crow", data["narration"])
        self.assertEqual(data["passage"], "Morning")
        self.assertIsNone(data["learnedChoice"])
        self.assertEqual(self.client.calls, [("Morning", 2, "Climb the tree")])

    def test_successful_action_returns_a_reusable_learned_choice(self):
        status, data = self.request(
            "POST",
            "/api/action",
            {"passage": "Morning", "loopCount": 1, "action": "Offer the crow a trade"},
        )

        self.assertEqual(status, 200)
        self.assertEqual(
            data["learnedChoice"],
            {"label": "Offer a trade", "action": "Offer the crow a trade"},
        )

    def test_action_rejects_empty_input_without_calling_deepseek(self):
        status, data = self.request(
            "POST",
            "/api/action",
            {"passage": "Morning", "loopCount": 0, "action": "   "},
        )

        self.assertEqual(status, 400)
        self.assertIn("Enter an action", data["error"])
        self.assertEqual(self.client.calls, [])

    def test_action_reports_missing_api_configuration(self):
        self.client.configured = False

        status, data = self.request(
            "POST",
            "/api/action",
            {"passage": "Morning", "loopCount": 0, "action": "Call to the crow"},
        )

        self.assertEqual(status, 503)
        self.assertEqual(
            data["error"],
            "The story API is not configured. Set DEEPSEEK_API_KEY and restart the server.",
        )
        self.assertNotIn("DeepSeek", data["error"])

    def test_dynamic_session_runs_the_complete_golden_path(self):
        status, created = self.request("POST", "/api/session", {"loopCount": 3})
        self.assertEqual(status, 201)
        self.assertEqual(set(created), {"sessionId", "playerState"})
        self.assertEqual(set(created["playerState"]), {"loopCount", "memories"})
        session_id = created["sessionId"]

        status, asked = self.request(
            "POST",
            "/api/turn",
            {"sessionId": session_id, "action": "What is wrong?"},
        )
        self.assertEqual(status, 200)
        self.assertEqual(
            set(asked),
            {"sessionId", "narration", "outcome", "playerState"},
        )
        self.assertEqual(set(asked["playerState"]), {"loopCount", "memories"})
        self.assertTrue(
            game_agent_view(self.session_store.get(session_id))["crow"]["problemRevealed"]
        )

        status, found = self.request(
            "POST",
            "/api/turn",
            {"sessionId": session_id, "action": "Search the bushes for the necklace"},
        )
        self.assertEqual(status, 200)
        self.assertEqual(
            game_agent_view(self.session_store.get(session_id))["necklace"]["status"],
            "found",
        )

        status, returned = self.request(
            "POST",
            "/api/turn",
            {"sessionId": session_id, "action": "Return the necklace to the crow"},
        )
        self.assertEqual(status, 200)
        self.assertEqual(returned["outcome"], "loop_escaped")
        self.assertEqual(
            set(returned),
            {"sessionId", "narration", "outcome", "playerState"},
        )
        self.assertEqual(
            game_agent_view(self.session_store.get(session_id))["necklace"]["status"],
            "returned",
        )

    def test_story_agent_receives_only_player_visible_context_and_public_events(self):
        _, created = self.request("POST", "/api/session", {"loopCount": 3})
        session_id = created["sessionId"]

        status, result = self.request(
            "POST",
            "/api/turn",
            {"sessionId": session_id, "action": "I decide to sleep and do nothing."},
        )

        self.assertEqual(status, 200)
        before, after, action, public_events, feedback = self.client.narration_calls[-1]
        story_context = json.dumps(
            {"before": before, "after": after, "publicEvents": public_events}
        ).casefold()
        game_agent_context = json.dumps(
            self.client.game_agent_calls[-1][0]
        ).casefold()
        self.assertIn("necklace", game_agent_context)
        self.assertEqual(len(self.client.game_agent_calls), 1)
        self.assertNotIn("necklace", story_context)
        self.assertNotIn("necklace", result["narration"].casefold())
        self.assertIn("hungrier", result["narration"])
        self.assertEqual(action, "I decide to sleep and do nothing.")
        self.assertIsNone(feedback)

    def test_searching_toward_the_crows_gaze_narrates_only_observed_results(self):
        _, created = self.request("POST", "/api/session", {"loopCount": 3})

        status, result = self.request(
            "POST",
            "/api/turn",
            {
                "sessionId": created["sessionId"],
                "action": "I search where the crow keeps looking.",
            },
        )

        self.assertEqual(status, 200)
        _, _, _, public_events, _ = self.client.narration_calls[-1]
        event_names = [event["event"] for event in public_events]
        self.assertEqual(
            event_names,
            ["fox_searches_bushes", "search_inconclusive"],
        )
        self.assertIn("nothing conclusive", result["narration"])
        self.assertNotIn("necklace", result["narration"].casefold())

    def test_unsupported_narration_is_rewritten_before_commit(self):
        self.client.audit_results = [
            NarrationAudit(
                grounded=False,
                feedback="Remove claims that are not supported by the public events.",
            ),
            NarrationAudit(grounded=True),
        ]
        _, created = self.request("POST", "/api/session", {"loopCount": 3})

        status, _ = self.request(
            "POST",
            "/api/turn",
            {"sessionId": created["sessionId"], "action": "I wait."},
        )

        self.assertEqual(status, 200)
        self.assertEqual(len(self.client.narration_calls), 2)
        self.assertEqual(len(self.client.audit_calls), 2)
        self.assertIsNone(self.client.narration_calls[0][4])
        self.assertEqual(
            self.client.narration_calls[1][4],
            "Remove claims that are not supported by the public events.",
        )

    def test_twice_rejected_narration_falls_back_to_confirmed_public_events(self):
        self.client.audit_results = [
            NarrationAudit(grounded=False, feedback="Remove unsupported claims."),
            NarrationAudit(grounded=False, feedback="Still unsupported."),
        ]
        _, created = self.request("POST", "/api/session", {"loopCount": 3})

        status, result = self.request(
            "POST",
            "/api/turn",
            {"sessionId": created["sessionId"], "action": "I wait."},
        )

        self.assertEqual(status, 200)
        self.assertEqual(result["narration"], "Time passes, and you feel hungrier.")
        self.assertEqual(len(self.client.audit_calls), 2)

    def test_failed_game_agent_does_not_commit_the_candidate_state(self):
        _, created = self.request("POST", "/api/session", {"loopCount": 3})
        session_id = created["sessionId"]
        before = self.session_store.get(session_id)
        self.client.fail_game_agent = True

        status, data = self.request(
            "POST",
            "/api/turn",
            {"sessionId": session_id, "action": "What is wrong?"},
        )

        self.assertEqual(status, 502)
        self.assertEqual(
            data["error"],
            "The story cannot answer right now. Check the server terminal and try again.",
        )
        self.assertNotIn("Narration", data["error"])
        self.assertNotIn("Agent", data["error"])
        self.assertEqual(self.session_store.get(session_id), before)

    def test_api_balance_error_is_actionable_and_does_not_commit_state(self):
        _, created = self.request("POST", "/api/session", {"loopCount": 3})
        session_id = created["sessionId"]
        before = self.session_store.get(session_id)
        self.client.game_agent_error = DeepSeekError(
            "DeepSeek returned HTTP 402: Insufficient balance",
            status_code=402,
        )

        status, data = self.request(
            "POST",
            "/api/turn",
            {"sessionId": session_id, "action": "What is wrong?"},
        )

        self.assertEqual(status, 503)
        self.assertIn("insufficient balance", data["error"])
        self.assertEqual(self.session_store.get(session_id), before)

    def test_restart_discards_the_server_session_idempotently(self):
        _, created = self.request("POST", "/api/session", {"loopCount": 3})
        session_id = created["sessionId"]

        status, data = self.request(
            "POST",
            "/api/session/reset",
            {"sessionId": session_id},
        )
        self.assertEqual(status, 200)
        self.assertEqual(data, {"status": "ok"})
        with self.assertRaisesRegex(SessionStoreError, "Unknown or expired"):
            self.session_store.get(session_id)

        status, data = self.request(
            "POST",
            "/api/session/reset",
            {"sessionId": session_id},
        )
        self.assertEqual(status, 200)
        self.assertEqual(data, {"status": "ok"})


class DeepSeekAgentGatewayTests(unittest.TestCase):
    @patch("backend.infrastructure.deepseek.urlopen")
    def test_client_sends_chat_completion_and_parses_json_narration(self, mock_urlopen):
        model_content = json.dumps(
            {
                "narration": "You wait beneath the branch.",
                "promoted": True,
                "choiceLabel": "Wait beneath the branch",
            }
        )
        mock_urlopen.return_value = FakeHTTPResponse(
            {"choices": [{"message": {"content": model_content}}]}
        )
        client = DeepSeekAgentGateway(
            api_key="test-secret",
            base_url="https://deepseek.example",
            model="deepseek-v4-flash",
        )

        outcome = client.generate_free_action("Morning", 1, "Wait quietly")

        self.assertEqual(outcome.narration, "You wait beneath the branch.")
        self.assertTrue(outcome.promoted)
        self.assertEqual(outcome.choice_label, "Wait beneath the branch")
        request = mock_urlopen.call_args.args[0]
        payload = json.loads(request.data.decode("utf-8"))
        self.assertEqual(request.full_url, "https://deepseek.example/chat/completions")
        self.assertEqual(request.get_header("Authorization"), "Bearer test-secret")
        self.assertEqual(payload["model"], "deepseek-v4-flash")
        self.assertEqual(payload["response_format"], {"type": "json_object"})
        self.assertFalse(payload["stream"])
        system_prompt = payload["messages"][0]["content"]
        self.assertIn("meaningful character or world consequence", system_prompt)
        self.assertIn("Partial successes and failures may be promoted", system_prompt)

    @patch("backend.infrastructure.deepseek.urlopen")
    def test_client_rejects_a_promoted_action_without_a_label(self, mock_urlopen):
        model_content = json.dumps(
            {"narration": "You try a new approach.", "promoted": True, "choiceLabel": None}
        )
        mock_urlopen.return_value = FakeHTTPResponse(
            {"choices": [{"message": {"content": model_content}}]}
        )
        client = DeepSeekAgentGateway(api_key="test-secret")

        with self.assertRaisesRegex(DeepSeekError, "without a choice label"):
            client.generate_free_action("Morning", 0, "Try something")

    @patch("backend.infrastructure.deepseek.time.sleep")
    @patch("backend.infrastructure.deepseek.urlopen")
    def test_client_retries_rate_limit_before_succeeding(self, mock_urlopen, mock_sleep):
        rate_limit = HTTPError(
            "https://api.deepseek.com/chat/completions",
            429,
            "Too Many Requests",
            {},
            io.BytesIO(b'{"error":{"message":"Rate limit reached"}}'),
        )
        model_content = json.dumps(
            {"narration": "You wait.", "promoted": False, "choiceLabel": None}
        )
        mock_urlopen.side_effect = [
            rate_limit,
            FakeHTTPResponse({"choices": [{"message": {"content": model_content}}]}),
        ]
        client = DeepSeekAgentGateway(api_key="test-secret", api_attempts=2)

        outcome = client.generate_free_action("Morning", 0, "Wait")

        self.assertEqual(outcome.narration, "You wait.")
        self.assertEqual(mock_urlopen.call_count, 2)
        mock_sleep.assert_called_once_with(0.5)

    @patch("backend.infrastructure.deepseek.urlopen")
    def test_client_preserves_provider_error_details(self, mock_urlopen):
        mock_urlopen.side_effect = HTTPError(
            "https://api.deepseek.com/chat/completions",
            402,
            "Payment Required",
            {},
            io.BytesIO(b'{"error":{"message":"Insufficient balance"}}'),
        )
        client = DeepSeekAgentGateway(api_key="test-secret")

        with self.assertRaisesRegex(DeepSeekError, "HTTP 402: Insufficient balance") as caught:
            client.generate_free_action("Morning", 0, "Wait")

        self.assertEqual(caught.exception.status_code, 402)
        self.assertFalse(caught.exception.retryable)

    @patch("backend.infrastructure.deepseek.urlopen")
    def test_story_agent_request_contains_only_perspective_and_public_events(
        self,
        mock_urlopen,
    ):
        mock_urlopen.return_value = FakeHTTPResponse(
            {"choices": [{"message": {"content": '{"narration":"You wait."}'}}]}
        )
        client = DeepSeekAgentGateway(api_key="test-secret")
        perspective = {
            "visibleScene": {"foxLocation": "clearing", "surroundings": []},
            "foxCondition": "hungry",
            "foxKnowledge": [],
        }

        narration = client.narrate(
            perspective,
            perspective,
            "I wait.",
            [{"event": "time_passes_hungrier", "description": "Time passes."}],
        )

        self.assertEqual(narration, "You wait.")
        request = mock_urlopen.call_args.args[0]
        payload = json.loads(request.data.decode("utf-8"))
        context = json.loads(payload["messages"][1]["content"].split("\n", 1)[1])
        self.assertEqual(
            set(context),
            {"perspectiveBefore", "playerAction", "publicEvents", "perspectiveAfter"},
        )

    @patch("backend.infrastructure.deepseek.urlopen")
    def test_grounding_agent_returns_revision_feedback(self, mock_urlopen):
        mock_urlopen.return_value = FakeHTTPResponse(
            {
                "choices": [
                    {
                        "message": {
                            "content": json.dumps(
                                {
                                    "grounded": False,
                                    "feedback": "Remove the unsupported object claim.",
                                }
                            )
                        }
                    }
                ]
            }
        )
        client = DeepSeekAgentGateway(api_key="test-secret")
        perspective = {
            "visibleScene": {"foxLocation": "clearing", "surroundings": []},
            "foxCondition": "hungry",
            "foxKnowledge": [],
        }

        audit = client.audit_narration(
            perspective,
            perspective,
            "I wait.",
            [{"event": "time_passes_hungrier", "description": "Time passes."}],
            "You wait beside an unknown object.",
        )

        self.assertFalse(audit.grounded)
        self.assertIn("unsupported", audit.feedback)

class LocalEnvironmentTests(unittest.TestCase):
    def test_env_local_loads_values_without_overriding_process_environment(self):
        with tempfile.TemporaryDirectory() as directory:
            env_path = Path(directory) / ".env.local"
            env_path.write_text(
                "DEEPSEEK_API_KEY=file-key\n"
                "DEEPSEEK_MODEL='deepseek-v4-pro'\n"
                "DEEPSEEK_BASE_URL=https://api.deepseek.com\n",
                encoding="utf-8",
            )

            with patch.dict(os.environ, {"DEEPSEEK_API_KEY": "process-key"}, clear=True):
                loaded = load_env_local(env_path)

                self.assertTrue(loaded)
                self.assertEqual(os.environ["DEEPSEEK_API_KEY"], "process-key")
                self.assertEqual(os.environ["DEEPSEEK_MODEL"], "deepseek-v4-pro")
                self.assertEqual(os.environ["DEEPSEEK_BASE_URL"], "https://api.deepseek.com")


if __name__ == "__main__":
    unittest.main()
