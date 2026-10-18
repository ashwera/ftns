import dataclasses
import json
import tempfile
import unittest
from pathlib import Path

import golden_harness as G
from signalforge import claim_extraction as L1
from signalforge import pipeline as P
from signalforge import research_bridge as RB
from signalforge import source_retrieval as SR
from signalforge.config import Config
from signalforge.pipeline_contract import read_jsonl, validate_against

SYN_TEXT = """• Meridian Power Limited reported group installed capacity of 12,000 MW on a consolidated basis as on 31 March 2025.
• As on 31 March 2025, Meridian Power Limited has projects with a total capacity of 4,000 MW under implementation, including 3,000 MW being developed by joint venture and subsidiary companies.
• As on 31 March 2025, Meridian's renewable capacity of 2,000 MW is under implementation, including 1,800 MW of renewable projects being developed by joint venture and subsidiary companies.
• As on 31 March 2025, Meridian has a commissioned renewable capacity of 900 MW.
• Meridian has set a target to achieve 5,000 MW of renewable capacity by 2032."""
ROLES = {"installed_total_group": (12000, "group", "commissioned", ["installed capacity"]), "re_installed_group": (900, "group", "commissioned", ["renewable capacity"]), "re_pipeline_group": (2000, "group", "under_implementation", ["renewable capacity"]),
         "pipeline_total_group": (4000, "group", "under_implementation", ["total capacity"]), "pipeline_jv_sub": (3000, "jv_subsidiary_part", "under_implementation", ["being developed"]),
         "re_pipeline_jv_sub": (1800, "jv_subsidiary_part", "under_implementation", ["renewable projects"]), "re_target": (5000, "group", "target", ["renewable capacity"])}

def canonical_pending_record(source):
    """Map saved real-text fixture records to the canonical, explicitly pending schema."""
    return {
        "evidence_id": source["evidence_id"], "company_name": "NTPC Limited", "verified_identifier": "INE733E01010",
        "company_identity_status": "verified", "source_organization": "NTPC Limited", "document_title": str(source.get("document_title") or "NTPC annual report fixture"),
        "document_type": "annual_report", "source_url": None, "source_path": source.get("source_path"),
        "source_locator": str(source.get("source_locator") or f"page:{source.get('page_number')}"),
        "source_identifier_status": "repository_path_only", "publication_date": None, "event_date": None,
        "retrieval_date": "2026-10-18", "excerpt_or_fact": str(source.get("excerpt_or_fact") or source.get("text") or ""),
        "metric_name": None, "metric_value": None, "unit": None, "currency": None, "reporting_period": None,
        "evidence_category": "annual_report_text", "related_claim": None, "claim_key": None,
        "source_relationship": "original_disclosure", "claim_verification_status": "unverified",
        "information_type": "reported_fact", "parsing_status": "parsed", "extraction_warnings": [],
        "page_number": source.get("page_number"), "table_identifier": None, "review_status": "pending_review",
        "reviewed_by": None, "reviewed_at": None, "review_note": None,
    }

def synthetic_company(tmp, drop=()):
    """SYNTHETIC company 'Meridian Power Limited': evidence, claims extracted by the real extractor, registry entry and reviewed inputs."""
    rec = {"evidence_id": "ev_" + "1" * 24, "company_name": "Meridian Power Limited", "verified_identifier": None,
           "company_identity_status": "verified", "source_organization": "Meridian (synthetic)", "document_title": "synthetic",
           "document_type": "synthetic test fixture", "source_url": None, "source_path": "SYNTHETIC/meridian.txt",
           "source_locator": "page:3:block:1", "source_identifier_status": "repository_path_only",
           "publication_date": None, "event_date": None, "retrieval_date": "2026-10-18", "excerpt_or_fact": SYN_TEXT,
           "metric_name": None, "metric_value": None, "unit": None, "currency": None, "reporting_period": None,
           "evidence_category": "synthetic_test_fixture", "related_claim": None, "claim_key": None,
           "source_relationship": "unknown", "claim_verification_status": "unverified", "information_type": "reported_fact",
           "parsing_status": "parsed", "extraction_warnings": [], "page_number": 3, "table_identifier": None,
           "review_status": "approved", "reviewed_by": "test-fixture", "reviewed_at": "2026-10-18T00:00:00Z", "review_note": "Synthetic test evidence explicitly approved for offline integration coverage."}
    claims = L1.extract_claims(rec, "doc_syn", target=L1.TargetCompany("Meridian Power Limited", ("Meridian",)))
    tmp = Path(tmp); (tmp / "evidence.jsonl").write_text(json.dumps(rec) + "\n"); (tmp / "claims.jsonl").write_text("".join(json.dumps(c) + "\n" for c in claims))
    (tmp / "registry.json").write_text(json.dumps({"version": 1, "companies": [{"canonical_name": "Meridian Power Limited", "verified_identifier": None, "identifiers": ["Meridian"], "aliases": ["Meridian"], "verification_source": "synthetic://fixture-only",
                                                                                 "verification_source_type": "synthetic", "verification_status": "verified", "note": "SYNTHETIC test registry entry"}]}))
    items = []
    for role, (v, basis, status, terms) in ROLES.items():
        if role in drop: continue
        hit = [c for c in claims if c["value"] == v and c["unit"] == "MW"]; assert len(hit) == 1, (role, v, len(hit))
        items.append({"role": role, "name": role, "claim_id": hit[0]["claim_id"], "as_of_date": None if role == "re_target" else "2025-03-31", "period_text": "2032" if role == "re_target" else "As on 31 March 2025", "basis": basis, "statement_status": status, "label_terms": terms, "rounding_uncertainty": None})
    (tmp / "inputs.json").write_text(json.dumps({"company": "Meridian Power Limited", "reference_year": 2026, "hypothesis_id": "H_syn", "reviewer": {"kind": "ai_assisted_analyst", "id": "test", "note": "SYNTHETIC"}, "inputs": items}))
    return tmp

class BridgeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls): cls.chunks, cls.cases = G.load()
    def real_claims(self):
        source_records = [self.chunks[i] for i in ("ev_252ddc5ca75aa6a8bc871cb1", "ev_2484a0e981c95b1829d91ac3", "ev_fcde1c84df4f8b650bb1afdd")]
        recs = [canonical_pending_record(r) for r in source_records]
        claims = [c for r in recs for c in L1.extract_claims(r, "d", target=L1.TargetCompany("NTPC Limited", ("NTPC",)))]
        return claims, {r["evidence_id"]: r for r in recs}
    def test_unreviewed_real_claims_are_blocked_even_when_simulation_is_requested(self):
        claims, by_id = self.real_claims(); bundle = RB.select_bundle(claims, by_id, max_claims=15)
        self.assertTrue(0 < len(bundle["claims"]) <= 15); self.assertTrue(all(c["claim_verification_status"] == "unverified" for c in bundle["claims"]))
        with tempfile.TemporaryDirectory() as d:
            RB.write_bundle(bundle, Path(d) / "b"); st = RB.run_f1_r1("NTPC Limited", Path(d) / "b", Path(d) / "o", simulate=True)
            self.assertEqual(("blocked", "not_executed"), (st["f1"]["execution"], st["r1"]["execution"]))
            self.assertIn("human-reviewed, approved", st["f1"]["error"])
            self.assertFalse((Path(d) / "o" / "f1_output.json").exists())
    def test_ineligible_inputs_are_rejected(self):
        unresolved = self.chunks["ev_7b29bace955f23aa73e02e78"]; claims = L1.extract_claims(unresolved, "d", target=None)
        bundle = RB.select_bundle(claims, {unresolved["evidence_id"]: unresolved}); self.assertEqual([], bundle["claims"])   # identity unresolved => not eligible
        with tempfile.TemporaryDirectory() as d:
            RB.write_bundle(bundle, Path(d) / "b"); st = RB.run_f1_r1("NTPC Limited", Path(d) / "b", Path(d) / "o", simulate=True)
            self.assertEqual("blocked", st["f1"]["execution"]); self.assertEqual("not_executed", st["r1"]["execution"])
            st2 = RB.run_f1_r1("Unregistered Example Limited", Path(d) / "b", Path(d) / "o2", simulate=True); self.assertEqual("blocked", st2["f1"]["execution"]); self.assertIn("unresolved", st2["f1"]["error"])
    def test_missing_credentials_are_not_bypassed(self):
        with tempfile.TemporaryDirectory() as d:
            src=synthetic_company(d); claims=read_jsonl(src/"claims.jsonl"); records=read_jsonl(src/"evidence.jsonl"); bundle=RB.select_bundle(claims,{r["evidence_id"]:r for r in records},max_claims=5)
            RB.write_bundle(bundle, Path(d) / "b"); st = RB.run_f1_r1("Meridian Power Limited", Path(d) / "b", Path(d) / "o", config=dataclasses.replace(Config(), api_key="", registry_path=src/"registry.json"), simulate=False)
            self.assertEqual("blocked", st["f1"]["execution"]); self.assertIn("SIGNALFORGE_API_KEY", st["f1"]["error"]); self.assertFalse((Path(d) / "o" / "f1_output.json").exists())

def fake_fetcher(report):
    return lambda urls, d: {"sources": [dict(report[u], requested_url=u) for u in urls if u in report]}

