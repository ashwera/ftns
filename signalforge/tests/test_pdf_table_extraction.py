import copy, json, os, re, unittest
from pathlib import Path
from signalforge import pdf_table_extraction as P
from signalforge.f1_research_angle_selector import _validate

HERE = Path(__file__).resolve().parent
FIX = json.loads((HERE / "fixtures" / "pdf_tables" / "ntpc_ar_2024_25_pdf_p91_layout.json").read_text(encoding="utf-8"))
SCHEMA = json.loads((HERE.parent / "schemas" / "claim.schema.json").read_text(encoding="utf-8"))
SHA = FIX["provenance"]["pdf_sha256"]
DOC = {"sha256": SHA, "path": "Annual Report 2024-25_1.pdf", "document_id": "pdfdoc_" + SHA[:16]}
EVID = "ev_2484a0e981c95b1829d91ac3"

def layout(): return copy.deepcopy(FIX["layout"])

def claims_for(lay, table=0, evidence=EVID):
    tables = P.table_structure(lay)
    return P.claims_from_table(tables[table], doc=DOC, pdf_page_index=91, entity="NTPC Limited", entity_status="verified", linked_evidence_id=evidence), tables

def lines(lay):
    return [(b, l) for b in lay["blocks"] for l in b["lines"]]

def find_line(lay, text):
    return next((b, l) for b, l in lines(lay) if l["text"].strip() == text)

def drop_line(lay, text):
    b, l = find_line(lay, text); b["lines"].remove(l)
    return lay

def table1(lay=None):
    cl, _ = claims_for(lay or layout()); return cl

def by_label(cl, label, scope=None):
    hit = [c for c in cl if c["raw_metric_text"] == label and (scope is None or c["ownership_scope"] == scope)]
    return hit

# value, scope, label, row_kind: read from the rendered PDF page 91 (printed page 179, right-hand table "Ongoing Projects / Capacity (MW)")
EXPECTED = [
    (13840.0, "parent_owned", "a) Coal Based Projects", "item"), (811.0, "parent_owned", "b) Hydro Electric Power Projects (HEPP)", "item"),
    (725.0, "parent_owned", "c) Renewable Energy Projects", "item"), (15376.0, "parent_owned", "Total (I)", "total"),
    (3060.0, "jv_subsidiary", "a) Coal Based Projects", "item"), (1444.0, "jv_subsidiary", "b) Hydro Projects", "item"),
    (13791.0, "jv_subsidiary", "c) Renewable Projects", "item"), (18295.0, "jv_subsidiary", "Total (II)", "total"),
    (33671.0, "group", "Total On-Going Projects as on 31 March 2025 (I)+(II)", "total")]

