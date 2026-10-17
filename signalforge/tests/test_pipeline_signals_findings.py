import unittest

from signalforge import findings as FD
from signalforge import signals as S
from signalforge.pipeline_contract import ClaimStore

def ver(outcome="confirmed", level="extracted_text_review", vid="v", cross=()):
    return {"verification_id": vid, "outcome": outcome, "verification_level": level, "cross_checks": list(cross), "claim_id": "cl1_" + "a" * 24}

def inp(name, value, unit="MW", asof="2025-03-31", basis="group", status="under_implementation", outcome="confirmed", rounding=None):
    return S.make_input(name, value, unit, as_of=asof, period_text=asof, basis=basis, status=status, claim_ids=["cl1_" + name.encode().hex()[:24].ljust(24, "0")], verification=ver(outcome, vid="v_" + name), rounding=rounding)

class SignalTests(unittest.TestCase):  # all inputs here are SYNTHETIC
    def test_ratio_value_trace_units_and_gw_conversion(self):
        c = S.ratio_signal("renewable_transition", "share", inp("re", 2.0, "GW"), inp("tot", 4000), counterargument="c", falsification_test="f", synthetic=True, basis_relation={("group", "group")}, status_pairs={("under_implementation", "under_implementation")})
        self.assertEqual(("computed", 50.0), (c["status"], c["result"]["value"])); self.assertIn("2000", c["trace"]); self.assertTrue(c["synthetic"]); self.assertTrue(all(i["claim_ids"] and i["verification_ids"] for i in c["inputs"]))
    def test_rounding_bounds_are_carried(self):
        c = S.ratio_signal("renewable_transition", "share", inp("re", 14.5, "GW", rounding=0.05), inp("tot", 33671), counterargument="c", falsification_test="f", basis_relation={("group", "group")}, status_pairs={("under_implementation", "under_implementation")})
        self.assertAlmostEqual(43.06, c["result"]["value"], 2); self.assertLess(c["result"]["lower_bound"], c["result"]["value"]); self.assertGreater(c["result"]["upper_bound"], c["result"]["value"])
    def test_incompatible_inputs_are_not_computed(self):
        base = dict(counterargument="c", falsification_test="f", basis_relation={("group", "group")}, status_pairs={("under_implementation", "under_implementation")})
        cases = [("unit", inp("a", 10, "MW"), inp("b", 10, "MWh")), ("date", inp("a", 10), inp("b", 10, asof="2024-03-31")), ("basis", inp("a", 10), inp("b", 10, basis="standalone")),
                 ("status", inp("a", 10, status="target"), inp("b", 10)), ("unverified", inp("a", 10, outcome="contradicted"), inp("b", 10))]
        for name, a, b in cases:
            c = S.ratio_signal("renewable_transition", name, a, b, **base); self.assertEqual("not_computable", c["status"], name); self.assertIsNone(c["result"]); self.assertTrue(c["missing_inputs"])
    def test_zero_denominator(self):
        c = S.ratio_signal("renewable_transition", "z", inp("a", 10), inp("b", 0), counterargument="c", falsification_test="f", basis_relation={("group", "group")}, status_pairs={("under_implementation", "under_implementation")})
        self.assertEqual("not_computable", c["status"]); self.assertIn("denominator", c["missing_inputs"][0])
    def test_composition_sum_check_and_difference_input(self):
        parts = [inp("coal", 60), inp("re", 40)]; ok = S.composition_signal("renewable_transition", "mix", parts, inp("total", 100), counterargument="c", falsification_test="f")
        self.assertEqual("computed", ok["status"]); self.assertIn("re = 40.0000%", ok["trace"])
        bad = S.composition_signal("renewable_transition", "mix", parts, inp("total", 120), counterargument="c", falsification_test="f"); self.assertEqual("not_computable", bad["status"])
        d = S.difference_input("parent", inp("whole", 100), inp("part", 30), basis="parent_own"); self.assertEqual(70, d["value"]); self.assertEqual(2, len(d["claim_ids"]))
        with self.assertRaises(ValueError): S.difference_input("x", inp("whole", 10), inp("part", 30), basis="b")
        with self.assertRaises(ValueError): S.difference_input("x", inp("whole", 10), inp("part", 3, asof="2024-03-31"), basis="b")
    def test_growth_and_target_coverage(self):
        g = S.growth_signal("g", inp("cur", 120, asof="2025-03-31", basis="standalone", status="actual"), inp("pri", 100, asof="2024-03-31", basis="standalone", status="actual"), counterargument="c", falsification_test="f")
        self.assertAlmostEqual(20.0, g["result"]["value"]); self.assertEqual("not_computable", S.growth_signal("g", inp("cur", 1, basis="a", status="actual"), inp("pri", 1, basis="b", status="actual"), counterargument="c", falsification_test="f")["status"])
        t = S.target_coverage_signal("cov", [inp("done", 5, status="commissioned"), inp("wip", 15, status="under_implementation")], inp("target", 100, status="target"), counterargument="c", falsification_test="f")
        self.assertAlmostEqual(20.0, t["result"]["value"]); self.assertEqual("not_computable", S.target_coverage_signal("cov", [inp("done", 5)], inp("target", 100, status="actual"), counterargument="c", falsification_test="f")["status"])
    def test_calculations_are_reproducible(self):
        a = S.ratio_signal("renewable_transition", "s", inp("a", 10), inp("b", 40), counterargument="c", falsification_test="f", basis_relation={("group", "group")}, status_pairs={("under_implementation", "under_implementation")})
        b = S.ratio_signal("renewable_transition", "s", inp("a", 10), inp("b", 40), counterargument="c", falsification_test="f", basis_relation={("group", "group")}, status_pairs={("under_implementation", "under_implementation")})
        self.assertEqual(a, b)

