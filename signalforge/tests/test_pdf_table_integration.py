import copy, json, tempfile, unittest
from pathlib import Path
from signalforge import claim_verification as V
from signalforge import pipeline as P
from signalforge import pdf_table_extraction as T

ROOT = Path(__file__).resolve().parents[1]
FIX = json.loads((ROOT / "tests" / "fixtures" / "pdf_tables" / "ntpc_ar_2024_25_pdf_p91_layout.json").read_text(encoding="utf-8"))
SHA = FIX["provenance"]["pdf_sha256"]
DOC = {"sha256": SHA, "path": "Annual Report 2024-25_1.pdf", "document_id": "pdfdoc_" + SHA[:16]}
EVIDENCE = ROOT / "data" / "processed_step6" / "evidence.jsonl"
REGISTRY = ROOT / "data" / "company_registry.json"
EV91 = "ev_2484a0e981c95b1829d91ac3"

def evidence_records():
    return [json.loads(l) for l in EVIDENCE.read_text(encoding="utf-8").splitlines() if l.strip()]

def table_claims():
    recs = evidence_records()
    tables = T.table_structure(copy.deepcopy(FIX["layout"]))
    return T.claims_from_table(tables[0], doc=DOC, pdf_page_index=91, entity="NTPC Limited", entity_status="verified", evidence_records=recs)

def claim(label, scope):
    return next(c for c in table_claims() if c["raw_metric_text"] == label and c["ownership_scope"] == scope)

def chunk_text(): return next(r["excerpt_or_fact"] for r in evidence_records() if r["evidence_id"] == EV91)

def assertion(c, basis, status="under_implementation", **over):
    a = V.assertion_from_claim(c, basis=basis, statement_status=status, label_terms=[]); a["entity"] = "NTPC Limited"; a.update(over); return a

def verify(c, basis, text=None, **over):
    return V.verify_table_cell(assertion(c, basis, **over), c, text if text is not None else chunk_text(), verification_id="v", input_name="n", claim_id=c["claim_id"])

class TableCellVerificationTests(unittest.TestCase):
    def test_parent_renewable_725_is_supported_in_reading_order_with_only_the_entity_open(self):
        r = verify(claim("c) Renewable Energy Projects", "parent_owned"), "standalone")
        self.assertEqual("partially_supported", r["outcome"])
        self.assertEqual({k: "match" for k in ("value", "unit_scale", "metric_definition", "period", "basis", "statement_status")}, {k: r["checks"][k]["result"] for k in r["checks"] if k != "entity"})
        self.assertEqual("unresolved", r["checks"]["entity"]["result"])

    def test_jv_renewable_13791_is_checked_under_the_jv_heading(self):
        r = verify(claim("c) Renewable Projects", "jv_subsidiary"), "jv_subsidiary_part")
        self.assertEqual(("partially_supported", "match"), (r["outcome"], r["checks"]["basis"]["result"])); self.assertIn("II Projects under JVs", r["checks"]["basis"]["detail"])

    def test_totals_and_group_total_verify(self):
        for label, scope, basis in (("Total (I)", "parent_owned", "standalone"), ("Total (II)", "jv_subsidiary", "jv_subsidiary_part"), ("Total On-Going Projects as on 31 March 2025 (I)+(II)", "group", "group")):
            r = verify(claim(label, scope), basis)
            self.assertEqual("partially_supported", r["outcome"], (label, r["checks"], r["rationale"]))

    def test_a_passage_that_starts_below_the_heading_is_unresolved_not_contradicted(self):
        text = chunk_text(); cut = text.index("c) Renewable Energy Projects")
        r = verify(claim("c) Renewable Energy Projects", "parent_owned"), "standalone", text=text[cut:])
        self.assertEqual(("unresolved", "partially_supported"), (r["checks"]["basis"]["result"], r["outcome"]))

    def test_value_under_the_wrong_heading_is_a_scope_contradiction(self):
        c = dict(claim("c) Renewable Projects", "jv_subsidiary"), section_heading="I Owned by your Company", ownership_scope="parent_owned")
        r = verify(c, "standalone")
        self.assertEqual(("contradicted", "mismatch"), (r["outcome"], r["checks"]["basis"]["result"]))

    def test_same_label_different_number_under_the_same_heading_contradicts(self):
        c = dict(claim("c) Renewable Energy Projects", "parent_owned"), value=726.0, raw_value_text="726")
        r = verify(c, "standalone"); self.assertEqual(("contradicted", "mismatch"), (r["outcome"], r["checks"]["value"]["result"]))

    def test_unknown_row_or_value_is_unable_to_verify_not_confirmed(self):
        c = dict(claim("c) Renewable Energy Projects", "parent_owned"), raw_metric_text="d) Wind Projects", row_label_first_line="d) Wind Projects")
        self.assertEqual("unable_to_verify", verify(c, "standalone")["outcome"])
        self.assertEqual("unable_to_verify", verify(claim("Total (I)", "parent_owned"), "standalone", text="")["outcome"])

    def test_unit_and_period_come_from_the_source_not_the_claim(self):
        c = claim("Total (I)", "parent_owned")
        self.assertEqual("mismatch", verify(dict(c, unit="GW"), "standalone", unit="GW")["checks"]["unit_scale"]["result"])
        self.assertEqual("mismatch", verify(c, "standalone", as_of_date="2024-03-31")["checks"]["period"]["result"])

    def test_basis_inconsistent_with_table_scope_is_flagged(self):
        r = verify(claim("c) Renewable Energy Projects", "parent_owned"), "jv_subsidiary_part")
        self.assertEqual(("contradicted", "mismatch"), (r["outcome"], r["checks"]["basis"]["result"]))

