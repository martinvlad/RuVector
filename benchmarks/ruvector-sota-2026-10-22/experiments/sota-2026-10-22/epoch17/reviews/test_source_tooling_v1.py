"""Generic metadata-only gate fixtures; never data or native/model execution."""
from __future__ import annotations
import hashlib
import contextlib
import io
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest

HERE=Path(__file__).resolve().parent
EPOCH=HERE.parent

def put(path,value):
    path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(value))

def load(name):
    spec=importlib.util.spec_from_file_location('review_'+name,EPOCH/(name+'.py'))
    module=importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module

def fixture(module,root):
    module.ROOT=root
    module.S=root/'experiments/sota-2026-10-22'
    module.E=module.S/'epoch17'
    module.E.mkdir(parents=True)
    return module.S,module.E

def valid_handoff(root,s):
    policy=s/'audit/epoch17/acceptance-contract-v1.json'
    put(policy,{'generic_policy_fixture':True})
    checker=s/'audit/epoch17/checker.py'
    checker.write_text('GENERIC_CHECKER_FIXTURE=True\n')
    candidate=s/'candidate/epoch17/candidate.py'
    candidate.parent.mkdir(parents=True)
    candidate.write_text('GENERIC_CANDIDATE_FIXTURE=True\n')
    row=lambda p:{'path':str(p.relative_to(root)),'bytes':p.stat().st_size,
        'sha256':hashlib.sha256(p.read_bytes()).hexdigest()}
    handoff={'checks_passed':True,
        'source_and_checker_ready_for_prelabel_freeze':True,
        'source_immutable_head':'cec9a7bbdc8c4ced83e5d1b826bce67da18339df',
        'native_execution_admitted':False,'auditor_model_native_fit_paid_GPU_calls':0,
        'new_role_annotation_choices_read':0,
        'policy_sha256':row(policy)['sha256'],
        'checker_source_and_tests':[row(checker)],
        'reviewed_candidate_and_role_sources':[row(candidate)]}
    put(s/'audit/epoch17/code-handoff-v1.json',handoff)
    put(root.parent/'kit/CHECKPOINT_MANIFEST.json',{'project_files':[]})
    return handoff,checker,candidate,policy

class MetadataGates(unittest.TestCase):
    def test_publication_symlinks_rejected_before_read(self):
        for kind in ('file','directory'):
            with self.subTest(kind=kind),tempfile.TemporaryDirectory(dir=HERE)as temporary:
                module=load('make_source_closure_inputs')
                root=Path(temporary)/'project';s,e=fixture(module,root)
                kit=root.parent/'kit'
                for name in ('CHECKPOINT_MANIFEST.json','KIT_MANIFEST.json'):
                    put(kit/name,{'project_files':[]})
                put(kit/'BASE_PUBLIC_MANIFEST.json',{'files':[]})
                put(kit/'BASE_DOWNLOADS.json',{'paths':[]})
                candidate=s/'candidate/epoch17';candidate.mkdir(parents=True)
                target=root.parent/'outside'
                if kind=='file':target.write_text('GENERIC_OUTSIDE_FIXTURE\n')
                else:
                    target.mkdir()
                    (target/'payload.py').write_text('GENERIC_OUTSIDE_FIXTURE\n')
                (candidate/'alias').symlink_to(target,target_is_directory=kind=='directory')
                with self.assertRaises((AssertionError,ValueError)):module.main()
                self.assertFalse((e/'declared-public.json').exists())

    def test_stale_independent_handoff_rejected(self):
        module=load('freeze_sources')
        with tempfile.TemporaryDirectory(dir=HERE)as temporary:
            root=Path(temporary)/'project';s,e=fixture(module,root)
            _,checker,_,_=valid_handoff(root,s)
            checker.write_text('CHANGED_AFTER_HANDOFF\n')
            with self.assertRaises((AssertionError,ValueError,FileNotFoundError)):
                module.main()
            self.assertFalse((e/'candidate-source-freeze.json').exists())

    def test_current_independent_handoff_accepted(self):
        module=load('freeze_sources')
        with tempfile.TemporaryDirectory(dir=HERE)as temporary:
            root=Path(temporary)/'project';s,e=fixture(module,root)
            valid_handoff(root,s)
            with contextlib.redirect_stdout(io.StringIO()):module.main()
            self.assertEqual(json.loads((e/'candidate-source-freeze.json').read_text())['epoch'],17)

    def test_changed_reviewed_candidate_rejected(self):
        module=load('freeze_sources')
        with tempfile.TemporaryDirectory(dir=HERE)as temporary:
            root=Path(temporary)/'project';s,e=fixture(module,root)
            _,_,candidate,_=valid_handoff(root,s)
            candidate.write_text('CHANGED_AFTER_REVIEW\n')
            with self.assertRaises((AssertionError,ValueError)):module.main()
            self.assertFalse((e/'candidate-source-freeze.json').exists())

    def test_changed_reviewed_policy_rejected(self):
        module=load('freeze_sources')
        with tempfile.TemporaryDirectory(dir=HERE)as temporary:
            root=Path(temporary)/'project';s,e=fixture(module,root)
            _,_,_,policy=valid_handoff(root,s)
            put(policy,{'changed_after_review':True})
            with self.assertRaises((AssertionError,ValueError)):module.main()
            self.assertFalse((e/'candidate-source-freeze.json').exists())

    def test_failed_capacity_rejected_before_plan_assembly(self):
        module=load('freeze_study')
        with tempfile.TemporaryDirectory(dir=HERE)as temporary:
            root=Path(temporary)/'project';s,e=fixture(module,root)
            frozen=e/'candidate-source-freeze.json'
            put(frozen,{'files':[]})
            transfer=s/'legal-transfer/epoch17'
            transfer.mkdir(parents=True)
            (transfer/'development24.jsonl').write_text('generic fixture; not a benchmark row\n')
            put(transfer/'dev-materialization.json',{
                'annotation_choices_projected':24,'other_role_annotation_choices_accessed':0,
                'root_source_freeze_sha256':hashlib.sha256(frozen.read_bytes()).hexdigest()})
            put(s/'audit/epoch17/context-capacity-independent-v1.json',{
                'checks_passed':False,'status':'INDEPENDENT_CAPACITY_FAIL',
                'phases':{'development':{'max_units':1},'confirmation':{'max_units':1}},
                'CONF_annotation_choices_read':0,
                'auditor_model_native_session_fit_paid_GPU_calls':0})
            # A bad report must fail the actual capacity guard rather than merely
            # continuing until a later, absent historical-plan file happens to fail.
            with self.assertRaises((AssertionError,ValueError)):
                module.main()
            self.assertFalse((e/'RESEARCH_PLAN.json').exists())

if __name__=='__main__':unittest.main(verbosity=2)
