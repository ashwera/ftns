"""R1 research-plan runner. Consumes F1 output and supplied evidence IDs; performs no retrieval."""
import argparse
import copy
import json
import re
import sys
from pathlib import Path

from .config import Config
from .evidence_ingestion import load_registry, verify_company
from .f1_research_angle_selector import MAX_F1_EVIDENCE_RECORDS, _validate, eligible_ingested_evidence
from .llm_client import LLMError, generate_json
from .structured_generation import generate_validated

def validate_plan(plan, schema_path, supplied_ids=()):
    schema = json.loads(Path(schema_path).read_text(encoding="utf-8"))
    errors = _validate(plan, schema)
    known = set(supplied_ids)
    for i, item in enumerate(plan.get("evidence_ledger", []) if isinstance(plan, dict) else []):
        eid = item.get("evidence_id") if isinstance(item, dict) else None
        if eid is not None and eid not in known: errors.append(f"$/evidence_ledger/{i}: evidence_id was not supplied")
        if isinstance(item, dict) and item.get("status") == "planned_lookup" and (item.get("source_url") or item.get("excerpt_or_data_point")):
            errors.append(f"$/evidence_ledger/{i}: planned lookup must not contain a URL or excerpt")
    if errors: raise ValueError("R1 output failed validation: " + "; ".join(errors))
    return plan


def supplied_sources(config, company, ids):
    """Only original, eligible evidence supplies ledger text and provenance."""
    records={}
    canonical,identifier,status=verify_company(company,load_registry(config.registry_path))
    if status!='verified':return records
    for line in (config.evidence_dir/'evidence.jsonl').read_text().splitlines() if (config.evidence_dir/'evidence.jsonl').is_file() else ():
        try:record=json.loads(line)
        except json.JSONDecodeError:continue
        if isinstance(record,dict) and record.get('evidence_id') in ids and eligible_ingested_evidence([record],canonical,identifier):
            records[record['evidence_id']]={'evidence_id':record['evidence_id'],'source_url':record.get('source_url'),
                'publication_date':record.get('publication_date'),'excerpt_or_data_point':record['excerpt_or_fact']}
    return records


def ledger_generation_schema(schema, company, candidate_id, records):
    """Stronger generation constraints; the original R1 validator stays mandatory."""
    schema=copy.deepcopy(schema)
    def require_all(value):
        if isinstance(value,dict):
            if value.get('type')=='object':value['required']=list(value.get('properties',{}))
            for item in value.values():require_all(item)
        elif isinstance(value,list):
            for item in value:require_all(item)
    require_all(schema)
    props=schema['properties']
    props['company_name']['enum']=[company]
    props['candidate_id']['enum']=[candidate_id]
    ledger=props['evidence_ledger']['items']['properties']
    ledger['evidence_id']['enum']=[None,*records]
    ledger['source_url']['enum']=list(dict.fromkeys([None,*[r['source_url'] for r in records.values()]]))
    ledger['publication_date']['enum']=list(dict.fromkeys([None,*[r['publication_date'] for r in records.values()]]))
    excerpts=[None]
    for record in records.values():
        text=record['excerpt_or_data_point']
        options=[line for line in text.splitlines() if 30<=len(line)<=240]
        excerpts.extend(options[:8] or [text[:240]])
    ledger['excerpt_or_data_point']['enum']=list(dict.fromkeys(excerpts))
    for field in ('research_questions','checklist'):props[field]['maxItems']=3
    props['evidence_ledger']['maxItems']=4
    return schema


def validate_ledger_sources(plan, records):
    for item in plan.get('evidence_ledger',[]):
        if item['status']=='planned_lookup':
            if any(item.get(k) is not None for k in ('evidence_id','source_url','publication_date','excerpt_or_data_point')):
                raise ValueError('R1 planned lookup must have null evidence ID, URL, date and excerpt')
            continue
        if item['status'] in {'supplied','contradictory'} or item.get('evidence_id') is not None:
            source=records.get(item.get('evidence_id'))
            if source is None:raise ValueError('R1 supplied ledger item requires an eligible evidence ID')
            for field in ('source_url','publication_date'):
                if item.get(field)!=source[field]:raise ValueError(f'R1 supplied {field} must match original evidence; use null when unavailable')
            quote=item.get('excerpt_or_data_point')
            if quote and ' '.join(quote.split()) not in ' '.join(source['excerpt_or_data_point'].split()):
                raise ValueError('R1 supplied excerpt must be an exact contiguous span of original evidence, not an F1 paraphrase')

def select_candidate(f1):
    cid = f1.get("recommended_candidate_id")
    if not cid: raise ValueError("F1 output has no recommended candidate")
    cand = next((c for c in f1.get("ranked_candidates", []) if c.get("candidate_id") == cid), None)
    if cand is None: raise ValueError(f"Recommended candidate {cid!r} not found in F1 output")
    return cand

