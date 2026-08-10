from __future__ import annotations

import argparse
import json
import os
import time
from dataclasses import dataclass
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit
from urllib.request import Request, urlopen

try:
    from backend.node_two import (
        NodeTwoError,
        NodeTwoSessionStore,
        narrative_view,
        parse_dm_decision,
        player_view,
        public_event_view,
        resolve_node_two_turn,
        state_view,
    )
except ModuleNotFoundError:  # Support `python backend/server.py` from the project root.
    from node_two import (  # type: ignore[no-redef]
        NodeTwoError,
        NodeTwoSessionStore,
        narrative_view,
        parse_dm_decision,
        player_view,
        public_event_view,
        resolve_node_two_turn,
        state_view,
    )


DEFAULT_BASE_URL = "https://api.deepseek.com"
DEFAULT_MODEL = "deepseek-v4-pro"
MAX_ACTION_LENGTH = 500
MAX_REQUEST_BYTES = 4096
DEFAULT_API_ATTEMPTS = 3
RETRYABLE_HTTP_STATUSES = {429, 500, 502, 503, 504}

SCENE_CONTEXT = {
    "Morning": "The hungry fox sees a crow holding cheese on a high branch.",
    "Under the Tree": "The fox stands below the crow and wants her to open her beak.",
    "Flattery": "The fox has praised the crow's feathers; she is proud but still holds the cheese.",
    "The Song": "The fox has asked the crow to sing and waits below the branch.",
    "The Cheese Falls": "The crow has opened her beak and the fox has caught the fallen cheese.",
    "Evening": "The fox ate the cheese, but the day is rewinding toward the same morning.",
}


class ConfigurationError(RuntimeError):
    pass


class DeepSeekError(RuntimeError):
    def __init__(
        self,
        message: str,
        *,
        status_code: int | None = None,
        retryable: bool = False,
    ) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.retryable = retryable


@dataclass(frozen=True)
class ActionOutcome:
    narration: str
    promoted: bool
    choice_label: str | None = None


@dataclass(frozen=True)
class NarrationAudit:
    grounded: bool
    feedback: str | None = None


ENV_LOCAL_KEYS = {
    "DEEPSEEK_API_KEY",
    "DEEPSEEK_BASE_URL",
    "DEEPSEEK_MODEL",
}


def load_env_local(path: Path) -> bool:
    if not path.is_file():
        return False

    for line_number, raw_line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("export "):
            line = line[7:].lstrip()
        if "=" not in line:
            raise ConfigurationError(f"Invalid .env.local line {line_number}: expected NAME=value.")

        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip()
        if key not in ENV_LOCAL_KEYS:
            raise ConfigurationError(f"Unsupported .env.local setting on line {line_number}: {key}.")
        if len(value) >= 2 and value[0] == value[-1] and value[0] in {"'", '"'}:
            value = value[1:-1]

        os.environ.setdefault(key, value)
    return True


