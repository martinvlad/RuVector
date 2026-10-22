"""Unseen synthetic inputs only; no benchmark files or labels imported."""
import copy
from fractions import Fraction
import importlib.util
import json
from pathlib import Path
import unittest

HERE=Path(__file__).resolve().parent
spec=importlib.util.spec_from_file_location('synthetic_probability',HERE/'probability.py');p=importlib.util.module_from_spec(spec);spec.loader.exec_module(p)


def bayes(prior=(20,40,40),rate=(2,4,1),mode=(25,50,75),order=(0,1,2)):
    names=['Aster Components Ltd','Birch Devices SA','Cobalt Systems AG']
    aliases=[x.split()[0] for x in names]
    return '\n'.join(['NORTH WORKSHOP INVESTIGATION',
      'Failed part: pressure valve, part number VP-Q4, returned after 5 months in service.',
      'Failure mode determined by the lab: cracked aperture ("aperture crack").','',
      'Supply data for VP-Q4 (purchasing, relevant build period):',
      *[f'  {names[i]} ........ {prior[i]} %'+(' of VP-Q4 valves' if i==0 else '') for i in order],
      '(For the VP-X2 valve the split is Aster 90 %, Birch 5 %, Cobalt 5 %.)','',
      'Field failure rates of VP-Q4 within 10 months in service (all failure modes):',
      '  '+' · '.join(f'{aliases[i]} {rate[i]} %' for i in order),
      "Failure-mode mix of those field failures (share of each supplier's VP-Q4 failures that were aperture cracks; the remainder were other modes):",
      '  '+' · '.join(f'{aliases[i]} {mode[i]} %' for i in order),
      "Engineer's note: failure rate and failure mode are stable across build years; nothing else in the history distinguishes the suppliers.",
      'Supplier scorecard (all parts): Aster 99 %, Birch 98 %, Cobalt 97 %.'])


B={'type':'choice','instructions':'Which supplier made the failed VP-Q4 valve? Give probabilities.',
   'criteria':{'indigo':'The valve was supplied by Cobalt Systems AG.','amber':'The valve was supplied by Aster Components Ltd.','rose':'The valve was supplied by Birch Devices SA.'}}


def connection(short=9,middle=7,long=4,late=40):
    return '\n'.join(['WEST TERMINAL CONNECTION NOTE',
      'Itinerary: inbound flight NX 82 scheduled to arrive at the hub at 10:00; outbound flight JZ 11 scheduled to depart at 11:00.',
      'Connection rule (hub data): with the outbound on time, the passenger makes the connection if the inbound arrives no more than 25 minutes late. If the outbound departs at least 15 minutes late, the passenger makes it if the inbound arrives no more than 40 minutes late. The outbound never departs early.',
      f'- Inbound NX 82, last {short+middle+long} operations on this weekday and season: {short} arrived no more than 25 minutes late; {middle} arrived between 26 and 40 minutes late; {long} arrived more than 40 minutes late.',
      f'- Outbound JZ 11: departs at least 15 minutes late on {late}% of days, otherwise on time (within 3 minutes).',
      "- The two flights' delays are independent (distinct equipment)."])


C={'type':'noul','instructions':'Will the passenger miss the connection? Give probabilities.',
   'criteria':{'false':'The passenger makes the connection.','true':'The passenger misses the connection.'}}


