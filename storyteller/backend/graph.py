"""The graphs: understanding the tale, then judging and writing each turn.

    understanding   START -> understand -> write_opening -> END
    turn            START -> judge -> write -> review -> END

Preparation runs once per case, language and input fingerprint; its completed
result is cached. Both graphs are orchestration, without case-specific rules.
"""

from __future__ import annotations

from typing import Any, Callable, TypedDict

from langgraph.graph import END, START, StateGraph

from backend.review import MAX_REVISIONS, Review, ReviewRecord
from backend.session import Narration, Ruling, RulingError
from backend.understanding import Understanding

UnderstandFn = Callable[[str, str], Understanding]
OpeningFn = Callable[[Understanding, str], Understanding]
JudgeFn = Callable[[str, dict[str, Any]], Ruling]
WriteFn = Callable[[str, dict[str, Any], Ruling], Narration]
ReviewFn = Callable[[str, dict[str, Any], Ruling, Narration], Review]


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
    review_prompt: str
    context: dict[str, Any]
    ruling: Ruling
    narration: Narration
    feedback: Review
    revision_count: int
    review_history: tuple[ReviewRecord, ...]


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


def build_turn_graph(judge: JudgeFn, write: WriteFn, review: ReviewFn):
    """Review before publication, with one repair from the same pre-turn state."""

    def judge_node(state: TurnState) -> dict[str, Any]:
        context = dict(state["context"])
        if state.get("feedback") is not None:
            context["revision"] = {
                "previous_ruling": state["ruling"].to_dict(),
                "previous_candidate": {"narration": state["narration"].text,
                                       "hints": list(state["narration"].hints)},
                "review": state["feedback"].to_dict(),
            }
        return {"ruling": judge(state["judge_prompt"], context)}

    def write_node(state: TurnState) -> dict[str, Any]:
        context = dict(state["context"])
        feedback = state.get("feedback")
        if feedback is not None:
            context["writer_feedback"] = feedback.writer_feedback()
            if feedback.target == "writer":
                context["writer_feedback"]["previous_candidate"] = {
                    "narration": state["narration"].text,
                    "hints": list(state["narration"].hints),
                }
        return {
            "narration": write(
                state["writer_prompt"],
                context,
                state["ruling"],
            )
        }

    def review_node(state: TurnState) -> dict[str, Any]:
        report = review(state["review_prompt"], state["context"],
                        state["ruling"], state["narration"])
        revisions = state.get("revision_count", 0)
        if report.decision == "revise" and revisions >= MAX_REVISIONS:
            raise RulingError("Content review still requests revision after the repair limit.")
        record = ReviewRecord(report, state["ruling"].to_dict(),
                              state["narration"].text, state["narration"].hints)
        return {"feedback": report,
                "revision_count": revisions + (report.decision == "revise"),
                "review_history": (*state.get("review_history", ()), record)}

    def route_review(state: TurnState) -> str:
        return state["feedback"].target

    graph = StateGraph(TurnState)
    graph.add_node("judge", judge_node)
    graph.add_node("write", write_node)
    graph.add_node("review", review_node)
    graph.add_edge(START, "judge")
    graph.add_edge("judge", "write")
    graph.add_edge("write", "review")
    graph.add_conditional_edges("review", route_review,
                                {"none": END, "judge": "judge", "writer": "write"})
    return graph.compile()
