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
from .machine_evidence import machine_evidence_eligible
from .structured_generation import generate_validated

WEIGHTS = {"financial_significance": .30, "evidence_availability": .25, "testability": .20, "non_obviousness": .075, "cross_validation_potential": .175}
MAX_F1_PAYLOAD_BYTES = 250_000
MAX_F1_EVIDENCE_RECORDS = 40
MAX_F1_EVIDENCE_RECORD_BYTES = 1_000_000

def weighted_score(scores):
    return sum((scores[key] / 5) * weight * 100 for key, weight in WEIGHTS.items())

def normalize_f1_scores(output):
    """Recompute arithmetic only; preserve hypotheses, ranks and recommendation."""
    corrections = []
    if not isinstance(output, dict) or not isinstance(output.get("ranked_candidates"), list):
        return corrections
    for candidate in output["ranked_candidates"]:
        if not isinstance(candidate, dict): continue
        scores = candidate.get("scores")
        if not isinstance(scores, dict) or set(scores) != set(WEIGHTS): continue
        if not all(isinstance(v, dict) and type(v.get("score")) is int and 0 <= v["score"] <= 5
                   for v in scores.values()): continue
        previous = candidate.get("weighted_score")
        if type(previous) not in (int, float): continue
        computed = round(weighted_score({k: v["score"] for k, v in scores.items()}), 10)
        if previous != computed:
            candidate["weighted_score"] = computed
            corrections.append({"candidate_id": candidate.get("candidate_id"),
                                "field": "weighted_score", "model_value": previous,
                                "computed_value": computed, "weights": WEIGHTS,
                                "formula": "sum((score / 5) * weight * 100)"})
    return corrections

def slim_for_local_model(records, config):
    """Small local context windows: send only fields the model reasons over.

    Applies to the Ollama provider only; stored records, eligibility gates and
    ID validation still use the full records. Hashes, paths and the duplicated
    issuer passage stay in the audit trail, not in the prompt.
    """
    if getattr(config, "provider", "").strip().lower() != "ollama":
        return records
    keep = ("evidence_id", "company_name", "document_title", "source_url", "source_locator", "page_number",
            "publication_date", "reporting_period", "metric_name", "metric_value", "unit", "excerpt_or_fact",
            "source_relationship", "claim_verification_status", "review_status", "extraction_warnings")
    return [{k: r[k] for k in keep if r.get(k) not in (None, "", [])} for r in records]


def f1_conclusions(output):
    """Existing decisions and scoring inputs a schema repair may not rewrite."""
    if not isinstance(output, dict): return {}
    result = {key: output[key] for key in ("ranking_reliable", "recommended_candidate_id") if key in output}
    candidates = output.get("ranked_candidates")
    if isinstance(candidates, list) and all(isinstance(c, dict) for c in candidates):
        result["candidates"] = [{key: c[key] for key in
            ("candidate_id", "rank", "category", "hypothesis", "scores") if key in c} for c in candidates]
    return result


ANGLE_RULES = {
    "renewable_transition": {
        "terms": ("renewable", "solar", "wind", "green energy", "renewable energy", "mix", "generation", "revenue"),
        "question": "Do issuer disclosures on renewable capacity and revenue or generation mix support the stated transition trajectory?",
        "metrics": ["renewable capacity and commissioned capacity by reporting period", "revenue or generation mix by source and reporting period"],
        "retrieve": ["Dated annual report and investor presentation with renewable capacity, generation or revenue mix", "Independent operating or regulatory data for the same periods"],
    },
    "capacity_conversion": {
        "terms": ("announced", "commission", "commissioned", "capacity", "project", "under implementation", "commercial operation", "cod", "trial operation"),
        "question": "Do dated project disclosures distinguish announced capacity from capacity that reached commissioning or commercial operation?",
        "metrics": ["announced, under-implementation and commissioned capacity on a consistent unit and period basis", "target, trial operation and commercial operation dates"],
        "retrieve": ["Project level issuer filings with dated status and capacity", "Independent regulator or system operator records confirming commissioning milestones"],
    },
    "hidden_relationships": {
        "terms": ("related party", "subsidiary", "joint venture", "counterparty", "supplier", "customer", "loan", "guarantee", "transaction", "investment"),
        "question": "Do disclosures identify financially material relationships whose terms or exposure merit independent checking?",
        "metrics": ["related party transaction value and period", "counterparty exposure, guarantees, loans or investment balance"],
        "retrieve": ["Related party and subsidiary disclosures with transaction values and periods", "Independent registry, regulator or counterparty records to test the relationship and terms"],
    },
}


