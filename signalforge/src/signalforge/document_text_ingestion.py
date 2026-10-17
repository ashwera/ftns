"""Ingest page-marker text extractions (PDF-to-CSV dumps) as page-block evidence.

These files are not tables: each starts a block with a ``Page N`` line followed by loosely CSV-quoted
text fragments. The generic CSV loader would misread the first row as a header, so this module keeps
every block as raw text with its page number and never extracts metric values.
"""
import argparse
import datetime as dt
import hashlib
import json
import re
import sys
from dataclasses import asdict
from pathlib import Path

from .config import Config
from .evidence_ingestion import _hash_file, _record, load_registry
from .f1_research_angle_selector import validate_output

PAGE_RE = re.compile(r"^Page (\d+)[ \t\r]*$", re.M)
STRONG_ID_PATTERNS = (r"\bINE733E01010\b", r"\b532555\b", r"Scrip Code\W{0,5}NTPC\b")
PERIOD_RE = re.compile(r"(?:quarter|half[- ]year|six months|year)\s+ended\s+(?:on\s+)?(\d{1,2}[./ ]\w+[./ ]\d{2,4}|\w+ \d{1,2},? \d{4})", re.I)
# Tags are keyword triage for manual review, not conclusions about what a page proves.
TAGS = {
    "renewable_transition": r"\b(renewable|solar|wind|green energy|hydro|pumped storage|nuclear|BESS|RE capacity|NGEL|non-fossil)\b",
    "capacity_pipeline": r"\b(installed capacity|commissioned|commissioning|under construction|under implementation|letter of award|LoA|awarded|COD|commercial operation|capacity addition)\b|\bMW\b|\bGW\b",
    "relationships": r"\b(subsidiar\w+|joint venture|JV|associate|related part\w+|guarantee\w*|debenture\w*|bonds?|borrowings?|loans?|supplier|customer|offtake|PPA)\b",
    "financial_statements": r"\b(revenue from operations|total income|segment|profit before tax|balance sheet|cash flow|statement of profit)\b",
}

def split_page_blocks(text):
    """Return [(page_number, block_index_on_page, text)] preserving file order. Text before the first marker is dropped (reported separately)."""
    marks=list(PAGE_RE.finditer(text)); blocks=[]; seen={}
    for i,m in enumerate(marks):
        body=text[m.end():marks[i+1].start() if i+1<len(marks) else len(text)].strip()
        page=int(m.group(1)); seen[page]=seen.get(page,0)+1
        blocks.append((page,seen[page],body))
    return blocks

def document_identity(text, registry, canonical_name, verified_identifier):
    """Verify only on exchange identifiers; a name alone cannot separate NTPC Limited from a subsidiary or parent mention."""
    entry=next((e for e in registry.get("companies",[]) if e.get("canonical_name")==canonical_name and e.get("verification_status")=="verified" and e.get("verification_source")),None)
    flat=re.sub(r"\s+"," ",text)
    hits=[p for p in STRONG_ID_PATTERNS if re.search(p,flat,re.I)]
    name=bool(re.search(re.escape(canonical_name),flat,re.I))
    if entry and hits and entry.get("verified_identifier")==verified_identifier:
        return "verified",f"document text contains exchange identifier pattern(s) {hits}"
    if name: return "unresolved","name appears but no ISIN/scrip code/NSE symbol label; may be a parent/subsidiary mention"
    return "unresolved","no canonical name or exchange identifier in document text"

def classify(text):
    return [tag for tag,pat in TAGS.items() if re.search(pat,text,re.I)]

def block_quality(text):
    flags=[]
    meaningful=re.sub(r"[\s,\"'\-•.]+","",text)
    if len(meaningful)<15: flags.append("fragment_or_empty")
    if "�" in text: flags.append("replacement_characters")
    if re.search(r"\b\w*[a-z][A-Z1l]{1}[a-z]*(?:ndia|ndla|nd1a)\b|Depa1t|Jndia|oflndia",text): flags.append("ocr_like_misreads")
    if re.search(r"\d\.\d{2}\d{1,3}\.\d{2}",text): flags.append("merged_numeric_cells")
    return flags

