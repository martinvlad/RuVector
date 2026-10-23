"""Metadata-only source-freezer regressions, with no runtime imports/execution."""
from pathlib import Path
from types import SimpleNamespace
import hashlib, importlib.util, json, os, sys, tempfile, time, unittest
TARGET=Path(os.environ.get('E19_FREEZE_REVIEW_TARGET',str(Path(__file__).resolve().parents[1]/'preparation/build_plan.py')))
spec=importlib.util.spec_from_file_location('reviewed_build_plan',TARGET)
M=importlib.util.module_from_spec(spec);spec.loader.exec_module(M)
P=M.P
OLD=[P+'epoch18/reporting/SEMANTIC_PRECISION_QUALIFICATION_SPEC.json',P+'candidate/epoch17/model-assets.lock.json',P+'epoch17/preparation/python-wheel-identities.json',P+'epoch17/preparation/runtime-closure.json']
NEW=[P+'legal-transfer/epoch19/canaries.json',P+'epoch19/NATIVE_ENGINEERING_ADDENDUM.json',P+'audit/epoch19/protocol.json']
class Guards(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.scope=Path(self.tmp.name);self.root=self.scope/'project';self.kit=self.scope/'kit'
        self.root.mkdir();self.kit.mkdir()
        (self.scope/'owner.json').write_text(json.dumps({'pid':os.getpid(),'expires_unix':time.time()+5000}))
        old=OLD+[f'history/file{i:04}.txt'for i in range(2797-len(OLD))]
        rows=[]
        for name in old:
            p=self.root/name;p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes(b'{}\n')
            rows.append({'path':name,'bytes':3,'sha256':hashlib.sha256(b'{}\n').hexdigest()})
        for manifest,value in [('CHECKPOINT_MANIFEST.json',{'project_files':rows}),('KIT_MANIFEST.json',{'project_files':[]}),('BASE_PUBLIC_MANIFEST.json',{'files':[]}),('BASE_DOWNLOADS.json',{'paths':[]})]:
            (self.kit/manifest).write_text(json.dumps(value))
        for name in NEW:
            p=self.root/name;p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes(b'{}\n')
        self.args=SimpleNamespace(project=self.root,kit=self.kit,scope=self.scope)
        self.freeze=self.root/(P+'epoch19/candidate-source-freeze.json')
    def test_clean_plan_has_all_source_references(self):
        out=M.build(self.args)
        plan=json.loads((self.root/(P+'epoch19/plan.json')).read_text())
        refs={r['path']:r['sha256']for r in plan['pins']}
        for name in OLD+NEW:self.assertEqual(refs[name],M.digest(self.root/name))
        self.assertEqual(out['source_files'],2800)
    def test_controller_is_inside_freeze(self):
        name=P+'controller/epoch19/run.py';p=self.root/name;p.parent.mkdir(parents=True);p.write_text('pass\n')
        M.build(self.args)
        refs={r['path']for r in json.loads(self.freeze.read_text())['files']}
        self.assertTrue(name in refs, 'controller source must be pinned')
    def test_escape_identity_rejected(self):
        (self.scope/'outside.txt').write_text('outside\n')
        with self.assertRaises((ValueError,AssertionError)):M.identity(self.root,'../outside.txt')
    def test_dangling_new_source_rejected_before_freeze(self):
        (self.root/(P+'epoch19/dangling.py')).symlink_to('missing.py')
        with self.assertRaises((ValueError,AssertionError,FileNotFoundError)):M.build(self.args)
        self.assertFalse(self.freeze.exists())
    def test_missing_named_reference_does_not_write_partial_freeze(self):
        (self.root/(P+'audit/epoch19/protocol.json')).unlink()
        with self.assertRaises((ValueError,AssertionError,FileNotFoundError)):M.build(self.args)
        self.assertFalse(self.freeze.exists())
    def test_symlink_directory_rejected_before_freeze(self):
        other=self.scope/'elsewhere';other.mkdir();(other/'x.py').write_text('pass\n')
        (self.root/(P+'epoch19/linked-dir')).symlink_to(other,target_is_directory=True)
        with self.assertRaises((ValueError,AssertionError,FileNotFoundError)):M.build(self.args)
        self.assertFalse(self.freeze.exists())
    def test_prior_attempt_and_final_artifacts_rejected_before_freeze(self):
        for suffix in ('launch.json','runs/qualification/attempt.json','RESULTS.json','USED_IDENTITIES.json','EPOCH_MANIFEST.json'):
            with self.subTest(suffix=suffix):
                path=self.root/(P+'epoch19/'+suffix);path.parent.mkdir(parents=True,exist_ok=True);path.write_text('{}\n')
                with self.assertRaises((ValueError,AssertionError)):M.build(self.args)
                self.assertFalse(self.freeze.exists())
                path.unlink()
if __name__=='__main__':unittest.main()
