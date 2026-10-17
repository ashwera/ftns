import hashlib
import json
import re
import tempfile
import unittest
from pathlib import Path

from signalforge.claim_extraction import PARSER_VERSION, TargetCompany, extract_claims, run_extraction
from signalforge.f1_research_angle_selector import validate_output

SCHEMA = Path(__file__).resolve().parents[1] / "schemas/claim.schema.json"

def rec(text, n=1, **kw):
    r = {"evidence_id": "ev_" + f"{n:024x}", "source_path": "CSV/annual reports/fixture.csv", "page_number": 7, "company_name": "NTPC Limited", "company_identity_status": "verified",
         "excerpt_or_fact": text, "parsing_status": "parsed"}
    r.update(kw); return r

def claims_for(text, **kw): return extract_claims(rec(text, **kw), "doc_fixture")

class ExtractionTests(unittest.TestCase):
    def test_simple_capacity_claim_with_as_of_date(self):
        [c] = claims_for("The installed capacity of NTPC stood at 59,413 MW as on March 31, 2025.")
        validate_output(c, SCHEMA)
        self.assertEqual((c["metric"], c["value"], c["unit"], c["raw_unit_text"]), ("installed_capacity", 59413, "MW", "MW"))
        self.assertEqual((c["period_type"], c["as_of_date"], c["raw_period_text"]), ("as_of", "2025-03-31", "as on March 31, 2025"))
        self.assertEqual(("extracted", "unverified", "NTPC Limited"), (c["extraction_status"], c["claim_verification_status"], c["entity"]))
        self.assertEqual(PARSER_VERSION, c["parser_version"])
    def test_indian_number_formats_and_scales_are_not_converted(self):
        [a] = claims_for("Revenue from operations was Rs. 1,23,456.78 crore for the year ended 31 March 2025.")
        self.assertEqual((a["value"], a["raw_value_text"], a["unit"]), (123456.78, "Rs. 1,23,456.78", "INR crore"))
        self.assertEqual((a["period_type"], a["period_end"]), ("duration", "2025-03-31")); self.assertIsNone(a["period_start"])
        [b] = claims_for("Borrowings stood at Rs. 12,34,567 lakh.")
        self.assertEqual((b["value"], b["unit"]), (1234567, "INR lakh"))
    def test_backtick_currency_is_flagged_not_trusted(self):
        [c] = claims_for("Enterprise value of ` 19,500 crore was disclosed.")
        self.assertEqual("needs_review", c["extraction_status"]); self.assertIn("backtick", c["ambiguity_notes"])
    def test_multiple_claims_in_one_chunk_have_distinct_ids(self):
        text = "Installed capacity was 100 MW. Gross generation was 50 BU. Dividend was Rs. 5 crore. PLF was 70%. Borrowings were Rs. 9 crore."
        cs = claims_for(text); self.assertEqual(5, len(cs)); self.assertEqual(5, len({c["claim_id"] for c in cs}))
        self.assertEqual(["installed_capacity", "generation", "dividend", "plant_load_factor", "borrowings"], [c["metric"] for c in cs])
    def test_missing_unit_stays_null_and_bare_numbers_are_ignored(self):
        [c] = claims_for("Total borrowings were 5,000 crore.")
        self.assertIsNone(c["unit"]); self.assertEqual("crore", c["raw_unit_text"]); self.assertEqual("needs_review", c["extraction_status"])
        self.assertEqual([], claims_for("The company reached 59,413 by year end."))
    def test_missing_period_is_null_and_noted(self):
        [c] = claims_for("Installed capacity was 100 MW.")
        self.assertEqual("unknown", c["period_type"]); self.assertTrue(all(c[k] is None for k in ("period_start", "period_end", "as_of_date", "raw_period_text")))
        self.assertIn("no period", c["ambiguity_notes"])
    def test_period_from_other_sentence_is_ambiguous_and_fy_not_converted(self):
        [c] = claims_for("Quarter ended 30 June 2026. Installed capacity was 100 MW.")
        self.assertEqual(("ambiguous", "quarter", "2026-06-30"), (c["extraction_status"], c["period_type"], c["period_end"]))
        [f] = claims_for("In FY 2024-25 the PLF was 70%.")
        self.assertEqual(("financial_year", None, None, "FY 2024-25"), (f["period_type"], f["period_start"], f["period_end"], f["raw_period_text"]))
    def test_flow_figure_does_not_borrow_the_following_as_on_date(self):
        cs = claims_for("During FY 2024-25 the company added 335 MW and reached 59,413 MW as on 31 March 2025.")
        self.assertEqual(("financial_year", "as_of"), (cs[0]["period_type"], cs[1]["period_type"]))
    def test_negative_percent_and_percentage_points(self):
        [n] = claims_for("Profit for the year was Rs. (2.04) crore.")
        self.assertEqual((n["value"], n["raw_value_text"]), (-2.04, "Rs. (2.04)")); self.assertIn("negative", n["ambiguity_notes"])
        [p] = claims_for("PLF was -5.5% last year.")
        self.assertEqual((p["value"], p["unit"]), (-5.5, "percent"))
        [pp] = claims_for("PLF improved by 2.5 percentage points.")
        self.assertEqual("percentage_points", pp["unit"])
    def test_detached_label_is_not_confidently_assigned(self):
        [c] = claims_for("1,500 MW")
        self.assertIsNone(c["metric"]); self.assertEqual("needs_review", c["extraction_status"])
    def test_table_fragment_multiplicative_pronoun_and_other_entity_are_flagged(self):
        ts = claims_for("71.2% 68.4% 65.1% 70.3% 69.9%")
        self.assertEqual(5, len(ts)); self.assertTrue(all("table fragment" in t["ambiguity_notes"] and t["extraction_status"] == "needs_review" for t in ts))
        [m] = claims_for("Capacity of 4x700 MW is under construction.")
        self.assertIn("multiplicative", m["ambiguity_notes"])
        [p] = claims_for("It has 2,123 MW operational capacity.")
        self.assertIn("pronoun", p["ambiguity_notes"])
        [o] = claims_for("NEEPCO operates stations with installed capacity of 2,057 MW.")
        self.assertEqual("needs_review", o["extraction_status"]); self.assertIn("NEEPCO", o["ambiguity_notes"])
    def test_wider_scope_sentence_is_ambiguous(self):
        [c] = claims_for("India added nearly 29 GW of renewable capacity.")
        self.assertEqual("needs_review", c["extraction_status"]); self.assertIn("national/industry-scope", c["ambiguity_notes"])
    def test_empty_and_narrative_chunks_yield_nothing(self):
        self.assertEqual([], claims_for("")); self.assertEqual([], claims_for("The company places safety first."))
    def test_unresolved_entity_is_not_invented(self):
        [c] = claims_for("Installed capacity was 100 MW.", company_name=None, company_identity_status="unresolved")
        self.assertIsNone(c["entity"]); self.assertEqual("unresolved", c["entity_identity_status"])
    def test_excerpt_is_contiguous_source_text(self):
        text = "Intro text.\nInstalled capacity was\n100 MW at year end. Other text."
        [c] = claims_for(text); self.assertIn(c["source_excerpt"], re.sub(r"\s+", " ", text))