def ingest_document(path, source_path, registry, canonical_name, verified_identifier, folder_hint):
    raw=Path(path).read_bytes(); text=raw.decode("utf-8-sig",errors="replace").replace("\r\n","\n"); sha=_hash_file(path)
    status,basis=document_identity(text,registry,canonical_name,verified_identifier)
    blocks=split_page_blocks(text); pages=sorted({b[0] for b in blocks})
    periods=sorted({m.group(0).strip() for m in PERIOD_RE.finditer(text[:20000])},key=str.casefold)
    doc_type={"annual reports":"annual_report_text_extract","quarterly reports":"quarterly_results_filing_text_extract"}.get(folder_hint,"text_extract")
    records=[]; source_records=[]
    for page,idx,body in blocks:
        flags=block_quality(body); tags=classify(body)
        warns=["Source is a PDF-to-CSV text extraction supplied without URL, publisher, or publication date; original PDF not available.",
               "Table structure and numeric cell boundaries are not reliable; verify any figure against the original filing before use.",
               f"Company association is document-level ({basis}), not established for this page individually." if status=="verified" else f"Company association unresolved: {basis}.",
               "Reporting period not assigned to this block; see document-level period candidates in ingestion_report.json."]
        warns+= [f"Quality flag: {f}." for f in flags]
        empty="fragment_or_empty" in flags
        locator=f"page:{page}:block:{idx}"
        rec=_record(source_path,locator,body,document_title=Path(path).name,document_type=doc_type,page_number=page,
            company_name=canonical_name if status=="verified" else None,verified_identifier=verified_identifier if status=="verified" else None,company_identity_status=status,
            evidence_category=";".join(tags) if tags else "unclassified",parsing_status="empty" if empty else "parsed",extraction_warnings=warns,
            source_identifier_status="repository_path_only",claim_verification_status="unverified",information_type="reported_fact")
        records.append(asdict(rec))
        source_records.append({"source_path":source_path,"source_sha256":sha,"source_record_id":"sr_"+hashlib.sha256(f"{sha}:{locator}".encode()).hexdigest()[:24],"evidence_id":rec.evidence_id,"raw_extracted_text":body,"quality_flags":flags})
    detail={"source_path":source_path,"source_sha256":sha,"size_bytes":len(raw),"folder_hint":folder_hint,"document_type":doc_type,"block_count":len(blocks),"distinct_pages":len(pages),
        "first_page":pages[0] if pages else None,"last_page":pages[-1] if pages else None,"page_numbers_contiguous":bool(pages) and pages==list(range(pages[0],pages[-1]+1)),
        "pages_missing_between_first_and_last":(pages[-1]-pages[0]+1-len(pages)) if pages else None,"identity_status":status,"identity_basis":basis,"period_candidates_from_text":periods[:6],
        "tag_counts":{t:sum(1 for r in records if t in r["evidence_category"].split(";")) for t in TAGS}}
    return records,source_records,detail

def ingest_directory(input_dir, output_dir, registry_path, canonical_name="NTPC Limited", root=None):
    registry=load_registry(registry_path)
    entity=next((e for e in registry.get("companies",[]) if e.get("canonical_name")==canonical_name),None)
    if not entity: raise ValueError(f"{canonical_name!r} is not in the registry")
    verified_identifier=entity.get("verified_identifier"); inp=Path(input_dir); root=Path(root) if root else inp
    files=sorted(p for p in inp.rglob("*.csv") if p.is_file() and not p.name.startswith("._") and "__MACOSX" not in p.parts)
    if not files: raise ValueError(f"No CSV files under {inp}")
    all_records=[]; all_sources=[]; docs=[]
    for f in files:
        rel=f.resolve().relative_to(root.resolve()).as_posix()
        recs,srcs,detail=ingest_document(f,rel,registry,canonical_name,verified_identifier,f.parent.name.casefold())
        all_records+=recs; all_sources+=srcs; docs.append(detail)
    schema=Config().schema_path.parent/"evidence_record.schema.json"
    for r in all_records: validate_output(r,schema)
    by_hash={}
    for d in docs: by_hash.setdefault(d["source_sha256"],[]).append(d["source_path"])
    report={"generated_at":dt.datetime.now(dt.timezone.utc).isoformat(),"company_under_test":canonical_name,"document_count":len(docs),"evidence_record_count":len(all_records),
        "schema_validated_records":len(all_records),"verified_record_count":sum(r["company_identity_status"]=="verified" for r in all_records),
        "unresolved_record_count":sum(r["company_identity_status"]!="verified" for r in all_records),"empty_or_fragment_records":sum(r["parsing_status"]=="empty" for r in all_records),
        "duplicate_documents":[{"source_sha256":h,"source_paths":p} for h,p in by_hash.items() if len(p)>1],
        "manual_review_evidence_ids_count":sum(1 for r in all_records if r["extraction_warnings"]),
        "auto_approved_records":0,"metrics_extracted":0,
        "notes":["Every record carries warnings and stays unverified; no numeric metric was extracted.","Association is document-level and only on exchange identifiers (ISIN, scrip code, NSE symbol label)."],
        "documents":docs}
    out=Path(output_dir); out.mkdir(parents=True,exist_ok=True)
    (out/"evidence.jsonl").write_text("".join(json.dumps(r,ensure_ascii=False)+"\n" for r in all_records),encoding="utf-8")
    (out/"source_records.jsonl").write_text("".join(json.dumps(r,ensure_ascii=False)+"\n" for r in all_sources),encoding="utf-8")
    (out/"ingestion_report.json").write_text(json.dumps(report,indent=2,ensure_ascii=False)+"\n",encoding="utf-8")
    return all_records,report

