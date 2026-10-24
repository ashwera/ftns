import hashlib
import json
from pathlib import Path
import tempfile
import unittest
from types import SimpleNamespace
from unittest.mock import patch

from signalforge.company_onboarding import onboard, isin_valid, score_pdf_link, page_links, read_identity
from signalforge.config import Config


class OnboardingTests(unittest.TestCase):
    def test_discovered_original_works_without_catalog_and_rejects_wrong_company_drop(self):
        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp); (folder/'discovery').mkdir()
            pdf = folder/'source.pdf'; pdf.write_bytes(b'%PDF-fixture')
            digest = hashlib.sha256(pdf.read_bytes()).hexdigest()
            report = {'company':'Meridian Energy Limited', 'search_results':[{'retrieval_report':{'sources':[
                {'retrieval_status':'retrieved','saved_path':str(pdf),'source_sha256':digest,'canonical_url':'https://issuer.example/original.pdf'}]}}]}
            (folder/'discovery/discovery_report.json').write_text(json.dumps(report))
            identity = dict(canonical_name='Meridian Energy Limited', isin='INE733E01010', page=2, snippet='Synthetic issuer declaration')
            with patch('signalforge.company_onboarding.drop_folder_pdfs',return_value=[]), \
                 patch('signalforge.company_onboarding.read_identity', return_value=identity) as read, \
                 patch('signalforge.company_onboarding.wikidata_identity', return_value=(None,None)), \
                 patch('signalforge.company_onboarding.candidate_pdf_urls') as search:
                registry, path, actual, output = onboard('Meridian Energy Limited', folder, Config())
            search.assert_not_called()
            self.assertEqual(read.call_args.args[1], 'Meridian Energy Limited')
            self.assertEqual(output['selected_origin'],'live_discovery_snapshot')
            self.assertEqual(output['selected_url'],'https://issuer.example/original.pdf')
            self.assertEqual(actual,digest)
            self.assertTrue(registry.is_file())

    def test_external_identity_conflict_stops_and_never_creates_verified_registry(self):
        with tempfile.TemporaryDirectory() as tmp:
            folder=Path(tmp); pdf=folder/'source.pdf'; pdf.write_bytes(b'%PDF-fixture')
            identity=dict(canonical_name='Meridian Energy',isin='INE733E01010',page=1,snippet='Synthetic')
            with patch('signalforge.company_onboarding.drop_folder_pdfs',return_value=[]), \
                 patch('signalforge.company_onboarding.read_identity',return_value=identity), \
                 patch('signalforge.company_onboarding.wikidata_identity',return_value=('INE038A01020',None)):
                with self.assertRaisesRegex(ValueError,'conflicts'):
                    onboard('Meridian Energy',folder,Config(),pdf_path=pdf)
            self.assertFalse((folder/'run_registry.json').exists())
            self.assertEqual(json.loads((folder/'onboarding_report.json').read_text())['identity_status'],'conflicting')

    def test_known_isins_and_invalid_check_digits(self):
        self.assertTrue(isin_valid('INE038A01020'))
        self.assertFalse(isin_valid('INE038A01021'))

    def test_integrated_report_acronym_ranks_above_older_annual(self):
        self.assertGreater(score_pdf_link('https://issuer.example/HYPERLINKED_IAR_2024-25.pdf'),
                           score_pdf_link('https://issuer.example/AR2008.pdf'))

    def test_literal_pdf_links_in_script_are_navigation_leads(self):
        html = '<script>const html = "<a href=\'/documents/2026/AR2026.pdf\'>PDF</a>";</script>'
        with patch('signalforge.company_onboarding._fetch_text',return_value=html):
            self.assertIn(('https://issuer.example/documents/2026/AR2026.pdf',''), page_links('https://issuer.example/reports'))

    def test_labelled_cin_is_separate_identity_without_fabricated_isin(self):
        from signalforge.machine_evidence import _issuer_matches
        text='Corporate information. Registered office Example Energy Limited. CIN: L12345MH2000PLC123456. Contact details.'
        page=SimpleNamespace(extract_text=lambda:text)
        with patch('pypdf.PdfReader',return_value=SimpleNamespace(is_encrypted=False,pages=[page])):
            identity=read_identity(b'%PDF-fixture','Example Energy Limited')
        self.assertEqual(identity['identifier_type'],'CIN')
        self.assertIsNone(identity['isin'])
        self.assertEqual(identity['identifier'],'L12345MH2000PLC123456')
        self.assertTrue(_issuer_matches(text,identity['canonical_name'],identity['identifier']))
        self.assertFalse(_issuer_matches(text,'Other Energy Limited',identity['identifier']))
