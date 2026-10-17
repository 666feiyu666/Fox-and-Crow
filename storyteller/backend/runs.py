"""Past runs on disk: a played story, kept so it can be read again or continued.

A run file holds the visible opening, the committed story state and the story
fingerprint the run was prepared with. Fingerprints matter: if the tale, the
skills, the task instructions or the model changed, the old run's world no longer
matches what the case would derive today, so the run refuses to continue instead
of silently drifting. Turn reviews are not stored; the visible text and the ruling
are.
"""

from __future__ import annotations

import json
import os
import re
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from backend.session import StoryState
from backend.space import ContractError, obj, text

RUNS_DIRNAME = ".runs"
RUN_VERSION = 1
RUN_ID_PATTERN = re.compile(r"^[0-9a-f]{32}$")


class RunError(ContractError):
    """A stored run that cannot be read, written or resumed."""


@dataclass(frozen=True)
class RunRecord:
    """One played story, as it sits on disk."""

    id: str
    case_id: str
    language: str
    opening: str
    digest: str
    created: float
    updated: float
    state: StoryState

    @classmethod
    def from_dict(cls, payload: Any) -> "RunRecord":
        try:
            payload = obj(payload, "run")
            if payload.get("version") != RUN_VERSION:
                raise RunError("This run file was written by another version.")
            language = payload.get("language")
            if language not in ("en", "zh"):
                raise RunError("run.language must be en or zh.")
            return cls(
                id=text(payload.get("id"), "run.id"),
                case_id=text(payload.get("case"), "run.case"),
                language=language,
                opening=text(payload.get("opening"), "run.opening", 8000),
                digest=text(payload.get("digest"), "run.digest", 200),
                created=float(payload.get("created", 0.0)),
                updated=float(payload.get("updated", 0.0)),
                state=StoryState.from_dict(payload.get("state")),
            )
        except (TypeError, ValueError) as error:
            raise RunError(f"Unreadable run file: {error}") from error

    def to_dict(self) -> dict:
        return {
            "version": RUN_VERSION,
            "id": self.id,
            "case": self.case_id,
            "language": self.language,
            "opening": self.opening,
            "digest": self.digest,
            "created": self.created,
            "updated": self.updated,
            "state": self.state.to_dict(),
        }


class RunStore:
    """One JSON file per run, written atomically so a crash cannot truncate it."""

    def __init__(self, directory: Path) -> None:
        self.directory = Path(directory)

    def path(self, run_id: str) -> Path:
        if not RUN_ID_PATTERN.match(run_id):
            raise RunError(f"Invalid run id: {run_id!r}.")
        return self.directory / f"{run_id}.json"

    def save(self, record: RunRecord) -> Path:
        path = self.path(record.id)
        self.directory.mkdir(parents=True, exist_ok=True)
        temporary = path.with_suffix(".tmp")
        temporary.write_text(
            json.dumps(record.to_dict(), ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        os.replace(temporary, path)
        return path

    def load(self, run_id: str) -> RunRecord | None:
        try:
            raw = json.loads(self.path(run_id).read_text(encoding="utf-8"))
        except FileNotFoundError:
            return None
        except json.JSONDecodeError as error:
            raise RunError(f"Run file is not valid JSON: {error}") from error
        return RunRecord.from_dict(raw)

    def read_all(self) -> list[RunRecord]:
        """Every readable run, newest first. A broken file is skipped, not fatal."""
        if not self.directory.is_dir():
            return []
        runs = []
        for path in self.directory.glob("*.json"):
            try:
                runs.append(RunRecord.from_dict(json.loads(path.read_text(encoding="utf-8"))))
            except (OSError, json.JSONDecodeError, RunError):
                continue
        return sorted(runs, key=lambda run: run.updated, reverse=True)

    def delete(self, run_id: str) -> None:
        try:
            self.path(run_id).unlink()
        except FileNotFoundError:
            pass

    @staticmethod
    def now() -> float:
        return time.time()
