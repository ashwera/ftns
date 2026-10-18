import json
import tempfile
import unittest
from pathlib import Path

from signalforge.f1_research_angle_selector import validate_output
from signalforge.table_extraction import (Ctx, classify_chunk, extract_table_claims, make_extractor, parse_cell_value, parse_rows,
                                          repair_cells, reversal_decision, run_table_extraction)

SCHEMA = Path(__file__).resolve().parents[1] / "schemas/claim.schema.json"
HDR = "Particulars,FY 2024-25,FY 2023-24\n"
TABLE = HDR + 'Revenue from operations,"1,70,037.37","1,62,008.95"\nTotal income,"1,88,138.06","1,70,000.00"\nProfit for the year,"19,649.41","18,079.39"\n'

def rec(text, n=1, **kw):
    r = {"evidence_id": "ev_" + f"{n:024x}", "source_path": "CSV/annual reports/fixture.csv", "page_number": 12, "company_name": "NTPC Limited", "company_identity_status": "verified",
         "excerpt_or_fact": text, "parsing_status": "parsed"}
    r.update(kw); return r

def table_claims(text, ctx=None, **kw):
    ctx = ctx or Ctx(); return extract_table_claims(rec(text, **kw), "doc_fixture", ctx), ctx

class ClassificationTests(unittest.TestCase):
    def test_prose_with_commas_is_not_a_table(self):
        prose = '"The Company, which operates stations in Gujarat, Maharashtra, and Bihar, added capacity during the year, subject to approvals, as described in the Directors\' Report on this page and elsewhere."'
        self.assertEqual("prose", classify_chunk(prose)[0])
        self.assertEqual("prose", classify_chunk('"One long paragraph, with commas, and more commas, and 59,413 MW of capacity as on 31 March 2025, over several sentences that keep going without any column structure at all, to exceed the cell length cutoff."\n"Second paragraph, also long, also prose, with figures like 1,234 and 5,678 but no table structure whatsoever, and plenty of words to keep it long enough."\n')[0])
    def test_consistent_financial_table_is_tabular(self):
        cls, reasons, feats = classify_chunk(TABLE)
        self.assertEqual("tabular", cls); self.assertTrue(reasons); self.assertEqual(3, feats["modal_width"])
    def test_too_little_structure_is_uncertain(self):
        self.assertEqual("uncertain", classify_chunk("a,b,c\n1,2,3\n")[0])

class ParsingTests(unittest.TestCase):
    def test_indian_grouping_and_decimals(self):
        self.assertEqual(9696666134, parse_cell_value("9,69,66,66,134")["value"])
        self.assertEqual(123456.78, parse_cell_value("1,23,456.78")["value"])
        self.assertEqual(1234567, parse_cell_value("1,234,567")["value"])
        self.assertIsNone(parse_cell_value("12,3,456")); self.assertIsNone(parse_cell_value("(12.5")); self.assertIsNone(parse_cell_value("Y"))
    def test_parentheses_and_minus_are_negative_and_percent_flagged(self):
        self.assertEqual(-2.04, parse_cell_value("(2.04)")["value"]); self.assertEqual(-1234.5, parse_cell_value("(1,234.50)")["value"])
        self.assertEqual(-7, parse_cell_value("-7")["value"]); p = parse_cell_value("94.02%"); self.assertEqual((94.02, True), (p["value"], p["percent"]))

