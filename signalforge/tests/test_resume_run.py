import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from signalforge.resume_run import resume
from signalforge.research_session import record_investigation_outcome, ResearchSessions
from signalforge.config import Config


class ResumeRunTests(unittest.TestCase):
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
            sessions = ResearchSessions(root=Path(tmp), config=Config())
            sessions.active = run_id
            with patch('signalforge.resume_run.ResearchSessions', return_value=sessions), \
                 patch('signalforge.resume_run.run_investigation') as investigate:
                with self.assertRaisesRegex(ValueError,'still marked active'):
                    resume(run_id)
                with self.assertRaises(KeyError):
                    resume('../../.env')
            investigate.assert_not_called()
