import copy
from dataclasses import replace
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock, patch

from signalforge.config import Config
from signalforge.f1_research_angle_selector import _validate, normalize_f1_scores
from signalforge.llm_client import LLMError
from signalforge.structured_generation import generate_validated


class StructuredGenerationTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(); self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.schema = self.root / "schema.json"
        self.schema.write_text(json.dumps({"type": "object", "required": ["answer"],
            "properties": {"answer": {"type": "integer"}}, "additionalProperties": False}))
        self.cfg = replace(Config(), api_key="fixture-secret")

    def generate(self, generator, **kwargs):
        def validate(result):
            errors = _validate(result, json.loads(self.schema.read_text()))
            if errors: raise ValueError("; ".join(errors))
        return generate_validated("prompt", {"value": 1}, self.cfg, schema_path=self.schema,
            output_path=self.root / "result.json", generate=generator,
            validate=validate, stage="test", **kwargs)

    def audit(self):
        return next((self.root / "result_model_audit").iterdir())

    def test_one_repair_schema_in_both_requests_and_raw_responses_preserved(self):
        generator = Mock(side_effect=[{"wrong": 2}, {"answer": 3}])
        self.assertEqual({"answer": 3}, self.generate(generator))
        self.assertEqual(2, generator.call_count)
        for call in generator.call_args_list:
            self.assertIn('"required": ["answer"]', call.args[0])
        self.assertIn("previous response failed validation", generator.call_args.args[0])
        audit = self.audit()
        self.assertEqual({"wrong": 2}, json.loads((audit / "attempt_1_raw_response.json").read_text()))
        self.assertEqual({"answer": 3}, json.loads((audit / "attempt_2_raw_response.json").read_text()))
        self.assertEqual(2, json.loads((audit / "summary.json").read_text())["accepted_attempt"])

    def test_two_invalid_responses_fail_without_final_output_or_third_call(self):
        generator = Mock(return_value={"wrong": 2})
        with self.assertRaises(ValueError): self.generate(generator)
        self.assertEqual(2, generator.call_count)
        self.assertFalse((self.root / "result.json").exists())
        self.assertEqual("rejected", json.loads((self.audit() / "summary.json").read_text())["status"])

    def test_client_errors_are_not_retried_here_but_invalid_json_can_repair(self):
        generator = Mock(side_effect=LLMError("Model request failed (AuthenticationError)"))
        with self.assertRaises(LLMError): self.generate(generator)
        self.assertEqual(1, generator.call_count)
        other = Mock(side_effect=[LLMError("Model returned invalid JSON: fixture"), {"answer": 3}])
        self.assertEqual({"answer": 3}, self.generate(other))
        self.assertEqual(2, other.call_count)

    def test_audit_and_repair_feedback_redact_configured_key(self):
        generator = Mock(side_effect=[{"wrong": "fixture-secret"}, {"answer": 3}])
        self.generate(generator)
        for path in self.audit().glob("*.json"):
            self.assertNotIn("fixture-secret", path.read_text())
        self.assertIn("[redacted]", (self.audit() / "attempt_1_raw_response.json").read_text())

    def test_normalization_preserves_raw_before_modifying_copy(self):
        response = {"answer": 99}
        def normalize(output):
            output["answer"] = 3
            return [{"field": "answer", "model_value": 99, "computed_value": 3}]
        self.assertEqual({"answer": 3}, self.generate(Mock(return_value=response), normalize=normalize))
        self.assertEqual({"answer": 99}, response)
        self.assertEqual(99, json.loads((self.audit() / "attempt_1_raw_response.json").read_text())["answer"])
        summary = json.loads((self.audit() / "summary.json").read_text())
        self.assertEqual(3, summary["attempts"][0]["corrections"][0]["computed_value"])

    def test_f1_arithmetic_correction_does_not_rerank_or_change_conclusions(self):
        scores = {"financial_significance": {"score": 5}, "evidence_availability": {"score": 4},
                  "testability": {"score": 4}, "non_obviousness": {"score": 3},
                  "cross_validation_potential": {"score": 4}}
        result = {"recommended_candidate_id": "c1", "ranking_reliable": True,
            "ranked_candidates": [{"candidate_id": "c1", "rank": 2, "hypothesis": "unchanged",
                "weighted_score": 425, "scores": scores},
                {"candidate_id": "c2", "rank": 1, "hypothesis": "also unchanged",
                 "weighted_score": 0, "scores": {k: {"score": 5} for k in scores}}]}
        before = copy.deepcopy(result)
        corrections = normalize_f1_scores(result)
        self.assertEqual([84.5, 100], [c["weighted_score"] for c in result["ranked_candidates"]])
        for candidate in result["ranked_candidates"]:
            original = next(c for c in before["ranked_candidates"] if c["candidate_id"] == candidate["candidate_id"])
            candidate["weighted_score"] = original["weighted_score"]
        self.assertEqual(before, result)
        self.assertEqual(2, len(corrections))
        bad = {"ranked_candidates": [{"scores": {k: {"score": True} for k in scores}, "weighted_score": 425}]}
        self.assertEqual([], normalize_f1_scores(bad))

    def test_schema_repair_cannot_change_existing_conclusion(self):
        self.schema.write_text(json.dumps({"type": "object", "required": ["answer", "hypothesis"],
            "properties": {"answer": {"type": "integer"}, "hypothesis": {"type": "string"}}}))
        generator = Mock(side_effect=[{"hypothesis": "original"}, {"answer": 3, "hypothesis": "changed"}])
        with self.assertRaisesRegex(ValueError, "changed an existing research conclusion"):
            self.generate(generator, preserve=lambda p: {"hypothesis": p["hypothesis"]})
        self.assertEqual(2, generator.call_count)
        self.assertIn('"hypothesis": "original"', generator.call_args.args[0])


if __name__ == "__main__":
    unittest.main()