class DeepSeekClient:
    def __init__(
        self,
        api_key: str | None = None,
        base_url: str | None = None,
        model: str | None = None,
        timeout: float = 30.0,
        api_attempts: int = DEFAULT_API_ATTEMPTS,
    ) -> None:
        self.api_key = api_key if api_key is not None else os.getenv("DEEPSEEK_API_KEY", "")
        self.base_url = (base_url or os.getenv("DEEPSEEK_BASE_URL", DEFAULT_BASE_URL)).rstrip("/")
        self.model = model or os.getenv("DEEPSEEK_MODEL", DEFAULT_MODEL)
        self.timeout = timeout
        self.api_attempts = max(1, api_attempts)

    @property
    def configured(self) -> bool:
        return bool(self.api_key.strip())

    def generate_action(self, passage: str, loop_count: int, action: str) -> ActionOutcome:
        system_prompt = (
            "You are the narrator of an interactive adaptation of The Fox and the Crow. "
            "Respond to the fox player's alternative action without deciding navigation or ending the time loop. "
            "Write two to four concise sentences in English, in second person and present tense. "
            "Respect the current scene and describe an immediate, plausible consequence. "
            "Also decide whether the action should become a reusable choice. Promote any concrete, "
            "scene-grounded action that creates a meaningful character or world consequence, or reveals "
            "useful repeatable information. Partial successes and failures may be promoted when they change "
            "trust, reveal a disposition, move someone, consume a resource, or teach the player something. "
            "Do not promote only when the input is not an action, is incoherent or impossible in the scene, "
            "or produces no meaningful consequence. If promoted, write a concise action-oriented choice label "
            "of at most 80 characters. Return JSON only, in exactly this shape: "
            "{\"narration\": \"...\", \"promoted\": true, \"choiceLabel\": \"...\"}. "
            "Use false and null for the final two values when the action is not promoted."
        )
        player_state = {
            "passage": passage,
            "scene": SCENE_CONTEXT[passage],
            "completed_loops": loop_count,
            "player_action": action,
        }
        result = self._request_json(
            system_prompt,
            player_state,
            instruction="Narrate this game state as JSON:\n",
            max_tokens=300,
            temperature=0.7,
        )

        try:
            narration = result["narration"].strip()
            promoted = result["promoted"]
            choice_label = result["choiceLabel"]
        except (KeyError, TypeError, AttributeError) as error:
            raise DeepSeekError("DeepSeek returned an unexpected response shape.") from error

        if not narration:
            raise DeepSeekError("DeepSeek returned an empty narration.")
        if not isinstance(promoted, bool):
            raise DeepSeekError("DeepSeek returned an invalid promotion decision.")
        if promoted:
            if not isinstance(choice_label, str) or not choice_label.strip():
                raise DeepSeekError("DeepSeek promoted the action without a choice label.")
            choice_label = " ".join(choice_label.split())
            if len(choice_label) > 80:
                raise DeepSeekError("DeepSeek returned a choice label longer than 80 characters.")
        elif choice_label is not None:
            raise DeepSeekError("DeepSeek returned a choice label for an unpromoted action.")

        return ActionOutcome(
            narration=narration,
            promoted=promoted,
            choice_label=choice_label,
        )

    def resolve_node_two(self, state: dict[str, Any], action: str) -> dict[str, Any]:
        system_prompt = (
            "You are the DM resolver for a small interactive adaptation of The Fox and the Crow. "
            "Classify the fox player's action using the authoritative state supplied by the server. "
            "Choose ask_problem when the fox asks the crow about her distress, missing possession, "
            "or what is wrong. Choose search_necklace when the fox searches the bushes or looks for "
            "the crow's necklace. Choose return_necklace when the fox tries to give the necklace back. "
            "Choose other for every other action. Use timeCost 1 for asking, returning, and other actions; "
            "use timeCost 2 for searching unless less time remains. Do not invent state changes or narration. "
            "Return JSON only in exactly this shape: {\"intent\": \"ask_problem\", \"timeCost\": 1}."
        )
        return self._request_json(
            system_prompt,
            {"state": state, "playerAction": action},
            instruction="Resolve this turn as JSON:\n",
            max_tokens=100,
            temperature=0.0,
        )

    def narrate_node_two(
        self,
        before_perspective: dict[str, Any],
        after_perspective: dict[str, Any],
        action: str,
        public_events: list[dict[str, str]],
        grounding_feedback: str | None = None,
    ) -> str:
        system_prompt = (
            "You are the Story Agent for an interactive adaptation of The Fox and the Crow. "
            "Write two to four concise sentences in English, in second person and present tense. "
            "Freely dramatize the player's action with pacing, atmosphere, and sensory detail, while "
            "treating the supplied public events as the complete factual result of the turn. You receive "
            "only the fox's perspective, not the authoritative world state. Do not infer explanations for "
            "visible behavior or add an object, motive, discovery, knowledge, relationship change, or "
            "world-state change that is not supported by the perspective, player action, or public events. "
            "Return JSON only as {\"narration\": \"...\"}."
        )
        turn_context: dict[str, Any] = {
            "perspectiveBefore": before_perspective,
            "playerAction": action,
            "publicEvents": public_events,
            "perspectiveAfter": after_perspective,
        }
        if grounding_feedback is not None:
            turn_context["groundingFeedback"] = grounding_feedback

        result = self._request_json(
            system_prompt,
            turn_context,
            instruction="Write this grounded story continuation as JSON:\n",
            max_tokens=240,
            temperature=0.6,
        )
        narration = result.get("narration")
        if not isinstance(narration, str) or not narration.strip():
            raise DeepSeekError("DeepSeek returned an invalid Node Two narration.")
        return " ".join(narration.split())

    def audit_node_two_narration(
        self,
        before_perspective: dict[str, Any],
        after_perspective: dict[str, Any],
        action: str,
        public_events: list[dict[str, str]],
        narration: str,
    ) -> NarrationAudit:
        system_prompt = (
            "You are an independent Grounding Agent for player-facing interactive fiction. Check whether "
            "every story fact in the proposed narration is supported by the player's action, the public "
            "events, or the before/after player perspective. Those sources are complete; plausibility and "
            "genre expectations are not evidence. Sensory style is allowed only when it adds no new story "
            "fact. Reject unsupported objects, hidden goals, explanations of behavior, discoveries, "
            "knowledge, relationships, or state changes. Return JSON only as "
            "{\"grounded\": true, \"feedback\": null}. When false, feedback must be one concise editing "
            "instruction that identifies unsupported claims to remove without suggesting replacement facts."
        )
        result = self._request_json(
            system_prompt,
            {
                "perspectiveBefore": before_perspective,
                "playerAction": action,
                "publicEvents": public_events,
                "perspectiveAfter": after_perspective,
                "proposedNarration": narration,
            },
            instruction="Audit this proposed narration as JSON:\n",
            max_tokens=180,
            temperature=0.0,
        )
        grounded = result.get("grounded")
        feedback = result.get("feedback")
        if not isinstance(grounded, bool):
            raise DeepSeekError("DeepSeek returned an invalid narration audit decision.")
        if grounded:
            if feedback is not None:
                raise DeepSeekError("DeepSeek returned feedback for a grounded narration.")
            return NarrationAudit(grounded=True)
        if not isinstance(feedback, str) or not feedback.strip():
            raise DeepSeekError("DeepSeek rejected narration without grounding feedback.")
        return NarrationAudit(grounded=False, feedback=feedback.strip())

    def _request_json(
        self,
        system_prompt: str,
        data: dict[str, Any],
        *,
        instruction: str,
        max_tokens: int,
        temperature: float,
    ) -> dict[str, Any]:
        if not self.configured:
            raise ConfigurationError(
                "DeepSeek is not configured. Set DEEPSEEK_API_KEY before starting the server."
            )

        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {
                    "role": "user",
                    "content": instruction + json.dumps(data, ensure_ascii=False),
                },
            ],
            "response_format": {"type": "json_object"},
            "thinking": {"type": "disabled"},
            "max_tokens": max_tokens,
            "temperature": temperature,
            "stream": False,
        }
        request = Request(
            f"{self.base_url}/chat/completions",
            data=json.dumps(payload).encode("utf-8"),
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            },
            method="POST",
        )

        for attempt in range(1, self.api_attempts + 1):
            try:
                with urlopen(request, timeout=self.timeout) as response:
                    raw_response = response.read().decode("utf-8")
                response_data = json.loads(raw_response)
                break
            except HTTPError as error:
                retryable = error.code in RETRYABLE_HTTP_STATUSES
                if retryable and attempt < self.api_attempts:
                    time.sleep(0.5 * attempt)
                    continue
                detail = self._http_error_detail(error)
                message = f"DeepSeek returned HTTP {error.code}"
                if detail:
                    message += f": {detail}"
                raise DeepSeekError(
                    message,
                    status_code=error.code,
                    retryable=retryable,
                ) from error
            except (URLError, TimeoutError) as error:
                if attempt < self.api_attempts:
                    time.sleep(0.5 * attempt)
                    continue
                raise DeepSeekError(
                    "DeepSeek could not be reached before the request timed out.",
                    retryable=True,
                ) from error
            except (UnicodeDecodeError, json.JSONDecodeError) as error:
                raise DeepSeekError("DeepSeek returned an unreadable response.") from error

        try:
            content = response_data["choices"][0]["message"]["content"]
            result = json.loads(content)
        except (KeyError, IndexError, TypeError, json.JSONDecodeError) as error:
            raise DeepSeekError("DeepSeek returned an unexpected response shape.") from error
        if not isinstance(result, dict):
            raise DeepSeekError("DeepSeek returned JSON that is not an object.")
        return result

    @staticmethod
    def _http_error_detail(error: HTTPError) -> str:
        try:
            body = error.read().decode("utf-8", errors="replace")
            payload = json.loads(body)
        except (AttributeError, OSError, TypeError, json.JSONDecodeError):
            return ""

        if isinstance(payload, dict):
            provider_error = payload.get("error")
            if isinstance(provider_error, dict):
                message = provider_error.get("message")
                if isinstance(message, str):
                    return " ".join(message.split())[:500]
            if isinstance(provider_error, str):
                return " ".join(provider_error.split())[:500]
        return ""


