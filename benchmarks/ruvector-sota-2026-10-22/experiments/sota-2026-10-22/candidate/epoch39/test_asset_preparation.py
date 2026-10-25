"""Invented tiny cache fixtures only, never actual root plan/cache or model files."""
from pathlib import Path
import hashlib
import importlib.util
import json
import os
import tempfile
import unittest
from unittest.mock import patch
HERE=Path(__file__).resolve().parent

def load(name,path):
 sp=importlib.util.spec_from_file_location(name,path);m=importlib.util.module_from_spec(sp);sp.loader.exec_module(m);return m
G=load('e39_tiny_guard',HERE/'runtime/model_assets_guard.py');M=load('e39_tiny_materializer',HERE/'runtime/materialize_assets.py')
def put(p,x):p.parent.mkdir(parents=True,exist_ok=True);p.write_text(json.dumps(x)+'\n')
def tiny_fixture(base):
 candidate=base/'candidate';runtime=candidate/'runtime';runtime.mkdir(parents=True);plan={'source_profiles':{},'minimum_workspace_free_bytes':1024};specs={}
 for tag,n in [('b354',9),('xxlarge',5)]:
  source=base/(tag+'-source');source.mkdir();target=base/(tag+'-target');rows=[]
  for i in range(n):
   name='fixture'+str(i)+'.bin';body=('Unrelated tiny public-cache fixture '+tag+str(i)+'\n').encode();p=source/name;p.write_bytes(body);p.chmod(0o600 if i==0 else 0o444);h=hashlib.sha256(body).hexdigest()
   r={'path':name,'bytes':len(body),'source_url':'https://example.invalid/'+tag+'/'+name}
   if i<n-2:r.update(metadata_body_sha256=h,upstream_git_blob_sha1=G.identities().git_blob_sha1(body))
   else:
    pointer=f'version https://git-lfs.github.com/spec/v1\noid sha256:{h}\nsize {len(body)}\n'.encode();r.update(upstream_sha256=h,upstream_git_blob_sha1=G.identities().git_blob_sha1(pointer))
   rows.append(r)
  catalog=candidate/('MODEL_'+tag.upper()+'_ASSETS.expected.json');put(catalog,{'repository':'fixture/'+tag,'revision':'a'*40,'files':rows});digest=G.sha(catalog)
  specs[tag]={'repository':'fixture/'+tag,'revision':'a'*40,'catalog':catalog.name,'catalog_sha256':digest,'files':n}
  plan['source_profiles'][tag]={'cache_directory':str(source),'target_directory':str(target),'expected_catalog':{'path':str(catalog),'bytes':catalog.stat().st_size,'sha256':digest}}
 return candidate,runtime,plan,specs
