"""The Storyteller: skill loading and the two-phase turn.

Phase 1 (ruling) decides what the player's line changes in the world.
Phase 2 (narration) turns that ruling into the visible passage. Both phases are
driven only by the skill files under ``skills/storyteller/``.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from backend.model import ChatModel, ConfigurationError
from backend.session import InputType, Narration, Ruling, RulingError, StoryState

SKILL_DIR = Path(__file__).resolve().parents[1] / "skills" / "storyteller"

RULING_PHASE = (
    "You are in phase 1 (ruling). Judge the action in `action` against the world "
    "canon and the current `state`, then return the ruling object only."
)
NARRATION_PHASE = (
    "You are in phase 2 (narration). The ruling is already made and is final. "
    "Write the visible passage it authorises, then return the narration object only."
)


@dataclass(frozen=True)
class Skill:
    """The Storyteller's written identity, world canon, and opening scenes."""

    instructions: str
    world: str
    openings: dict[str, dict[str, str]]

    @classmethod
    def load(cls, directory: Path = SKILL_DIR) -> "Skill":
        try:
            instructions = (directory / "SKILL.md").read_text(encoding="utf-8")
            world = (directory / "world.md").read_text(encoding="utf-8")
        except FileNotFoundError as error:
            raise ConfigurationError(f"Storyteller skill file is missing: {error.filename}") from error
        try:
            openings = json.loads((directory / "openings.json").read_text(encoding="utf-8"))
        except (FileNotFoundError, json.JSONDecodeError) as error:
            raise ConfigurationError(f"Storyteller openings are unreadable: {error}") from error
        if not isinstance(openings, dict) or not openings:
            raise ConfigurationError("Storyteller openings must be a non-empty object.")
        return cls(instructions=instructions, world=world, openings=openings)

    def opening(self, language: str) -> dict[str, str]:
        opening = self.openings.get(language) or self.openings.get("en")
        if not isinstance(opening, dict) or "text" not in opening:
            raise ConfigurationError("Storyteller opening is malformed.")
        return {"title": str(opening.get("title", "")), "text": str(opening["text"])}

    def system_prompt(self, phase: str) -> str:
        return f"{self.instructions}\n\n---\n\n{self.world}\n\n---\n\n{phase}"


class Storyteller:
    """Judges one player input, then narrates it, in two separate model calls."""

    def __init__(self, model: ChatModel | None = None, skill: Skill | None = None) -> None:
        self.model = model or ChatModel()
        self.skill = skill or Skill.load()

    @property
    def configured(self) -> bool:
        return self.model.configured

    def opening(self, language: str) -> dict[str, str]:
        return self.skill.opening(language)

    def resolve(
        self,
        state: StoryState,
        input_type: InputType,
        text: str,
    ) -> tuple[Ruling, Narration]:
        context = state.to_agent_context(input_type, text)
        ruling = self.rule(context)
        narration = self.narrate(context, ruling)
        return ruling, narration

    def rule(self, context: dict[str, Any]) -> Ruling:
        payload = self.model.complete_json(
            self.skill.system_prompt(RULING_PHASE),
            "Turn input:\n" + json.dumps(context, ensure_ascii=False),
            max_tokens=700,
            temperature=0.2,
        )
        try:
            return Ruling.from_dict(payload)
        except RulingError as error:
            raise RulingError(f"Storyteller returned an unusable ruling: {error}") from error

    def narrate(self, context: dict[str, Any], ruling: Ruling) -> Narration:
        payload = self.model.complete_json(
            self.skill.system_prompt(NARRATION_PHASE),
            "Turn input with the final ruling:\n"
            + json.dumps(
                {**context, "ruling": ruling.to_dict()},
                ensure_ascii=False,
            ),
            max_tokens=800,
            temperature=0.8,
        )
        try:
            return Narration.from_dict(payload)
        except RulingError as error:
            raise RulingError(f"Storyteller returned an unusable narration: {error}") from error
