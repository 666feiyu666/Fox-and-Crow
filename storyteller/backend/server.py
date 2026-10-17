"""HTTP entry point: the case shelf, one Storyteller per case, plus the pages."""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import threading
import uuid
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

if __package__ in {None, ""}:  # Allow `python backend/server.py` from the project root.
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from backend.case import LANGUAGES, Case, CaseError
from backend.model import ConfigurationError, ChatModel, ModelError, load_env_local
from backend.session import RulingError, StoryState, apply_turn, initial_state
from backend.storyteller import Storyteller
from backend.understanding import Understanding

MAX_INPUT_LENGTH = 400
MAX_REQUEST_BYTES = 8192
API_PATHS = ("/api/session", "/api/session/reset", "/api/turn")
REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
CASE_ROOT = REPOSITORY_ROOT / "cases"
SENTENCE_END = re.compile(r"[。！？]|[.!?](?=\s|$)")
EXCERPT_LIMIT = 180


def first_sentence(text: str) -> str:
    """The line a shelf shows: the tale's own opening words, not a summary."""
    flat = " ".join(text.split())
    match = SENTENCE_END.search(flat)
    excerpt = flat[: match.end()] if match else flat
    if len(excerpt) > EXCERPT_LIMIT:
        excerpt = excerpt[: EXCERPT_LIMIT - 1].rstrip() + "…"
    return excerpt


class SessionNotFound(LookupError):
    pass


class SessionBusy(RuntimeError):
    pass


