"""Shared, case-independent contracts for facts, events and writing briefs."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any, Mapping


class ContractError(ValueError):
    """Structured story data that cannot safely be used."""


def text(value: Any, label: str, limit: int = 2000) -> str:
    if not isinstance(value, str) or not value.strip() or len(value) > limit:
        raise ContractError(f"{label} must be non-empty text of at most {limit} characters.")
    return value.strip()


def array(value: Any, label: str, limit: int = 32) -> list:
    if not isinstance(value, list) or len(value) > limit:
        raise ContractError(f"{label} must be an array of at most {limit} items.")
    return value


def texts(value: Any, label: str, limit: int = 32) -> tuple[str, ...]:
    return tuple(text(item, label) for item in array(value, label, limit))


def obj(value: Any, label: str) -> Mapping:
    if not isinstance(value, Mapping):
        raise ContractError(f"{label} must be an object.")
    return value


def flag(value: Any, label: str) -> bool:
    if not isinstance(value, bool):
        raise ContractError(f"{label} must be true or false.")
    return value


def unique(items, label: str) -> tuple:
    result = tuple(items)
    if len({item.key for item in result}) != len(result):
        raise ContractError(f"{label} contains duplicate keys.")
    return result


@dataclass(frozen=True)
class Fact:
    key: str
    value: str
    known_by: tuple[str, ...] = ()

    @classmethod
    def from_dict(cls, value: Any) -> "Fact":
        value = obj(value, "fact")
        return cls(text(value.get("key"), "fact.key", 120),
                   text(value.get("value"), "fact.value"),
                   texts(value.get("known_by", []), "fact.known_by"))

    def to_dict(self) -> dict:
        return {"key": self.key, "value": self.value, "known_by": list(self.known_by)}


@dataclass(frozen=True)
class Event:
    text: str
    observers: tuple[str, ...]

    @classmethod
    def from_dict(cls, value: Any) -> "Event":
        value = obj(value, "event")
        return cls(text(value.get("text"), "event.text"),
                   texts(value.get("observers"), "event.observers"))

    def to_dict(self) -> dict:
        return {"text": self.text, "observers": list(self.observers)}


@dataclass(frozen=True)
class Observation:
    observer: str
    fact_key: str

    @classmethod
    def from_dict(cls, value: Any) -> "Observation":
        value = obj(value, "observation")
        return cls(text(value.get("observer"), "observation.observer", 120),
                   text(value.get("fact_key"), "observation.fact_key", 120))

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass(frozen=True)
class WritingBrief:
    focus: str
    mode: str
    visible: tuple[str, ...]
    uncertainty: tuple[str, ...]
    stop_before: str

    @classmethod
    def from_dict(cls, value: Any) -> "WritingBrief":
        value = obj(value, "brief")
        mode = value.get("mode")
        if mode not in ("direct", "dialogue", "action", "transition", "return", "ending"):
            raise ContractError("Unknown writing mode.")
        visible = texts(value.get("visible"), "brief.visible", 8)
        if not visible:
            raise ContractError("A brief needs at least one perceptible result.")
        return cls(text(value.get("focus"), "brief.focus"), mode, visible,
                   texts(value.get("uncertainty", []), "brief.uncertainty", 6),
                   text(value.get("stop_before"), "brief.stop_before"))

    def to_dict(self) -> dict:
        return {**asdict(self), "visible": list(self.visible),
                "uncertainty": list(self.uncertainty)}
