"""Case loading: the world, the opening, and the player of one story.

A case is data only — canon, an opening passage, and the character the player
plays, each written in every supported language. The engine adds judgement and a
page; it adds no rules of its own.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping

LANGUAGES = ("en", "zh")
ENGINE_SKILL = Path(__file__).resolve().parents[1] / "skills" / "storyteller" / "SKILL.md"


class CaseError(RuntimeError):
    """A case directory that the engine cannot play."""


def _text(value: Any, label: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise CaseError(f"{label} must be a non-empty string.")
    return value.strip()


def _by_language(value: Any, label: str) -> dict[str, str]:
    if not isinstance(value, Mapping):
        raise CaseError(f"{label} must be an object of language to text.")
    parsed = {
        language: _text(text, f"{label}.{language}")
        for language, text in value.items()
        if language in LANGUAGES
    }
    missing = [language for language in LANGUAGES if language not in parsed]
    if missing:
        raise CaseError(f"{label} is missing: {', '.join(missing)}.")
    return parsed


def _document(directory: Path, kind: str, language: str) -> str:
    path = directory / f"{kind}.{language}.md"
    try:
        text = path.read_text(encoding="utf-8").strip()
    except FileNotFoundError as error:
        raise CaseError(f"Case file is missing: {path}") from error
    if not text:
        raise CaseError(f"Case file is empty: {path}")
    return text


@dataclass(frozen=True)
class Case:
    id: str
    titles: Mapping[str, str]
    players: Mapping[str, str]
    worlds: Mapping[str, str]
    openings: Mapping[str, str]
    instructions: str

    @classmethod
    def load(cls, directory: Path, skill: Path = ENGINE_SKILL) -> "Case":
        directory = Path(directory)
        try:
            raw = json.loads((directory / "case.json").read_text(encoding="utf-8"))
            instructions = skill.read_text(encoding="utf-8")
        except FileNotFoundError as error:
            raise CaseError(f"Case file is missing: {error.filename}") from error
        except json.JSONDecodeError as error:
            raise CaseError(f"case.json is invalid in {directory}: {error}") from error
        if not isinstance(raw, Mapping):
            raise CaseError("case.json must contain a JSON object.")

        return cls(
            id=str(raw.get("id") or directory.name),
            titles=_by_language(raw.get("title"), "title"),
            players=_by_language(raw.get("player"), "player"),
            worlds={language: _document(directory, "world", language) for language in LANGUAGES},
            openings={language: _document(directory, "opening", language) for language in LANGUAGES},
            instructions=instructions,
        )

    def title(self, language: str) -> str:
        return self.titles.get(language) or self.titles["en"]

    def player(self, language: str) -> str:
        return self.players.get(language) or self.players["en"]

    def world(self, language: str) -> str:
        return self.worlds.get(language) or self.worlds["en"]

    def opening(self, language: str) -> str:
        return self.openings.get(language) or self.openings["en"]

    def system_prompt(self, language: str) -> str:
        brief = (
            f"The player plays {self.player(language)}.\n"
            f"The story language is {language}: write scene, facts, narration, and "
            f"hints in {language}, and keep every name as this world writes it."
        )
        return f"{self.instructions}\n\n---\n\n{brief}\n\n---\n\n{self.world(language)}"
