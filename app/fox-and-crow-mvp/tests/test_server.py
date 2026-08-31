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

from backend.infrastructure.deepseek import (
    ConfigurationError,
    DeepSeekAgentGateway,
    DeepSeekError,
    load_env_local,
)
from backend.infrastructure.session_store import (
    InMemoryStorySessionStore,
    SessionNotFoundError,
)
from backend.server import create_server


class FakeHTTPResponse:
    def __init__(self, payload):
        self.payload = payload

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        return False

    def read(self):
        return json.dumps(self.payload).encode("utf-8")


class StubStoryAgent:
    def __init__(self, configured=True):
        self.configured = configured
        self.model = "test-model"
        self.calls = []
        self.error = None

    def narrate(self, context):
        if not self.configured:
            raise ConfigurationError("Story model is not configured.")
        if self.error is not None:
            raise self.error
        self.calls.append(context)
        input_data = context["input"]
        if input_data["type"] == "say":
            return f'I say, "{input_data["text"]}" The crow tilts her head.'
        return f'I try to {input_data["text"]}. Leaves stir around me.'


class StoryServerTests(unittest.TestCase):
    def setUp(self):
        self.client = StubStoryAgent()
        self.session_store = InMemoryStorySessionStore()
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
        raw_body = response.read()
        data = json.loads(raw_body.decode("utf-8")) if raw_body else None
        connection.close()
        return response.status, data, response

    def create_session(self, loop_count=1):
        status, data, _ = self.request(
            "POST",
            "/api/session",
            {"loopCount": loop_count},
        )
        self.assertEqual(status, 201)
        return data

    def test_health_does_not_expose_backend_configuration(self):
        status, data, _ = self.request("GET", "/health")
        self.assertEqual(status, 200)
        self.assertEqual(data, {"status": "ok"})

    def test_api_supports_browser_cors_preflight(self):
        connection = http.client.HTTPConnection("127.0.0.1", self.port, timeout=3)
        connection.request(
            "OPTIONS",
            "/api/turn",
            headers={
                "Origin": "https://html-classic.itch.zone",
                "Access-Control-Request-Method": "POST",
                "Access-Control-Request-Headers": "content-type",
            },
        )
        response = connection.getresponse()
        body = response.read()
        connection.close()
        self.assertEqual(response.status, 204)
        self.assertEqual(body, b"")
        self.assertEqual(response.getheader("Access-Control-Allow-Origin"), "*")

    def test_session_exposes_only_time_and_loop_state(self):
        created = self.create_session(loop_count=2)
        self.assertEqual(set(created), {"sessionId", "playerState"})
        self.assertEqual(
            created["playerState"],
            {
                "loopCount": 2,
                "elapsedUnits": 0,
                "remainingUnits": 6,
                "totalUnits": 6,
                "timePhase": "morning",
            },
        )
        serialized = json.dumps(created).casefold()
        for forbidden in ("hunger", "trust", "inventory", "relationship"):
            self.assertNotIn(forbidden, serialized)

    def test_session_rejects_non_positive_loop_count(self):
        status, data, _ = self.request(
            "POST",
            "/api/session",
            {"loopCount": 0},
        )
        self.assertEqual(status, 400)
        self.assertIn("positive integer", data["error"])

    def test_turn_rejects_unknown_input_type_without_model_call(self):
        created = self.create_session()
        for invalid_type in ("ask", []):
            with self.subTest(input_type=invalid_type):
                status, data, _ = self.request(
                    "POST",
                    "/api/turn",
                    {
                        "sessionId": created["sessionId"],
                        "inputType": invalid_type,
                        "content": "What is wrong?",
                    },
                )
                self.assertEqual(status, 400)
                self.assertIn("say or do", data["error"])
        self.assertEqual(self.client.calls, [])

    def test_turn_rejects_empty_content_without_model_call(self):
        created = self.create_session()
        status, data, _ = self.request(
            "POST",
            "/api/turn",
            {
                "sessionId": created["sessionId"],
                "inputType": "say",
                "content": "   ",
            },
        )
        self.assertEqual(status, 400)
        self.assertIn("one line", data["error"])
        self.assertEqual(self.client.calls, [])

    def test_say_turn_preserves_original_words_and_advances_one_unit(self):
        created = self.create_session()
        content = "Tell me why you keep looking at the bushes."
        status, data, _ = self.request(
            "POST",
            "/api/turn",
            {
                "sessionId": created["sessionId"],
                "inputType": "say",
                "content": content,
            },
        )
        self.assertEqual(status, 200)
        self.assertEqual(
            data["storyEntry"]["playerInput"],
            content,
        )
        self.assertEqual(data["storyEntry"]["inputType"], "say")
        self.assertEqual(data["playerState"]["elapsedUnits"], 1)
        self.assertEqual(data["playerState"]["remainingUnits"], 5)
        self.assertEqual(len(self.client.calls), 1)
        self.assertEqual(self.client.calls[0]["input"], {"type": "say", "text": content})

    def test_do_turn_is_sent_as_one_declared_action(self):
        created = self.create_session()
        status, data, _ = self.request(
            "POST",
            "/api/turn",
            {
                "sessionId": created["sessionId"],
                "inputType": "do",
                "content": "search beneath the thorn bush",
            },
        )
        self.assertEqual(status, 200)
        self.assertEqual(data["storyEntry"]["inputType"], "do")
        self.assertEqual(len(self.client.calls), 1)

    def test_six_successful_turns_advance_to_the_next_loop(self):
        created = self.create_session(loop_count=4)
        for index in range(6):
            status, data, _ = self.request(
                "POST",
                "/api/turn",
                {
                    "sessionId": created["sessionId"],
                    "inputType": "do",
                    "content": f"wait and observe {index}",
                },
            )
            self.assertEqual(status, 200)
        self.assertEqual(data["outcome"], "loop_advanced")
        self.assertEqual(data["playerState"]["loopCount"], 5)
        self.assertEqual(data["playerState"]["elapsedUnits"], 0)
        self.assertEqual(data["playerState"]["remainingUnits"], 6)
        self.assertEqual(len(self.client.calls), 6)

    def test_model_failure_preserves_time_and_input_can_be_retried(self):
        created = self.create_session()
        session_id = created["sessionId"]
        before = self.session_store.get(session_id)
        self.client.error = DeepSeekError("Temporary failure.", retryable=True)
        payload = {
            "sessionId": session_id,
            "inputType": "do",
            "content": "step closer to the tree",
        }
        status, _, _ = self.request("POST", "/api/turn", payload)
        self.assertEqual(status, 503)
        self.assertEqual(self.session_store.get(session_id), before)

        self.client.error = None
        status, data, _ = self.request("POST", "/api/turn", payload)
        self.assertEqual(status, 200)
        self.assertEqual(data["storyEntry"]["playerInput"], payload["content"])

    def test_missing_configuration_uses_collaborator_facing_error(self):
        created = self.create_session()
        self.client.configured = False
        status, data, _ = self.request(
            "POST",
            "/api/turn",
            {
                "sessionId": created["sessionId"],
                "inputType": "say",
                "content": "Hello.",
            },
        )
        self.assertEqual(status, 503)
        self.assertNotIn("DeepSeek", data["error"])
        self.assertNotIn("API key", data["error"])

    def test_restart_discards_the_server_session_idempotently(self):
        created = self.create_session()
        session_id = created["sessionId"]
        for _ in range(2):
            status, data, _ = self.request(
                "POST",
                "/api/session/reset",
                {"sessionId": session_id},
            )
            self.assertEqual(status, 200)
            self.assertEqual(data, {"status": "ok"})
        with self.assertRaises(SessionNotFoundError):
            self.session_store.get(session_id)


