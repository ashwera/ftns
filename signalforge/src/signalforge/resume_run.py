"""Resume a stopped run from saved F1/R1 without repeating onboarding or discovery."""
import argparse
from dataclasses import replace
import json

from .config import ROOT
from .investigation import run_investigation, attach_planning_leads, write, write_report
from .research_session import ResearchSessions, local_config, now, record_investigation_outcome
from .r1_research_investigator import load_evidence_ids, select_candidate, validate_plan


def resume(run_id, config=None):
    sessions = ResearchSessions(config=config or local_config())
    manifest = sessions.get(run_id)  # validates ID before filesystem access
    if manifest['status'] in {'running', 'queued'}:
        raise ValueError('Run still marked active. Inspect its process before attempting recovery; no duplicate started.')
    folder = sessions.root / run_id
    cfg = replace(sessions.config, output_dir=folder, evidence_dir=folder/'eligible_evidence',
                  registry_path=folder/'run_registry.json' if (folder/'run_registry.json').is_file() else sessions.config.registry_path)
    f1 = json.loads((folder/'f1.json').read_text())
    plan = json.loads((folder/'r1.json').read_text())
    if not f1.get('ranking_reliable') or plan['candidate_id'] != select_candidate(f1)['candidate_id'] or plan['company_name'] != f1['company_name']:
        raise ValueError('Saved F1/R1 company or recommendation does not match')
    ids = load_evidence_ids(cfg.evidence_dir/'evidence.jsonl', f1['company_name'], cfg)
    validate_plan(plan, cfg.schema_path.with_name('r1_output.schema.json'), ids)
    manifest.setdefault('recovery_history', []).append({'at':now(), 'from_status':manifest['status'],
        'from_stage':manifest['stage'], 'model':cfg.model, 'method':'Saved F1/R1 revalidated; completed search checkpoints reused; originals rehashed'})
    manifest.pop('finished_at', None)
    if manifest.get('investigation'):
        manifest['previous_report'] = {k:manifest['investigation'].get(k) for k in ('report_type','status','completed_at')}
    manifest['investigation'] = None
    manifest['model'] = {'provider':cfg.provider,'model':cfg.model}
    def execute(folder, manifest, config, update):
        update('investigation', 'Resuming saved F1/R1 and completed source searches; exact evidence checks remain required.')
        result = run_investigation(folder, manifest['company'], manifest['prompt'], plan, cfg, update)
        attach_planning_leads(result, plan)
        write(folder/'investigation.json', result)
        write_report(folder, result)
        record_investigation_outcome(manifest, result)
        artifacts = [str(p.relative_to(folder)) for p in folder.glob('investigation*') if p.is_file()]
        update('complete', f"Report finished: {result['status']} / {result['evidence_strength']}; inspect actual execution record.", 'completed',
            investigation=result, artifacts=list(dict.fromkeys(manifest.get('artifacts', [])+artifacts)))
    sessions.executor = execute
    sessions._work(folder, manifest)
    return sessions.get(run_id)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--run-id', required=True)
    args=parser.parse_args()
    result=resume(args.run_id)
    print(json.dumps({'run_id':args.run_id,'status':result['status'],'report_type':result.get('investigation',{}).get('report_type','investigation')}))


if __name__ == '__main__':
    main()
