"""Content-review decisions and private records, shared by every case."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from backend.space import ContractError, array, flag, obj, text, texts

MAX_REVISIONS = 1
CATEGORIES = (
    "direction", "causality", "character", "continuity", "prose", "voice",
    "pacing", "clarity", "disclosure", "scope",
)


@dataclass(frozen=True)
class Finding:
    target: str
    blocking: bool
    category: str
    location: str
    evidence: str
    reason: str
    request: str

    @classmethod
    def from_dict(cls, value: Any) -> "Finding":
        value = obj(value, "finding")
        if value.get("target") not in ("judge", "writer"):
            raise ContractError("A finding must target judge or writer.")
        if value.get("category") not in CATEGORIES:
            raise ContractError("Unknown review category.")
        return cls(
            value["target"], flag(value.get("blocking"), "finding.blocking"),
            value["category"], text(value.get("location"), "finding.location", 200),
            text(value.get("evidence"), "finding.evidence"),
            text(value.get("reason"), "finding.reason"),
            text(value.get("request"), "finding.request"),
        )

    def to_dict(self) -> dict:
        return dict(vars(self))


@dataclass(frozen=True)
class Review:
    decision: str
    summary: str
    preserve: tuple[str, ...]
    findings: tuple[Finding, ...]

    @classmethod
    def from_dict(cls, value: Any) -> "Review":
        value = obj(value, "review")
        decision = value.get("decision")
        if decision not in ("pass", "revise"):
            raise ContractError("Review decision must be pass or revise.")
        findings = tuple(Finding.from_dict(item) for item in
                         array(value.get("findings"), "review.findings", 6))
        if (decision == "revise") != any(item.blocking for item in findings):
            raise ContractError("A revision decision must agree with blocking findings.")
        return cls(decision, text(value.get("summary"), "review.summary"),
                   texts(value.get("preserve", []), "review.preserve", 4), findings)

    @property
    def target(self) -> str:
        if self.decision == "pass":
            return "none"
        return "judge" if any(item.blocking and item.target == "judge"
                              for item in self.findings) else "writer"

    def to_dict(self) -> dict:
        return {"decision": self.decision, "summary": self.summary,
                "preserve": list(self.preserve),
                "findings": [item.to_dict() for item in self.findings]}

    def writer_feedback(self) -> dict:
        """Only actionable public requests, never the private report or its evidence."""
        return {
            "preserve": list(self.preserve),
            "requests": [{"category": item.category, "location": item.location,
                          "request": item.request} for item in self.findings
                         if item.target == "writer" and item.blocking],
        }


@dataclass(frozen=True)
class ReviewRecord:
    review: Review
    ruling: dict | None
    narration: str
    hints: tuple[str, ...]

    def to_dict(self) -> dict:
        return {"review": self.review.to_dict(), "ruling": self.ruling,
                "candidate": {"narration": self.narration, "hints": list(self.hints)}}
