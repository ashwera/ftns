"""Small Groq requests; browser leads and structured inference are separate."""
import copy
import hashlib
import json
from pathlib import Path
import re
import threading
import time

from .llm_client import LLMError, redact

BASE_URL = 'https://api.groq.com/openai/v1'
MAX_OUTPUT = 2048
MAX_REQUEST_BYTES = 18000
_lock = threading.Lock()
_next_call = 0.0


def client(config, timeout=60):
    from openai import OpenAI
    if not getattr(config,'groq_api_key','').strip():
        raise LLMError('Missing GROQ_API_KEY; configure the dedicated Groq key in an ignored local .env or shell. No provider fallback used.')
    base=config.base_url or BASE_URL
    if base.rstrip('/') != BASE_URL:
        raise LLMError('Groq free-provider endpoint must be https://api.groq.com/openai/v1; no credential sent to another endpoint.')
    return OpenAI(api_key=config.groq_api_key,base_url=base,timeout=timeout,max_retries=0)


def failure(error):
    status=getattr(error,'status_code',None)
    kind='authentication' if status in (401,403) else 'rate_limit' if status==429 else 'request_limit' if status==413 else 'timeout' if 'Timeout' in type(error).__name__ else 'provider'
    suffix=' Wait for the free-tier limit to reset; no retries or upgrade attempted.' if status==429 else ' No automatic retry or paid fallback.'
    return LLMError(f'Groq {kind} error'+(f' (HTTP {status})' if isinstance(status,int) else '')+suffix)


def failure_metadata(error):
    """Allowlist only numeric quota diagnostics; never copy provider error text."""
    headers=getattr(getattr(error,'response',None),'headers',{})
    limits={k:headers.get(k) for k in ('retry-after','x-ratelimit-limit-tokens','x-ratelimit-remaining-tokens','x-ratelimit-reset-tokens') if headers.get(k) is not None}
    body=getattr(error,'body',{})
    detail=body.get('error',body) if isinstance(body,dict) else {}
    message=detail.get('message','') if isinstance(detail,dict) else ''
    scope=next((s for s in ('tokens per day','tokens per minute','requests per day','requests per minute') if s in message.lower()),None)
    numbers={k.lower():m.group(1) for k in ('Limit','Used','Requested') if (m:=re.search(r'\b'+k+r'\s*:?\s*(\d+)',message,re.I))}
    code=detail.get('code') if isinstance(detail,dict) else None
    return {'limits':limits,'quota_scope':scope,'quota_numbers':numbers,
            'error_code':code if isinstance(code,str) and re.fullmatch(r'[a-z_]{1,60}',code) else None}


def models(config):
    try:return sorted(m.id for m in client(config).models.list().data)
    except LLMError:raise
    except Exception as error:raise failure(error) from None


def pause():
    with _lock:
        delay=max(0,_next_call-time.monotonic())
    if delay:time.sleep(min(60,delay))


def call(config, *, messages, schema=None, browser=False, audit_path=None, max_output=MAX_OUTPUT):
    global _next_call
    if browser and schema is not None:raise ValueError('Browser search and structured output must be separate requests')
    if config.model in {'groq/compound','groq/compound-mini'}:raise LLMError('Deprecated Compound model IDs are disabled')
    kwargs={'model':config.model,'messages':messages,'max_completion_tokens':max_output,'reasoning_effort':'low'}
    if browser:kwargs.update(tools=[{'type':'browser_search'}],tool_choice='required')
    else:
        kwargs['response_format']=({'type':'json_schema','json_schema':{'name':'signalforge','schema':schema,'strict':strict_schema(schema)}} if schema else {'type':'json_object'})
    if len(json.dumps(kwargs,ensure_ascii=False).encode())>MAX_REQUEST_BYTES:
        raise LLMError('Groq request exceeds the bounded free-tier payload limit; reduce source context, not evidence checks.')
    pause()
    started=time.monotonic()
    try:
        raw=client(config).chat.completions.with_raw_response.create(**kwargs)
        response=raw.parse()
    except LLMError:raise
    except Exception as error:
        metadata=failure_metadata(error)
        if audit_path:
            Path(audit_path).write_text(redact(json.dumps({'provider':'groq','model':config.model,'browser_search':browser,'status':'failed',
                'http_status':getattr(error,'status_code',None),'error':str(failure(error)),
                **metadata,'sdk_retries':0},indent=2),config)+'\n')
        if getattr(error,'status_code',None)==429:
            with _lock:_next_call=time.monotonic()+60
        if getattr(error,'status_code',None)==400 and metadata.get('error_code')=='json_validate_failed':
            with _lock:_next_call=time.monotonic()+60
            raise LLMError('Model returned invalid JSON from Groq structured generation; provider schema validation failed.') from None
        raise failure(error) from None
    usage=response.usage.model_dump(mode='json') if response.usage else None
    limits={k:raw.headers.get(k) for k in ('x-ratelimit-limit-tokens','x-ratelimit-remaining-tokens','x-ratelimit-reset-tokens','x-ratelimit-remaining-requests','retry-after') if raw.headers.get(k) is not None}
    # Pace successive agent stages conservatively; never retry a 429.
    with _lock:_next_call=time.monotonic()+60
    data=response.model_dump(mode='json')
    audit={'provider':'groq','model':config.model,'api':'chat.completions','browser_search':browser,
           'elapsed_seconds':round(time.monotonic()-started,3),'usage':usage,'limits':limits,
           'request_bytes':len(json.dumps(kwargs,ensure_ascii=False).encode()),'sdk_retries':0,
           'request':kwargs,'response':data}
    if audit_path:Path(audit_path).write_text(redact(json.dumps(audit,indent=2),config)+'\n')
    if response.choices[0].finish_reason!='stop':raise LLMError('Groq response incomplete; no claim accepted. Inspect token/usage audit.')
    return data


