"""Pure local WAL/object/metadata fixtures; no CLI, tail, Git or stage runs."""
import sys
sys.dont_write_bytecode=True
import copy
import importlib.util
import json
from pathlib import Path
import unittest
from unittest.mock import patch

OWN=Path('/workspace/ruvector-e34-publication-impl')
spec=importlib.util.spec_from_file_location('source_tail_local_fixture',OWN/'verify-source-publication-tail-inputs-v1.py')
V=importlib.util.module_from_spec(spec);spec.loader.exec_module(V)

class LocalTailFixtures(unittest.TestCase):
 @classmethod
 def setUpClass(cls):
  cls.rows=[json.loads(line)for line in(V.W/'mutation-journal.jsonl').read_text().splitlines()]
  cls.meta=V.parse(V.W/'stage-source/metadata.json')
 def valid(self,rows=None,meta=None):return V.check_wal(self.rows if rows is None else rows,self.meta if meta is None else meta)
 def test_exact20resolvedpairs_pass_without_replay(self):
  r=self.valid();self.assertEqual(r['successful_pairs'],20);self.assertEqual(r['unused_tail_ids'],['e34-source-commit','e34-source-ref'])
 def test_missing_or_extra_WAL_rows_refused(self):
  for rows in(self.rows[:-1],self.rows+[copy.deepcopy(self.rows[-1])]):
   with self.assertRaises(ValueError):self.valid(rows)
 def test_failed_or_uncertain_response_refused(self):
  bad=copy.deepcopy(self.rows);bad[9]['payload']['ok']=False
  with self.assertRaisesRegex(ValueError,'Uncertain/failed'):self.valid(bad)
 def test_wrong_owner_refused(self):
  bad=copy.deepcopy(self.rows);bad[8]['owner']=1
  with self.assertRaisesRegex(ValueError,'owner-bound'):self.valid(bad)
 def test_reordered_pair_refused(self):
  bad=copy.deepcopy(self.rows);bad[8],bad[9]=bad[9],bad[8]
  with self.assertRaises(ValueError):self.valid(bad)
 def test_args_intent_hash_drift_refused(self):
  bad=copy.deepcopy(self.rows);bad[8]['payload']['sha256']='0'*64
  with self.assertRaisesRegex(ValueError,'request args differ'):self.valid(bad)
 def test_blob_response_not_matching_stage_refused(self):
  bad=copy.deepcopy(self.rows);bad[9]['payload']['result']['sha']='0'*40
  with self.assertRaisesRegex(ValueError,'Completed blob'):self.valid(bad)
 def test_tree_chain_not_matching_stage_refused(self):
  bad=copy.deepcopy(self.rows);bad[21]['payload']['result']['sha']='0'*40
  with self.assertRaisesRegex(ValueError,'tree request differs'):self.valid(bad)
 def test_final_tree_wrong_root_refused(self):
  bad=copy.deepcopy(self.rows);bad[-1]['payload']['result']['sha']='0'*40
  with self.assertRaisesRegex(ValueError,'known created root'):self.valid(bad)
 def test_any_reserved_tail_request_is_refused(self):
  request_dir=V.W/'mutation-requests';current=list(request_dir.iterdir())
  with patch.object(Path,'iterdir',return_value=iter(current+[request_dir/'e34-source-commit.json'])):
   with self.assertRaisesRegex(ValueError,'Only20 resolved request'):self.valid()
 def test_wrong_staged_object_counts_refused(self):
  bad=copy.deepcopy(self.meta);bad['large_blob_requests']=bad['large_blob_requests'][:-1]
  with self.assertRaisesRegex(ValueError,'6blob10tree'):self.valid(meta=bad)
 def test_transport_path_escape_refused(self):
  bad=copy.deepcopy(self.meta);bad['large_blob_requests'][0]['file']='../outside.json'
  with self.assertRaisesRegex(ValueError,'Unsafe'):self.valid(meta=bad)
 def test_actual_parent_and_created_tree_hashes(self):
  for name,sha in [('baseline-0.json',V.PARENT_ROOT),('baseline-1.json',V.PARENT_BENCH),('source-created-root.json',V.CREATED['root']),('source-created-bench.json',V.CREATED['bench'])]:
   self.assertEqual(V.git_tree_sha(V.parse(V.W/name)),sha)
 def test_sibling_drift_is_refused(self):
  original=V.parse(V.W/'baseline-0.json');created=V.parse(V.W/'source-created-root.json');V.check_siblings(created,original,'benchmarks',V.CREATED['bench'])
  bad=copy.deepcopy(created);next(row for row in bad['tree']if row['path']!='benchmarks')['sha']='0'*40
  with self.assertRaisesRegex(ValueError,'Sibling identity'):V.check_siblings(bad,original,'benchmarks',V.CREATED['bench'])
 def test_all_metadata_pins_exact(self):
  for path,expected in V.PINS.items():V.file_ref(path,expected)

if __name__=='__main__':unittest.main()
