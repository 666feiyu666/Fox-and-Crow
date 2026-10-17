import http.client
import json
import threading
import unittest

from backend.model import ConfigurationError, ModelError
from backend.server import SessionRegistry, create_server
from backend.session import Narration, Ruling

class StubStoryteller:
    """Stands in for the two model calls so the API can be tested offline."""

    configured = True

    def __init__(self, time_cost=1, ending="none", fail=None):
        self.time_cost = time_cost
        self.ending = ending
        self.fail = fail
        self.turns = 0

    def opening(self, language):
        return {
            "title": "The Fox and the Crow",
            "text": "Cold moss." if language == "en" else "湿冷的苔藓。",
        }

    def resolve(self, state, input_type, text):
        if self.fail is not None:
            raise self.fail
        self.turns += 1
        ruling = Ruling.from_dict(
            {
                "outcome": "partial",
                "time_cost": self.time_cost,
                "trust": 1,
                "insight": 1,
                "facts": [f"Turn {self.turns} happened."],
                "scene": "Private plan.",
                "ending": self.ending,
            }
        )
        narration = Narration.from_dict(
            {"narration": f"You {text}.", "hints": ["Wait.", "Look up."]}
        )
        return ruling, narration


class StoryServerTests(unittest.TestCase):
    storyteller_factory = StubStoryteller

    def setUp(self):
        self.storyteller = self.storyteller_factory()
        self.sessions = SessionRegistry()
        self.server = create_server(
            port=0,
            storyteller=self.storyteller,
            sessions=self.sessions,
        )
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.port = self.server.server_address[1]

    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=2)

    def request(self, method, path, payload=None):
        connection = http.client.HTTPConnection("127.0.0.1", self.port, timeout=5)
        body = None if payload is None else json.dumps(payload)
        headers = {} if body is None else {"Content-Type": "application/json"}
        connection.request(method, path, body=body, headers=headers)
        response = connection.getresponse()
        raw = response.read().decode("utf-8")
        connection.close()
        try:
            return response.status, json.loads(raw)
        except json.JSONDecodeError:
            return response.status, raw

    def new_session(self, language="en"):
        status, payload = self.request("POST", "/api/session", {"language": language})
        self.assertEqual(status, 201)
        return payload

    def take_turn(self, session_id, text="look around", input_type="do"):
        return self.request(
            "POST",
            "/api/turn",
            {"sessionId": session_id, "type": input_type, "text": text},
        )


class BasicServerTests(StoryServerTests):
    def test_health(self):
        status, payload = self.request("GET", "/health")
        self.assertEqual((status, payload), (200, {"status": "ok"}))

    def test_serves_the_playable_page(self):
        for path in ("/", "/app.js", "/style.css"):
            status, body = self.request("GET", path)
            self.assertEqual(status, 200, path)
            self.assertIsInstance(body, str)

    def test_session_returns_opening_in_requested_language(self):
        payload = self.new_session("zh")
        self.assertEqual(payload["opening"]["text"], "湿冷的苔藓。")
        self.assertEqual(payload["playerState"]["language"], "zh")
        self.assertEqual(payload["playerState"]["remainingUnits"], 6)
        self.assertFalse(payload["playerState"]["ended"])

    def test_session_rejects_unknown_language(self):
        status, _ = self.request("POST", "/api/session", {"language": "fr"})
        self.assertEqual(status, 400)

    def test_turn_returns_narration_hints_and_state(self):
        session = self.new_session()
        status, payload = self.take_turn(session["sessionId"], "nose the thorns")
        self.assertEqual(status, 200)
        self.assertEqual(payload["narration"], "You nose the thorns.")
        self.assertEqual(payload["hints"], ["Wait.", "Look up."])
        self.assertEqual(payload["outcome"], "partial")
        self.assertEqual(payload["playerState"]["elapsedUnits"], 1)
        self.assertEqual(payload["events"], [])

    def test_turn_validates_payload(self):
        session_id = self.new_session()["sessionId"]
        cases = [
            {"sessionId": session_id, "type": "shout", "text": "hey"},
            {"sessionId": session_id, "type": "do", "text": "   "},
            {"sessionId": session_id, "type": "do", "text": "x" * 401},
            {"sessionId": session_id, "type": "do"},
        ]
        for payload in cases:
            status, _ = self.request("POST", "/api/turn", payload)
            self.assertEqual(status, 400, payload)

    def test_unknown_session_is_not_found(self):
        status, payload = self.take_turn("missing")
        self.assertEqual(status, 404)
        self.assertIn("expired", payload["error"])

    def test_reset_discards_the_session(self):
        session_id = self.new_session()["sessionId"]
        status, _ = self.request("POST", "/api/session/reset", {"sessionId": session_id})
        self.assertEqual(status, 200)
        status, _ = self.take_turn(session_id)
        self.assertEqual(status, 404)


class TurnProgressionTests(StoryServerTests):
    storyteller_factory = staticmethod(lambda: StubStoryteller(time_cost=3))

    def test_day_closes_once_six_units_are_spent(self):
        session_id = self.new_session()["sessionId"]
        status, first = self.take_turn(session_id)
        self.assertEqual((status, first["events"]), (200, []))
        self.assertEqual(first["playerState"]["elapsedUnits"], 3)
        status, second = self.take_turn(session_id)
        self.assertEqual(second["events"], ["day_reset"])
        self.assertEqual(second["playerState"]["loop"], 2)
        self.assertEqual(second["playerState"]["elapsedUnits"], 0)
        self.assertEqual(second["playerState"]["phase"], "morning")


class EndedStoryTests(StoryServerTests):
    def test_ended_story_refuses_further_turns(self):
        session_id = self.new_session()["sessionId"]
        state = self.sessions.claim(session_id)
        self.sessions.release(session_id)
        self.storyteller.ending = "loop_broken"
        for _ in range(12):
            status, payload = self.take_turn(session_id, "there is something I must say", "say")
            if payload["playerState"]["ended"]:
                break
        self.assertTrue(payload["playerState"]["ended"])
        status, payload = self.take_turn(session_id)
        self.assertEqual(status, 409)
        self.assertIn("ended", payload["error"])


class ModelFailureTests(StoryServerTests):
    storyteller_factory = staticmethod(lambda: StubStoryteller(fail=ConfigurationError("no key")))

    def test_unconfigured_model_is_a_503(self):
        session_id = self.new_session()["sessionId"]
        status, _ = self.take_turn(session_id)
        self.assertEqual(status, 503)


class ModelErrorTests(StoryServerTests):
    storyteller_factory = staticmethod(lambda: StubStoryteller(fail=ModelError("bad", status_code=401)))

    def test_rejected_key_is_a_503_with_guidance(self):
        session_id = self.new_session()["sessionId"]
        status, payload = self.take_turn(session_id)
        self.assertEqual(status, 503)
        self.assertIn("DEEPSEEK_API_KEY", payload["error"])


if __name__ == "__main__":
    unittest.main()
