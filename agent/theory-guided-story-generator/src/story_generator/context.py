from __future__ import annotations

from dataclasses import dataclass, field, replace
from typing import Any, Mapping


def _mapping(value: Any, label: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise ValueError(f"{label} must be an object.")
    return value


def _text(value: Any, label: str, *, allow_empty: bool = False) -> str:
    if not isinstance(value, str):
        raise ValueError(f"{label} must be a string.")
    normalized = " ".join(value.split())
    if not normalized and not allow_empty:
        raise ValueError(f"{label} must not be empty.")
    return normalized


def _texts(value: Any, label: str) -> tuple[str, ...]:
    if value is None:
        return ()
    if not isinstance(value, list):
        raise ValueError(f"{label} must be an array of strings.")
    return tuple(_text(item, f"{label}[{index}]") for index, item in enumerate(value))


def _days(value: Any, label: str) -> tuple[int, ...]:
    if value is None:
        return ()
    if not isinstance(value, list):
        raise ValueError(f"{label} must be an array of positive integers.")
    days: list[int] = []
    for index, day in enumerate(value):
        if isinstance(day, bool) or not isinstance(day, int) or day < 1:
            raise ValueError(f"{label}[{index}] must be a positive integer.")
        days.append(day)
    return tuple(days)


def _text_map(value: Any, label: str) -> dict[str, tuple[str, ...]]:
    if value is None:
        return {}
    payload = _mapping(value, label)
    return {
        str(key): _texts(items, f"{label}.{key}")
        for key, items in payload.items()
    }


def _unique(*groups: tuple[str, ...]) -> tuple[str, ...]:
    return tuple(dict.fromkeys(item for group in groups for item in group))


def _merge_text_maps(
    before: Mapping[str, tuple[str, ...]],
    additions: Mapping[str, tuple[str, ...]],
) -> dict[str, tuple[str, ...]]:
    keys = set(before) | set(additions)
    return {
        key: _unique(before.get(key, ()), additions.get(key, ()))
        for key in keys
    }


@dataclass(frozen=True)
class GenerationPosition:
    sequence_index: int = 0
    plot_stage: str = ""
    section_label: str = ""

    @classmethod
    def from_dict(cls, value: Any) -> GenerationPosition:
        payload = _mapping(value, "generation position")
        sequence_index = payload.get("sequence_index", 0)
        if (
            isinstance(sequence_index, bool)
            or not isinstance(sequence_index, int)
            or sequence_index < 0
        ):
            raise ValueError(
                "generation position.sequence_index must be a non-negative integer."
            )
        return cls(
            sequence_index=sequence_index,
            plot_stage=_text(
                payload.get("plot_stage", ""),
                "generation position.plot_stage",
                allow_empty=True,
            ),
            section_label=_text(
                payload.get("section_label", ""),
                "generation position.section_label",
                allow_empty=True,
            ),
        )

    def to_dict(self) -> dict[str, object]:
        return {
            "sequence_index": self.sequence_index,
            "plot_stage": self.plot_stage,
            "section_label": self.section_label,
        }


@dataclass(frozen=True)
class GeneratedSection:
    label: str
    text: str
    plot_stage: str
    days: tuple[int, ...]

    @classmethod
    def from_dict(cls, value: Any) -> GeneratedSection:
        payload = _mapping(value, "generated section")
        return cls(
            label=_text(payload.get("label"), "generated section.label"),
            text=_text(payload.get("text"), "generated section.text"),
            plot_stage=_text(
                payload.get("plot_stage"), "generated section.plot_stage"
            ),
            days=_days(payload.get("days"), "generated section.days"),
        )

    def to_dict(self) -> dict[str, object]:
        return {
            "label": self.label,
            "days": list(self.days),
            "plot_stage": self.plot_stage,
            "text": self.text,
        }


@dataclass(frozen=True)
class GenerationContext:
    generated_sections: tuple[GeneratedSection, ...] = ()
    established_facts: tuple[str, ...] = ()
    unresolved_threads: tuple[str, ...] = ()
    character_knowledge: Mapping[str, tuple[str, ...]] = field(default_factory=dict)
    character_beliefs: Mapping[str, tuple[str, ...]] = field(default_factory=dict)
    relationship_changes: tuple[str, ...] = ()
    attempted_actions: tuple[str, ...] = ()
    outcomes: tuple[str, ...] = ()
    current_position: GenerationPosition = field(default_factory=GenerationPosition)

    @classmethod
    def from_dict(cls, value: Any) -> GenerationContext:
        payload = _mapping(value, "generation context")
        raw_sections = payload.get("generated_sections", [])
        if not isinstance(raw_sections, list):
            raise ValueError("generation context.generated_sections must be an array.")
        return cls(
            generated_sections=tuple(
                GeneratedSection.from_dict(item) for item in raw_sections
            ),
            established_facts=_texts(
                payload.get("established_facts"),
                "generation context.established_facts",
            ),
            unresolved_threads=_texts(
                payload.get("unresolved_threads"),
                "generation context.unresolved_threads",
            ),
            character_knowledge=_text_map(
                payload.get("character_knowledge"),
                "generation context.character_knowledge",
            ),
            character_beliefs=_text_map(
                payload.get("character_beliefs"),
                "generation context.character_beliefs",
            ),
            relationship_changes=_texts(
                payload.get("relationship_changes"),
                "generation context.relationship_changes",
            ),
            attempted_actions=_texts(
                payload.get("attempted_actions"),
                "generation context.attempted_actions",
            ),
            outcomes=_texts(payload.get("outcomes"), "generation context.outcomes"),
            current_position=GenerationPosition.from_dict(
                payload.get("current_position", {})
            ),
        )

    def to_dict(self) -> dict[str, object]:
        return {
            "generated_sections": [
                section.to_dict() for section in self.generated_sections
            ],
            "established_facts": list(self.established_facts),
            "unresolved_threads": list(self.unresolved_threads),
            "character_knowledge": {
                key: list(values) for key, values in self.character_knowledge.items()
            },
            "character_beliefs": {
                key: list(values) for key, values in self.character_beliefs.items()
            },
            "relationship_changes": list(self.relationship_changes),
            "attempted_actions": list(self.attempted_actions),
            "outcomes": list(self.outcomes),
            "current_position": self.current_position.to_dict(),
        }

    def at_position(self, position: GenerationPosition) -> GenerationContext:
        return replace(self, current_position=position)


@dataclass(frozen=True)
class ContextUpdate:
    established_facts: tuple[str, ...] = ()
    unresolved_threads_add: tuple[str, ...] = ()
    unresolved_threads_resolve: tuple[str, ...] = ()
    character_knowledge: Mapping[str, tuple[str, ...]] = field(default_factory=dict)
    character_beliefs: Mapping[str, tuple[str, ...]] = field(default_factory=dict)
    relationship_changes: tuple[str, ...] = ()
    attempted_actions: tuple[str, ...] = ()
    outcomes: tuple[str, ...] = ()

    @classmethod
    def from_dict(cls, value: Any) -> ContextUpdate:
        payload = _mapping(value, "context update")
        return cls(
            established_facts=_texts(
                payload.get("established_facts"), "context update.established_facts"
            ),
            unresolved_threads_add=_texts(
                payload.get("unresolved_threads_add"),
                "context update.unresolved_threads_add",
            ),
            unresolved_threads_resolve=_texts(
                payload.get("unresolved_threads_resolve"),
                "context update.unresolved_threads_resolve",
            ),
            character_knowledge=_text_map(
                payload.get("character_knowledge"),
                "context update.character_knowledge",
            ),
            character_beliefs=_text_map(
                payload.get("character_beliefs"),
                "context update.character_beliefs",
            ),
            relationship_changes=_texts(
                payload.get("relationship_changes"),
                "context update.relationship_changes",
            ),
            attempted_actions=_texts(
                payload.get("attempted_actions"),
                "context update.attempted_actions",
            ),
            outcomes=_texts(payload.get("outcomes"), "context update.outcomes"),
        )

    def to_dict(self) -> dict[str, object]:
        return {
            "established_facts": list(self.established_facts),
            "unresolved_threads_add": list(self.unresolved_threads_add),
            "unresolved_threads_resolve": list(self.unresolved_threads_resolve),
            "character_knowledge": {
                key: list(values) for key, values in self.character_knowledge.items()
            },
            "character_beliefs": {
                key: list(values) for key, values in self.character_beliefs.items()
            },
            "relationship_changes": list(self.relationship_changes),
            "attempted_actions": list(self.attempted_actions),
            "outcomes": list(self.outcomes),
        }


def apply_context_update(
    context: GenerationContext,
    section: GeneratedSection,
    update: ContextUpdate,
    next_position: GenerationPosition,
) -> GenerationContext:
    resolved = set(update.unresolved_threads_resolve)
    remaining_threads = tuple(
        thread for thread in context.unresolved_threads if thread not in resolved
    )
    return GenerationContext(
        generated_sections=(*context.generated_sections, section),
        established_facts=_unique(context.established_facts, update.established_facts),
        unresolved_threads=_unique(remaining_threads, update.unresolved_threads_add),
        character_knowledge=_merge_text_maps(
            context.character_knowledge, update.character_knowledge
        ),
        character_beliefs=_merge_text_maps(
            context.character_beliefs, update.character_beliefs
        ),
        relationship_changes=_unique(
            context.relationship_changes, update.relationship_changes
        ),
        attempted_actions=_unique(context.attempted_actions, update.attempted_actions),
        outcomes=_unique(context.outcomes, update.outcomes),
        current_position=next_position,
    )
