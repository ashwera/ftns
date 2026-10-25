import copy
import hashlib
from pathlib import Path
import tempfile
import unittest
from signalforge.investigation import check_citation, calculate, adjudicate, evidence_map, attach_machine_evidence_passages, bound_source_passages


class InvestigationTests(unittest.TestCase):
    def test_excerpt_absence_cannot_become_document_wide_non_disclosure(self):
        draft,review=self.fixture()
        draft['claims'][0]['text']='The report does not disclose any other commissioned capacity.'
        result=adjudicate(draft,review,self.sources)
        self.assertEqual(result['claims'][0]['assessment'],'unresolved')
        self.assertEqual(result['status'],'inconclusive')
        self.assertIn('Selected passages',result['summary'])

    def test_quote_references_resolve_only_to_unchanged_matching_passages(self):
        from signalforge.investigation import quote_catalog, resolve_quote_references, norm
        sources=[{'id':'s','passages':[{'id':'p','page':1,'text':'The unit has a capacity of 660 MW. Commercial operation begins in June.'}]}]
        catalog=quote_catalog(sources)
        self.assertTrue(all(q['text'] in norm(sources[0]['passages'][0]['text']) for q in catalog))
        citation={'evidence_id':'p','quote':catalog[0]['quote_id']}
        value={'claims':[{'citations':[citation]}]}
        self.assertTrue(resolve_quote_references(value,catalog))
        self.assertEqual(citation['quote'],catalog[0]['text'])
        with self.assertRaises(ValueError):
            resolve_quote_references({'claims':[{'citations':[{'evidence_id':'other','quote':catalog[0]['quote_id']}]}]},catalog)

    def test_bounded_model_view_preserves_required_full_passage(self):
        from dataclasses import replace
        from signalforge.config import Config
        from signalforge.investigation import model_sources
        source={'id':'s1','title':'Synthetic','lineage':'issuer:fixture','passages':[{'id':'required','page':1,'text':'x'*9500}]}
        cfg=replace(Config(),provider='groq')
        self.assertEqual(model_sources([source],cfg),[])
        view=model_sources([source],cfg,{'required'})
        self.assertEqual(view[0]['passages'][0]['text'],source['passages'][0]['text'])

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

    def test_exact_short_quote_gets_actionable_length_error_not_mismatch(self):
        sources = [{'id': 's', 'passages': [{'id': 'p', 'text': '15 MTY Capacity 68.5% \nComplete'}]}]
        evidence = evidence_map(sources)
        with self.assertRaisesRegex(ValueError, r'too short \(14 normalized characters; minimum 15\)'):
            check_citation({'evidence_id': 'p', 'quote': '68.5% Complete'}, evidence)
        check_citation({'evidence_id': 'p', 'quote': '15 MTY Capacity 68.5% Complete'}, evidence)
        with self.assertRaisesRegex(ValueError, 'exact contiguous span'):
            check_citation({'evidence_id': 'p', 'quote': '15 MTY Capacity 69.5% Complete'}, evidence)

    def test_failed_optional_quote_repairs_without_losing_other_observations(self):
        from dataclasses import replace
        from unittest.mock import Mock, patch
        from signalforge.config import Config
        from signalforge.investigation import draft_result
        draft, _ = self.fixture()
        source = copy.deepcopy(self.sources)
        source[0]['passages'].append({'id': 'short', 'page': 3,
            'text': 'JCRL rail project: 68.5% Complete; commissioning expected June 2027.'})
        draft['calculations'] = [{'label': 'Unsupported percentage calculation', 'operation': 'ratio_percent',
            'inputs': [{'value': v, 'evidence_id': 'short', 'quote': '68.5% Complete'} for v in ('68.5', '100')],
            'unit': '%', 'basis': 'project progress'}]
        draft['follow_up_queries'] = []
        repaired = copy.deepcopy(draft)
        repaired['calculations'] = []
        generator = Mock(side_effect=[draft, repaired])
        with tempfile.TemporaryDirectory() as temp, patch('signalforge.investigation.generate_json', generator):
            result = draft_result(Path(temp), 'Fixture', 'Question', {}, source,
                replace(Config(), provider='gemini', fallback_providers=''), 'investigation_initial')
            self.assertEqual(result['claims'], draft['claims'])
            self.assertEqual(result['calculations'], [])
            self.assertEqual(generator.call_count, 2)
            self.assertIn('too short (14 normalized characters; minimum 15)', generator.call_args.args[0])
            self.assertIn('Previous JSON to repair in place', generator.call_args.args[0])
            # A resume feeds the rejected artifact and precise error back to the
            # model, while the original raw response remains unchanged.
            generator.reset_mock(side_effect=True)
            generator.return_value = repaired
            import json
            original = Path(temp) / 'investigation_resume_model_audit' / 'failed' / 'attempt_1_raw_response.json'
            original.parent.mkdir(parents=True)
            original.write_text(json.dumps(draft))
            # An existing rejected stage file must enter the same bounded
            # repair path rather than abort before model repair can run.
            (Path(temp) / 'investigation_resume.json').write_text(json.dumps(draft))
            second = draft_result(Path(temp), 'Fixture', 'Question', {}, source,
                replace(Config(), provider='gemini', fallback_providers=''), 'investigation_resume')
            self.assertEqual(second['claims'], draft['claims'])
            self.assertEqual(generator.call_count, 1)
            self.assertEqual(generator.call_args.args[1]['repair_context']['previous_draft'], draft)
            self.assertIn('too short', generator.call_args.args[1]['repair_context']['validation_error'])
            self.assertEqual(json.loads(original.read_text()), draft)

    def test_sum_cannot_count_the_same_quoted_project_twice(self):
        spec = {'label': 'Duplicated unit', 'operation': 'sum', 'unit': 'MW', 'basis': 'same unit',
            'inputs': [{'value': '660', 'evidence_id': 'a1', 'quote': 'Unit 3 capacity is 660 MW'} for _ in range(2)]}
        with self.assertRaisesRegex(ValueError, 'double-counts one observation'):
            calculate(spec, self.evidence)

    def test_saved_duplicate_calculation_is_withheld_without_erasing_exact_claims(self):
        from dataclasses import replace
        from unittest.mock import Mock, patch
        import json
        from signalforge.config import Config
        from signalforge.investigation import draft_result
        draft, _ = self.fixture()
        draft['follow_up_queries'] = []
        draft['calculations'] = [{'label': 'Duplicate unit', 'operation': 'sum', 'unit': 'MW', 'basis': 'same unit',
            'inputs': [{'value': '660', 'evidence_id': 'a1', 'quote': 'Unit 3 capacity is 660 MW'} for _ in range(2)]}]
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            raw = root / 'investigation_final_model_audit' / 'saved' / 'attempt_1_raw_response.json'
            raw.parent.mkdir(parents=True)
            raw.write_text(json.dumps(draft))
            generator = Mock(side_effect=AssertionError('No new draft needed for duplicate operand rejection'))
            with patch('signalforge.investigation.generate_json', generator):
                result = draft_result(root, 'Fixture', 'Question', {}, self.sources,
                    replace(Config(), provider='gemini', fallback_providers=''), 'investigation_final')
            self.assertEqual(result['claims'], draft['claims'])
            self.assertEqual(result['calculations'], [])
            generator.assert_not_called()
            self.assertEqual(json.loads(raw.read_text()), draft)
            audit = json.loads((root / 'investigation_final_recovery.json').read_text())
            self.assertIn('double-counts', audit['discarded_calculations'][0]['reason'])

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
