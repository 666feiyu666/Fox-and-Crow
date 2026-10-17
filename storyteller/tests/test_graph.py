import unittest

from backend.graph import build_turn_graph
from backend.session import Narration, Ruling


class GraphTests(unittest.TestCase):
    def test_judge_runs_before_the_writer_and_hands_over_the_ruling(self):
        calls = []

        def judge(prompt, context):
            calls.append(("judge", prompt, context["action"]["text"]))
            return Ruling.from_dict(
                {"outcome": "failure", "facts": ["The crow turned away."], "scene": "She turns."}
            )

        def write(prompt, context, ruling):
            calls.append(("write", prompt, ruling.outcome))
            return Narration.from_dict({"narration": "She turns her back.", "hints": ["Wait."]})

        graph = build_turn_graph(judge, write)
        result = graph.invoke(
            {
                "judge_prompt": "JUDGE-PROMPT",
                "writer_prompt": "WRITER-PROMPT",
                "context": {"action": {"type": "say", "text": "喂，乌鸦"}},
            }
        )

        self.assertEqual([call[0] for call in calls], ["judge", "write"])
        self.assertEqual(calls[0][2], "喂，乌鸦")
        self.assertEqual(calls[1][2], "failure")
        self.assertEqual(result["ruling"].outcome, "failure")
        self.assertEqual(result["narration"].text, "She turns her back.")

    def test_each_agent_gets_its_own_prompt(self):
        seen = {}

        def judge(prompt, context):
            seen["judge"] = prompt
            return Ruling.from_dict({"outcome": "success", "facts": [], "scene": "plan"})

        def write(prompt, context, ruling):
            seen["writer"] = prompt
            return Narration.from_dict({"narration": "You do it."})

        build_turn_graph(judge, write).invoke(
            {"judge_prompt": "J", "writer_prompt": "W", "context": {"action": {"type": "do", "text": "x"}}}
        )
        self.assertEqual(seen, {"judge": "J", "writer": "W"})

    def test_a_rejected_ruling_stops_the_turn(self):
        def judge(prompt, context):
            return Ruling.from_dict({"outcome": "success", "facts": [], "scene": "plan"})

        def write(prompt, context, ruling):
            raise AssertionError("the writer must not run when the judge fails")

        graph = build_turn_graph(judge, write)
        with self.assertRaises(AssertionError):
            graph.invoke(
                {"judge_prompt": "J", "writer_prompt": "W", "context": {"action": {"type": "do", "text": "x"}}}
            )


if __name__ == "__main__":
    unittest.main()
