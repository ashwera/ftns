import os
import tempfile
import unittest
from dataclasses import replace
from pathlib import Path
from unittest.mock import patch
from signalforge.config import Config
from signalforge.llm_client import LLMError
from signalforge.model_runtime import model_runtime, invoke, effective_config


class RuntimeTests(unittest.TestCase):
    def test_quote_grammar_contains_only_source_spans_and_keeps_schema_immutable(self):
        from signalforge.llm_client import local_quote_schema
        schema={'type':'object','properties':{'quote':{'type':'string'}}}
        payload={'sources':[{'passages':[{'id':'p1','text':'As of 31 March 2025 installed solar capacity was 209.08 MW. Other text.'}]}]}
        constrained,options=local_quote_schema(schema,payload)
        self.assertEqual(options[0]['evidence_id'],'p1')
        for option in options:self.assertIn(option['quote'],payload['sources'][0]['passages'][0]['text'])
        self.assertEqual(constrained['properties']['quote']['enum'],[o['quote'] for o in options])
        self.assertNotIn('enum',schema['properties']['quote'])

    def test_rate_limit_switches_remaining_calls_and_preserves_stage_paths(self):
        cfg=replace(Config(),provider='groq',model='openai/gpt-oss-20b',base_url='https://api.groq.com/openai/v1')
        calls=[];events=[]
        def call(selected):
            calls.append(selected)
            if selected.provider=='groq':raise LLMError('Groq rate_limit error (HTTP 429)')
            return {'ok':True}
        with patch.dict(os.environ,{'SIGNALFORGE_OLLAMA_FALLBACK':'signalforge-qwen'}), patch('signalforge.llm_client.local_model_status',return_value=(True,'')):
            with model_runtime(cfg,lambda *args:events.append(args)):
                stage=replace(cfg,evidence_dir=Path('/stage/evidence'))
                self.assertEqual(invoke(stage,call),{'ok':True})
                self.assertEqual(invoke(stage,call),{'ok':True})
                self.assertEqual(effective_config(stage).evidence_dir,Path('/stage/evidence'))
        self.assertEqual([c.provider for c in calls],['groq','ollama','ollama'])
        self.assertEqual(calls[-1].model,'signalforge-qwen')
        self.assertEqual(calls[-1].base_url,'http://127.0.0.1:11434/v1')
        self.assertEqual([x[0] for x in events],['provider_error','fallback_selected','generated','generated'])
        self.assertEqual(effective_config(cfg),cfg)

    def test_authentication_schema_and_disabled_fallback_do_not_switch(self):
        cfg=replace(Config(),provider='groq')
        for message in ('Groq authentication error (HTTP 401)','Model returned invalid JSON from Groq'):
            with patch.dict(os.environ,{'SIGNALFORGE_OLLAMA_FALLBACK':'signalforge-qwen'}), model_runtime(cfg,lambda *a:None), patch('signalforge.llm_client.local_model_status') as status:
                with self.assertRaises(LLMError):invoke(cfg,lambda c:(_ for _ in ()).throw(LLMError(message)))
                status.assert_not_called()
        with patch.dict(os.environ,{'SIGNALFORGE_OLLAMA_FALLBACK':''}), model_runtime(cfg,lambda *a:None), patch('signalforge.llm_client.local_model_status') as status:
            with self.assertRaises(LLMError):invoke(cfg,lambda c:(_ for _ in ()).throw(LLMError('Groq rate_limit error (HTTP 429)')))
            status.assert_not_called()

    def test_unavailable_local_model_keeps_original_failure(self):
        cfg=replace(Config(),provider='groq')
        with patch.dict(os.environ,{'SIGNALFORGE_OLLAMA_FALLBACK':'missing'}), model_runtime(cfg,lambda *a:None), patch('signalforge.llm_client.local_model_status',return_value=(False,'missing model')):
            with self.assertRaisesRegex(LLMError,'429'):
                invoke(cfg,lambda c:(_ for _ in ()).throw(LLMError('Groq rate_limit error (HTTP 429)')))

    def test_provider_json_schema_rejection_can_recover_without_accepting_it(self):
        cfg=replace(Config(),provider='groq')
        calls=[]
        def generate(selected):
            calls.append(selected.provider)
            if selected.provider=='groq':raise LLMError('Model returned invalid JSON from Groq structured generation; provider schema validation failed.')
            return {'local_proposal':'requires normal validation'}
        with patch.dict(os.environ,{'SIGNALFORGE_OLLAMA_FALLBACK':'signalforge-qwen'}), model_runtime(cfg,lambda *a:None), patch('signalforge.llm_client.local_model_status',return_value=(True,'')):
            self.assertEqual(invoke(cfg,generate),{'local_proposal':'requires normal validation'})
        self.assertEqual(calls,['groq','ollama'])