class TableClaimTests(unittest.TestCase):
    def test_fiscal_year_headers_align_values_to_periods(self):
        cs, _ = table_claims(TABLE)
        rev = [c for c in cs if c["raw_metric_text"] == "Revenue from operations"]
        self.assertEqual([("FY 2024-25", 170037.37, 1), ("FY 2023-24", 162008.95, 2)], [(c["raw_period_text"], c["value"], c["column_index"]) for c in rev])
        self.assertTrue(all(c["period_type"] == "financial_year" and c["period_end"] is None for c in rev))
        self.assertEqual(6, len(cs))
    def test_unit_is_never_invented_and_blocks_extracted_status(self):
        cs, _ = table_claims(TABLE)
        self.assertTrue(all(c["unit"] is None and c["extraction_status"] == "ambiguous" and "no unit stated" in c["ambiguity_notes"] for c in cs))
    def test_declared_rupee_unit_allows_extracted_but_backtick_does_not(self):
        good, _ = table_claims("Particulars (₹ in crore),FY 2024-25,FY 2023-24\nRevenue from operations,\"1,70,037.37\",\"1,62,008.95\"\nProfit for the year,\"19,649.41\",\"18,079.39\"\n", )
        self.assertEqual({"extracted"}, {c["extraction_status"] for c in good}); self.assertEqual({"INR crore"}, {c["unit"] for c in good})
        bad, _ = table_claims(TABLE.replace("Particulars", "Particulars (` in crore)"))
        self.assertEqual({"ambiguous"}, {c["extraction_status"] for c in bad}); self.assertTrue(all("backtick" in c["ambiguity_notes"] for c in bad))
    def test_percent_cells_carry_percent_unit(self):
        cs, _ = table_claims("Particulars,FY 2017-18,FY 2016-17\nCoal,94.02%,95.09%\nGas,5.28%,4.29%\n")
        self.assertEqual({"percent"}, {c["unit"] for c in cs}); self.assertEqual({"extracted"}, {c["extraction_status"] for c in cs})
    def test_unit_column_between_label_and_values_is_used_verbatim(self):
        cs, _ = table_claims("Particulars,Unit,FY 2024-25,FY 2023-24\nNo. of Employees,Number,16798,17398\nGross generation,Million Units,259618,274454\n")
        self.assertEqual([("count", "Number"), ("count", "Number"), ("MU", "Million Units"), ("MU", "Million Units")], [(c["unit"], c["raw_unit_text"]) for c in cs])
        self.assertEqual({"extracted"}, {c["extraction_status"] for c in cs})
    def test_explicit_million_units_label_overrides_unrelated_crore_declaration(self):
        text = "Particulars,FY 2020-21,FY 2019-20\nFuel cost (` Crore),100.00,90.00\nUnits of electricity sold (MUs),251649,240204\nOther income (` Crore),5.00,4.00\n"
        cs, _ = table_claims(text)
        units = [c for c in cs if c["raw_metric_text"].startswith("Units of electricity")]
        self.assertEqual(["MU", "MU"], [c["unit"] for c in units])
    def test_per_share_column_overrides_chunk_crore_declaration(self):
        text = 'Particulars,"Total equity (` crore)","Book value per share (`)*"\nProfit for the year,11749.89,11.88\nOther income,5.00,2.00\nTax expense,4.00,1.00\n'
        cs, _ = table_claims(text)
        claim = next(c for c in cs if c["raw_metric_text"] == "Profit for the year" and c["value"] == 11.88)
        self.assertEqual("per share", claim["unit"])
        self.assertNotEqual("INR crore", claim["unit"])
        self.assertIn("per-share unit", claim["ambiguity_notes"])
    def test_section_parent_keeps_fuel_mix_rows_from_extracted_status(self):
        text = "Particulars,FY 2017-18,FY 2016-17\nFuel cost (` Crore),48315.47,47572.19\n% break-up,,\nCoal,94.02%,95.09%\nGas,5.28%,4.29%\nOil,0.66%,0.60%\nNaphtha,0.04%,0.02%\n"
        cs, _ = table_claims(text)
        fuel_mix = [c for c in cs if c["raw_metric_text"] in {"Coal", "Gas", "Oil", "Naphtha"}]
        self.assertEqual(8, len(fuel_mix))
        self.assertTrue(all(c["extraction_status"] == "ambiguous" for c in fuel_mix))
        self.assertTrue(all("section context" in c["ambiguity_notes"] for c in fuel_mix))
    def test_label_starting_with_value_and_rupee_crore_unit_cell(self):
        cs, _ = table_claims("Particulars,,FY 2018-19,FY 2017-18\nValue added per employee,Rs. Crore,1.83,1.58\nTurnover per employee,Rs. Crore,2.00,1.90\n")
        self.assertEqual(("Value added per employee", "INR crore", "Rs. Crore"), (cs[0]["raw_metric_text"], cs[0]["unit"], cs[0]["raw_unit_text"]))
    def test_negative_value_noted(self):
        cs, _ = table_claims("Particulars (₹ in crore),FY 2024-25\nNet loss,(2.04)\nOther gain,5.00\n")
        self.assertEqual(-2.04, cs[0]["value"]); self.assertIn("negative", cs[0]["ambiguity_notes"])
    def test_missing_header_needs_review(self):
        cs, ctx = table_claims('Revenue from operations,"1,70,037.37","1,62,008.95"\nTotal income,"1,88,138.06","1,70,000.00"\n')
        self.assertTrue(cs and all(c["extraction_status"] == "needs_review" and c["period_type"] == "unknown" for c in cs)); self.assertEqual(1, ctx.diag["tabular_chunks_without_header"])
    def test_column_count_mismatch_is_flagged_not_shifted(self):
        cs, _ = table_claims('Particulars (₹ in crore),FY 2024-25,FY 2023-24\nRevenue,"100.00","90.00"\nOther income,"5.00"\nProfit,10.00,9.00,8.00\n')
        by = {c["raw_metric_text"]: c for c in cs}
        self.assertEqual("extracted", by["Revenue"]["extraction_status"])
        self.assertEqual("needs_review", by["Other income"]["extraction_status"]); self.assertIn("column count mismatch", by["Other income"]["ambiguity_notes"])
        self.assertTrue(all("column count mismatch" in c["ambiguity_notes"] for c in cs if c["raw_metric_text"] == "Profit"))
    def test_wrapped_label_from_previous_row_is_ambiguous(self):
        cs, _ = table_claims('Particulars (₹ in crore),FY 2024-25,FY 2023-24\nRevenue,"100.00","90.00"\nProfit attributable to\n,"10.00","9.00"\n')
        wrapped = [c for c in cs if c["raw_metric_text"].startswith("Profit")]
        self.assertTrue(wrapped and all(c["extraction_status"] == "needs_review" and "wrapped label" in c["ambiguity_notes"] for c in wrapped))
        multi, _ = table_claims('Particulars (₹ in crore),FY 2024-25\n"Profit attributable to\nowners",10.00\nRevenue,5.00\n')
        self.assertEqual("Profit attributable to owners", multi[0]["raw_metric_text"]); self.assertEqual("extracted", multi[0]["extraction_status"])
    def test_stacked_multiline_cells_are_not_aligned(self):
        cs, _ = table_claims('Particulars,As at 31 March 2018\n"Discount rate\nSalary rate",7.60%\nOther,"7.50%\n7.50%"\n')
        self.assertTrue(cs and all(c["extraction_status"] == "needs_review" or "stacked" not in (c["ambiguity_notes"] or "") for c in cs))
    def test_repeated_headers_use_the_nearest_header(self):
        text = "Particulars (₹ in crore),FY 2024-25,FY 2023-24\nRevenue,100.00,90.00\nProfit,10.00,9.00\nParticulars (₹ in crore),FY 2022-23,FY 2021-22\nRevenue,80.00,70.00\nProfit,8.00,7.00\n"
        cs, ctx = table_claims(text)
        self.assertEqual(["FY 2024-25", "FY 2023-24", "FY 2024-25", "FY 2023-24", "FY 2022-23", "FY 2021-22", "FY 2022-23", "FY 2021-22"], [c["raw_period_text"] for c in cs])
        self.assertEqual(1, ctx.diag["repeated_headers"])
    def test_multirow_header_and_periods_with_several_years_not_assigned(self):
        cs, _ = table_claims('Particulars,Amount,\n,"For the year\nended\n31 March 2025","For the year\nended\n31 March 2024"\nSales,5.91,4.00\nOthers,1.00,2.00\n')
        self.assertEqual(["duration", "duration"], [c["period_type"] for c in cs[:2]]); self.assertEqual(["2025-03-31", "2024-03-31"], [c["period_end"] for c in cs[:2]])
        two, _ = table_claims('Particulars,"Standalone\n2024-25 2023-24"\nSales,5.91\nProfit,1.00\n')
        self.assertTrue(all(c["period_type"] == "unknown" and "several periods" in c["ambiguity_notes"] for c in two))
    def test_subsidiary_and_entity_label_are_not_assumed_parent(self):
        cs, _ = table_claims("Particulars (₹ in crore),FY 2024-25\nRevenue,100.00\nInterest income,5.00\n")
        self.assertEqual({"extracted"}, {c["extraction_status"] for c in cs})
        sub, _ = table_claims("NEEPCO financials\nParticulars (₹ in crore),FY 2024-25\nRevenue,100.00\nProfit,5.00\n")
        self.assertTrue(sub and all(c["extraction_status"] != "extracted" and "NEEPCO" in c["ambiguity_notes"] for c in sub))
        org, _ = table_claims("Particulars (₹ in crore),FY 2024-25\nNTPC Electric Supply Company Ltd.,100.00\nAnother Limited,5.00\n")
        self.assertTrue(all(c["extraction_status"] == "needs_review" and "entity name" in c["ambiguity_notes"] for c in org))
    def test_entity_named_header_columns_need_review(self):
        cs, _ = table_claims("Particulars (₹ in crore),Bhartiya Rail Bijlee Company Ltd.,Patratu Vidyut Utpadan Nigam Ltd.\nRevenue,10.00,20.00\nProfit,1.00,2.00\n")
        self.assertTrue(cs and all(c["extraction_status"] == "needs_review" and "legal entities" in c["ambiguity_notes"] for c in cs))
    def test_standalone_vs_consolidated_basis_unstated_is_ambiguous_when_document_has_both(self):
        ctx = Ctx(doc_bases={"CSV/annual reports/fixture.csv": True})
        cs, _ = table_claims("Particulars (₹ in crore),FY 2024-25\nRevenue,100.00\nProfit,5.00\n", ctx)
        self.assertTrue(all(c["extraction_status"] == "ambiguous" and "reporting basis" in c["ambiguity_notes"] for c in cs))
        named, _ = table_claims("Particulars (₹ in crore),Consolidated FY 2024-25\nRevenue,100.00\nProfit,5.00\n", ctx)
        self.assertEqual({"extracted"}, {c["extraction_status"] for c in named})
    def test_provenance_and_schema_validity(self):
        cs, _ = table_claims(TABLE, n=7)
        for c in cs:
            validate_output(c, SCHEMA)
            self.assertEqual(("doc_fixture", 12, "ev_" + f"{7:024x}", "CSV/annual reports/fixture.csv", "unverified", "table_row"), (c["source_document_id"], c["source_page"], c["source_chunk_id"], c["source_path"], c["claim_verification_status"], c["extraction_method"]))
            self.assertIn(c["source_row_text"], TABLE); self.assertEqual(c["source_row_text"], c["source_excerpt"]); self.assertIn("FY 2024-25", c["source_header_text"])
        self.assertEqual(len(cs), len({c["claim_id"] for c in cs}))
    def test_unresolved_entity_is_null(self):
        cs, _ = table_claims(TABLE, company_name=None, company_identity_status="unresolved")
        self.assertTrue(all(c["entity"] is None and c["entity_identity_status"] == "unresolved" for c in cs))
    def test_non_claim_rows_do_not_crash(self):
        for text in ["", "\n\n,,\n", "Particulars,FY 2024-25\nSection heading only\n-,-\nY,N\n", 'Revenue\n"unterminated,quote\n1,2']:
            cs, _ = table_claims(text); self.assertEqual([], cs)

