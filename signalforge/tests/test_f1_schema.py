import json
import dataclasses
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from signalforge.f1_research_angle_selector import run, weighted_score, validate_output
from signalforge.config import Config, ROOT
from signalforge.data_loader import DataLoadError
from signalforge.llm_client import LLMError

SCHEMA = json.loads((ROOT / "schemas/f1_output.schema.json").read_text())

def evidence_record(*, review_status="pending_review", excerpt="Extracted page text.", evidence_id="ev_" + "1" * 24):
    return {
        "evidence_id": evidence_id, "company_name": "NTPC Limited", "verified_identifier": "INE733E01010", "company_identity_status": "verified",
        "source_organization": "NTPC Limited", "document_title": "Fixture report", "document_type": "annual_report", "source_url": None,
        "source_path": "fixture/report.csv", "source_locator": "page:3:block:1", "source_identifier_status": "repository_path_only",
        "publication_date": None, "event_date": None, "retrieval_date": "2026-10-18T00:00:00Z", "excerpt_or_fact": excerpt,
        "metric_name": None, "metric_value": None, "unit": None, "currency": None, "reporting_period": None, "evidence_category": "report",
        "related_claim": None, "claim_key": None, "source_relationship": "unknown", "claim_verification_status": "unverified",
        "information_type": "reported_fact", "parsing_status": "parsed", "extraction_warnings": [], "page_number": 3, "table_identifier": None,
        "review_status": review_status, "reviewed_by": None, "reviewed_at": None, "review_note": None,
    }

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
    def test_unreviewed_verified_identity_is_blocked_before_model_call(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d); csv=root/"quotes.csv"; csv.write_text("Date,Close\n2025-01-01,10\n")
            registry=root/"registry.json"; registry.write_text(json.dumps({"companies":[{"canonical_name":"NTPC Limited","verified_identifier":"INE733E01010","aliases":["NTPC"],"identifiers":[],"verification_status":"verified","verification_source":"fixture"}]}))
            evidence=root/"evidence"; evidence.mkdir()
            record=evidence_record(excerpt="Unreviewed extracted page text.")
            (evidence/"evidence.jsonl").write_text(json.dumps(record)+"\n")
            original_evidence=(evidence/"evidence.jsonl").read_bytes()
            cfg=dataclasses.replace(Config(),csv_path=csv,registry_path=registry,evidence_dir=evidence)
            with patch("signalforge.f1_research_angle_selector.generate_json") as model:
                with self.assertRaisesRegex(DataLoadError,"human-reviewed, approved"):
                    run("NTPC Limited",csv,root/"f1.json",cfg)
                model.assert_not_called()
            self.assertEqual(original_evidence,(evidence/"evidence.jsonl").read_bytes())
    def test_legacy_null_review_status_is_treated_as_unreviewed_not_malformed(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d); csv=root/"quotes.csv"; csv.write_text("Date,Close\n2025-01-01,10\n")
            registry=root/"registry.json"; registry.write_text(json.dumps({"companies":[{"canonical_name":"NTPC Limited","verified_identifier":"INE733E01010","aliases":["NTPC"],"identifiers":[],"verification_status":"verified","verification_source":"fixture"}]}))
            evidence=root/"evidence"; evidence.mkdir(); record=evidence_record(review_status=None)
            (evidence/"evidence.jsonl").write_text(json.dumps(record)+"\n")
            cfg=dataclasses.replace(Config(),csv_path=csv,registry_path=registry,evidence_dir=evidence)
            with patch("signalforge.f1_research_angle_selector.generate_json") as model:
                with self.assertRaisesRegex(DataLoadError,"human-reviewed, approved"):
                    run("NTPC Limited",csv,root/"f1.json",cfg)
                model.assert_not_called()
    def test_oversized_f1_payload_is_blocked_before_model_call(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d); csv=root/"quotes.csv"; csv.write_text("Date,Close\n2025-01-01,10\n")
            registry=root/"registry.json"; registry.write_text(json.dumps({"companies":[{"canonical_name":"NTPC Limited","verified_identifier":"INE733E01010","aliases":["NTPC"],"identifiers":[],"verification_status":"verified","verification_source":"fixture"}]}))
            evidence=root/"evidence"; evidence.mkdir()
            record=evidence_record(review_status="approved", excerpt="x"*260_000)
            record.update(reviewed_by="reviewer-1",reviewed_at="2026-10-18T12:00:00Z",review_note="Reviewed fixture.")
            (evidence/"evidence.jsonl").write_text(json.dumps(record)+"\n")
            cfg=dataclasses.replace(Config(),csv_path=csv,registry_path=registry,evidence_dir=evidence)
            with patch("signalforge.f1_research_angle_selector.generate_json") as model:
                with self.assertRaisesRegex(DataLoadError,"request payload"):
                    run("NTPC Limited",csv,root/"f1.json",cfg)
                model.assert_not_called()
    def test_malformed_json_is_rejected_before_model_call(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d); csv=root/"quotes.csv"; csv.write_text("Date,Close\n2025-01-01,10\n")
            registry=root/"registry.json"; registry.write_text(json.dumps({"companies":[{"canonical_name":"NTPC Limited","verified_identifier":"INE733E01010","aliases":["NTPC"],"identifiers":[],"verification_status":"verified","verification_source":"fixture"}]}))
            evidence=root/"evidence"; evidence.mkdir(); (evidence/"evidence.jsonl").write_text('{not-json}\n')
            cfg=dataclasses.replace(Config(),csv_path=csv,registry_path=registry,evidence_dir=evidence)
            with patch("signalforge.f1_research_angle_selector.generate_json") as model:
                with self.assertRaisesRegex(DataLoadError,"Invalid normalized evidence JSONL at line 1"):
                    run("NTPC Limited",csv,root/"f1.json",cfg)
                model.assert_not_called()
    def test_schema_invalid_evidence_is_rejected_before_model_call(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d); csv=root/"quotes.csv"; csv.write_text("Date,Close\n2025-01-01,10\n")
            registry=root/"registry.json"; registry.write_text(json.dumps({"companies":[{"canonical_name":"NTPC Limited","verified_identifier":"INE733E01010","aliases":["NTPC"],"identifiers":[],"verification_status":"verified","verification_source":"fixture"}]}))
            evidence=root/"evidence"; evidence.mkdir(); record=evidence_record(); record.pop("source_locator"); (evidence/"evidence.jsonl").write_text(json.dumps(record)+"\n")
            cfg=dataclasses.replace(Config(),csv_path=csv,registry_path=registry,evidence_dir=evidence)
            with patch("signalforge.f1_research_angle_selector.generate_json") as model:
                with self.assertRaisesRegex(DataLoadError,"source_locator"):
                    run("NTPC Limited",csv,root/"f1.json",cfg)
                model.assert_not_called()
    def test_duplicate_evidence_ids_are_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d); csv=root/"quotes.csv"; csv.write_text("Date,Close\n2025-01-01,10\n")
            registry=root/"registry.json"; registry.write_text(json.dumps({"companies":[{"canonical_name":"NTPC Limited","verified_identifier":"INE733E01010","aliases":["NTPC"],"identifiers":[],"verification_status":"verified","verification_source":"fixture"}]}))
            evidence=root/"evidence"; evidence.mkdir(); record=evidence_record(); (evidence/"evidence.jsonl").write_text(json.dumps(record)+"\n"+json.dumps(record)+"\n")
            cfg=dataclasses.replace(Config(),csv_path=csv,registry_path=registry,evidence_dir=evidence)
            with patch("signalforge.f1_research_angle_selector.generate_json") as model:
                with self.assertRaisesRegex(DataLoadError,"Duplicate evidence_id"):
                    run("NTPC Limited",csv,root/"f1.json",cfg)
                model.assert_not_called()
    def test_oversized_evidence_line_is_rejected_before_json_parse(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d); csv=root/"quotes.csv"; csv.write_text("Date,Close\n2025-01-01,10\n")
            registry=root/"registry.json"; registry.write_text(json.dumps({"companies":[{"canonical_name":"NTPC Limited","verified_identifier":"INE733E01010","aliases":["NTPC"],"identifiers":[],"verification_status":"verified","verification_source":"fixture"}]}))
            evidence=root/"evidence"; evidence.mkdir(); (evidence/"evidence.jsonl").write_text("x"*(1_000_001))
            cfg=dataclasses.replace(Config(),csv_path=csv,registry_path=registry,evidence_dir=evidence)
            with patch("signalforge.f1_research_angle_selector.generate_json") as model:
                with self.assertRaisesRegex(DataLoadError,"exceeds 1000000 bytes"):
                    run("NTPC Limited",csv,root/"f1.json",cfg)
                model.assert_not_called()

if __name__ == "__main__": unittest.main()
