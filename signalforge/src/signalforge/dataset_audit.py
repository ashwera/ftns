"""Dataset profiling and evidence-based Energy, Power & Renewables readiness audit."""
import argparse
import datetime as dt
import json
import math
import re
import sys
from pathlib import Path

from .data_loader import DataLoadError, _norm, _parse_date, load_csv
from .config import Config

CATEGORIES = ("renewable_transition", "capacity_conversion", "hidden_relationships")
CATEGORY_TERMS = {
    "renewable_transition": ("renewable", "generation", "energy mix", "revenue mix", "solar", "wind", "target", "emission", "green"),
    "capacity_conversion": ("capacity", "commission", "award", "awarded", "project", "under implementation", "announced", "mw", "gw"),
    "hidden_relationships": ("subsidiary", "joint venture", "related party", "supplier", "customer", "counterparty", "financing", "lender"),
}
COMPANY_TERMS = {"company", "company name", "issuer", "issuer name", "security name", "entity", "entity name", "corporate name"}
TICKER_TERMS = {"ticker", "symbol", "stock symbol", "trading symbol"}

def _number(raw):
    s = raw.strip().replace(",", "")
    if s.endswith("%"): s=s[:-1]
    try:
        n=float(s)
        return n if math.isfinite(n) else None
    except (ValueError, TypeError): return None

def _sensitive(column):
    n=_norm(column)
    return any(t in n.split() for t in ("email", "phone", "mobile", "address", "password", "token", "secret", "account"))

def _categorical_values(rows, column):
    from collections import Counter
    vals=Counter(r[column] for r in rows if r.get(column))
    return [{"value":v,"count":c} for v,c in vals.most_common(20)]

def _numeric_stats(rows, column):
    vals=[v for r in rows if (v:=_number(r.get(column,""))) is not None]
    if not vals: return None
    vals.sort(); n=len(vals)
    def percentile(p): return vals[round((n-1)*p)]
    return {"count":n,"min":vals[0],"max":vals[-1],"mean":round(sum(vals)/n,6),"median":percentile(.5)}

def _business_duplicates(rows, fields, company_cols, date_cols):
    # Repeated company/date records are a useful warning; no arbitrary business key is assumed.
    key_cols=company_cols+date_cols
    if len(key_cols)<2: return {"key_columns":key_cols,"duplicate_records":None,"limitation":"No verified company-plus-date key is available."}
    keys=[tuple(r.get(c,"").casefold() for c in key_cols) for r in rows]
    return {"key_columns":key_cols,"duplicate_records":len(keys)-len(set(keys)),"limitation":None}

