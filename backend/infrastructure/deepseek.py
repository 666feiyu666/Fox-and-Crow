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
DEFAULT_API_ATTEMPTS = 3
RETRYABLE_HTTP_STATUSES = {429, 500, 502, 503, 504}

ENV_LOCAL_KEYS = {
    "DEEPSEEK_API_KEY",
    "DEEPSEEK_BASE_URL",
    "DEEPSEEK_MODEL",
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


def load_env_local(path: Path) -> bool:
    if not path.is_file():
        return False

    for line_number, raw_line in enumerate(
        path.read_text(encoding="utf-8").splitlines(),
        start=1,
    ):
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("export "):
            line = line[7:].lstrip()
        if "=" not in line:
            raise ConfigurationError(
                f"Invalid .env.local line {line_number}: expected NAME=value."
            )

        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip()
        if key not in ENV_LOCAL_KEYS:
            raise ConfigurationError(
                f"Unsupported .env.local setting on line {line_number}: {key}."
            )
        if len(value) >= 2 and value[0] == value[-1] and value[0] in {"'", '"'}:
            value = value[1:-1]

        os.environ.setdefault(key, value)
    return True


class DeepSeekAgentGateway:
    """DeepSeek adapter for the single Node 2.5 Story Agent."""

    def __init__(
        self,
        api_key: str | None = None,
        base_url: str | None = None,
        model: str | None = None,
        timeout: float = 30.0,
        api_attempts: int = DEFAULT_API_ATTEMPTS,
    ) -> None:
        self.api_key = api_key if api_key is not None else os.getenv("DEEPSEEK_API_KEY", "")
        self.base_url = (
            base_url or os.getenv("DEEPSEEK_BASE_URL", DEFAULT_BASE_URL)
        ).rstrip("/")
        self.model = model or os.getenv("DEEPSEEK_MODEL", DEFAULT_MODEL)
        self.timeout = timeout
        self.api_attempts = max(1, api_attempts)

    @property
    def configured(self) -> bool:
        return bool(self.api_key.strip())

    def narrate(self, context: dict[str, Any]) -> str:
        system_prompt = (
            "You are the Story Agent for an interactive adaptation of The Fox and the Crow. "
            "Continue the visible story in English using first-person limited perspective, present tense, "
            "and two to four concise sentences. The supplied recent turns are the only continuity context. "
            "When input.type is say, treat input.text as the fox's exact spoken words: do not rewrite them "
            "or append another promise, goal, decision, or line of dialogue for the fox. When input.type is "
            "do, treat input.text as one attempted action: describe its process, perceptible result, and the "
            "reactions of other characters or the environment, but do not add another major action or any "
            "unrequested fox dialogue. Never decide victory, escape from the loop, inventory, trust, hunger, "
            "or other authoritative state. Stop after the immediate response, leaving the next meaningful "
            "choice to the player. "
            'Return JSON only as {"narration": "..."}.'
        )
        result = self._request_json(
            system_prompt,
            context,
            instruction="Write the next visible story passage as JSON:\n",
            max_tokens=240,
            temperature=0.6,
        )
        narration = result.get("narration")
        if not isinstance(narration, str) or not narration.strip():
            raise DeepSeekError("DeepSeek returned an invalid Story Agent narration.")
        return " ".join(narration.split())

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
