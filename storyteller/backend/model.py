"""Minimal OpenAI-compatible chat client used by the Storyteller."""

from __future__ import annotations

import json
import os
import time
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

DEFAULT_BASE_URL = "https://api.deepseek.com"
DEFAULT_MODEL = "deepseek-v4-pro"
RETRYABLE_STATUSES = {429, 500, 502, 503, 504}
ENV_LOCAL_KEYS = {"DEEPSEEK_API_KEY", "DEEPSEEK_BASE_URL", "DEEPSEEK_MODEL"}


class ConfigurationError(RuntimeError):
    """The model is not configured, so no turn can be judged."""


class ModelError(RuntimeError):
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


def load_env_local(path: Path) -> bool:
    """Read NAME=value lines from a local env file without overwriting real env."""
    if not path.is_file():
        return False
    for number, raw_line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("export "):
            line = line[7:].lstrip()
        if "=" not in line:
            raise ConfigurationError(
                f"Invalid .env.local line {number}: expected NAME=value."
            )
        key, value = (part.strip() for part in line.split("=", 1))
        if key not in ENV_LOCAL_KEYS:
            raise ConfigurationError(f"Unsupported .env.local setting: {key}.")
        if len(value) >= 2 and value[0] == value[-1] and value[0] in {"'", '"'}:
            value = value[1:-1]
        os.environ.setdefault(key, value)
    return True


class ChatModel:
    def __init__(
        self,
        api_key: str | None = None,
        base_url: str | None = None,
        model: str | None = None,
        timeout: float = 60.0,
        attempts: int = 3,
    ) -> None:
        self.api_key = api_key if api_key is not None else os.getenv("DEEPSEEK_API_KEY", "")
        self.base_url = (base_url or os.getenv("DEEPSEEK_BASE_URL", DEFAULT_BASE_URL)).rstrip("/")
        self.model = model or os.getenv("DEEPSEEK_MODEL", DEFAULT_MODEL)
        self.timeout = timeout
        self.attempts = max(1, attempts)

    @property
    def configured(self) -> bool:
        return bool(self.api_key.strip())

    def complete_json(
        self,
        system: str,
        user: str,
        *,
        max_tokens: int = 700,
        temperature: float = 0.4,
    ) -> dict[str, Any]:
        """Send one chat request and return the decoded JSON object it produced."""
        if not self.configured:
            raise ConfigurationError(
                "DEEPSEEK_API_KEY is not set; the Storyteller cannot judge a turn."
            )
        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
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

        for attempt in range(1, self.attempts + 1):
            try:
                with urlopen(request, timeout=self.timeout) as response:
                    body = response.read().decode("utf-8")
                break
            except HTTPError as error:
                retryable = error.code in RETRYABLE_STATUSES
                if retryable and attempt < self.attempts:
                    time.sleep(0.5 * attempt)
                    continue
                raise ModelError(
                    f"Model returned HTTP {error.code}: {self._detail(error)}",
                    status_code=error.code,
                    retryable=retryable,
                ) from error
            except (URLError, TimeoutError) as error:
                if attempt < self.attempts:
                    time.sleep(0.5 * attempt)
                    continue
                raise ModelError(
                    "The model could not be reached before the request timed out.",
                    retryable=True,
                ) from error
            except (UnicodeDecodeError, json.JSONDecodeError) as error:
                raise ModelError("The model returned an unreadable response.") from error

        try:
            content = json.loads(body)["choices"][0]["message"]["content"]
            result = json.loads(content)
        except (KeyError, IndexError, TypeError, json.JSONDecodeError) as error:
            raise ModelError("The model returned an unexpected response shape.") from error
        if not isinstance(result, dict):
            raise ModelError("The model returned JSON that is not an object.")
        return result

    @staticmethod
    def _detail(error: HTTPError) -> str:
        try:
            payload = json.loads(error.read().decode("utf-8", errors="replace"))
        except (AttributeError, OSError, TypeError, json.JSONDecodeError):
            return ""
        provider_error = payload.get("error") if isinstance(payload, dict) else None
        if isinstance(provider_error, dict) and isinstance(provider_error.get("message"), str):
            return " ".join(provider_error["message"].split())[:300]
        if isinstance(provider_error, str):
            return " ".join(provider_error.split())[:300]
        return ""
