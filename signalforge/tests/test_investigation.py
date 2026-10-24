import copy
import unittest
from signalforge.investigation import check_citation, calculate, adjudicate, evidence_map


class InvestigationTests(unittest.TestCase):
    def setUp(self):
        self.sources = [
            {'id':'a','lineage':'issuer:X','passages':[{'id':'a1','page':1,'text':'Unit 3 capacity is 660 MW; commercial operation 15.06.2025.'}]},
            {'id':'b','lineage':'regulator:Y','passages':[{'id':'b1','page':2,'text':'Unit 3 capacity is 660 MW. Forecast did not include this unit.'}]}]
        self.evidence = evidence_map(self.sources)

    def test_fabricated_quote_and_unknown_id_rejected(self):
        check_citation({'evidence_id':'a1','quote':'Unit 3 capacity is 660 MW'}, self.evidence)
        for citation in [{'evidence_id':'a1','quote':'Unit 3 capacity is 990 MW'}, {'evidence_id':'invented','quote':'Unit 3 capacity is 660 MW'}]:
            with self.assertRaises(ValueError): check_citation(citation, self.evidence)

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
        self.assertEqual(adjudicate(draft,review,self.sources)['status'],'inconclusive')


if __name__ == '__main__': unittest.main()