def strict_schema(schema):
    if not isinstance(schema,dict):return False
    if any(k in schema for k in ('if','then','else','allOf','not')):return False
    if schema.get('type')=='object' and (set(schema.get('required',[]))!=set(schema.get('properties',{})) or schema.get('additionalProperties') is not False):return False
    return all(strict_schema(v) for k,v in schema.items() if isinstance(v,dict) and k not in ('properties','$defs')) and all(strict_schema(v) for k in ('properties','$defs') for v in schema.get(k,{}).values())


def excerpt(text, limit=600):
    text=' '.join(str(text).split())
    match=re.search(r'commission|commercial operation|related party|renewable|capacity',text,re.I)
    start=max(0,(match.start()-100) if match else 0)
    start=text.rfind(' ',0,start)+1
    end=text.rfind(' ',start,min(len(text),start+limit))
    return text[start:end] if end>start else text[start:start+limit]


def bounded_payload(payload):
    value=copy.deepcopy(payload)
    if 'sources' in value or 'verified_ingested_evidence' in value:
        value['_context_scope']='Bounded excerpts only; full originals remain on disk. Omitted text is not evidence of absent financial activity or missing company disclosures. Do not infer completion, delay, loss or independence from absent context.'
    if 'sources' in value:
        sources=[]
        for source in value['sources'][:4]:
            slim={k:source[k] for k in ('id','title','lineage','source_class','publication_date') if k in source}
            passages=source.get('passages',[])
            passages=sorted(passages,key=lambda p:not bool(p.get('origin_evidence_id')))
            slim['passages']=[{**p,'text':excerpt(p['text'])} for p in passages[:3]]
            sources.append(slim)
        value['sources']=sources
    for key in ('verified_ingested_evidence',):
        if key in value:
            value[key]=[{k:(excerpt(r[k]) if k=='excerpt_or_fact' else r[k]) for k in ('evidence_id','company_name','document_title','source_locator','excerpt_or_fact') if k in r} for r in value[key][:4]]
    if 'r1_plan' in value:value['r1_plan']={k:value['r1_plan'][k] for k in ('hypothesis','alternative_explanation') if k in value['r1_plan']}
    if 'candidate' in value:
        candidate=value['candidate']
        value['candidate']={k:candidate[k] for k in ('candidate_id','category','hypothesis','alternative_explanation','falsification_condition','additional_evidence_needed') if k in candidate}
    return value


def structured_json(prompt,payload,config,*,schema=None,audit_path=None):
    data=call(config,messages=[{'role':'system','content':prompt},{'role':'user','content':json.dumps(bounded_payload(payload),ensure_ascii=False)}],schema=schema,audit_path=audit_path)
    text=data['choices'][0]['message'].get('content') or ''
    try:output=json.loads(text)
    except json.JSONDecodeError:raise LLMError('Model returned invalid JSON from Groq') from None
    if not isinstance(output,dict):raise LLMError('Model returned invalid JSON object from Groq')
    return output


class GroqBrowserSearch:
    name='groq_browser_search'
    execution_mode='real'

    def __init__(self,config,audit_dir=None):
        self.config=config;self.audit_dir=Path(audit_dir) if audit_dir else None

    def search(self,query,*,timeout=30):
        from .source_discovery import BingRSSSearch, _public_url, SearchError
        path=None
        if self.audit_dir:
            self.audit_dir.mkdir(parents=True,exist_ok=True)
            path=self.audit_dir/(hashlib.sha256(query.encode()).hexdigest()[:16]+'.json')
        try:
            data=call(self.config,messages=[{'role':'user','content':'Run one concise search for original public company documents: '+query+'. Stop after the first search results; do not open pages or search again. Return at most five source URLs, no financial conclusion.'}],browser=True,audit_path=path,max_output=1024)
        except LLMError as error:
            if 'rate_limit' in str(error):raise SearchError(str(error)) from None
            reply=BingRSSSearch().search(query,timeout=timeout)
            reply['provider_attempts']=[{'provider':self.name,'error':str(error),'status':'failed'},*reply.get('provider_attempts',[])]
            return reply
        hits=[];seen=set()
        def walk(value,tool_context=False):
            if isinstance(value,dict):
                for k,v in value.items():
                    context=tool_context or k in ('executed_tools','citations','sources','annotations','search_results')
                    if context and k in ('url','source_url','link') and isinstance(v,str) and _public_url(v) and v not in seen:
                        seen.add(v);hits.append({'url':v,'title':str(value.get('title','')),'url_provenance':'groq_browser_tool_or_citation','company_identity_status':'unresolved'})
                    walk(v,context)
            elif isinstance(value,list):
                for v in value:walk(v,tool_context)
        walk(data)
        if not hits:
            content=data['choices'][0]['message'].get('content') or ''
            for url in re.findall(r'https?://[^\s<>\]\)"\x27]+',content):
                url=url.rstrip('.,;')
                if _public_url(url) and url not in seen:
                    seen.add(url);hits.append({'url':url,'title':'','url_provenance':'model_suggested_url_unverified','company_identity_status':'unresolved'})
        return {'results':hits[:5],'executed_queries':[query],'provider_attempts':[{'provider':self.name,'status':'completed','returned_count':len(hits)}]}


def discovery_provider(config, audit_dir=None):
    if config.provider.strip().lower()=='groq':
        if not getattr(config,'groq_api_key','').strip():
            raise LLMError('Missing GROQ_API_KEY; configure the dedicated Groq key in an ignored local .env or shell. No provider fallback used.')
        return GroqBrowserSearch(config,audit_dir)
    from .source_discovery import BingRSSSearch
    return BingRSSSearch()
