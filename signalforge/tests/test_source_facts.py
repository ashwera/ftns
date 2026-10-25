import hashlib,json
from pathlib import Path
import tempfile,unittest
from unittest.mock import patch
from signalforge.source_facts import attach_source_facts


class SourceFactTests(unittest.TestCase):
    def test_exact_reported_figures_arithmetic_and_stale_source_rejection(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);base=root/'data/pipeline_inputs';base.mkdir(parents=True)
            file=base/'original.txt';text='Page 1\nReport FY2025: Ground installed 12 MW. Rooftop installed 3 MW.';file.write_text(text)
            sha=hashlib.sha256(file.read_bytes()).hexdigest()
            cat={'company':'Example','sources':[{'source_id':'s','source_class':'official_filing','publisher':'Example','source_type':'report','local_path':'original.txt','sha256':sha}],
                'reported_facts':[{'id':'ground','label':'Ground','value':'12','unit':'MW','period':'FY2025','source_id':'s','page':1,'quote':'Ground installed 12 MW.'},
                                  {'id':'roof','label':'Roof','value':'3','unit':'MW','period':'FY2025','source_id':'s','page':1,'quote':'Rooftop installed 3 MW.'},
                                  {'id':'fake','label':'Fake','value':'99','unit':'MW','period':'FY2025','source_id':'s','page':1,'quote':'Invented 99 MW.'}],
                'source_crosschecks':[{'label':'Total','operation':'sum','fact_ids':['ground','roof']}]}
            (base/'example_catalog.json').write_text(json.dumps(cat))
            result={'company':'Example','sources':[{'id':'source','sha256':sha,'passages':[]}]}
            with patch('signalforge.source_facts.ROOT',root):
                attach_source_facts(result,None)
                self.assertEqual(len(result['reported_facts']),2)
                self.assertEqual(result['source_crosschecks'][0]['result'],'15')
                self.assertEqual(len(result['source_fact_rejections']),1)
                file.write_text('changed after initial parse')
                attach_source_facts(result,None)
                self.assertEqual(result['reported_facts'],[])
                self.assertEqual(result['source_crosschecks'],[])
