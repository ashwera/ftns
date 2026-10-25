import copy
import hashlib
import json
from dataclasses import replace
from pathlib import Path
import tempfile
import unittest
from signalforge.investigation import check_citation, calculate, adjudicate, evidence_map, attach_machine_evidence_passages, bound_source_passages, attach_planning_leads, collect_sources
from signalforge.config import Config
from unittest.mock import patch


class InvestigationTests(unittest.TestCase):
    def test_same_url_and_repeated_content_cannot_become_distinct_sources(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp); inputs=root/'data/pipeline_inputs'; inputs.mkdir(parents=True)
            folder=root/'run'; folder.mkdir()
            registry=root/'registry.json'; registry.write_text(json.dumps({'companies':[{'canonical_name':'Example Energy Limited','verified_identifier':'EXAMPLE','aliases':['Example Energy'],'verification_status':'verified','verification_source':'fixture'}]}))
            rows=[]
            for index,text in enumerate(['Capacity is a future target; commissioning needs a dated operational record. '*3,
                                         'Capacity  is  a future target; commissioning needs a dated operational record. '*3,
                                         'Capacity differs in this snapshot but its source URL repeats the first document. '*3]):
                p=inputs/f'{index}.txt'; p.write_text(text)
                rows.append(dict(source_id=str(index),publisher='Example Energy Limited',source_class='official_filing',source_type='report',local_path=p.name,
                    sha256=hashlib.sha256(p.read_bytes()).hexdigest(),url='https://issuer.example/original' if index!=1 else 'https://mirror.example/copy'))
            (inputs/'example_catalog.json').write_text(json.dumps({'company':'Example Energy Limited','sources':rows}))
            cfg=replace(Config(),registry_path=registry,evidence_dir=root/'no-evidence')
            with patch('signalforge.investigation.ROOT',root):
                sources,audit=collect_sources(folder,'Example Energy Limited','capacity commissioning',cfg)
            self.assertEqual(len(sources),1)
            self.assertEqual(len([a for a in audit if a['action']=='Deduplicate source']),2)
    def test_research_lead_quotes_a_real_checked_passage_without_creating_claims(self):
        result={'claims':[], 'sources':[{'id':'s','lineage':'issuer:X', 'passages':[
            {'id':'s1','origin_evidence_id':'ev_x','text':'Commissioned capacity is disclosed for one project; future project targets need separate checks.'}]}]}
        attach_planning_leads(result, {'hypothesis':'Did the same project reach its announced milestone?'})
        self.assertEqual(result['claims'], [])
        lead=result['research_leads'][0]
        check_citation(lead['citation'], evidence_map(result['sources']))
        self.assertEqual(lead['confidence'],'Weak')
        self.assertIsNone(lead['date'])
    def test_context_bound_keeps_whole_upstream_passages_and_document_diversity(self):
        sources = [dict(id='a',passages=[dict(id='a1',text='a'*30),dict(id='a2',text='b'*30,origin_evidence_id='ev_a')]),
                   dict(id='b',passages=[dict(id='b1',text='c'*30)])]
        result = bound_source_passages(sources, max_chars=90)
        self.assertEqual(sum(len(p['text']) for s in result for p in s['passages']), 90)
        self.assertEqual({p['id'] for s in result for p in s['passages']},{'a1','a2','b1'})
        small = bound_source_passages(sources, max_chars=35)
        self.assertEqual([p['id'] for s in small for p in s['passages']], ['a2'])
    def test_upstream_passage_requires_same_original_hash_path_and_exact_quote(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'original.pdf'
            path.write_bytes(b'original bytes')
            digest = hashlib.sha256(path.read_bytes()).hexdigest()
            text = 'The planned project is expected to commission in 2027.'
            eid = 'ev_' + 'a' * 24
            source = {'id': 'src_x', 'lineage': 'issuer:X', 'sha256': digest,
                      'snapshot_path': str(path), 'passages': []}
            record = {'evidence_id': eid, 'source_path': str(path), 'excerpt_or_fact': text,
                'page_number': 5, 'machine_verification': {'source_sha256': digest,
                'passage_sha256': hashlib.sha256(text.encode()).hexdigest(),
                'checks': dict.fromkeys(['original_sha256','verbatim_page_passage','canonical_issuer','substantive_text'], True)}}
            for field, bad in [('source_sha256', 'b'*64), ('passage_sha256', 'c'*64)]:
                changed = copy.deepcopy(record); changed['machine_verification'][field] = bad
                self.assertEqual(attach_machine_evidence_passages([source], [changed]), 0)
            changed = copy.deepcopy(record); changed['source_path'] = str(path.with_name('other.pdf'))
            self.assertEqual(attach_machine_evidence_passages([source], [changed]), 0)
            self.assertEqual(attach_machine_evidence_passages([source], [record]), 1)
            self.assertEqual(attach_machine_evidence_passages([source], [record]), 0)
            citation = {'evidence_id': eid, 'quote': text}
            check_citation(citation, evidence_map([source]))
            self.assertEqual(citation['evidence_id'], 'src_x_' + eid)
            with self.assertRaises(ValueError):
                check_citation({'evidence_id': eid, 'quote': text.replace('2027', '2024')}, evidence_map([source]))

    def setUp(self):
        self.sources = [
            {'id':'a','lineage':'issuer:X','passages':[{'id':'a1','page':1,'text':'Unit 3 capacity is 660 MW; commercial operation 15.06.2025.'}]},
            {'id':'b','lineage':'regulator:Y','passages':[{'id':'b1','page':2,'text':'Unit 3 capacity is 660 MW. Forecast did not include this unit.'}]}]
        self.evidence = evidence_map(self.sources)

    def test_fabricated_quote_and_unknown_id_rejected(self):
        check_citation({'evidence_id':'a1','quote':'Unit 3 capacity is 660 MW'}, self.evidence)
        for citation in [{'evidence_id':'a1','quote':'Unit 3 capacity is 990 MW'}, {'evidence_id':'invented','quote':'Unit 3 capacity is 660 MW'}]:
            with self.assertRaises(ValueError): check_citation(citation, self.evidence)
        with self.assertRaises(ValueError):
            check_citation({'evidence_id':'a1','quote':'Unit 3 capacity is not 660 MW'}, self.evidence)

    def test_decimal_calculation_requires_real_operands(self):
        spec={'label':'Same capacity ratio','operation':'ratio_percent','unit':'%','basis':'same unit',
              'inputs':[{'value':'660','evidence_id':e,'quote':'Unit 3 capacity is 660 MW'} for e in ['a1','b1']]}
        self.assertEqual(calculate(spec, self.evidence)['result'], '100')
        spec['inputs'][0]['value']='66'
        with self.assertRaises(ValueError): calculate(spec, self.evidence)

    def test_dates_cannot_invent_month_end(self):
        spec={'label':'gap','operation':'days','unit':'days','basis':'same COD',
            'inputs':[{'value':d,'evidence_id':'a1','quote':'commercial operation 15.06.2025.'} for d in ['2025-06-15','2025-03-31']]}
        with self.assertRaises(ValueError): calculate(spec, self.evidence)

    def fixture(self):
        draft={'status':'supported','headline':'Narrow finding','summary':'Supported statement','why_it_matters':[],
            'claims':[{'id':'c1','key':True,'assessment':'supported','text':'Unit capacity is 660 MW',
            'citations':[{'evidence_id':e,'quote':'Unit 3 capacity is 660 MW'} for e in ['a1','b1']]}],
            'timeline':[],'calculations':[],'counterargument':{'text':'Alternative','evidence_ids':['b1']},
            'falsification':'A correction','limitations':[]}
        review={'claims':[{'id':'c1','verdict':'supported','reason':'Both passages agree','independent_corroboration':True}],
            'conclusion_supported':True,'conclusion_reason':'Narrow factual match','calculation_basis_valid':True,
            'counterargument_addressed':True,'novelty_established':False}
        return draft,review

    def test_mirror_and_semantic_disagreement_do_not_raise_grade(self):
        draft, review=self.fixture()
        self.assertEqual(adjudicate(draft,review,self.sources)['evidence_strength'],'Moderate')
        mirrors=copy.deepcopy(self.sources); mirrors[1]['lineage']='issuer:X'
        self.assertEqual(adjudicate(draft,review,mirrors)['evidence_strength'],'Weak')
        review['claims'][0]['independent_corroboration']=False
        self.assertEqual(adjudicate(draft,review,self.sources)['evidence_strength'],'Weak')
        review['conclusion_supported']=False
        result = adjudicate(draft,review,self.sources)
        self.assertEqual(result['status'],'inconclusive')
        self.assertNotEqual(result['headline'], draft['headline'])
        self.assertEqual(result['proposed_headline'], draft['headline'])


if __name__ == '__main__': unittest.main()
