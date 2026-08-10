from __future__ import annotations

import argparse
import json
import sys
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

if __package__ in {None, ""}:  # Support `python backend/server.py` from the project root.
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from backend.application.turns import TurnCoordinator
from backend.game_system.fox_crow import FoxCrowRuleError, player_view
from backend.infrastructure.deepseek import (
    SCENE_CONTEXT,
    ConfigurationError,
    DeepSeekAgentGateway,
    DeepSeekError,
    load_env_local,
)
from backend.infrastructure.session_store import (
    InMemoryGameSessionStore,
    SessionNotFoundError,
    StaleSessionError,
)


MAX_ACTION_LENGTH = 500
MAX_REQUEST_BYTES = 4096


class StoryRequestHandler(SimpleHTTPRequestHandler):
    def __init__(
        self,
        *args: Any,
        directory: str,
        agent_gateway: DeepSeekAgentGateway,
        session_store: InMemoryGameSessionStore,
        **kwargs: Any,
    ) -> None:
        self.agent_gateway = agent_gateway
        self.session_store = session_store
        super().__init__(*args, directory=directory, **kwargs)

    def do_GET(self) -> None:
        path = urlsplit(self.path).path
        if path == "/health":
            self._send_json(200, {"status": "ok"})
            return
        super().do_GET()

    def do_POST(self) -> None:
        path = urlsplit(self.path).path
        if path not in {
            "/api/action",
            "/api/session",
            "/api/session/reset",
            "/api/turn",
        }:
            self._send_json(404, {"error": "Endpoint not found."})
            return

        ok, payload = self._read_json_payload()
        if not ok:
            return

        if path == "/api/action":
            self._handle_free_action(payload)
        elif path == "/api/session":
            self._handle_session(payload)
        elif path == "/api/session/reset":
            self._handle_session_reset(payload)
        else:
            self._handle_turn(payload)

    def _read_json_payload(self) -> tuple[bool, Any]:
        content_length = self.headers.get("Content-Length")
        if content_length is None:
            self._send_json(411, {"error": "Content-Length is required."})
            return False, None

        try:
            body_length = int(content_length)
        except ValueError:
            self._send_json(400, {"error": "Invalid Content-Length."})
            return False, None

        if body_length <= 0 or body_length > MAX_REQUEST_BYTES:
            self._send_json(413, {"error": "Request body is too large or empty."})
            return False, None

        try:
            payload = json.loads(self.rfile.read(body_length).decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError):
            self._send_json(400, {"error": "Request body must be valid UTF-8 JSON."})
            return False, None
        return True, payload

    def _handle_free_action(self, payload: Any) -> None:
        error = self._validate_free_action_payload(payload)
        if error is not None:
            self._send_json(400, {"error": error})
            return

        passage = payload["passage"]
        loop_count = payload["loopCount"]
        action = payload["action"].strip()

        try:
            outcome = self.agent_gateway.generate_free_action(
                passage,
                loop_count,
                action,
            )
        except ConfigurationError:
            self._send_configuration_error()
            return
        except DeepSeekError as error:
            self._send_deepseek_error(error)
            return

        self._send_json(
            200,
            {
                "narration": outcome.narration,
                "passage": passage,
                "learnedChoice": (
                    {
                        "label": outcome.choice_label,
                        "action": action,
                    }
                    if outcome.promoted
                    else None
                ),
            },
        )

    def _handle_session(self, payload: Any) -> None:
        if not isinstance(payload, dict) or not set(payload) <= {"loopCount"}:
            self._send_json(400, {"error": "Session JSON may contain only loopCount."})
            return
        loop_count = payload.get("loopCount", 3)
        if (
            isinstance(loop_count, bool)
            or not isinstance(loop_count, int)
            or loop_count < 3
        ):
            self._send_json(
                400,
                {"error": "Dynamic story sessions begin at loopCount 3 or later."},
            )
            return

        session_id, state = self.session_store.create(loop_count=loop_count)
        self._send_json(
            201,
            {"sessionId": session_id, "playerState": player_view(state)},
        )

    def _handle_turn(self, payload: Any) -> None:
        if not isinstance(payload, dict) or set(payload) != {"sessionId", "action"}:
            self._send_json(400, {"error": "Turn JSON must contain sessionId and action."})
            return
        session_id = payload["sessionId"]
        action = payload["action"]
        if not isinstance(session_id, str) or not session_id.strip():
            self._send_json(400, {"error": "sessionId must be a non-empty string."})
            return
        if not isinstance(action, str) or not action.strip():
            self._send_json(400, {"error": "Enter an action before submitting."})
            return
        if len(action) > MAX_ACTION_LENGTH:
            self._send_json(
                400,
                {"error": f"Action must be {MAX_ACTION_LENGTH} characters or fewer."},
            )
            return

        coordinator = TurnCoordinator(
            game_agent=self.agent_gateway,
            story_agent=self.agent_gateway,
            narrative_grounder=self.agent_gateway,
            session_store=self.session_store,
            log_fallback=lambda message: self.log_message("%s", message),
        )
        try:
            result = coordinator.resolve_turn(session_id, action.strip())
        except ConfigurationError:
            self._send_configuration_error()
            return
        except DeepSeekError as error:
            self._send_deepseek_error(error)
            return
        except FoxCrowRuleError:
            self._send_json(
                502,
                {
                    "error": (
                        "The story could not understand that action. "
                        "Try describing it another way."
                    )
                },
            )
            return
        except SessionNotFoundError:
            self._send_json(
                404,
                {
                    "error": (
                        "This story session has expired. "
                        "Restart the story to continue."
                    )
                },
            )
            return
        except StaleSessionError:
            self._send_json(
                409,
                {"error": "The story changed before this action finished. Try again."},
            )
            return

        self._send_json(
            200,
            {
                "sessionId": result.session_id,
                "narration": result.narration,
                "outcome": result.outcome,
                "playerState": result.player_state,
            },
        )

    def _handle_session_reset(self, payload: Any) -> None:
        if not isinstance(payload, dict) or set(payload) != {"sessionId"}:
            self._send_json(400, {"error": "Restart request is incomplete."})
            return
        session_id = payload["sessionId"]
        if not isinstance(session_id, str) or not session_id.strip():
            self._send_json(400, {"error": "Restart request is incomplete."})
            return

        self.session_store.discard(session_id)
        self._send_json(200, {"status": "ok"})

    @staticmethod
    def _validate_free_action_payload(payload: Any) -> str | None:
        if not isinstance(payload, dict):
            return "Request JSON must be an object."

        passage = payload.get("passage")
        if passage not in SCENE_CONTEXT:
            return "Unknown story passage."

        loop_count = payload.get("loopCount")
        if isinstance(loop_count, bool) or not isinstance(loop_count, int) or loop_count < 0:
            return "loopCount must be a non-negative integer."

        action = payload.get("action")
        if not isinstance(action, str) or not action.strip():
            return "Enter an action before submitting."
        if len(action) > MAX_ACTION_LENGTH:
            return f"Action must be {MAX_ACTION_LENGTH} characters or fewer."
        return None

    def _send_configuration_error(self) -> None:
        self._send_json(
            503,
            {
                "error": (
                    "The story API is not configured. Set DEEPSEEK_API_KEY "
                    "and restart the server."
                )
            },
        )

    def _send_deepseek_error(self, error: DeepSeekError) -> None:
        self.log_error("DeepSeek request failed: %s", error)
        messages = {
            401: "The story API key was rejected. Check DEEPSEEK_API_KEY and restart the server.",
            402: "The story API account has insufficient balance. Top it up and try again.",
            429: "The story service is busy. Wait a moment and try again.",
            400: "The story request was rejected by the AI service. Check the server terminal for details.",
            422: "The story request was rejected by the AI service. Check the server terminal for details.",
        }
        message = messages.get(
            error.status_code,
            "The story cannot answer right now. Check the server terminal and try again.",
        )
        status = 503 if error.retryable or error.status_code in {401, 402} else 502
        self._send_json(status, {"error": message})

    def _send_json(self, status: int, payload: dict[str, Any]) -> None:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)