class Page91Tests(unittest.TestCase):
    def test_header_labels_and_tables(self):
        lay = layout(); tables = P.table_structure(lay)
        self.assertEqual({"left": "178", "right": "179"}, P.printed_labels(lay))
        self.assertEqual([("Ongoing Projects", ["Capacity (MW)"]), ("Description", ["Capacity (MW)"])], [(t["title"], t["column_headers"]) for t in tables])
        self.assertTrue(all(t["printed_page_label"] == "179" for t in tables)); self.assertTrue(all(not t["warnings"] for t in tables))

    def test_every_cell_recovered_with_scope_unit_period_and_label(self):
        cl = table1()
        self.assertEqual(EXPECTED, [(c["value"], c["ownership_scope"], c["raw_metric_text"], c["row_kind"]) for c in cl])
        for c in cl:
            self.assertEqual(("MW", "2025-03-31", "as_of", "179", 91, "extracted", "unverified", "NTPC Limited"),
                             (c["unit"], c["as_of_date"], c["period_type"], c["printed_page_label"], c["source_page"], c["extraction_status"], c["claim_verification_status"], c["entity"]))
            self.assertEqual(("Ongoing Projects | Capacity (MW)", "under_implementation", SHA, EVID), (c["source_header_text"], c["project_status"], c["source_sha256"], c["source_chunk_id"]))

    def test_the_five_regression_values(self):
        cl = table1()
        pick = lambda label, scope: by_label(cl, label, scope)[0]["value"]
        self.assertEqual(725.0, pick("c) Renewable Energy Projects", "parent_owned"))
        self.assertEqual(15376.0, pick("Total (I)", "parent_owned"))
        self.assertEqual(13791.0, pick("c) Renewable Projects", "jv_subsidiary"))
        self.assertEqual(18295.0, pick("Total (II)", "jv_subsidiary"))
        self.assertEqual(33671.0, cl[-1]["value"]); self.assertEqual("group", cl[-1]["ownership_scope"])
        self.assertNotIn(709.0, [c["value"] for c in cl])  # the derived residual is never a table value

    def test_scope_comes_from_the_section_heading_and_is_recorded(self):
        cl = table1()
        self.assertEqual({"I Owned by your Company", "II Projects under JVs & Subsidiaries", None}, {c["section_heading"] for c in cl})
        self.assertIn("matched", by_label(cl, "c) Renewable Energy Projects")[0]["scope_evidence"])
        self.assertIn("sum of the section totals", cl[-1]["scope_evidence"])
        self.assertTrue(all("not NTPC's economic ownership share" in c["ambiguity_notes"] for c in cl if c["ownership_scope"] == "jv_subsidiary"))

    def test_totals_are_tied_out_arithmetically(self):
        cl = table1()
        self.assertEqual([("section_sum", 15376.0, True), ("section_sum", 18295.0, True), ("sum_of_section_totals", 33671.0, True)],
                         [(c["tie_out"]["kind"], c["tie_out"]["sum"], c["tie_out"]["ok"]) for c in cl if c["row_kind"] == "total"])

    def test_wrapped_labels_are_joined(self):
        labels = [c["raw_metric_text"] for c in table1()]
        self.assertIn("b) Hydro Electric Power Projects (HEPP)", labels); self.assertTrue(any(l.startswith("Total On-Going Projects as on 31 March 2025") for l in labels))

    def test_geometry_provenance_is_inside_the_right_hand_table(self):
        for c in table1():
            x0, y0, x1, y1 = c["bbox"]; self.assertTrue(1090 < x0 < x1 <= 1135 and 440 < y0 < y1 < 640, c["bbox"])

    def test_ids_are_stable_unique_and_schema_conformant(self):
        a, b = table1(), table1()
        self.assertEqual([c["claim_id"] for c in a], [c["claim_id"] for c in b]); self.assertEqual(len(a), len({c["claim_id"] for c in a}))
        for c in a:
            self.assertEqual([], _validate(c, SCHEMA)); self.assertRegex(c["claim_id"], r"^pdfn_[a-f0-9]{24}$"); self.assertRegex(c["source_chunk_id"], r"^ev_[a-f0-9]{24}$")

    def test_description_table_is_scoped_but_refuses_without_a_period(self):
        cl, _ = claims_for(layout(), table=1)
        self.assertEqual(11, len(cl)); self.assertEqual({"ambiguous"}, {c["extraction_status"] for c in cl})
        self.assertEqual(79930.0, cl[-1]["value"]); self.assertEqual("group", cl[-1]["ownership_scope"])
        self.assertTrue(all(c["as_of_date"] is None and "no 'as on' date" in c["ambiguity_notes"] for c in cl))
        self.assertEqual([("parent_owned", 59413.0), ("jv_subsidiary", 20517.0)], [(c["ownership_scope"], c["value"]) for c in cl if c["metric"] == "sub_total"])

