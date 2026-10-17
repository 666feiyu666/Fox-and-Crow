"""The graphs: understanding the tale, then judging and writing each turn.

    understanding   START -> understand -> write_opening -> END
    turn            START -> judge -> write -> END

Preparation runs once per case, language and input fingerprint; its completed
result is cached. Both graphs are orchestration, without case-specific rules.
"""

from __future__ import annotations

from typing import Any, Callable, TypedDict

from langgraph.graph import END, START, StateGraph

from backend.session import Narration, Ruling
from backend.understanding import Understanding

UnderstandFn = Callable[[str, str], Understanding]
OpeningFn = Callable[[Understanding, str], Understanding]
JudgeFn = Callable[[str, dict[str, Any]], Ruling]
WriteFn = Callable[[str, dict[str, Any], Ruling], Narration]


class UnderstandingState(TypedDict, total=False):
    """What the understanding graph carries."""

    prompt: str
    source: str
    language: str
    understanding: Understanding


class TurnState(TypedDict, total=False):
    """What the turn graph carries."""

    judge_prompt: str
    writer_prompt: str
    context: dict[str, Any]
    ruling: Ruling
    narration: Narration


def build_understanding_graph(understand: UnderstandFn, opening: OpeningFn | None = None):
    """Prepare the space, then render its opening with the same writer craft."""

    def understand_node(state: UnderstandingState) -> dict[str, Any]:
        return {
            "understanding": understand(state["prompt"], state["source"])
        }

    graph = StateGraph(UnderstandingState)
    graph.add_node("understand", understand_node)
    graph.add_edge(START, "understand")
    if opening is None:
        graph.add_edge("understand", END)
    else:
        def opening_node(state: UnderstandingState) -> dict[str, Any]:
            return {"understanding": opening(state["understanding"], state["language"])}

        graph.add_node("write_opening", opening_node)
        graph.add_edge("understand", "write_opening")
        graph.add_edge("write_opening", END)
    return graph.compile()


def build_turn_graph(judge: JudgeFn, write: WriteFn):
    """Compile the judge -> write graph around the two agent calls."""

    def judge_node(state: TurnState) -> dict[str, Any]:
        return {"ruling": judge(state["judge_prompt"], state["context"])}

    def write_node(state: TurnState) -> dict[str, Any]:
        return {
            "narration": write(
                state["writer_prompt"],
                state["context"],
                state["ruling"],
            )
        }

    graph = StateGraph(TurnState)
    graph.add_node("judge", judge_node)
    graph.add_node("write", write_node)
    graph.add_edge(START, "judge")
    graph.add_edge("judge", "write")
    graph.add_edge("write", END)
    return graph.compile()
