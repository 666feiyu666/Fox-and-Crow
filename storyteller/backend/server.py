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
from backend.runs import RunError, RunRecord, RunStore
from backend.session import RulingError, StoryState, apply_turn, initial_state
from backend.storyteller import Storyteller
from backend.understanding import Understanding

MAX_INPUT_LENGTH = 400
MAX_REQUEST_BYTES = 8192
API_PATHS = (
    "/api/session",
    "/api/session/reset",
    "/api/turn",
    "/api/runs/resume",
    "/api/runs/delete",
    "/api/settings",
)
REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
CASE_ROOT = REPOSITORY_ROOT / "cases"
PROJECT_ROOT = Path(__file__).resolve().parents[1]
RUNS_ROOT = PROJECT_ROOT / ".runs"
ENV_FILE = PROJECT_ROOT / ".env.local"
SENTENCE_END = re.compile(r"[。！？]|[.!?](?=\s|$)")
EXCERPT_LIMIT = 180
MAX_KEY_LENGTH = 200


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

    def adopt(self, session_id: str, case_id: str, state: StoryState) -> None:
        """Restore a stored run under its own id, so its later turns find it."""
        with self._lock:
            self._states[session_id] = (case_id, state)
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

    def set_api_key(self, api_key: str) -> None:
        """A key set from the page takes effect without restarting the server."""
        with self._lock:
            if self.model is not None:
                self.model.api_key = api_key
            for storyteller in self._storytellers.values():
                storyteller.model.api_key = api_key

    @property
    def model_name(self) -> str:
        return getattr(self.model, "model", "") or ChatModel().model

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
        runs: RunStore,
        env_file: Path,
        **kwargs: Any,
    ) -> None:
        self.library = library
        self.sessions = sessions
        self.runs = runs
        self.env_file = Path(env_file)
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
        if path == "/api/runs":
            self._send_json(200, {"runs": self._run_summaries()})
            return
        if path == "/api/settings":
            self._send_settings()
            return
        super().do_GET()

    @staticmethod
    def _case_summary(case: Case) -> dict[str, Any]:
        return {
            "id": case.id,
            "title": dict(case.titles),
            "excerpt": {language: first_sentence(case.source(language)) for language in LANGUAGES},
        }

    def _run_summaries(self) -> list[dict[str, Any]]:
        summaries = []
        for record in self.runs.read_all():
            title = {language: record.case_id for language in LANGUAGES}
            try:
                title = dict(self.library.storyteller(record.case_id).case.titles)
            except CaseError:
                pass
            last = record.state.turns[-1].narration if record.state.turns else record.opening
            summaries.append({
                "id": record.id,
                "case": record.case_id,
                "title": title,
                "language": record.language,
                "loop": record.state.loop,
                "turn": record.state.turn,
                "ended": record.state.ended,
                "updated": record.updated,
                "excerpt": first_sentence(last),
            })
        return summaries

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
        elif path == "/api/runs/resume":
            self._resume_run(payload)
        elif path == "/api/runs/delete":
            self._delete_run(payload)
        elif path == "/api/settings":
            self._save_settings(payload)
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
        self._save_run(storyteller, session_id, state, understanding.opening)
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

    def _passages(self, record: RunRecord) -> list[dict[str, Any]]:
        """The visible text of a run, in the order the player read it."""
        passages = [{"kind": "opening", "text": record.opening}]
        for turn in record.state.turns:
            passages.append({
                "kind": "turn", "type": turn.input_type, "text": turn.player_input,
                "narration": turn.narration, "turn": turn.number, "loop": turn.loop,
            })
        return passages

    def _resume_run(self, payload: dict[str, Any]) -> None:
        run_id = payload.get("runId")
        if set(payload) != {"runId"} or not isinstance(run_id, str):
            self._send_json(400, {"error": "Resume request must contain runId."})
            return
        try:
            record = self.runs.load(run_id)
        except RunError as error:
            self._send_json(400, {"error": str(error)})
            return
        if record is None:
            self._send_json(404, {"error": "That run is not stored on this server."})
            return
        try:
            storyteller = self.library.storyteller(record.case_id)
        except CaseError:
            self._send_json(404, {"error": "The case this run belongs to is not on the shelf."})
            return
        if storyteller.fingerprint(record.language) != record.digest:
            self._send_json(409, {
                "error": "This run was prepared with a different tale, skill set or model, "
                         "so it cannot continue. Read it here, or start a new story.",
            })
            return
        try:
            understanding, source = storyteller.understanding_with_source(record.language)
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
        self.sessions.adopt(record.id, record.case_id, record.state)
        self._send_json(
            200,
            {
                "sessionId": record.id,
                "case": {
                    "id": record.case_id,
                    "title": dict(storyteller.case.titles),
                    "player": understanding.player,
                },
                "opening": record.opening,
                "passages": self._passages(record),
                "understandingSource": source,
                "playerState": record.state.to_wire(),
            },
        )

    def _delete_run(self, payload: dict[str, Any]) -> None:
        run_id = payload.get("runId")
        if set(payload) != {"runId"} or not isinstance(run_id, str):
            self._send_json(400, {"error": "Delete request must contain runId."})
            return
        try:
            self.runs.delete(run_id)
        except RunError as error:
            self._send_json(400, {"error": str(error)})
            return
        self.sessions.discard(run_id)
        self._send_json(200, {"status": "ok"})

    def _save_run(
        self, storyteller: Storyteller, run_id: str, state: StoryState, opening: str,
    ) -> None:
        """Keep the run on disk after every commit, so a restart does not lose it."""
        try:
            existing = self.runs.load(run_id)
        except RunError:
            existing = None
        opening = opening or (existing.opening if existing else "")
        if not opening:
            try:
                opening = storyteller.understanding(state.language).opening
            except (ConfigurationError, ModelError, RulingError):
                opening = ""
        if not opening:
            self.log_error("Run %s was not saved: no opening passage to store.", run_id)
            return
        now = RunStore.now()
        record = RunRecord(
            id=run_id, case_id=storyteller.case.id, language=state.language,
            opening=opening, digest=storyteller.fingerprint(state.language),
            created=existing.created if existing else now, updated=now, state=state,
        )
        try:
            self.runs.save(record)
        except OSError as error:
            self.log_error("Run %s could not be saved: %s", run_id, error)

    def _settings_state(self) -> dict[str, Any]:
        try:
            configured = self.library.storyteller().configured
        except CaseError:
            configured = bool(getattr(self.library.model, "configured", False))
        return {"configured": configured, "model": self.library.model_name}

    def _send_settings(self) -> None:
        self._send_json(200, self._settings_state(), cors=False)

    def _save_settings(self, payload: dict[str, Any]) -> None:
        if not self._is_local_origin():
            self._send_json(
                403, {"error": "Settings can only be changed from this machine."}, cors=False
            )
            return
        api_key = payload.get("apiKey")
        if set(payload) != {"apiKey"} or not isinstance(api_key, str):
            self._send_json(400, {"error": "Settings must contain apiKey."}, cors=False)
            return
        api_key = api_key.strip()
        if (
            not api_key
            or len(api_key) > MAX_KEY_LENGTH
            or any(character in api_key for character in "\r\n")
        ):
            self._send_json(400, {"error": "That does not look like an API key."}, cors=False)
            return
        try:
            self._write_env_key(api_key)
        except OSError as error:
            self.log_error("Cannot write %s: %s", self.env_file, error)
            self._send_json(
                500, {"error": "The key could not be saved next to the server."}, cors=False
            )
            return
        os.environ["DEEPSEEK_API_KEY"] = api_key
        self.library.set_api_key(api_key)
        self._send_json(200, self._settings_state(), cors=False)

    def _write_env_key(self, api_key: str) -> None:
        lines: list[str] = []
        if self.env_file.is_file():
            lines = self.env_file.read_text(encoding="utf-8").splitlines()
        written = False
        updated: list[str] = []
        for line in lines:
            stripped = line.strip()
            name = stripped[7:].strip() if stripped.startswith("export ") else stripped
            if stripped and not stripped.startswith("#") and "=" in name:
                if name.split("=", 1)[0].strip() == "DEEPSEEK_API_KEY":
                    updated.append(f"DEEPSEEK_API_KEY={api_key}")
                    written = True
                    continue
            updated.append(line)
        if not written:
            updated.append(f"DEEPSEEK_API_KEY={api_key}")
        self.env_file.parent.mkdir(parents=True, exist_ok=True)
        self.env_file.write_text("\n".join(updated).rstrip() + "\n", encoding="utf-8")

    def _is_local_origin(self) -> bool:
        """Writing a key to disk is a local act; a remote page may not trigger it."""
        origin = self.headers.get("Origin")
        if not origin:
            return True
        host = (urlsplit(origin).hostname or "").lower()
        if host in {"localhost", "127.0.0.1", "::1"}:
            return True
        request_host = (self.headers.get("Host") or "").split(":")[0].strip().lower()
        return bool(request_host) and host == request_host

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
        self._save_run(storyteller, session_id, after, "")
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

    def _send_json(
        self, status: int, payload: dict[str, Any], *, cors: bool = True,
    ) -> None:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        if cors:
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
    runs: RunStore | None = None,
    env_file: Path | None = None,
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
        runs=runs or RunStore(RUNS_ROOT),
        env_file=env_file or ENV_FILE,
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
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8000)
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
    print(f"Past runs: {RUNS_ROOT}")
    print(f"Settings file: {ENV_FILE}")
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
