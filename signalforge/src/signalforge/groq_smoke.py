"""Free-tier Groq schema and exact-passage preflight (no search in JSON calls)."""
import argparse
import json
from pathlib import Path

from .groq_provider import models, structured_json, excerpt
from .research_session import local_config
from .investigation import DRAFT_SCHEMA, CITATION, check_citation, evidence_map, write
from .evidence_ingestion import load_registry, verify_company
from .f1_research_angle_selector import eligible_ingested_evidence, validate_output
from .llm_client import LLMError
from .structured_generation import generate_validated
from .llm_client import generate_json


def run(folder, output, config=None):
    cfg=config or local_config()
    if cfg.provider!='groq':raise ValueError('Select SIGNALFORGE_PROVIDER=groq')
    output.mkdir(parents=True,exist_ok=False)
    summary={'provider':'groq','status':'running','model':cfg.model}
    try:
        available=models(cfg);summary['model_verified']=cfg.model in available
        if not summary['model_verified']:raise LLMError('Preferred model not accessible in authenticated Groq list; no replacement inferred.')
        manifest=json.loads((folder/'manifest.json').read_text())
        registry=folder/'run_registry.json'
        canonical,identifier,status=verify_company(manifest['company'],load_registry(registry))
        if status!='verified':raise ValueError('Saved company identity unresolved')
        records=[json.loads(l) for l in (folder/'eligible_evidence/evidence.jsonl').read_text().splitlines()]
        record=next(r for r in records if 'commission' in r['excerpt_or_fact'].lower() and eligible_ingested_evidence([r],canonical,identifier))
        pid='src_'+record['machine_verification']['source_sha256'][:16]+'_'+record['evidence_id']
        text=excerpt(record['excerpt_or_fact'])
        evidence=evidence_map([{'id':'original','passages':[{'id':pid,'text':record['excerpt_or_fact']}]}])
        write(output/'draft.schema.json',DRAFT_SCHEMA)
        def validate_draft(draft):
            validate_output(draft,output/'draft.schema.json')
            for claim in draft['claims']:
                for citation in claim['citations']:check_citation(citation,evidence)
        draft=generate_validated('Return JSON for an inconclusive investigation with exactly one narrow issuer-disclosure claim, citing only the supplied passage. '
            'Every citation quote must be ONE short contiguous substring copied character for character from text. Never insert ellipses, stitch sentences, omit footnote digits or change punctuation. '
            'Empty timeline, calculations, follow_up_queries. Counterargument must cite this same passage and explain that issuer targets do not establish actual completion or independent corroboration.',
            {'company':canonical,'passage_id':pid,'text':text},cfg,schema_path=output/'draft.schema.json',output_path=output/'structured_response.json',
            generate=generate_json,validate=validate_draft,stage='preflight')
        write(output/'structured_response.json',draft);summary['structured_output']='passed'
        quote=structured_json('Copy one exact contiguous quote from the supplied text into JSON. Use the supplied evidence_id. Do not paraphrase.',
            {'evidence_id':pid,'text':text},cfg,schema=CITATION,audit_path=output/'quotation_provider.json')
        write(output/'citation.schema.json',CITATION);validate_output(quote,output/'citation.schema.json');check_citation(quote,evidence)
        write(output/'quotation_response.json',quote)
        summary.update(status='passed',quotation_validation='passed',evidence_id=pid)
        return summary
    except (LLMError,ValueError,StopIteration) as error:
        summary.update(status='failed',error=str(error));raise
    finally:write(output/'summary.json',summary)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--run-dir',type=Path,required=True);parser.add_argument('--output-dir',type=Path,required=True)
    args=parser.parse_args()
    try:print(json.dumps(run(args.run_dir,args.output_dir)))
    except (LLMError,ValueError,StopIteration) as e:print(str(e));raise SystemExit(2)

if __name__=='__main__':main()
