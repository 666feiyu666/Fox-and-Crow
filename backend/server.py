from __future__ import annotations

import argparse
import json
import os
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit
from urllib.request import Request, urlopen


DEFAULT_BASE_URL = "https://api.deepseek.com"
DEFAULT_MODEL = "deepseek-v4-flash"
MAX_ACTION_LENGTH = 500
MAX_REQUEST_BYTES = 4096

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
    pass


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
    ) -> None:
        self.api_key = api_key if api_key is not None else os.getenv("DEEPSEEK_API_KEY", "")
        self.base_url = (base_url or os.getenv("DEEPSEEK_BASE_URL", DEFAULT_BASE_URL)).rstrip("/")
        self.model = model or os.getenv("DEEPSEEK_MODEL", DEFAULT_MODEL)
        self.timeout = timeout

    @property
    def configured(self) -> bool:
        return bool(self.api_key.strip())

    def generate_action(self, passage: str, loop_count: int, action: str) -> str:
        if not self.configured:
            raise ConfigurationError(
                "DeepSeek is not configured. Set DEEPSEEK_API_KEY before starting the server."
            )

        system_prompt = (
            "You are the narrator of an interactive adaptation of The Fox and the Crow. "
            "Respond to the fox player's alternative action without changing passages or ending the time loop. "
            "Write two to four concise sentences in English, in second person and present tense. "
            "Respect the current scene and describe an immediate, plausible consequence. "
            "Return JSON only, in exactly this shape: {\"narration\": \"...\"}."
        )
        player_state = {
            "passage": passage,
            "scene": SCENE_CONTEXT[passage],
            "completed_loops": loop_count,
            "player_action": action,
        }
        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {
                    "role": "user",
                    "content": "Narrate this game state as JSON:\n"
                    + json.dumps(player_state, ensure_ascii=False),
                },
            ],
            "response_format": {"type": "json_object"},
            "thinking": {"type": "disabled"},
            "max_tokens": 300,
            "temperature": 0.7,
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

        try:
            with urlopen(request, timeout=self.timeout) as response:
                response_data = json.loads(response.read().decode("utf-8"))
        except HTTPError as error:
            raise DeepSeekError(f"DeepSeek returned HTTP {error.code}.") from error
        except (URLError, TimeoutError) as error:
            raise DeepSeekError("DeepSeek could not be reached before the request timed out.") from error
        except (UnicodeDecodeError, json.JSONDecodeError) as error:
            raise DeepSeekError("DeepSeek returned an unreadable response.") from error

        try:
            content = response_data["choices"][0]["message"]["content"]
            result = json.loads(content)
            narration = result["narration"].strip()
        except (KeyError, IndexError, TypeError, AttributeError, json.JSONDecodeError) as error:
            raise DeepSeekError("DeepSeek returned an unexpected response shape.") from error

        if not narration:
            raise DeepSeekError("DeepSeek returned an empty narration.")
        return narration


class StoryRequestHandler(SimpleHTTPRequestHandler):
    def __init__(
        self,
        *args: Any,
        directory: str,
        deepseek_client: DeepSeekClient,
        **kwargs: Any,
    ) -> None:
        self.deepseek_client = deepseek_client
        super().__init__(*args, directory=directory, **kwargs)

    def do_GET(self) -> None:
        path = urlsplit(self.path).path
        if path == "/health":
            self._send_json(
                200,
                {
                    "status": "ok",
                    "deepseekConfigured": self.deepseek_client.configured,
                    "model": self.deepseek_client.model,
                },
            )
            return
        super().do_GET()

    def do_POST(self) -> None:
        if urlsplit(self.path).path != "/api/action":
            self._send_json(404, {"error": "Endpoint not found."})
            return

        content_length = self.headers.get("Content-Length")
        if content_length is None:
            self._send_json(411, {"error": "Content-Length is required."})
            return

        try:
            body_length = int(content_length)
        except ValueError:
            self._send_json(400, {"error": "Invalid Content-Length."})
            return

        if body_length <= 0 or body_length > MAX_REQUEST_BYTES:
            self._send_json(413, {"error": "Request body is too large or empty."})
            return

        try:
            payload = json.loads(self.rfile.read(body_length).decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError):
            self._send_json(400, {"error": "Request body must be valid UTF-8 JSON."})
            return

        error = self._validate_payload(payload)
        if error is not None:
            self._send_json(400, {"error": error})
            return

        passage = payload["passage"]
        loop_count = payload["loopCount"]
        action = payload["action"].strip()

        try:
            narration = self.deepseek_client.generate_action(passage, loop_count, action)
        except ConfigurationError as error:
            self._send_json(503, {"error": str(error)})
            return
        except DeepSeekError as error:
            self._send_json(502, {"error": str(error)})
            return

        self._send_json(
            200,
            {
                "narration": narration,
                "passage": passage,
                "model": self.deepseek_client.model,
            },
        )

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
) -> ThreadingHTTPServer:
    project_root = Path(__file__).resolve().parents[1]
    static_dir = (dist_dir or project_root / "dist").resolve()
    if not (static_dir / "index.html").is_file():
        raise FileNotFoundError(f"Built story not found: {static_dir / 'index.html'}")

    deepseek_client = client or DeepSeekClient()
    handler = partial(
        StoryRequestHandler,
        directory=str(static_dir),
        deepseek_client=deepseek_client,
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
