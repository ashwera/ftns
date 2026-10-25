"""Bounded live xAI preflight: models, JSON schema, then a real-passage draft."""
import argparse
from dataclasses import replace
from datetime import datetime, timezone
import json
from pathlib import Path

from .config import ROOT
from .f1_research_angle_selector import validate_output
from .investigation import DRAFT_SCHEMA, check_citation, collect_sources, evidence_map, write
from .llm_client import LLMError, generate_json, list_xai_models, redact
from .research_session import local_config


def run(run_dir, output_dir, config=None):
    cfg = config or local_config()
    if cfg.provider.strip().lower() != 'xai':
        raise ValueError('Select SIGNALFORGE_PROVIDER=xai for this live check')
    output_dir=Path(output_dir); output_dir.mkdir(parents=True, exist_ok=False)
    summary={'provider':'xai','execution':'real_api_preflight','started_at':datetime.now(timezone.utc).isoformat(), 'status':'running', 'requested_model':cfg.model, 'step':'authenticated_model_list'}
    try:
        models=list_xai_models(cfg)
        summary.update(available_models=models, requested_model=cfg.model, model_list_authenticated=True)
        selected=cfg.model if cfg.model in models else next((m for m in ('grok-4.7','grok-4.20','grok-4.1-fast-reasoning','grok-4') if m in models), None)
        if selected is None:
            raise LLMError('No verified suitable Grok model ID available to this key; no inference attempted.')
        cfg=replace(cfg,model=selected)
        summary['selected_model']=selected
        summary['step']='connectivity_json_schema'
        schema={'type':'object','properties':{'ok':{'type':'boolean'}},'required':['ok'],'additionalProperties':False}
        write(output_dir/'connectivity.schema.json',schema)
        small=generate_json('Return JSON with ok=true.', {},cfg,schema=schema,audit_path=output_dir/'connectivity_provider.json')
        validate_output(small,output_dir/'connectivity.schema.json')
        if small['ok'] is not True: raise ValueError('Connectivity response did not return ok=true')
        summary['connectivity_and_json_schema']='passed'
        summary['step']='representative_draft_and_exact_quote'
        folder=Path(run_dir)
        manifest=json.loads((folder/'manifest.json').read_text())
        scoped=replace(cfg,registry_path=folder/'run_registry.json' if (folder/'run_registry.json').exists() else cfg.registry_path,
                       evidence_dir=folder/'eligible_evidence')
        sources,_=collect_sources(folder,manifest['company'],manifest['prompt'],scoped)
        record=next(( (s,p) for s in sources for p in s['passages'] if p.get('origin_evidence_id')),None)
        if not record: raise ValueError('No revalidated original passage available for quotation smoke test')
        source,passage=record
        write(output_dir/'draft.schema.json',DRAFT_SCHEMA)
        draft=generate_json('Return a short inconclusive investigation draft with exactly one narrow claim reporting what the supplied passage says. '
            'Use one short exact contiguous quote and the supplied passage ID. No financial discrepancy is established. '
            'Leave calculations, timeline and follow_up_queries empty. Counterargument must cite the supplied passage and explain that an issuer statement is not independent confirmation. Return JSON.',
            {'company':manifest['company'],'source':source['title'],'passage':passage},cfg,
            schema=DRAFT_SCHEMA,audit_path=output_dir/'quotation_provider.json')
        validate_output(draft,output_dir/'draft.schema.json')
        evidence=evidence_map([source])
        for claim in draft['claims']:
            if not claim['citations']: raise ValueError('Quotation smoke requires an actual citation')
            for citation in claim['citations']: check_citation(citation,evidence)
        summary.update(status='passed',representative_draft_schema='passed',exact_passage_validation='passed',evidence_id=passage['id'])
        write(output_dir/'quotation_response.json',draft)
        return summary
    except (LLMError,ValueError) as error:
        summary.update(status='failed',error=redact(str(error),cfg))
        raise
    finally:
        summary['completed_at']=datetime.now(timezone.utc).isoformat()
        write(output_dir/'summary.json',summary)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--run-dir',type=Path,required=True)
    parser.add_argument('--output-dir',type=Path,required=True)
    args=parser.parse_args()
    try: print(json.dumps(run(args.run_dir,args.output_dir)))
    except (LLMError,ValueError) as error:
        print(str(error)); raise SystemExit(2)


if __name__ == '__main__': main()
