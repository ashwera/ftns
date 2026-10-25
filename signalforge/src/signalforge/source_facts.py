"""Catalog-selected reported figures, rechecked against originals at run time."""
import hashlib
import re
from .config import ROOT
from .source_catalog import load


def attach_source_facts(result, config):
    from .investigation import parsed, norm, evidence_map, calculate
    sources={s['sha256']:s for s in result.get('sources',[])}
    facts=[];checks=[];audit=[]
    for catalog_path in sorted((ROOT/'data/pipeline_inputs').glob('*catalog.json')):
        try:
            catalog=load(catalog_path)
            if catalog.get('company','').casefold()!=result.get('company','').casefold():continue
            entries={s['source_id']:s for s in catalog['sources']}
            accepted={}
            for spec in catalog.get('reported_facts',[]):
                try:
                    entry=entries[spec['source_id']];source=sources[entry['sha256']]
                    path=(catalog_path.parent/entry['local_path']).resolve()
                    if path.stat().st_size>64*1024*1024 or hashlib.sha256(path.read_bytes()).hexdigest()!=entry['sha256']:
                        raise ValueError('Original source hash mismatch')
                    pages=parsed(str(path),entry['sha256'])
                    page=next(p['text'] for p in pages if p['page']==spec['page'])
                    quote=spec['quote']
                    if norm(quote) not in norm(page):raise ValueError('Source quote mismatch')
                    if not re.search(r'(?<![\d.])'+re.escape(spec['value'])+r'(?![\d.])',quote.replace(',','')):raise ValueError('Value absent from quote')
                    if spec.get('period') and norm(spec['period']) not in norm(page):raise ValueError('Period absent from source page')
                    pid=source['id']+'_fact_'+spec['id']
                    # The complete source quote remains linked to the same rehashed original.
                    if not any(p['id']==pid for p in source['passages']):
                        source['passages'].append({'id':pid,'page':spec['page'],'text':norm(quote)})
                    fact={k:spec[k] for k in ('id','label','value','unit','period','milestone') if k in spec}
                    fact.update(evidence_id=pid,quote=norm(quote),source_id=source['id'],sha256=entry['sha256'],
                        provenance='operator_selected_reported_figure_exact_passage_checked',independently_corroborated=False)
                    facts.append(fact);accepted[spec['id']]=fact
                except (KeyError,ValueError,OSError,StopIteration) as error:
                    audit.append({'fact':spec.get('id'),'status':'rejected','reason':type(error).__name__})
            for spec in catalog.get('source_crosschecks',[]):
                try:
                    operands=[accepted[key] for key in spec['fact_ids']]
                    # Only arithmetic components from an explicitly identical source/page/period/unit.
                    if len({(f['source_id'],f.get('period'),f['unit']) for f in operands})!=1:raise ValueError('Incomparable source-fact basis')
                    value=calculate({'label':spec['label'],'operation':spec['operation'],'unit':operands[0]['unit'],
                        'basis':'Reported components from the same original source and period; arithmetic only.',
                        'inputs':[{'value':f['value'],'evidence_id':f['evidence_id'],'quote':f['quote']} for f in operands]},evidence_map(list(sources.values())))
                    value['verification_scope']='deterministic_arithmetic_only'
                    checks.append(value)
                except (KeyError,ValueError) as error:
                    audit.append({'crosscheck':spec.get('label'),'status':'rejected','reason':type(error).__name__})
        except (ValueError,OSError,KeyError,TypeError):continue
    result['reported_facts']=facts
    result['source_crosschecks']=checks
    if audit:result['source_fact_rejections']=audit
    return result
