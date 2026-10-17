"""The Storyteller: prepare a tale, then judge, write and review each turn.

Four shared skills:

1. **understand** prepares a source-grounded story space; the writer renders its
   opening. Both results are cached beside the case, once per language and inputs.
2. **judge** decides what the player's line changes.
3. **write** turns that ruling into the visible passage.
4. **reader-review** checks content and creative direction before publication.

Preparation reviews the written opening. Turns allow one directed repair before
requiring a passing review, all against the same uncommitted pre-turn state.
"""

from __future__ import annotations

import json
from dataclasses import replace
from typing import Any

from backend.case import Case
from backend.graph import build_turn_graph, build_understanding_graph
from backend.model import ChatModel
from backend.review import MAX_REVISIONS, Review
from backend.space import ContractError, Fact
from backend.session import (
    InputType, Narration, Ruling, RulingError, StoryState, merge_facts,
    validate_ruling, writer_context,
)
from backend.understanding import (
    Understanding,
    UnderstandingCache,
    UnderstandingError,
    source_digest,
)

# How a session got its understanding: the model just ran, or the case was reused.
UNDERSTANDING_DERIVED = "derived"
UNDERSTANDING_REUSED = "cached"

UNDERSTAND_TASK = (
    "Read the original story and return the case object only: player, canon, opening, space."
)
OPENING_TASK = "Render the opening seed for task opening. Return narration and hints only."
JUDGE_TASK = (
    "You are the judge for this turn. Decide what the action changes and return "
    "the ruling object only."
)
WRITER_TASK = (
    "You are the writer for this turn. The ruling is final; write the passage it "
    "authorises and return the narration object only."
)
REVIEW_TASK = (
    "Review the candidate's content quality and creative direction. "
    "Return the content review object only, not a playability assessment."
)