def calc(value=70.0, ok=True):
    a, b = inp("a", 4), inp("b", 80); c = S.ratio_signal("renewable_transition", "s", a, b, counterargument="c", falsification_test="f", synthetic=True, basis_relation={("group", "group")}, status_pairs={("under_implementation", "under_implementation")})
    return c

def src(pub, fam, sha=None, derived=()): return {"publisher": pub, "document_family": fam, "sha256": sha or fam, "derived_from": list(derived)}

class FindingTests(unittest.TestCase):  # SYNTHETIC scenarios
    def adjudicate(self, verifs, sources, effect=60.0, contradictory=(), calcs=None, store_inputs=None):
        inputs = store_inputs if store_inputs is not None else [{"name": "a", "value": 4.0, "unit": "MW", "as_of_date": "2025-03-31", "basis": "group", "statement_status": "under_implementation", "claim_ids": ["cl1_" + "a" * 24], "verification_ids": ["v1"], "verification_outcome": "confirmed",
                   "verification_level": "extracted_text_review", "citation": {"source_chunk_id": "ev_" + "a" * 24, "source_path": "x", "page": 1, "locator": None, "excerpt": "zzz unmatched", "url": None}}]
        return FD.adjudicate(finding_id="f", run_id="r", company={"name": "Synthco", "aliases": [], "identity_status": "config_only"}, headline="Synthetic 5.0", why_it_matters="w", materiality_pp=effect, inputs=inputs, verifications=verifs,
                             calculations=calcs if calcs is not None else [calc()], sources=sources, supporting_evidence=[], contradictory_evidence=list(contradictory), alternative_explanations=["alt"], falsification_conditions=["f"], stage_provenance=[{"stage": "t", "execution": "real", "detail": "d"}],
                             claims_all_unverified=True, synthetic=True, reference_year=2026)
    def test_strong_requires_primary_source_independence_and_crosschecks(self):
        v = [ver("confirmed", "primary_source", cross=[{"ok": True, "independent": True}])]
        f = self.adjudicate(v, [src("issuer", "ar"), src("regulator", "cea")]); self.assertEqual(("Strong", "supported_finding"), (f["evidence_strength"], f["finding_status"]))
    def test_moderate_single_primary_source(self):
        f = self.adjudicate([ver("confirmed", "primary_source")], [src("issuer", "ar")]); self.assertEqual(("Moderate", "supported_finding"), (f["evidence_strength"], f["finding_status"]))
    def test_weak_text_only_evidence_is_provisional_and_capped(self):
        f = self.adjudicate([ver("confirmed")], [src("issuer", "ar")]); self.assertEqual(("Weak", "provisional_hypothesis"), (f["evidence_strength"], f["finding_status"])); self.assertLess(f["rank_score"], 50); self.assertTrue(any("Provisional" in l for l in f["limitations"]))
        p = self.adjudicate([ver("partially_supported")], [src("issuer", "ar")]); self.assertEqual("Weak", p["evidence_strength"])
    def test_contradiction_blocks_publication_and_lowers_score(self):
        f = self.adjudicate([ver("confirmed", "primary_source"), ver("contradicted", "primary_source", vid="v2")], [src("issuer", "ar")]); self.assertEqual(("None", "no_defensible_signal"), (f["evidence_strength"], f["finding_status"]))
        g = self.adjudicate([ver("confirmed", "primary_source")], [src("issuer", "ar")], contradictory=[{"statement": "x", "claim_ids": [], "citation": {"source_chunk_id": None, "source_path": None, "page": None, "locator": None, "excerpt": "x", "url": None}, "independent": False}])
        self.assertEqual("no_defensible_signal", g["finding_status"])
    def test_duplicate_and_mirrored_documents_do_not_inflate_strength(self):
        mirrors = [src("issuer", "ar", "h1"), src("mirror", "ar-copy", "h1"), src("issuer", "deck", "h2", derived=["ar"])]
        f = self.adjudicate([ver("confirmed", "primary_source", cross=[{"ok": True, "independent": False}])], mirrors); self.assertEqual("Moderate", f["evidence_strength"])
    def test_missing_denominator_unsupported_hypothesis_and_immaterial_effect(self):
        bad = S.ratio_signal("renewable_transition", "s", inp("a", 4), inp("b", 0), counterargument="c", falsification_test="f", basis_relation={("group", "group")}, status_pairs={("under_implementation", "under_implementation")})
        self.assertEqual("None", self.adjudicate([ver("confirmed", "primary_source")], [src("issuer", "ar")], calcs=[bad])["evidence_strength"])
        small = self.adjudicate([ver("confirmed", "primary_source")], [src("issuer", "ar")], effect=2.0); self.assertEqual("no_defensible_signal", small["finding_status"]); self.assertLessEqual(small["rank_score"], 10)
        none = FD.no_signal_finding(finding_id="n", run_id="r", company={"name": "X", "aliases": [], "identity_status": "config_only"}, reason="no data", missing_evidence=["everything"], stage_provenance=[{"stage": "s", "execution": "not_executed", "detail": "d"}]); self.assertEqual("None", none["evidence_strength"])
    def test_ranking_prefers_stronger_better_corroborated_evidence(self):
        a = FD.rank("Moderate", 40, 1, 1.0, 2025, 2026, 0)[0]; b = FD.rank("Weak", 40, 1, 1.0, 2025, 2026, 0)[0]; c = FD.rank("Moderate", 40, 1, 1.0, 2025, 2026, 1)[0]
        self.assertGreater(a, b); self.assertGreater(a, c); self.assertGreater(FD.rank("Moderate", 40, 1, 1.0, 2025, 2026, 0)[0], FD.rank("Moderate", 40, 1, 1.0, 2018, 2026, 0)[0])
    def test_traceability_catches_unknown_claims_bad_excerpts_and_unmapped_numbers(self):
        claim = {"claim_id": "cl1_" + "a" * 24, "claim_verification_status": "unverified"}; store = ClaimStore([claim])
        f = self.adjudicate([ver("confirmed")], [src("issuer", "ar")]); f["headline"] = "Share is 5.0 and 99.9"
        problems = FD.check_traceability(f, store, {"ev_" + "a" * 24: {"excerpt_or_fact": "different text"}})
        self.assertTrue(any("99.9" in p for p in problems)); self.assertTrue(any("not in chunk" in p for p in problems))
        f["inputs"][0]["claim_ids"] = ["cl1_" + "b" * 24]; self.assertTrue(any("unknown claim" in p for p in FD.check_traceability(f, store)))

if __name__ == "__main__": unittest.main()
