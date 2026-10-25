import http.client
import json
import os
from pathlib import Path
import tempfile
import threading
import time
import unittest
from unittest.mock import patch
from signalforge.config import Config
from signalforge.research_service import handler
from signalforge.research_session import ResearchSessions, local_config, execute
from signalforge.research_session import cached_machine_records
from http.server import ThreadingHTTPServer


class ServiceTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        def execute(folder, manifest, config, update):
            update('discovery', 'Actual test executor invoked')
            update('retrieval', 'No fixture sources available', 'blocked')
        self.sessions = ResearchSessions(self.temp.name, Config(), execute)
        self.server = ThreadingHTTPServer(('127.0.0.1', 0), handler(self.sessions))
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()

    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join()
        deadline = time.monotonic() + 2
        while self.sessions.active and time.monotonic() < deadline:
            time.sleep(.01)
        self.temp.cleanup()

    def request(self, method, path, payload=None, **headers):
        connection = http.client.HTTPConnection('127.0.0.1', self.server.server_port)
        defaults = {'Host': '127.0.0.1:8765', 'Origin': 'http://127.0.0.1:5173', 'Content-Type': 'application/json'}
        defaults.update(headers)
        connection.request(method, path, json.dumps(payload) if payload is not None else None, defaults)
        response = connection.getresponse()
        result = response.status, json.loads(response.read())
        connection.close()
        return result

    def test_actual_start_poll_and_persistence(self):
        status, run = self.request('POST', '/api/agent/runs', {'company': 'Generic Company', 'prompt': 'Find contradictory disclosures'})
        self.assertEqual(status, 202)
        deadline = time.monotonic() + 2
        while self.sessions.active and time.monotonic() < deadline:
            time.sleep(.01)
        status, result = self.request('GET', '/api/agent/runs/' + run['run_id'])
        self.assertEqual(status, 200)
        self.assertEqual(result['status'], 'blocked')
        self.assertIsNone(result['finding'])
        self.assertEqual(len(result['events']), 2)
        restored = ResearchSessions(self.temp.name, Config()).get(run['run_id'])
        self.assertEqual(restored, result)
        self.assertTrue((Path(self.temp.name) / run['run_id'] / 'events.jsonl').is_file())

    def test_reject_foreign_hosts_origins_and_paths(self):
        for headers in ({'Host': 'evil.example:8765'}, {'Origin': 'https://evil.example'}, {'Origin': 'null'}):
            self.assertEqual(self.request('POST', '/api/agent/runs', {}, **headers)[0], 403)
        self.assertEqual(self.request('GET', '/api/agent/runs/../../.env')[0], 404)
        self.assertEqual(self.request('GET', '/api/agent/files')[0], 404)

    def test_input_contract(self):
        for payload in ({}, {'company': 'X', 'prompt': 'Y', 'command': 'ls'}, {'company': '', 'prompt': 'Y'}, {'company': 'X', 'prompt': 'x' * 4001}):
            self.assertEqual(self.request('POST', '/api/agent/runs', payload)[0], 400)
        self.assertEqual(self.request('POST', '/api/agent/runs', {}, **{'Content-Type': 'text/plain'})[0], 415)

    def test_busy_and_redacted_failure(self):
        release = threading.Event()
        def failure(folder, manifest, config, update):
            release.wait(2)
            raise RuntimeError('SECRET_KEY_DO_NOT_LOG')
        self.sessions.executor = failure
        _, run = self.request('POST', '/api/agent/runs', {'company': 'X', 'prompt': 'Y'})
        self.assertEqual(self.request('POST', '/api/agent/runs', {'company': 'X', 'prompt': 'Y'})[0], 409)
        release.set()
        deadline = time.monotonic() + 2
        while self.sessions.active and time.monotonic() < deadline:
            time.sleep(.01)
        result = self.sessions.get(run['run_id'])
        self.assertEqual(result['status'], 'completed')
        self.assertEqual(result['investigation']['report_type'], 'evidence_gap')
        self.assertEqual(result['investigation']['failed_stage'], 'queued')
        self.assertEqual(result['investigation']['claims'], [])
        self.assertNotIn('SECRET_KEY', json.dumps(result))

    def test_dotenv_literal_and_config_override_after_import(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / 'project'
            root.mkdir()
            (root / '.env').write_text('SIGNALFORGE_API_KEY="literal-$(never-execute)"\nSIGNALFORGE_MODEL=dotenv-model\nIGNORED_KEY=secret\n')
            with patch('signalforge.research_session.ROOT', root), patch.dict(os.environ, {}, clear=True):
                config = local_config()
                self.assertEqual(config.api_key, 'literal-$(never-execute)')
                self.assertEqual(config.model, 'dotenv-model')
                self.assertNotIn('IGNORED_KEY', os.environ)

    def test_execution_uses_public_provider_and_bounded_retrieval(self):
        from signalforge import source_discovery as sd
        folder = Path(self.temp.name) / 'execution'
        folder.mkdir()
        updates = []
        report = {'search_results': [], 'retrieval_status': 'no_results'}
        with patch.object(sd, 'discover', return_value=report) as discover, patch('signalforge.research_session.machine_records', return_value=[]), \
             patch('signalforge.company_onboarding.onboard', side_effect=ValueError('No original fixture')):
            execute(folder, {'company': 'Any Company', 'prompt': 'Any question'}, Config(), lambda *a, **kw: updates.append((a, kw)))
        args = discover.call_args
        self.assertEqual(args.args, ('Any Company', 'Any question'))
        self.assertTrue(args.kwargs['retrieve'])
        self.assertEqual(args.kwargs['provider'].name, 'bing_rss')
        self.assertEqual(args.kwargs['budget'].request_timeout, 40)
        self.assertEqual(args.kwargs['budget'].max_seconds, 90)
        self.assertEqual(updates[-1][0][2], 'completed')
        result = json.loads((folder/'investigation.json').read_text())
        self.assertEqual(result['report_type'], 'evidence_gap')
        self.assertEqual(result['claims'], [])
        self.assertTrue((folder/'investigation_report.md').is_file())

    def test_cached_intake_requires_matching_company_and_pinned_original(self):
        from dataclasses import replace
        root = Path(self.temp.name) / 'cache_fixture'
        inputs = root / 'data/pipeline_inputs'; inputs.mkdir(parents=True)
        catalog = {'company':'Example Limited', 'sources':[{'source_id':'annual', 'source_class':'official_filing', 'source_type':'annual_report', 'publisher':'Example Limited', 'local_path':'original.pdf', 'sha256':'a'*64}]}
        (inputs / 'example_catalog.json').write_text(json.dumps(catalog))
        registry = root / 'registry.json'
        registry.write_text(json.dumps({'companies':[{'canonical_name':'Example Limited', 'aliases':['Example'], 'verified_identifier':'EXAMPLE', 'verification_status':'verified', 'verification_source':'https://exchange.example/issuer'}]}))
        folder = root / 'run'; folder.mkdir()
        cfg = replace(Config(), registry_path=registry)
        with patch('signalforge.research_session.ROOT', root), patch('signalforge.machine_evidence.create_machine_evidence', return_value=[{'evidence_id':'test'}]) as checker:
            self.assertEqual(len(cached_machine_records(folder, 'Example', cfg)), 1)
            self.assertEqual(checker.call_args.kwargs['expected_sha256'], 'a'*64)
            saved=json.loads((folder/'machine_evidence_report.json').read_text())
            self.assertEqual(saved['intake_mode'], 'cached_original_rechecked')
            catalog['sources'][0].pop('sha256'); (inputs/'example_catalog.json').write_text(json.dumps(catalog))
            checker.reset_mock()
            self.assertEqual(cached_machine_records(folder, 'Example', cfg), [])
            checker.assert_not_called()

    def test_onboarding_resume_reuses_only_completed_matching_discovery(self):
        from dataclasses import replace
        from signalforge import source_discovery as sd
        root=Path(self.temp.name)/'resume';root.mkdir();(root/'discovery').mkdir()
        report={'company':'Unseen Energy','search_results':[],'retrieval_status':'failed',
                'action_log':[{'action':'discovery_stopped'}]}
        path=root/'discovery/discovery_report.json';path.write_text(json.dumps(report))
        cfg=replace(Config(),provider='groq',groq_api_key='fixture')
        updates=[]
        with patch.object(sd,'discover') as discover,patch('signalforge.company_onboarding.onboard',side_effect=ValueError('No eligible original')):
            execute(root,{'company':'Unseen Energy','prompt':'Capacity'},cfg,lambda *a,**kw:updates.append((a,kw)),reuse_discovery=True)
            discover.assert_not_called()
        self.assertEqual(updates[0][1]['search_execution'],'cached_completed_live_search')
        self.assertEqual(updates[-1][0][2],'completed')
        for company,actions in [('Other',[{'action':'discovery_stopped'}]),('Unseen Energy',[])]:
            path.write_text(json.dumps({**report,'company':company,'action_log':actions}))
            with self.assertRaisesRegex(ValueError,'incomplete or mismatched'):
                execute(root,{'company':'Unseen Energy','prompt':'Capacity'},cfg,lambda *a,**kw:None,reuse_discovery=True)


if __name__ == '__main__':
    unittest.main()
