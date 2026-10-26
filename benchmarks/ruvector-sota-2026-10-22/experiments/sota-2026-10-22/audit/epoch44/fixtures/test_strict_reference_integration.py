"""One metadata-only regression: real failing inherited source rows -> strict E44 consumer."""
from pathlib import Path
import ast,copy,hashlib,importlib.util,json,tempfile,unittest
S=Path(__file__).resolve().parent;A='experiments/sota-2026-10-22/audit/epoch44/'
p=S.parent/'e44_features.py'
if not p.is_file():p=S/'source-v1/project'/A/'e44_features.py'
sp=importlib.util.spec_from_file_location('e44_metadata_strict_source',p);F=importlib.util.module_from_spec(sp);sp.loader.exec_module(F)
class StrictReferenceIntegration(unittest.TestCase):
 def test_real_inherited_three_rows_canonicalize_then_strict_consumer(self):
  proof=json.loads(Path('/workspace/ruvector-e43-independent-audit/ACTUAL_PRE_DATA_SOURCE_SCHEMA_FAILURE_INDEPENDENT.v1.json').read_text());rows=proof['source_failure']['inherited_rows_with_extra_key'];self.assertEqual(len(rows),3)
  p=Path('/workspace/ruvector-e43-engineering/future-reference-schema-v2/future_freeze_and_results.py');b=p.read_bytes();self.assertEqual(F.sha(b),'f6a2175954392edfc1ca455e382b5970cc2d835163708a4fccbd5af6a2dd80a8');tree=ast.parse(b);selected=ast.Module(body=[n for n in tree.body if isinstance(n,ast.FunctionDef)and n.name in ['public_ref','canonical_reference','canonical_freeze_references']],type_ignores=[])
  class C:
   require=staticmethod(F.require)
   @staticmethod
   def relative(value):
    p=Path(value);F.require(not p.is_absolute()and all(x not in['','.','..']for x in value.split('/')),'RELATIVE');return p
   @staticmethod
   def checked(path,row):return F.read_ref(dict(row,path=str(path)))
   @staticmethod
   def public_text(path,body):return None # This fixture tests schema/typed Git; public-source body whitelist was independently reviewed.
   @staticmethod
   def same(a,b):return type(a)is type(b)and a==b
  env={'c':C,'hashlib':hashlib};exec(compile(selected,str(p),'exec'),env)
  current=Path('/tmp/ruvector-sota-2026-10-22/epoch44-02ed8c956725');cp={r['path']:r for r in json.loads((current/'remote-current/CHECKPOINT_MANIFEST.json').read_text())['project_files']};git={r['path']:r for r in json.loads((current/'actual-git-map.json').read_text())['files']if r['type']=='blob'}
  with tempfile.TemporaryDirectory()as td:
   root=Path(td)
   for row in rows:
    donor=current/'project'/row['path'];body=donor.read_bytes();self.assertEqual(F.sha(body),cp[row['path']]['sha256']);self.assertEqual(hashlib.sha1(b'blob '+str(len(body)).encode()+b'\0'+body).hexdigest(),git[row['path']]['sha']);target=root/row['path'];target.parent.mkdir(parents=True,exist_ok=True);target.write_bytes(body)
    with self.assertRaisesRegex(ValueError,'EXACT_REFERENCE_REQUIRED'):F.read_ref(row,root)
   canonical,origins=env['canonical_freeze_references'](root,[],rows);self.assertEqual(len(canonical),3);self.assertEqual(len(origins),3)
   for row in canonical:self.assertEqual(set(row),{'path','bytes','sha256'});self.assertEqual(len(F.read_ref(row,root)),row['bytes'])
   for row in origins:self.assertIs(row['payload_git_blob_identity_verified'],True);self.assertEqual(row['actual_git_blob_sha1'],git[row['path']]['sha'])
   for bad in [dict(rows[0],actual_git_blob_sha1=None),dict(rows[0],actual_git_blob_sha1='0'*40)]:
    with self.assertRaises(ValueError):env['canonical_freeze_references'](root,[],[bad])
if __name__=='__main__':unittest.main()
