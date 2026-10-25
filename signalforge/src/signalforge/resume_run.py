"""Resume a stopped run from saved F1/R1 without repeating onboarding or discovery."""
import argparse
from dataclasses import replace
import json
import shutil
import uuid

from .config import ROOT
from .investigation import run_investigation, attach_planning_leads, write, write_report
from .research_session import ResearchSessions, local_config, now, record_investigation_outcome
from .r1_research_investigator import load_evidence_ids, select_candidate, validate_plan
from .llm_client import model_configured, LLMError


def preserve_report(folder):
    """Snapshot the valid prior report before a provider recovery can replace it."""
    archive=folder/'recovery_history'/uuid.uuid4().hex
    archive.mkdir(parents=True)
    for name in ('manifest.json','onboarding_report.json','investigation.json','investigation_report.md','investigation_initial.json','investigation_final.json','investigation_review.json'):
        path=folder/name
        if path.is_file(): shutil.copy2(path,archive/name)
    return str(archive.relative_to(folder))


def mark_reused_stages(manifest):
    modes={'discovery':('cached_completed_live_search','Reused saved discovery; no new search during recovery.'),
        'retrieval':('cached_original_rechecked','Reused saved source snapshots; originals rehashed.'),
        'machine_evidence':('cached_original_rechecked','Saved issuer identity and eligible evidence revalidated.'),
        'f1':('cached_deterministic_planning_fallback' if manifest.get('f1_ranking_provenance',{}).get('used') else 'cached_model_ranking','Saved F1 recommendation reused; no new F1 inference.'),
        'r1':('cached_validated_plan','Saved R1 plan revalidated against the schema and eligible evidence IDs.'),
        'counterevidence_search':('cached_completed_live_search','Completed opposition search and retrieval audit reused; no new queries during recovery.')}
    if manifest.get('source_intake') == 'cached_original_rechecked':
        modes['discovery']=('cached_original_rechecked','Operator-prepared source catalog reused and rehashed; no online search performed.')
        modes['counterevidence_search']=('cached_original_rechecked','Prepared source set reused for counterevidence review; no new online search performed.')
    for stage in manifest.get('stages',[]):
        if stage['name'] in modes:
            stage.update(zip(('execution','detail'),modes[stage['name']]))


