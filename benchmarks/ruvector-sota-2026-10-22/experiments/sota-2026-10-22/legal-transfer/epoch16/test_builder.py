"""Pure policy tests only; artificial fixtures are not benchmark measurements."""
from pathlib import Path
import copy
import hashlib
import importlib.util
import json
import tempfile
import unittest
from unittest.mock import patch

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location('epoch16_role_builder', HERE/'build.py')
B = importlib.util.module_from_spec(spec)
spec.loader.exec_module(B)


class PolicyTests(unittest.TestCase):
    def test_exact_partition_and_role_rank_no_labels(self):
        plan, registry, selected = B.selection_metadata()
        self.assertEqual(len(selected), 16)
        self.assertEqual(len({r['document_id'] for r in selected}), 16)
        self.assertEqual([r['role'] for r in selected], ['dev']*8+['confirmation']*8)
        self.assertTrue({r['document_id'] for r in selected} <= set(registry['eligible_document_ids']))
        self.assertEqual(selected, B.selection_metadata()[2])

    def test_selection_cannot_open_source_or_annotations(self):
        with tempfile.TemporaryDirectory() as d:
            target = Path(d)
            for n in ['draw-plan.json', 'eligibility-manifest.json']:
                (target/n).write_bytes((HERE/n).read_bytes())
            with patch.object(B, 'HERE', target):
                result = B.select_only()
                self.assertFalse(result['source_or_annotation_choices_accessed'])
                self.assertEqual(sorted(x.name for x in target.iterdir()),
                                 ['document-selection.json', 'draw-plan.json', 'eligibility-manifest.json'])
                with self.assertRaises(FileExistsError): B.select_only()

    def test_overlap_registry_rejected_before_draw(self):
        plan, registry, selected = B.selection_metadata()
        bad = copy.deepcopy(registry)
        bad['eligible_document_ids'][0] = bad['excluded_document_ids'][0]
        with patch.object(B, 'read', side_effect=lambda p: plan if Path(p).name=='draw-plan.json' else bad):
            with self.assertRaises(ValueError): B.selection_metadata()

    def test_choice_projection_requires_role_and_authorization(self):
        with patch.object(B, 'validate_inputs', side_effect=AssertionError('Must not access choices')):
            with self.assertRaises(PermissionError): B.materialize('confirmation', None, None, None, None, False)
            with self.assertRaises(PermissionError): B.materialize('unknown', None, None, None, None, True)

    def test_bad_or_absent_freeze_rejected_before_source(self):
        with self.assertRaises(PermissionError): B.verify_source_freeze(None, None)
        with tempfile.TemporaryDirectory() as d:
            p = Path(d)/'freeze.json';p.write_text('{}')
            with self.assertRaises(PermissionError): B.verify_source_freeze(p, '0'*64)
            B.verify_source_freeze(p, hashlib.sha256(p.read_bytes()).hexdigest())

    def test_dev_projection_preserves_threeway_and_never_reads_conf_choices(self):
        class NoConfirmationChoices(dict):
            def __getitem__(self, k):
                if k == 'annotation_sets': raise AssertionError('CONF choice accessed during DEV projection')
                return super().__getitem__(k)
        docs, prepared = {}, []
        labels = ['Entailment', 'Contradiction', 'NotMentioned']
        for i in range(16):
            d = {'id':i, 'file_name':'artificial-engineering-fixture',
                 'annotation_sets':[{'annotations':{h:{'choice':labels[n]} for n,h in enumerate(B.HYPOTHESES)}}]}
            docs[i] = d if i<8 else NoConfirmationChoices(d)
            for h in B.HYPOTHESES:
                prepared.append({'selection':{'document_id':i,'document_rank':i,
                    'document_draw_key':'engineering','role':'dev' if i<8 else 'confirmation'},
                    'hypothesis_id':h,'input':{'state':'artificial engineering fixture','questions':{}},
                    'input_sha256':'engineering','normalized_input_sha256':'engineering',
                    'normalized_document_sha256':'engineering'})
        with tempfile.TemporaryDirectory() as d:
            target=Path(d);(target/'document-selection.json').write_text('{}')
            with patch.object(B,'HERE',target), patch.object(B,'validate_inputs',return_value=({},docs,prepared,{})):
                r=B.materialize('dev',None,None,None,'engineering-source-freeze',True)
                self.assertEqual(r['annotation_choices_projected'],24)
                rows=[json.loads(x) for x in (target/'development24.jsonl').read_text().splitlines()]
                self.assertEqual([x['evaluation']['original_threeway_label'] for x in rows[:3]],labels)
                self.assertEqual([x['evaluation']['gold'] for x in rows[:3]],['Yes','No','No'])
                self.assertFalse((target/'confirmation24.jsonl').exists())
                with self.assertRaises(FileExistsError): B.materialize('dev',None,None,None,'engineering-source-freeze',True)


if __name__ == '__main__': unittest.main()