def load_evidence_ids(path, company, config=None):
    """Evidence IDs R1 may be given or cite. Same gate as F1: schema-valid, verified identity (canonical name and identifier),
    parsed non-empty text, and human-approved or deterministically machine-cross-checked. Anything else, including malformed lines, is excluded.
    Fails closed: an unresolved company yields no IDs."""
    config = config or Config()
    p = Path(path)
    if not p.is_file(): return []
    canonical, identifier, status = verify_company(company, load_registry(config.registry_path))
    if status != "verified" or not canonical: return []
    schema = json.loads((config.schema_path.parent / "evidence_record.schema.json").read_text(encoding="utf-8"))
    ids = []
    for line in p.read_text(encoding="utf-8").splitlines():
        if not line.strip(): continue
        try: record = json.loads(line)
        except json.JSONDecodeError: continue
        if not isinstance(record, dict) or _validate(record, schema, root=schema): continue
        eid = record.get("evidence_id")
        if not isinstance(eid, str) or not re.fullmatch(r"ev_[a-f0-9]{24}", eid) or eid in ids or not eligible_ingested_evidence([record], canonical, identifier): continue
        ids.append(eid)
        if len(ids) > MAX_F1_EVIDENCE_RECORDS: raise ValueError(f"R1 evidence allowlist has more than {MAX_F1_EVIDENCE_RECORDS} approved records")
    return ids

def run(f1_path, output_path, config=None):
    config = config or Config()
    f1 = json.loads(Path(f1_path).read_text(encoding="utf-8"))
    if not f1.get("ranking_reliable"): raise ValueError("F1 ranking is not reliable; R1 will not plan from it")
    cand = select_candidate(f1)
    ids = load_evidence_ids(config.evidence_dir / "evidence.jsonl", f1["company_name"], config)
    records=supplied_sources(config,f1['company_name'],ids)
    prompt = (config.prompt_dir / "r1_research_investigator.md").read_text(encoding="utf-8")
    payload = {"company_name": f1["company_name"], "candidate": cand, "dataset_summary": f1.get("dataset_summary"), "supplied_evidence_ids": ids}
    payload['supplied_sources']=list(records.values())
    # F1 narrative remains a hypothesis. Its dates, URLs and paraphrases are not source metadata.
    payload['candidate']={**{k:v for k,v in cand.items() if k!='evidence_found'},
        'evidence_found':[{'evidence_id':source['evidence_id'],'source_type':'original_document',
            'source_url':source['source_url'],'date':source['publication_date'],'statement':source['excerpt_or_data_point']}
            for source in records.values()]}
    prompt+='\nThe supplied_sources array is the only source of ledger URLs, dates and excerpts. Never infer them from the F1 narrative. kind must be reported_fact, calculation, inference or unverified_hypothesis; planned_lookup is a STATUS, never a kind. For planned items use kind=unverified_hypothesis and all source fields null. Keep at most three questions/steps and four ledger items. Use the assigned hypothesis as a question to test, not an established finding.'
    def validate_r1(plan):
        validate_plan(plan, config.schema_path.with_name("r1_output.schema.json"), ids)
        if plan["candidate_id"] != cand["candidate_id"] or plan["company_name"] != f1["company_name"]:
            raise ValueError("R1 company and candidate must match supplied F1 recommendation")
        validate_ledger_sources(plan,records)
    generation_path=Path(output_path).with_name('r1_generation.schema.json')
    generation_path.parent.mkdir(parents=True,exist_ok=True)
    generation_path.write_text(json.dumps(ledger_generation_schema(json.loads(config.schema_path.with_name('r1_output.schema.json').read_text()),
        f1['company_name'],cand['candidate_id'],records),indent=2)+'\n')
    plan = generate_validated(prompt, payload, config,
        schema_path=generation_path, output_path=output_path,
        generate=generate_json, validate=validate_r1,
        preserve=lambda p: {key: p[key] for key in ("company_name", "candidate_id", "hypothesis") if key in p}
            if isinstance(p, dict) else {}, stage="r1")
    out = Path(output_path); out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(plan, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"R1 plan saved to {out} ({len(plan['checklist'])} steps; no retrieval performed)")
    return plan

def main(argv=None):
    config = Config()
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--f1", default=str(config.output_dir / "f1_output.json"))
    ap.add_argument("--output", default=str(config.output_dir / "r1_plan.json"))
    args = ap.parse_args(argv)
    try: run(args.f1, args.output, config); return 0
    except (FileNotFoundError, ValueError, LLMError, OSError) as e:
        print(f"R1 error: {e}", file=sys.stderr); return 2

if __name__ == "__main__":
    raise SystemExit(main())