class PreparationFixtures(unittest.TestCase):
 def run_preparation(self,base,mutate=None):
  candidate,runtime,plan,specs=tiny_fixture(base);scope=base/'scope';scope.mkdir()
  if mutate:mutate(plan)
  with patch.object(M,'HERE',runtime),patch.object(M,'SCOPE',scope),patch.object(M,'load_guard',return_value=G),\
   patch.object(M,'validate_frozen_plan',return_value=plan),patch.object(M,'guardian'),patch.object(G,'PROFILE_SPECS',specs),\
   patch.object(M.os,'sched_setaffinity'),patch.object(M.os,'sched_getaffinity',return_value={0,1}),\
   patch.object(M.signal,'signal'),patch.object(M.signal,'setitimer'),\
   patch.object(G,'verify_runtime_files',return_value={'status':'PURE_UNIT_RUNTIME_STUB_NOT_REAL_ADMISSION','wheel_members_actually_hashed':0}):
   try:result=M.prepare_assets(base/'invented-price0-plan.json',root=Path('/'),runtime_request={});error=None
   except BaseException as e:result=json.loads((scope/'ASSET_PREPARATION_RESULT.json').read_text());error=e
  return plan,result,error,scope
 def test_all14_tiny_files_full_typed_guard_copies_and_links(self):
  with tempfile.TemporaryDirectory(prefix='e39-invented-assets-')as n:
   plan,result,error,scope=self.run_preparation(Path(n));self.assertIsNone(error)
   self.assertEqual(result['actual_complete_validator']['actual_payload_files_verified'],14)
   self.assertEqual(result['actual_complete_validator']['ordinary_Git_payloads_verified'],10)
   self.assertEqual(result['actual_complete_validator']['canonical_LFS_pointers_verified'],4)
   for tag,row in plan['source_profiles'].items():
    source=Path(row['cache_directory']);target=Path(row['target_directory'])
    self.assertEqual(source.joinpath('fixture0.bin').stat().st_mode&0o777,0o600);self.assertEqual(target.joinpath('fixture0.bin').stat().st_mode&0o777,0o444)
    self.assertNotEqual(source.joinpath('fixture0.bin').stat().st_ino,target.joinpath('fixture0.bin').stat().st_ino)
    self.assertEqual(source.joinpath('fixture1.bin').stat().st_ino,target.joinpath('fixture1.bin').stat().st_ino)
   self.assertTrue((scope/'ASSET_PREPARATION_ATTEMPT.json').is_file())
 def test_missing_cache_is_captured_after_once_reservation(self):
  def mutate(p):p['source_profiles']['b354']['cache_directory']+='/missing'
  with tempfile.TemporaryDirectory(prefix='e39-invented-assets-')as n:
   p,r,e,s=self.run_preparation(Path(n),mutate);self.assertIsNotNone(e);self.assertEqual(r['status'],'ASSET_PREPARATION_FAILED_STOP_NO_RETRY');self.assertTrue((s/'ASSET_PREPARATION_ATTEMPT.json').is_file())
 def test_corrupt_source_stops_and_retains_failure(self):
  def mutate(p):Path(p['source_profiles']['b354']['cache_directory']).joinpath('fixture0.bin').write_bytes(b'not the declared invented bytes')
  with tempfile.TemporaryDirectory(prefix='e39-invented-assets-')as n:
   p,r,e,s=self.run_preparation(Path(n),mutate);self.assertIsNotNone(e);self.assertTrue((s/'asset-preparation-exact-error.txt').is_file());self.assertEqual(r['status'],'ASSET_PREPARATION_FAILED_STOP_NO_RETRY')
 def test_existing_target_is_never_overwritten(self):
  def mutate(p):Path(p['source_profiles']['b354']['target_directory']).mkdir()
  with tempfile.TemporaryDirectory(prefix='e39-invented-assets-')as n:
   p,r,e,s=self.run_preparation(Path(n),mutate);self.assertIsInstance(e,ValueError);self.assertEqual(list(Path(p['source_profiles']['b354']['target_directory']).iterdir()),[])
 def test_untyped_observed_row_rejected_as_source(self):
  identity=G.identities();raw=b'invented';h=hashlib.sha256(raw).hexdigest()
  with self.assertRaises(ValueError):identity.expected_payload({'path':'x','bytes':len(raw),'source_url':'https://example.invalid/x','sha256':h,'upstream_git_blob_sha1':identity.git_blob_sha1(raw)})
class MetadataOnlyFixtures(unittest.TestCase):
 def test_all14_real_catalog_metadata_types_without_payload_reads(self):
  counts={};ordinary=lfs=0
  for tag,spec in G.PROFILE_SPECS.items():
   path=HERE/spec['catalog'];self.assertEqual(G.sha(path),spec['catalog_sha256']);rows=G.read_metadata(path)['files'];counts[tag]=len(rows)
   for row in rows:
    declaration=G.identities().expected_payload(row)
    if declaration['raw_payload_git_blob_sha1_required']:ordinary+=1
    else:lfs+=1
    observed={k:v for k,v in row.items()if k not in('upstream_sha256','metadata_body_sha256')}|{'sha256':declaration['payload_sha256']}
    with self.assertRaises(ValueError):G.identities().expected_payload(observed)
  self.assertEqual(counts,{'b354':9,'xxlarge':5});self.assertEqual((ordinary,lfs),(10,4))
 def test_imports_are_source_only_and_files_below500_lines(self):
  import ast,sys
  for name in ['runtime/model_assets_guard.py','runtime/materialize_assets.py']:
   source=(HERE/name).read_text();ast.parse(source);self.assertLess(len(source.splitlines()),500)
  self.assertEqual([n for n in('torch','transformers','onnxruntime','tokenizers','numpy')if n in sys.modules],[])

if __name__=='__main__':unittest.main()
