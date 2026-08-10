import http.client
import json
import os
import tempfile
import threading
import unittest
from pathlib import Path
from unittest.mock import patch

from backend.server import (
    ActionOutcome,
    ConfigurationError,
    DeepSeekClient,
    DeepSeekError,
    create_server,
    load_env_local,
)


class FakeHTTPResponse:
    def __init__(self, payload):
        self.payload = payload

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        return False

    def read(self):
        return json.dumps(self.payload).encode("utf-8")


class StubDeepSeekClient:
    def __init__(self, configured=True):
        self.configured = configured
        self.model = "test-model"
        self.calls = []

    def generate_action(self, passage, loop_count, action):
        if not self.configured:
            raise ConfigurationError(
                "DeepSeek is not configured. Set DEEPSEEK_API_KEY before starting the server."
            )
        self.calls.append((passage, loop_count, action))
        return ActionOutcome(
            narration="You circle the tree, and the crow watches you with new suspicion.",
            promoted=action == "Offer the crow a trade",
            choice_label="Offer a trade" if action == "Offer the crow a trade" else None,
        )


class StoryServerTests(unittest.TestCase):
    def setUp(self):
        self.client = StubDeepSeekClient()
        self.server = create_server(port=0, client=self.client)
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

    def test_health_reports_configuration_without_exposing_key(self):
        status, data = self.request("GET", "/health")

        self.assertEqual(status, 200)
        self.assertEqual(data["status"], "ok")
        self.assertTrue(data["deepseekConfigured"])
        self.assertEqual(data["model"], "test-model")
        self.assertNotIn("apiKey", data)

    def test_action_returns_narration_and_passes_story_state(self):
        status, data = self.request(
            "POST",
            "/api/action",
            {"passage": "Morning", "loopCount": 2, "action": "Climb the tree"},
        )

        self.assertEqual(status, 200)
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
        self.assertIn("DEEPSEEK_API_KEY", data["error"])


class DeepSeekClientTests(unittest.TestCase):
    @patch("backend.server.urlopen")
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
        client = DeepSeekClient(
            api_key="test-secret",
            base_url="https://deepseek.example",
            model="deepseek-v4-flash",
        )

        outcome = client.generate_action("Morning", 1, "Wait quietly")

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

    @patch("backend.server.urlopen")
    def test_client_rejects_a_promoted_action_without_a_label(self, mock_urlopen):
        model_content = json.dumps(
            {"narration": "You try a new approach.", "promoted": True, "choiceLabel": None}
        )
        mock_urlopen.return_value = FakeHTTPResponse(
            {"choices": [{"message": {"content": model_content}}]}
        )
        client = DeepSeekClient(api_key="test-secret")

        with self.assertRaisesRegex(DeepSeekError, "without a choice label"):
            client.generate_action("Morning", 0, "Try something")


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
