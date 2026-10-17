"""What the agent derives from the original story, and where it is kept.

The case ships only the tale. An understanding — the player's role, the world
canon, the opening passage — is produced once per language, written next to the
case under `.generated/`, and reused until the source changes. Keeping it on disk
means it can be read, reviewed, and edited like any other authored file.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping

CACHE_DIRNAME = ".generated"
CACHE_VERSION = 1


class UnderstandingError(ValueError):
    """A derivation the engine cannot use."""


def source_digest(text: str) -> str:
    """A stable fingerprint of the tale, so an edited source regenerates."""
    return hashlib.sha256(text.strip().encode("utf-8")).hexdigest()


def _text(value: Any, label: str, *, limit: int) -> str:
    if not isinstance(value, str) or not value.strip():
        raise UnderstandingError(f"{label} must be a non-empty string.")
    return value.strip()[:limit]


@dataclass(frozen=True)
class Understanding:
    """The story as the agents understand it, in one language."""

    player: str
    canon: str
    opening: str

    @classmethod
    def from_dict(cls, payload: Any) -> "Understanding":
        if not isinstance(payload, Mapping):
            raise UnderstandingError("Understanding must be a JSON object.")
        return cls(
            player=_text(payload.get("player"), "player", limit=120),
            canon=_text(payload.get("canon"), "canon", limit=20000),
            opening=_text(payload.get("opening"), "opening", limit=4000),
        )

    def to_dict(self) -> dict[str, str]:
        return {"player": self.player, "canon": self.canon, "opening": self.opening}


class UnderstandingCache:
    """One understanding per case and language, stored beside the case."""

    def __init__(self, directory: Path) -> None:
        self.directory = Path(directory) / CACHE_DIRNAME

    def path(self, language: str) -> Path:
        return self.directory / f"understanding.{language}.json"

    def read(self, language: str, digest: str) -> Understanding | None:
        path = self.path(language)
        try:
            raw = json.loads(path.read_text(encoding="utf-8"))
        except (FileNotFoundError, json.JSONDecodeError):
            return None
        if not isinstance(raw, Mapping) or raw.get("version") != CACHE_VERSION:
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
        payload = {
            "version": CACHE_VERSION,
            "source_digest": digest,
            "understanding": understanding.to_dict(),
        }
        path.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        return path