def deterministic_angle_fallback(company, dataset_summary, records, failure_reason):
    """Rank research questions using eligible company evidence; never assert findings.

    Rule: each category gets up to 5 points for matching eligible records (one
    point per distinct evidence ID, capped at five), plus a small 0-2 score for
    explicit cross-checkability. Weighted scores use the published F1 weights.
    Categories with no matching evidence remain visible as unranked (score 0)
    research possibilities; if no eligible company evidence exists, stop.
    """
    valid_records = [r for r in records if r.get("evidence_id") and r.get("excerpt_or_fact") and
                     r.get("company_identity_status") == "verified" and r.get("parsing_status") == "parsed"
                     and str(r.get("company_name", "")).casefold() == company.casefold()]
    if not valid_records:
        return None
    candidates = []
    for category, rule in ANGLE_RULES.items():
        matches = []
        for r in valid_records:
            text = " ".join(str(r.get(k) or "") for k in ("excerpt_or_fact", "metric_name", "document_title")).lower()
            if any(term in text for term in rule["terms"]):
                matches.append(r)
        distinct = {r["evidence_id"]: r for r in matches}
        matching = list(distinct.values())[:5]
        availability = min(5, len(distinct))
        cross_check = 2 if availability >= 2 else (1 if availability == 1 else 0)
        scores = {
            "financial_significance": {"score": 4, "rationale": "Contest angle concerns potentially financially material disclosures; this is a prioritization rule, not a finding."},
            "evidence_availability": {"score": availability, "rationale": f"{len(distinct)} distinct eligible company evidence records matched the category terms; capped at 5."},
            "testability": {"score": 4 if availability else 2, "rationale": "The stated period and metric comparisons are directly retrievable; matching issuer evidence exists." if availability else "The defined comparison is testable through retrieval, but no supplied record matched this angle."},
            "non_obviousness": {"score": 3, "rationale": "Fixed neutral baseline applied equally to all contest-defined angles."},
            "cross_validation_potential": {"score": cross_check, "rationale": "Two points for at least two distinct matching records, one for one record, zero for none; independent sources are still required."},
        }
        ids = [r["evidence_id"] for r in matching]
        found = [{"statement": str(r["excerpt_or_fact"]), "source_type": str(r.get("document_type") or "issuer disclosure"),
                  "source_url": r.get("source_url"), "date": r.get("publication_date"),
                  "row_identifier": str(r.get("source_locator") or r.get("page_number") or r["evidence_id"]),
                  "evidence_id": r["evidence_id"], "status": "observed_in_ingested_source"} for r in matching]
        score_values = {k: v["score"] for k, v in scores.items()}
        candidates.append({"candidate_id": "fallback_" + category, "rank": 1, "category": category,
            "hypothesis": rule["question"], "financial_importance": "Investigate whether verified disclosures support or contradict a potentially material issue; no financial discovery is asserted.",
            "metrics_and_periods": rule["metrics"], "evidence_found": found,
            "additional_evidence_needed": rule["retrieve"],
            "alternative_explanation": "Reported movements or status differences may reflect timing, scope, consolidation basis or definitions rather than underperformance or undisclosed exposure.",
            "falsification_condition": "The defined comparison is reconciled on a consistent period, entity, unit and reporting basis, with independent records supporting the disclosed position.",
            "data_risks_and_limitations": ["This is research planning, not a verified financial finding.", "Issuer-only evidence is not independent corroboration.", "The NTPC quote CSV has no verified company join and is dataset context only."],
            "scores": scores, "weighted_score": round(weighted_score(score_values), 10),
            "weighted_score_rationale": "Deterministic score from the declared counts and fixed baseline rules; see manifest fallback method.",
            "next_research_action": "Retrieve the listed dated issuer and independent records, then verify company identity, exact passages, metric basis and counterevidence."})
    candidates.sort(key=lambda c: (-c["weighted_score"], c["category"]))
    for rank, candidate in enumerate(candidates, 1):
        candidate["rank"] = rank
    recommended = next((c for c in candidates if c["evidence_found"]), None)
    if not recommended:
        return None
    return {"company_name": company, "dataset_summary": dataset_summary, "ranking_reliable": True,
            "ranking_limitation": "Deterministic planning fallback used because the schema-valid model ranking was unusable or unreliable. Ranking prioritizes eligible company evidence matches; no verified financial finding is implied.",
            "ranked_candidates": candidates, "recommended_candidate_id": recommended["candidate_id"]}

