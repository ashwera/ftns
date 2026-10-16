import json
import tempfile
import unittest
from pathlib import Path

from signalforge.dataset_audit import audit_csv, build_readiness, profile_dataset
from signalforge.f1_research_angle_selector import WEIGHTS, validate_output
from signalforge.data_loader import DataLoadError

class DatasetAuditTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory(); self.addCleanup(self.tmp.cleanup)
        self.path=Path(self.tmp.name)/"sample.csv"
    def test_profile_numeric_missing_dates_duplicates(self):
        self.path.write_text("Company,Date,Revenue\nA,2026-01-01,10\nA,2026-01-01,10\nB,2026-01-02,\n",encoding="utf-8")
        rows,audit=profile_dataset(self.path)
        self.assertEqual(3,audit["row_count"]); self.assertEqual(1,audit["exact_duplicate_rows"])
        self.assertEqual(["Date"],audit["date_columns"]); self.assertEqual(1,audit["field_statistics"]["Revenue"]["missing_count"])
        self.assertEqual(10,audit["field_statistics"]["Revenue"]["numeric_summary"]["median"])
        self.assertEqual(["A","B"],audit["distinct_companies"])
    def test_empty_dataset(self):
        self.path.write_text("Date,Close\n",encoding="utf-8")
        _,audit=profile_dataset(self.path)
        self.assertEqual(0,audit["row_count"]); self.assertEqual(2,audit["column_count"])
    def test_missing_file(self):
        with self.assertRaises(FileNotFoundError): profile_dataset(self.path)
    def test_missing_or_ambiguous_company_identifier(self):
        self.path.write_text("Date,Close\n2026-01-01,4\n",encoding="utf-8")
        rows,audit=profile_dataset(self.path)
        self.assertEqual([],audit["company_identifier_columns"])
        self.assertFalse(build_readiness(audit,rows,"X")["company_filter_applied"])
        self.path.write_text("Company,company\nA,A\n",encoding="utf-8")
        with self.assertRaises(DataLoadError): profile_dataset(self.path)
    def test_unsupported_category(self):
        self.path.write_text("Close\n3\n",encoding="utf-8")
        rows,audit=profile_dataset(self.path)
        with self.assertRaises(ValueError): build_readiness(audit,rows,categories=("unrelated",))
    def test_weights_and_output_schema(self):
        self.assertAlmostEqual(1,sum(WEIGHTS.values()))
        self.path.write_text("Date,Close\n2026-01-01,3\n",encoding="utf-8")
        with tempfile.TemporaryDirectory() as output_dir:
            audit,readiness=audit_csv(self.path,output_dir)
            schemas=Path(__file__).resolve().parents[1]/"schemas"
            self.assertEqual(audit,validate_output(audit,schemas/"dataset_audit.schema.json"))
            self.assertEqual(readiness,validate_output(readiness,schemas/"research_readiness.schema.json"))

if __name__=="__main__": unittest.main()
