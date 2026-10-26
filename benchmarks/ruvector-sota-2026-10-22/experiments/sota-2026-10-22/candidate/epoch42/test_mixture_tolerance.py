"""Pure precision-boundary regression for the prospectively fixed1e-12 gate."""
import importlib.util
import math
from pathlib import Path
import unittest

spec=importlib.util.spec_from_file_location('e42_mixture_precision',Path(__file__).with_name('mixture.py'))
M=importlib.util.module_from_spec(spec);spec.loader.exec_module(M)


class Precision(unittest.TestCase):
    def test_reject_between_old_and_fixed_tolerance(self):
        row=[math.log(.5+2e-11),math.log(.3),math.log(.2)]
        with self.assertRaisesRegex(ValueError,'UNNORMALIZED'):M.two_window_mixture([row,row])

    def test_valid_roundoff_and_unclipped_tail(self):
        row=[math.log(.5+2e-14),math.log(.3),math.log(.2)]
        result=M.two_window_mixture([row,row])
        self.assertLess(abs(sum(result['probabilities_N_E_C'])-1),1e-12)
        tail=M.two_window_mixture([[0.,-1200.,-1400.]]*2)
        self.assertEqual(tail['log_probabilities_N_E_C'][2],-1400.)


if __name__=='__main__':unittest.main()
