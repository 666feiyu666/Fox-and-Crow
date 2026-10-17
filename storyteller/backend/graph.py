"""The graphs: understanding the tale, then judging and writing each turn.

    understanding   START -> understand -> END
    turn            START -> judge -> write -> END

The understander runs once per case and language; its result is cached, so the
turn graph never pays for it. Both graphs are pure orchestration — they hold no
story knowledge and no rules.
"""

from __future__ import annotations

from typing import Any, Callable, TypedDict

from langgraph.graph import END, START, StateGraph

from backend.session import Narration, Ruling
from backend.understanding import Understanding

UnderstandFn = Callable[[str, str], Understanding]
JudgeFn = Callable[[str, dict[str, Any]], Ruling]
WriteFn = Callable[[str, dict[str, Any], Ruling], Narration]


class UnderstandingState(TypedDict, total=False):
    """What the understanding graph carries."""

    prompt: str
    source: str
    understanding: Understanding


class TurnState(TypedDict, total=False):
    """What the turn graph carries."""

    judge_prompt: str
    writer_prompt: str
    context: dict[str, Any]
    ruling: Ruling
    narration: Narration


def build_understanding_graph(understand: UnderstandFn):
    """Compile the single-node graph that derives the case from the tale."""

    def understand_node(state: UnderstandingState) -> dict[str, Any]:
        return {
            "understanding": understand(state["prompt"], state["source"])
        }

    graph = StateGraph(UnderstandingState)
    graph.add_node("understand", understand_node)
    graph.add_edge(START, "understand")
    graph.add_edge("understand", END)
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
