"""Pure source/arithmetic and generic owned-process fixtures; never load models."""
import importlib.util
import fcntl
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time
import unittest
from unittest import mock

HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE))
import common as C
import launch as L
import worker as W


class SourceAndMath(unittest.TestCase):
    def test_exact_published_three_canary_identities_and_vectors(self):
        rows=C.fixtures({'spec_path':C.SPEC_PATH,'fixtures_path':C.FIXTURES_PATH})
        bundle,reference=C.engineering_vectors(rows)
        self.assertEqual([v[:5]for v in bundle['vectors']],[[1,1,0,0,0],[1,1,1,0,0],[0,0,0,1,1]])
        self.assertTrue(all(len(v)==384 and v[5:]==[0]*379 for v in bundle['vectors']+bundle['query_vectors']))
        self.assertEqual(reference['cosine_order'],[[0,1,2]]*3)
        self.assertEqual(reference['lexical_order'],[[0,1,2]]*3)
        self.assertFalse(reference['native_selection_affects_NLI'])

    def test_lexical_all_ascii_words_and_declared_order_tie(self):
        rows=[{'premise':'same extra extra','hypothesis':'same'},
              {'premise':'same','hypothesis':'same'},{'premise':'unrelated','hypothesis':'same'}]
        # Use the fixed nonzero engineering vocabulary while testing the lexical tie.
        for row in rows:row['premise']+=' lamp';row['hypothesis']+=' lamp'
        _,reference=C.engineering_vectors(rows)
        self.assertEqual(reference['lexical_order'],[[0,1,2]]*3)

    def test_actual_unchanged_full_inherited_source_verifier_checks_pin_and_limit(self):
        verifier=C.inherited_verifier()
        plan={'pins':[{'path':C.NATIVE_SCRIPT,'sha256':C.NATIVE_SCRIPT_SHA}],'limits':dict(C.LIMITS)}
        verifier.verify_plan(plan)
        plan['pins'][0]['sha256']='0'*64
        with self.assertRaisesRegex(ValueError,'Frozen identity changed'):verifier.verify_plan(plan)
        plan['pins'][0]['sha256']=C.NATIVE_SCRIPT_SHA;plan['limits']['seconds_per_decision']=31
        with self.assertRaisesRegex(ValueError,'Execution limit invalid'):verifier.verify_plan(plan)

    def test_wrong_boolean_budget_cannot_reach_verifier_or_import_runtime(self):
        value={'schema_version':1,'epoch':19,'source_checkpoint':C.SOURCE,'study_id':C.STUDY_ID,'limits':dict(C.LIMITS)}
        value['limits']['worker_attempts']=True
        with tempfile.TemporaryDirectory()as temp:
            file=Path(temp)/'SOURCE_ONLY_FIXTURE.json';file.write_text(json.dumps(value))
            with mock.patch.object(C,'inherited_verifier')as verifier:
                with self.assertRaisesRegex(ValueError,'Exact engineering'):C.require_plan(file)
                verifier.assert_not_called()

    def test_safe_regular_path_refuses_ancestor_or_dangling_links(self):
        with tempfile.TemporaryDirectory()as temp:
            root=Path(temp);(root/'real').mkdir();(root/'real/source.json').write_text('{}')
            (root/'alias').symlink_to(root/'real',target_is_directory=True);(root/'dangling.json').symlink_to(root/'absent')
            for name in ('alias/source.json','dangling.json','../outside','a\\b'):
                with self.assertRaises(ValueError):C.checked(name,root)

    def test_importing_worker_for_asset_metadata_does_not_import_neural_frameworks(self):
        self.assertNotIn('torch',sys.modules);self.assertNotIn('transformers',sys.modules)
        self.assertTrue(callable(W.verify_assets))


