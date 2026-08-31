from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, Mapping

from .context import GenerationContext


PLOT_STAGE_ORDER = (
    "cause",
    "development",
    "turning_point",
    "climax",
    "resolution",
)
PLOT_STAGE_LABELS = {
    "cause": "起因",
    "development": "发展",
    "turning_point": "转折",
    "climax": "高潮",
    "resolution": "结局",
}
IDENTIFIER_PATTERN = re.compile(r"^[a-z][a-z0-9_\-]*$")


class ConfigError(ValueError):
    """Raised when a story or model configuration is invalid."""


def _require_mapping(value: Any, label: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise ConfigError(f"{label} must be an object.")
    return value


def _require_text(value: Any, label: str, *, allow_empty: bool = False) -> str:
    if not isinstance(value, str):
        raise ConfigError(f"{label} must be a string.")
    normalized = " ".join(value.split())
    if not normalized and not allow_empty:
        raise ConfigError(f"{label} must not be empty.")
    return normalized


def _identifier(value: Any, label: str) -> str:
    identifier = _require_text(value, label)
    if IDENTIFIER_PATTERN.fullmatch(identifier) is None:
        raise ConfigError(
            f"{label} must start with a lowercase letter and use letters, numbers, _ or -."
        )
    return identifier


def _text_tuple(value: Any, label: str) -> tuple[str, ...]:
    if value is None:
        return ()
    if not isinstance(value, list):
        raise ConfigError(f"{label} must be an array of strings.")
    return tuple(
        _require_text(item, f"{label}[{index}]")
        for index, item in enumerate(value)
    )


def _days(value: Any, label: str) -> tuple[int, ...]:
    if value is None:
        return ()
    if not isinstance(value, list):
        raise ConfigError(f"{label} must be an array of positive integers.")
    days: list[int] = []
    for index, day in enumerate(value):
        if isinstance(day, bool) or not isinstance(day, int) or day < 1:
            raise ConfigError(f"{label}[{index}] must be a positive integer.")
        days.append(day)
    if days and len(days) != 3:
        raise ConfigError(f"{label} must contain exactly three story days.")
    if len(days) != len(set(days)):
        raise ConfigError(f"{label} must not contain duplicate story days.")
    return tuple(days)


def _reject_unknown_keys(
    payload: Mapping[str, Any],
    allowed: set[str],
    label: str,
) -> None:
    unknown = sorted(set(payload) - allowed)
    if unknown:
        raise ConfigError(f"{label} contains unsupported fields: {', '.join(unknown)}.")


@dataclass(frozen=True)
class PlotStageConfig:
    """One of the five sections; a configured section always targets three days."""

    purpose: str = ""
    days: tuple[int, ...] = ()
    requirements: tuple[str, ...] = ()

    @property
    def configured(self) -> bool:
        return bool(self.days)

    @classmethod
    def from_dict(cls, value: Any, label: str) -> PlotStageConfig:
        payload = _require_mapping(value, label)
        _reject_unknown_keys(payload, {"purpose", "days", "requirements"}, label)
        days = _days(payload.get("days"), f"{label}.days")
        purpose = _require_text(
            payload.get("purpose", ""),
            f"{label}.purpose",
            allow_empty=True,
        )
        requirements = _text_tuple(
            payload.get("requirements"), f"{label}.requirements"
        )
        if days and not purpose:
            raise ConfigError(f"{label}.purpose is required when the section is configured.")
        if not days and (purpose or requirements):
            raise ConfigError(
                f"{label}.days must be configured before purpose or requirements."
            )
        return cls(purpose=purpose, days=days, requirements=requirements)

    def to_dict(self) -> dict[str, object]:
        return {
            "purpose": self.purpose,
            "days": list(self.days),
            "requirements": list(self.requirements),
        }


@dataclass(frozen=True)
class PlotStructureConfig:
    cause: PlotStageConfig
    development: PlotStageConfig
    turning_point: PlotStageConfig
    climax: PlotStageConfig
    resolution: PlotStageConfig
    constraints: tuple[str, ...] = ()

    @classmethod
    def from_dict(cls, value: Any) -> PlotStructureConfig:
        payload = _require_mapping(value, "plot structure")
        _reject_unknown_keys(
            payload,
            {*PLOT_STAGE_ORDER, "constraints"},
            "plot structure",
        )
        missing = [stage for stage in PLOT_STAGE_ORDER if stage not in payload]
        if missing:
            raise ConfigError(
                "plot structure is missing stages: " + ", ".join(missing) + "."
            )
        stages = {
            stage_name: PlotStageConfig.from_dict(
                payload[stage_name], f"plot structure.{stage_name}"
            )
            for stage_name in PLOT_STAGE_ORDER
        }
        configured = [stages[name].configured for name in PLOT_STAGE_ORDER]
        if True in configured:
            final_configured = max(index for index, ready in enumerate(configured) if ready)
            if not all(configured[: final_configured + 1]):
                raise ConfigError(
                    "plot structure sections must be configured in narrative order."
                )
        return cls(
            cause=stages["cause"],
            development=stages["development"],
            turning_point=stages["turning_point"],
            climax=stages["climax"],
            resolution=stages["resolution"],
            constraints=_text_tuple(
                payload.get("constraints"), "plot structure.constraints"
            ),
        )

    def stage(self, name: str) -> PlotStageConfig:
        if name not in PLOT_STAGE_ORDER:
            raise ConfigError(f"Unsupported plot stage: {name}.")
        return getattr(self, name)

    def generation_plan(self) -> tuple[str, ...]:
        return tuple(
            stage_name
            for stage_name in PLOT_STAGE_ORDER
            if self.stage(stage_name).configured
        )

    def to_dict(self) -> dict[str, object]:
        return {
            stage_name: self.stage(stage_name).to_dict()
            for stage_name in PLOT_STAGE_ORDER
        } | {"constraints": list(self.constraints)}


@dataclass(frozen=True)
class CharacterConfig:
    id: str
    name: str
    role: str
    traits: tuple[str, ...] = ()
    goals: tuple[str, ...] = ()
    beliefs: tuple[str, ...] = ()
    knowledge: tuple[str, ...] = ()
    relationships: tuple[str, ...] = ()
    constraints: tuple[str, ...] = ()

    @classmethod
    def from_dict(cls, value: Any) -> CharacterConfig:
        payload = _require_mapping(value, "character")
        _reject_unknown_keys(
            payload,
            {
                "id",
                "name",
                "role",
                "traits",
                "goals",
                "beliefs",
                "knowledge",
                "relationships",
                "constraints",
            },
            "character",
        )
        return cls(
            id=_identifier(payload.get("id"), "character.id"),
            name=_require_text(payload.get("name"), "character.name"),
            role=_require_text(
                payload.get("role", ""),
                "character.role",
                allow_empty=True,
            ),
            traits=_text_tuple(payload.get("traits"), "character.traits"),
            goals=_text_tuple(payload.get("goals"), "character.goals"),
            beliefs=_text_tuple(payload.get("beliefs"), "character.beliefs"),
            knowledge=_text_tuple(payload.get("knowledge"), "character.knowledge"),
            relationships=_text_tuple(
                payload.get("relationships"), "character.relationships"
            ),
            constraints=_text_tuple(payload.get("constraints"), "character.constraints"),
        )

    def to_dict(self) -> dict[str, object]:
        return {
            "id": self.id,
            "name": self.name,
            "role": self.role,
            "traits": list(self.traits),
            "goals": list(self.goals),
            "beliefs": list(self.beliefs),
            "knowledge": list(self.knowledge),
            "relationships": list(self.relationships),
            "constraints": list(self.constraints),
        }


@dataclass(frozen=True)
class WorldEntityConfig:
    id: str
    name: str
    description: str
    properties: tuple[str, ...] = ()

    @classmethod
    def from_dict(cls, value: Any, label: str) -> WorldEntityConfig:
        payload = _require_mapping(value, label)
        _reject_unknown_keys(payload, {"id", "name", "description", "properties"}, label)
        return cls(
            id=_identifier(payload.get("id"), f"{label}.id"),
            name=_require_text(payload.get("name"), f"{label}.name"),
            description=_require_text(payload.get("description"), f"{label}.description"),
            properties=_text_tuple(payload.get("properties"), f"{label}.properties"),
        )

    def to_dict(self) -> dict[str, object]:
        return {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "properties": list(self.properties),
        }


def _entity_tuple(value: Any, label: str) -> tuple[WorldEntityConfig, ...]:
    if value is None:
        return ()
    if not isinstance(value, list):
        raise ConfigError(f"{label} must be an array.")
    return tuple(WorldEntityConfig.from_dict(item, label) for item in value)


@dataclass(frozen=True)
class StoryWorldConfig:
    characters: tuple[CharacterConfig, ...]
    locations: tuple[WorldEntityConfig, ...] = ()
    items: tuple[WorldEntityConfig, ...] = ()
    obstacles: tuple[WorldEntityConfig, ...] = ()
    facts: tuple[str, ...] = ()
    rules: tuple[str, ...] = ()
    initial_state: tuple[str, ...] = ()
    reset_rules: tuple[str, ...] = ()
    persistence_rules: tuple[str, ...] = ()

    @classmethod
    def from_dict(cls, value: Any) -> StoryWorldConfig:
        payload = _require_mapping(value, "story world")
        _reject_unknown_keys(
            payload,
            {
                "characters",
                "locations",
                "items",
                "obstacles",
                "facts",
                "rules",
                "initial_state",
                "reset_rules",
                "persistence_rules",
            },
            "story world",
        )
        raw_characters = payload.get("characters")
        if not isinstance(raw_characters, list) or not raw_characters:
            raise ConfigError("story world.characters must contain at least one character.")
        characters = tuple(CharacterConfig.from_dict(item) for item in raw_characters)
        identifiers = [character.id for character in characters]
        if len(identifiers) != len(set(identifiers)):
            raise ConfigError("story world character IDs must be unique.")
        return cls(
            characters=characters,
            locations=_entity_tuple(payload.get("locations"), "story world.locations"),
            items=_entity_tuple(payload.get("items"), "story world.items"),
            obstacles=_entity_tuple(payload.get("obstacles"), "story world.obstacles"),
            facts=_text_tuple(payload.get("facts"), "story world.facts"),
            rules=_text_tuple(payload.get("rules"), "story world.rules"),
            initial_state=_text_tuple(
                payload.get("initial_state"), "story world.initial_state"
            ),
            reset_rules=_text_tuple(
                payload.get("reset_rules"), "story world.reset_rules"
            ),
            persistence_rules=_text_tuple(
                payload.get("persistence_rules"), "story world.persistence_rules"
            ),
        )

    def to_dict(self) -> dict[str, object]:
        return {
            "characters": [character.to_dict() for character in self.characters],
            "locations": [entity.to_dict() for entity in self.locations],
            "items": [entity.to_dict() for entity in self.items],
            "obstacles": [entity.to_dict() for entity in self.obstacles],
            "facts": list(self.facts),
            "rules": list(self.rules),
            "initial_state": list(self.initial_state),
            "reset_rules": list(self.reset_rules),
            "persistence_rules": list(self.persistence_rules),
        }


@dataclass(frozen=True)
class NarrativeConstraintsConfig:
    cast_and_subplots: tuple[str, ...] = ()
    plot_and_pacing: tuple[str, ...] = ()
    time_loop: tuple[str, ...] = ()
    viewpoint_and_information: tuple[str, ...] = ()
    character_and_relationships: tuple[str, ...] = ()
    prose_and_dialogue: tuple[str, ...] = ()
    continuity_and_resolution: tuple[str, ...] = ()

    @classmethod
    def from_dict(cls, value: Any) -> NarrativeConstraintsConfig:
        payload = _require_mapping(value, "narrative constraints")
        fields = {
            "cast_and_subplots",
            "plot_and_pacing",
            "time_loop",
            "viewpoint_and_information",
            "character_and_relationships",
            "prose_and_dialogue",
            "continuity_and_resolution",
        }
        _reject_unknown_keys(payload, fields, "narrative constraints")
        return cls(
            **{
                field: _text_tuple(
                    payload.get(field), f"narrative constraints.{field}"
                )
                for field in fields
            }
        )

    def to_dict(self) -> dict[str, object]:
        return {
            "cast_and_subplots": list(self.cast_and_subplots),
            "plot_and_pacing": list(self.plot_and_pacing),
            "time_loop": list(self.time_loop),
            "viewpoint_and_information": list(self.viewpoint_and_information),
            "character_and_relationships": list(self.character_and_relationships),
            "prose_and_dialogue": list(self.prose_and_dialogue),
            "continuity_and_resolution": list(self.continuity_and_resolution),
        }


@dataclass(frozen=True)
class DiscourseConfig:
    language: str
    style: str
    length: str
    format: str
    point_of_view: str
    tense: str
    constraints: tuple[str, ...] = ()

    @classmethod
    def from_dict(cls, value: Any) -> DiscourseConfig:
        payload = _require_mapping(value, "discourse specification")
        _reject_unknown_keys(
            payload,
            {
                "language",
                "style",
                "length",
                "format",
                "point_of_view",
                "tense",
                "constraints",
            },
            "discourse specification",
        )
        return cls(
            language=_require_text(
                payload.get("language", ""),
                "discourse specification.language",
                allow_empty=True,
            ),
            style=_require_text(
                payload.get("style", ""),
                "discourse specification.style",
                allow_empty=True,
            ),
            length=_require_text(
                payload.get("length", ""),
                "discourse specification.length",
                allow_empty=True,
            ),
            format=_require_text(
                payload.get("format", ""),
                "discourse specification.format",
                allow_empty=True,
            ),
            point_of_view=_require_text(
                payload.get("point_of_view", ""),
                "discourse specification.point_of_view",
                allow_empty=True,
            ),
            tense=_require_text(
                payload.get("tense", ""),
                "discourse specification.tense",
                allow_empty=True,
            ),
            constraints=_text_tuple(
                payload.get("constraints"), "discourse specification.constraints"
            ),
        )

    def to_dict(self) -> dict[str, object]:
        return {
            "language": self.language,
            "style": self.style,
            "length": self.length,
            "format": self.format,
            "point_of_view": self.point_of_view,
            "tense": self.tense,
            "constraints": list(self.constraints),
        }


@dataclass(frozen=True)
class StoryConfig:
    title: str
    premise: str
    plot_structure: PlotStructureConfig
    story_world: StoryWorldConfig
    generation_context: GenerationContext
    narrative_constraints: NarrativeConstraintsConfig
    discourse: DiscourseConfig

    @classmethod
    def from_dict(cls, value: Any) -> StoryConfig:
        payload = _require_mapping(value, "story configuration")
        _reject_unknown_keys(
            payload,
            {
                "title",
                "premise",
                "plot_structure",
                "story_world",
                "generation_context",
                "narrative_constraints",
                "discourse",
            },
            "story configuration",
        )
        return cls(
            title=_require_text(
                payload.get("title", ""),
                "story configuration.title",
                allow_empty=True,
            ),
            premise=_require_text(
                payload.get("premise", ""),
                "story configuration.premise",
                allow_empty=True,
            ),
            plot_structure=PlotStructureConfig.from_dict(payload.get("plot_structure")),
            story_world=StoryWorldConfig.from_dict(payload.get("story_world")),
            generation_context=GenerationContext.from_dict(
                payload.get("generation_context", {})
            ),
            narrative_constraints=NarrativeConstraintsConfig.from_dict(
                payload.get("narrative_constraints")
            ),
            discourse=DiscourseConfig.from_dict(payload.get("discourse")),
        )

    def to_dict(self) -> dict[str, object]:
        return {
            "title": self.title,
            "premise": self.premise,
            "plot_structure": self.plot_structure.to_dict(),
            "story_world": self.story_world.to_dict(),
            "generation_context": self.generation_context.to_dict(),
            "narrative_constraints": self.narrative_constraints.to_dict(),
            "discourse": self.discourse.to_dict(),
        }


@dataclass(frozen=True)
class ModelConfig:
    model: str = "deepseek-chat"
    temperature: float = 0.7
    max_tokens: int = 3600
    timeout: float = 90.0
    max_retries: int = 2

    def __post_init__(self) -> None:
        if not self.model.strip():
            raise ConfigError("model must not be empty.")
        if isinstance(self.temperature, bool) or not isinstance(
            self.temperature, (int, float)
        ):
            raise ConfigError("temperature must be a number.")
        if not 0 <= float(self.temperature) <= 2:
            raise ConfigError("temperature must be between 0 and 2.")
        if isinstance(self.max_tokens, bool) or not isinstance(self.max_tokens, int):
            raise ConfigError("max_tokens must be an integer.")
        if self.max_tokens < 1:
            raise ConfigError("max_tokens must be positive.")
        if self.timeout <= 0:
            raise ConfigError("timeout must be positive.")
        if isinstance(self.max_retries, bool) or not isinstance(self.max_retries, int):
            raise ConfigError("max_retries must be an integer.")
        if self.max_retries < 0:
            raise ConfigError("max_retries must not be negative.")

    def to_dict(self) -> dict[str, object]:
        return {
            "model": self.model,
            "temperature": float(self.temperature),
            "max_tokens": self.max_tokens,
            "timeout": float(self.timeout),
            "max_retries": self.max_retries,
        }
