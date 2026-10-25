import hashlib
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from signalforge.company_onboarding import onboard, isin_valid
from signalforge.config import Config


class OnboardingTests(unittest.TestCase):
    def test_ambiguous_saved_pdf_lead_requires_original_identity_and_is_not_financial_evidence(self):
        for valid in (True,False):
            with tempfile.TemporaryDirectory() as tmp:
                folder=Path(tmp);(folder/'discovery').mkdir()
                pdf=folder/'download.pdf';pdf.write_bytes(b'%PDF-fixture')
                url='https://issuer.example/annual.pdf'
                report={'company':'Meridian Energy Limited','rejected_results':[{'rejection_reason':'no_distinctive_company_token_brand_or_issuer_domain_match',
                    'result':{'title':'Annual Report','url':url}}]}
                (folder/'discovery/discovery_report.json').write_text(json.dumps(report))
                identity=dict(canonical_name='Meridian Energy Limited',isin='INE733E01010',page=2,snippet='Synthetic issuer declaration')
                with patch('signalforge.company_onboarding.download_pdf',return_value=(pdf,hashlib.sha256(pdf.read_bytes()).hexdigest())) as download, \
                     patch('signalforge.company_onboarding.read_identity',side_effect=None if valid else ValueError('Wrong company'),return_value=identity), \
                     patch('signalforge.company_onboarding.drop_folder_pdfs',return_value=[]), \
                     patch('signalforge.company_onboarding.wikidata_identity',return_value=(None,None)), \
                     patch('signalforge.company_onboarding.candidate_pdf_urls',return_value=[]):
                    if valid:
                        _,_,_,output=onboard('Meridian Energy Limited',folder,Config())
                        self.assertEqual(output['selected_origin'],'unverified_discovery_pdf_identity_probe')
                        self.assertEqual(output['selected_url'],url)
                    else:
                        with self.assertRaisesRegex(ValueError,'No annual-report'):onboard('Meridian Energy Limited',folder,Config())
                        self.assertFalse((folder/'run_registry.json').exists())
                    self.assertEqual(download.call_count,1)
                    self.assertFalse((folder/'eligible_evidence').exists())

    def test_wrong_company_or_noise_rejection_never_becomes_identity_probe(self):
        with tempfile.TemporaryDirectory() as tmp:
            folder=Path(tmp);(folder/'discovery').mkdir()
            report={'company':'Meridian','rejected_results':[{'rejection_reason':'wrong_company','result':{'title':'Annual Report','url':'https://other.example/annual.pdf'}}]}
            (folder/'discovery/discovery_report.json').write_text(json.dumps(report))
            with patch('signalforge.company_onboarding.download_pdf') as download, \
                 patch('signalforge.company_onboarding.drop_folder_pdfs',return_value=[]), \
                 patch('signalforge.company_onboarding.candidate_pdf_urls',return_value=[]):
                with self.assertRaises(ValueError):onboard('Meridian',folder,Config())
                download.assert_not_called()

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