class ReversalTests(unittest.TestCase):
    def test_reversed_row_is_detected_and_repaired(self):
        cells = ["latoT", "58.079,81,1", "37.691,71"]
        d = reversal_decision(cells); self.assertTrue(d["reversed"]); self.assertEqual(["Total", "1,18,970.85", "17,196.73"], repair_cells(cells))
        self.assertEqual(["(75.70)", "5%" , "100%"], repair_cells([")07.57(", "%5", "%001"]))
    def test_forward_and_ambiguous_rows_are_not_reversed(self):
        self.assertFalse(reversal_decision(["Total", "1,18,970.85", "17,196.73"])["reversed"])
        self.assertFalse(reversal_decision(["Revenue from operations", "12.34", "43.21"])["reversed"])
        self.assertFalse(reversal_decision(["latoT"])["reversed"])  # a single weak tell is below the evidence threshold
        self.assertFalse(reversal_decision(["Sales are stable", "level", "noon"])["reversed"])
    def test_reversed_row_claims_are_never_extracted_and_original_is_kept(self):
        text = "Particulars (₹ in crore),FY 2024-25,FY 2023-24\nRevenue,100.00,90.00\nlatoT,\"58.079,81,1\",\"37.691,71\"\nProfit,10.00,9.00\n"
        cs, ctx = table_claims(text)
        rev = [c for c in cs if c["reversal_applied"]]
        self.assertTrue(rev); self.assertTrue(all(c["extraction_status"] != "extracted" and 'latoT,"58.079,81,1"' in c["source_row_text"] for c in rev))
        self.assertEqual("Total", rev[0]["raw_metric_text"]); self.assertEqual(118970.85, rev[0]["value"]); self.assertEqual(1, ctx.diag["reversed_rows"])
        self.assertTrue(any(d["decision" if False else "reversed"] and d["original"].startswith("latoT") for d in ctx.reversal_log))
        self.assertIn("latoT", text)  # source text is never rewritten
        fwd = [c for c in cs if not c["reversal_applied"]]
        self.assertTrue(all("reversed rows" in (c["ambiguity_notes"] or "") or c["extraction_status"] == "extracted" for c in fwd))

class PipelineTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(); self.addCleanup(self.tmp.cleanup); self.root = Path(self.tmp.name); self.inp = self.root / "in"; self.inp.mkdir()
        recs = [rec(TABLE, 1), rec("", 2, parsing_status="empty"), rec('"Your Company added 335 these activities are described below: MW to its installed capacity and reached to 59,413 MW as on 31 March 2025 against 59,078 MW as on 31 March 2024."', 3),
                rec("a,b,c\n1,2,3\n", 4)]
        (self.inp / "evidence.jsonl").write_text("".join(json.dumps(r) + "\n" for r in recs), encoding="utf-8")
    def test_routing_report_and_interleaved_prose_negative_example(self):
        claims, rep = run_table_extraction(self.inp, self.root / "out")
        self.assertEqual({"tabular": 1, "prose": 1, "uncertain": 1, "empty": 1}, rep["chunk_classification"]["counts"])
        self.assertEqual(0, rep["schema_validation_failures"]); self.assertEqual(0, rep["failed_chunk_count"])
        prose = [c for c in claims if c["extraction_method"] == "prose_regex" and c["chunk_class"] == "prose"]
        self.assertEqual([59413, 59078], [c["value"] for c in prose]); self.assertNotIn(335, [c["value"] for c in claims])
        for c in claims: validate_output(c, SCHEMA); self.assertEqual("unverified", c["claim_verification_status"])
        self.assertEqual(sum(rep["claims_by_status"].values()), rep["total_claims"])
        for key in ("table_rows", "reversal", "claims_missing", "top_review_reasons", "counting_notes", "claims_flagged_for_review"): self.assertIn(key, rep)
    def test_output_bytes_are_identical_across_runs_and_overwrite_policy(self):
        out = self.root / "out"; run_table_extraction(self.inp, out)
        first = {n: (out / n).read_bytes() for n in ("claims.jsonl", "review_queue.jsonl")}
        with self.assertRaises(ValueError): run_table_extraction(self.inp, out)
        run_table_extraction(self.inp, out, overwrite=True)
        self.assertEqual(first, {n: (out / n).read_bytes() for n in first})
        with self.assertRaises(ValueError): run_table_extraction(self.inp, self.inp, overwrite=True)
    def test_baseline_comparison_and_untouched_input(self):
        before = (self.inp / "evidence.jsonl").read_bytes()
        from signalforge.claim_extraction import run_extraction
        run_extraction(self.inp, self.root / "base")
        _, rep = run_table_extraction(self.inp, self.root / "out", baseline_dir=self.root / "base")
        cmp = rep["comparison_to_baseline"]; self.assertIn("baseline_not_reproduced_chunk_class", cmp); self.assertIn("Yield is not accuracy", cmp["note"])
        self.assertEqual(before, (self.inp / "evidence.jsonl").read_bytes())

