import dataclasses, json, tempfile, unittest
from unittest import mock
from pathlib import Path
from signalforge.config import Config
from signalforge import r1_research_investigator as r1

from test_f1_schema import evidence_record

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

def eid(n): return "ev_" + str(n) * 24

def approved(n, **over):
    r = evidence_record(review_status="approved", evidence_id=eid(n))
    r.update(reviewed_by="Reviewer", reviewed_at="2026-10-19T10:00:00+00:00", review_note="Checked against page 3."); r.update(over); return r

class EvidenceGateTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(); self.addCleanup(self.tmp.cleanup); self.root = Path(self.tmp.name)
        (self.root / "registry.json").write_text(json.dumps({"companies": [{"canonical_name": "NTPC Limited", "verified_identifier": "INE733E01010", "aliases": ["NTPC"], "identifiers": [], "verification_status": "verified", "verification_source": "fixture"}]}))
        self.cfg = dataclasses.replace(Config(), registry_path=self.root / "registry.json", evidence_dir=self.root)
    def write(self, *records, raw=()):
        (self.root / "evidence.jsonl").write_text("\n".join([json.dumps(r) for r in records] + list(raw)) + "\n"); return self.root / "evidence.jsonl"
    def ids(self, *records, raw=(), company="NTPC Limited"): return r1.load_evidence_ids(self.write(*records, raw=raw), company, self.cfg)

    def test_valid_approved_included(self): self.assertEqual([eid(1)], self.ids(approved(1)))
    def test_alias_resolves_to_canonical(self): self.assertEqual([eid(1)], self.ids(approved(1), company="NTPC"))
    def test_pending_excluded(self): self.assertEqual([], self.ids(evidence_record(review_status="pending_review", evidence_id=eid(2))))
    def test_rejected_excluded(self): self.assertEqual([], self.ids(approved(2, review_status="rejected")))
    def test_unparsed_or_empty_excluded(self):
        self.assertEqual([], self.ids(approved(2, parsing_status="empty"), approved(3, parsing_status="failed"), approved(4, excerpt_or_fact="  ")))
    def test_missing_approval_metadata_excluded(self):
        bad = [approved(2, reviewed_by=None), approved(3, reviewed_by=" "), approved(4, reviewed_at=None), approved(5, reviewed_at="2026-10-19T10:00:00"),
               approved(6, reviewed_at="not a date"), approved(7, review_note=None), approved(8, review_note="")]
        self.assertEqual([], self.ids(*bad))
    def test_wrong_company_or_identifier_excluded(self):
        self.assertEqual([], self.ids(approved(2, company_name="Other Limited"), approved(3, verified_identifier="INE000000000"), approved(4, verified_identifier=None)))
    def test_unverified_identity_status_excluded(self): self.assertEqual([], self.ids(approved(2, company_identity_status="unresolved")))
    def test_matching_name_alone_is_not_enough(self):
        # Previous behaviour: verified status + name match sufficed, whatever the review state.
        self.assertEqual([], self.ids(evidence_record(review_status="pending_review", evidence_id=eid(2))))
    def test_malformed_excluded_and_does_not_hide_valid(self):
        missing_field = approved(3); del missing_field["parsing_status"]
        bad_id = approved(4, evidence_id="ev_short")
        out = self.ids(approved(1), missing_field, bad_id, [1, 2], raw=["{not json", "null", '"str"'])
        self.assertEqual([eid(1)], out)
    def test_duplicate_ids_collapsed(self): self.assertEqual([eid(1)], self.ids(approved(1), approved(1)))
    def test_unresolved_company_fails_closed(self): self.assertEqual([], self.ids(approved(1), company="Unregistered Example Limited"))
    def test_missing_file_gives_empty(self): self.assertEqual([], r1.load_evidence_ids(self.root / "none.jsonl", "NTPC Limited", self.cfg))
    def test_allowlist_cap(self):
        recs = [approved(1, evidence_id="ev_" + f"{i:024x}") for i in range(41)]
        with self.assertRaises(ValueError): self.ids(*recs)

    def test_excluded_ids_never_reach_prompt_payload_or_allowlist(self):
        self.write(approved(1), evidence_record(review_status="pending_review", evidence_id=eid(2)), approved(3, parsing_status="empty"), approved(4, company_name="Other"))
        f1 = {"ranking_reliable": True, "company_name": "NTPC Limited", "recommended_candidate_id": "c1", "dataset_summary": None, "ranked_candidates": [{"candidate_id": "c1"}]}
        f1_path = self.root / "f1.json"; f1_path.write_text(json.dumps(f1))
        seen = {}
        def fake(prompt, payload, config):
            seen["prompt"], seen["payload"] = prompt, payload
            p = plan(company_name="NTPC Limited", candidate_id="c1"); p["evidence_ledger"][0].update(evidence_id=eid(2), status="supplied"); return p
        with mock.patch.object(r1, "generate_json", fake):
            with self.assertRaisesRegex(ValueError, "was not supplied"): r1.run(f1_path, self.root / "o.json", self.cfg)
        self.assertEqual([eid(1)], seen["payload"]["supplied_evidence_ids"])
        blob = seen["prompt"] + json.dumps(seen["payload"])
        for n in (2, 3, 4): self.assertNotIn(eid(n), blob)
        self.assertFalse((self.root / "o.json").exists())

if __name__ == "__main__": unittest.main()
