"""The turn graph: judgement first, writing second, wired with LangGraph.

Two agents, two skills, one direction:

    START -> judge -> write -> END

The judge reads the world and the player's line and decides what changes. The
writer receives that ruling as final and turns it into the visible passage. The
graph is pure orchestration: it holds no story knowledge and no rules.
"""

from __future__ import annotations

from typing import Any, Callable, TypedDict

from langgraph.graph import END, START, StateGraph

from backend.session import Narration, Ruling

JudgeFn = Callable[[str, dict[str, Any]], Ruling]
WriteFn = Callable[[str, dict[str, Any], Ruling], Narration]


class TurnState(TypedDict, total=False):
    """What flows between the two nodes."""

    judge_prompt: str
    writer_prompt: str
    context: dict[str, Any]
    ruling: Ruling
    narration: Narration


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