def eligible_ingested_evidence(records, canonical_name, verified_identifier):
    """Shared F1/R1 gate: human approval OR independently rechecked PDF passages.

    Machine eligibility certifies exact extraction/provenance only, not claims,
    human review, source independence, or an evidence-strength grade.
    """
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
        ((r.get("review_status") == "approved" and approved_review(r)) or
         machine_evidence_eligible(r, canonical_name, verified_identifier))]

def validate_output(result, schema_path):
    schema = json.loads(Path(schema_path).read_text(encoding="utf-8"))
    errors = _validate(result, schema)
    if errors: raise ValueError("F1 output failed schema validation: " + "; ".join(errors))
    return result

def _validate(value, schema, path="$", root=None):
    root = root or schema
    errors=[]
    if "if" in schema:
        branch = "else" if _validate(value, schema["if"], path, root) else "then"
        if branch in schema: errors.extend(_validate(value, schema[branch], path, root))
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
        if len(value)>schema.get("maxLength",float("inf")): errors.append(f"{path}: string is too long")
        if "pattern" in schema and not re.search(schema["pattern"], value): errors.append(f"{path}: string does not match pattern")
        if schema.get("format")=="uri" and value and not value.startswith(("https://","http://")): errors.append(f"{path}: expected URI")
    if isinstance(value,(int,float)) and not isinstance(value,bool):
        if value<schema.get("minimum",float("-inf")) or value>schema.get("maximum",float("inf")): errors.append(f"{path}: number outside allowed range")
    if "const" in schema and value != schema["const"]: errors.append(f"{path}: value does not match required constant")
    if "enum" in schema and value not in schema["enum"]: errors.append(f"{path}: value not in enum")
    return errors

def inspect_csv(path):
    _, meta = load_csv(path)
    print(json.dumps(meta, indent=2, ensure_ascii=False))