class NegativeTests(unittest.TestCase):
    def test_missing_section_heading_leaves_rows_unresolved_not_guessed(self):
        cl = table1(drop_line(layout(), "II  Projects under JVs & Subsidiaries"))
        # without heading II the JV rows fall under heading I, so Total (I) no longer ties out and no total may be `extracted`
        self.assertTrue(all(c["extraction_status"] != "extracted" for c in cl if c["row_kind"] == "total"))
        self.assertFalse([c for c in cl if c["ownership_scope"] == "jv_subsidiary"])

    def test_section_wording_naming_both_owners_is_unresolved(self):
        lay = layout(); _, l = find_line(lay, "II  Projects under JVs & Subsidiaries"); l["text"] = "II  Parent owned and JV subsidiary projects"
        cl = table1(lay)
        sec2 = [c for c in cl if c["section_heading"] and c["section_heading"].startswith("II")]
        self.assertEqual(4, len(sec2)); self.assertEqual({"unresolved"}, {c["ownership_scope"] for c in sec2})
        self.assertEqual({"ambiguous"}, {c["extraction_status"] for c in sec2}); self.assertIn("both parent and JV/subsidiary wording", sec2[0]["ambiguity_notes"])

    def test_heading_without_owner_wording_is_unresolved(self):
        lay = layout(); _, l = find_line(lay, "II  Projects under JVs & Subsidiaries"); l["text"] = "II  Other projects"
        cl = table1(lay)
        rows = [c for c in cl if c["section_heading"] == "II Other projects"]
        self.assertEqual(4, len(rows)); self.assertTrue(all(c["ownership_scope"] == "unresolved" and c["extraction_status"] == "ambiguous" for c in rows))

    def test_nearby_prose_naming_an_entity_does_not_change_scope(self):
        lay = layout()
        for b, l in lines(lay):
            if "joint venture and subsidiary company" in l["text"] or "being developed" in l["text"] or "under implementation" in l["text"]:
                l["text"] = l["text"] + " all of it is owned by your Company and subsidiaries"
        self.assertEqual([(v, s) for v, s, _, _ in EXPECTED], [(c["value"], c["ownership_scope"]) for c in table1(lay)])

    def test_no_value_is_attributed_across_owners(self):
        cl = table1()
        self.assertFalse([c for c in cl if c["ownership_scope"] == "parent_owned" and c["value"] in (3060.0, 1444.0, 13791.0, 18295.0)])
        self.assertFalse([c for c in cl if c["ownership_scope"] == "jv_subsidiary" and c["value"] in (13840.0, 811.0, 725.0, 15376.0)])

    def test_a_changed_cell_breaks_the_tie_out_and_demotes_the_total(self):
        lay = layout(); _, l = find_line(lay, "725"); l["text"] = "715"
        cl = table1(lay); t1 = by_label(cl, "Total (I)")[0]
        self.assertEqual(("ambiguous", False), (t1["extraction_status"], t1["tie_out"]["ok"])); self.assertIn("does not equal the sum", t1["ambiguity_notes"])
        self.assertNotEqual("extracted", cl[-1]["extraction_status"])  # grand total no longer equals the section totals

    def test_malformed_cell_text_is_not_a_value(self):
        lay = layout(); _, l = find_line(lay, "725"); l["text"] = "7x5"
        cl = table1(lay)
        self.assertNotIn(725.0, [c["value"] for c in cl]); self.assertNotIn("extracted", [c["extraction_status"] for c in cl if c["row_kind"] == "total" and c["value"] == 15376.0])

    def test_two_values_in_one_cell_are_flagged(self):
        lay = layout(); b, l = find_line(lay, "725"); dup = copy.deepcopy(l); dup["text"] = "730"; dup["bbox"][0] -= 12; dup["bbox"][2] -= 12; b["lines"].append(dup)
        cl = table1(lay)
        self.assertTrue(all(c["extraction_status"] != "extracted" for c in cl))

    def test_missing_as_on_date_or_unpointed_intro_downgrades_period(self):
        lay = layout()
        for b, l in lines(lay):
            if l["text"].lstrip().startswith("implementation, including 18,295") or "As on 31 March 2025" in l["text"] or "As on" in l["text"]:
                l["text"] = l["text"].replace("As on 31 March 2025", "At year end")
        cl = table1(lay)
        non_total = [c for c in cl if c["row_kind"] == "item"]
        self.assertTrue(all(c["as_of_date"] is None and c["extraction_status"] != "extracted" for c in non_total))
        lay2 = layout()
        for b, l in lines(lay2):
            if "The details are as under" in l["text"]: l["text"] = "Further commentary follows."
        self.assertTrue(all(c["extraction_status"] != "extracted" and "does not point at the table" in c["ambiguity_notes"] for c in table1(lay2) if c["row_kind"] == "item"))

    def test_header_without_unit_or_period_is_not_a_table(self):
        lay = layout(); _, l = find_line(lay, "Capacity (MW)"); 
        for b, ln in lines(lay):
            if ln["text"].strip() == "Capacity (MW)": ln["text"] = "Capacity"
        tables = P.table_structure(lay)
        self.assertEqual([], tables)

    def test_unit_comes_only_from_the_header(self):
        lay = layout()
        for b, ln in lines(lay):
            if ln["text"].strip() == "Capacity (MW)" and ln["bbox"][0] > 1000: ln["text"] = "Capacity (GW)"
        self.assertEqual({"GW"}, {c["unit"] for c in table1(lay)})

