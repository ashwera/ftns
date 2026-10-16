import csv
import tempfile
import unittest
from pathlib import Path

from signalforge.data_loader import DataLoadError, evidence_summary, filter_company, load_csv

class DataLoaderTests(unittest.TestCase):
    def make_csv(self, content):
        td = tempfile.TemporaryDirectory(); self.addCleanup(td.cleanup)
        p = Path(td.name) / "data.csv"; p.write_text(content, encoding="utf-8"); return p
    def test_load_metadata_missing_duplicate_types_and_dates(self):
        p = self.make_csv('Issuer,Date,Price,Source URL\nA,2026-01-01,2.5,https://example.com\nA,2026-01-01,2.5,https://example.com\nB,2026-01-02,,\n')
        rows, meta = load_csv(p)
        self.assertEqual(3, meta["row_count"]); self.assertEqual(1, meta["duplicate_rows"])
        self.assertEqual(1, meta["missing_values"]["Price"]); self.assertEqual("2026-01-01", meta["date_coverage"]["start"])
        self.assertEqual(["Issuer"], meta["company_identifier_candidates"])
        self.assertEqual(["A", "A"], [r["Issuer"] for r in filter_company(rows, meta, "A")])
        self.assertIn("Source URL", evidence_summary(rows, meta, "A")["provenance_columns"])
    def test_missing_file(self):
        with self.assertRaises(FileNotFoundError): load_csv("/definitely/missing.csv")
    def test_no_company_column_is_explicit(self):
        rows, meta = load_csv(self.make_csv("DATE,CLOSE\n2026-01-01,2\n"))
        self.assertFalse(meta["company_filtering_available"])
        with self.assertRaises(DataLoadError): filter_company(rows, meta, "A")
    def test_ambiguous_column(self):
        with self.assertRaises(DataLoadError): load_csv(self.make_csv("Company,company\nA,A\n"))

if __name__ == "__main__": unittest.main()