def create_server(
    host: str = "127.0.0.1",
    port: int = 8000,
    dist_dir: Path | None = None,
    agent_gateway: DeepSeekAgentGateway | None = None,
    session_store: InMemoryGameSessionStore | None = None,
) -> ThreadingHTTPServer:
    project_root = Path(__file__).resolve().parents[1]
    static_dir = (dist_dir or project_root / "dist").resolve()
    if not (static_dir / "index.html").is_file():
        raise FileNotFoundError(f"Built story not found: {static_dir / 'index.html'}")

    gateway = agent_gateway or DeepSeekAgentGateway()
    sessions = session_store or InMemoryGameSessionStore()
    handler = partial(
        StoryRequestHandler,
        directory=str(static_dir),
        agent_gateway=gateway,
        session_store=sessions,
    )
    return ThreadingHTTPServer((host, port), handler)


def main() -> None:
    parser = argparse.ArgumentParser(description="Serve the Twine story and Agent APIs.")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8000)
    args = parser.parse_args()

    project_root = Path(__file__).resolve().parents[1]
    env_local_loaded = load_env_local(project_root / ".env.local")
    gateway = DeepSeekAgentGateway()
    server = create_server(
        host=args.host,
        port=args.port,
        agent_gateway=gateway,
    )
    print(f"Story server: http://{args.host}:{args.port}")
    print(f"DeepSeek model: {gateway.model}")
    if env_local_loaded:
        print("Loaded local configuration from .env.local.")
    if not gateway.configured:
        print("DeepSeek is not configured; set DEEPSEEK_API_KEY and restart the server.")

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopping story server.")
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
