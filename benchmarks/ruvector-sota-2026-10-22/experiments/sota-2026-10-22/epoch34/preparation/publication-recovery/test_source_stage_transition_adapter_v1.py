"""Pure transition/hash fixtures. Never invokes adapter main or stage.prepare."""
from __future__ import annotations
import sys
sys.dont_write_bytecode=True
import copy
import hashlib
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest

OWN=Path('/workspace/ruvector-e34-publication-impl')
spec=importlib.util.spec_from_file_location('outside_source_transition_adapter_fixture',OWN/'source-stage-transition-adapter-v1.py')
A=importlib.util.module_from_spec(spec);spec.loader.exec_module(A)


class AdapterFixtures(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.stage=A.load_frozen_stager()  # hash-bound stdlib-only module imports
        cls.baseline=A.parse(A.ROOT/'kit/CONTINUATION.json')
        cls.planning=A.parse(A.ROOT/'controls-lease/CONTINUATION.json')
        cls.source=A.parse(A.ROOT/'controls-source/CONTINUATION.json')
        cls.mutable=cls.stage.MUTABLE.copy()

    def bridge(self, **changes):
        return A.SourcePriorityBridge(changes.get('original',self.stage.preserve_history),
            changes.get('baseline',self.baseline),changes.get('planning',self.planning),
            changes.get('source',self.source),changes.get('mutable',self.mutable))

    def test_original_BASE_refusal_is_reproduced_without_staging(self):
        with self.assertRaisesRegex(ValueError,'Historical continuation field changed: next_research_priority'):
            self.stage.preserve_history(self.baseline,self.source,self.mutable)

    def test_exact_approved_transition_then_original_parent_passes(self):
        bridge=self.bridge();bridge(self.baseline,self.source,self.mutable);bridge(self.planning,self.source,self.mutable)
        self.assertEqual(bridge.finish()['BASE_priority_exceptions'],1)
        self.assertEqual(bridge.finish()['normal_parent_comparisons'],1)
        self.assertEqual(self.stage.MUTABLE,self.mutable)
        self.assertNotIn(A.PRIORITY,self.stage.MUTABLE)

    def test_only_first_call_receives_one_additional_field(self):
        seen=[]
        def original(before,after,mutable):
            seen.append(mutable.copy());self.stage.preserve_history(before,after,mutable)
        bridge=self.bridge(original=original);bridge(self.baseline,self.source,self.mutable);bridge(self.planning,self.source,self.mutable)
        self.assertEqual(seen,[self.mutable|{A.PRIORITY},self.mutable]);bridge.finish()

    def test_unrelated_BASE_champion_change_still_fails(self):
        bad=copy.deepcopy(self.source);bad['champion']='tampered'
        bridge=self.bridge(source=bad)
        with self.assertRaisesRegex(ValueError,'champion'):bridge(self.baseline,bad,self.mutable)
        self.assertEqual(bridge.trace,[])

    def test_unrelated_BASE_rejection_ledger_change_still_fails(self):
        bad=copy.deepcopy(self.source);bad['rejection_ledger']={'path':'invented'}
        bridge=self.bridge(source=bad)
        with self.assertRaisesRegex(ValueError,'rejection_ledger'):bridge(self.baseline,bad,self.mutable)

    def test_normal_parent_check_is_not_relaxed(self):
        bad=copy.deepcopy(self.planning);bad['champion']='different parent champion'
        bridge=self.bridge(planning=bad);bridge(self.baseline,self.source,self.mutable)
        with self.assertRaisesRegex(ValueError,'champion'):bridge(bad,self.source,self.mutable)

    def test_planning_priority_drift_is_refused(self):
        bad=copy.deepcopy(self.planning);bad[A.PRIORITY]='unapproved new choice'
        with self.assertRaisesRegex(ValueError,'exact authorized planning priority'):self.bridge(planning=bad)

    def test_SOURCE_priority_drift_is_refused(self):
        bad=copy.deepcopy(self.source);bad[A.PRIORITY]='unapproved new choice'
        with self.assertRaisesRegex(ValueError,'exact authorized planning priority'):self.bridge(source=bad)

    def test_wrong_BASE_snapshot_is_refused(self):
        bad=copy.deepcopy(self.baseline);bad['goal_met']=True;bridge=self.bridge()
        with self.assertRaisesRegex(ValueError,'exact hash-bound BASE'):bridge(bad,self.source,self.mutable)

    def test_typed_snapshot_equality_rejects_bool_integer_alias(self):
        bad=copy.deepcopy(self.baseline);bad['goal_met']=0;bridge=self.bridge()
        with self.assertRaisesRegex(ValueError,'exact hash-bound BASE'):bridge(bad,self.source,self.mutable)

    def test_wrong_SOURCE_snapshot_is_refused(self):
        bad=copy.deepcopy(self.source);bad['epoch34_unapproved']='extra';bridge=self.bridge()
        with self.assertRaisesRegex(ValueError,'exact hash-bound SOURCE'):bridge(self.baseline,bad,self.mutable)

    def test_wrong_call_order_is_refused(self):
        bridge=self.bridge()
        with self.assertRaisesRegex(ValueError,'First comparison'):bridge(self.planning,self.source,self.mutable)

    def test_extra_history_call_is_refused(self):
        bridge=self.bridge();bridge(self.baseline,self.source,self.mutable);bridge(self.planning,self.source,self.mutable)
        with self.assertRaisesRegex(ValueError,'Unexpected extra'):bridge(self.planning,self.source,self.mutable)

    def test_missing_normal_parent_comparison_cannot_finish(self):
        bridge=self.bridge();bridge(self.baseline,self.source,self.mutable)
        with self.assertRaisesRegex(ValueError,'Exactly one BASE exception'):bridge.finish()

    def test_preextended_mutable_is_refused(self):
        with self.assertRaisesRegex(ValueError,'original SOURCE mutable'):self.bridge(mutable=self.mutable|{A.PRIORITY})
        bridge=self.bridge()
        with self.assertRaisesRegex(ValueError,'SOURCE mutable set changed'):bridge(self.baseline,self.source,self.mutable|{'champion'})

    def test_fixed_SOURCE_parent_and_output_are_not_cli_selectable(self):
        args=A.fixed_arguments('a'*40)
        self.assertEqual(args.phase,'source');self.assertEqual(args.parent,A.PARENT)
        self.assertEqual(args.out,A.ROOT/'stage-source');self.assertEqual(args.controls,A.ROOT/'controls-source')
        self.assertEqual(args.priorcontrols,A.ROOT/'controls-lease')

    def test_main_is_format_checked_but_not_a_CAS_condition(self):
        self.assertEqual(A.fixed_arguments('0'*40).expected_main,'0'*40)
        with self.assertRaises(ValueError):A.fixed_arguments('main')

    def test_all_frozen_metadata_input_hashes_match(self):
        for path,expected in A.INPUTS.items():A.file_ref(path,expected)
        for name,expected in A.FROZEN_MODULES.items():A.file_ref(A.PUB/(name+'.py'),expected)

    def test_wrong_hash_or_symlink_is_refused(self):
        with tempfile.TemporaryDirectory(prefix='adapter-fixture-',dir=OWN) as directory:
            p=Path(directory)/'fixture.json';p.write_bytes(b'{}')
            with self.assertRaisesRegex(ValueError,'Pinned byte identity'):A.file_ref(p,(2,'0'*64))
            link=Path(directory)/'alias.json';link.symlink_to(p)
            with self.assertRaisesRegex(ValueError,'non-symlink'):A.file_ref(link)


if __name__=='__main__':
    unittest.main()