class OwnedProcess(unittest.TestCase):
    def test_admission_rejects_unrelated_lock_scope_before_other_receipts(self):
        with tempfile.TemporaryDirectory()as temp:
            study=Path(temp)
            with mock.patch.object(C,'STUDY',study),mock.patch.object(C,'read',return_value={'lock_path':str(study/'UNRELATED.lock')}):
                with self.assertRaisesRegex(ValueError,'work-lock scope'):C.verify_admission(study/'NATIVE_ADMISSION.json','0'*64)

    def test_actual_kernel_flock_owner_identity_and_stale_or_unlocked_rejection(self):
        with tempfile.TemporaryDirectory()as temp:
            file=Path(temp)/'GENERIC_ENGINEERING_ONLY.lock'
            with file.open('w')as owned:
                fcntl.flock(owned,fcntl.LOCK_EX|fcntl.LOCK_NB)
                ticks=int(Path('/proc/self/stat').read_text().rsplit(')',1)[1].split()[19])
                identity={'owner_pid':os.getpid(),'owner_start_ticks':ticks,'lock_path':str(file),'lock_inode':file.stat().st_ino}
                C.verify_owner_lock(identity)
                for field in ('owner_start_ticks','lock_inode'):
                    stale=dict(identity);stale[field]+=1
                    with self.assertRaises(ValueError):C.verify_owner_lock(stale)
                fcntl.flock(owned,fcntl.LOCK_UN)
                with self.assertRaisesRegex(ValueError,'no active kernel'):C.verify_owner_lock(identity)

    def plan(self,temp):
        root=Path(temp);study=root/'study';study.mkdir();file=root/'plan.json';file.write_text('{"generic":true}')
        return root,study,file,{'inference_python':str(Path(sys.executable).absolute()),'lease_expires_unix':time.time()+1000}

    def test_failed_popen_consumes_only_slot_without_claiming_worker_start(self):
        with tempfile.TemporaryDirectory()as temp:
            root,study,file,plan=self.plan(temp)
            with mock.patch.object(C,'STUDY',study),mock.patch.object(C,'ROOT',root),mock.patch.object(C,'require_plan',return_value=plan),mock.patch.object(C,'verify_admission'),mock.patch.object(L.subprocess,'Popen',side_effect=OSError('GENERIC_EXPECTED_POPEN_FAILURE')):
                with self.assertRaises(RuntimeError):L.launch(file,root/'admission.json')
            report=C.read(study/'runs/qualification/execution.json')
            self.assertEqual(report['qualification_worker_attempts'],1);self.assertEqual(report['verified_worker_starts'],0)
            self.assertIsNone(report['native_helper_pid']);self.assertEqual(report['allowed_further_qualification_attempts'],0)
            self.assertTrue((study/'runs/qualification/popen-attempt.json').exists())

    def test_pid_receipt_failure_cleans_actual_generic_owned_python_child(self):
        with tempfile.TemporaryDirectory()as temp:
            root,study,file,plan=self.plan(temp);original_write=C.write_new;original_popen=subprocess.Popen;children=[]
            def spawn(*args,**kwargs):
                child=original_popen([sys.executable,'-B','-c','import time;time.sleep(20)'],start_new_session=True)
                children.append(child);return child
            def write(path,value):
                if Path(path).name=='attempt.json':raise OSError('GENERIC_PID_RECEIPT_FAILURE')
                return original_write(path,value)
            try:
                with mock.patch.object(C,'STUDY',study),mock.patch.object(C,'ROOT',root),mock.patch.object(C,'require_plan',return_value=plan),mock.patch.object(C,'verify_admission'),mock.patch.object(C,'write_new',side_effect=write),mock.patch.object(L.subprocess,'Popen',side_effect=spawn):
                    with self.assertRaises(RuntimeError):L.launch(file,root/'admission.json')
                report=C.read(study/'runs/qualification/execution.json')
                self.assertEqual(report['verified_worker_starts'],1)
                self.assertTrue(report['cleanup']['worker_exited']);self.assertTrue(report['cleanup']['process_group_empty'])
                self.assertEqual(report['cleanup']['owned_live_pids'],[])
            finally:
                for child in children:
                    if child.poll()is None:child.kill()
                    child.wait()


if __name__=='__main__':unittest.main()
