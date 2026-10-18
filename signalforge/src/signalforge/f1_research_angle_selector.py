"""F1 command line runner and score helpers."""
import argparse
import datetime as dt
import json
import os
import re
import sys
from pathlib import Path

from .config import Config
from .data_loader import DataLoadError, evidence_summary, filter_company, load_csv
from .llm_client import LLMError, generate_json
from .dataset_audit import build_readiness, profile_dataset
from .evidence_ingestion import load_registry, verify_company

WEIGHTS = {"financial_significance": .30, "evidence_availability": .25, "testability": .20, "non_obviousness": .075, "cross_validation_potential": .175}
MAX_F1_PAYLOAD_BYTES = 250_000
MAX_F1_EVIDENCE_RECORDS = 40
MAX_F1_EVIDENCE_RECORD_BYTES = 1_000_000

def weighted_score(scores):
    return sum((scores[key] / 5) * weight * 100 for key, weight in WEIGHTS.items())

def eligible_ingested_evidence(records, canonical_name, verified_identifier):
    def approved_review(record):
        reviewer, timestamp, note = (record.get(k) for k in ("reviewed_by", "reviewed_at", "review_note"))
        if not all(isinstance(v, str) and v.strip() for v in (reviewer, timestamp, note)):
            return False
        try:
            parsed = dt.datetime.fromisoformat(timestamp.strip().replace("Z", "+00:00"))
        except ValueError:
            return False
        return parsed.tzinfo is not None and parsed.utcoffset() is not None

    def identity_matches(record):
        name_matches = str(record.get("company_name") or "").strip().casefold() == str(canonical_name or "").strip().casefold()
        identifier_matches = bool(verified_identifier) and str(record.get("verified_identifier") or "").strip().casefold() == str(verified_identifier).strip().casefold()
        return name_matches and (identifier_matches if verified_identifier else True)

    return [r for r in records if r.get("company_identity_status") == "verified" and identity_matches(r) and
        r.get("parsing_status") == "parsed" and isinstance(r.get("excerpt_or_fact"), str) and bool(r["excerpt_or_fact"].strip()) and
        r.get("review_status") == "approved" and approved_review(r)]

def validate_output(result, schema_path):
    schema = json.loads(Path(schema_path).read_text(encoding="utf-8"))
    errors = _validate(result, schema)
    if errors: raise ValueError("F1 output failed schema validation: " + "; ".join(errors))
    return result

def _validate(value, schema, path="$", root=None):
    root = root or schema
    errors=[]
    if "$ref" in schema:
        target = root
        for part in schema["$ref"].removeprefix("#/").split("/"): target=target[part]
        return _validate(value,target,path,root)
    typ=schema.get("type")
    allowed=[typ] if isinstance(typ,str) else typ
    checks={"object":lambda x:isinstance(x,dict),"array":lambda x:isinstance(x,list),"string":lambda x:isinstance(x,str),"integer":lambda x:isinstance(x,int) and not isinstance(x,bool),"number":lambda x:isinstance(x,(int,float)) and not isinstance(x,bool),"boolean":lambda x:isinstance(x,bool),"null":lambda x:x is None}
    if allowed and not any(checks[t](value) for t in allowed): return [f"{path}: expected {' or '.join(allowed)}"]
    if isinstance(value,dict):
        for k in schema.get("required",[]):
            if k not in value: errors.append(f"{path}: missing required property {k!r}")
        if schema.get("additionalProperties") is False:
            errors.extend(f"{path}: unexpected property {k!r}" for k in value if k not in schema.get("properties",{}))
        for k,v in value.items():
            if k in schema.get("properties",{}): errors.extend(_validate(v,schema["properties"][k],f"{path}/{k}",root))
    if isinstance(value,list):
        for i,v in enumerate(value):
            if "items" in schema: errors.extend(_validate(v,schema["items"],f"{path}/{i}",root))
    if isinstance(value,str):
        if len(value)<schema.get("minLength",0): errors.append(f"{path}: string is too short")
        if schema.get("format")=="uri" and value and not value.startswith(("https://","http://")): errors.append(f"{path}: expected URI")
    if isinstance(value,(int,float)) and not isinstance(value,bool):
        if value<schema.get("minimum",float("-inf")) or value>schema.get("maximum",float("inf")): errors.append(f"{path}: number outside allowed range")
    if "const" in schema and value != schema["const"]: errors.append(f"{path}: value does not match required constant")
    if "enum" in schema and value not in schema["enum"]: errors.append(f"{path}: value not in enum")
    return errors

def inspect_csv(path):
    _, meta = load_csv(path)
    print(json.dumps(meta, indent=2, ensure_ascii=False))

