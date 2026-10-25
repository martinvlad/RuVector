"""Authored source-only fixtures; fake tokenizer, no benchmark inputs or ML/native."""
import importlib.util
import json
from pathlib import Path
import re
import subprocess
import sys
from types import SimpleNamespace
import unittest

HERE = Path(__file__).resolve().parent


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


Q = load('e35_pure_query', HERE / 'query.py')
S = load('e35_pure_source_context', HERE / 'source_context.py')
P = load('e35_pure_disabled_proof', HERE / 'proof.py')
E = load('e35_pure_evidence', HERE / 'evidence.py')
M = load('e35_pure_readout', HERE / 'model.py')


class FakeTokenizer:
    """Wholly authored word-count/offset substitute, never a model tokenizer."""
    def encode(self, text, pair=None, add_special_tokens=True):
        matches = list(re.finditer(r'\S+', text))
        count = len(matches) + (2 if add_special_tokens else 0)
        if pair is not None:
            count += len(re.findall(r'\S+', pair)) + 1
        return SimpleNamespace(ids=list(range(count)), offsets=[m.span() for m in matches])


class PolicyFixtures(unittest.TestCase):
    def setUp(self):
        self.t = FakeTokenizer()

    def partition(self, document):
        return S.partition(document, self.t, self.t)

    def test_original_hypothesis_unchanged_including_unicode_whitespace_negation(self):
        h = '  Café MAY not disclose 1,250.75 dollars.\nOriginal text.  '
        receipt = Q.query(h)
        self.assertEqual(receipt['query'], h)
        self.assertEqual(receipt['original_query'], h)
        self.assertFalse(receipt['expansion_applied'])
        self.assertEqual(receipt['query_sha256'], receipt['original_hypothesis_sha256'])
        self.assertEqual(set(receipt), {'schema_version','epoch','policy','query_source_sha256',
            'query_policy_sha256','original_hypothesis_sha256','original_query','query',
            'original_query_sha256','query_sha256','expansion_applied'})
        for bad in (None, '', '  ', 'x\0y'):
            with self.assertRaises(ValueError): Q.query(bad)

    def test_hybrid_first_native_complement_is_distinct_group_and_keeps_order(self):
        units = [{'id':0,'group_id':0},{'id':1,'group_id':0},
                 {'id':2,'group_id':1},{'id':3,'group_id':2}]
        ranking, receipt = Q.hybrid_order([1,0,3,2], [0,1,2,3], units)
        self.assertEqual(ranking, [1,2,0,3])
        self.assertEqual(receipt['lexical_anchor_group_id'], 0)
        self.assertEqual(receipt['native_complement_unit_id'], 2)
        self.assertEqual(receipt['native_complement_group_id'], 1)
        self.assertFalse(receipt['single_group_degenerate'])

    def test_hybrid_lexical_anchor_outside_actual_top40_is_kept(self):
        units = [{'id':i,'group_id':i} for i in range(50)]
        lexical = [45] + [i for i in range(50) if i != 45]
        ranking, receipt = Q.hybrid_order(lexical, list(range(40)), units)
        self.assertEqual(ranking[:2], [45,0])
        self.assertEqual(len(ranking), 40)
        self.assertNotIn(39, ranking)
        self.assertEqual(receipt['native_complement_unit_id'], 0)

    def test_single_group_is_disclosed_not_a_fallback_for_multi_group_source(self):
        units = [{'id':0,'group_id':0},{'id':1,'group_id':0}]
        ranking, receipt = Q.hybrid_order([1,0], [0,1], units)
        self.assertEqual(ranking, [1,0])
        self.assertTrue(receipt['single_group_degenerate'])
        self.assertIsNone(receipt['native_complement_unit_id'])
        missing = [{'id':i,'group_id':0 if i < 40 else 1} for i in range(41)]
        with self.assertRaisesRegex(ValueError, 'No distinct native complement'):
            Q.hybrid_order(list(range(41)), list(range(40)), missing)

    def test_malformed_rankings_fail_closed(self):
        units = [{'id':0,'group_id':0},{'id':1,'group_id':1}]
        for lexical, native in [([0,0],[0,1]),([0],[0,1]),([0,1],[0,0]),
                                ([0,1],[0]),([0,1],[0,2]),([0,1],[0,True])]:
            with self.assertRaises(ValueError): Q.hybrid_order(lexical, native, units)

    def test_packer_keeps_two_groups_then_optional_definition_only(self):
        document = ('First sales fact is 2019.\n\nSecond accounting fact is 2020.\n\n'
                    '"Confidential Information" means unreleased designs.\n\n'
                    'Fourth material fact is 2021.')
        units = self.partition(document)
        self.assertEqual(len(units), 4)
        premise, receipt = S.pack(document, units, [1,0,3,2], 'A whole claim.', self.t,
                                  rank_depth=4, prelude=S.select_prelude(document, units, self.t))
        self.assertEqual(receipt['mandatory_ranked_group_ids'], [1,0])
        self.assertEqual(receipt['optional_definition_group_ids_admitted'], [2])
        self.assertEqual(receipt['selected_group_ids_admission_order'], [1,0,2])
        self.assertNotIn(3, receipt['selected_chunk_ids_rank_order'])
        self.assertNotIn('Fourth', premise)
        self.assertEqual(receipt['additional_neighbor_unit_ids_inspected'], [])
        provenance = E.provenance(document, premise, receipt)
        self.assertEqual(provenance['numeric_literals_retained'], 2)
        self.assertEqual(provenance['numeric_literals_omitted'], 1)
        self.assertFalse(provenance['semantic_decision_override'])

    def test_qualifiers_stay_whole_even_when_spanning_multiple_units(self):
        document = ('The recipient may disclose records. However, only public records may be disclosed.\n\n'
                    'Other documents shall remain confidential.')
        units = self.partition(document)
        catalog = S.groups(document, units)
        self.assertEqual(len(catalog), 2)
        self.assertEqual(len(catalog[0]['sentence_ids']), 2)
        ranking = list(reversed(range(len(units))))
        premise, receipt = S.pack(document, units, ranking, 'The recipient may disclose.', self.t,
                                  rank_depth=len(units))
        self.assertIn('However, only public records', premise)
        self.assertEqual(set(receipt['selected_chunk_ids_rank_order']), set(range(len(units))))
        self.assertTrue(receipt['all_selected_groups_complete'])

    def test_optional_definition_may_be_omitted_but_mandatory_groups_never_dropped(self):
        document = (' '.join(['alpha'] * 225) + '.\n\n' + ' '.join(['beta'] * 225) + '.\n\n'
                    '"Confidential Information" means ' + ' '.join(['gamma'] * 100) + '.')
        units = self.partition(document)
        groups = S.groups(document, units)
        ranking = [groups[0]['unit_ids'][0],groups[1]['unit_ids'][0]]
        ranking += [i for i in range(len(units)) if i not in ranking]
        premise, receipt = S.pack(document, units, ranking, 'Whole claim.', self.t, rank_depth=len(units))
        self.assertEqual(receipt['mandatory_ranked_group_ids'], [0,1])
        self.assertEqual(receipt['optional_definition_group_ids_admitted'], [])
        self.assertNotIn('gamma', premise)
        self.assertEqual(receipt['selected_group_ids_admission_order'], [0,1])
        self.assertFalse(receipt['packing_attempts'][-1]['accepted'])

    def test_oversize_mandatory_groups_fail_without_silent_clipping_or_fallback(self):
        document = ' '.join(['alpha'] * 300) + '.\n\n' + ' '.join(['beta'] * 300) + '.'
        units = self.partition(document)
        groups = S.groups(document, units)
        ranking = [groups[0]['unit_ids'][0],groups[1]['unit_ids'][0]]
        ranking += [i for i in range(len(units)) if i not in ranking]
        with self.assertRaisesRegex(ValueError, 'Mandatory whole source groups exceed512'):
            S.pack(document, units, ranking, 'Whole claim.', self.t, rank_depth=len(units))

    def test_single_source_group_packer_discloses_degenerate(self):
        document = 'One complete source statement 2024.'
        units = self.partition(document)
        premise, receipt = S.pack(document, units, list(range(len(units))), 'One claim.', self.t,
                                  rank_depth=len(units))
        self.assertEqual(premise, document)
        self.assertTrue(receipt['single_group_degenerate'])
        self.assertEqual(receipt['mandatory_ranked_group_ids'], [0])

    def test_disabled_proof_preserves_native_tie_label_and_exact_probabilities(self):
        reader = M.decisions([0,4,4])
        self.assertEqual(reader['native_typed_argmax'], 'NotMentioned')
        result = P.decide('source', 'source', 'claim', [[0,6]], reader, enabled=False)
        self.assertEqual(result['final_typed_argmax'], 'NotMentioned')
        self.assertEqual(result['final_probabilities_E_C_N'], reader['probabilities_E_C_N'])
        self.assertIsNone(result['certificate'])
        self.assertFalse(result['semantic_decision_override'])
        with self.assertRaises(ValueError): P.decide('s','s','c',[[0,1]],reader,enabled=True)

    def test_fixed_operation_counts_and_no_ML_imports(self):
        worker = load('e35_pure_counter_worker', HERE / 'worker.py')
        full, short = worker.expected_counters(True), worker.expected_counters(False)
        self.assertEqual(full['native_queries_completed'], 12)
        self.assertEqual(short['native_queries_completed'], 12)
        self.assertEqual(full['NLI_forward_calls_completed'], 48)
        self.assertEqual(short['NLI_forward_calls_completed'], 48)
        self.assertEqual(full['native_index_initializations_completed'], 12)
        self.assertFalse(any(name in sys.modules for name in
            ('torch','transformers','numpy','onnxruntime','tokenizers')))

    def test_all_native_guard_identity_checks_bind_current_Python_owner(self):
        worker = load('e35_pure_owner_binding_worker', HERE / 'worker.py')
        c = worker.C
        node = (HERE / 'runtime/node_guard.cjs').read_text()
        for literal in (f'value.owner_pid!=={c.OWNER_PID}',
                f'value.owner_startticks!=={c.OWNER_TICKS}',
                f'/proc/{c.OWNER_PID}/fd/{c.LOCK_FD}',
                f'/proc/{c.OWNER_PID}/stat', f'/proc/{c.OWNER_PID}/ns/pid',
                f'FLOCK,ADVISORY,WRITE,{c.OWNER_PID}',
                f'owner.pid!=={c.OWNER_PID}', f'owner.startticks!=={c.OWNER_TICKS}',
                f'owner.expires_unix!=={c.OWNER_EXPIRY}',
                f'Number(proc[19])!=={c.OWNER_TICKS}'):
            self.assertIn(literal, node)
        self.assertNotRegex(node, r'\b(?:100799|22293151|1792910029\.5943027|96223|21488832|1792901986\.405032)\b')


if __name__ == '__main__':
    unittest.main(verbosity=2)
