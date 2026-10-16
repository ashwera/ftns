import json
import unittest
from pathlib import Path

from signalforge.f1_research_angle_selector import weighted_score, validate_output
from signalforge.config import ROOT
from signalforge.llm_client import LLMError

SCHEMA = json.loads((ROOT / "schemas/f1_output.schema.json").read_text())

class F1SchemaTests(unittest.TestCase):
    def test_weighted_score(self):
        self.assertEqual(100, weighted_score({"financial_significance":5,"evidence_availability":5,"testability":5,"non_obviousness":5,"cross_validation_potential":5}))
        self.assertEqual(0, weighted_score(dict.fromkeys(["financial_significance","evidence_availability","testability","non_obviousness","cross_validation_potential"],0)))
        self.assertEqual(30, weighted_score({"financial_significance":5,"evidence_availability":0,"testability":0,"non_obviousness":0,"cross_validation_potential":0}))
        self.assertEqual(17.5, weighted_score({"financial_significance":0,"evidence_availability":0,"testability":0,"non_obviousness":0,"cross_validation_potential":5}))
    def test_schema_accepts_minimal_consistent_output(self):
        data = {"company_name":"A","dataset_summary":{"row_count":1,"columns":["Close"],"date_coverage":None,"missing_information":[],"data_limitations":[]},"ranking_reliable":False,"ranking_limitation":"insufficient","ranked_candidates":[],"recommended_candidate_id":None}
        self.assertEqual(data, validate_output(data, ROOT / "schemas/f1_output.schema.json"))
    def test_schema_rejects_bad_score(self):
        data = {"company_name":"A","dataset_summary":{"row_count":1,"columns":[],"date_coverage":None,"missing_information":[],"data_limitations":[]},"ranking_reliable":False,"ranking_limitation":None,"ranked_candidates":[],"recommended_candidate_id":None,"bogus":True}
        with self.assertRaises(ValueError): validate_output(data, ROOT / "schemas/f1_output.schema.json")
    def test_invalid_json_handling(self):
        with self.assertRaises(json.JSONDecodeError): json.loads("not-json")

if __name__ == "__main__": unittest.main()