class LinkingAndSchemaTests(unittest.TestCase):
    def test_evidence_link_requires_a_unique_same_document_page(self):
        rec = lambda i, stem, page: {"evidence_id": i, "source_path": f"CSV/annual reports/{stem}.csv", "page_number": page}
        self.assertEqual("ev_" + "a" * 24, P._linked_evidence([rec("ev_" + "a" * 24, "Annual Report 2024-25_1", 91)], "Annual Report 2024-25_1", 91))
        self.assertIsNone(P._linked_evidence([rec("ev_" + "a" * 24, "Annual Report 2024-25_1", 91), rec("ev_" + "b" * 24, "Annual Report 2024-25_1", 91)], "Annual Report 2024-25_1", 91))
        self.assertIsNone(P._linked_evidence([rec("ev_" + "a" * 24, "Other", 91)], "Annual Report 2024-25_1", 91))

    def test_without_a_linked_record_the_claim_is_still_valid_but_unlinked(self):
        cl, _ = claims_for(layout(), evidence=None)
        self.assertTrue(all(c["source_chunk_id"] is None and _validate(c, SCHEMA) == [] for c in cl))


    def test_each_claim_links_to_the_chunk_that_prints_its_value(self):
        recs = [{"evidence_id": "ev_" + "1" * 24, "source_path": "CSV/x/Annual Report 2024-25_1.csv", "page_number": 91, "excerpt_or_fact": "Total (I) 15,376 and renewable 725 MW"},
                {"evidence_id": "ev_" + "2" * 24, "source_path": "CSV/x/Annual Report 2024-25_1.csv", "page_number": 91, "excerpt_or_fact": "only 18,295 here"},
                {"evidence_id": "ev_" + "3" * 24, "source_path": "CSV/x/Annual Report 2024-25_1.csv", "page_number": 90, "excerpt_or_fact": "725 on another page"}]
        link = lambda v: P.link_by_value(recs, "Annual Report 2024-25_1", 91, v)
        self.assertEqual(("ev_" + "1" * 24, "ev_" + "2" * 24, None), (link("725"), link("18,295"), link("33,671")))
        self.assertIsNone(link("25"))  # a substring of 725 must not match
        recs.append(dict(recs[0], evidence_id="ev_" + "4" * 24)); self.assertIsNone(link("725"))  # ambiguous: two chunks print it

    def test_unknown_fields_are_still_rejected_and_old_claims_still_validate(self):
        bad = dict(table1()[0], surprise=1); self.assertTrue(_validate(bad, SCHEMA))
        legacy = {"schema_version": "1.1", "claim_id": "cl1_" + "a" * 24, "entity": "X", "entity_identity_status": "verified", "metric": "coal", "raw_metric_text": "Coal", "value": 1.0, "raw_value_text": "1", "unit": "percent", "raw_unit_text": "%",
                  "period_type": "financial_year", "period_start": None, "period_end": None, "as_of_date": None, "raw_period_text": "FY 2017-18", "source_document_id": "doc_1", "source_path": "a.csv", "source_page": 1, "source_chunk_id": "ev_" + "b" * 24,
                  "source_excerpt": "Coal,1", "extraction_status": "extracted", "ambiguity_notes": None, "claim_verification_status": "unverified", "parser_version": "layer1.5-table-0.2.0", "extraction_method": "table_row", "chunk_class": "tabular",
                  "source_row_text": "Coal,1", "source_header_text": "P,FY", "row_index": 1, "column_index": 1, "reversal_applied": False}
        self.assertEqual([], _validate(legacy, SCHEMA))

PDF = Path(os.environ.get("SIGNALFORGE_AR_PDF", HERE.parent / "data" / "Annual Report 2024-25_1.pdf"))

@unittest.skipUnless(PDF.exists(), "original annual report PDF not present (not committed); set SIGNALFORGE_AR_PDF")
class LivePdfTests(unittest.TestCase):
    def test_pdf_hash_and_page91_match_the_committed_layout_fixture(self):
        try: import pymupdf  # noqa: F401
        except ImportError: self.skipTest("PyMuPDF not installed")
        self.assertEqual(SHA, P.sha256_file(PDF))
        claims, report = P.extract_pages(PDF, [91], entity="NTPC Limited", entity_status="verified", evidence_records=[{"evidence_id": EVID, "source_path": "CSV/annual reports/Annual Report 2024-25_1.csv", "page_number": 91}], pdf_sha256=SHA)
        t1 = [c for c in claims if c["table_title"] == "Ongoing Projects"]
        self.assertEqual(EXPECTED, [(c["value"], c["ownership_scope"], c["raw_metric_text"], c["row_kind"]) for c in t1])
        self.assertEqual(report["pages"][0]["linked_evidence_id"], EVID); self.assertEqual(0, report["duplicates_dropped"])

    def test_prose_pages_yield_no_table_claims(self):
        try: import pymupdf  # noqa: F401
        except ImportError: self.skipTest("PyMuPDF not installed")
        claims, _ = P.extract_pages(PDF, [112], entity="NTPC Limited", entity_status="verified", pdf_sha256=SHA)
        self.assertEqual([], claims)

if __name__ == "__main__": unittest.main()
