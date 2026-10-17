import unittest

from backend.review import Review
from backend.space import ContractError
from tests.fixtures import review_payload


class ReviewTests(unittest.TestCase):
    def test_pass_may_carry_minor_suggestions(self):
        report = Review.from_dict(review_payload("writer", blocking=False))
        self.assertEqual((report.decision, report.target), ("pass", "none"))
        self.assertEqual(Review.from_dict(report.to_dict()), report)

    def test_mixed_findings_route_to_judge_first(self):
        payload = review_payload("writer")
        payload["findings"].extend(review_payload("judge")["findings"])
        self.assertEqual(Review.from_dict(payload).target, "judge")

    def test_writer_feedback_excludes_private_evidence_and_diagnosis(self):
        payload = review_payload("writer")
        payload["summary"] = "private-summary"
        payload["findings"][0]["reason"] = "hidden-goal"
        payload["findings"][0]["evidence"] = "secret-state"
        report = Review.from_dict(payload)
        feedback = str(report.writer_feedback())
        for private in ("private-summary", "hidden-goal", "secret-state"):
            self.assertNotIn(private, feedback)
        self.assertIn(payload["findings"][0]["request"], feedback)

    def test_report_requires_consistent_decision_and_concrete_findings(self):
        invalid = [review_payload(decision="unknown"), review_payload(decision="revise"),
                   review_payload("writer", decision="pass"), review_payload(findings="bad")]
        for field, value in (("target", "both"), ("blocking", "yes"),
                             ("category", "playability"), ("evidence", ""), ("request", "")):
            payload = review_payload("writer")
            payload["findings"][0][field] = value
            invalid.append(payload)
        for payload in invalid:
            with self.subTest(payload=payload), self.assertRaises(ContractError):
                Review.from_dict(payload)


if __name__ == "__main__":
    unittest.main()
