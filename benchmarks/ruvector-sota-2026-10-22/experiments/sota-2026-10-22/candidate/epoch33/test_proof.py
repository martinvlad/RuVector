"""Adversarial, purely symbolic grammar checks; no benchmark/generalization claim."""
import importlib.util
from pathlib import Path
import sys
import unittest
sys.dont_write_bytecode=True
spec=importlib.util.spec_from_file_location('tested_proof',Path(__file__).with_name('proof.py'))
P=importlib.util.module_from_spec(spec);spec.loader.exec_module(P)


def exact(n=7,unit='months',subject='This Agreement',event='terminates',reference='the Effective Date'):
    return f'{subject} {event} exactly {n} {unit} after {reference}.'


def certify(doc,claim,premise=None,spans=None):
    return P.certificate(doc,doc if premise is None else premise,claim,
        [[0,len(doc)]] if spans is None else spans)


class SymbolicPolicy(unittest.TestCase):
    def test_exact_fact_and_plural_unit(self):
        cert,_=certify(exact(7,'month'),exact(7,'months'))
        self.assertEqual(cert['conclusion'],'Entailment')
        self.assertEqual(cert['rule'],'EXACT_GROUND_FACT')

    def test_positive_integer_metamorphic_contradictions(self):
        for a,b in [(2,9),(7,13),(31,45),(100,101),(999999998,999999999)]:
            cert,_=certify(exact(a),exact(b))
            self.assertEqual(cert['conclusion'],'Contradiction')
            self.assertEqual(cert['witness']['source_positive_exact_value'],a)
            self.assertEqual(cert['witness']['claim_positive_exact_value'],b)

    def test_anaphoric_source_link_is_not_discarded(self):
        doc=exact(8)+' The confidentiality obligations also end on that date.'
        cert,_=certify(doc,exact(11))
        self.assertEqual(cert['conclusion'],'Contradiction')
        self.assertEqual(len(cert['source_clauses']),2)
        self.assertEqual(cert['source_clauses'][1]['atom']['predicate'],'confidentiality_end_same_date')

    def test_open_world_two_models(self):
        doc='The Receiving Party shall return all written Confidential Information within five business days after a written request from the Disclosing Party.'
        claim='Disputes under this Agreement are governed by the laws of Ontario.'
        cert,_=certify(doc,claim)
        self.assertEqual(cert['conclusion'],'NotMentioned')
        self.assertEqual(cert['witness']['extensions'],[
            {'all_source_facts':True,'claim_atom':True},
            {'all_source_facts':True,'claim_atom':False}])

    def test_generic_return_words_and_exact_ground_fact(self):
        doc='The Disclosing Party shall return all written Confidential Information within eleven business days after a written request from the Receiving Party.'
        claim=doc.replace('eleven','11')
        cert,_=certify(doc,claim)
        self.assertEqual(cert['conclusion'],'Entailment')

    def test_within_is_not_exclusive_exactly(self):
        doc='The Receiving Party shall return all written Confidential Information within five business days after a written request from the Disclosing Party.'
        self.assertIsNone(certify(doc,doc.replace('five','nine'))[0])

    def test_units_are_not_converted(self):
        self.assertIsNone(certify(exact(1,'years'),exact(13,'months'))[0])
        self.assertIsNone(certify(exact(1,'years'),exact(12,'months'))[0])

    def test_reference_subject_event_must_match(self):
        for claim in [exact(13,subject='This Contract'),exact(13,event='expires'),
                exact(13,reference='the Execution Date'),exact(13,reference='disclosure')]:
            self.assertIsNone(certify(exact(7),claim)[0])

    def test_exactly_is_mandatory(self):
        self.assertIsNone(certify(exact().replace(' exactly',''),exact(13))[0])
        self.assertIsNone(certify(exact(),exact(13).replace(' exactly',''))[0])

    def test_no_partial_context_repairs(self):
        doc=exact(7)+' The confidentiality obligations also end on that date.'
        self.assertIsNone(certify(doc,exact(13),premise=exact(7),spans=[[0,len(exact(7))]])[0])
        self.assertIsNone(certify(doc,exact(13),premise=doc,spans=[[0,len(exact(7))]])[0])
        self.assertIsNone(certify(doc,exact(13),premise=' '+doc,spans=[[0,len(doc)]])[0])

    def test_unparsed_clause_and_trailing_fragment(self):
        for doc in [exact()+' Renewal is available.',exact()+' garbage',
                exact()+' This sentence is not part of the grammar.',exact()+';']:
            self.assertIsNone(certify(doc,exact(13))[0])

    def test_conditions_exceptions_negation_coordination(self):
        for doc in [exact().replace('.',' unless renewed.'),
                exact().replace('.',' except when extended.'),
                exact().replace('terminates','does not terminate'),
                exact()+' Provided that an extension is signed.',
                exact().replace(' exactly',' approximately'),
                exact().replace('.',' and the license continues.'),
                'Disputes under this Agreement are governed by the laws of Ontario when requested.',
                'Disputes under this Agreement are governed by the laws of Ontario on request.',
                'Disputes under this Agreement are governed by the laws of New York.']:
            self.assertIsNone(certify(doc,exact(13))[0])

    def test_inconsistent_or_ambiguous_scalar_source_abstains(self):
        for doc in [exact(7)+' '+exact(13),exact(7)+' '+exact(1,'years')]:
            self.assertIsNone(certify(doc,exact(7))[0])

    def test_unsupported_link_claim(self):
        self.assertIsNone(certify(exact(7),'The confidentiality obligations also end on that date.')[0])
        self.assertIsNone(certify('The confidentiality obligations also end on that date.',exact(7))[0])

    def test_existing_predicate_other_law_abstains(self):
        doc='Disputes under this Agreement are governed by the laws of Ontario.'
        self.assertIsNone(certify(doc,doc.replace('Ontario','Quebec'))[0])

    def test_unicode_and_nonpositive_or_decimal_scalars(self):
        for doc in [exact().replace('This','Thİs'),exact().replace('This','Thiſ'),
                exact().replace('Agreement','Agreement\u00a0'),exact(-3),exact(0),exact('1.5'),exact('01')]:
            self.assertIsNone(certify(doc,exact(13))[0])

    def test_source_size_and_clause_limits(self):
        self.assertIsNone(certify(exact()+' '*8192,exact(13))[0])
        self.assertIsNone(certify(' '.join([exact()]*17),exact(13))[0])

    def test_DEV_proof_explicitly_disabled_and_raw_tie_preserved(self):
        raw={'probabilities_E_C_N':[.1,.45,.45],'native_typed_argmax':'NotMentioned'}
        doc=exact(7);out=P.decide(doc,doc,exact(13),[[0,len(doc)]],raw,enabled=False)
        self.assertIsNone(out['certificate'])
        self.assertEqual(out['fallback_reason'],'proof_disabled_for_DEV')
        self.assertEqual(out['final_probabilities_E_C_N'],raw['probabilities_E_C_N'])
        self.assertEqual(out['final_typed_argmax'],'NotMentioned')

    def test_final_probabilities_and_raw_ablation(self):
        raw={'probabilities_E_C_N':[.8,.1,.1],'native_typed_argmax':'Entailment'}
        doc=exact(7);out=P.decide(doc,doc,exact(13),[[0,len(doc)]],raw)
        self.assertEqual(out['raw_probabilities_E_C_N'],raw['probabilities_E_C_N'])
        self.assertEqual(out['final_probabilities_E_C_N'],[0.,1.,0.])
        self.assertTrue(out['semantic_decision_override'])
        out=P.decide(doc,doc,'The recipient is allowed to disclose information.',[[0,len(doc)]],raw)
        self.assertEqual(out['final_probabilities_E_C_N'],raw['probabilities_E_C_N'])
        self.assertIsNone(out['certificate'])
        self.assertFalse(out['semantic_decision_override'])


if __name__=='__main__':
    unittest.main(verbosity=2)