class ExactBayes(unittest.TestCase):
    def test_unseen_names_labels_values(self):
        proof=p.solve(bayes(),B)
        self.assertEqual(proof['exact_probability_fractions'],{'amber':[1,12],'rose':[2,3],'indigo':[1,4]})
        self.assertEqual(proof['normalization_denominator'],[3,250])
    def test_prior_counterfactual_changes_result(self):
        a=p.solve(bayes(),B);b=p.solve(bayes(prior=(80,10,10)),B)
        self.assertNotEqual(a['probabilities'],b['probabilities']);self.assertGreater(b['probabilities']['amber'],a['probabilities']['amber'])
    def test_likelihood_and_observed_mode_counterfactual(self):
        a=p.solve(bayes(),B);b=p.solve(bayes(rate=(1,1,8),mode=(10,10,90)),B)
        self.assertGreater(b['probabilities']['indigo'],a['probabilities']['indigo'])
    def test_permuted_rows_and_factors(self):
        self.assertEqual(p.solve(bayes(),B)['probabilities'],p.solve(bayes(order=(2,0,1)),B)['probabilities'])
    def test_irrelevant_different_part_and_scorecard_not_pooled(self):
        a=p.solve(bayes(),B);b=p.solve(bayes().replace('Aster 90 %, Birch 5 %, Cobalt 5 %','Aster 0 %, Birch 0 %, Cobalt 100 %').replace('Aster 99 %, Birch 98 %, Cobalt 97 %','Aster 1 %, Birch 2 %, Cobalt 3 %'),B)
        self.assertEqual(a['probabilities'],b['probabilities'])
    def test_source_offsets_and_JSON_serialization(self):
        state=bayes();proof=p.solve(state,B)
        for record in proof['source_spans']+proof['source_rows']:
            start,end=record['span'];self.assertEqual(state[start:end],record['text'])
        self.assertEqual(json.loads(json.dumps(proof)),proof)
    def test_all_operation_tree_nodes_exact(self):
        proof=p.solve(bayes(),B)
        for item in proof['tree']:
            inputs=[Fraction(*x) for x in item['inputs']]
            value=inputs[0]*inputs[1] if item['operation']=='multiply' else inputs[0]/inputs[1] if item['operation']=='divide' else sum(inputs)
            self.assertEqual(list(p.exact(value)),item['fraction'])
    def test_missing_likelihood_abstains(self):
        self.assertIsNone(p.solve(bayes().replace('Birch 4 % · ',''),B))
    def test_missing_conditional_mode_and_sufficiency_abstain(self):
        self.assertIsNone(p.solve(bayes().replace('aperture cracks','different mode'),B))
        self.assertIsNone(p.solve(bayes().replace('nothing else','other evidence'),B))
    def test_invalid_prior_norm_or_probability_abstain(self):
        self.assertIsNone(p.solve(bayes(prior=(20,20,20)),B));self.assertIsNone(p.solve(bayes(rate=(101,4,1)),B))
    def test_zero_denominator_abstains(self):
        self.assertIsNone(p.solve(bayes(rate=(0,0,0)),B));self.assertIsNone(p.solve(bayes(mode=(0,0,0)),B))
    def test_ambiguous_label_or_alias_abstains(self):
        q=copy.deepcopy(B);q['criteria']['rose']='The valve was supplied by Birch Devices SA or Aster Components Ltd.'
        self.assertIsNone(p.solve(bayes(),q));self.assertIsNone(p.solve(bayes().replace('Birch Devices SA','Aster Other SA'),B))
    def test_mismatched_target_or_unparsed_factor_condition_abstains(self):
        self.assertIsNone(p.solve(bayes().replace('Supply data for VP-Q4','Supply data for VP-X2'),B))
        self.assertIsNone(p.solve(bayes().replace('Aster 2 %','Aster 2 % if approved'),B))
    def test_observation_outside_likelihood_window_abstains(self):
        self.assertIsNone(p.solve(bayes().replace('after 5 months','after 11 months'),B))
    def test_duplicate_scope_or_factor_abstains(self):
        self.assertIsNone(p.solve(bayes()+'\n'+bayes(),B))
        self.assertIsNone(p.solve(bayes().replace('Aster 2 %','Aster 2 % · Aster 2 %'),B))


