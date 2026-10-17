"""The Storyteller: one case, two agents per turn, wired as a LangGraph.

The judge decides what the player's line changes; the writer turns that ruling
into the visible passage. Each agent has its own skill file, and both receive the
case canon in the session language, so the story never changes language halfway
through.
"""

from __future__ import annotations

import json
from typing import Any

from backend.case import Case
from backend.graph import build_turn_graph
from backend.model import ChatModel
from backend.session import InputType, Narration, Ruling, RulingError, StoryState

JUDGE_TASK = (
    "You are the judge for this turn. Decide what the action changes and return "
    "the ruling object only."
)
WRITER_TASK = (
    "You are the writer for this turn. The ruling is final; write the passage it "
    "authorises and return the narration object only."
)


class Storyteller:
    """Runs one turn through the judge and the writer, in that order."""

    def __init__(self, case: Case, model: ChatModel | None = None) -> None:
        self.case = case
        self.model = model or ChatModel()
        self.graph = build_turn_graph(self.judge, self.write)

    @property
    def configured(self) -> bool:
        return self.model.configured

    def opening(self, language: str) -> str:
        return self.case.opening(language)

    def resolve(
        self,
        state: StoryState,
        input_type: InputType,
        text: str,
    ) -> tuple[Ruling, Narration]:
        result = self.graph.invoke(
            {
                "judge_prompt": self.case.judge_prompt(state.language),
                "writer_prompt": self.case.writer_prompt(state.language),
                "context": state.to_agent_context(self.case, input_type, text),
            }
        )
        return result["ruling"], result["narration"]

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

    def write(
        self, prompt: str, context: dict[str, Any], ruling: Ruling
    ) -> Narration:
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
