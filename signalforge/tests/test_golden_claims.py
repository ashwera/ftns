import json
import unittest
from pathlib import Path

import golden_harness as G

REQUIRED_CATEGORY_KEYWORDS = {
    "clean single-chunk table": "clean_single_chunk_table", "header and data split across chunks": "split_header_and_data", "reversed or garbled table text": "reversed_table_text",
    "table continued across three chunks": "three_chunks", "chunks read by page order": "ordered_by_page", "same-width different-table boundary": "different_table_boundary",
    "clear historical prose": "historical_prose", "forward-looking statement": "forward_looking", "national figure": "national_figure", "subsidiary/JV sentence": "subsidiary",
    "ambiguous or missing unit": "unit_scale_detached", "standalone vs consolidated": "standalone_vs_consolidated", "multiple numbers, different meanings": "multiple_numbers",
    "valid percentage / amount with context": "historical_prose_with_national_comparator", "target/planned/awarded/under-construction capacity": "under_implementation"}
EVIDENCE = Path(__file__).resolve().parents[1] / "data" / "processed_step6" / "evidence.jsonl"

class FixtureIntegrityTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls): cls.chunks, cls.cases = G.load()
    def test_size_and_unique_ids(self):
        self.assertTrue(20 <= len(self.cases) <= 32, len(self.cases)); self.assertEqual(len(self.cases), len({c["case_id"] for c in self.cases}))
    def test_required_failure_categories_are_covered(self):
        cats = " ".join(c["category"] for c in self.cases)
        for label, kw in REQUIRED_CATEGORY_KEYWORDS.items(): self.assertIn(kw, cats, label)
    def test_every_case_references_known_chunks_and_has_documentation(self):
        for c in self.cases:
            all_ids = c["chunk_ids"] + c["context_chunk_ids"]
            for cid in all_ids: self.assertIn(cid, self.chunks, c["case_id"])
            self.assertTrue(c["explanation"] and c["target_company"]["name"] and c["applies_to"], c["case_id"])
            self.assertTrue(c["expected"]["claims"] or c["expected"]["forbidden_extracted"] or c["expected"]["no_extracted_claims"], c["case_id"])
            if c["expected"]["forbidden_extracted"] or c["expected"]["no_extracted_claims"]: self.assertTrue(c["expected"]["reason"], c["case_id"])
            for claim in c["expected"]["claims"]:
                if claim.get("must_emit"):
                    for field in ("metric", "value", "unit", "period_type", "period_text", "source_chunk_id"):
                        self.assertIn(field, claim, f"{c['case_id']} missing {field}")
                    self.assertIn(claim["source_chunk_id"], all_ids, c["case_id"])
                    header_id = claim.get("source_header_chunk_id")
                    if header_id is not None: self.assertIn(header_id, all_ids, c["case_id"])
    def test_synthetic_cases_are_labelled_and_real_chunks_have_provenance(self):
        for c in self.cases:
            syn = [self.chunks[i]["synthetic"] for i in c["chunk_ids"] + c["context_chunk_ids"]]
            self.assertEqual([c["synthetic"]] * len(syn), syn, c["case_id"])
            if c["synthetic"]: self.assertTrue(c["explanation"].startswith("SYNTHETIC"), c["case_id"])
        for ch in self.chunks.values():
            if not ch["synthetic"]: self.assertTrue(all(ch.get(k) for k in ("evidence_id", "source_path", "source_locator", "source_sha256")) and isinstance(ch["page_number"], int), ch["evidence_id"])
            else: self.assertTrue(ch["source_path"].startswith("SYNTHETIC/"))
    def test_focus_text_appears_verbatim_in_the_case_chunks(self):
        for c in self.cases:
            text = " ".join(G.collapse(self.chunks[i]["excerpt_or_fact"]) for i in c["chunk_ids"] + c["context_chunk_ids"])
            for e in c["expected"]["claims"] + c["expected"]["forbidden_extracted"]: self.assertIn(G.collapse(e["focus"]), text, f"{c['case_id']}: {e['focus']}")
    @unittest.skipUnless(EVIDENCE.is_file(), "Step 6 evidence store not present")
    def test_real_chunks_are_verbatim_copies_of_the_step6_store(self):
        store = {r["evidence_id"]: r for r in (json.loads(l) for l in EVIDENCE.read_text(encoding="utf-8").splitlines() if l.strip())}
        for cid, ch in self.chunks.items():
            if ch["synthetic"]: continue
            self.assertEqual(store[cid]["excerpt_or_fact"], ch["excerpt_or_fact"], cid); self.assertEqual(store[cid]["page_number"], ch["page_number"], cid)

class GoldenCaseTests(unittest.TestCase):
    def test_every_case_against_each_applicable_extractor(self):
        results = G.run_all(); self.assertGreaterEqual(len(results), 28)
        for r in results:
            with self.subTest(case=r["case_id"], extractor=r["extractor"]):
                failing = [c for c in r["checks"] if not c["ok"]]
                if r["xfail"]:
                    self.assertTrue(failing, f"{r['case_id']} is marked xfail ({r['xfail']}) but now passes; remove the xfail")
                else:
                    self.assertFalse(failing, "; ".join(f"{c['name']}: want {c['expected']} got {c['actual']}" for c in failing))

if __name__ == "__main__": unittest.main()