class Storyteller:
    """Prepares a case, then runs reviewed turns with bounded editorial repair."""

    def __init__(self, case: Case, model: ChatModel | None = None) -> None:
        self.case = case
        self.model = model or ChatModel()
        self.cache = UnderstandingCache(case.directory)
        self.understander = build_understanding_graph(self.understand, self.write_opening)
        self.graph = build_turn_graph(self.judge, self.write, self.review)
        self._understood: dict[str, tuple[str, Understanding]] = {}

    @property
    def configured(self) -> bool:
        return self.model.configured

    def understanding(self, language: str) -> Understanding:
        """Derive the case from the tale once per language, then reuse it."""
        return self.understanding_with_source(language)[0]

    def understanding_with_source(self, language: str) -> tuple[Understanding, str]:
        """The understanding, plus how this call got it.

        The second element is ``UNDERSTANDING_DERIVED`` when the understander
        just prepared and reviewed the opening, and ``UNDERSTANDING_REUSED``
        when an earlier derivation — in memory or beside the case — was reused.
        """
        source = self.case.source(language)
        # Include every preparation input, not credentials. A skill edit must take
        # effect even when the original tale has not changed.
        digest = source_digest(json.dumps({
            "source": source, "language": language,
            "understand": self.case.understand, "writer": self.case.writer,
            "reader_review": self.case.reader_review,
            "tasks": [UNDERSTAND_TASK, OPENING_TASK, REVIEW_TASK],
            "revision_limit": MAX_REVISIONS,
            "model": getattr(self.model, "model", type(self.model).__name__),
            "endpoint": getattr(self.model, "base_url", "stub"),
        }, ensure_ascii=False, sort_keys=True))
        if language in self._understood and self._understood[language][0] == digest:
            return self._understood[language][1], UNDERSTANDING_REUSED
        understanding = self.cache.read(language, digest)
        if understanding is None:
            result = self.understander.invoke(
                {"prompt": self.case.understand_prompt(language), "source": source,
                 "language": language}
            )
            understanding = result["understanding"]
            self.cache.write(language, digest, understanding)
            origin = UNDERSTANDING_DERIVED
        else:
            origin = UNDERSTANDING_REUSED
        try:
            understanding.validate_source(source)
        except UnderstandingError as error:
            raise RulingError(str(error)) from error
        self._understood[language] = (digest, understanding)
        return understanding, origin

    def opening(self, language: str) -> str:
        return self.understanding(language).opening

    def resolve(
        self,
        state: StoryState,
        input_type: InputType,
        text: str,
    ) -> tuple[Ruling, Narration]:
        understanding = self.understanding(state.language)
        result = self.graph.invoke(
            {
                "judge_prompt": self.case.judge_prompt(state.language, understanding),
                "writer_prompt": self.case.writer_prompt(state.language, understanding),
                "review_prompt": self.case.review_prompt(state.language, understanding),
                "context": state.to_agent_context(
                    self.case, understanding.player, input_type, text, understanding
                ),
            }
        )
        return replace(result["ruling"], review_history=result["review_history"]), result["narration"]

    def understand(self, prompt: str, source: str) -> Understanding:
        payload = self.model.complete_json(
            f"{prompt}\n\n---\n\n{UNDERSTAND_TASK}",
            "The original story:\n\n" + source,
            max_tokens=5500,
            temperature=0.4,
        )
        try:
            understanding = Understanding.from_dict(payload)
            understanding.validate_source(source)
            return understanding
        except UnderstandingError as error:
            raise RulingError(f"Understander returned an unusable case: {error}") from error

    def write_opening(self, understanding: Understanding, language: str) -> Understanding:
        context = {
            "task": "opening", "language": language,
            "opening_seed": understanding.opening,
            "visible_facts": [fact.to_dict() for fact in understanding.space.initial_facts
                              if "player" in fact.known_by],
        }
        for attempt in range(MAX_REVISIONS + 1):
            payload = self.model.complete_json(
                self.case.writer_prompt(language, understanding) + "\n\n" + OPENING_TASK,
                "Opening input:\n" + json.dumps(context, ensure_ascii=False),
                max_tokens=1200, temperature=0.8,
            )
            narration = Narration.from_dict(payload)
            report = self._review(self.case.review_prompt(language, understanding), {
                "task": "opening", "language": language,
                "opening_seed": understanding.opening,
                "initial_facts": [fact.to_dict() for fact in understanding.space.initial_facts],
                "candidate": {"narration": narration.text, "hints": list(narration.hints)},
            })
            if report.decision == "pass":
                return replace(understanding, opening=narration.text)
            if report.target == "judge":
                raise RulingError("Opening review requires correction of the prepared story space.")
            if attempt >= MAX_REVISIONS:
                raise RulingError("Opening content review still requests revision after the repair limit.")
            context["revision"] = {**report.writer_feedback(), "previous_candidate": {
                "narration": narration.text, "hints": list(narration.hints),
            }}
        raise AssertionError("Opening review loop did not terminate.")

    def judge(self, prompt: str, context: dict[str, Any]) -> Ruling:
        payload = self.model.complete_json(
            f"{prompt}\n\n---\n\n{JUDGE_TASK}",
            "Turn input:\n" + json.dumps(context, ensure_ascii=False),
            max_tokens=2400,
            temperature=0.2,
        )
        try:
            ruling = Ruling.from_dict(payload)
            validate_ruling(context, ruling)
            return ruling
        except RulingError as error:
            raise RulingError(f"Judge returned an unusable ruling: {error}") from error

    def write(self, prompt: str, context: dict[str, Any], ruling: Ruling) -> Narration:
        visible = writer_context(context, ruling)
        if "writer_feedback" in context:
            visible["revision"] = context["writer_feedback"]
        payload = self.model.complete_json(
            f"{prompt}\n\n---\n\n{WRITER_TASK}",
            "Turn input with the final ruling:\n"
            + json.dumps(visible, ensure_ascii=False),
            max_tokens=1200,
            temperature=0.8,
        )
        try:
            return Narration.from_dict(payload)
        except RulingError as error:
            raise RulingError(f"Writer returned an unusable narration: {error}") from error

    def _review(self, prompt: str, context: dict[str, Any]) -> Review:
        payload = self.model.complete_json(
            f"{prompt}\n\n---\n\n{REVIEW_TASK}",
            "Review input:\n" + json.dumps(context, ensure_ascii=False),
            max_tokens=1800, temperature=0.2,
        )
        try:
            return Review.from_dict(payload)
        except ContractError as error:
            raise RulingError(f"Reviewer returned an unusable report: {error}") from error

    def review(
        self, prompt: str, context: dict[str, Any], ruling: Ruling, narration: Narration,
    ) -> Review:
        projected = validate_ruling(context, ruling)
        if ruling.restart:
            projected = merge_facts(
                tuple(Fact.from_dict(item) for item in context["state"]["initial_facts"]),
                tuple(Fact.from_dict(item) for item in context["state"]["world_facts"]),
                ruling.expansions,
            )
        return self._review(prompt, {
            "task": "turn", "context": context, "ruling": ruling.to_dict(),
            "projected_facts": [fact.to_dict() for fact in projected],
            "candidate": {"narration": narration.text, "hints": list(narration.hints)},
        })
