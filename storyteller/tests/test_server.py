import http.client
import json
import tempfile
import threading
import unittest
from pathlib import Path

from backend.case import Case
from backend.model import ConfigurationError, ModelError
from backend.server import SessionRegistry, create_server
from backend.storyteller import Storyteller
from backend.understanding import UnderstandingCache
from tests.fixtures import OPENING, review_payload, ruling_payload, understand_reply, understanding_payload

CASE_ROOT = Path(__file__).resolve().parents[2] / "cases"
FOX = Case.load(CASE_ROOT / "fox-and-crow")
CINDERELLA = Case.load(CASE_ROOT / "cinderella")

UNDERSTANDING = understanding_payload()


class StubModel:
    """Stands in for the two model calls so the API can be tested offline."""

    configured = True

    def __init__(self, fail=None, restart=False, ending=False):
        self.fail = fail
        self.restart = restart
        self.ending = ending
        self.turns = 0

    def complete_json(self, system, user, **kwargs):
        if "case object only" in system:
            return understand_reply(system, user)
        if user.startswith("Opening input:"):
            return OPENING
        if user.startswith("Review input:"):
            return review_payload()
        if self.fail is not None:
            raise self.fail
        if "judge for this turn" in system:
            self.turns += 1
            return ruling_payload(restart=self.restart, ending=self.ending)
        return {"narration": "You move, and the world answers.", "hints": ["Wait.", "Look up."]}


class ServerTestBase(unittest.TestCase):
    case = FOX

    def make_model(self):
        return StubModel()

    def setUp(self):
        self.tempdir = tempfile.TemporaryDirectory()
        self.addCleanup(self.tempdir.cleanup)
        self.model = self.make_model()
        self.storyteller = Storyteller(self.case, model=self.model)
        self.storyteller.cache = UnderstandingCache(Path(self.tempdir.name))
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
            "POST", "/api/turn", {"sessionId": session_id, "type": input_type, "text": text}
        )


class BasicServerTests(ServerTestBase):
    def test_health_reports_the_case(self):
        status, payload = self.request("GET", "/health")
        self.assertEqual((status, payload["status"]), (200, "ok"))
        self.assertEqual(payload["case"], FOX.id)

    def test_serves_the_playable_page(self):
        for path in ("/", "/app.js", "/style.css"):
            status, body = self.request("GET", path)
            self.assertEqual(status, 200, path)
            self.assertIsInstance(body, str)

    def test_session_returns_the_story_the_role_and_the_opening(self):
        payload = self.new_session("zh")
        self.assertEqual(payload["opening"], UNDERSTANDING["opening"])
        self.assertEqual(payload["case"]["id"], FOX.id)
        self.assertEqual(payload["case"]["title"]["zh"], "狐狸与乌鸦")
        self.assertEqual(payload["case"]["player"], UNDERSTANDING["player"])
        self.assertEqual(
            payload["playerState"],
            {"language": "zh", "loop": 1, "turn": 0, "ended": False},
        )

    def test_session_rejects_an_unknown_language(self):
        status, _ = self.request("POST", "/api/session", {"language": "fr"})
        self.assertEqual(status, 400)

    def test_the_session_says_whether_the_understander_just_ran(self):
        self.assertEqual(self.new_session("en")["understandingSource"], "derived")
        self.assertEqual(self.new_session("en")["understandingSource"], "cached")

    def test_turn_returns_the_next_passage(self):
        session = self.new_session()
        status, payload = self.take_turn(session["sessionId"], "nose the thorns")
        self.assertEqual(status, 200)
        self.assertEqual(payload["narration"], "You move, and the world answers.")
        self.assertEqual(payload["hints"], ["Wait.", "Look up."])
        self.assertEqual(payload["outcome"], "partial")
        self.assertEqual(
            payload["playerState"],
            {"language": "en", "loop": 1, "turn": 1, "ended": False},
        )
        self.assertNotIn("events", payload)

    def test_turn_validates_its_payload(self):
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

    def test_an_unknown_session_is_not_found(self):
        status, payload = self.take_turn("missing")
        self.assertEqual(status, 404)
        self.assertIn("expired", payload["error"])

    def test_reset_discards_the_session(self):
        session_id = self.new_session()["sessionId"]
        status, _ = self.request("POST", "/api/session/reset", {"sessionId": session_id})
        self.assertEqual(status, 200)
        status, _ = self.take_turn(session_id)
        self.assertEqual(status, 404)

    def test_the_story_keeps_going_for_many_turns(self):
        session_id = self.new_session()["sessionId"]
        for expected in range(1, 13):
            status, payload = self.take_turn(session_id)
            self.assertEqual(status, 200)
            self.assertEqual(payload["playerState"]["turn"], expected)