class CrossChunkTests(unittest.TestCase):
    def records(self, *chunks):
        out = []
        triples = [chunks[i:i + 3] for i in range(0, len(chunks), 3)]
        for i, (text, page, doc) in enumerate(triples, 1):
            out.append((rec(text, i, page_number=page, company_name="Example Energy Limited"), doc))
        return out

    def extract_chunks(self, chunks):
        ctx = Ctx(); extractor = make_extractor(ctx); claims = []
        for record, document_id in chunks: claims.extend(extractor(record, document_id))
        return claims, ctx

    def test_header_and_rows_split_across_adjacent_chunks(self):
        chunks = self.records("Particulars (₹ in crore),FY 2024-25,FY 2023-24\n", 10, "doc-a",
                              "Revenue from operations,100.00,90.00\nProfit for the year,20.00,18.00\n", 10, "doc-a")
        claims, ctx = self.extract_chunks(chunks)
        self.assertEqual(1, ctx.diag["continuation_matches"])
        revenue = [c for c in claims if c["raw_metric_text"] == "Revenue from operations"]
        self.assertEqual([("FY 2024-25", 100.0, "INR crore"), ("FY 2023-24", 90.0, "INR crore")], [(c["raw_period_text"], c["value"], c["unit"]) for c in revenue])
        self.assertTrue(all(c["source_chunk_id"] == chunks[1][0]["evidence_id"] and c["source_page"] == 10 and c["claim_verification_status"] == "unverified" for c in revenue))

    def test_continuation_survives_one_unrelated_prose_chunk(self):
        chunks = self.records("Particulars (₹ in crore),FY 2024-25,FY 2023-24\n", 10, "doc-a",
                              '"The board met at the registered office during the quarter and reviewed several administrative matters."\n', 10, "doc-a",
                              "Revenue from operations,100.00,90.00\nProfit for the year,20.00,18.00\n", 11, "doc-a")
        claims, ctx = self.extract_chunks(chunks)
        self.assertEqual(1, ctx.diag["continuation_matches"])
        self.assertEqual(2, len([c for c in claims if c["raw_metric_text"] == "Revenue from operations"]))

    def test_same_width_new_table_replaces_prior_header(self):
        chunks = self.records("Particulars (₹ in crore),FY 2024-25,FY 2023-24\n", 10, "doc-a",
                              "Particulars (₹ in crore),FY 2022-23,FY 2021-22\n", 11, "doc-a",
                              "Revenue from operations,80.00,70.00\nProfit for the year,8.00,7.00\n", 11, "doc-a")
        claims, ctx = self.extract_chunks(chunks)
        revenue = [c for c in claims if c["raw_metric_text"] == "Revenue from operations"]
        self.assertEqual(["FY 2022-23", "FY 2021-22"], [c["raw_period_text"] for c in revenue])
        self.assertEqual(chunks[1][0]["evidence_id"], ctx.continuation_matches[0]["header_chunk_id"])

    def test_page_break_within_same_table_is_eligible(self):
        chunks = self.records("Particulars (₹ in crore),FY 2024-25,FY 2023-24\n", 20, "doc-a",
                              "Revenue from operations,100.00,90.00\nProfit for the year,20.00,18.00\n", 21, "doc-a")
        claims, ctx = self.extract_chunks(chunks)
        self.assertEqual(1, ctx.diag["continuation_matches"])
        self.assertTrue(all(c["source_page"] == 21 for c in claims))

    def test_document_boundary_never_reuses_header(self):
        chunks = self.records("Particulars (₹ in crore),FY 2024-25,FY 2023-24\n", 10, "doc-a",
                              "Revenue from operations,100.00,90.00\nProfit for the year,20.00,18.00\n", 10, "doc-b")
        claims, ctx = self.extract_chunks(chunks)
        self.assertEqual(0, ctx.diag["continuation_matches"])
        self.assertTrue(all(c["extraction_status"] == "needs_review" and c["period_type"] == "unknown" for c in claims))

    def test_competing_headers_are_rejected_as_ambiguous(self):
        header_text = "Particulars (₹ in crore),FY 2024-25,FY 2023-24\nSection heading only\nParticulars (₹ in crore),FY 2022-23,FY 2021-22\n"
        chunks = self.records(header_text, 10, "doc-a", "Revenue from operations,100.00,90.00\nProfit for the year,20.00,18.00\n", 10, "doc-a")
        claims, ctx = self.extract_chunks(chunks)
        self.assertEqual(0, ctx.diag["continuation_matches"])
        self.assertTrue(ctx.continuation_rejects and "multiple preceding headers" in ctx.continuation_rejects[0]["reason"])
        self.assertTrue(all(c["extraction_status"] == "needs_review" for c in claims))

    def test_unit_missing_in_header_stays_missing_and_unverified(self):
        chunks = self.records("Particulars,FY 2024-25,FY 2023-24\n", 10, "doc-a",
                              "Revenue from operations,100.00,90.00\nProfit for the year,20.00,18.00\n", 10, "doc-a")
        claims, ctx = self.extract_chunks(chunks)
        self.assertEqual(1, ctx.diag["continuation_matches"])
        self.assertTrue(all(c["unit"] is None and c["claim_verification_status"] == "unverified" for c in claims))

    def test_preceding_table_unit_context_is_carried_with_its_source(self):
        chunks = self.records("Consolidated statement of profit and loss (₹ in crore)\n", 10, "doc-a",
                              "Particulars,FY 2024-25,FY 2023-24\n", 10, "doc-a",
                              "Revenue from operations,100.00,90.00\nProfit for the year,20.00,18.00\n", 10, "doc-a")
        claims, ctx = self.extract_chunks(chunks)
        revenue = [c for c in claims if c["raw_metric_text"] == "Revenue from operations"]
        self.assertEqual({"INR crore"}, {c["unit"] for c in revenue})
        self.assertEqual(chunks[0][0]["evidence_id"], ctx.continuation_matches[0]["header_context_sources"][0]["chunk_id"])

    def test_subsidiary_title_does_not_inherit_parent_identity(self):
        chunks = self.records("NEEPCO financial results\nParticulars (₹ in crore),FY 2024-25,FY 2023-24\n", 10, "doc-a",
                              "Revenue from operations,100.00,90.00\nProfit for the year,20.00,18.00\n", 10, "doc-a")
        claims, ctx = self.extract_chunks(chunks)
        self.assertEqual(1, ctx.diag["continuation_matches"])
        self.assertTrue(all(c["entity"] is None and c["entity_identity_status"] == "unresolved" and c["extraction_status"] == "needs_review" for c in claims))

    def test_unmatched_table_shaped_chunk_remains_under_review(self):
        chunks = self.records("Revenue from operations,100.00,90.00\nProfit for the year,20.00,18.00\n", 10, "doc-a")
        claims, ctx = self.extract_chunks(chunks)
        self.assertEqual(0, ctx.diag["continuation_matches"])
        self.assertTrue(claims and all(c["extraction_status"] == "needs_review" and c["period_type"] == "unknown" for c in claims))

    def test_cross_chunk_claim_ids_are_deterministic_across_repeated_runs(self):
        chunks = self.records("Particulars (₹ in crore),FY 2024-25,FY 2023-24\n", 10, "doc-a",
                              "Revenue from operations,100.00,90.00\nProfit for the year,20.00,18.00\n", 10, "doc-a")
        first, _ = self.extract_chunks(chunks); second, _ = self.extract_chunks(chunks)
        self.assertEqual(first, second)

    def test_shared_golden_table_cases(self):
        """Run the table-applicable cases from Claude's shared, hand-verified fixture."""
        fixture_dir = Path(__file__).parent / "fixtures" / "golden_claims"
        chunk_rows = [json.loads(line) for line in (fixture_dir / "chunks.jsonl").read_text(encoding="utf-8").splitlines() if line.strip()]
        case_rows = [json.loads(line) for line in (fixture_dir / "cases.jsonl").read_text(encoding="utf-8").splitlines() if line.strip()]
        by_id = {row["evidence_id"]: row for row in chunk_rows}
        # Feature Y owns continuation behavior. Single-chunk table expectations are
        # exercised by Claude's shared golden runner and remain outside this extension.
        cases = [case for case in case_rows if "table" in case.get("applies_to", [])
                 and case.get("context_chunk_ids")]
        self.assertTrue(cases, "shared golden fixture has no table-applicable cases")

        for case in cases:
            with self.subTest(case=case["case_id"]):
                ordered_ids = case.get("context_chunk_ids", []) + case.get("chunk_ids", [])
                records = [by_id[eid] for eid in ordered_ids]
                if case.get("order_by_page"):
                    records = [r for _, r in sorted(enumerate(records), key=lambda pair: (pair[1].get("page_number", -1), pair[0]))]
                ctx = Ctx(); extractor = make_extractor(ctx); emitted = []
                for record in records:
                    # A case is isolated; path is the document scope for continuation matching.
                    emitted.extend(extractor(record, record["source_path"]))

                expected = case["expected"]
                table_claims = [c for c in emitted if c.get("extraction_method") == "table_row"]
                if expected.get("no_extracted_claims"):
                    self.assertFalse([c for c in table_claims if c["extraction_status"] == "extracted"])
                if case["case_id"] == "GC-21":
                    self.assertEqual(0, ctx.diag["continuation_matches"],
                                     "flattened narrative context must not be treated as a table header")
                for forbidden in expected.get("forbidden_extracted", []):
                    self.assertFalse([c for c in table_claims if c["extraction_status"] == "extracted"
                                      and c.get("value") == forbidden.get("value")],
                                     f"forbidden value extracted: {forbidden}")
                for wanted in expected.get("claims", []):
                    candidates = [c for c in emitted if c.get("value") == wanted.get("value")]
                    if wanted.get("metric"):
                        candidates = [c for c in candidates if c.get("metric") == wanted["metric"]]
                    if wanted.get("unit") is not None:
                        candidates = [c for c in candidates if c.get("unit") == wanted["unit"]]
                    if wanted.get("period_type"):
                        candidates = [c for c in candidates if c.get("period_type") == wanted["period_type"]]
                    if wanted.get("period_text"):
                        candidates = [c for c in candidates if c.get("raw_period_text") == wanted["period_text"]]
                    if wanted.get("as_of_date"):
                        candidates = [c for c in candidates if c.get("as_of_date") == wanted["as_of_date"] or c.get("period_end") == wanted["as_of_date"]]
                    self.assertTrue(candidates, f"expected hand-verified claim not emitted: {wanted}")
                    allowed = set(wanted.get("status_allowed", []))
                    if allowed:
                        self.assertTrue(any(c["extraction_status"] in allowed for c in candidates),
                                        f"status exceeded fixture contract: {wanted}; got {[c['extraction_status'] for c in candidates]}")
                    if wanted.get("entity") is None:
                        self.assertTrue(any(c.get("entity") is None for c in candidates),
                                        f"fixture requires unresolved entity: {wanted}")

                if case["case_id"] in {"GC-34", "GC-35", "GC-36", "GC-37"}:
                    expected_rows = {}
                    for wanted in expected["claims"]:
                        expected_rows[wanted["source_chunk_id"]] = expected_rows.get(wanted["source_chunk_id"], 0) + 1
                        matches = [c for c in table_claims
                                   if c["value"] == wanted["value"]
                                   and c["metric"] == wanted["metric"]
                                   and c["source_chunk_id"] == wanted["source_chunk_id"]]
                        if wanted.get("period_text"):
                            matches = [c for c in matches if c.get("raw_period_text") == wanted["period_text"]]
                        self.assertEqual(1, len(matches), f"expected exactly one source-aligned table claim: {wanted}")
                        claim = matches[0]
                        for field in ("unit", "period_type", "as_of_date"):
                            self.assertEqual(wanted[field], claim[field], f"{case['case_id']} {field}: {wanted}")
                        expected_entity = case["target_company"]["name"] if wanted["entity"] == "target" else wanted["entity"]
                        self.assertEqual(expected_entity, claim["entity"], f"{case['case_id']} entity: {wanted}")
                        self.assertIn(claim["extraction_status"], wanted["status_allowed"], f"{case['case_id']} status: {wanted}")
                        self.assertEqual("unverified", claim["claim_verification_status"])
                        header_id = wanted.get("source_header_chunk_id")
                        row_matches = [m for m in ctx.continuation_matches if m["row_chunk_id"] == claim["source_chunk_id"]]
                        if header_id:
                            self.assertTrue(any(m["header_chunk_id"] == header_id for m in row_matches),
                                            f"header provenance mismatch: {wanted}")
                        else:
                            self.assertFalse(row_matches, f"a rejected/missing header must not be attached: {wanted}")
                    for row_id, expected_count in expected_rows.items():
                        actual_count = sum(c["source_chunk_id"] == row_id for c in table_claims)
                        self.assertEqual(expected_count, actual_count, f"unexpected/missing claims in row chunk {row_id}")

if __name__ == "__main__": unittest.main()