class ClaimStoreTests(unittest.TestCase):
    def write(self, d, name, rows):
        p = Path(d) / name; p.write_text("".join(json.dumps(r) + "\n" for r in rows)); return p

    def test_extra_claims_are_additive_and_unlinked_ones_are_skipped_loudly(self):
        base = [{"claim_id": "cl1_" + "a" * 24, "claim_verification_status": "unverified", "source_chunk_id": "ev_" + "b" * 24}]
        extra = [dict(c, claim_verification_status="unverified") for c in table_claims()]; extra[0] = dict(extra[0], source_chunk_id=None)
        with tempfile.TemporaryDirectory() as d:
            store = P.load_claim_store(self.write(d, "b.jsonl", base), self.write(d, "e.jsonl", extra))
        self.assertEqual((1 + len(extra) - 1, 1), (len(store.claims), len(store.extra_skipped))); self.assertEqual(extra[0]["claim_id"], store.extra_skipped[0])
        with self.assertRaises(KeyError): store.get(extra[0]["claim_id"])

    def test_baseline_claims_without_a_chunk_are_refused(self):
        with tempfile.TemporaryDirectory() as d:
            with self.assertRaises(ValueError): P.load_claim_store(self.write(d, "b.jsonl", [{"claim_id": "cl1_" + "a" * 24, "claim_verification_status": "unverified", "source_chunk_id": None}]))

    def test_duplicate_ids_and_verified_claims_are_refused(self):
        extra = [dict(c) for c in table_claims()]
        with tempfile.TemporaryDirectory() as d:
            with self.assertRaises(ValueError): P.load_claim_store(self.write(d, "b.jsonl", [dict(extra[0], claim_id=extra[0]["claim_id"])]), self.write(d, "e.jsonl", extra))
            with self.assertRaises(ValueError): P.load_claim_store(self.write(d, "b2.jsonl", []), self.write(d, "e2.jsonl", [dict(extra[0], claim_verification_status="verified")]))

class EndToEndTests(unittest.TestCase):
    ROLES = (("pipeline_total_group", "group", "Total On-Going Projects as on 31 March 2025 (I)+(II)", "group", True), ("pipeline_jv_sub", "jv_subsidiary", "Total (II)", "jv_subsidiary_part", True),
             ("re_pipeline_jv_sub", "jv_subsidiary", "c) Renewable Projects", "jv_subsidiary_part", True), ("pipeline_parent", "parent_owned", "Total (I)", "standalone", True),
             ("re_pipeline_parent", "parent_owned", "c) Renewable Energy Projects", "standalone", True))

    def test_direct_parent_figures_drive_the_shares_and_the_709_residual_is_not_used(self):
        claims = table_claims()
        spec = {"schema": "pipeline_inputs/1.0", "company": "NTPC Limited", "reference_year": 2026, "hypothesis_id": "H1_renewable_pipeline_location", "reviewer": {"kind": "ai_assisted_analyst", "id": "test", "note": "fixture"}, "inputs": []}
        for role, scope, label, basis, key in self.ROLES:
            c = next(x for x in claims if x["raw_metric_text"] == label and x["ownership_scope"] == scope)
            spec["inputs"].append({"role": role, "name": role, "claim_id": c["claim_id"], "as_of_date": "2025-03-31", "period_text": "As on 31 March 2025", "basis": basis, "statement_status": "under_implementation", "label_terms": [], "rounding_uncertainty": None, "key": key})
        # the two group renewable roles are absent here, so the finding cannot compute a group renewable share; the parent and JV shares come from table cells
        with tempfile.TemporaryDirectory() as d:
            t = Path(d); (t / "claims.jsonl").write_text("".join(json.dumps(c) + "\n" for c in claims)); (t / "inputs.json").write_text(json.dumps(spec))
            f, problems = P.run_pipeline("NTPC Limited", t / "claims.jsonl", EVIDENCE, t / "inputs.json", t / "run", registry_path=REGISTRY, simulate_llm=True)
        self.assertEqual([], problems)
        calc = {c["name"]: c["result"]["value"] for c in f["calculations"] if c["result"]}
        self.assertAlmostEqual(725 / 15376 * 100, calc["re_share_of_parent_own_pipeline"], places=4); self.assertAlmostEqual(13791 / 18295 * 100, calc["re_share_of_jv_subsidiary_pipeline"], places=4)
        names = {i["name"] for i in f["inputs"]}
        self.assertNotIn("parent_re_under_implementation", names); self.assertNotIn(709.0, [i["value"] for i in f["inputs"]])
        self.assertEqual(("provisional_hypothesis", "Weak"), (f["finding_status"], f["evidence_strength"])); self.assertTrue(f["all_claims_unverified"])
        self.assertTrue(all(a["claim_verification_status"] == "unverified" and a["effective_outcome"] == "partially_supported" for a in f["audit_trail"]))

    # The residual fallback (whole minus part when no direct parent role exists) is covered by the synthetic-company end-to-end tests,
    # which have no direct parent roles and still compute the 20% parent share from the residual.

if __name__ == "__main__": unittest.main()