def profile_dataset(csv_path):
    rows, meta = load_csv(csv_path, allow_empty=True)
    fields=meta["columns"]
    date_cols=[]
    date_values={}
    for c in fields:
        found=[(i,_parse_date(r.get(c,""))) for i,r in enumerate(rows) if _parse_date(r.get(c,""))]
        if found and (any(t in _norm(c).split() for t in ("date","period","year","time")) or len(found)>=max(1,int(.8*len(rows)))):
            date_cols.append(c); date_values[c]=[d for _,d in found]
    numeric_cols=[c for c in fields if rows and sum(_number(r.get(c,"")) is not None for r in rows)>=max(1,int(.8*sum(bool(r.get(c,"")) for r in rows)))]
    company_cols=[c for c in fields if _norm(c) in COMPANY_TERMS|TICKER_TERMS]
    ticker_cols=[c for c in fields if _norm(c) in TICKER_TERMS]
    categorical={c:_categorical_values(rows,c) for c in fields if c not in numeric_cols and c not in date_cols and len({r.get(c) for r in rows if r.get(c)})<=100}
    field_stats={}
    for c in fields:
        miss=meta["missing_values"][c]
        field_stats[c]={"inferred_type":meta["types"][c],"missing_count":miss,"missing_percentage":round(100*miss/len(rows),2) if rows else 0,
                        "sensitive_excluded_from_samples":_sensitive(c)}
        if c in numeric_cols: field_stats[c]["numeric_summary"]=_numeric_stats(rows,c)
        if c in date_cols:
            dates=date_values[c]
            field_stats[c]["date_coverage"]={"start":min(dates).isoformat(),"end":max(dates).isoformat()}
    sample_fields=[c for c in fields if not _sensitive(c)]
    samples=[{c:r[c] for c in sample_fields} for r in rows[:5]]
    dates=[d for col in date_cols for d in date_values.get(col,[])]
    today=dt.datetime.now(dt.timezone.utc).date()
    quality=[]
    if meta["malformed_record_count"]: quality.append(f"{meta['malformed_record_count']} malformed CSV records were skipped (physical lines {meta['malformed_record_lines'][:20]}).")
    if meta["duplicate_rows"]: quality.append(f"{meta['duplicate_rows']} exact duplicate rows detected.")
    if dates and max(dates)>today: quality.append("One or more detected dates are in the future relative to the audit date.")
    stale=[d for d in dates if d < today-dt.timedelta(days=365*5)]
    if stale: quality.append(f"Detected dates include records older than five years ({len(stale)} values); assess staleness against intended use.")
    if not company_cols: quality.append("No recognized company or ticker identifier field; company coverage cannot be verified from rows.")
    lower={_norm(c):c for c in fields}
    for c in numeric_cols:
        if any(term in _norm(c).split() for term in ("volume","value","trades","trade","capacity")):
            negatives=[i+2 for i,r in enumerate(rows) if (_number(r.get(c,"")) is not None and _number(r.get(c,""))<0)]
            if negatives: quality.append(f"Potentially suspicious negative values in {c!r} at CSV lines {negatives[:20]}.")
    ohlc=[(term,c) for term in ("open","high","low","close") for c in fields if _norm(c)==term]
    if len(ohlc)==4:
        names=dict(ohlc)
        bad=[]
        for i,r in enumerate(rows,2):
            o,h,l,c=(_number(r.get(names[k],"")) for k in ("open","high","low","close"))
            if None not in (o,h,l,c) and (h<l or max(o,c)>h or min(o,c)<l): bad.append(i)
        if bad: quality.append(f"OHLC range inconsistencies at CSV lines {bad[:20]}.")
    urls=[c for c in fields if "url" in _norm(c).split() or "link" in _norm(c).split()]
    docs=[c for c in fields if any(t in _norm(c).split() for t in ("document","filing","accession","report id"))]
    pubdates=[c for c in fields if any(t in _norm(c).split() for t in ("publication","published","filing date"))]
    currencies=[c for c in fields if any(t in _norm(c).split() for t in ("currency","ccy")) or any(x in c for x in ("₹","INR","USD","EUR"))]
    units=[c for c in fields if any(t in _norm(c).split() for t in ("unit","units")) or re.search(r"\b(mw|gw|mwh|gwh|twh|crore|lakh|million|billion)\b",c,re.I)]
    periods=[c for c in fields if any(t in _norm(c).split() for t in ("period","quarter","fiscal","year"))]
    audit={"dataset_filename":Path(csv_path).name,"file_path":str(Path(csv_path).resolve()),"file_format":Path(csv_path).suffix.lower().lstrip(".") or "unknown",
        "audit_timestamp":dt.datetime.now(dt.timezone.utc).isoformat(),"row_count":len(rows),"column_count":len(fields),"column_names":fields,
        "inferred_types":meta["types"],"field_statistics":field_stats,"sample_records":samples,"sample_excluded_sensitive_fields":[c for c in fields if _sensitive(c)],
        "exact_duplicate_rows":meta["duplicate_rows"],"potential_duplicate_business_records":_business_duplicates(rows,fields,company_cols,date_cols),
        "date_columns":date_cols,"date_coverage":{c:field_stats[c]["date_coverage"] for c in date_cols},"numeric_columns":numeric_cols,
        "categorical_values":categorical,"company_identifier_columns":company_cols,
        "distinct_companies":sorted({r[c] for c in company_cols for r in rows if r.get(c)}) if company_cols else [],
        "distinct_tickers":sorted({r[c] for c in ticker_cols for r in rows if r.get(c)}) if ticker_cols else [],
        "source_url_columns":urls,"document_identifier_columns":docs,"filing_or_publication_date_columns":pubdates,
        "currency_columns":currencies,"unit_columns":units,"financial_period_columns":periods,
        "quality_warnings":quality,"temporal_assessment":{"audit_date":today.isoformat(),"future_dated_records":sum(d>today for d in dates),"records_older_than_five_years":len(stale),"leakage_note":"Future timestamps and stale records were checked. Potential target leakage still depends on how time-indexed rows are used in a later prediction task."},
        "malformed_records":{"count":meta["malformed_record_count"],"physical_lines":meta["malformed_record_lines"]},
        "limitations":([meta["company_filter_limitation"]] if not company_cols else []) + (["No source/document provenance fields identified."] if not urls and not docs else [])}
    return rows, audit