class RetrievalTests(unittest.TestCase):
    PLAN = {"evidence_ledger": [{"evidence_id": None, "source_type": "annual_report", "source_url": None, "publication_date": None, "excerpt_or_data_point": None, "claim_supported": "h", "kind": "unverified_hypothesis", "status": "planned_lookup"},
                                {"evidence_id": None, "source_type": "regulator_data", "source_url": None, "publication_date": None, "excerpt_or_data_point": None, "claim_supported": "h", "kind": "unverified_hypothesis", "status": "planned_lookup"}]}
    CAT = {"official_domains": ["issuer.example", "regulator.example"], "sources": [{"url": "https://issuer.example/ar.pdf", "source_type": "annual_report", "source_class": "official_filing", "publisher": "Issuer"},
                                                                                 {"url": "https://mirror.example/ar.pdf", "source_type": "annual_report", "source_class": "third_party", "publisher": "Mirror"},
                                                                                 {"url": "https://issuer.example/old.pdf", "source_type": "annual_report", "source_class": "official_filing", "publisher": "Issuer"}]}
    def test_requests_are_catalog_only_and_gaps_are_reported_not_invented(self):
        reqs = SR.plan_requests(self.PLAN, SR.load_catalog(self.CAT), ["cl1_x"], "H1")
        self.assertEqual(3, sum(r["status"] == "planned" for r in reqs)); gap = [r for r in reqs if r["status"] == "no_catalog_source"]; self.assertEqual(1, len(gap)); self.assertIsNone(gap[0]["url"])
        with self.assertRaises(ValueError): SR.load_catalog({"official_domains": ["issuer.example"], "sources": [{"url": "https://evil.example/x", "source_type": "t", "source_class": "official_filing"}]})
    def test_provenance_dedup_failures_staleness_and_classification(self):
        rep = {"https://issuer.example/ar.pdf": {"retrieval_status": "retrieved", "source_sha256": "h1", "publication_date": "2025-06-01", "retrieved_at": "t", "canonical_url": "https://issuer.example/ar.pdf", "company_association_status": "verified", "warnings": []},
               "https://mirror.example/ar.pdf": {"retrieval_status": "retrieved", "source_sha256": "h1", "publication_date": None, "retrieved_at": "t", "company_association_status": "verified", "warnings": []},
               "https://issuer.example/old.pdf": {"retrieval_status": "retrieved", "source_sha256": "h2", "publication_date": "2019-01-01", "retrieved_at": "t", "company_association_status": "verified", "warnings": []}}
        import datetime as dt
        with tempfile.TemporaryDirectory() as d:
            reqs = SR.plan_requests(self.PLAN, SR.load_catalog(self.CAT), ["cl1_x"], "H1")
            out = SR.execute(reqs, d, fetcher=fake_fetcher(rep), today=dt.date(2026, 10, 18)); by = {r["url"]: r for r in out["results"] if r.get("url")}
            self.assertEqual("retrieved", by["https://issuer.example/ar.pdf"]["status"]); self.assertTrue(by["https://issuer.example/ar.pdf"]["is_primary"])
            self.assertEqual("duplicate_mirror", by["https://mirror.example/ar.pdf"]["status"]); self.assertEqual("stale", by["https://issuer.example/old.pdf"]["status"])
            self.assertEqual("primary_source", SR.verification_level_for(by["https://issuer.example/ar.pdf"])); self.assertEqual("extracted_text_review", SR.verification_level_for(by["https://issuer.example/old.pdf"]))
            self.assertEqual(1, out["summary"]["no_catalog_source"]); self.assertTrue((Path(d) / "retrieval_results.json").is_file())
    def test_failures_and_exceptions_are_reported(self):
        reqs = SR.plan_requests(self.PLAN, SR.load_catalog(self.CAT), [], "H1")
        out = SR.execute(reqs, tempfile.mkdtemp(), fetcher=lambda u, d: (_ for _ in ()).throw(OSError("offline")))
        self.assertEqual(3, out["summary"]["failed"]); self.assertTrue(all("offline" in r["error"] for r in out["results"] if r["status"] == "failed"))
    def test_undated_source_is_not_a_primary_source_for_verification(self):
        self.assertEqual("extracted_text_review", SR.verification_level_for({"is_primary": True, "status": "retrieved", "publication_date": None, "company_association": "verified"}))

