from __future__ import annotations

import json
import os
import time
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from backend.story_agent.ports import FreeActionOutcome, NarrationAudit


DEFAULT_BASE_URL = "https://api.deepseek.com"
DEFAULT_MODEL = "deepseek-v4-pro"
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
    """DeepSeek adapter implementing the current Game and Story Agent ports."""

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

    def generate_free_action(
        self,
        passage: str,
        loop_count: int,
        action: str,
    ) -> FreeActionOutcome:
        """Preserve the original free-action prototype behind a responsibility name."""
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
            '{"narration": "...", "promoted": true, "choiceLabel": "..."}. '
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
                raise DeepSeekError(
                    "DeepSeek returned a choice label longer than 80 characters."
                )
        elif choice_label is not None:
            raise DeepSeekError("DeepSeek returned a choice label for an unpromoted action.")

        return FreeActionOutcome(
            narration=narration,
            promoted=promoted,
            choice_label=choice_label,
        )

    def interpret_action(self, state: dict[str, Any], action: str) -> dict[str, Any]:
        system_prompt = (
            "You are the Game Agent for a small interactive adaptation of The Fox and the Crow. "
            "Classify the fox player's action using the authoritative state supplied by the server. "
            "Choose ask_problem when the fox asks the crow about her distress, missing possession, "
            "or what is wrong. Choose search_necklace when the fox searches the bushes or looks for "
            "the crow's necklace. Choose return_necklace when the fox tries to give the necklace back. "
            "Choose other for every other action. Use timeCost 1 for asking, returning, and other actions; "
            "use timeCost 2 for searching unless less time remains. Do not invent state changes or narration. "
            'Return JSON only in exactly this shape: {"intent": "ask_problem", "timeCost": 1}.'
        )
        return self._request_json(
            system_prompt,
            {"state": state, "playerAction": action},
            instruction="Resolve this turn as JSON:\n",
            max_tokens=100,
            temperature=0.0,
        )

    def narrate(
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
            'Return JSON only as {"narration": "..."}.'
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
            raise DeepSeekError("DeepSeek returned an invalid Story Agent narration.")
        return " ".join(narration.split())

    def audit_narration(
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
            '{"grounded": true, "feedback": null}. When false, feedback must be one concise editing '
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