SELF = "Your Company"
def one(text, **kw):
    cs = claims_for(text, **kw); assert len(cs) == 1, cs; return cs[0]

class PrecisionRuleTests(unittest.TestCase):
    """Feature X: `extracted` needs subject, metric, unit, period and temporal status to all be explicit."""
    def test_fully_explicit_statement_is_extracted_with_entity(self):
        c = one("Your Company reported an installed capacity of 500 MW as on 31 March 2024.")
        self.assertEqual(("extracted", "NTPC Limited", "installed_capacity", "2024-03-31"), (c["extraction_status"], c["entity"], c["metric"], c["as_of_date"]))
    def test_subject_not_stated_is_ambiguous_and_entity_null(self):
        c = one("Installed capacity was 100 MW as on 31 March 2025.")
        self.assertEqual(("ambiguous", None), (c["extraction_status"], c["entity"])); self.assertIn("subject is not stated", c["ambiguity_notes"])
    def test_no_target_means_no_attribution(self):
        c = extract_claims(rec("Your Company reported an installed capacity of 500 MW as on 31 March 2024."), "d", target=None)[0]
        self.assertEqual(("ambiguous", None), (c["extraction_status"], c["entity"]))
    def test_forward_looking_is_never_extracted_and_never_an_installed_metric(self):
        for text in ["Your Company has set a target to reach installed capacity of 130 GW by 2032.", "Your Company expects to commission 800 MW of wind capacity as on 31 March 2028.", "Your Company plans an installed capacity of 10 GW."]:
            c = one(text); self.assertEqual("ambiguous", c["extraction_status"], text); self.assertNotIn(c["metric"], ("installed_capacity", "commercial_capacity", "capacity_commissioned"))
        self.assertEqual("capacity_target", one("Your Company aims to have 60 GW of installed capacity by 2032.")["metric"])
    def test_target_company_is_supplied_not_hardcoded(self):
        t = TargetCompany("Meridian Power Limited", ("Meridian",))
        rc = rec("Meridian reported an installed capacity of 500 MW as on 31 March 2024.", company_name="Meridian Power Limited")
        [c] = extract_claims(rc, "d", target=t); self.assertEqual(("extracted", "Meridian Power Limited"), (c["extraction_status"], c["entity"]))
        [o] = extract_claims(rec("Your Company reported an installed capacity of 500 MW as on 31 March 2024.", company_name="Meridian Power Limited"), "d", target=TargetCompany("Other Holdings Limited"))
        self.assertEqual("extracted", o["extraction_status"])  # generic self-reference still resolves to the supplied target, whatever its name
        [n] = extract_claims(rec("NTPC Limited reported an installed capacity of 500 MW as on 31 March 2024.", company_name="Meridian Power Limited"), "d", target=t)
        self.assertEqual(("needs_review", None), (n["extraction_status"], n["entity"])); self.assertIn("NTPC Limited", n["ambiguity_notes"])
    def test_other_organizations_are_found_structurally_without_an_allowlist(self):
        for text, name in [("Zephyr Hydro Private Limited has an installed capacity of 120 MW as on 31 March 2024, says Your Company.", "Zephyr Hydro Private Limited"),
                           ("ZORBA operates an installed capacity of 120 MW as on 31 March 2024 according to Your Company.", "ZORBA")]:
            c = one(text); self.assertEqual("needs_review", c["extraction_status"]); self.assertIn(name, c["ambiguity_notes"])
    def test_national_wording_before_the_figure_blocks_extraction_but_comparator_pairs_split(self):
        cs = claims_for("Your Company achieved an average PLF of 77.44% in FY25, higher than the national average of 69.96% for coal plants.")
        by = {c["value"]: c for c in cs}; self.assertEqual("extracted", by[77.44]["extraction_status"]); self.assertEqual("needs_review", by[69.96]["extraction_status"])
    def test_group_or_consolidated_basis_is_not_the_standalone_figure(self):
        cs = claims_for("As on 31 March 2025, the total commercial capacity of Your Company stood at 79,930 MW on a consolidated basis and 59,413 MW on a standalone basis.")
        by = {c["value"]: c for c in cs}
        self.assertEqual(("ambiguous", None), (by[79930]["extraction_status"], by[79930]["entity"])); self.assertEqual("extracted", by[59413]["extraction_status"])
    def test_joint_venture_and_subsidiary_wording_needs_review(self):
        c = one("Your Company's joint venture commissioned 1320 MW of capacity as on 31 March 2025.")
        self.assertEqual("needs_review", c["extraction_status"])
    def test_stock_metric_needs_an_as_on_date(self):
        c = one("Your Company's installed capacity was 100 MW in FY25.")
        self.assertEqual("ambiguous", c["extraction_status"]); self.assertIn("as on/at", c["ambiguity_notes"])
    def test_generic_capacity_is_not_specific_enough(self):
        c = one("Your Company's capacity of 100 MW was noted as on 31 March 2025.")
        self.assertEqual("ambiguous", c["extraction_status"]); self.assertEqual("capacity", c["metric"])
    def test_scale_is_not_inferred_when_the_chunk_mentions_scale_elsewhere(self):
        c = one("Your Company's dividend was Rs. 4,000.00 in FY25 (amounts in Rs. crore).")
        self.assertEqual(("INR", "ambiguous"), (c["unit"], c["extraction_status"])); self.assertIn("scale", c["ambiguity_notes"])
        self.assertEqual("INR crore", one("Your Company's dividend was Rs. 4,000.00 crore in FY25.")["unit"])
    def test_percent_change_rate_is_not_a_level(self):
        cs = claims_for("Your Company's coal production grew with year-on-year growth of 29%, to 45.82 MMT in FY25.")
        by = {c["value"]: c for c in cs}; self.assertEqual("needs_review", by[29]["extraction_status"]); self.assertIsNone(by[29]["metric"])
    def test_fraction_partial_status_needs_review(self):
        c = one("Your Company's 23 MW Solapur project (10/23 commissioned) is in service.")
        self.assertEqual("needs_review", c["extraction_status"]); self.assertIn("fraction", c["ambiguity_notes"])
    def test_embedded_capitalized_sentence_start_flags_interleaving(self):
        c = one("As on 31 March 2025, The details of the plans taken by Your Company projects with a total capacity of 33,671 MW are under implementation.")
        self.assertIn("interleaving", c["ambiguity_notes"]); self.assertNotEqual("extracted", c["extraction_status"])
    def test_parallel_comparative_inherits_label_but_intervening_figure_blocks_other_labels(self):
        cs = claims_for("Your Company's installed capacity reached 59,413 MW as on 31 March 2025 against 59,078 MW as on 31 March 2024.")
        self.assertEqual([("installed_capacity", "2025-03-31"), ("installed_capacity", "2024-03-31")], [(c["metric"], c["as_of_date"]) for c in cs])
        c = claims_for("Your Company added 335 MW. Separately the board met on 5 March 2025 and noted 12 MW.")
        self.assertIsNone(next(x for x in c if x["value"] == 12)["metric"])
    def test_bullet_scope_shares_subject_but_paragraph_sentences_do_not(self):
        bullet = claims_for("• The captive coal production rose to 45.82 MMT in FY25. This strengthened fuel security for the Company's operations.")
        self.assertEqual("extracted", bullet[0]["extraction_status"])
        para = claims_for("Your Company is large. The captive coal production rose to 45.82 MMT in FY25.")
        self.assertEqual("ambiguous", para[0]["extraction_status"])
    def test_all_claims_stay_unverified(self):
        for c in claims_for("Your Company reported an installed capacity of 500 MW as on 31 March 2024."): self.assertEqual("unverified", c["claim_verification_status"])

class PipelineTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(); self.addCleanup(self.tmp.cleanup); self.root = Path(self.tmp.name)
        self.inp, self.out = self.root / "in", self.root / "out"; self.inp.mkdir()
    def store(self, records, source_records=None):
        (self.inp / "evidence.jsonl").write_text("".join((json.dumps(r) if isinstance(r, dict) else r) + "\n" for r in records), encoding="utf-8")
        if source_records is not None: (self.inp / "source_records.jsonl").write_text("".join(json.dumps(r) + "\n" for r in source_records), encoding="utf-8")
    def lines(self, name): return [json.loads(l) for l in (self.out / name).read_text(encoding="utf-8").splitlines() if l.strip()]
    def test_provenance_is_preserved_and_report_distinguishes_outcomes(self):
        r1, r2, r3 = rec("Installed capacity was 100 MW.", 1), rec("", 2, parsing_status="empty"), rec("Narrative only.", 3)
        self.store([r1, r2, r3], [{"evidence_id": r1["evidence_id"], "source_sha256": "ab" * 32}])
        claims, rep = run_extraction(self.inp, self.out)
        [c] = claims
        self.assertEqual((r1["evidence_id"], "doc_" + "ab" * 8, 7, r1["source_path"]), (c["source_chunk_id"], c["source_document_id"], c["source_page"], c["source_path"]))
        self.assertEqual((3, 3, 0, 2, 1, 1, 1), (rep["input_record_count"], rep["processed_chunk_count"], rep["failed_chunk_count"], rep["chunks_with_zero_claims"], rep["zero_claims_empty_or_unparsed"], rep["zero_claims_no_extractable_claim"], rep["total_claims"]))
        self.assertEqual("completed", rep["run_status"])
    def test_missing_provenance_and_bad_json_are_failures_not_silent_drops(self):
        bad = rec("Your Company's installed capacity was 100 MW as on 31 March 2025.", 1); del bad["evidence_id"]
        self.store([bad, "{not json", rec("Your Company's installed capacity was 100 MW as on 31 March 2025.", 2)])
        claims, rep = run_extraction(self.inp, self.out)
        self.assertEqual((3, 1, 2, 1), (rep["input_record_count"], rep["processed_chunk_count"], rep["failed_chunk_count"], len(claims)))
        self.assertEqual("completed_with_failures", rep["run_status"])
        self.assertEqual({"chunk_failure", "input_error"}, {q["kind"] for q in self.lines("review_queue.jsonl")})
    def test_malformed_and_schema_invalid_extractor_output_never_enters_claims(self):
        good = extract_claims(rec("Installed capacity was 100 MW.", 1), "d")[0]
        invalid = dict(good, claim_id="cl1_" + "0" * 24, extraction_status="verified")
        wrong_chunk = dict(good, claim_id="cl1_" + "1" * 24, source_chunk_id="ev_" + "f" * 24)
        self.store([rec("x", 1)])
        claims, rep = run_extraction(self.inp, self.out, extractor=lambda r, d: ["garbage", invalid, wrong_chunk, good])
        self.assertEqual([good["claim_id"]], [c["claim_id"] for c in claims]); self.assertEqual(3, rep["schema_validation_failures"])
        self.assertEqual(3, sum(q["kind"] == "invalid_claim" for q in self.lines("review_queue.jsonl")))
    def test_extractor_exception_is_a_chunk_failure(self):
        self.store([rec("x", 1)])
        def boom(r, d): raise RuntimeError("boom")
        _, rep = run_extraction(self.inp, self.out, extractor=boom); self.assertEqual((1, 0), (rep["failed_chunk_count"], rep["processed_chunk_count"]))
    def test_duplicates_ids_stable_across_reruns_and_overwrite_policy(self):
        self.store([rec("Installed capacity was 100 MW. Dividend was Rs. 5 crore.", 1)])
        good = extract_claims(rec("Installed capacity was 100 MW.", 1), "d")[0]
        _, rep = run_extraction(self.inp, self.out, extractor=lambda r, d: [good, dict(good)]); self.assertEqual(1, rep["duplicate_claims_skipped"])
        a, _ = run_extraction(self.inp, self.out, overwrite=True); first = (self.out / "claims.jsonl").read_bytes()
        b, _ = run_extraction(self.inp, self.out, overwrite=True)
        self.assertEqual([x["claim_id"] for x in a], [x["claim_id"] for x in b]); self.assertEqual(first, (self.out / "claims.jsonl").read_bytes())
        with self.assertRaises(ValueError): run_extraction(self.inp, self.out)
    def test_input_store_untouched_and_output_dir_must_differ(self):
        self.store([rec("Installed capacity was 100 MW.", 1)])
        before = hashlib.sha256((self.inp / "evidence.jsonl").read_bytes()).hexdigest()
        run_extraction(self.inp, self.out)
        self.assertEqual(before, hashlib.sha256((self.inp / "evidence.jsonl").read_bytes()).hexdigest())
        self.assertEqual({"evidence.jsonl"}, {p.name for p in self.inp.iterdir()})
        with self.assertRaises(ValueError): run_extraction(self.inp, self.inp, overwrite=True)
    def test_flagged_claims_are_queued_for_review(self):
        self.store([rec("1,500 MW", 1), rec("Your Company's installed capacity was 100 MW as on 31 March 2025.", 2)])
        claims, rep = run_extraction(self.inp, self.out)
        self.assertEqual(1, rep["claims_by_status"]["extracted"]); self.assertEqual(1, rep["claims_needing_attention"])
        [q] = self.lines("review_queue.jsonl"); self.assertEqual(("claim_review", "needs_review"), (q["kind"], q["extraction_status"]))
    def test_missing_input_file_errors(self):
        with self.assertRaises(FileNotFoundError): run_extraction(self.inp, self.out)

if __name__ == "__main__": unittest.main()