class EndToEndTests(unittest.TestCase):
    def test_synthetic_company_vertical_slice_is_reproducible_and_honest(self):
        with tempfile.TemporaryDirectory() as d:
            t = synthetic_company(d); run = t / "run"
            f, problems = P.run_pipeline("Meridian Power Limited", t / "claims.jsonl", t / "evidence.jsonl", t / "inputs.json", run, registry_path=t / "registry.json", simulate_llm=True, synthetic=True)
            self.assertEqual([], problems); validate_against(f, "finding")
            self.assertEqual(("provisional_hypothesis", "Weak", True, True), (f["finding_status"], f["evidence_strength"], f["synthetic"], f["all_claims_unverified"]))
            names = {c["name"]: c["result"]["value"] for c in f["calculations"]}
            self.assertAlmostEqual(20.0, names["re_share_of_parent_own_pipeline"]); self.assertAlmostEqual(60.0, names["re_share_of_jv_subsidiary_pipeline"]); self.assertAlmostEqual(58.0, names["re_installed_plus_pipeline_vs_target"])
            prov = {s["stage"]: s["execution"] for s in f["stage_provenance"]}
            self.assertEqual(("simulated", "simulated", "not_executed"), (prov["F1"], prov["R1"], prov["source_catalog"])); self.assertEqual("real", prov["source_verification"])
            self.assertTrue(all(c["claim_verification_status"] == "unverified" for c in read_jsonl(t / "claims.jsonl")))
            f2, _ = P.run_pipeline("Meridian Power Limited", t / "claims.jsonl", t / "evidence.jsonl", t / "inputs.json", t / "run2", registry_path=t / "registry.json", simulate_llm=True, synthetic=True)
            norm = lambda x: {**x, "run_id": "r", "finding_id": "f"}
            self.assertEqual(norm(f), norm(f2))   # deterministic apart from the run id
    def test_missing_roles_give_no_defensible_signal_not_a_forced_finding(self):
        with tempfile.TemporaryDirectory() as d:
            t = synthetic_company(d, drop=("re_pipeline_jv_sub", "pipeline_jv_sub"))
            f, problems = P.run_pipeline("Meridian Power Limited", t / "claims.jsonl", t / "evidence.jsonl", t / "inputs.json", t / "run", registry_path=t / "registry.json", simulate_llm=True, synthetic=True)
            self.assertEqual(("no_defensible_signal", "None", []), (f["finding_status"], f["evidence_strength"], problems)); self.assertTrue(f["missing_evidence"])
    def test_company_with_no_source_data_is_refused_and_target_comes_from_configuration(self):
        with tempfile.TemporaryDirectory() as d:
            t = Path(d); (t / "claims.jsonl").write_text(""); (t / "evidence.jsonl").write_text("")
            (t / "inputs.json").write_text(json.dumps({"company": "Example Grid Limited", "reference_year": 2026, "hypothesis_id": "H0", "reviewer": {"kind": "ai_assisted_analyst", "id": "t", "note": "n"}, "inputs": []}))
            f, problems = P.run_pipeline("Example Grid Limited", t / "claims.jsonl", t / "evidence.jsonl", t / "inputs.json", t / "run", registry_path=t / "none.json")
            self.assertEqual(("no_defensible_signal", "config_only"), (f["finding_status"], f["company"]["identity_status"])); self.assertEqual("blocked", {s["stage"]: s["execution"] for s in f["stage_provenance"]}["F1"])
    def test_contradicted_inputs_are_excluded_from_calculations(self):
        with tempfile.TemporaryDirectory() as d:
            t = synthetic_company(d); spec = json.loads((t / "inputs.json").read_text())
            for i in spec["inputs"]:
                if i["role"] == "re_pipeline_jv_sub": i["as_of_date"] = "2024-03-31"; i["period_text"] = "As on 31 March 2024"   # wrong period asserted
            (t / "inputs.json").write_text(json.dumps(spec))
            f, _ = P.run_pipeline("Meridian Power Limited", t / "claims.jsonl", t / "evidence.jsonl", t / "inputs.json", t / "run", registry_path=t / "registry.json", simulate_llm=True, synthetic=True)
            self.assertEqual("no_defensible_signal", f["finding_status"])
    def test_real_ntpc_slice_if_archive_outputs_exist(self):
        claims = Path(__file__).resolve().parents[1] / "data" / "runs" / "run_20261018_archive" / "table_aware" / "claims.jsonl"; spec = Path(__file__).resolve().parents[1] / "data" / "pipeline_inputs" / "ntpc_renewable_pipeline_reviewed_inputs.json"
        if not claims.is_file() or not spec.is_file(): self.skipTest("archive evaluation outputs not present")
        with tempfile.TemporaryDirectory() as d:
            f, problems = P.run_pipeline("NTPC Limited", claims, Path(__file__).resolve().parents[1] / "data" / "processed_step6" / "evidence.jsonl", spec, Path(d) / "run", simulate_llm=True)
            self.assertEqual([], problems); self.assertEqual(("registry_verified", "Weak", False), (f["company"]["identity_status"], f["evidence_strength"], f["synthetic"]))
            self.assertEqual("provisional_hypothesis", f["finding_status"]); self.assertTrue(all(i["verification_level"] == "extracted_text_review" for i in f["inputs"]))
            self.assertAlmostEqual(4.6, {c["name"]: c["result"]["value"] for c in f["calculations"]}["re_share_of_parent_own_pipeline"], places=1)

if __name__ == "__main__": unittest.main()
