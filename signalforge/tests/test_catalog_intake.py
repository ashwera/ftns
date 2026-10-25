import hashlib
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from signalforge.config import Config
from signalforge.catalog_intake import prepared_discovery


class CatalogIntakeTests(unittest.TestCase):
    def test_explicit_company_and_hash_gate_no_fresh_search_claim(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);folder=root/'data/pipeline_inputs';folder.mkdir(parents=True)
            source=folder/'source.pdf';source.write_bytes(b'%PDF- synthetic test bytes')
            catalog={'company':'Example Limited','research_intake':'operator_cached_originals','sources':[
                {'source_id':'original','publisher':'Example Limited','source_class':'official_filing','source_type':'annual_report',
                 'local_path':'source.pdf','sha256':hashlib.sha256(source.read_bytes()).hexdigest()}]}
            path=folder/'example_catalog.json';path.write_text(json.dumps(catalog))
            with patch('signalforge.catalog_intake.ROOT',root), patch('signalforge.catalog_intake.load_registry',return_value={}), patch('signalforge.catalog_intake.verify_company',return_value=('Example Limited','TEST','verified')):
                report=prepared_discovery('Example','question',Config(),root/'run')
                self.assertEqual(report['search_queries'],[])
                self.assertEqual(report['execution_mode'],'cached_original_intake')
                self.assertEqual(len(report['catalog_sources']),1)
                source.write_bytes(b'changed')
                self.assertIsNone(prepared_discovery('Example','question',Config(),root/'other'))
                source.write_bytes(b'%PDF- synthetic test bytes')
                catalog['company']='Other Limited';path.write_text(json.dumps(catalog))
                self.assertIsNone(prepared_discovery('Example','question',Config(),root/'other'))
