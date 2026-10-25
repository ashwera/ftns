"""Explicit operator-catalog intake, distinct from online discovery."""
import hashlib
import json
import re
from pathlib import Path
from .config import ROOT
from .evidence_ingestion import verify_company, load_registry
from .source_catalog import load


def prepared_discovery(company, question, config, output_dir):
    canonical, _, status = verify_company(company, load_registry(config.registry_path))
    if status != "verified":
        return None
    sources, rejected = [], []
    for path in sorted((ROOT/'data/pipeline_inputs').glob('*catalog.json')):
        try:
            catalog = load(path)
            if catalog.get('research_intake') != 'operator_cached_originals' or catalog.get('company','').casefold() != canonical.casefold():
                continue
            for src in catalog['sources']:
                snapshot = (path.parent / (src.get('local_path') or '')).resolve()
                if not src.get('local_path') or not re.fullmatch('[a-f0-9]{64}', src.get('sha256') or ''):
                    continue
                try:
                    if snapshot.stat().st_size > 64*1024*1024 or hashlib.sha256(snapshot.read_bytes()).hexdigest() != src['sha256']:
                        raise ValueError('Snapshot size or pinned hash mismatch')
                    sources.append({'source_id':src['source_id'], 'catalog':str(path), 'path':str(snapshot),
                        'url':src.get('url'), 'sha256':src['sha256'], 'intake_mode':'cached_original_rechecked'})
                except (OSError, ValueError) as error:
                    rejected.append({'source_id':src['source_id'], 'reason':str(error)})
        except (ValueError, OSError, TypeError, KeyError):
            continue
    if not sources:
        return None
    report = {'company':company, 'topic':question, 'provider':'operator_source_catalog', 'execution_mode':'cached_original_intake',
        'search_queries':[], 'search_results':[], 'catalog_sources':sources, 'rejected_sources':rejected,
        'retrieval_status':'cached_original_rechecked', 'budget':{'max_queries':0, 'max_fetches':0},
        'action_log':[{'action':'cached_original_intake', 'outcome':'Operator-selected originals rehashed; no live search or download performed.'},
                      {'action':'discovery_stopped', 'reason':'operator_catalog_selected'}],
        'limitations':['Operator-prepared sources; not autonomous discovery. Eligibility and financial-claim checks remain separate. Additional proposed searches are unexecuted.']}
    output_dir=Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir/'discovery_report.json').write_text(json.dumps(report,indent=2)+'\n')
    return report
