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
from signalforge.llm_client import generate_json, list_xai_models, model_configured, LLMError, XAI_BASE_URL
from signalforge.research_session import local_config
from signalforge.structured_generation import generate_validated
from signalforge.investigation import CITATION, check_citation, evidence_map


class XaiProviderTests(unittest.TestCase):
    def cfg(self, **kwargs):
        return replace(Config(),provider='xai',model='grok-4.7',base_url='',api_key='other-provider-secret',xai_api_key='xai-fixture-secret',**kwargs)

    def fake_sdk(self, content='{"ok":true}', status='completed', error=None):
        calls={}
        class FakeOpenAI:
            def __init__(self,**kwargs):
                calls['client']=kwargs
                self.responses=types.SimpleNamespace(create=self.create)
                self.models=types.SimpleNamespace(list=self.models_list)
            def create(self,**kwargs):
                calls.setdefault('requests',[]).append(kwargs)
                if error: raise error
                return types.SimpleNamespace(output_text=content,status=status,model='grok-4.7',_request_id='request-fixture',
                    usage=types.SimpleNamespace(model_dump=lambda **kw:{'input_tokens':20,'output_tokens':10,'total_tokens':30}))
            def models_list(self):
                calls['model_list_calls']=calls.get('model_list_calls',0)+1
                if error: raise error
                return types.SimpleNamespace(data=[types.SimpleNamespace(id='grok-4.7')])
        return types.SimpleNamespace(OpenAI=FakeOpenAI),calls

    def test_responses_schema_key_endpoint_usage_and_no_ollama_parameters(self):
        sdk,calls=self.fake_sdk()
        schema={'type':'object','properties':{'ok':{'type':'boolean'}},'required':['ok'],'additionalProperties':False}
        with tempfile.TemporaryDirectory() as tmp, patch.dict(sys.modules,{'openai':sdk}):
            audit=Path(tmp)/'provider.json'
            self.assertEqual(generate_json('Return JSON',{},self.cfg(),schema=schema,audit_path=audit),{'ok':True})
            usage=json.loads(audit.read_text())
            self.assertEqual(usage['usage']['total_tokens'],30)
            self.assertNotIn('xai-fixture-secret',audit.read_text())
        self.assertEqual(calls['client'],dict(api_key='xai-fixture-secret',base_url=XAI_BASE_URL,timeout=60,max_retries=0))
        request=calls['requests'][0]
        self.assertEqual(request['text']['format'],dict(type='json_schema',name='signalforge_output',schema=schema,strict=True))
        self.assertFalse(request['store'])
        self.assertEqual(request['model'],'grok-4.7')
        self.assertTrue(request['max_output_tokens']>0)
        for key in ('reasoning_effort','num_ctx','response_format','max_tokens'): self.assertNotIn(key,request)

    def test_dedicated_key_required_and_no_cross_provider_fallback(self):
        cfg=replace(self.cfg(),xai_api_key='')
        self.assertFalse(model_configured(cfg))
        with patch.dict(sys.modules,{'openai':None}), self.assertRaisesRegex(LLMError,'Missing XAI_API_KEY'):
            generate_json('p',{},cfg)
        with self.assertRaisesRegex(LLMError,'Invalid xAI base URL'):
            generate_json('p',{},replace(self.cfg(),base_url='http://127.0.0.1:11434/v1'))

    def test_model_list_and_explicit_https_endpoint(self):
        sdk,calls=self.fake_sdk()
        with patch.dict(sys.modules,{'openai':sdk}):
            self.assertEqual(list_xai_models(replace(self.cfg(),base_url='https://xai.example/v1')),['grok-4.7'])
        self.assertEqual(calls['client']['base_url'],'https://xai.example/v1')
        self.assertEqual(calls['model_list_calls'],1)

    def test_authentication_rate_limit_and_timeout_are_safe_and_not_retried(self):
        for status,category in ((401,'authentication'),(403,'authentication'),(429,'rate_limit'),(503,'provider')):
            error=type('APIStatusError',(Exception,),{'status_code':status})('Authorization: Bearer xai-fixture-secret other-provider-secret')
            sdk,calls=self.fake_sdk(error=error)
            with patch.dict(sys.modules,{'openai':sdk}), self.assertRaisesRegex(LLMError,category) as caught:
                generate_json('p',{},self.cfg())
            self.assertEqual(len(calls['requests']),1)
            trace=''.join(traceback.format_exception(caught.exception))
            self.assertNotIn('xai-fixture-secret',trace)
            self.assertNotIn('other-provider-secret',trace)
        sdk,calls=self.fake_sdk(error=type('APITimeoutError',(Exception,),{})('secret body'))
        with patch.dict(sys.modules,{'openai':sdk}), self.assertRaisesRegex(LLMError,'timeout'):
            generate_json('p',{},self.cfg())
        self.assertEqual(len(calls['requests']),1)
        error=type('APIStatusError',(Exception,),{'status_code':400,'body':'Malformed API key provided'})('private body')
        sdk,_=self.fake_sdk(error=error)
        with patch.dict(sys.modules,{'openai':sdk}), self.assertRaisesRegex(LLMError,'authentication.*HTTP 400'):
            generate_json('p',{},self.cfg())

    def test_exact_quote_gate_still_rejects_invented_cloud_quotations_after_two_attempts(self):
        evidence=evidence_map([{'id':'s','passages':[{'id':'s1','text':'The project has a target capacity of 170 MW.'}]}])
        for quote,valid in [('The project has a target capacity of 170 MW.',True),('The project has a target capacity of 999 MW.',False)]:
            response={'evidence_id':'s1','quote':quote}
            sdk,calls=self.fake_sdk(json.dumps(response))
            with tempfile.TemporaryDirectory() as tmp, patch.dict(sys.modules,{'openai':sdk}):
                root=Path(tmp);path=root/'schema.json';path.write_text(json.dumps(CITATION))
                def validate(value): check_citation(value,evidence)
                if valid:
                    result=generate_validated('Return JSON',{},self.cfg(),schema_path=path,output_path=root/'quote.json',generate=generate_json,validate=validate)
                    self.assertEqual(result,response)
                else:
                    with self.assertRaisesRegex(ValueError,'exact contiguous span'):
                        generate_validated('Return JSON',{},self.cfg(),schema_path=path,output_path=root/'quote.json',generate=generate_json,validate=validate)
                    self.assertEqual(len(calls['requests']),2)
                    self.assertFalse((root/'quote.json').exists())

    def test_invalid_empty_incomplete_and_non_object_outputs_fail_closed(self):
        for content,status,expected in [('not-json','completed','invalid JSON'),('','completed','empty response'),('{}','incomplete','incomplete response'),('[]','completed','invalid JSON object')]:
            sdk,_=self.fake_sdk(content,status)
            with patch.dict(sys.modules,{'openai':sdk}), self.assertRaisesRegex(LLMError,expected):
                generate_json('p',{},self.cfg())

    def test_config_defaults_and_dotenv_load_dedicated_key_without_overwriting_other_keys(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)/'project';root.mkdir()
            (root/'.env').write_text('XAI_API_KEY=fixture-xai\nSIGNALFORGE_API_KEY=fixture-gemini\n')
            with patch('signalforge.research_session.ROOT',root), patch.dict('os.environ',{},clear=True):
                cfg=local_config(paths=[root/'.env'])
                self.assertEqual((cfg.provider,cfg.model,cfg.xai_api_key,cfg.api_key),('xai','grok-4.7','fixture-xai','fixture-gemini'))
                self.assertNotIn('XAI_API_KEY',__import__('os').environ)
                self.assertNotIn('SIGNALFORGE_PROVIDER',__import__('os').environ)
            with patch.dict('os.environ',{'XAI_API_KEY':'xai','SIGNALFORGE_PROVIDER':'ollama'},clear=True):
                cfg=Config();self.assertEqual((cfg.provider,cfg.model),('ollama','signalforge-qwen'))

    def test_structured_stage_passes_schema_and_redacts_both_secrets(self):
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp);schema={'type':'object','properties':{'answer':{'type':'integer'}},'required':['answer'],'additionalProperties':False}
            path=p/'schema.json';path.write_text(json.dumps(schema))
            calls=[]
            def generate(prompt,payload,config,**kwargs):
                calls.append((prompt,kwargs))
                return {'wrong':'xai-fixture-secret other-provider-secret'} if len(calls)==1 else {'answer':1}
            def validate(value):
                if 'answer' not in value: raise ValueError('xai-fixture-secret other-provider-secret missing answer')
            result=generate_validated('p',{},self.cfg(),schema_path=path,output_path=p/'result.json',generate=generate,validate=validate)
            self.assertEqual(result,{'answer':1})
            self.assertEqual(calls[0][1]['schema'],schema)
            for f in p.rglob('*.json'):
                self.assertNotIn('xai-fixture-secret',f.read_text()); self.assertNotIn('other-provider-secret',f.read_text())
            self.assertNotIn('xai-fixture-secret',calls[1][0])