class DeepSeekAgentGatewayTests(unittest.TestCase):
    @patch("backend.infrastructure.deepseek.urlopen")
    def test_story_agent_sends_story_first_context_and_parses_narration(
        self,
        mock_urlopen,
    ):
        mock_urlopen.return_value = FakeHTTPResponse(
            {"choices": [{"message": {"content": '{"narration":"I wait."}'}}]}
        )
        client = DeepSeekAgentGateway(
            api_key="test-secret",
            base_url="https://deepseek.example",
            model="deepseek-v4-flash",
        )
        context = {
            "storyConfig": {"pointOfView": "first-person limited"},
            "playerCharacter": {"role": "the fox"},
            "time": {"loopCount": 1, "remainingUnits": 6},
            "recentVisibleTurns": [],
            "input": {"type": "say", "text": "Wait."},
        }
        narration = client.narrate(context)
        self.assertEqual(narration, "I wait.")

        request = mock_urlopen.call_args.args[0]
        payload = json.loads(request.data.decode("utf-8"))
        self.assertEqual(request.full_url, "https://deepseek.example/chat/completions")
        self.assertEqual(request.get_header("Authorization"), "Bearer test-secret")
        self.assertEqual(payload["model"], "deepseek-v4-flash")
        self.assertEqual(payload["response_format"], {"type": "json_object"})
        self.assertEqual(
            json.loads(payload["messages"][1]["content"].split("\n", 1)[1]),
            context,
        )
        prompt = payload["messages"][0]["content"]
        self.assertIn("first-person limited", prompt)
        self.assertIn("input.type is say", prompt)
        self.assertIn("input.type is do", prompt)
        self.assertIn("Never decide victory", prompt)

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
        mock_urlopen.side_effect = [
            rate_limit,
            FakeHTTPResponse(
                {"choices": [{"message": {"content": '{"narration":"I wait."}'}}]}
            ),
        ]
        client = DeepSeekAgentGateway(api_key="test-secret", api_attempts=2)
        narration = client.narrate({"input": {"type": "do", "text": "wait"}})
        self.assertEqual(narration, "I wait.")
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
        with self.assertRaisesRegex(DeepSeekError, "HTTP 402: Insufficient balance"):
            client.narrate({"input": {"type": "do", "text": "wait"}})


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
