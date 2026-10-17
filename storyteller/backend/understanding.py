"""A source-grounded story space, with possibilities kept separate from facts."""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from backend.space import ContractError, Fact, array, obj, text, texts, unique

CACHE_DIRNAME = ".generated"
CACHE_VERSION = 2
_PARAGRAPH_BREAK = re.compile(r"\n\s*\n")


def quote_form(value: str) -> str:
    """Text as a reader compares it: wrapped lines rarely survive quotation.

    Whitespace inside a paragraph collapses to single spaces, so a quotation that
    rejoins a hard-wrapped line still counts as the same words; a paragraph break
    stays a break, so two separate passages cannot be spliced into one quotation.
    """
    paragraphs = (" ".join(block.split()) for block in _PARAGRAPH_BREAK.split(value.strip()))
    return "\n".join(paragraphs)


class UnderstandingError(ContractError):
    """A derivation the engine cannot use."""


def source_digest(source: str) -> str:
    return hashlib.sha256(source.strip().encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class SourceAnchor:
    fact: str
    quote: str

    @classmethod
    def from_dict(cls, value: Any) -> "SourceAnchor":
        value = obj(value, "source anchor")
        return cls(text(value.get("fact"), "anchor.fact"),
                   text(value.get("quote"), "anchor.quote"))

    def to_dict(self) -> dict:
        return {"fact": self.fact, "quote": self.quote}


@dataclass(frozen=True)
class StorySpace:
    anchors: tuple[SourceAnchor, ...]
    situation: str
    initial_facts: tuple[Fact, ...]
    fixed_keys: tuple[str, ...]
    possibilities: tuple[str, ...]
    adaptation: str
    style: str

    @classmethod
    def from_dict(cls, value: Any) -> "StorySpace":
        value = obj(value, "space")
        anchors = tuple(SourceAnchor.from_dict(item)
                        for item in array(value.get("anchors"), "space.anchors"))
        if not anchors:
            raise ContractError("A story space needs source evidence.")
        facts = unique((Fact.from_dict(item) for item in
                        array(value.get("initial_facts"), "space.initial_facts", 64)),
                       "space.initial_facts")
        fixed = texts(value.get("fixed_keys", []), "space.fixed_keys", 64)
        if set(fixed) - {fact.key for fact in facts}:
            raise ContractError("fixed_keys must refer to initial_facts.")
        return cls(anchors, text(value.get("situation"), "space.situation", 5000), facts,
                   fixed, texts(value.get("possibilities"), "space.possibilities"),
                   text(value.get("adaptation"), "space.adaptation", 5000),
                   text(value.get("style"), "space.style", 3000))

    def to_dict(self) -> dict:
        return {"anchors": [item.to_dict() for item in self.anchors],
                "situation": self.situation,
                "initial_facts": [item.to_dict() for item in self.initial_facts],
                "fixed_keys": list(self.fixed_keys), "possibilities": list(self.possibilities),
                "adaptation": self.adaptation, "style": self.style}


@dataclass(frozen=True)
class Understanding:
    player: str
    canon: str
    opening: str
    space: StorySpace

    @classmethod
    def from_dict(cls, payload: Any) -> "Understanding":
        try:
            payload = obj(payload, "Understanding")
            return cls(text(payload.get("player"), "player", 120),
                       text(payload.get("canon"), "canon", 20000),
                       text(payload.get("opening"), "opening", 4000),
                       StorySpace.from_dict(payload.get("space")))
        except ContractError as error:
            raise UnderstandingError(str(error)) from error

    def validate_source(self, source: str) -> None:
        tale = quote_form(source)
        for anchor in self.space.anchors:
            if quote_form(anchor.quote) not in tale:
                raise UnderstandingError("Source evidence must be an exact excerpt of this tale.")

    def to_dict(self) -> dict:
        return {"player": self.player, "canon": self.canon, "opening": self.opening,
                "space": self.space.to_dict()}


class UnderstandingCache:
    """Schema and derivation fingerprints invalidate incompatible cached readings."""

    def __init__(self, directory: Path) -> None:
        self.directory = Path(directory) / CACHE_DIRNAME

    def path(self, language: str) -> Path:
        return self.directory / f"understanding.{language}.json"

    def read(self, language: str, digest: str) -> Understanding | None:
        try:
            raw = json.loads(self.path(language).read_text(encoding="utf-8"))
        except (FileNotFoundError, json.JSONDecodeError):
            return None
        if not isinstance(raw, dict) or raw.get("version") != CACHE_VERSION:
            return None
        if raw.get("source_digest") != digest:
            return None
        try:
            return Understanding.from_dict(raw.get("understanding"))
        except UnderstandingError:
            return None

    def write(self, language: str, digest: str, understanding: Understanding) -> Path:
        path = self.path(language)
        path.parent.mkdir(parents=True, exist_ok=True)
        payload = {"version": CACHE_VERSION, "source_digest": digest,
                   "understanding": understanding.to_dict()}
        path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        return path
