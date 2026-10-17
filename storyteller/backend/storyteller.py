"""The Storyteller: understanding the tale, then two agents per turn.

Three agents, three skills, one direction:

1. **understand** reads the original story once and derives the case from it —
   the player's role, the canon, and the opening passage. The result is cached
   beside the case, so it is paid for once per language.
2. **judge** decides what the player's line changes.
3. **write** turns that ruling into the visible passage.

The first step runs as its own LangGraph; the last two run as the turn graph.
"""

from __future__ import annotations

import json
from typing import Any

from backend.case import Case
from backend.graph import build_turn_graph, build_understanding_graph
from backend.model import ChatModel
from backend.session import InputType, Narration, Ruling, RulingError, StoryState
from backend.understanding import (
    Understanding,
    UnderstandingCache,
    UnderstandingError,
    source_digest,
)

UNDERSTAND_TASK = (
    "Read the original story and return the case object only: player, canon, opening."
)
JUDGE_TASK = (
    "You are the judge for this turn. Decide what the action changes and return "
    "the ruling object only."
)
WRITER_TASK = (
    "You are the writer for this turn. The ruling is final; write the passage it "
    "authorises and return the narration object only."
)


class Storyteller:
    """Derives the case from the tale, then runs turns through judge and write."""

    def __init__(self, case: Case, model: ChatModel | None = None) -> None:
        self.case = case
        self.model = model or ChatModel()
        self.cache = UnderstandingCache(case.directory)
        self.understander = build_understanding_graph(self.understand)
        self.graph = build_turn_graph(self.judge, self.write)
        self._understood: dict[str, Understanding] = {}

    @property
    def configured(self) -> bool:
        return self.model.configured

    def understanding(self, language: str) -> Understanding:
        """Derive the case from the tale once per language, then reuse it."""
        if language in self._understood:
            return self._understood[language]
        source = self.case.source(language)
        digest = source_digest(source)
        understanding = self.cache.read(language, digest)
        if understanding is None:
            result = self.understander.invoke(
                {"prompt": self.case.understand_prompt(language), "source": source}
            )
            understanding = result["understanding"]
            self.cache.write(language, digest, understanding)
        self._understood[language] = understanding
        return understanding

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
                "context": state.to_agent_context(
                    self.case, understanding.player, input_type, text
                ),
            }
        )
        return result["ruling"], result["narration"]

    def understand(self, prompt: str, source: str) -> Understanding:
        payload = self.model.complete_json(
            f"{prompt}\n\n---\n\n{UNDERSTAND_TASK}",
            "The original story:\n\n" + source,
            max_tokens=3000,
            temperature=0.4,
        )
        try:
            return Understanding.from_dict(payload)
        except UnderstandingError as error:
            raise RulingError(f"Understander returned an unusable case: {error}") from error

    def judge(self, prompt: str, context: dict[str, Any]) -> Ruling:
        payload = self.model.complete_json(
            f"{prompt}\n\n---\n\n{JUDGE_TASK}",
            "Turn input:\n" + json.dumps(context, ensure_ascii=False),
            max_tokens=700,
            temperature=0.2,
        )
        try:
            return Ruling.from_dict(payload)
        except RulingError as error:
            raise RulingError(f"Judge returned an unusable ruling: {error}") from error

    def write(self, prompt: str, context: dict[str, Any], ruling: Ruling) -> Narration:
        payload = self.model.complete_json(
            f"{prompt}\n\n---\n\n{WRITER_TASK}",
            "Turn input with the final ruling:\n"
            + json.dumps({**context, "ruling": ruling.to_dict()}, ensure_ascii=False),
            max_tokens=900,
            temperature=0.8,
        )
        try:
            return Narration.from_dict(payload)
        except RulingError as error:
            raise RulingError(f"Writer returned an unusable narration: {error}") from error
