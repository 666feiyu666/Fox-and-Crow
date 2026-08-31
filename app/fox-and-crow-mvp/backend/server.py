from __future__ import annotations

import argparse
import json
import os
import sys
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

if __package__ in {None, ""}:  # Support `python backend/server.py` from the project root.
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from backend.application.turns import TurnCoordinator
from backend.infrastructure.deepseek import (
    ConfigurationError,
    DeepSeekAgentGateway,
    DeepSeekError,
    load_env_local,
)
from backend.infrastructure.session_store import (
    InMemoryStorySessionStore,
    SessionNotFoundError,
    StaleSessionError,
)
from backend.story_runtime.state import player_view


MAX_ACTION_LENGTH = 500
MAX_REQUEST_BYTES = 4096
API_PATHS = {
    "/api/session",
    "/api/session/reset",
    "/api/turn",
}


class StoryRequestHandler(SimpleHTTPRequestHandler):
    def __init__(
        self,
        *args: Any,
        directory: str,
        agent_gateway: DeepSeekAgentGateway,
        session_store: InMemoryStorySessionStore,
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

    def do_OPTIONS(self) -> None:
        path = urlsplit(self.path).path
        if path not in API_PATHS:
            self._send_json(404, {"error": "Endpoint not found."})
            return

        self.send_response(204)
        self._send_cors_headers()
        self.send_header("Content-Length", "0")
        self.send_header("Cache-Control", "public, max-age=600")
        self.end_headers()

    def do_POST(self) -> None:
        path = urlsplit(self.path).path
        if path not in API_PATHS:
            self._send_json(404, {"error": "Endpoint not found."})
            return

        ok, payload = self._read_json_payload()
        if not ok:
            return

        if path == "/api/session":
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

    def _handle_session(self, payload: Any) -> None:
        if not isinstance(payload, dict) or not set(payload) <= {"loopCount"}:
            self._send_json(400, {"error": "Session JSON may contain only loopCount."})
            return
        loop_count = payload.get("loopCount", 1)
        if (
            isinstance(loop_count, bool)
            or not isinstance(loop_count, int)
            or loop_count < 1
        ):
            self._send_json(
                400,
                {"error": "loopCount must be a positive integer."},
            )
            return

        session_id, state = self.session_store.create(loop_count=loop_count)
        self._send_json(
            201,
            {"sessionId": session_id, "playerState": player_view(state)},
        )

    def _handle_turn(self, payload: Any) -> None:
        if not isinstance(payload, dict) or set(payload) != {
            "sessionId",
            "inputType",
            "content",
        }:
            self._send_json(
                400,
                {"error": "Turn JSON must contain sessionId, inputType, and content."},
            )
            return
        session_id = payload["sessionId"]
        input_type = payload["inputType"]
        content = payload["content"]
        if not isinstance(session_id, str) or not session_id.strip():
            self._send_json(400, {"error": "sessionId must be a non-empty string."})
            return
        if not isinstance(input_type, str) or input_type not in {"say", "do"}:
            self._send_json(400, {"error": "inputType must be either say or do."})
            return
        if not isinstance(content, str) or not content.strip():
            self._send_json(400, {"error": "Enter one line to say or one action to do."})
            return
        if len(content) > MAX_ACTION_LENGTH:
            self._send_json(
                400,
                {"error": f"Input must be {MAX_ACTION_LENGTH} characters or fewer."},
            )
            return

        coordinator = TurnCoordinator(
            story_agent=self.agent_gateway,
            session_store=self.session_store,
        )
        try:
            result = coordinator.resolve_turn(
                session_id,
                input_type,
                content.strip(),
            )
        except ConfigurationError:
            self._send_configuration_error()
            return
        except DeepSeekError as error:
            self._send_deepseek_error(error)
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
                "storyEntry": {
                    "inputType": result.input_type,
                    "playerInput": result.player_input,
                    "narration": result.narration,
                },
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

    def _send_configuration_error(self) -> None:
        self._send_json(
            503,
            {
                "error": (
                    "The story service is not configured yet. Please try again later."
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
        self._send_cors_headers()
        self.end_headers()
        self.wfile.write(body)

    def _send_cors_headers(self) -> None:
        """Allow the browser-hosted itch.io build to call this test API."""
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")


def create_server(
    host: str = "127.0.0.1",
    port: int = 8000,
    dist_dir: Path | None = None,
    agent_gateway: DeepSeekAgentGateway | None = None,
    session_store: InMemoryStorySessionStore | None = None,
) -> ThreadingHTTPServer:
    project_root = Path(__file__).resolve().parents[1]
    static_dir = (dist_dir or project_root / "dist").resolve()
    if not (static_dir / "index.html").is_file():
        raise FileNotFoundError(f"Built story not found: {static_dir / 'index.html'}")

    gateway = agent_gateway or DeepSeekAgentGateway()
    sessions = session_store or InMemoryStorySessionStore()
    handler = partial(
        StoryRequestHandler,
        directory=str(static_dir),
        agent_gateway=gateway,
        session_store=sessions,
    )
    return ThreadingHTTPServer((host, port), handler)


def main() -> None:
    parser = argparse.ArgumentParser(description="Serve the Twine story and Agent APIs.")
    default_host = "0.0.0.0" if os.getenv("RENDER") else "127.0.0.1"
    parser.add_argument("--host", default=default_host)
    parser.add_argument("--port", type=int, default=os.getenv("PORT", "8000"))
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
