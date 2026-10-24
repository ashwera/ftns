from dataclasses import replace
import json
import sys
import tempfile
from pathlib import Path
from types import SimpleNamespace as NS
import unittest
from unittest.mock import patch

from signalforge.config import Config
from signalforge.llm_client import generate_json, trace_requests, GROQ_BASE_URL, LLMError, model_configured
from signalforge.structured_generation import generate_validated


class Failure(Exception):
    def __init__(self, status):
        self.status_code = status


class FailoverTests(unittest.TestCase):
    def sdk(self, replies):
        clients, requests = [], []
        class Fake:
            def __init__(self, **kw):
                clients.append(kw)
                def create(**request):
                    requests.append(request)
                    reply = replies.pop(0)
                    if isinstance(reply, Exception): raise reply
                    return NS(choices=[NS(message=NS(content=reply))], usage=NS(prompt_tokens=10,completion_tokens=4,total_tokens=14))
                self.chat = NS(completions=NS(create=create))
        return NS(OpenAI=Fake), clients, requests

    def cfg(self, **kw):
        return replace(Config(), provider='groq', model='openai/gpt-oss-20b', api_key='gemini-secret',
                       groq_api_key='groq-secret', base_url='', **kw)

    def test_groq_dedicated_key_url_and_json_compatible_parameters(self):
        sdk,clients,requests=self.sdk(['{"ok":true}'])
        with patch.dict(sys.modules, {'openai':sdk}):
            self.assertEqual(generate_json('p',{},self.cfg()),{'ok':True})
        self.assertEqual(clients[0]['api_key'],'groq-secret')
        self.assertEqual(clients[0]['base_url'],GROQ_BASE_URL)
        self.assertEqual(clients[0]['max_retries'],0)
        self.assertEqual(requests[0]['reasoning_effort'],'low')
        self.assertEqual(requests[0]['response_format'],{'type':'json_object'})

    def test_missing_groq_key_never_uses_gemini_key(self):
        cfg=replace(self.cfg(),groq_api_key='')
        self.assertFalse(model_configured(cfg))
        with self.assertRaisesRegex(LLMError,'GROQ_API_KEY'):
            generate_json('p',{},cfg)

    def test_quota_falls_through_once_and_records_actual_stage(self):
        sdk,clients,requests=self.sdk([Failure(429),'{"ok":true}'])
        cfg=replace(self.cfg(),provider='gemini',model='gemini-test',fallback_providers='groq,gemini,groq')
        trace=[]
        with patch.dict(sys.modules,{'openai':sdk}),trace_requests(trace,'r1'):
            self.assertEqual(generate_json('p',{},cfg),{'ok':True})
        self.assertEqual(len(clients),2)
        self.assertEqual(trace[0]['outcome'],'failed')
        self.assertEqual(trace[1]['stage'],'r1')
        self.assertEqual(trace[1]['provider'],'groq')
        self.assertIn('Model request failed',trace[1]['fallback_reason'])
        self.assertEqual(trace[1]['usage']['total_tokens'],14)

    def test_content_schema_and_oversized_errors_do_not_failover(self):
        for reply in ['not JSON',Failure(400)]:
            sdk,clients,_=self.sdk([reply,'{"ok":true}'])
            with patch.dict(sys.modules,{'openai':sdk}),self.assertRaises(LLMError):
                generate_json('p',{},self.cfg(fallback_providers='gemini'))
            self.assertEqual(len(clients),1)

    def test_groq_token_quota_uses_explicit_larger_gemini_route_once(self):
        sdk,clients,_=self.sdk([Failure(413),'{"ok":true}'])
        with patch.dict(sys.modules,{'openai':sdk}):
            self.assertEqual(generate_json('p',{},self.cfg(fallback_providers='gemini')),{'ok':True})
        self.assertEqual(len(clients),2)
        sdk,clients,_=self.sdk([Failure(413)])
        with patch.dict(sys.modules,{'openai':sdk}), self.assertRaises(LLMError):
            generate_json('p',{},self.cfg(fallback_providers='ollama'))
        self.assertEqual(len(clients),1)

    def test_bounded_exhaustion(self):
        sdk,clients,_=self.sdk([Failure(503),Failure(401)])
        with patch.dict(sys.modules,{'openai':sdk}),self.assertRaisesRegex(LLMError,'All configured'):
            generate_json('p',{},self.cfg(fallback_providers='gemini,groq,gemini'))
        self.assertEqual(len(clients),2)

    def test_provider_json_failure_uses_schema_repair_not_failover(self):
        error=Failure(400); error.body={'error':{'code':'json_validate_failed'}}
        sdk,clients,_=self.sdk([error])
        with patch.dict(sys.modules,{'openai':sdk}), self.assertRaisesRegex(LLMError,'Model returned invalid JSON'):
            generate_json('p',{},self.cfg(fallback_providers='gemini'))
        self.assertEqual(len(clients),1)

    def test_one_short_provider_directed_quota_wait_only(self):
        error=Failure(429);error.headers={'retry-after':'2'}
        sdk,clients,_=self.sdk([error,error,Failure(503)])
        with patch.dict(sys.modules,{'openai':sdk}),patch('signalforge.llm_client.time.sleep') as sleep,self.assertRaises(LLMError):
            generate_json('p',{},self.cfg(fallback_providers='gemini'))
        self.assertEqual(len(clients),3)
        sleep.assert_called_once_with(2.25)

    def test_schema_audit_preserves_provider_and_redacts_both_keys(self):
        sdk,_,_=self.sdk([Failure(503),'{"ok":true}'])
        cfg=replace(self.cfg(),provider='gemini',fallback_providers='groq')
        with tempfile.TemporaryDirectory() as temp:
            path=Path(temp); schema=path/'schema.json';schema.write_text('{"type":"object"}')
            with patch.dict(sys.modules,{'openai':sdk}):
                result=generate_validated('p',{'fixture':'groq-secret gemini-secret'},cfg,schema_path=schema,
                    output_path=path/'r1.json',generate=generate_json,validate=lambda x:None,stage='r1')
            self.assertEqual(result,{'ok':True})
            summary=json.loads(next(path.glob('r1_model_audit/*/summary.json')).read_text())
            self.assertEqual(summary['attempts'][0]['provider_calls'][-1]['provider'],'groq')
            all_text=''.join(p.read_text() for p in path.rglob('*.json'))
            self.assertNotIn('groq-secret',all_text)
            self.assertNotIn('gemini-secret',all_text)


if __name__=='__main__': unittest.main()
