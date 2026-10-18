import io
import json
import re
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path

import test_pipeline_bridge_retrieval_e2e as E
from signalforge import pipeline as P
from signalforge import source_catalog as SC
from signalforge.pipeline_contract import validate_against

SRC_DIR = Path(__file__).resolve().parents[1] / "src" / "signalforge"

def snapshot(text, number_changes=()):
    t = "Page 7\n" + text
    for old, new in number_changes: t = t.replace(old, new)
    return t

def entry(sid, publisher, cls="official_filing", issuer=False, derived=(), **kw):
    e = {"source_id": sid, "publisher": publisher, "source_class": cls, "source_type": "annual_report", "title": sid, "publication_date": "2025-06-30", "reporting_period": "FY2024-25", "issuer_submitted": issuer,
         "derived_from": list(derived), "verified_by": "Samaira (synthetic test catalog)", "verified_on": "2026-10-18", "local_path": f"{sid}.txt"}
    e.update(kw); return e

def setup(tmp, snapshots, entries, key_overrides=None):
    t = E.synthetic_company(tmp)
    for sid, body in snapshots.items(): (t / f"{sid}.txt").write_text(body, encoding="utf-8")
    (t / "catalog.json").write_text(json.dumps({"catalog_version": "1.0", "company": "Meridian Power Limited", "sources": entries}))
    if key_overrides:
        spec = json.loads((t / "inputs.json").read_text())
        for i in spec["inputs"]:
            if i["role"] in key_overrides: i["key"] = key_overrides[i["role"]]
        (t / "inputs.json").write_text(json.dumps(spec))
    return t

def run(t, name="run", **kw):
    return P.run_pipeline("Meridian Power Limited", t / "claims.jsonl", t / "evidence.jsonl", t / "inputs.json", t / name, registry_path=t / "registry.json", simulate_llm=True, synthetic=True, catalog_path=t / "catalog.json", **kw)

OK = """• At group level, Meridian Power Limited reported installed capacity of 12,000 MW on a consolidated basis as on 31 March 2025.
• At group level, as on 31 March 2025, Meridian Power Limited has projects with a total capacity of 4,000 MW under implementation, including 3,000 MW being developed by joint venture and subsidiary companies.
• At group level, as on 31 March 2025, Meridian's renewable capacity of 2,000 MW is under implementation, including 1,800 MW of renewable projects being developed by joint venture and subsidiary companies.
• At group level, as on 31 March 2025, Meridian has a commissioned renewable capacity of 900 MW.
• At group level, Meridian's target is to achieve 5,000 MW of renewable capacity by 2032."""
REG = "Page 31\nThe regulator's pipeline survey records that, at group level, as on 31 March 2025, Meridian Power Limited has projects with a total capacity of 4,000 MW under implementation, including 3,000 MW being developed by joint venture and subsidiary companies. At group level, as on 31 March 2025, Meridian's renewable capacity of 2,000 MW is under implementation, including 1,800 MW of renewable projects being developed by joint venture and subsidiary companies. At group level, Meridian Power Limited reported installed capacity of 12,000 MW on a consolidated basis as on 31 March 2025. At group level, as on 31 March 2025, Meridian has a commissioned renewable capacity of 900 MW. At group level, Meridian's target is to achieve 5,000 MW of renewable capacity by 2032."

