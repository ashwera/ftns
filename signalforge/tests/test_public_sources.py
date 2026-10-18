import json
import tempfile
import unittest
import urllib.error
from pathlib import Path

from signalforge.evidence_ingestion import _cross_validation_summary, ingest_file, load_registry, registry_mapping_conflicts, verify_company
from signalforge.f1_research_angle_selector import eligible_ingested_evidence, validate_output
from signalforge.public_sources import retrieve_urls, verify_identity_from_document

class FakeResponse:
    def __init__(self,data,url,ctype="text/html"):
        self.data=data; self.url=url; self.headers={"Content-Type":ctype}; self.status=200
    def read(self,n=-1): return self.data if n<0 else self.data[:n]
    def geturl(self): return self.url
    def __enter__(self): return self
    def __exit__(self,*args): pass
class FakeOpener:
    def __init__(self,data,ctype="text/html",failure=None): self.data=data; self.ctype=ctype; self.failure=failure
    def open(self,request,timeout=None):
        if self.failure: raise self.failure
        return FakeResponse(self.data,request.full_url,self.ctype)

class PublicSourcesTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory(); self.addCleanup(self.tmp.cleanup); self.root=Path(self.tmp.name)
        self.registry=self.root/"registry.json"
        self.registry.write_text(json.dumps({"version":1,"companies":[{"canonical_name":None,"verified_identifier":None,"identifiers":[],"aliases":["NTPC"],"verification_source":None,"verification_status":"unresolved"}]}))
    def test_verified_identity_from_authoritative_document_and_conflict(self):
        html=b'<html><head><title>Exchange Filing</title></head><body>NTPC LIMITED | NSE Symbol NTPC | ISIN INE733E01010 | Scrip Code 532555</body></html>'
        result=verify_identity_from_document("NTPC","NTPC Limited","NTPC","INE733E01010","https://exchange.example/filing",self.registry,self.root/"out",opener=FakeOpener(html),robots_checker=lambda u:(True,0,"fixture robots allow"))
        self.assertEqual("verified",result["verification_status"])
        reg=load_registry(self.registry); self.assertEqual("verified",verify_company("NTPC",reg)[2])
        entry=reg["companies"][-1]; self.assertIn("verification_retrieval_date",entry); self.assertIn("NTPC LIMITED",entry["verification_excerpt"].upper())
        conflict=registry_mapping_conflicts({"companies":[{"canonical_name":"Other Corp","verified_identifier":"OTHER","aliases":["NTPC"],"verification_status":"verified"}]},"NTPC","NTPC Limited","INE733E01010")
        self.assertEqual(1,len(conflict))
        self.assertEqual([],eligible_ingested_evidence([{"company_identity_status":"unresolved","company_name":"NTPC Limited"}],"NTPC Limited","INE733E01010"))
        matching={"company_identity_status":"verified","company_name":"NTPC Limited","verified_identifier":"INE733E01010","evidence_id":"ev_123","parsing_status":"parsed","excerpt_or_fact":"Reviewed filing passage.",
                  "review_status":"approved","reviewed_by":"reviewer-1","reviewed_at":"2026-10-18T12:00:00Z","review_note":"Checked against the original filing page."}
        wrong_company={**matching,"company_name":"Other Limited","verified_identifier":"OTHER"}
        pending={**matching,"review_status":"pending_review"}
        missing_review={k:v for k,v in matching.items() if k not in {"reviewed_by","reviewed_at","review_note"}}
        unparsed={**matching,"parsing_status":"ocr_required"}
        empty={**matching,"excerpt_or_fact":"  "}
        self.assertEqual([matching],eligible_ingested_evidence([matching,wrong_company,pending,missing_review,unparsed,empty],"NTPC Limited","INE733E01010"))
    def test_f1_approval_requires_exact_identity_and_a_timezone_aware_review_record(self):
        matching={"company_identity_status":"verified","company_name":"NTPC Limited","verified_identifier":"INE733E01010","parsing_status":"parsed","excerpt_or_fact":"Reviewed filing passage.",
                  "review_status":"approved","reviewed_by":"reviewer-1","reviewed_at":"2026-10-18T12:00:00Z","review_note":"Checked against the original filing page."}
        cases=[
            {**matching,"company_name":"NTPC Corporation"},
            {**matching,"verified_identifier":"INE000000000"},
            {**matching,"reviewed_at":"not-a-timestamp"},
            {**matching,"reviewed_at":"2026-10-18T12:00:00"},
            {**matching,"reviewed_by":"  "},
            {**matching,"review_note":None},
        ]
        for record in cases:
            with self.subTest(record=record):
                self.assertEqual([],eligible_ingested_evidence([record],"NTPC Limited","INE733E01010"))
        self.assertEqual([matching],eligible_ingested_evidence([matching],"NTPC Limited","INE733E01010"))
    def test_f1_rejects_each_nonparsed_and_fragment_status(self):
        matching={"company_identity_status":"verified","company_name":"NTPC Limited","verified_identifier":"INE733E01010","parsing_status":"parsed","excerpt_or_fact":"Reviewed filing passage.",
                  "review_status":"approved","reviewed_by":"reviewer-1","reviewed_at":"2026-10-18T12:00:00Z","review_note":"Checked against the original filing page."}
        for status in ("empty","failed","ocr_required"):
            with self.subTest(parsing_status=status):
                self.assertEqual([],eligible_ingested_evidence([{**matching,"parsing_status":status}],"NTPC Limited","INE733E01010"))
    def test_inaccessible_source_and_missing_metadata(self):
        bad=retrieve_urls(["https://example.test/a"],self.root/"bad",opener=FakeOpener(b"",failure=urllib.error.URLError("blocked")),robots_checker=lambda u:(True,0,"robots ok"),sleep_fn=lambda _:None)
        self.assertEqual(1,bad["failed_count"])
        html=b"<html><title>No date</title><body>Public report</body></html>"
        good=retrieve_urls(["https://example.test/report"],self.root/"ok",opener=FakeOpener(html),robots_checker=lambda u:(True,0,"robots ok"),sleep_fn=lambda _:None)
        self.assertEqual(1,good["retrieved_count"])
        rec=json.loads((self.root/"ok/evidence.jsonl").read_text().splitlines()[0])
        self.assertIsNone(rec["publication_date"]); self.assertEqual("https://example.test/report",rec["source_url"])
        self.assertEqual("pending_review",rec["review_status"]); self.assertIsNone(rec["reviewed_by"])
        self.assertTrue(any("Publication date" in w for w in rec["extraction_warnings"]))
        validate_output(rec,Path(__file__).resolve().parents[1]/"schemas/evidence_record.schema.json")
    def test_duplicate_source_and_independence_classification(self):
        html=b"<html><body>Same disclosure text</body></html>"
        report=retrieve_urls(["https://a.example/doc","https://b.example/republication"],self.root/"dups",opener=FakeOpener(html),robots_checker=lambda u:(True,0,"robots ok"),sleep_fn=lambda _:None,source_relationship="republication")
        self.assertEqual(1,len(report["duplicate_documents"]))
        entries=[{"claim_key":"cl_1","evidence_id":"ev_a","source_path":"a","source_relationship":"original_disclosure"},{"claim_key":"cl_1","evidence_id":"ev_b","source_path":"b","source_relationship":"republication"},{"claim_key":"cl_1","evidence_id":"ev_c","source_path":"c","source_relationship":"independent_source"}]
        status=_cross_validation_summary(entries)[0]
        self.assertEqual(1,status["independent_source_count"]); self.assertEqual(1,status["republication_count"]); self.assertEqual("independently_corroborated",status["status"])
    def test_units_periods_and_conflicting_mappings(self):
        registry={"companies":[{"canonical_name":"Acme Energy","verified_identifier":"ISIN1","identifiers":["ACME"],"aliases":["Acme"],"verification_source":"https://exchange.test/id","verification_status":"verified"}]}
        csv=self.root/"metrics.csv"; csv.write_text("Company,Period,Revenue,Unit,Currency\nAcme,FY2025,120,crore,INR\n")
        rec=ingest_file(csv,registry,root=self.root)["records"]
        revenue=next(x for x in rec if x["metric_name"]=="Revenue")
        self.assertEqual("FY2025",revenue["reporting_period"]); self.assertEqual("crore",revenue["unit"]); self.assertEqual("INR",revenue["currency"])
        self.assertEqual("ISIN1",revenue["verified_identifier"])
        conflicted={"companies":[*registry["companies"],{"canonical_name":"Different Co","verified_identifier":"ISIN2","identifiers":[],"aliases":["Acme"],"verification_status":"verified","verification_source":"https://other.test"}]}
        self.assertEqual("unresolved",verify_company("Acme",conflicted)[2])

if __name__=="__main__": unittest.main()
