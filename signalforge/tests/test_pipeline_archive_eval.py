import unittest

from signalforge import archive_evaluation as AE

def claim(i, **kw):
    c = {"claim_id": f"cl1_{i:024x}", "extraction_method": "table_row", "extraction_status": "ambiguous", "entity": None, "metric": "m", "raw_metric_text": "m", "value": 1.0, "raw_value_text": "1", "unit": "MW", "period_type": "as_of", "raw_period_text": "p",
         "as_of_date": "2025-03-31", "source_path": f"d{i % 2}.csv", "source_page": 1, "source_chunk_id": "ev_" + f"{i:024x}", "source_excerpt": "e", "ambiguity_notes": None, "claim_verification_status": "unverified", "source_header_text": None}
    c.update(kw); return c

class ArchiveEvalTests(unittest.TestCase):
    def test_summary_counts_missing_fields_and_unverified(self):
        cs = [claim(1, extraction_status="extracted"), claim(2, unit=None), claim(3, period_type="unknown", metric=None)]
        s = AE.summarize(cs); self.assertEqual(3, s["total_claims"]); self.assertEqual({"extracted": 1, "ambiguous": 2}, s["status_total"]); self.assertEqual((1, 1, 1), (s["missing_counts"]["unit"], s["missing_counts"]["period"], s["missing_counts"]["metric"])); self.assertEqual(["unverified"], s["verification_status_values"])
    def test_repeats_across_documents_are_never_independent_corroboration(self):
        groups = AE.duplicate_groups([claim(1), claim(2), claim(3, value=2.0)])
        self.assertEqual(1, len(groups)); self.assertEqual((2, 2, False), (groups[0]["claim_count"], groups[0]["distinct_documents"], groups[0]["independent_corroboration"]))
    def test_audit_sample_is_deterministic_stratified_and_keeps_unverified(self):
        cs = [claim(i, extraction_status="extracted" if i < 3 else "ambiguous", ambiguity_notes="forward-looking wording" if i % 5 == 0 else None) for i in range(60)]
        a, b = AE.audit_sample(cs, seed=7), AE.audit_sample(cs, seed=7); self.assertEqual(a, b); self.assertEqual(len(a), len({x["claim_id"] for x in a}))
        self.assertEqual({"unverified"}, {x["claim_verification_status"] for x in a}); self.assertIn("table_extracted", {x["stratum"] for x in a}); self.assertTrue(all(x["audit_result"] is None for x in a))

if __name__ == "__main__": unittest.main()