class CatalogAuditTests(unittest.TestCase):  # all SYNTHETIC
    def test_issuer_primary_source_confirms_keys_and_yields_moderate_with_one_group(self):
        with tempfile.TemporaryDirectory() as d:
            t = setup(d, {"ar": snapshot(OK)}, [entry("ar", "Meridian")]); f, problems = run(t)
            self.assertEqual([], problems); self.assertEqual(("supported_finding", "Moderate"), (f["finding_status"], f["evidence_strength"]))
            keys = [a for a in f["audit_trail"] if a["key"]]; self.assertTrue(all(a["effective_outcome"] == "confirmed" and a["effective_level"] == "primary_source" and a["independent_confirming_groups"] == 1 for a in keys))
            self.assertTrue(any("independent source group" in r for r in f["downgrade_reasons"])); self.assertTrue(all(i["claim_verification_status"] == "unverified" for i in map(lambda c: c, [json.loads(l) for l in (t / "claims.jsonl").read_text().splitlines()])))
    def test_independent_regulator_source_makes_it_strong_but_issuer_copies_do_not(self):
        with tempfile.TemporaryDirectory() as d:
            t = setup(d, {"ar": snapshot(OK), "reg": REG}, [entry("ar", "Meridian"), entry("reg", "Energy Regulator", cls="regulator")]); f, _ = run(t)
            self.assertEqual("Strong", f["evidence_strength"]); self.assertEqual(2, f["verification_summary"]["min_independent_groups"])
        with tempfile.TemporaryDirectory() as d:
            t = setup(d, {"ar": snapshot(OK), "ex": snapshot(OK).replace("Page 7", "Page 70")}, [entry("ar", "Meridian"), entry("ex", "Stock Exchange", cls="exchange_announcement", issuer=True)]); f, _ = run(t)
            self.assertEqual("Moderate", f["evidence_strength"]); self.assertEqual(1, f["verification_summary"]["min_independent_groups"])   # exchange-hosted issuer filing is not independent
        with tempfile.TemporaryDirectory() as d:
            t = setup(d, {"ar": snapshot(OK), "deck": snapshot(OK).replace("Page 7", "Page 9")}, [entry("ar", "Meridian"), entry("deck", "Meridian IR", cls="official_filing", derived=["ar"])]); f, _ = run(t)
            self.assertEqual("Moderate", f["evidence_strength"])   # derived-from document counts once
    def test_conflicting_primary_sources_downgrade_and_stay_visible(self):
        with tempfile.TemporaryDirectory() as d:
            t = setup(d, {"ar": snapshot(OK), "reg": REG.replace("1,800 MW of renewable projects", "1,100 MW of renewable projects")}, [entry("ar", "Meridian"), entry("reg", "Energy Regulator", cls="regulator")]); f, _ = run(t)
            self.assertEqual("provisional_hypothesis", f["finding_status"]); self.assertNotEqual("Strong", f["evidence_strength"])
            self.assertTrue(any(a["conflict"] for a in f["audit_trail"])); self.assertTrue(any("Energy Regulator" in e["statement"] or "reg" in e["statement"] for e in f["contradictory_evidence"])); self.assertTrue(any("conflicting" in r for r in f["downgrade_reasons"]))
    def test_key_input_contradicted_by_its_only_primary_source_rejects_the_finding(self):
        with tempfile.TemporaryDirectory() as d:
            t = setup(d, {"reg": REG.replace("1,800 MW of renewable projects", "1,100 MW of renewable projects")}, [entry("reg", "Energy Regulator", cls="regulator")]); f, problems = run(t)
            self.assertEqual(([], "no_defensible_signal", "None"), (problems, f["finding_status"], f["evidence_strength"])); self.assertIsNotNone(f["rejected_hypothesis"]); self.assertIn("re_pipeline_jv_sub", f["rejected_hypothesis"]["failed_inputs"])
            self.assertTrue(f["contradictory_evidence"]); self.assertTrue(any("REJECTED" in x for x in f["decision_log"])); self.assertEqual([], f["calculations"])
    def test_pinned_hash_mismatch_rejects_the_source_and_downgrades(self):
        with tempfile.TemporaryDirectory() as d:
            t = setup(d, {"ar": snapshot(OK)}, [entry("ar", "Meridian", sha256="0" * 64)]); f, _ = run(t)
            st = json.loads((t / "run" / "source_catalog_status.json").read_text()); self.assertEqual("hash_mismatch", st[0]["status"])
            self.assertEqual(("provisional_hypothesis", "Weak"), (f["finding_status"], f["evidence_strength"])); self.assertTrue(any("hash" in str(a["unavailable_sources"]) for a in f["audit_trail"]))
    def test_undated_or_unattested_source_is_not_primary(self):
        with tempfile.TemporaryDirectory() as d:
            t = setup(d, {"ar": snapshot(OK)}, [entry("ar", "Meridian", publication_date=None)]); f, _ = run(t)
            self.assertEqual(("provisional_hypothesis", "Weak"), (f["finding_status"], f["evidence_strength"])); self.assertTrue(all(a["effective_level"] == "extracted_text_review" for a in f["audit_trail"]))
    def test_failed_non_key_input_cannot_raise_strength_or_reject(self):
        with tempfile.TemporaryDirectory() as d:
            t = setup(d, {"reg": REG.replace("5,000 MW", "9,000 MW")}, [entry("reg", "Energy Regulator", cls="regulator")], key_overrides={"re_target": False, "installed_total_group": False, "re_installed_group": False}); f, _ = run(t)
            tgt = next(a for a in f["audit_trail"] if a["role"] == "re_target"); self.assertFalse(tgt["key"]); self.assertEqual("contradicted", tgt["effective_outcome"])
            self.assertNotEqual("no_defensible_signal", f["finding_status"])
            self.assertNotIn("re_installed_plus_pipeline_vs_target", [c["name"] for c in f["calculations"]])   # contradicted input excluded from calculations
    def test_url_only_entries_are_not_fetched_without_network_permission_and_fetched_with_it(self):
        with tempfile.TemporaryDirectory() as d:
            e = entry("ar", "Meridian", url="https://reports.meridian.example/ar.txt"); e.pop("local_path"); t = setup(d, {}, [e]); cat = json.loads((t / "catalog.json").read_text()); cat["official_domains"] = ["meridian.example"]; (t / "catalog.json").write_text(json.dumps(cat))
            calls = []
            def fetcher(urls, out):
                calls.append(urls); p = Path(out) / "sources" / "ar.txt"; p.parent.mkdir(parents=True, exist_ok=True); p.write_text(snapshot(OK))
                return {"sources": [{"requested_url": urls[0], "retrieval_status": "retrieved", "source_sha256": "h", "saved_path": str(p), "publication_date": "2025-06-30", "retrieved_at": "t", "canonical_url": urls[0], "company_association_status": "verified", "warnings": []}]}
            f, _ = run(t, "off", fetcher=fetcher); self.assertEqual([], calls); self.assertEqual("Weak", f["evidence_strength"])
            f2, _ = run(t, "on", fetcher=fetcher, allow_network=True); self.assertEqual(1, len(calls)); self.assertEqual("Moderate", f2["evidence_strength"]); self.assertEqual("simulated", {s["stage"]: s["execution"] for s in f2["stage_provenance"]}["source_catalog"])
    def test_catalog_validation(self):
        base = {"sources": [entry("a", "P")]}
        with self.assertRaises(ValueError): SC.load({"sources": [entry("a", "P"), entry("a", "Q")]})
        with self.assertRaises(ValueError): SC.load({"sources": [entry("a", "P", derived=["zzz"])]})
        with self.assertRaises(ValueError): SC.load({"official_domains": ["x.example"], "sources": [entry("a", "P", url="https://evil.example/a", local_path=None)]})
        with self.assertRaises(ValueError): SC.load({"sources": [entry("a", "P", source_class="blog")]})
        SC.load(base)
    def test_company_mismatch_catalog_is_refused(self):
        with tempfile.TemporaryDirectory() as d:
            t = setup(d, {"ar": snapshot(OK)}, [entry("ar", "Meridian")]); cat = json.loads((t / "catalog.json").read_text()); cat["company"] = "Other Limited"; (t / "catalog.json").write_text(json.dumps(cat))
            with self.assertRaises(ValueError): run(t)
    def test_audit_trail_maps_every_key_input_to_results_and_the_finding_validates(self):
        with tempfile.TemporaryDirectory() as d:
            t = setup(d, {"ar": snapshot(OK)}, [entry("ar", "Meridian")]); f, _ = run(t); validate_against(f, "finding")
            ids = {r["verification_id"] for r in json.loads((t / "run" / "verification_results.json").read_text())}
            for a in f["audit_trail"]:
                self.assertTrue(a["results"] and {r["verification_id"] for r in a["results"]} <= ids); self.assertTrue(all(r["passage_sha256"] for r in a["results"] if r["level"] == "primary_source"))
            self.assertTrue(f["decision_log"]); self.assertEqual(f["verification_summary"]["key_inputs"], sum(a["key"] for a in f["audit_trail"]))
    def test_one_command_prints_the_verification_table(self):
        with tempfile.TemporaryDirectory() as d:
            t = setup(d, {"ar": snapshot(OK)}, [entry("ar", "Meridian")]); buf = io.StringIO()
            with redirect_stdout(buf): rc = P.main(["--company", "Meridian Power Limited", "--claims", str(t / "claims.jsonl"), "--evidence", str(t / "evidence.jsonl"), "--inputs", str(t / "inputs.json"), "--registry", str(t / "registry.json"),
                                                  "--catalog", str(t / "catalog.json"), "--run-dir", str(t / "cli"), "--simulate-llm", "--synthetic"])
            out = buf.getvalue(); self.assertEqual(0, rc); self.assertIn("primary_source", out); self.assertIn("confirmed", out); self.assertIn("supported_finding", out)
    def test_no_document_url_is_hardcoded_in_pipeline_code(self):
        for f in SRC_DIR.glob("*.py"):
            if f.name in ("public_sources.py", "evidence_ingestion.py", "f1_research_angle_selector.py"): continue
            urls = re.findall(r"https?://[A-Za-z][^\s\"')|]+", f.read_text())
            self.assertEqual([], [u for u in urls if not any(x in u for x in ("w3.org", "json-schema", "example", "synthetic", "claude.com", "generativelanguage.googleapis.com"))], f.name)

if __name__ == "__main__": unittest.main()