def run(company, csv_path, output_path, config=None, *, research_question=None):
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
        raise DataLoadError(limitation + " No human-reviewed, approved, company-specific ingested evidence was available either, nor eligible automatically_cross_checked evidence; F1 cannot run without company-specific evidence.")
    company_rows=evidence_summary(rows,meta,company) if meta["company_filtering_available"] else {"company":company,"rows":[],"limitation":meta["company_filter_limitation"],"matched_rows":0}
    payload = {"company": company, "company_records": company_rows,
        "dataset_level_profile_not_company_evidence": {"row_count": audit["row_count"], "columns": audit["column_names"], "quality_warnings": audit["quality_warnings"], "limitations": audit["limitations"]},
        "research_readiness_matrix": readiness["candidate_categories"],
        "verified_ingested_evidence": slim_for_local_model(ingested_evidence, config),
        "ingested_evidence_quality_warnings": evidence_warnings,
        "f1_scoring_weights_percent": {"financial_significance":30,"evidence_availability":25,"testability":20,"non_obviousness":7.5,"cross_validation_potential":17.5},
        "evidence_boundary": "Only company_records and verified_ingested_evidence contain selected-company evidence. Dataset profile values are dataset-level context, never company-specific evidence. automatically_cross_checked records passed deterministic original-PDF identity/hash/page/passage checks, not human approval or claim verification. Neither approval state establishes independent corroboration or justifies Strong/Moderate evidence strength.",
        "data_limitations": [f"Column {c!r} has {n} missing values." for c,n in meta["missing_values"].items() if n] + audit["quality_warnings"]}
    if research_question:
        payload["assigned_research_question"] = research_question
    payload_bytes = len(json.dumps(payload, ensure_ascii=False).encode("utf-8"))
    if payload_bytes > MAX_F1_PAYLOAD_BYTES:
        raise DataLoadError(f"F1 request payload is {payload_bytes} bytes; maximum is {MAX_F1_PAYLOAD_BYTES}. Reduce the reviewed evidence bundle before retrying.")
    prompt = (config.prompt_dir / "f1_research_angle_selector.md").read_text(encoding="utf-8")
    if research_question:
        prompt += "\nPrioritize testable angles that answer assigned_research_question. Do not replace it with an unrelated research family merely because that evidence is easier to find."
        prompt += "\nRead verified_ingested_evidence as the principal research input. The anonymous quote CSV is only excluded context; its lack of operational columns does not erase eligible PDF disclosures. Cite supplied PDF evidence IDs when present."
    supplied_ids = {record["evidence_id"] for record in ingested_evidence}
    def validate_f1(result):
        validate_output(result, config.schema_path)
        candidates = result["ranked_candidates"]
        candidate_ids = [c["candidate_id"] for c in candidates]
        if len(candidate_ids) != len(set(candidate_ids)):
            raise ValueError("F1 candidate IDs must be unique")
        if result["recommended_candidate_id"] is not None and result["recommended_candidate_id"] not in candidate_ids:
            raise ValueError("F1 recommended candidate was not supplied in ranked_candidates")
        for candidate in candidates:
            for item in candidate["evidence_found"]:
                if item.get("evidence_id") is not None and item["evidence_id"] not in supplied_ids:
                    raise ValueError("F1 evidence_id was not supplied")
    output = generate_validated(prompt, payload, config, schema_path=config.schema_path,
        output_path=output_path, generate=generate_json, validate=validate_f1,
        normalize=normalize_f1_scores, preserve=f1_conclusions, stage="f1")
    out = Path(output_path); out.parent.mkdir(parents=True, exist_ok=True)
    rec_id = output.get("recommended_candidate_id")
    usable = output.get("ranking_reliable") and rec_id and any(c.get("candidate_id") == rec_id for c in output.get("ranked_candidates", []))
    if not usable:
        reason = ("model returned ranking_reliable=false" if not output.get("ranking_reliable") else
                  "model returned no recommendation or recommendation did not identify a candidate")
        model_output_path = out.with_name(out.stem + "_model_output.json")
        model_output_path.write_text(json.dumps(output, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        fallback = deterministic_angle_fallback(canonical, output.get("dataset_summary", {}), ingested_evidence, reason)
        if fallback is not None:
            validate_output(fallback, config.schema_path)
            output = fallback
            (out.parent / "f1_fallback.json").write_text(json.dumps({"used": True, "reason": reason,
                "method": "For each contest angle, count distinct eligible company evidence IDs whose excerpt, metric name or title contains its fixed keyword list (0-5). Fixed scores: financial significance 4, testability 4 with a match or 2 without, non-obviousness 3; cross-validation potential 0/1/2 for zero/one/two-or-more distinct matching IDs. Apply existing F1 weights and sort by weighted score, then category. At least one angle must cite an eligible record.",
                "evidence_ids_by_category": {c["category"]: [e["evidence_id"] for e in c["evidence_found"]] for c in output["ranked_candidates"]},
                "ranking_type": "deterministic_research_planning_fallback", "financial_finding": False}, indent=2) + "\n", encoding="utf-8")
        else:
            (out.parent / "f1_fallback.json").write_text(json.dumps({"used": False, "reason": reason,
                "blocked": "No eligible company-specific evidence matched; no generic candidates were manufactured."}, indent=2) + "\n", encoding="utf-8")
    else:
        (out.parent / "f1_fallback.json").write_text(json.dumps({"used": False, "reason": None,
            "ranking_type": "model_generated", "financial_finding": False}, indent=2) + "\n", encoding="utf-8")
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