class SessionRegistry:
    """Process-local sessions, one in-flight turn per session, each bound to a case."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._states: dict[str, tuple[str, StoryState]] = {}
        self._busy: set[str] = set()

    def create(
        self,
        case_id: str,
        language: str,
        understanding: Understanding | None = None,
    ) -> tuple[str, StoryState]:
        session_id = uuid.uuid4().hex
        state = initial_state(language, understanding)
        with self._lock:
            self._states[session_id] = (case_id, state)
        return session_id, state

    def claim(self, session_id: str) -> tuple[str, StoryState]:
        with self._lock:
            if session_id not in self._states:
                raise SessionNotFound(session_id)
            if session_id in self._busy:
                raise SessionBusy(session_id)
            self._busy.add(session_id)
            return self._states[session_id]

    def release(self, session_id: str, state: StoryState | None = None) -> None:
        with self._lock:
            self._busy.discard(session_id)
            if state is not None and session_id in self._states:
                case_id, _ = self._states[session_id]
                self._states[session_id] = (case_id, state)

    def discard(self, session_id: str) -> None:
        with self._lock:
            self._states.pop(session_id, None)
            self._busy.discard(session_id)


class CaseLibrary:
    """Every case on the shelf, each with one Storyteller reused across sessions."""

    def __init__(
        self,
        case_root: Path | None = None,
        model: ChatModel | None = None,
        only: str | None = None,
    ) -> None:
        self.case_root = Path(case_root or CASE_ROOT)
        self.model = model
        self.only = only
        self._lock = threading.Lock()
        self._cases: dict[str, Case] | None = None
        self._storytellers: dict[str, Storyteller] = {}

    @classmethod
    def of(cls, storyteller: Storyteller) -> "CaseLibrary":
        """A shelf holding one already-built Storyteller, as the tests use."""
        library = cls(case_root=storyteller.case.directory.parent, only=storyteller.case.id)
        library._cases = {storyteller.case.id: storyteller.case}
        library._storytellers[storyteller.case.id] = storyteller
        return library

    def _load(self) -> dict[str, Case]:
        if self._cases is None:
            loaded: dict[str, Case] = {}
            for directory in sorted(self.case_root.iterdir()):
                if not directory.is_dir() or directory.name.startswith((".", "_")):
                    continue
                try:
                    case = Case.load(directory)
                except CaseError:
                    continue
                if self.only is None or case.id == self.only:
                    loaded[case.id] = case
            self._cases = loaded
        return self._cases

    def entries(self) -> list[Case]:
        with self._lock:
            return list(self._load().values())

    def default_case(self) -> Case:
        cases = self.entries()
        if not cases:
            raise CaseError(f"No playable cases in {self.case_root}.")
        return cases[0]

    def storyteller(self, case_id: str | None = None) -> Storyteller:
        case = self.default_case() if case_id is None else self._find(case_id)
        with self._lock:
            if case.id not in self._storytellers:
                self._storytellers[case.id] = Storyteller(case, model=self.model)
            return self._storytellers[case.id]

    def _find(self, case_id: str) -> Case:
        case = self._load().get(case_id)
        if case is None:
            available = ", ".join(sorted(self._load())) or "none"
            raise CaseError(f"Unknown case: {case_id}. Available cases: {available}.")
        return case


def resolve_case(name_or_path: str) -> Case:
    """Load a case by directory name under cases/, or by an explicit path."""
    candidate = Path(name_or_path)
    if not candidate.is_dir():
        candidate = CASE_ROOT / name_or_path
    if not candidate.is_dir():
        available = ", ".join(sorted(path.name for path in CASE_ROOT.iterdir() if path.is_dir()))
        raise CaseError(f"Unknown case: {name_or_path}. Available cases: {available}.")
    return Case.load(candidate)


class StoryRequestHandler(SimpleHTTPRequestHandler):
    def __init__(
        self,
        *args: Any,
        directory: str,
        library: CaseLibrary,
        sessions: SessionRegistry,
        **kwargs: Any,
    ) -> None:
        self.library = library
        self.sessions = sessions
        super().__init__(*args, directory=directory, **kwargs)

    def do_GET(self) -> None:  # noqa: N802 - stdlib naming
        path = urlsplit(self.path).path
        if path == "/health":
            try:
                case = self.library.default_case()
            except CaseError as error:
                self._send_json(503, {"status": "empty", "error": str(error)})
                return
            self._send_json(200, {"status": "ok", "case": case.id})
            return
        if path == "/api/cases":
            self._send_json(200, {"cases": [self._case_summary(case) for case in self.library.entries()]})
            return
        super().do_GET()

    @staticmethod
    def _case_summary(case: Case) -> dict[str, Any]:
        return {
            "id": case.id,
            "title": dict(case.titles),
            "excerpt": {language: first_sentence(case.source(language)) for language in LANGUAGES},
        }

    def do_OPTIONS(self) -> None:  # noqa: N802 - stdlib naming
        if urlsplit(self.path).path not in API_PATHS:
            self._send_json(404, {"error": "Endpoint not found."})
            return
        self.send_response(204)
        self._send_cors_headers()
        self.send_header("Content-Length", "0")
        self.end_headers()

    def do_POST(self) -> None:  # noqa: N802 - stdlib naming
        path = urlsplit(self.path).path
        if path not in API_PATHS:
            self._send_json(404, {"error": "Endpoint not found."})
            return
        payload = self._read_json()
        if payload is None:
            return
        if path == "/api/session":
            self._create_session(payload)
        elif path == "/api/session/reset":
            self._reset_session(payload)
        else:
            self._take_turn(payload)

    def _read_json(self) -> Any | None:
        length = self.headers.get("Content-Length")
        if length is None:
            self._send_json(411, {"error": "Content-Length is required."})
            return None
        try:
            size = int(length)
        except ValueError:
            self._send_json(400, {"error": "Invalid Content-Length."})
            return None
        if size <= 0 or size > MAX_REQUEST_BYTES:
            self._send_json(413, {"error": "Request body is too large or empty."})
            return None
        try:
            payload = json.loads(self.rfile.read(size).decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError):
            self._send_json(400, {"error": "Request body must be valid UTF-8 JSON."})
            return None
        if not isinstance(payload, dict):
            self._send_json(400, {"error": "Request body must be a JSON object."})
            return None
        return payload

    def _create_session(self, payload: dict[str, Any]) -> None:
        if set(payload) - {"language", "case"}:
            self._send_json(400, {"error": "Session JSON may contain only language and case."})
            return
        language = payload.get("language", "en")
        if language not in LANGUAGES:
            self._send_json(400, {"error": "language must be en or zh."})
            return
        case_id = payload.get("case")
        if case_id is not None and not isinstance(case_id, str):
            self._send_json(400, {"error": "case must be a case id."})
            return
        try:
            storyteller = self.library.storyteller(case_id)
        except CaseError as error:
            self._send_json(404, {"error": str(error)})
            return
        try:
            understanding, understanding_source = storyteller.understanding_with_source(
                language
            )
        except ConfigurationError:
            self._send_json(
                503, {"error": "The Storyteller is not configured yet. Try again later."}
            )
            return
        except ModelError as error:
            self._send_model_error(error)
            return
        except RulingError as error:
            self.log_error("Understander output rejected: %s", error)
            self._send_json(
                502, {"error": "The Storyteller could not read this story. Try again."}
            )
            return

        session_id, state = self.sessions.create(storyteller.case.id, language, understanding)
        self._send_json(
            201,
            {
                "sessionId": session_id,
                "case": {
                    "id": storyteller.case.id,
                    "title": dict(storyteller.case.titles),
                    "player": understanding.player,
                },
                "opening": understanding.opening,
                "understandingSource": understanding_source,
                "playerState": state.to_wire(),
            },
        )

    def _reset_session(self, payload: dict[str, Any]) -> None:
        session_id = payload.get("sessionId")
        if set(payload) != {"sessionId"} or not isinstance(session_id, str):
            self._send_json(400, {"error": "Restart request is incomplete."})
            return
        self.sessions.discard(session_id)
        self._send_json(200, {"status": "ok"})

    def _take_turn(self, payload: dict[str, Any]) -> None:
        if set(payload) != {"sessionId", "type", "text"}:
            self._send_json(
                400, {"error": "Turn JSON must contain sessionId, type, and text."}
            )
            return
        session_id, input_type, text = (
            payload["sessionId"],
            payload["type"],
            payload["text"],
        )
        if not isinstance(session_id, str) or not session_id.strip():
            self._send_json(400, {"error": "sessionId must be a non-empty string."})
            return
        if input_type not in ("say", "do"):
            self._send_json(400, {"error": "type must be either say or do."})
            return
        if not isinstance(text, str) or not text.strip():
            self._send_json(400, {"error": "Enter one line to say or one action to do."})
            return
        if len(text) > MAX_INPUT_LENGTH:
            self._send_json(
                400, {"error": f"Input must be {MAX_INPUT_LENGTH} characters or fewer."}
            )
            return

        try:
            case_id, before = self.sessions.claim(session_id)
        except SessionNotFound:
            self._send_json(404, {"error": "This story session has expired. Restart it."})
            return
        except SessionBusy:
            self._send_json(409, {"error": "The story is still answering. Wait a moment."})
            return

        if before.ended:
            self.sessions.release(session_id)
            self._send_json(409, {"error": "This story has ended. Start a new one."})
            return

        try:
            storyteller = self.library.storyteller(case_id)
        except CaseError as error:
            self.sessions.release(session_id)
            self.log_error("Session points at an unavailable case: %s", error)
            self._send_json(404, {"error": "This story is no longer on the shelf."})
            return

        try:
            ruling, narration = storyteller.resolve(before, input_type, text.strip())
            after = apply_turn(before, input_type, text.strip(), ruling, narration)
        except ConfigurationError:
            self.sessions.release(session_id)
            self._send_json(
                503,
                {"error": "The Storyteller is not configured yet. Try again later."},
            )
            return
        except ModelError as error:
            self.sessions.release(session_id)
            self._send_model_error(error)
            return
        except RulingError as error:
            self.sessions.release(session_id)
            self.log_error("Storyteller output rejected: %s", error)
            self._send_json(
                502,
                {"error": "The Storyteller could not resolve that turn. Try again."},
            )
            return

        self.sessions.release(session_id, after)
        self._send_json(
            200,
            {
                "sessionId": session_id,
                "narration": narration.text,
                "hints": list(narration.hints),
                "outcome": ruling.outcome,
                "restart": ruling.restart,
                "ending": ruling.ending,
                "playerState": after.to_wire(),
            },
        )

    def _send_model_error(self, error: ModelError) -> None:
        self.log_error("Model request failed: %s", error)
        messages = {
            401: "The story API key was rejected. Check DEEPSEEK_API_KEY and restart.",
            402: "The story API account has no balance. Top it up and try again.",
            429: "The storyteller is busy. Wait a moment and try again.",
        }
        status = 503 if error.retryable or error.status_code in {401, 402} else 502
        self._send_json(
            status,
            {
                "error": messages.get(
                    error.status_code,
                    "The storyteller cannot answer right now. Check the server terminal.",
                )
            },
        )

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
        """Let a page served from another origin reach this API."""
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")


def create_server(
    host: str = "127.0.0.1",
    port: int = 8000,
    web_dir: Path | None = None,
    storyteller: Storyteller | None = None,
    sessions: SessionRegistry | None = None,
    case: Case | None = None,
    cases: CaseLibrary | None = None,
) -> ThreadingHTTPServer:
    project_root = Path(__file__).resolve().parents[1]
    static_dir = (web_dir or project_root / "web").resolve()
    if not (static_dir / "index.html").is_file():
        raise FileNotFoundError(f"Playable page not found: {static_dir / 'index.html'}")
    if cases is None:
        if storyteller is not None:
            cases = CaseLibrary.of(storyteller)
        elif case is not None:
            cases = CaseLibrary.of(Storyteller(case))
        else:
            cases = CaseLibrary()
    handler = partial(
        StoryRequestHandler,
        directory=str(static_dir),
        library=cases,
        sessions=sessions or SessionRegistry(),
    )
    return ThreadingHTTPServer((host, port), handler)


def main() -> None:
    parser = argparse.ArgumentParser(description="Serve the case shelf as playable stories.")
    parser.add_argument(
        "--case",
        default=os.getenv("STORYTELLER_CASE") or None,
        help=(
            "Serve only this case (a directory name under cases/, or a path to one). "
            "Omit it to put every case on the shelf."
        ),
    )
    default_host = "0.0.0.0" if os.getenv("RENDER") else "127.0.0.1"
    parser.add_argument("--host", default=default_host)
    parser.add_argument("--port", type=int, default=int(os.getenv("PORT", "8000")))
    args = parser.parse_args()

    project_root = Path(__file__).resolve().parents[1]
    env_loaded = load_env_local(project_root / ".env.local")
    try:
        library = (
            CaseLibrary.of(Storyteller(resolve_case(args.case)))
            if args.case
            else CaseLibrary()
        )
        shelf = library.entries()
        if not shelf:
            raise CaseError(f"No playable cases in {library.case_root}.")
    except CaseError as error:
        print(f"Cannot start: {error}")
        raise SystemExit(2) from error

    server = create_server(host=args.host, port=args.port, cases=library)
    print(f"Playable stories: http://{args.host}:{args.port}")
    print(f"On the shelf: {', '.join(f'{case.id} ({case.title('en')})' for case in shelf)}")
    print(f"Storyteller model: {library.storyteller(shelf[0].id).model.model}")
    if env_loaded:
        print("Loaded local configuration from .env.local.")
    if not library.storyteller(shelf[0].id).configured:
        print("DEEPSEEK_API_KEY is not set; turns will fail until it is.")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopping the story server.")
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
