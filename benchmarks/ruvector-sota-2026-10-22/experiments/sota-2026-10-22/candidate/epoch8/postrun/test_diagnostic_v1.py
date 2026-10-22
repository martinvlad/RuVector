"""Pure synthetic checks for the saved-output analyzer, without model modules."""
import importlib.util
import json
import math
from pathlib import Path
import tempfile
import unittest


def load(filename):
    path = Path(__file__).with_name(filename)
    spec = importlib.util.spec_from_file_location(path.stem, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


D = load('build_diagnostic_v1.py')
F = load('build_findings_v1.py')


class SavedReplayTests(unittest.TestCase):
    def test_binary_mapping_preserves_neutral_mass(self):
        distribution = D.binary({'Entailment': .2, 'Contradiction': .1, 'NotMentioned': .7})
        self.assertAlmostEqual(distribution['Yes'], .2)
        self.assertAlmostEqual(distribution['No'], .8)

    def test_exact_binary_tie_is_no(self):
        self.assertEqual(D.decision({'Yes': .5, 'No': .5}), 'No')

    def test_nonfinite_or_nonprobability_rejected(self):
        for p in ({'Yes': math.nan, 'No': .5}, {'Yes': .7, 'No': .7}, {'Yes': -1., 'No': 2.}):
            with self.assertRaises(ValueError):
                D.score(p, 'No')

    def test_train_uses_frozen_saved_replay_without_fitting(self):
        trace = {'raw_threeway_probabilities': {'Entailment': .2, 'Contradiction': .1, 'NotMentioned': .7},
                 'typed_head_state': 'TRAIN_COLLECTION', 'typed_head_canonical_logits': [math.log(.2), math.log(.1), math.log(.7)]}
        row = {'id': 'synthetic', 'source_group': 'group', 'evaluation': {'gold': 'No', 'original_threeway_label': 'NotMentioned'},
               'provenance': {'hypothesis_id': 'synthetic'},
               'response': {'diagnostics': {'decision': {'arms': {a: {'decoding': trace} for a in D.SELECTORS}}}}}
        trained = {'Entailment': .6, 'Contradiction': .1, 'NotMentioned': .3}
        replay = [{'id': 'synthetic', 'arm': a, 'threeway_probabilities': trained} for a in D.SELECTORS]
        case = D.cases_for([row], replay)[0]
        for views in case['selectors'].values():
            self.assertEqual(views['trained_head']['binary']['predicted'], 'Yes')
            self.assertEqual(views['fixed_raw_threeway']['binary']['predicted'], 'No')
            self.assertEqual(views['historical_discarded_neutral']['binary']['predicted'], 'Yes')
            self.assertIsNone(views['historical_discarded_neutral']['threeway'])

    def test_nonterminal_refuses_before_label_or_record_access(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            study = root / (D.PREFIX + 'epoch8')
            study.mkdir(parents=True)
            (study / 'study-completion.json').write_text(json.dumps({'finished_at': None}))
            with self.assertRaisesRegex(ValueError, 'terminal closed'):
                D.build(root, root)

    def test_findings_reject_other_diagnostic_identity(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / 'different.json'
            path.write_text('{}')
            with self.assertRaisesRegex(ValueError, 'exact pinned'):
                F.build(path)


if __name__ == '__main__':
    unittest.main()
