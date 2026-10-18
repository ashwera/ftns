import unittest

from signalforge.claim_verification import assess_independence, assertion_from_claim, locate_passages, verify_assertion
from signalforge.pipeline_contract import ClaimStore, validate_against

P = "As on 31 March 2025, the total commercial capacity stood at 79,930 MW on a consolidated basis and 59,413 MW on a standalone basis. Your Company reported it. Targets: your Company aims to reach 130 GW by 2032."
BASE = dict(value=59413, unit="MW", period_type="as_of", as_of_date="2025-03-31", period_text="As on 31 March 2025", basis="standalone", statement_status="actual", label_terms=["commercial capacity"], entity="NTPC Limited", entity_names=["NTPC"])

def ver(passage=P, **over):
    return verify_assertion({**BASE, **over}, passage, verification_id="v1", input_name="x", source={"source_chunk_id": "ev_" + "a" * 24, "source_path": "doc.csv", "page": 90})

class VerificationTests(unittest.TestCase):
    def test_correct_match_is_confirmed_at_text_review_level_with_limitation(self):
        r = ver(); self.assertEqual("confirmed", r["outcome"]); self.assertEqual("extracted_text_review", r["verification_level"])
        self.assertTrue(all(c["result"] in ("match", "not_applicable") for c in r["checks"].values())); self.assertIn("not primary-source", r["limitations"][0]); self.assertTrue(r["rationale"])
    def test_wrong_value_is_contradicted_with_the_passage_values(self):
        r = ver(value=59000); self.assertEqual("contradicted", r["outcome"]); self.assertEqual("mismatch", r["checks"]["value"]["result"]); self.assertIn("59413", " ".join(r["discrepancies"]))
    def test_wrong_period(self):
        r = ver(as_of_date="2024-03-31", period_text="As on 31 March 2024"); self.assertEqual(("contradicted", "mismatch"), (r["outcome"], r["checks"]["period"]["result"]))
    def test_wrong_unit_or_scale(self):
        self.assertEqual("mismatch", ver(unit="GW")["checks"]["unit_scale"]["result"])
        r = verify_assertion({**BASE, "value": 4000.0, "unit": "INR crore", "basis": None, "statement_status": None, "label_terms": [], "period_text": None, "as_of_date": None, "entity": None}, "Rs. 4,000.00 was raised.", verification_id="v", input_name="x")
        self.assertEqual("mismatch", r["checks"]["unit_scale"]["result"]); self.assertEqual("contradicted", r["outcome"])
    def test_wrong_entity_other_organization_without_target(self):
        r = ver("As on 31 March 2025, NEEPCO Limited reported commercial capacity of 59,413 MW on a standalone basis."); self.assertEqual("mismatch", r["checks"]["entity"]["result"]); self.assertEqual("contradicted", r["outcome"])
    def test_other_organization_next_to_the_target_is_unresolved_not_contradicted(self):
        r = ver("As on 31 March 2025, Your Company's commercial capacity was 59,413 MW on a standalone basis, while NGEL Limited is separate."); self.assertEqual("unresolved", r["checks"]["entity"]["result"]); self.assertEqual("partially_supported", r["outcome"])
    def test_group_re_pipeline_uses_value_sentence_not_nearby_dvc_umrepp_sentence(self):
        assertion = {"value": 14.5, "unit": "GW", "period_type": "as_of", "as_of_date": "2025-03-31",
                     "period_text": "As on 31 March 2025", "basis": "group", "statement_status": "under_implementation",
                     "label_terms": ["RE capacity"], "entity": "NTPC Limited", "entity_names": ["NTPC"]}
        passage = ("As on 31 March 2025, RE capacity of NTPC under various stages of implementation totals up to 14.5 GW. "
                   "RE projects with a cumulative capacity of 14.5 GW are under execution which includes Solar, Wind and energy storage projects. "
                   "UMREPP at Gujarat (4.75 GW), DVC (0.7 GW), and Madhya Pradesh (0.6 GW).")
        r = verify_assertion(assertion, passage, verification_id="v_group", input_name="re_under_implementation_group")
        self.assertEqual("match", r["checks"]["metric_definition"]["result"])
        self.assertEqual("match", r["checks"]["entity"]["result"])
        self.assertEqual("match", r["checks"]["period"]["result"])
        self.assertEqual("match", r["checks"]["unit_scale"]["result"])
        hits = locate_passages([{"page": 112, "text": passage}], 14.5, ["RE capacity"])
        self.assertIn("RE capacity of NTPC", hits[0]["passage"])
    def test_group_re_pipeline_still_rejects_genuine_dvc_entity_mismatch(self):
        assertion = {"value": 14.5, "unit": "GW", "period_type": "as_of", "as_of_date": "2025-03-31",
                     "period_text": "As on 31 March 2025", "basis": "group", "statement_status": "under_implementation",
                     "label_terms": ["RE capacity"], "entity": "NTPC Limited", "entity_names": ["NTPC"]}
        r = verify_assertion(assertion, "As on 31 March 2025, DVC's RE capacity under implementation is 14.5 GW.",
                             verification_id="v_dvc", input_name="re_under_implementation_group")
        self.assertEqual("mismatch", r["checks"]["entity"]["result"])
        self.assertEqual("contradicted", r["outcome"])
    def test_consolidated_versus_standalone_mismatch_both_ways(self):
        self.assertEqual("mismatch", ver(basis="consolidated")["checks"]["basis"]["result"])
        r = ver(value=79930, basis="standalone"); self.assertEqual(("contradicted", "mismatch"), (r["outcome"], r["checks"]["basis"]["result"]))
        self.assertEqual("confirmed", ver(value=79930, basis="consolidated")["outcome"])
    def test_forecast_mistaken_for_actual(self):
        r = verify_assertion({**BASE, "value": 130, "unit": "GW", "as_of_date": None, "period_text": "2032", "basis": None, "statement_status": "actual", "label_terms": []}, P, verification_id="v", input_name="x")
        self.assertEqual(("contradicted", "mismatch"), (r["outcome"], r["checks"]["statement_status"]["result"]))
        ok = verify_assertion({**BASE, "value": 130, "unit": "GW", "as_of_date": None, "period_text": "2032", "basis": None, "statement_status": "target", "label_terms": []}, P, verification_id="v", input_name="x")
        self.assertEqual("match", ok["checks"]["statement_status"]["result"])
    def test_insufficient_evidence(self):
        r = ver("Nothing about capacity here."); self.assertEqual("unable_to_verify", r["outcome"])
        r2 = ver("The commercial capacity was 59,413 MW."); self.assertIn(r2["outcome"], ("partially_supported", "unresolved")); self.assertNotEqual("confirmed", r2["outcome"])
    def test_contradictory_sources_stay_visible_and_are_not_averaged(self):
        a = ver("As on 31 March 2025, Your Company's commercial capacity was 59,413 MW on a standalone basis.")
        b = ver("As on 31 March 2025, Your Company's commercial capacity was 58,000 MW on a standalone basis.")
        self.assertEqual(("confirmed", "contradicted"), (a["outcome"], b["outcome"])); self.assertIn("58000", b["rationale"] + " ".join(b["discrepancies"]))
    def test_cross_checks_are_internal_and_never_independent(self):
        r = verify_assertion({**BASE, "basis": None}, P + " Total (II) 18,295", verification_id="v", input_name="x", cross_checks=[{"description": "t", "label_regex": "Total \\(II\\)", "expected_value": 18295}])
        self.assertTrue(r["cross_checks"][0]["ok"]); self.assertFalse(r["cross_checks"][0]["independent"])
    def test_results_validate_and_claims_are_not_mutated(self):
        claim = {"claim_id": "cl1_" + "a" * 24, "value": 59413, "unit": "MW", "period_type": "as_of", "as_of_date": "2025-03-31", "raw_period_text": "As on 31 March 2025", "raw_metric_text": "commercial capacity", "entity": "NTPC Limited", "claim_verification_status": "unverified"}
        before = dict(claim); a = assertion_from_claim(claim, basis="standalone"); r = verify_assertion(a, P, verification_id="v", input_name="x", claim_id=claim["claim_id"])
        validate_against(r, "verification_result"); self.assertEqual(before, claim)
        with self.assertRaises(ValueError): ClaimStore([{**claim, "claim_verification_status": "confirmed"}])

class IndependenceTests(unittest.TestCase):
    def test_mirrors_same_publisher_and_derived_documents_count_once(self):
        ar = {"publisher": "issuer", "document_family": "ar24", "sha256": "h1", "derived_from": []}
        mirror = dict(ar, publisher="mirror site")
        deck = {"publisher": "issuer", "document_family": "deck", "sha256": "h2", "derived_from": ["ar24"]}
        ext = {"publisher": "regulator", "document_family": "cea", "sha256": "h3", "derived_from": []}
        self.assertEqual(1, assess_independence([ar, mirror, deck])["independent_source_count"]); self.assertEqual(1, assess_independence([ar, mirror, deck])["mirror_copies_removed"])
        self.assertEqual(2, assess_independence([ar, deck, ext])["independent_source_count"])

if __name__ == "__main__": unittest.main()
