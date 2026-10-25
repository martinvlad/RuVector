"""Disjoint metadata-byte fixtures; never opens real custody files or root modes."""
import sys
sys.dont_write_bytecode=True
from pathlib import Path
HERE=Path(__file__).parent
sys.path.insert(0,str(HERE.parent/'experiments/sota-2026-10-22/epoch40/publication'))
import ast,copy,hashlib,importlib.util,tempfile,unittest
from unittest.mock import patch
spec=importlib.util.spec_from_file_location('postrun_metadata_results_fixture',HERE/'reviewed_build_results_v2.py');m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
class Metadata(unittest.TestCase):
 def fixture(self):
  tmp=tempfile.TemporaryDirectory();base=Path(tmp.name);root=base/'public';root.mkdir();f=base/'opaque.bin';f.write_bytes(b'\xff\x00not JSON, authored disjoint metadata bytes');row={'path':str(f),'bytes':f.stat().st_size,'sha256':hashlib.sha256(f.read_bytes()).hexdigest()};return tmp,root,f,row
 def test_external_exact_opaque_bytes_need_no_json(self):
  t,r,f,row=self.fixture()
  with t,patch.object(m,'EXTERNAL_REPLAY_EVIDENCE',{'joined_labels':row}),patch.object(m.c,'parse',side_effect=AssertionError('JSON semantic read forbidden')):
   self.assertIs(m.checked_evidence(r,'joined_labels',row),row)
 def test_changed_hash_size_type_or_path_rejected(self):
  t,r,f,row=self.fixture()
  with t,patch.object(m,'EXTERNAL_REPLAY_EVIDENCE',{'joined_labels':row}):
   for key,value in [('path',str(f.parent/'other')),('bytes',float(row['bytes'])),('bytes',row['bytes']+1),('sha256','0'*64)]:
    wrong=dict(row);wrong[key]=value
    with self.assertRaises(ValueError):m.checked_evidence(r,'joined_labels',wrong)
   f.write_bytes(b'wrong bytes')
   with self.assertRaises(ValueError):m.checked_evidence(r,'joined_labels',row)
 def test_other_absolute_roles_still_use_strict_public_ref(self):
  t,r,f,row=self.fixture()
  with t:
   for role in ('raw','unknown','joined_labels_alias'):
    with self.assertRaises(ValueError):m.checked_evidence(r,role,row)
 def test_declared_external_ref_cannot_be_inside_R_or_symlink(self):
  t,r,f,row=self.fixture()
  with t:
   inside=r/'opaque.bin';inside.write_bytes(b'x');ir={'path':str(inside),'bytes':1,'sha256':hashlib.sha256(b'x').hexdigest()}
   with patch.object(m,'EXTERNAL_REPLAY_EVIDENCE',{'joined_labels':ir}):
    with self.assertRaises(ValueError):m.checked_evidence(r,'joined_labels',ir)
   alias=f.parent/'alias.bin';alias.symlink_to(f);ar=dict(row,path=str(alias))
   with patch.object(m,'EXTERNAL_REPLAY_EVIDENCE',{'joined_labels':ar}):
    with self.assertRaises(ValueError):m.checked_evidence(r,'joined_labels',ar)
 def test_public_relative_ref_remains_exact(self):
  with tempfile.TemporaryDirectory()as t:
   root=Path(t);(root/'public.json').write_bytes(b'{}');row={'path':'public.json','bytes':2,'sha256':hashlib.sha256(b'{}').hexdigest()};self.assertEqual(m.checked_evidence(root,'raw',row),row)
   with self.assertRaises(ValueError):m.checked_evidence(root,'raw',dict(row,path='../outside'))
 def test_every_replay_field_and_type_retained(self):
  replay={'checks_passed':True,'dev_passed':False,'status':'REJECTED_DEV_PILOT','nested':[False,0,1.0,None,{'private_ref_metadata_only':'fixture'}]};result=m.preserve_replay(replay,{'metadata_only':True});self.assertTrue(m.c.same_fact({k:result[k]for k in replay},replay));result['nested'].append('new');self.assertEqual(len(replay['nested']),5)
 def test_delta_contains_no_changed_scoring_or_results_logic(self):
  before=ast.parse((HERE/'frozen-original/reviewed_build_results.py').read_text());after=ast.parse((HERE/'reviewed_build_results_v2.py').read_text());old={n.name:ast.dump(n,include_attributes=False)for n in before.body if isinstance(n,ast.FunctionDef)};new={n.name:ast.dump(n,include_attributes=False)for n in after.body if isinstance(n,ast.FunctionDef)}
  self.assertEqual(set(new)-set(old),{'checked_evidence'});self.assertEqual([k for k in old if old[k]!=new[k]],['setup'])
  fn=next(n for n in after.body if isinstance(n,ast.FunctionDef)and n.name=='checked_evidence');calls=[ast.unparse(n.func)for n in ast.walk(fn)if isinstance(n,ast.Call)];self.assertFalse(any('parse' in c or 'json' in c or 'label' in c for c in calls));self.assertLess(len((HERE/'reviewed_build_results_v2.py').read_text().splitlines()),500)
if __name__=='__main__':unittest.main()
