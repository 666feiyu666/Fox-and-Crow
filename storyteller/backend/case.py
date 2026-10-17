"""Case loading: the original tale, its title, and the shared agent skills.

A case ships data only — the story it is built from, in every supported language,
and a title. What the player is, what the world is, and what they read first are
derived from that tale by the understander and cached beside the case.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping

from backend.understanding import Understanding

LANGUAGES = ("en", "zh")
STAGES = ("understand", "judge", "writer", "reader-review")
SKILLS_DIR = Path(__file__).resolve().parents[1] / "skills"


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


def _skill(skills: Path, stage: str) -> str:
    path = Path(skills) / stage / "SKILL.md"
    try:
        text = path.read_text(encoding="utf-8").strip()
    except FileNotFoundError as error:
        raise CaseError(f"Agent skill is missing: {path}") from error
    if not text:
        raise CaseError(f"Agent skill is empty: {path}")
    if stage == "writer":
        resource = Path(skills) / stage / "references" / "craft.md"
        try:
            text += "\n\n---\n\n" + resource.read_text(encoding="utf-8")
        except FileNotFoundError as error:
            raise CaseError(f"Writer craft resource is missing: {resource}") from error
    return text


@dataclass(frozen=True)
class Case:
    id: str
    directory: Path
    titles: Mapping[str, str]
    sources: Mapping[str, str]
    understand: str
    judge: str
    writer: str
    reader_review: str

    @classmethod
    def load(cls, directory: Path, skills: Path = SKILLS_DIR) -> "Case":
        directory = Path(directory)
        try:
            raw = json.loads((directory / "case.json").read_text(encoding="utf-8"))
        except FileNotFoundError as error:
            raise CaseError(f"Case file is missing: {error.filename}") from error
        except json.JSONDecodeError as error:
            raise CaseError(f"case.json is invalid in {directory}: {error}") from error
        if not isinstance(raw, Mapping):
            raise CaseError("case.json must contain a JSON object.")

        return cls(
            id=str(raw.get("id") or directory.name),
            directory=directory,
            titles=_by_language(raw.get("title"), "title"),
            sources={
                language: _document(directory, "source", language)
                for language in LANGUAGES
            },
            understand=_skill(skills, "understand"),
            judge=_skill(skills, "judge"),
            writer=_skill(skills, "writer"),
            reader_review=_skill(skills, "reader-review"),
        )

    def title(self, language: str) -> str:
        return self.titles.get(language) or self.titles["en"]

    def source(self, language: str) -> str:
        return self.sources.get(language) or self.sources["en"]

    def understand_prompt(self, language: str) -> str:
        brief = (
            f"The story language is {language}: write all prose fields in {language}, "
            f"and keep every name as the tale gives it. JSON keys and actor ids stay stable."
        )
        return (
            f"{self.understand}\n\n---\n\n{brief}\n\n---\n\n"
            f"# The original story\n\n{self.source(language)}"
        )

    def _stage_prompt(self, instructions: str, language: str, understanding: Understanding) -> str:
        brief = (
            f"The player plays {understanding.player}.\n"
            f"The story language is {language}: write everything in {language}, and "
            f"keep every name as this world writes it."
        )
        return f"{instructions}\n\n---\n\n{brief}\n\n---\n\n{understanding.canon}"

    def judge_prompt(self, language: str, understanding: Understanding) -> str:
        return (self._stage_prompt(self.judge, language, understanding)
                + "\n\n# Prepared story space\n"
                + json.dumps(understanding.space.to_dict(), ensure_ascii=False))

    def writer_prompt(self, language: str, understanding: Understanding) -> str:
        # Hidden canon, unresolved possibilities and NPC goals belong to judgement.
        return (f"{self.writer}\n\nThe player plays {understanding.player}.\n"
                f"The story language is {language}: write everything in {language}.\n"
                f"\n# Story voice\n{understanding.space.style}")

    def review_prompt(self, language: str, understanding: Understanding) -> str:
        return (self._stage_prompt(self.reader_review, language, understanding)
                + "\n\n# Prepared story space\n"
                + json.dumps(understanding.space.to_dict(), ensure_ascii=False))