class CinderellaServerTests(ServerTestBase):
    case = CINDERELLA

    def test_second_case_serves_its_own_story(self):
        session = self.new_session("zh")
        self.assertEqual(session["case"]["title"]["zh"], "灰姑娘")
        self.assertEqual(session["case"]["id"], "cinderella")


class LoopServerTests(ServerTestBase):
    def make_model(self):
        return StubModel(restart=True)

    def test_a_returned_morning_is_reported(self):
        session_id = self.new_session()["sessionId"]
        status, payload = self.take_turn(session_id)
        self.assertEqual(status, 200)
        self.assertTrue(payload["restart"])
        self.assertFalse(payload["ending"])
        self.assertEqual(payload["playerState"]["loop"], 2)
        self.assertEqual(payload["playerState"]["turn"], 0)


class EndedStoryServerTests(ServerTestBase):
    def make_model(self):
        return StubModel(ending=True)

    def test_a_broken_loop_closes_the_story(self):
        session_id = self.new_session()["sessionId"]
        status, payload = self.take_turn(session_id)
        self.assertEqual(status, 200)
        self.assertTrue(payload["ending"])
        self.assertTrue(payload["playerState"]["ended"])
        status, payload = self.take_turn(session_id)
        self.assertEqual(status, 409)
        self.assertIn("ended", payload["error"])


class ModelFailureTests(ServerTestBase):
    def make_model(self):
        return StubModel(fail=ConfigurationError("no key"))

    def test_an_unconfigured_model_is_a_503(self):
        status, _ = self.take_turn(self.new_session()["sessionId"])
        self.assertEqual(status, 503)


class UncommittedTurnTests(ServerTestBase):
    def test_rejected_content_leaves_state_unchanged_and_can_retry(self):
        session_id = self.new_session()["sessionId"]
        _, before = self.sessions.claim(session_id)
        self.sessions.release(session_id)
        original = self.model.complete_json

        def rejecting_review(system, user, **kwargs):
            if user.startswith("Review input:"):
                return review_payload("writer")
            return original(system, user, **kwargs)

        self.model.complete_json = rejecting_review
        status, _ = self.take_turn(session_id)
        self.assertEqual(status, 502)
        _, after = self.sessions.claim(session_id)
        self.sessions.release(session_id)
        self.assertEqual(before, after)
        self.assertFalse(after.turns)
        self.model.complete_json = original
        status, payload = self.take_turn(session_id)
        self.assertEqual((status, payload["playerState"]["turn"]), (200, 1))
        self.assertNotIn("review", str(payload).lower())

    def test_failed_writer_leaves_state_and_audit_untouched_and_can_retry(self):
        session_id = self.new_session()["sessionId"]
        _, before = self.sessions.claim(session_id)
        self.sessions.release(session_id)
        original = self.model.complete_json

        def invalid_writer(system, user, **kwargs):
            if user.startswith("Turn input with the final ruling:"):
                return {"narration": ""}
            return original(system, user, **kwargs)

        self.model.complete_json = invalid_writer
        status, _ = self.take_turn(session_id)
        self.assertEqual(status, 502)
        _, after = self.sessions.claim(session_id)
        self.sessions.release(session_id)
        self.assertEqual(before, after)
        self.assertFalse(after.turns)
        self.model.complete_json = original
        status, payload = self.take_turn(session_id)
        self.assertEqual((status, payload["playerState"]["turn"]), (200, 1))

    def test_session_initialises_hidden_world_without_exposing_it(self):
        session = self.new_session()
        self.assertNotIn("hidden-password", str(session))
        _, state = self.sessions.claim(session["sessionId"])
        self.sessions.release(session["sessionId"])
        self.assertIn("hidden-password", str(state.facts))


class ModelRejectionTests(ServerTestBase):
    def make_model(self):
        return StubModel(fail=ModelError("bad", status_code=401))

    def test_a_rejected_key_is_a_503_with_guidance(self):
        status, payload = self.take_turn(self.new_session()["sessionId"])
        self.assertEqual(status, 503)
        self.assertIn("DEEPSEEK_API_KEY", payload["error"])


if __name__ == "__main__":
    unittest.main()