class StoryRequestHandler(SimpleHTTPRequestHandler):
    def __init__(
        self,
        *args: Any,
        directory: str,
        deepseek_client: DeepSeekClient,
        node_two_sessions: NodeTwoSessionStore,
        **kwargs: Any,
    ) -> None:
        self.deepseek_client = deepseek_client
        self.node_two_sessions = node_two_sessions
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
            self._handle_action(payload)
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

    def _handle_action(self, payload: Any) -> None:

        error = self._validate_payload(payload)
        if error is not None:
            self._send_json(400, {"error": error})
            return

        passage = payload["passage"]
        loop_count = payload["loopCount"]
        action = payload["action"].strip()

        try:
            outcome = self.deepseek_client.generate_action(passage, loop_count, action)
        except ConfigurationError:
            self._send_json(
                503,
                {
                    "error": (
                        "The story API is not configured. Set DEEPSEEK_API_KEY "
                        "and restart the server."
                    )
                },
            )
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
            self._send_json(400, {"error": "Node Two begins at loopCount 3 or later."})
            return

        session_id, state = self.node_two_sessions.create(loop_count=loop_count)
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

        try:
            before = self.node_two_sessions.get(session_id)
        except NodeTwoError:
            self._send_json(
                404,
                {"error": "This story session has expired. Restart the story to continue."},
            )
            return

        clean_action = action.strip()
        try:
            dm_payload = self.deepseek_client.resolve_node_two(
                state_view(before),
                clean_action,
            )
            decision = parse_dm_decision(dm_payload, before)
            resolution = resolve_node_two_turn(before, decision)
            before_perspective = narrative_view(before)
            after_perspective = narrative_view(resolution.state)
            public_events = public_event_view(resolution)
            grounding_feedback = None
            for _ in range(2):
                narration = self.deepseek_client.narrate_node_two(
                    before_perspective,
                    after_perspective,
                    clean_action,
                    public_events,
                    grounding_feedback,
                )
                audit = self.deepseek_client.audit_node_two_narration(
                    before_perspective,
                    after_perspective,
                    clean_action,
                    public_events,
                    narration,
                )
                if audit.grounded:
                    break
                grounding_feedback = audit.feedback
            else:
                narration = " ".join(event["description"] for event in public_events)
                self.log_message(
                    "Story narration failed grounding twice; using public-event fallback."
                )
        except ConfigurationError:
            self._send_json(
                503,
                {
                    "error": (
                        "The story API is not configured. Set DEEPSEEK_API_KEY "
                        "and restart the server."
                    )
                },
            )
            return
        except DeepSeekError as error:
            self._send_deepseek_error(error)
            return
        except NodeTwoError:
            self._send_json(
                502,
                {"error": "The story could not understand that action. Try describing it another way."},
            )
            return

        try:
            self.node_two_sessions.commit(session_id, before, resolution.state)
        except NodeTwoError:
            self._send_json(
                409,
                {"error": "The story changed before this action finished. Try again."},
            )
            return

        self._send_json(
            200,
            {
                "sessionId": session_id,
                "narration": narration,
                "outcome": resolution.outcome.value,
                "playerState": player_view(resolution.state),
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

        self.node_two_sessions.discard(session_id)
        self._send_json(200, {"status": "ok"})

    @staticmethod
    def _validate_payload(payload: Any) -> str | None:
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
    client: DeepSeekClient | None = None,
    session_store: NodeTwoSessionStore | None = None,
) -> ThreadingHTTPServer:
    project_root = Path(__file__).resolve().parents[1]
    static_dir = (dist_dir or project_root / "dist").resolve()
    if not (static_dir / "index.html").is_file():
        raise FileNotFoundError(f"Built story not found: {static_dir / 'index.html'}")

    deepseek_client = client or DeepSeekClient()
    node_two_sessions = session_store or NodeTwoSessionStore()
    handler = partial(
        StoryRequestHandler,
        directory=str(static_dir),
        deepseek_client=deepseek_client,
        node_two_sessions=node_two_sessions,
    )
    return ThreadingHTTPServer((host, port), handler)


def main() -> None:
    parser = argparse.ArgumentParser(description="Serve the Twine story and DeepSeek action API.")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8000)
    args = parser.parse_args()

    project_root = Path(__file__).resolve().parents[1]
    env_local_loaded = load_env_local(project_root / ".env.local")
    client = DeepSeekClient()
    server = create_server(host=args.host, port=args.port, client=client)
    print(f"Story server: http://{args.host}:{args.port}")
    print(f"DeepSeek model: {client.model}")
    if env_local_loaded:
        print("Loaded local configuration from .env.local.")
    if not client.configured:
        print("DeepSeek is not configured; set DEEPSEEK_API_KEY and restart the server.")

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopping story server.")
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
