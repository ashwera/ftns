from dataclasses import replace
import json
from pathlib import Path
import sys
import tempfile
import traceback
import types
import unittest
from unittest.mock import patch

from signalforge.config import Config
from signalforge import groq_provider as G
from signalforge.llm_client import generate_json, model_configured, LLMError
from signalforge.research_session import local_config
from signalforge.structured_generation import generate_validated
from signalforge.investigation import CITATION, check_citation, evidence_map


class GroqProviderTests(unittest.TestCase):
    def cfg(self):
        return replace(Config(),provider='groq',model='openai/gpt-oss-120b',base_url='',
                       api_key='other-secret',xai_api_key='xai-secret',groq_api_key='groq-secret')

    def sdk(self,content='{"ok":true}',error=None,finish='stop'):
        calls={}
        class OpenAI:
            def __init__(self,**kwargs):
                calls['client']=kwargs
                self.models=types.SimpleNamespace(list=self.list)
                self.chat=types.SimpleNamespace(completions=types.SimpleNamespace(with_raw_response=types.SimpleNamespace(create=self.create)))
            def list(self):return types.SimpleNamespace(data=[types.SimpleNamespace(id='openai/gpt-oss-120b')])
            def create(self,**kwargs):
                calls.setdefault('requests',[]).append(kwargs)
                if error:raise error
                data={'choices':[{'message':{'content':content},'finish_reason':finish}]}
                response=types.SimpleNamespace(choices=[types.SimpleNamespace(finish_reason=finish)],
                    usage=types.SimpleNamespace(model_dump=lambda **kw:{'total_tokens':30}),model_dump=lambda **kw:data)
                return types.SimpleNamespace(headers={'x-ratelimit-limit-tokens':'8000'},parse=lambda:response)
        return types.SimpleNamespace(OpenAI=OpenAI),calls

    def setUp(self):
        self.pacing=patch.object(G,'pause');self.pacing.start();self.addCleanup(self.pacing.stop)

    def test_dedicated_key_default_endpoint_schema_and_safe_usage_audit(self):
        sdk,calls=self.sdk();cfg=self.cfg()
        schema={'type':'object','properties':{'ok':{'type':'boolean'}},'required':['ok'],'additionalProperties':False}
        with tempfile.TemporaryDirectory() as tmp,patch.dict(sys.modules,{'openai':sdk}):
            path=Path(tmp)/'audit.json'
            self.assertEqual(generate_json('Return JSON',{},cfg,schema=schema,audit_path=path),{'ok':True})
            audit=json.loads(path.read_text());self.assertEqual(audit['usage']['total_tokens'],30)
            self.assertNotIn('groq-secret',path.read_text())
            self.assertEqual(G.models(cfg),['openai/gpt-oss-120b'])
        self.assertEqual(calls['client'],dict(api_key='groq-secret',base_url=G.BASE_URL,timeout=60,max_retries=0))
        req=calls['requests'][0]
        self.assertEqual(req['response_format']['json_schema']['schema'],schema)
        self.assertTrue(req['response_format']['json_schema']['strict'])
        self.assertNotIn('tools',req);self.assertNotIn('extra_body',req);self.assertNotIn('num_ctx',req)

    def test_key_missing_endpoint_mismatch_and_deprecated_ids_fail_before_request(self):
        cfg=replace(self.cfg(),groq_api_key='')
        self.assertFalse(model_configured(cfg))
        with self.assertRaisesRegex(LLMError,'Missing GROQ_API_KEY'):generate_json('p',{},cfg)
        with self.assertRaisesRegex(LLMError,'Missing GROQ_API_KEY'):G.discovery_provider(cfg)
        with self.assertRaisesRegex(LLMError,'endpoint'):generate_json('p',{},replace(self.cfg(),base_url='https://other.example/v1'))
        for model in ('groq/compound','groq/compound-mini'):
            with self.assertRaisesRegex(LLMError,'Deprecated'):G.call(replace(self.cfg(),model=model),messages=[])

    def test_search_and_structured_output_are_separate_and_urls_remain_leads(self):
        sdk,calls=self.sdk('https://issuer.example/annual-report.pdf')
        with patch.dict(sys.modules,{'openai':sdk}):
            reply=G.GroqBrowserSearch(self.cfg()).search('Company annual report')
        req=calls['requests'][0]
        self.assertEqual(req['tools'],[{'type':'browser_search'}]);self.assertNotIn('response_format',req)
        hit=reply['results'][0]
        self.assertEqual(hit['company_identity_status'],'unresolved')
        self.assertEqual(hit['url_provenance'],'model_suggested_url_unverified')
        with self.assertRaises(ValueError):G.call(self.cfg(),messages=[],schema=CITATION,browser=True)

    def test_auth_rate_limit_timeout_no_retry_and_no_secret_traceback(self):
        for status,category in ((401,'authentication'),(429,'rate_limit'),(413,'request_limit'),(500,'provider')):
            err=type('APIStatusError',(Exception,),{'status_code':status})('Bearer groq-secret other-secret')
            sdk,calls=self.sdk(error=err)
            with patch.dict(sys.modules,{'openai':sdk}),self.assertRaisesRegex(LLMError,category) as caught:
                generate_json('p',{},self.cfg())
            self.assertEqual(len(calls['requests']),1)
            self.assertNotIn('groq-secret',''.join(traceback.format_exception(caught.exception)))
        sdk,calls=self.sdk(error=type('APITimeoutError',(Exception,),{})('groq-secret'))
        with patch.dict(sys.modules,{'openai':sdk}),self.assertRaisesRegex(LLMError,'timeout'):generate_json('p',{},self.cfg())
        self.assertEqual(len(calls['requests']),1)

    def test_rate_limit_search_does_not_retry_provider_or_fallback(self):
        from signalforge.source_discovery import SearchError
        with patch.object(G,'call',side_effect=LLMError('Groq rate_limit error (HTTP 429)')),patch('signalforge.source_discovery.BingRSSSearch.search') as fallback:
            with self.assertRaises(SearchError):G.GroqBrowserSearch(self.cfg()).search('query')
            fallback.assert_not_called()

    def test_browser_failure_has_transparent_public_search_fallback(self):
        with patch.object(G,'call',side_effect=LLMError('Groq provider error (HTTP 500)')),patch('signalforge.source_discovery.BingRSSSearch.search',return_value={'results':[]}) as fallback:
            reply=G.GroqBrowserSearch(self.cfg()).search('query')
        self.assertEqual(fallback.call_count,1)
        self.assertEqual(reply['provider_attempts'][0]['status'],'failed')

    def test_bounds_preserve_originals_and_keep_exact_contiguous_context(self):
        text='Intro. '+('word '*100)+' commissioned 100 MW on 1 April. '+('word '*200)
        original={'sources':[{'id':'s','passages':[{'id':'p','text':text,'origin_evidence_id':'e'}]}]}
        slim=G.bounded_payload(original)
        self.assertEqual(original['sources'][0]['passages'][0]['text'],text)
        quote=slim['sources'][0]['passages'][0]['text']
        self.assertIn(quote,' '.join(text.split()));self.assertIn('commissioned',quote)
        with self.assertRaisesRegex(LLMError,'bounded free-tier'):generate_json('p',{'text':'x'*20000},self.cfg())

    def test_csv_readiness_is_compact_context_without_removing_pdf_evidence(self):
        original={'research_readiness_matrix':[{'category':'capacity_conversion','readiness_rating':'not_ready',
            'readiness_rationale':'No matching CSV rows','evidence_missing':['x'*4000]}],
            'verified_ingested_evidence':[{'evidence_id':'ev_real','excerpt_or_fact':'Actual issuer solar capacity commissioned 100 MW.'}]}
        slim=G.bounded_payload(original)
        self.assertEqual(slim['verified_ingested_evidence'][0]['evidence_id'],'ev_real')
        self.assertEqual(slim['research_readiness_matrix'][0]['readiness_rating'],'not_ready')
        self.assertNotIn('evidence_missing',slim['research_readiness_matrix'][0])
        self.assertIn('evidence_missing',original['research_readiness_matrix'][0])

    def test_repairs_receive_feedback_and_fabricated_quotes_remain_rejected(self):
        evidence=evidence_map([{'id':'s','passages':[{'id':'p','text':'The project has a target capacity of 170 MW.'}]}])
        requests=[]
        def generate(prompt,payload,cfg,**kwargs):
            requests.append(prompt)
            return {'evidence_id':'p','quote':'The project has a target capacity of 999 MW.'}
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);schema=root/'schema.json';schema.write_text(json.dumps(CITATION))
            with self.assertRaisesRegex(ValueError,'exact contiguous span'):
                generate_validated('Return JSON',{},self.cfg(),schema_path=schema,output_path=root/'quote.json',
                    generate=generate,validate=lambda v:check_citation(v,evidence))
            self.assertEqual(len(requests),2)
            self.assertIn('previous response failed validation',requests[1]);self.assertNotIn('Required RESEARCH',requests[0])
            self.assertFalse((root/'quote.json').exists())

    def test_dotenv_defaults_to_groq_without_overwriting_other_credentials(self):
        with tempfile.TemporaryDirectory() as tmp,patch.dict('os.environ',{},clear=True):
            path=Path(tmp)/'.env';path.write_text('GROQ_API_KEY=groq-fixture\nXAI_API_KEY=xai-fixture\nSIGNALFORGE_API_KEY=gemini-fixture\n')
            cfg=local_config(paths=[path])
            self.assertEqual((cfg.provider,cfg.model,cfg.groq_api_key),('groq','openai/gpt-oss-120b','groq-fixture'))
            self.assertEqual((cfg.xai_api_key,cfg.api_key),('xai-fixture','gemini-fixture'))
            self.assertNotIn('GROQ_API_KEY',__import__('os').environ)
            self.assertTrue(model_configured(replace(cfg,provider='ollama')))

    def test_invalid_json_and_incomplete_generation_fail_closed(self):
        for content,finish in [('bad','stop'),('[]','stop'),('{}','length')]:
            sdk,_=self.sdk(content,finish=finish)
            with patch.dict(sys.modules,{'openai':sdk}),self.assertRaises(LLMError):generate_json('p',{},self.cfg())

    def test_quota_diagnostics_allowlist_numbers_and_scope_only(self):
        err=types.SimpleNamespace(body={'error':{'message':'secret-org: tokens per minute (TPM): Limit 8000, Used 200, Requested 8100. Bearer groq-secret'}},response=types.SimpleNamespace(headers={'retry-after':'60','Authorization':'groq-secret'}))
        result=G.failure_metadata(err)
        self.assertEqual(result['quota_scope'],'tokens per minute')
        self.assertEqual(result['quota_numbers'],{'limit':'8000','used':'200','requested':'8100'})
        self.assertNotIn('secret',json.dumps(result))

    def test_provider_json_validation_error_uses_only_one_application_repair(self):
        error=type('APIStatusError',(Exception,),{'status_code':400,'body':{'error':{'code':'json_validate_failed','message':'groq-secret'}}})('private')
        sdk,calls=self.sdk(error=error)
        with tempfile.TemporaryDirectory() as tmp,patch.dict(sys.modules,{'openai':sdk}):
            root=Path(tmp);schema=root/'schema.json';schema.write_text(json.dumps(CITATION))
            with self.assertRaisesRegex(ValueError,'invalid JSON'):
                generate_validated('Return JSON',{},self.cfg(),schema_path=schema,output_path=root/'result.json',
                    generate=generate_json,validate=lambda value:None)
            self.assertEqual(len(calls['requests']),2)
            for path in root.rglob('*.json'):self.assertNotIn('groq-secret',path.read_text())
