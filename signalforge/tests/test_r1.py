import json, tempfile, unittest
from pathlib import Path
from signalforge.config import Config
from signalforge import r1_research_investigator as r1

SCHEMA = Config().schema_path.with_name("r1_output.schema.json")

def plan(**over):
    p = {"company_name": "X", "candidate_id": "c1", "hypothesis": "h", "retrieval_performed": False,
         "research_questions": [{"question": "q", "metrics": ["m"], "periods": ["FY25"], "supported_by_dataset": False, "missing": ["filings"]}],
         "evidence_ledger": [{"evidence_id": None, "source_type": "annual_report", "source_url": None, "publication_date": None,
                              "excerpt_or_data_point": None, "claim_supported": "c", "kind": "unverified_hypothesis", "status": "planned_lookup"}],
         "checklist": [{"step": "s", "expected_evidence": "e", "cross_validation_sources": ["a"], "completion_criteria": "done"}],
         "alternative_explanation": "alt", "falsification_test": "ft"}
    p.update(over); return p

class R1Tests(unittest.TestCase):
    def test_valid(self): r1.validate_plan(plan(), SCHEMA)
    def test_retrieval_claim_rejected(self):
        with self.assertRaises(ValueError): r1.validate_plan(plan(retrieval_performed=True), SCHEMA)
    def test_unknown_evidence_id_rejected(self):
        p = plan(); p["evidence_ledger"][0].update(evidence_id="ev_nope", status="supplied")
        with self.assertRaises(ValueError): r1.validate_plan(p, SCHEMA, ["ev_1"])
    def test_planned_lookup_with_url_rejected(self):
        p = plan(); p["evidence_ledger"][0]["source_url"] = "https://x.test"
        with self.assertRaises(ValueError): r1.validate_plan(p, SCHEMA)
    def test_requires_recommendation(self):
        with self.assertRaises(ValueError): r1.select_candidate({"recommended_candidate_id": None})
    def test_unreliable_f1_refused(self):
        with tempfile.TemporaryDirectory() as d:
            f = Path(d) / "f1.json"; f.write_text(json.dumps({"ranking_reliable": False}))
            with self.assertRaises(ValueError): r1.run(f, Path(d) / "o.json")

if __name__ == "__main__": unittest.main()