def run(company, csv_path, output_path, config=None):
    config = config or Config()
    rows, meta = load_csv(csv_path)
    canonical, verified_identifier, identity_status = verify_company(company, load_registry(config.registry_path))
    if identity_status != "verified":
        raise DataLoadError(f"Company identity for {company!r} is unresolved in the registry; F1 company-specific joins are disabled until an authoritative verification source is recorded.")
    selected = filter_company(rows, meta, company) if meta["company_filtering_available"] else []
    _, audit = profile_dataset(csv_path)
    readiness = build_readiness(audit, rows, company)
    ingested_evidence=[]
    evidence_warnings=[]
    evidence_path=config.evidence_dir / "evidence.jsonl"
    report_path=config.evidence_dir / "ingestion_report.json"
    if evidence_path.is_file():
        evidence_schema_path = config.schema_path.parent / "evidence_record.schema.json"
        evidence_schema = json.loads(evidence_schema_path.read_text(encoding="utf-8"))
        seen_evidence_ids = set()
        with evidence_path.open(encoding="utf-8") as evidence_file:
            line_no = 0
            while True:
                line = evidence_file.readline(MAX_F1_EVIDENCE_RECORD_BYTES + 1)
                if not line: break
                line_no += 1
                if len(line.encode("utf-8")) > MAX_F1_EVIDENCE_RECORD_BYTES:
                    raise DataLoadError(f"Normalized evidence record at line {line_no} exceeds {MAX_F1_EVIDENCE_RECORD_BYTES} bytes.")
                if not line.strip(): continue
                try: record = json.loads(line)
                except json.JSONDecodeError as e: raise DataLoadError(f"Invalid normalized evidence JSONL at line {line_no}: {e.msg}") from e
                if not isinstance(record, dict): raise DataLoadError(f"Invalid normalized evidence at line {line_no}: expected a JSON object.")
                errors = _validate(record, evidence_schema, root=evidence_schema)
                if errors: raise DataLoadError(f"Invalid normalized evidence at line {line_no}: {errors[0]}.")
                evidence_id = record.get("evidence_id")
                if not re.fullmatch(r"ev_[a-f0-9]{24}", evidence_id or ""):
                    raise DataLoadError(f"Invalid normalized evidence at line {line_no}: evidence_id has invalid format.")
                if evidence_id in seen_evidence_ids:
                    raise DataLoadError(f"Duplicate evidence_id {evidence_id!r} in normalized evidence JSONL.")
                seen_evidence_ids.add(evidence_id)
                if eligible_ingested_evidence([record], canonical, verified_identifier):
                    ingested_evidence.append(record)
                    if len(ingested_evidence) > MAX_F1_EVIDENCE_RECORDS:
                        raise DataLoadError(f"F1 evidence bundle has more than {MAX_F1_EVIDENCE_RECORDS} approved records; maximum is {MAX_F1_EVIDENCE_RECORDS}.")
        if report_path.is_file():
            report=json.loads(report_path.read_text(encoding="utf-8"))
            relevant_ids={r["evidence_id"] for r in ingested_evidence}
            evidence_warnings=[w for w in report.get("data_quality_warnings",[]) if w.get("evidence_id") in relevant_ids]
    if not selected and not ingested_evidence:
        limitation=meta["company_filter_limitation"] if not meta["company_filtering_available"] else f"No rows for {company!r} were found."
        raise DataLoadError(limitation + " No human-reviewed, approved, company-specific ingested evidence was available either; F1 cannot run without company-specific evidence.")
    company_rows=evidence_summary(rows,meta,company) if meta["company_filtering_available"] else {"company":company,"rows":[],"limitation":meta["company_filter_limitation"],"matched_rows":0}
    payload = {"company": company, "company_records": company_rows,
        "dataset_level_profile_not_company_evidence": {"row_count": audit["row_count"], "columns": audit["column_names"], "quality_warnings": audit["quality_warnings"], "limitations": audit["limitations"]},
        "research_readiness_matrix": readiness["candidate_categories"],
        "verified_ingested_evidence": ingested_evidence,
        "ingested_evidence_quality_warnings": evidence_warnings,
        "f1_scoring_weights_percent": {"financial_significance":30,"evidence_availability":25,"testability":20,"non_obviousness":7.5,"cross_validation_potential":17.5},
        "evidence_boundary": "Only company_records and verified_ingested_evidence contain selected-company evidence. Dataset profile values are dataset-level context, never company-specific evidence.",
        "data_limitations": [f"Column {c!r} has {n} missing values." for c,n in meta["missing_values"].items() if n] + audit["quality_warnings"]}
    payload_bytes = len(json.dumps(payload, ensure_ascii=False).encode("utf-8"))
    if payload_bytes > MAX_F1_PAYLOAD_BYTES:
        raise DataLoadError(f"F1 request payload is {payload_bytes} bytes; maximum is {MAX_F1_PAYLOAD_BYTES}. Reduce the reviewed evidence bundle before retrying.")
    prompt = (config.prompt_dir / "f1_research_angle_selector.md").read_text(encoding="utf-8")
    output = generate_json(prompt, payload, config)
    validate_output(output, config.schema_path)
    out = Path(output_path); out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(output, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    recommendation = output.get("recommended_candidate_id")
    rec = next((x for x in output["ranked_candidates"] if x["candidate_id"] == recommendation), None)
    print(f"F1 completed for {company}. Candidates: {len(output['ranked_candidates'])}; reliable ranking: {output['ranking_reliable']}; recommendation: {rec['hypothesis'] if rec else 'none'}. Saved {out}")
    return output

def main(argv=None):
    config = Config()
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--company", help="Selected company (requires a company identifier column in the CSV)")
    parser.add_argument("--csv", default=str(config.csv_path), help="CSV path")
    parser.add_argument("--output", default=str(config.output_dir / "f1_output.json"), help="Output JSON path")
    parser.add_argument("--inspect", action="store_true", help="Print dataset metadata and exit")
    args = parser.parse_args(argv)
    try:
        if args.inspect: inspect_csv(args.csv); return 0
        if not args.company: parser.error("--company is required unless --inspect is used")
        run(args.company, args.csv, args.output, config)
        return 0
    except (FileNotFoundError, DataLoadError, LLMError, ValueError, OSError) as e:
        print(f"F1 error: {e}", file=sys.stderr)
        return 2

if __name__ == "__main__":
    raise SystemExit(main())
