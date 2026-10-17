"""Case loading: the story data that one Storyteller instance plays.

A case owns the world canon, the opening scene, and the mechanics the runtime
keeps (clock, meters, ending condition). The engine — skill, session rules, HTTP
surface, page — is shared by every case.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping

ENGINE_SKILL_DIR = Path(__file__).resolve().parents[1] / "skills" / "storyteller"
LANGUAGES = frozenset({"en", "zh"})
MAX_TIME_COST = 3


class CaseError(RuntimeError):
    """A case directory that the engine cannot play."""


def _mapping(value: Any, label: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise CaseError(f"{label} must be an object.")
    return value


def _text(value: Any, label: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise CaseError(f"{label} must be a non-empty string.")
    return value


def _integer(value: Any, label: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise CaseError(f"{label} must be an integer.")
    return value


@dataclass(frozen=True)
class Meter:
    id: str
    start: int
    minimum: int
    maximum: int


@dataclass(frozen=True)
class Clock:
    units_per_day: int
    loops: bool
    reset_on_loop: tuple[str, ...]


@dataclass(frozen=True)
class EndingRule:
    min_turns: int
    requires: Mapping[str, int]


@dataclass(frozen=True)
class Case:
    id: str
    titles: Mapping[str, str]
    characters: Mapping[str, str]
    clock: Clock | None
    meters: tuple[Meter, ...]
    ending: EndingRule
    world: str
    openings: Mapping[str, str]
    instructions: str

    @classmethod
    def load(cls, directory: Path, skill_dir: Path = ENGINE_SKILL_DIR) -> "Case":
        directory = Path(directory)
        try:
            raw = json.loads((directory / "case.json").read_text(encoding="utf-8"))
            world = (directory / "world.md").read_text(encoding="utf-8")
            openings = json.loads((directory / "openings.json").read_text(encoding="utf-8"))
            instructions = (skill_dir / "SKILL.md").read_text(encoding="utf-8")
        except FileNotFoundError as error:
            raise CaseError(f"Case file is missing: {error.filename}") from error
        except json.JSONDecodeError as error:
            raise CaseError(f"Case JSON is invalid in {directory}: {error}") from error

        settings = _mapping(_mapping(raw, "case").get("storyteller"), "case.storyteller")
        meters = cls._meters(settings.get("meters"))
        known = {meter.id for meter in meters}
        return cls(
            id=str(raw.get("case_id", directory.name)),
            titles=cls._titles(settings.get("title")),
            characters=cls._characters(settings.get("player_character")),
            clock=cls._clock(settings.get("clock"), known),
            meters=meters,
            ending=cls._ending(settings.get("ending"), known),
            world=world,
            openings=cls._openings(openings),
            instructions=instructions,
        )

    @staticmethod
    def _titles(value: Any) -> Mapping[str, str]:
        titles = _mapping(value, "storyteller.title")
        parsed = {
            str(language): _text(title, f"storyteller.title.{language}")
            for language, title in titles.items()
            if language in LANGUAGES
        }
        if "en" not in parsed:
            raise CaseError("storyteller.title must provide an English title.")
        return parsed

    @staticmethod
    def _characters(value: Any) -> Mapping[str, str]:
        if isinstance(value, str):
            return {"en": _text(value, "storyteller.player_character")}
        names = _mapping(value, "storyteller.player_character")
        parsed = {
            str(language): _text(name, f"storyteller.player_character.{language}")
            for language, name in names.items()
            if language in LANGUAGES
        }
        if "en" not in parsed:
            raise CaseError("storyteller.player_character must provide English.")
        return parsed

    @staticmethod
    def _meters(value: Any) -> tuple[Meter, ...]:
        payload = _mapping(value, "storyteller.meters")
        meters: list[Meter] = []
        for meter_id, spec in payload.items():
            settings = _mapping(spec, f"storyteller.meters.{meter_id}")
            minimum = _integer(settings.get("min", -5), f"meters.{meter_id}.min")
            maximum = _integer(settings.get("max", 5), f"meters.{meter_id}.max")
            start = _integer(settings.get("start", 0), f"meters.{meter_id}.start")
            if minimum > maximum:
                raise CaseError(f"meters.{meter_id} has min above max.")
            if not minimum <= start <= maximum:
                raise CaseError(f"meters.{meter_id}.start is outside its range.")
            meters.append(Meter(id=str(meter_id), start=start, minimum=minimum, maximum=maximum))
        return tuple(meters)

    @staticmethod
    def _clock(value: Any, known: set[str]) -> Clock | None:
        if value is None:
            return None
        payload = _mapping(value, "storyteller.clock")
        units = _integer(payload.get("units_per_day", 6), "clock.units_per_day")
        if units < 1 or units > 24:
            raise CaseError("clock.units_per_day must be between 1 and 24.")
        loops = payload.get("loops", False)
        if not isinstance(loops, bool):
            raise CaseError("clock.loops must be a boolean.")
        reset = payload.get("reset_meters_on_loop", [])
        if not isinstance(reset, list) or any(not isinstance(item, str) for item in reset):
            raise CaseError("clock.reset_meters_on_loop must be an array of meter names.")
        unknown = sorted(set(reset) - known)
        if unknown:
            raise CaseError(f"clock resets unknown meters: {', '.join(unknown)}.")
        return Clock(units_per_day=units, loops=loops, reset_on_loop=tuple(reset))

    @staticmethod
    def _ending(value: Any, known: set[str]) -> EndingRule:
        payload = _mapping(value, "storyteller.ending")
        min_turns = _integer(payload.get("min_turns", 1), "ending.min_turns")
        if min_turns < 1:
            raise CaseError("ending.min_turns must be at least 1.")
        requires = _mapping(payload.get("requires", {}), "ending.requires")
        thresholds = {
            str(meter_id): _integer(threshold, f"ending.requires.{meter_id}")
            for meter_id, threshold in requires.items()
        }
        unknown = sorted(set(thresholds) - known)
        if unknown:
            raise CaseError(f"ending requires unknown meters: {', '.join(unknown)}.")
        return EndingRule(min_turns=min_turns, requires=thresholds)

    @staticmethod
    def _openings(value: Any) -> Mapping[str, str]:
        payload = _mapping(value, "openings")
        openings = {
            str(language): _text(
                _mapping(opening, f"openings.{language}").get("text"),
                f"openings.{language}.text",
            )
            for language, opening in payload.items()
            if language in LANGUAGES
        }
        if "en" not in openings:
            raise CaseError("openings.json must provide an English opening.")
        return openings

    def title(self, language: str) -> str:
        return self.titles.get(language) or self.titles["en"]

    def opening(self, language: str) -> str:
        return self.openings.get(language) or self.openings["en"]

    def character_name(self, language: str) -> str:
        return self.characters.get(language) or self.characters["en"]

    def meter(self, meter_id: str) -> Meter | None:
        return next((meter for meter in self.meters if meter.id == meter_id), None)

    def system_prompt(self, phase: str) -> str:
        return f"{self.instructions}\n\n---\n\n{self.world}\n\n---\n\n{phase}"