def build_readiness(audit, rows, company=None, categories=CATEGORIES):
    unsupported=set(categories)-set(CATEGORIES)
    if unsupported: raise ValueError(f"Unsupported research category: {sorted(unsupported)[0]}")
    fields=audit["column_names"]
    allcols={_norm(c):c for c in fields}
    company_cols=audit["company_identifier_columns"]
    selected=rows
    if company:
        if not company_cols: selected=[]
        else: selected=[r for r in rows if any(r.get(c,"").casefold()==company.strip().casefold() for c in company_cols)]
    company_records=bool(company and selected)
    assessments=[]
    for category in categories:
        terms=CATEGORY_TERMS[category]
        matched=[c for c in fields if any(term in _norm(c) for term in terms)]
        observed_rows=[{c:r[c] for c in matched if r.get(c)} for r in selected[:5] if any(r.get(c) for c in matched)] if company else []
        if category=="renewable_transition": required=["revenue or generation by source", "renewable targets and baseline", "actual progress by consistent period"]
        elif category=="capacity_conversion": required=["project or asset identifier", "announced/awarded/under-implementation status", "commissioning status/date", "capacity and unit"]
        else: required=["named counterparties/entities", "relationship type", "period", "transaction or exposure value"]
        absent=[x for x in required if not matched]
        if company and not company_records: rating="not_ready"; rationale="No company-specific rows could be selected using a verified identifier."
        elif matched: rating="limited_screening"; rationale="Some potentially relevant fields exist, but key context and provenance are incomplete; field-name matches alone do not establish evidence."
        else: rating="not_ready"; rationale="No relevant category fields are present in the dataset."
        category_evidence={"columns":matched,"observed_company_records":observed_rows if company else [],"records_scope":"company_filtered" if company else "not_filtered"}
        next_action=("Add a verified company-level dataset with the listed fields and source provenance, then cross-check against primary disclosures." if rating!="defensible" else "Cross-validate each material claim against independent primary sources.")
        assessments.append({"category":category,"evidence_available":category_evidence,"evidence_missing":required if not matched else absent,
            "data_quality":{"rating":rating,"rationale":rationale,"dataset_quality_warnings":audit["quality_warnings"]},
            "relevant_metrics_calculable":[],"external_verification_requirements":["Company filings and annual reports","Exchange disclosures","Regulatory or project commissioning documents","Independent credible reporting"],
            "readiness_rating":rating,"readiness_rationale":rationale,"recommended_next_action":next_action,
            "claims_not_supported_by_this_dataset":[f"Do not claim {category.replace('_',' ')} progress or outcomes without direct, dated supporting fields and provenance."]})
    return {"dataset_filename":audit["dataset_filename"],"audit_timestamp":audit["audit_timestamp"],"company_filter":company,
        "company_filter_applied":bool(company and company_records),"candidate_categories":assessments,
        "f1_weights":{"financial_significance":30,"evidence_availability":25,"testability":20,"non_obviousness":7.5,"cross_validation_potential":17.5,"total":100},
        "overall_readiness":"not_ready" if not company_records and company else "limited_screening" if any(x["readiness_rating"]!="not_ready" for x in assessments) else "not_ready",
        "overall_rationale":"Current repository CSV contains daily trading quotes only, with no verified company identifier or operating/fundamental evidence."}

def audit_csv(csv_path, output_dir, company=None):
    rows,audit=profile_dataset(csv_path)
    readiness=build_readiness(audit,rows,company)
    out=Path(output_dir); out.mkdir(parents=True,exist_ok=True)
    (out/"dataset_audit.json").write_text(json.dumps(audit,indent=2,ensure_ascii=False)+"\n",encoding="utf-8")
    (out/"research_readiness.json").write_text(json.dumps(readiness,indent=2,ensure_ascii=False)+"\n",encoding="utf-8")
    return audit,readiness

def main(argv=None):
    cfg=Config(); parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--csv-path",default=str(cfg.csv_path)); parser.add_argument("--output-dir",default=str(cfg.output_dir)); parser.add_argument("--company")
    args=parser.parse_args(argv)
    try:
        audit,ready=audit_csv(args.csv_path,args.output_dir,args.company)
        print(f"Dataset audit: {audit['row_count']} rows x {audit['column_count']} columns ({audit['dataset_filename']}).")
        print(f"Company identifiers: {audit['company_identifier_columns'] or 'none'}; missing values: {sum(x['missing_count'] for x in audit['field_statistics'].values())}; exact duplicates: {audit['exact_duplicate_rows']}.")
        print(f"Research readiness: {ready['overall_readiness']}. Category ratings: " + ", ".join(f"{x['category']}={x['readiness_rating']}" for x in ready['candidate_categories']))
        print(f"Saved {Path(args.output_dir)/'dataset_audit.json'} and {Path(args.output_dir)/'research_readiness.json'}")
        return 0
    except (OSError,DataLoadError,ValueError) as e:
        print(f"Dataset audit error: {e}",file=sys.stderr); return 2

if __name__=="__main__": raise SystemExit(main())