class IndependentMixture(unittest.TestCase):
    def test_unseen_counts_and_complement(self):
        proof=p.solve(connection(),C);self.assertEqual(proof['exact_probability_fractions'],{'yes':[41,100],'no':[59,100]})
    def test_counterfactual_branch_probability(self):
        self.assertEqual(p.solve(connection(late=0),C)['exact_probability_fractions']['yes'],[11,20])
        self.assertEqual(p.solve(connection(late=100),C)['exact_probability_fractions']['yes'],[1,5])
    def test_counterfactual_conditional_counts(self):
        a=p.solve(connection(),C);b=p.solve(connection(short=1,middle=3,long=16),C)
        self.assertGreater(b['probabilities']['yes'],a['probabilities']['yes'])
    def test_inverse_question_and_criterion_mapping(self):
        q={'type':'noul','instructions':'Will the passenger make the connection?',
           'criteria':{'true':'The passenger makes the connection.','false':'The passenger misses the connection.'}}
        self.assertEqual(p.solve(connection(),q)['exact_probability_fractions']['yes'],[59,100])
    def test_missing_independence_and_non_exhaustive_branch_abstain(self):
        self.assertIsNone(p.solve(connection().replace('are independent','may be independent'),C))
        self.assertIsNone(p.solve(connection().replace('otherwise on time','sometimes on time'),C))
    def test_contradictory_independence_abstains(self):
        self.assertIsNone(p.solve(connection()+"\nThese delays are dependent.",C))
    def test_count_mismatch_gap_overlap_and_bad_rate_abstain(self):
        for changed in [connection().replace('last 20','last 21'),connection().replace('between 26','between 27'),connection().replace('between 26','between 25'),connection(late=101)]:
            with self.subTest(changed=changed):self.assertIsNone(p.solve(changed,C))
    def test_thresholds_and_entity_scope_must_match(self):
        self.assertIsNone(p.solve(connection().replace('15 minutes late on','16 minutes late on'),C))
        self.assertIsNone(p.solve(connection().replace('- Inbound NX 82','- Inbound NX 83'),C))
    def test_question_polarity_ambiguity_abstains(self):
        q=copy.deepcopy(C);q['instructions']='Will the passenger make or miss the connection?'
        self.assertIsNone(p.solve(connection(),q))
        q=copy.deepcopy(C);q['criteria']['true']='The passenger may make or miss the connection.'
        self.assertIsNone(p.solve(connection(),q))
    def test_source_spans_and_exact_tree_replay(self):
        state=connection();proof=p.solve(state,C)
        for record in proof['source_spans']:
            self.assertEqual(state[slice(*record['span'])],record['text'])
        for item in proof['tree']:
            op=item['operation'];inputs=item['inputs']
            values=[Fraction(*x) for x in inputs] if op!='conditional_frequency' else inputs
            out=1-values[0] if op=='complement' else values[0]*values[1] if op=='multiply' else sum(values) if op=='add' else Fraction(*values)
            self.assertEqual(p.exact(out),item['fraction'])
    def test_unsupported_and_malformed_inputs_abstain(self):
        for state in ['',{},None,'The likely answer is amber.']:
            self.assertIsNone(p.solve(state,C))


class ExactFallback(unittest.TestCase):
    def test_driver_unsupported_retains_frozen97(self):
        spec=importlib.util.spec_from_file_location('synthetic_cycle3_driver',HERE/'rules.py');driver=importlib.util.module_from_spec(spec);spec.loader.exec_module(driver)
        state='Task: Say exactly five words. Response:a b c';q={'type':'noul','instructions':'Does the response fully satisfy the request?'}
        self.assertEqual(driver.solve(state,q),driver.baseline_proof(state,q))
    def test_driver_probability_and_missing_fact_fallback(self):
        spec=importlib.util.spec_from_file_location('synthetic_cycle3_driver2',HERE/'rules.py');driver=importlib.util.module_from_spec(spec);spec.loader.exec_module(driver)
        self.assertEqual(driver.solve(bayes(),B),p.solve(bayes(),B))
        state=bayes().replace('Birch 4 % · ','');self.assertEqual(driver.solve(state,B),driver.baseline_proof(state,B))


if __name__=='__main__':unittest.main()