def resume(run_id, config=None, *, retry_onboarding=False, retry_f1=False):
    sessions = ResearchSessions(config=config or local_config())
    manifest = sessions.get(run_id)  # validates ID before filesystem access
    if manifest['status'] in {'running', 'queued'}:
        raise ValueError('Run still marked active. Inspect its process before attempting recovery; no duplicate started.')
    folder = sessions.root / run_id
    cfg = replace(sessions.config, output_dir=folder, evidence_dir=folder/'eligible_evidence',
                  registry_path=folder/'run_registry.json' if (folder/'run_registry.json').is_file() else sessions.config.registry_path)
    if not model_configured(cfg):
        variable={'groq':'GROQ_API_KEY','xai':'XAI_API_KEY'}.get(cfg.provider.strip().lower(),'SIGNALFORGE_API_KEY')
        raise LLMError(f'Missing {variable}; configure the selected provider before resume.')
    if retry_f1:
        if (folder/'f1.json').exists() or not (folder/'eligible_evidence/evidence.jsonl').exists():
            raise ValueError('F1 recovery requires saved eligible evidence and no completed F1 output')
        from .evidence_ingestion import verify_company, load_registry
        canonical, _, verified = verify_company(manifest['company'],load_registry(cfg.registry_path))
        if verified != 'verified' or not load_evidence_ids(cfg.evidence_dir/'evidence.jsonl',canonical,cfg):
            raise ValueError('Saved original evidence failed revalidation')
        archive=preserve_report(folder)
        manifest.setdefault('recovery_history',[]).append({'at':now(),'provider':cfg.provider,'model':cfg.model,
            'prior_report_archive':archive,'method':'Resume before F1 using revalidated saved eligible evidence; no search or onboarding repeated'})
        manifest['investigation']=None
        manifest.pop('finished_at',None)
        manifest.pop('error',None)
        for stage in manifest['stages']:
            if stage['name'] in {'discovery','retrieval','machine_evidence'}:
                stage.update(execution='cached_original_rechecked',detail='Saved source intake and eligible originals revalidated; no new online search or download.')
        from .research_session import execute_models
        sessions.executor=lambda f,m,c,u:execute_models(f,m,cfg,u)
        sessions._work(folder,manifest)
        return sessions.get(run_id)
    if retry_onboarding:
        if (folder/'f1.json').exists() or (folder/'eligible_evidence').exists():
            raise ValueError('Onboarding recovery only applies before eligible evidence/F1; completed stages must not be repeated')
        archive=preserve_report(folder)
        manifest.setdefault('recovery_history',[]).append({'at':now(),'provider':cfg.provider,'model':cfg.model,
            'prior_report_archive':archive,'method':'Retry identity acquisition using saved discovery leads; no search repeated'})
        manifest['investigation']=None
        manifest.pop('finished_at',None)
        from .research_session import execute as execute_session
        sessions.executor=lambda f,m,c,u:execute_session(f,m,c,u,reuse_discovery=True)
        sessions._work(folder,manifest)
        return sessions.get(run_id)
    f1 = json.loads((folder/'f1.json').read_text())
    plan = json.loads((folder/'r1.json').read_text())
    if not f1.get('ranking_reliable') or plan['candidate_id'] != select_candidate(f1)['candidate_id'] or plan['company_name'] != f1['company_name']:
        raise ValueError('Saved F1/R1 company or recommendation does not match')
    ids = load_evidence_ids(cfg.evidence_dir/'evidence.jsonl', f1['company_name'], cfg)
    validate_plan(plan, cfg.schema_path.with_name('r1_output.schema.json'), ids)
    archive=preserve_report(folder)
    manifest.setdefault('recovery_history', []).append({'at':now(), 'from_status':manifest['status'],
        'from_stage':manifest['stage'], 'provider':cfg.provider, 'model':cfg.model, 'prior_report_archive':archive,
        'method':'Saved F1/R1 revalidated; completed search checkpoints reused without new retrieval; originals rehashed'})
    manifest.pop('finished_at', None)
    if manifest.get('investigation'):
        manifest['previous_report'] = {k:manifest['investigation'].get(k) for k in ('report_type','status','completed_at')}
    manifest['investigation'] = None
    manifest['model'] = {'provider':cfg.provider,'model':cfg.model}
    mark_reused_stages(manifest)
    def execute(folder, manifest, config, update):
        update('investigation', 'Resuming saved F1/R1 and completed source searches; exact evidence checks remain required.')
        result = run_investigation(folder, manifest['company'], manifest['prompt'], plan, cfg, update, reuse_searches=True)
        from .source_facts import attach_source_facts
        attach_source_facts(result, cfg)
        attach_planning_leads(result, plan)
        write(folder/'investigation.json', result)
        write_report(folder, result)
        record_investigation_outcome(manifest, result)
        usage=[]
        for path in sorted(folder.glob('investigation*_model_audit/*/attempt_*_provider.json')):
            entry=json.loads(path.read_text())
            usage.append({**{k:entry[k] for k in ('provider','model','api','browser_search','status','http_status',
                'error','error_code','elapsed_seconds','usage','limits','quota_scope','quota_numbers','request_bytes','sdk_retries') if k in entry},
                'artifact':str(path.relative_to(folder))})
        manifest['provider_call_usage']=usage
        artifacts = [str(p.relative_to(folder)) for p in folder.glob('investigation*') if p.is_file()]
        update('complete', f"Report finished: {result['status']} / {result['evidence_strength']}; inspect actual execution record.", 'completed',
            investigation=result, artifacts=list(dict.fromkeys(manifest.get('artifacts', [])+artifacts)))
    sessions.executor = execute
    sessions._work(folder, manifest)
    return sessions.get(run_id)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--run-id', required=True)
    parser.add_argument('--retry-onboarding',action='store_true',help='Retry identity acquisition from completed saved discovery, only before F1')
    parser.add_argument('--retry-f1',action='store_true',help='Resume before F1 from existing revalidated evidence; never repeats completed F1')
    args=parser.parse_args()
    if args.retry_f1 and args.retry_onboarding:parser.error('Choose one recovery stage')
    result=resume(args.run_id,retry_onboarding=args.retry_onboarding,retry_f1=args.retry_f1)
    print(json.dumps({'run_id':args.run_id,'status':result['status'],'report_type':result.get('investigation',{}).get('report_type','investigation')}))


if __name__ == '__main__':
    main()
