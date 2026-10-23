"""Pure probability/whole-proposition tests; no model/native execution."""
from pathlib import Path
import importlib.util
import unittest

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location('test_e16_pairing', HERE/'pairing.py')
P = importlib.util.module_from_spec(spec); spec.loader.exec_module(P)


class PairingTests(unittest.TestCase):
    def test_whole_verbatim_proposition_only(self):
        self.assertEqual(set(P.HYPOTHESES), {'nda-17','nda-7','nda-3'})
        for h in P.HYPOTHESES.values():
            self.assertEqual(P.counterclaim(h), 'It is not the case that '+h)
            self.assertEqual(P.counterclaim(h)[len(P.PREFIX):].encode(), h.encode())
            self.assertTrue(P.counterclaim(h).endswith('.'))

    def test_unknown_and_changed_whitespace_fail(self):
        h = P.HYPOTHESES['nda-3']
        for x in [None, {}, 'Different proposition.', h+' ', h.lower(), h[:-1]]:
            with self.assertRaises(ValueError): P.counterclaim(x)

    def test_mass_and_label_swap_equivariance(self):
        examples = [dict(zip(P.ORDER,x)) for x in
                    [(1,0,0),(0,1,0),(0,0,1),(.6,.1,.3),(.2,.5,.3)]]
        for p in examples:
            for q in examples:
                a,b = P.pool(p,q),P.pool(q,p)
                self.assertAlmostEqual(sum(a.values()),1.)
                self.assertTrue(all(0<=v<=1 for v in a.values()))
                for k in P.ORDER:self.assertAlmostEqual(a[k],b[P.MIRROR[k]])

    def test_neutral_is_not_contradiction(self):
        n = {'Entailment':0.,'Contradiction':0.,'NotMentioned':1.}
        self.assertEqual(P.pool(n,n),n)
        self.assertEqual(P.binary(n),{'Yes':0.,'No':1.})

    def test_conflict_is_uncertainty_not_neutral_relabel(self):
        e = {'Entailment':1.,'Contradiction':0.,'NotMentioned':0.}
        self.assertEqual(P.pool(e,e),{'Entailment':.5,'Contradiction':.5,'NotMentioned':0.})
        self.assertTrue(P.receipt(e,e)['both_views_predict_entailment'])

    def test_explicit_counterclaim_support_can_change_decision(self):
        p = {'Entailment':.01,'Contradiction':.10,'NotMentioned':.89}
        q = {'Entailment':.95,'Contradiction':.01,'NotMentioned':.04}
        self.assertEqual(P.prediction(p),'NotMentioned')
        self.assertEqual(P.prediction(P.pool(p,q)),'Contradiction')

    def test_invalid_probability_vectors_rejected(self):
        for x in [{}, {'Entailment':1.}, dict(zip(P.ORDER,[True,0,0])),
                  dict(zip(P.ORDER,[float('nan'),0,1])),dict(zip(P.ORDER,[-1,1,1])),
                  dict(zip(P.ORDER,[.8,.8,.8]))]:
            with self.assertRaises(ValueError):P.checked(x)


if __name__=='__main__':unittest.main()