CATEGORY_ASSESSMENT = {
    "renewable_transition_and_revenue_mix": {
        "tag": "renewable_transition",
        "missing": ["Machine-reliable segment/energy-source revenue split (segment tables have labels detached from figures)", "Operating capacity and generation by fuel type for the same period", "Stated reporting basis (standalone vs consolidated) per figure"],
        "calculations_possible_after_review": ["Renewable share of installed capacity (MW) once a fuel-wise capacity table is manually transcribed", "Renewable share of generation (MU)", "Year-over-year change using FY annual reports (FY18-FY25) after unit and basis alignment"],
        "external_verification": ["Original annual report/results PDFs from NTPC or NSE/BSE", "NGEL filings for subsidiary-level renewable data"]},
    "announced_awarded_under_implementation_commissioned_capacity": {
        "tag": "capacity_pipeline",
        "missing": ["Dated project-level pipeline (announced vs awarded vs under implementation vs commissioned) from a single basis", "Quarterly capacity-addition disclosures: quarterly filings contain no capacity-tagged pages", "Award/LoA dates and commissioning dates"],
        "calculations_possible_after_review": ["Pipeline conversion ratios (awarded/announced, commissioned/awarded) only after project lists are transcribed", "Year-end installed capacity change from board-report statements, e.g. the FY2024-25 annual report capacity paragraph"],
        "external_verification": ["CEA/MNRE capacity records", "NTPC press releases and stock exchange commercial-operation intimations"]},
    "subsidiary_jv_related_party_supplier_customer_financing": {
        "tag": "relationships",
        "missing": ["Related-party transaction note tables with values (labels and values are separated or absent in extraction)", "Counterparty-level supplier/customer concentration", "Borrowing/guarantee schedules with maturity and counterparty"],
        "calculations_possible_after_review": ["Count and classification of subsidiaries/JVs per year from list pages", "Leverage and borrowing trends from debt-security disclosures after manual transcription"],
        "external_verification": ["Ind AS 24 note in original audited statements", "MCA filings for subsidiaries/JVs", "Rating agency reports for financing"]},
}

def build_category_readiness(records, report, per_category_cap=15):
    """Candidate review queues only: tagged page blocks are not validated facts and nothing here is approved."""
    out={"generated_at":dt.datetime.now(dt.timezone.utc).isoformat(),"approval_policy":"No record is approved; candidates require manual page review against original filings.","categories":{}}
    for name,spec in CATEGORY_ASSESSMENT.items():
        cands=[r for r in records if r["company_identity_status"]=="verified" and r["parsing_status"]=="parsed" and spec["tag"] in r["evidence_category"].split(";")]
        by_doc={}
        for r in cands: by_doc.setdefault(r["source_path"],[]).append(r)
        out["categories"][name]={"readiness":"candidate_review_queue_only","verified_association_candidate_count":len(cands),
            "candidate_evidence_ids_by_document":{d:[x["evidence_id"] for x in rs[:per_category_cap]] for d,rs in sorted(by_doc.items())},
            "usable_validated_evidence_ids":[],"missing_evidence":spec["missing"],"calculations_possible_after_review":spec["calculations_possible_after_review"],
            "quality_concerns":["No URL, publisher, or publication date for any file","Partial page coverage in most files","Detached table labels and values","Associations are document-level"],
            "external_verification_needed":spec["external_verification"]}
    return out

def main(argv=None):
    cfg=Config(); p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--input-dir",required=True,help="Directory tree of page-marker CSV text extractions")
    p.add_argument("--output-dir",required=True,help="Separate store; existing data/processed is never touched unless passed explicitly")
    p.add_argument("--registry",default=str(cfg.registry_path)); p.add_argument("--company",default="NTPC Limited",help="Canonical registry name to test association against")
    a=p.parse_args(argv)
    try:
        recs,rep=ingest_directory(a.input_dir,a.output_dir,a.registry,a.company,root=Path(a.input_dir).parent)
    except (OSError,ValueError) as e:
        print(f"Document text ingestion error: {e}",file=sys.stderr); return 2
    (Path(a.output_dir)/"category_readiness.json").write_text(json.dumps(build_category_readiness(recs,rep),indent=2,ensure_ascii=False)+"\n",encoding="utf-8")
    print(f"Ingested {rep['document_count']} documents into {rep['evidence_record_count']} page-block records ({rep['verified_record_count']} document-level verified, {rep['unresolved_record_count']} unresolved, {rep['empty_or_fragment_records']} empty/fragment). Report: {Path(a.output_dir)/'ingestion_report.json'}")
    return 0

if __name__=="__main__": raise SystemExit(main())
