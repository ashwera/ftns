import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from signalforge.resume_run import resume
from signalforge.resume_run import preserve_report
from signalforge.research_session import record_investigation_outcome


class ResumeRunTests(unittest.TestCase):
    def test_prior_report_is_preserved_before_provider_recovery(self):
        with tempfile.TemporaryDirectory() as tmp:
            folder=Path(tmp)
            for name in ('manifest.json','investigation.json','investigation_report.md'):
                (folder/name).write_text('original '+name)
            archive=folder/preserve_report(folder)
            (folder/'investigation.json').write_text('new attempted report')
            self.assertEqual((archive/'investigation.json').read_text(),'original investigation.json')
            self.assertEqual((archive/'manifest.json').read_text(),'original manifest.json')
    def test_gap_report_does_not_mark_model_investigation_successful(self):
        manifest={'stages':[{'name':'investigation','execution':'running'}, {'name':'adjudication','execution':'not_executed'}]}
        record_investigation_outcome(manifest, {'report_type':'evidence_gap','failed_stage':'investigation_initial','summary':'Exact quote validation failed'})
        self.assertEqual(manifest['stages'][0]['execution'],'failed')
        self.assertEqual(manifest['stages'][1]['execution'],'deterministic_evidence_gap')
    def test_active_run_and_invalid_id_cannot_start_duplicate_model_work(self):
        with tempfile.TemporaryDirectory() as tmp:
            run_id='research_20261025T000000_123456abcdef'
            folder=Path(tmp)/run_id; folder.mkdir()
            (folder/'manifest.json').write_text(json.dumps({'status':'running','stage':'investigation'}))
            with patch('signalforge.research_session.ROOT',Path(tmp)), \
                 patch('signalforge.research_session.ResearchSessions.__init__', lambda self, **kw: setattr(self,'root',Path(tmp))), \
                 patch('signalforge.resume_run.run_investigation') as investigate:
                with self.assertRaisesRegex(ValueError,'still marked active'):
                    resume(run_id)
                with self.assertRaises(KeyError):
                    resume('../../.env')
            investigate.assert_not_called()
