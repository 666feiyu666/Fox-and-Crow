import unittest

from backend.graph import build_turn_graph, build_understanding_graph
from backend.review import Review
from backend.session import Narration, Ruling, RulingError
from backend.understanding import Understanding
from tests.fixtures import review_payload, ruling_payload, understanding_payload


def pass_review(prompt, context, ruling, narration):
    return Review.from_dict(review_payload())


class GraphTests(unittest.TestCase):
    def test_judge_runs_before_the_writer_and_hands_over_the_ruling(self):
        calls = []

        def judge(prompt, context):
            calls.append(("judge", prompt, context["action"]["text"]))
            return Ruling.from_dict(ruling_payload(outcome="failure"))

        def write(prompt, context, ruling):
            calls.append(("write", prompt, ruling.outcome))
            return Narration.from_dict({"narration": "She turns her back.", "hints": ["Wait."]})

        graph = build_turn_graph(judge, write, pass_review)
        result = graph.invoke(
            {
                "judge_prompt": "JUDGE-PROMPT",
                "writer_prompt": "WRITER-PROMPT",
                "review_prompt": "REVIEW-PROMPT",
                "context": {"action": {"type": "say", "text": "喂，乌鸦"}},
            }
        )

        self.assertEqual([call[0] for call in calls], ["judge", "write"])
        self.assertEqual(calls[0][2], "喂，乌鸦")
        self.assertEqual(calls[1][2], "failure")
        self.assertEqual(result["ruling"].outcome, "failure")
        self.assertEqual(result["narration"].text, "She turns her back.")
        self.assertEqual(result["review_history"][0].review.decision, "pass")

    def test_each_agent_gets_its_own_prompt(self):
        seen = {}

        def judge(prompt, context):
            seen["judge"] = prompt
            return Ruling.from_dict(ruling_payload(outcome="success"))

        def write(prompt, context, ruling):
            seen["writer"] = prompt
            return Narration.from_dict({"narration": "You do it."})

        def review(prompt, context, ruling, narration):
            seen["review"] = prompt
            return pass_review(prompt, context, ruling, narration)

        build_turn_graph(judge, write, review).invoke(
            {"judge_prompt": "J", "writer_prompt": "W", "review_prompt": "R",
             "context": {"action": {"type": "do", "text": "x"}}}
        )
        self.assertEqual(seen, {"judge": "J", "writer": "W", "review": "R"})

    def test_a_rejected_ruling_stops_the_turn(self):
        def judge(prompt, context):
            raise ValueError("Rejected ruling")

        def write(prompt, context, ruling):
            raise AssertionError("the writer must not run when the judge fails")

        graph = build_turn_graph(judge, write, pass_review)
        with self.assertRaises(ValueError):
            graph.invoke(
                {"judge_prompt": "J", "writer_prompt": "W", "context": {"action": {"type": "do", "text": "x"}}}
            )

    def run_revision(self, target, *, always_reject=False):
        calls = []
        snapshot = {"action": {"type": "do", "text": "wait"}, "state": {"turn": 0}}
        reports = [Review.from_dict(review_payload(target)),
                   Review.from_dict(review_payload(target if always_reject else None))]

        def judge(prompt, context):
            calls.append(("judge", context))
            return Ruling.from_dict(ruling_payload())

        def write(prompt, context, ruling):
            calls.append(("writer", context))
            return Narration("The keeper turns away.")

        def review(prompt, context, ruling, narration):
            calls.append(("review", context))
            return reports.pop(0)

        graph = build_turn_graph(judge, write, review)
        result = graph.invoke({"judge_prompt": "J", "writer_prompt": "W",
                               "review_prompt": "R", "context": snapshot})
        self.assertEqual(snapshot, {"action": {"type": "do", "text": "wait"}, "state": {"turn": 0}})
        self.assertEqual(len(result["review_history"]), 2)
        return calls, result

    def test_prose_revision_reuses_ruling_and_skips_judge(self):
        calls, result = self.run_revision("writer")
        self.assertEqual([call[0] for call in calls],
                         ["judge", "writer", "review", "writer", "review"])
        feedback = calls[3][1]["writer_feedback"]
        self.assertIn("previous_candidate", feedback)
        self.assertNotIn("reason", str(feedback))
        self.assertEqual(result["revision_count"], 1)

    def test_structural_revision_returns_to_judge_then_writer(self):
        calls, _ = self.run_revision("judge")
        self.assertEqual([call[0] for call in calls],
                         ["judge", "writer", "review", "judge", "writer", "review"])
        self.assertIn("previous_ruling", calls[3][1]["revision"])
        self.assertIn("review", calls[3][1]["revision"])
        self.assertNotIn("previous_candidate", calls[4][1]["writer_feedback"])

    def test_repair_budget_is_global_and_never_publishes_a_rejected_candidate(self):
        with self.assertRaisesRegex(RulingError, "repair limit"):
            self.run_revision("writer", always_reject=True)


class UnderstandingGraphTests(unittest.TestCase):
    def test_understand_is_a_single_node_that_returns_the_case(self):
        calls = []

        def understand(prompt, source):
            calls.append((prompt, source))
            return Understanding.from_dict(understanding_payload(
                player="the fox", canon="# World", opening="Cold moss."))

        graph = build_understanding_graph(understand)
        result = graph.invoke({"prompt": "READ-THE-TALE", "source": "a tale"})

        self.assertEqual(calls, [("READ-THE-TALE", "a tale")])
        self.assertEqual(result["understanding"].player, "the fox")
        self.assertEqual(result["understanding"].opening, "Cold moss.")


if __name__ == "__main__":
    unittest.main()
