"""The Storyteller: one case, two model calls per turn.

The ruling decides what the player's line changes; the narration writes it. Both
calls use the same system prompt — the engine skill plus the case's canon in the
session language — so the story never changes language halfway through.
"""

from __future__ import annotations

import json
from typing import Any

from backend.case import Case
from backend.model import ChatModel
from backend.session import InputType, Narration, Ruling, RulingError, StoryState

RULING_PHASE = (
    "You are in phase 1 (ruling). Judge the action in `action` against the world "
    "canon and `recent_turns`, then return the ruling object only."
)
NARRATION_PHASE = (
    "You are in phase 2 (narration). The ruling is already made and is final. "
    "Write the visible passage it authorises, then return the narration object only."
)


class Storyteller:
    """Judges one player input, then narrates it, in two separate model calls."""

    def __init__(self, case: Case, model: ChatModel | None = None) -> None:
        self.case = case
        self.model = model or ChatModel()

    @property
    def configured(self) -> bool:
        return self.model.configured

    def opening(self, language: str) -> str:
        return self.case.opening(language)

    def resolve(
        self,
        state: StoryState,
        input_type: InputType,
        text: str,
    ) -> tuple[Ruling, Narration]:
        context = state.to_agent_context(self.case, input_type, text)
        system = self.case.system_prompt(state.language)
        ruling = self.rule(system, context)
        narration = self.narrate(system, context, ruling)
        return ruling, narration

    def rule(self, system: str, context: dict[str, Any]) -> Ruling:
        payload = self.model.complete_json(
            f"{system}\n\n---\n\n{RULING_PHASE}",
            "Turn input:\n" + json.dumps(context, ensure_ascii=False),
            max_tokens=700,
            temperature=0.2,
        )
        try:
            return Ruling.from_dict(payload)
        except RulingError as error:
            raise RulingError(f"Storyteller returned an unusable ruling: {error}") from error

    def narrate(
        self, system: str, context: dict[str, Any], ruling: Ruling
    ) -> Narration:
        payload = self.model.complete_json(
            f"{system}\n\n---\n\n{NARRATION_PHASE}",
            "Turn input with the final ruling:\n"
            + json.dumps({**context, "ruling": ruling.to_dict()}, ensure_ascii=False),
            max_tokens=900,
            temperature=0.8,
        )
        try:
            return Narration.from_dict(payload)
        except RulingError as error:
            raise RulingError(f"Storyteller returned an unusable narration: {error}") from error
