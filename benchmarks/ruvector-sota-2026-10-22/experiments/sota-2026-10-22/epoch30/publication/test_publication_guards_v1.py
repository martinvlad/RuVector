"""Metadata/codec/phase tamper tests only; no models, sockets or Git calls."""
import sys
sys.dont_write_bytecode=True
import base64,copy,hashlib,json,math,struct,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
import publication_common_v1 as c
import phase_schema_v1 as s
import phase_receipts_v1 as r
import parameter_artifact_v1 as a
import stage_publication_v1 as p

SCRATCH=Path('/workspace/ruvector-e30-publication-impl')

def bytes_json(value):return (json.dumps(value,separators=(',',':'),sort_keys=True)+'\n').encode()

class Guards(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory(prefix='guards-',dir=SCRATCH);self.root=Path(self.tmp.name)
  self.put(s.PLAN_PATH,{'epoch':30});self.put(s.FREEZE_PATH,{'epoch':30});self.planref=c.ref(self.root,s.PLAN_PATH)
 def tearDown(self):self.tmp.cleanup()
 def put(self,path,value):
  f=self.root/path;f.parent.mkdir(parents=True,exist_ok=True);f.write_bytes(bytes_json(value));return c.ref(self.root,path)
 def rows(self):return {x.relative_to(self.root).as_posix():c.ref(self.root,x.relative_to(self.root).as_posix()) for x in self.root.rglob('*') if x.is_file()}
 def reject(self,fn,*args):
  with self.assertRaises((ValueError,KeyError,FileNotFoundError)):fn(*args)
 def capture(self,phase='train',partial=False):
  self.put(s.PHASE_RESERVATIONS[phase],{'phase':phase,'plan_sha256':self.planref['sha256']})
  raw={'epoch':30,'phase':phase,'kind':s.KIND,'source_checkpoint':c.BASE_COMMIT,'data_roles':copy.deepcopy(s.ROLES),'plan_sha256':self.planref['sha256'],
   'status':'COMPLETED_TRAIN_AWAITING_INDEPENDENT_MODEL_SEAL' if phase=='train' else 'COMPLETED_DEV_AWAITING_INDEPENDENT_GOLD_JOIN',
   'counters':{'training_steps':24 if phase=='train' else 0,'optimizer_steps':24 if phase=='train' else 0,'NLI_forward_pairs_completed':24 if phase=='train' else 96,'paid_calls':0,'GPU_calls':0},'errors':[]}
  selected='raw.partial.json' if partial else 'raw.json';pin=self.put(s.E+'runs/'+phase+'/'+selected,raw)
  execution={'epoch':30,'phase':phase,'kind':s.KIND,'status':'WORKER_FAILED_OR_TIMEOUT' if partial else 'WORKER_COMPLETED',
   'worker_attempts_reserved':1,'verified_worker_starts':1,'uncertain_start':False,'exit_code':-9 if partial else 0,
   'owned_live_group_members':[],'owned_live_processes_closed':True,'wall_seconds_including_init_cleanup':1.0,'children_user_seconds':1.0,'children_system_seconds':0.0,'largest_child_peak_RSS_bytes':1000,'CPU_affinity':[0,1],
   'allowed_further_phase_workers':0,'cleanup_errors':[],'launcher_error':None,'source_plan_unchanged':True,'raw_closure_invariants':{'all_complete':not partial},
   'raw_bytes':None if partial else pin['bytes'],'raw_sha256':None if partial else pin['sha256'],'partial_raw_bytes':pin['bytes'] if partial else None,'partial_raw_sha256':pin['sha256'] if partial else None,
   'raw_operation_counters':raw['counters'],'raw_operation_counters_source':selected,'operation_counts_complete':not partial,'backend_execution_since_checkpoint':'UNKNOWN' if partial else 'NOT_APPLICABLE_FINAL_RAW'}
  self.put(s.E+'runs/'+phase+'/execution.json',execution)
  return raw,execution,pin
 def test_duplicate_and_nonfinite_JSON(self):
  self.reject(c.loads,b'{"a":1,"a":2}');self.reject(c.loads,b'{"a":NaN}')
 def test_scope_paths_binary_private(self):
  for path in ('../x','/x','a/../b','a\\b'):self.reject(c.relative,path)
  self.reject(c.public_text,s.E+'x.txt',b'a\0b');self.reject(c.public_text,s.E+'secret.txt',('gh'+'p_'+'x'*40).encode())
 def test_unstarted_phase_resources_unknown(self):
  value=r.phase_evidence(self.root,'dev',self.planref)
  self.assertEqual(value['actual']['worker_attempts'],0);self.assertIsNone(value['actual']['resources']);self.assertIsNone(value['actual']['errors'])
 def test_reservation_cannot_be_erased_as_unstarted(self):
  self.put(s.PHASE_RESERVATIONS['dev'],{'phase':'dev','plan_sha256':self.planref['sha256']});self.reject(r.phase_evidence,self.root,'dev',self.planref)
 def test_complete_train_phase(self):
  self.capture();value=r.phase_evidence(self.root,'train',self.planref,self.rows());self.assertTrue(r.phase_completed(value));self.assertEqual(value['actual']['training_steps'],24)
 def test_reserved_uncertain_start_burns_one(self):
  _,e,_=self.capture(partial=True);e.update(verified_worker_starts=0,uncertain_start=True,raw_operation_counters_source='UNKNOWN',raw_operation_counters=None,partial_raw_bytes=None,partial_raw_sha256=None)
  (self.root/(s.E+'runs/train/raw.partial.json')).unlink();self.put(s.E+'runs/train/execution.json',e)
  value=r.phase_evidence(self.root,'train',self.planref);self.assertEqual(value['actual']['worker_attempts'],1);self.assertEqual(value['actual']['verified_worker_starts'],0);self.assertIsNone(value['actual']['errors'])
 def unknown_capture(self):
  _,e,_=self.capture(partial=True)
  (self.root/(s.E+'runs/train/raw.partial.json')).unlink()
  e.update(verified_worker_starts=0,uncertain_start=True,exit_code=None,raw_operation_counters_source='UNKNOWN',raw_operation_counters=None,
   partial_raw_bytes=None,partial_raw_sha256=None,owned_live_group_members=None,owned_live_processes_closed=None,
   owned_process_closure_observation='UNKNOWN_UNRETURNED_POPEN_WITHOUT_IDENTITY_PROOF',worker_identity_source='UNKNOWN',worker_identity=None,recovered_preexec_child_identity=None)
  self.put(s.E+'runs/train/execution.json',e)
  return r.phase_evidence(self.root,'train',self.planref)
 def test_failed_unknown_physical_closure_preserved(self):
  value=self.unknown_capture();self.assertIsNone(value['actual']['owned_live_processes_closed']);self.assertIsNone(value['actual']['owned_live_group_members']);self.assertEqual(value['actual']['worker_attempts'],1)
  total=r.aggregate_actual(value,r.phase_evidence(self.root,'dev',self.planref));self.assertIsNone(total['owned_live_processes_closed'])
 def test_unknown_physical_closure_cannot_complete_or_MODEL(self):
  value=self.unknown_capture();self.assertFalse(r.phase_completed(value))
  with patch.object(p,'phase_evidence',return_value=value):self.reject(p.validate_model_seal,self.root,{},None,{'schema_version':1,'epoch':30,'kind':s.KIND,'status':'TRAINED_PARAMETER_ARTIFACT_SEALED','base_model_sha256':s.BASE_MODEL['weights_sha256'],'parameter_artifact':{},'train_raw':value['raw'],'train_execution':value['execution'],'independent_training_report':{},'source_plan':self.planref,'source_freeze':c.ref(self.root,s.FREEZE_PATH)})
 def test_FINAL_unknown_physical_closure_refused(self):
  value=self.unknown_capture();total=r.aggregate_actual(value,r.phase_evidence(self.root,'dev',self.planref));self.reject(r.require_final_physical_closure,total)
 def test_known_partial_counters_cannot_be_hidden(self):
  _,e,_=self.capture(partial=True);e.update(raw_operation_counters_source='UNKNOWN',raw_operation_counters=None)
  self.put(s.E+'runs/train/execution.json',e);self.reject(r.phase_evidence,self.root,'train',self.planref)
 def test_wrong_phase_receipt_rejected(self):
  raw,e,_=self.capture();e['phase']='dev';self.put(s.E+'runs/train/execution.json',e);self.reject(r.phase_evidence,self.root,'train',self.planref)
 def test_partial_not_completed(self):
  self.capture(partial=True);value=r.phase_evidence(self.root,'train',self.planref);self.assertFalse(r.phase_completed(value));self.assertFalse(value['actual']['operation_counts_complete']);self.assertEqual(value['actual']['backend_execution_since_checkpoint'],'UNKNOWN')
 def test_malformed_final_preserves_partial(self):
  _,e,_=self.capture(partial=True);f=self.root/(s.E+'runs/train/raw.json');f.write_bytes(b'{"unfinished":');pin=c.ref(self.root,s.E+'runs/train/raw.json');e.update(raw_bytes=pin['bytes'],raw_sha256=pin['sha256']);self.put(s.E+'runs/train/execution.json',e)
  value=r.phase_evidence(self.root,'train',self.planref);self.assertTrue(value['raw']['path'].endswith('raw.partial.json'));self.assertEqual(value['actual']['training_steps'],24)
 def test_actual_two_phase_accounting(self):
  self.capture();self.capture('dev');train=r.phase_evidence(self.root,'train',self.planref);dev=r.phase_evidence(self.root,'dev',self.planref);total=r.aggregate_actual(train,dev);self.assertEqual(total['worker_attempts'],2);self.assertEqual(total['completed_corpus_batches'],2);self.assertEqual(total['dev']['NLI_forward_pairs_completed'],96)
 def test_no_benchmark_flags(self):
  p.verify_flags(s.FLAGS);wrong=dict(s.FLAGS,benchmark_accepted=True);self.reject(p.verify_flags,wrong)
 def test_legacy_exposure_strings_retained(self):
  old={'exposed_development_sets':['legacy'], 'champion':{'id':'native104'}};new=copy.deepcopy(old);new['exposed_development_sets'].append(p.retirement_record());p.preserve_history(old,new,p.MUTABLE)
  new['exposed_development_sets']=[];self.reject(p.preserve_history,old,new,p.MUTABLE)
 def test_source_sole_parent_conflict(self):
  proof={'commit':p.SOURCE_PARENT,'parent':p.SOURCE_PARENT_SOLE_PARENT,'checks_passed':True,'verified_actual_remote_readback':True,'root':p.SOURCE_TREES[0],'bench':p.SOURCE_TREES[1],'scope':p.SOURCE_TREES[2]};p.check_readback(proof,'source',p.SOURCE_PARENT,p.SOURCE_TREES);proof['sole_parent']='0'*40;self.reject(p.check_readback,proof,'source',p.SOURCE_PARENT,p.SOURCE_TREES)
 def test_strict_transport_caps(self):
  blobs,groups=p.transport_groups({s.E+'x.json':b'['+b' '*200000+b']',s.E+'y.txt':b'y'*60000});self.assertEqual(len(blobs),1);self.assertTrue(all(len(c.encoded({'tree_elements':g}))<p.MAX_TREE_JSON for g in groups))
 def model_fixture(self,partial=False):
  self.capture(partial=partial);train=r.phase_evidence(self.root,'train',self.planref)
  artifact=self.put(s.ARTIFACT_PATH,{'component_test_only':'codec separately exercised in RAM'})
  report={'schema_version':1,'epoch':30,'kind':s.KIND,'train_integrity_passed':True,'evidence':{'artifact':artifact,'raw':train['raw'],'execution':train['execution'],'plan':self.planref,'freeze':c.ref(self.root,s.FREEZE_PATH)}}
  audit=self.put(s.P+'audit/epoch30/train-integrity.json',report)
  seal={'schema_version':1,'epoch':30,'kind':s.KIND,'status':'TRAINED_PARAMETER_ARTIFACT_SEALED','base_model_sha256':s.BASE_MODEL['weights_sha256'],'parameter_artifact':artifact,'train_raw':train['raw'],'train_execution':train['execution'],'independent_training_report':audit,'source_plan':self.planref,'source_freeze':c.ref(self.root,s.FREEZE_PATH)}
  plan={'expected_operation_counters':{'train':{'training_steps':24,'optimizer_steps':24,'NLI_forward_pairs_completed':24}},'train_inputs_sha256':'4'*64,'training_algorithm':{'seed':30030}}
  summary={key:True for key in ('original_head_preserved','initial_LoRA_B_bit_zero','all_frozen_pretrained_bit_unchanged','all12_trainable_tensors_changed','all4_effective_lora_mechanisms_nonzero')}
  return seal,plan,summary
 def test_MODEL_requires_closed_full_TRAIN(self):
  seal,plan,summary=self.model_fixture(partial=True)
  with patch.object(p,'validate_artifact',return_value=summary):self.reject(p.validate_model_seal,self.root,plan,self.rows(),seal)
 def test_MODEL_completed_TRAIN_and_functional_gate(self):
  seal,plan,summary=self.model_fixture()
  with patch.object(p,'validate_artifact',return_value=summary):p.validate_model_seal(self.root,plan,self.rows(),seal)
  report=c.parse(self.root/seal['independent_training_report']['path']);report['train_integrity_passed']=False;seal['independent_training_report']=self.put(seal['independent_training_report']['path'],report)
  with patch.object(p,'validate_artifact',return_value=summary):self.reject(p.validate_model_seal,self.root,plan,self.rows(),seal)
 def test_MODEL_cannot_override_zero_B_mechanism(self):
  seal,plan,summary=self.model_fixture();summary['all4_effective_lora_mechanisms_nonzero']=False
  with patch.object(p,'validate_artifact',return_value=summary):self.reject(p.validate_model_seal,self.root,plan,self.rows(),seal)
 def test_actual_historical_baseline_arithmetic(self):
  scope=Path('/tmp/ruvector-sota-2026-10-22/epoch30-9f13c9bb6e47');before=c.parse(scope/'kit/CONTINUATION.json')['execution_observed']
  self.assertEqual((before['epoch27_cumulative_corpus_attempts'],before['epoch27_cumulative_completed_corpus_batches']),(24,22));saved=copy.deepcopy(before)
  counts=r.cumulative_counts({'worker_attempts':2,'completed_corpus_batches':2});self.assertEqual((counts['corpus_attempts'],counts['completed_corpus_batches'],counts['bounded_native_process_attempts']),(26,24,32));self.assertEqual(counts['qualification_attempts'],6);self.assertEqual(before,saved)

def codec_fixture():
 rows=[];initial=[];original=[];changes=[]
 for name,shape in s.TENSORS:
  n=math.prod(shape);data=struct.pack('<f',0.001)*n;zero=bytes(4*n);digest=hashlib.sha256(data).hexdigest();z=hashlib.sha256(zero).hexdigest()
  meta={'name':name,'shape':shape,'dtype':'float32le','numel':n,'bytes':4*n,'sha256':digest};rows.append(dict(meta,data_base64=base64.b64encode(data).decode()));before=dict(meta,sha256=z);initial.append(before)
  if name.startswith('classification_head.'):original.append(before)
  changes.append({'name':name,'before_sha256':z,'after_sha256':digest,'changed':True})
 proof=[]
 for i in range(511):
  n=406291456-510 if i==0 else 1;proof.append({'name':'frozen.%04d'%i,'shape':[n],'dtype':'float32le','numel':n,'bytes':4*n,'sha256_before':'1'*64,'sha256_after':'1'*64})
 manifest=[{k:v for k,v in row.items() if not k.startswith('sha256_')}|{'sha256':row['sha256_before']} for row in proof]
 frozen={'parameter_count':406291456,'tensor_count':511,'before_after':proof,'all_bit_unchanged':True,'aggregate_before_sha256':a.aggregate(manifest),'aggregate_after_sha256':a.aggregate(manifest)}
 delta=[{'module':module,'shape':[1024,1024],'scale':2.0,'sha256':'2'*64,'l2_norm':1.0,'max_abs':1.0,'nonzero_entries':1048576,'B_nonzero_gradient_steps':[1],'max_B_gradient_l2':1.0} for module in s.MODULES]
 return {'schema_version':1,'epoch':30,'kind':s.KIND,'codec':s.ARTIFACT_CODEC,'base_model':s.BASE_MODEL,'algorithm':{'seed':30030},'source_plan_sha256':'3'*64,'training_inputs_sha256':'4'*64,'training_steps':24,'trainable_parameter_count':1085443,'tensors':rows,'original_head_manifest':original,'initial_trainable_manifest':initial,'trainable_changes':changes,'frozen_pretrained_proof':frozen,'effective_lora_delta':delta}

class Codec(unittest.TestCase):
 @classmethod
 def setUpClass(cls):cls.value=codec_fixture()
 def test_exact_lossless_codec_in_RAM(self):
  result=a.validate_artifact(bytes_json(self.value),'3'*64,'4'*64,{'seed':30030});self.assertEqual(result['decoded_float32_bytes'],4341772)
 def test_extra_tensor_or_base_payload_rejected(self):
  v=copy.deepcopy(self.value);v['tensors'].append(v['tensors'][0])
  with self.assertRaises(ValueError):a.validate_artifact(bytes_json(v))
 def test_nonfinite_payload_rejected(self):
  v=copy.deepcopy(self.value);row=v['tensors'][0];raw=struct.pack('<I',0x7fc00000)+base64.b64decode(row['data_base64'])[4:];row['data_base64']=base64.b64encode(raw).decode();row['sha256']=hashlib.sha256(raw).hexdigest()
  with self.assertRaises(ValueError):a.validate_artifact(bytes_json(v))
 def test_wrong_plan_or_train_identity_rejected(self):
  with self.assertRaises(ValueError):a.validate_artifact(bytes_json(self.value),'0'*64,'4'*64)
 def test_rejected_mechanism_can_be_retained_structurally(self):
  v=copy.deepcopy(self.value);v['effective_lora_delta'][0].update(l2_norm=0.0,max_abs=0.0,nonzero_entries=0,B_nonzero_gradient_steps=[],max_B_gradient_l2=0.0);summary=a.validate_artifact(bytes_json(v));self.assertFalse(summary['all4_effective_lora_mechanisms_nonzero'])

if __name__=='__main__':unittest.main()
