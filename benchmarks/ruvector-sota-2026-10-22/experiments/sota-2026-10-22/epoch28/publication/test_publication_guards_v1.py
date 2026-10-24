"""Meaningful publication tamper/role/transport guards; no services or inference."""
import sys
sys.dont_write_bytecode=True
import copy,json,tempfile,unittest
from pathlib import Path
import publication_common_v1 as c
import stage_publication_v1 as s

TEST_ROOT=Path('/tmp/ruvector-e28-publication-impl')

class Guards(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory(prefix='guards-',dir=TEST_ROOT);self.root=Path(self.tmp.name)
 def tearDown(self):self.tmp.cleanup()
 def rejects(self,fn,*args):
  with self.assertRaises((ValueError,FileNotFoundError,KeyError)):fn(*args)
 def write(self,path,body):
  target=self.root/path;target.parent.mkdir(parents=True,exist_ok=True);target.write_bytes(body);return target
 def plan_fixture(self):
  a=s.E+'fixture.txt';self.write(a,b'CC0 authored evidence.')
  freeze={'schema_version':1,'epoch':28,'kind':s.KIND,'source_checkpoint':c.BASE_COMMIT,'entries':[c.ref(self.root,a)]}
  self.write(s.FREEZE_PATH,c.encoded(freeze,pretty=True))
  plan={'epoch':28,'kind':s.KIND,'source_checkpoint':c.BASE_COMMIT,'source_freeze':c.ref(self.root,s.FREEZE_PATH),'data_roles':{'train':[],'dev':[],'calibration':[],'confirmation':[]},'engineering_ids':['authored01'],'limits':{'owned_workers':1,'CPU_threads':2,'CPU_affinity':[0,1],'seconds_per_batch':600,'native_corpus_batches':1,'paid_calls':0,'GPU_calls':0},'pins':[c.ref(self.root,a)]}
  self.write(s.PLAN_PATH,c.encoded(plan,pretty=True))
  current={name:(self.root/name).read_bytes() for name in [a,s.PLAN_PATH,s.FREEZE_PATH]}
  rows={p:{'path':p,'bytes':len(b),'sha256':c.sha(b)} for p,b in current.items()}
  cont={'epoch28_frozen_study':{'plan':rows[s.PLAN_PATH],'source_freeze':rows[s.FREEZE_PATH]}}
  return current,rows,cont,plan,freeze
 def rebind_plan(self,current,rows,cont,plan):
  self.write(s.PLAN_PATH,c.encoded(plan,pretty=True));b=(self.root/s.PLAN_PATH).read_bytes();current[s.PLAN_PATH]=b;rows[s.PLAN_PATH]=c.ref(self.root,s.PLAN_PATH);cont['epoch28_frozen_study']['plan']=rows[s.PLAN_PATH]
 def test_duplicate_json(self):self.rejects(c.loads,b'{"x":1,"x":2}')
 def test_nonfinite_json(self):self.rejects(c.loads,b'{"x":[NaN]}')
 def test_unsafe_paths(self):
  for name in ['../x','a/../b','/tmp/x','a\\b','a//b','a/./b']:self.rejects(c.relative,name)
 def test_symlink(self):
  f=self.write('original.txt',b'ok');(self.root/'link.txt').symlink_to(f);self.rejects(c.content,self.root/'link.txt')
 def test_private_credential(self):self.rejects(c.public_text,s.E+'safe.txt',('gh'+'p_'+'X'*40).encode())
 def test_raw_page_and_mail(self):
  self.rejects(c.public_text,s.E+'safe.txt',b'<ht'+b'ml>raw source</ht'+b'ml>');self.rejects(c.public_text,s.E+'safe.txt',b'Received: raw message')
 def test_binary(self):self.rejects(c.public_text,s.E+'safe.txt',b'a\0b')
 def test_unreviewed_extension(self):self.rejects(c.public_text,s.E+'unsafe.bin',b'printable')
 def test_no_weights_directory(self):self.rejects(c.public_text,s.E+'weights/model.json',b'{}')
 def test_no_private_directory(self):self.rejects(c.public_text,s.E+'private/x.txt',b'publiclike')
 def test_exhaustive_review(self):
  current={s.E+'ok.txt':b'ok'};self.rejects(s.checked_review,{'files':[]},current)
  self.rejects(s.checked_review,{'files':[{'path':s.E+'ok.txt','bytes':2,'sha256':'0'*64}]},current)
 def test_checkpoint_history(self):
  row={'path':'old.txt','bytes':2,'sha256':c.sha(b'ok')};old={'schema_version':1,'project_files':[row],'history':{'v':1}}
  altered=copy.deepcopy(old);altered['project_files'][0]['sha256']='0'*64;self.rejects(s.checkpoint_extension,old,altered,{})
 def test_checkpoint_metadata(self):
  old={'schema_version':1,'project_files':[],'history':{'v':1}};altered=copy.deepcopy(old);altered['history']['v']=2;self.rejects(s.checkpoint_extension,old,altered,{})
 def test_checkpoint_extra_scope_metadata(self):
  old={'schema_version':1,'project_files':[]};altered=copy.deepcopy(old);altered['unrelated']={};self.rejects(s.checkpoint_extension,old,altered,{})
 def test_role_protection(self):
  before={'champion':{'id':'native104'},'used_confirmation_sets':['old'],'epoch27_data_roles':{'confirmation':[]}}
  after=copy.deepcopy(before);after['champion']['id']='new';self.rejects(s.preserve_history,before,after,s.FINAL_MUTABLE)
  after=copy.deepcopy(before);after['used_confirmation_sets']=[];self.rejects(s.preserve_history,before,after,s.FINAL_MUTABLE)
 def test_frozen_plan_valid(self):
  current,rows,cont,plan,freeze=self.plan_fixture();s.checked_plan(self.root,cont,rows,current,'source')
 def test_frozen_source_omission(self):
  current,rows,cont,plan,freeze=self.plan_fixture();current[s.E+'unfrozen.txt']=b'new';self.rejects(s.checked_plan,self.root,cont,rows,current,'source')
 def test_frozen_source_tamper(self):
  current,rows,cont,plan,freeze=self.plan_fixture();self.write(s.E+'fixture.txt',b'changed');self.rejects(s.checked_plan,self.root,cont,rows,current,'source')
 def test_benchmark_dev_forbidden(self):
  current,rows,cont,plan,freeze=self.plan_fixture();plan['data_roles']['dev']=['real-question'];self.rebind_plan(current,rows,cont,plan);self.rejects(s.checked_plan,self.root,cont,rows,current,'source')
 def test_second_worker_forbidden(self):
  current,rows,cont,plan,freeze=self.plan_fixture();plan['limits']['owned_workers']=2;self.rebind_plan(current,rows,cont,plan);self.rejects(s.checked_plan,self.root,cont,rows,current,'source')
 def test_confirmation_allowance_forbidden(self):
  current,rows,cont,plan,freeze=self.plan_fixture();plan['limits']['CONF_worker_attempts']=1;self.rebind_plan(current,rows,cont,plan);self.rejects(s.checked_plan,self.root,cont,rows,current,'source')
 def test_wrong_source_checkpoint(self):
  current,rows,cont,plan,freeze=self.plan_fixture();plan['source_checkpoint']='0'*40;self.rebind_plan(current,rows,cont,plan);self.rejects(s.checked_plan,self.root,cont,rows,current,'source')
 def test_benchmark_claim_forbidden(self):
  doc={k:False for k in s.FORBIDDEN_RESULT_FLAGS};doc['official_rank']=None;s.false_benchmark_flags(doc)
  doc['champion_promoted']=True;self.rejects(s.false_benchmark_flags,doc)
 def test_wrong_parent_readback(self):
  receipt={'commit':s.LEASE_COMMIT,'verified':True,'parent':c.BASE_COMMIT,'root':s.LEASE_TREES[0],'bench':s.LEASE_TREES[1],'scope':s.LEASE_TREES[2]};s.check_readback(receipt,'source',s.LEASE_COMMIT,s.LEASE_TREES)
  receipt['scope']='0'*40;self.rejects(s.check_readback,receipt,'source',s.LEASE_COMMIT,s.LEASE_TREES)
 def test_sole_parent_receipt(self):
  receipt={'commit':s.LEASE_COMMIT,'checks_passed':True,'verified_actual_remote_readback':True,'sole_parent':c.BASE_COMMIT,'root':s.LEASE_TREES[0],'bench':s.LEASE_TREES[1],'scope':s.LEASE_TREES[2]};s.check_readback(receipt,'source',s.LEASE_COMMIT,s.LEASE_TREES)
  receipt['parent']='0'*40;self.rejects(s.check_readback,receipt,'source',s.LEASE_COMMIT,s.LEASE_TREES)
 def test_tuple_file_directory_collision(self):
  rows={'a':{'sha':'1'*40},'a/b':{'sha':'2'*40}};self.rejects(s.scope_tree_sha,rows)
 def test_strict_transport_caps(self):
  changed={s.E+'large.json':b'['+b' '*200000+b']',s.E+'small.txt':b'a'*60000,s.E+'other.txt':b'b'*60000}
  blobs,groups=s.transport_groups(changed);self.assertEqual(len(blobs),1);self.assertTrue(groups)
  self.assertTrue(all(len(c.encoded({'tree_elements':g}))<s.MAX_TREE_JSON for g in groups));self.assertTrue(all(len(c.encoded(p))<s.MAX_BLOB_JSON for _,_,p in blobs))
  large_entries=[x for g in groups for x in g if x['path'].endswith('large.json')];self.assertEqual(large_entries[0]['sha'],c.gitsha(changed[s.E+'large.json']));self.assertNotIn('content',large_entries[0])
 def final_fixture(self):
  def put(path,value):self.write(path,c.encoded(value,pretty=True));return c.ref(self.root,path)
  for p in (s.PLAN_PATH,s.FREEZE_PATH):put(p,{})
  raw={'schema_version':1,'epoch':28,'kind':s.KIND,'source_checkpoint':c.BASE_COMMIT,'plan_sha256':c.ref(self.root,s.PLAN_PATH)['sha256'],'data_roles':{'train':[],'dev':[],'calibration':[],'confirmation':[]},'status':'COMPLETED_AUTHORED_QUALIFICATION_AWAITING_INDEPENDENT_REPLAY','errors':[],'counters':{'native_systemOne_requests':8,'paid_calls':0,'GPU_calls':0,'confirmation_calls':0}}
  rawref=put(s.E+'runs/engineering/raw.json',raw)
  execution={'schema_version':1,'epoch':28,'kind':s.KIND,'status':'WORKER_COMPLETED','worker_attempts_reserved':1,'verified_worker_starts':1,'uncertain_start':False,'owned_live_group_members':[],'owned_live_processes_closed':True,'wall_seconds_including_init_cleanup':1.0,'CPU_affinity':[0,1],'children_user_seconds':1.0,'children_system_seconds':0.0,'largest_child_peak_RSS_bytes':123,'allowed_further_epoch28_workers':0,'cleanup_errors':[],'launcher_error':None,'raw_bytes':rawref['bytes'],'raw_sha256':rawref['sha256'],'raw_operation_counters':raw['counters'],'raw_closure_invariants':{'raw_completed':True},'source_plan_unchanged':True,'exit_code':0}
  execution.update(raw_operation_counters_source='raw.json',operation_counts_complete=True,backend_execution_since_checkpoint='NOT_APPLICABLE_FINAL_RAW')
  put(s.E+'execution.json',execution);actual=s.derive_actual(raw,execution)
  r={k:False for k in s.FORBIDDEN_RESULT_FLAGS};r.update(status='REJECTED_ENGINEERING_QUALIFICATION',official_rank=None,engineering_qualified=False,confirmation=[],actual_execution=actual)
  rr=put(s.E+'RESULTS.json',r)
  a={'epoch':28,'kind':s.KIND,'checks_passed':True,'engineering_qualified':False,'evidence':{'raw':rawref,'execution':c.ref(self.root,s.E+'execution.json'),'results':rr}}
  ar=put(c.P+'audit/epoch28/acceptance.json',a)
  m={k:False for k in s.FORBIDDEN_RESULT_FLAGS};m.update(epoch=28,kind=s.KIND,status=r['status'],all_slots_closed=True,confirmation=[],official_rank=None,engineering_qualified=False,plan=c.ref(self.root,s.PLAN_PATH),source_freeze=c.ref(self.root,s.FREEZE_PATH),results=rr,independent_report=ar,actual_execution=actual,files=[])
  mr=put(s.E+'EPOCH_MANIFEST.json',m)
  oldlr=put(c.P+'epoch27/REJECTION_LEDGER.json',{'champion':'native104','rejections':[{'epoch':1,'status':'REJECTED'}]})
  budget={'worker_attempts_used':1,'workers_remaining':0,'native_corpus_batches_remaining':0,'confirmation_remaining':0,'all_unspent_slots_permanently_closed':True}
  decision={k:False for k in s.FORBIDDEN_RESULT_FLAGS};decision.update(status=r['status'],engineering_qualified=False,official_rank=None,results=rr)
  newlr=put(s.E+'REJECTION_LEDGER.json',{'champion':'native104','rejections':[{'epoch':1,'status':'REJECTED'},{'epoch':28,'status':r['status'],'reason':'Authored semantic qualification failed.','results':rr}],'epoch28_budget':budget,'epoch28_decision':decision,'epoch28_actual_execution':actual})
  old={'epochs':[{'epoch':27}],'execution_observed':{'actual_HTTP_decisions':885,'cumulative_bounded_native_process_attempts_including_qualification':28,'native_qualification_attempts':4},'rejection_ledger':oldlr}
  flags={key:False for key in s.FORBIDDEN_RESULT_FLAGS}
  new=copy.deepcopy(old);new['epochs'].append({**flags,'epoch':28,'kind':s.KIND,'status':m['status'],'manifest':mr,'results':rr,'engineering_qualified':False,'official_rank':None});new['execution_observed'].update(epoch28_actual_execution=actual,cumulative_bounded_native_process_attempts_including_qualification=29,native_qualification_attempts=5);new['epoch28_final']={**flags,'manifest':mr,'results':rr,'status':m['status'],'engineering_qualified':False,'official_rank':None,'goal_met':False,'fresh_confirmation_consumed':False,'all_unspent_slots_closed':True};new['rejection_ledger']=newlr;new['cumulative_budget_ledger']={'epoch28_budget':copy.deepcopy(budget)}
  rows={f.relative_to(self.root).as_posix():c.ref(self.root,f.relative_to(self.root).as_posix()) for f in self.root.rglob('*') if f.is_file()}
  return rows,new,old,m
 def test_honest_failed_final_allowed(self):
  rows,new,old,m=self.final_fixture();s.checked_final(self.root,rows,new,old,{})
 def resync_final(self,new,m):
  def put(path,value):self.write(path,c.encoded(value,pretty=True));return c.ref(self.root,path)
  r=c.parse(self.root/(s.E+'RESULTS.json'));r.update(status=m.get('status'),engineering_qualified=m['engineering_qualified'],actual_execution=m['actual_execution']);rr=put(s.E+'RESULTS.json',r);m['results']=rr
  a=c.parse(self.root/m['independent_report']['path']);a['engineering_qualified']=m['engineering_qualified'];a['evidence']['results']=rr;a['evidence']['execution']=c.ref(self.root,s.E+'execution.json')
  m['independent_report']=put(m['independent_report']['path'],a)
  l=c.parse(self.root/new['rejection_ledger']['path']);l['epoch28_actual_execution']=m['actual_execution'];l['epoch28_budget']['worker_attempts_used']=m['actual_execution']['worker_attempts'];l['epoch28_decision'].update(status=m.get('status'),engineering_qualified=m['engineering_qualified'],results=rr)
  for rec in l['rejections']:
   if rec.get('epoch')==28:rec.update(status=m.get('status'),results=rr)
  if 'epoch28_qualification' in l:l['epoch28_qualification'].update(status=m.get('status'),results=rr)
  new['rejection_ledger']=put(new['rejection_ledger']['path'],l);new['execution_observed']['epoch28_actual_execution']=m['actual_execution'];new['cumulative_budget_ledger']['epoch28_budget']=copy.deepcopy(l['epoch28_budget']);mr=put(s.E+'EPOCH_MANIFEST.json',m)
  new['epoch28_final'].update(manifest=mr,results=rr,status=m.get('status'),engineering_qualified=m['engineering_qualified']);new['epochs'][-1].update(manifest=mr,results=rr,status=m.get('status'),engineering_qualified=m['engineering_qualified'])
  return {f.relative_to(self.root).as_posix():c.ref(self.root,f.relative_to(self.root).as_posix()) for f in self.root.rglob('*') if f.is_file()}
 def test_receipt_erasure_with_all_claim_refs_rebound(self):
  rows,new,old,m=self.final_fixture();m['actual_execution']['worker_attempts']=0;m['actual_execution']['verified_worker_starts']=0
  rows=self.resync_final(new,m);new['execution_observed'].update(cumulative_bounded_native_process_attempts_including_qualification=28,native_qualification_attempts=4)
  self.rejects(s.checked_final,self.root,rows,new,old,{})
 def test_missing_current_rejection_with_refs_rebound(self):
  rows,new,old,m=self.final_fixture();l=c.parse(self.root/new['rejection_ledger']['path']);l['rejections']=l['rejections'][:1];self.write(new['rejection_ledger']['path'],c.encoded(l,pretty=True));rows=self.resync_final(new,m);self.rejects(s.checked_final,self.root,rows,new,old,{})
 def test_success_requires_qualification_record(self):
  rows,new,old,m=self.final_fixture();m.update(status='ENGINEERING_QUALIFIED',engineering_qualified=True)
  l=c.parse(self.root/new['rejection_ledger']['path']);l['rejections']=l['rejections'][:1];self.write(new['rejection_ledger']['path'],c.encoded(l,pretty=True));rows=self.resync_final(new,m);self.rejects(s.checked_final,self.root,rows,new,old,{})
  l=c.parse(self.root/new['rejection_ledger']['path']);q={k:False for k in s.FORBIDDEN_RESULT_FLAGS};q.update(epoch=28,status=m['status'],engineering_qualified=True,official_rank=None,reason='Authored engineering checks passed.',results=m['results']);l['epoch28_qualification']=q;self.write(new['rejection_ledger']['path'],c.encoded(l,pretty=True));rows=self.resync_final(new,m);s.checked_final(self.root,rows,new,old,{})
 def test_historical_raw_evidence_rejected(self):
  rows,new,old,m=self.final_fixture();a=c.parse(self.root/m['independent_report']['path']);historical=c.P+'epoch27/runs/dev/raw.json';self.write(historical,(self.root/(s.E+'runs/engineering/raw.json')).read_bytes());a['evidence']['raw']=c.ref(self.root,historical);self.write(m['independent_report']['path'],c.encoded(a,pretty=True));rows=self.resync_final(new,m);self.rejects(s.checked_final,self.root,rows,new,old,{})
 def test_early_failure_final_preserves_unknowns(self):
  rows,new,old,m=self.final_fixture();(self.root/(s.E+'runs/engineering/raw.json')).unlink()
  e=c.parse(self.root/(s.E+'execution.json'));e.update(status='WORKER_FAILED_OR_TIMEOUT',verified_worker_starts=0,uncertain_start=True,raw_bytes=None,raw_sha256=None,raw_operation_counters=None,launcher_error={'message':'Popen failed'},exit_code=None,raw_operation_counters_source='UNKNOWN',operation_counts_complete=False,backend_execution_since_checkpoint='UNKNOWN')
  self.write(s.E+'execution.json',c.encoded(e,pretty=True));m.update(status='FAILED_ENGINEERING_EXECUTION',actual_execution=s.derive_actual(None,e))
  a=c.parse(self.root/m['independent_report']['path']);a['evidence']['raw']=None;self.write(m['independent_report']['path'],c.encoded(a,pretty=True));rows=self.resync_final(new,m);s.checked_final(self.root,rows,new,old,{})
 def partial_final_fixture(self):
  rows,new,old,m=self.final_fixture();full=self.root/(s.E+'runs/engineering/raw.json');partial=self.root/(s.E+'runs/engineering/raw.partial.json');full.rename(partial);raw=c.parse(partial);partialref=c.ref(self.root,s.E+'runs/engineering/raw.partial.json')
  e=c.parse(self.root/(s.E+'execution.json'));e.update(status='WORKER_FAILED_OR_TIMEOUT',raw_bytes=None,raw_sha256=None,partial_raw_bytes=partialref['bytes'],partial_raw_sha256=partialref['sha256'],raw_operation_counters_source='raw.partial.json',operation_counts_complete=False,backend_execution_since_checkpoint='UNKNOWN',exit_code=-9)
  self.write(s.E+'execution.json',c.encoded(e,pretty=True));m.update(status='FAILED_ENGINEERING_EXECUTION',actual_execution=s.derive_actual(raw,e))
  a=c.parse(self.root/m['independent_report']['path']);a['evidence']['raw']=partialref;self.write(m['independent_report']['path'],c.encoded(a,pretty=True));rows=self.resync_final(new,m)
  return rows,new,old,m
 def test_partial_failure_retains_known_counters_and_unknown_tail(self):
  rows,new,old,m=self.partial_final_fixture();s.checked_final(self.root,rows,new,old,{})
  self.assertEqual(m['actual_execution']['native_systemOne_requests'],8);self.assertFalse(m['actual_execution']['operation_counts_complete']);self.assertEqual(m['actual_execution']['backend_execution_since_checkpoint'],'UNKNOWN');self.assertEqual(m['actual_execution']['raw_operation_counters_source'],'raw.partial.json')
 def test_partial_seal_mismatch_rejected(self):
  rows,new,old,m=self.partial_final_fixture();e=c.parse(self.root/(s.E+'execution.json'));e['partial_raw_sha256']='0'*64;self.write(s.E+'execution.json',c.encoded(e,pretty=True));rows=self.resync_final(new,m);self.rejects(s.checked_final,self.root,rows,new,old,{})
 def test_known_partial_cannot_be_hidden_as_absent(self):
  rows,new,old,m=self.partial_final_fixture();a=c.parse(self.root/m['independent_report']['path']);a['evidence']['raw']=None;self.write(m['independent_report']['path'],c.encoded(a,pretty=True));rows=self.resync_final(new,m);self.rejects(s.checked_final,self.root,rows,new,old,{})
 def test_partial_cannot_be_relabelled_complete(self):
  rows,new,old,m=self.partial_final_fixture();e=c.parse(self.root/(s.E+'execution.json'));e.update(raw_operation_counters_source='raw.json',operation_counts_complete=True,backend_execution_since_checkpoint='NOT_APPLICABLE_FINAL_RAW');raw=c.parse(self.root/(s.E+'runs/engineering/raw.partial.json'));self.rejects(s.derive_actual,raw,e)
 def test_malformed_final_uses_sealed_partial_but_valid_final_takes_precedence(self):
  rows,new,old,m=self.partial_final_fixture();fullpath=s.E+'runs/engineering/raw.json';self.write(fullpath,b'{"interrupted":');fullref=c.ref(self.root,fullpath)
  e=c.parse(self.root/(s.E+'execution.json'));e.update(raw_bytes=fullref['bytes'],raw_sha256=fullref['sha256']);self.write(s.E+'execution.json',c.encoded(e,pretty=True));partial=c.parse(self.root/(s.E+'runs/engineering/raw.partial.json'));m['actual_execution']=s.derive_actual(partial,e);rows=self.resync_final(new,m);s.checked_final(self.root,rows,new,old,{})
  self.assertFalse(m['actual_execution']['operation_counts_complete']);self.assertEqual(m['actual_execution']['backend_execution_since_checkpoint'],'UNKNOWN')
  self.write(fullpath,b'{}');fullref=c.ref(self.root,fullpath);e.update(raw_bytes=fullref['bytes'],raw_sha256=fullref['sha256']);self.write(s.E+'execution.json',c.encoded(e,pretty=True));rows=self.resync_final(new,m);self.rejects(s.checked_final,self.root,rows,new,old,{})
 def test_selected_partial_with_malformed_final_cannot_claim_complete_after_rebinding(self):
  rows,new,old,m=self.partial_final_fixture();fullpath=s.E+'runs/engineering/raw.json';self.write(fullpath,b'{"interrupted":');fullref=c.ref(self.root,fullpath)
  e=c.parse(self.root/(s.E+'execution.json'));e.update(raw_bytes=fullref['bytes'],raw_sha256=fullref['sha256'],raw_operation_counters_source='raw.json',operation_counts_complete=True,backend_execution_since_checkpoint='NOT_APPLICABLE_FINAL_RAW');self.write(s.E+'execution.json',c.encoded(e,pretty=True));partial=c.parse(self.root/(s.E+'runs/engineering/raw.partial.json'));m['actual_execution']=s.derive_actual(partial,e);rows=self.resync_final(new,m);self.rejects(s.checked_final,self.root,rows,new,old,{})
 def test_known_partial_counters_cannot_hide_behind_malformed_final_unknown(self):
  rows,new,old,m=self.partial_final_fixture();fullpath=s.E+'runs/engineering/raw.json';self.write(fullpath,b'{"interrupted":');fullref=c.ref(self.root,fullpath)
  e=c.parse(self.root/(s.E+'execution.json'));e.update(raw_bytes=fullref['bytes'],raw_sha256=fullref['sha256'],raw_operation_counters=None,raw_operation_counters_source='UNKNOWN',operation_counts_complete=False,backend_execution_since_checkpoint='UNKNOWN');self.write(s.E+'execution.json',c.encoded(e,pretty=True));m['actual_execution']=s.derive_actual(None,e)
  a=c.parse(self.root/m['independent_report']['path']);a['evidence']['raw']=fullref;self.write(m['independent_report']['path'],c.encoded(a,pretty=True));rows=self.resync_final(new,m);self.rejects(s.checked_final,self.root,rows,new,old,{})
 def test_continuation_budget_used_erasure_rejected(self):
  rows,new,old,m=self.final_fixture();new['cumulative_budget_ledger']['epoch28_budget']['worker_attempts_used']=0;self.rejects(s.checked_final,self.root,rows,new,old,{})
 def test_continuation_final_verdict_flip_rejected(self):
  rows,new,old,m=self.final_fixture();new['epoch28_final'].update(engineering_qualified=True,status='ENGINEERING_QUALIFIED');self.rejects(s.checked_final,self.root,rows,new,old,{})
 def test_last_epoch_benchmark_claim_rejected(self):
  rows,new,old,m=self.final_fixture();new['epochs'][-1].update(benchmark_accepted=True,engineering_qualified=True);self.rejects(s.checked_final,self.root,rows,new,old,{})
 def test_historical_execution_counter_erasure(self):
  rows,new,old,m=self.final_fixture();new['execution_observed'].pop('actual_HTTP_decisions');self.rejects(s.checked_final,self.root,rows,new,old,{})
 def test_cumulative_attempt_counter_inflation(self):
  rows,new,old,m=self.final_fixture();new['execution_observed']['native_qualification_attempts']+=1;self.rejects(s.checked_final,self.root,rows,new,old,{})
 def test_rejection_outcomes_erasure(self):
  rows,new,old,m=self.final_fixture();path=s.E+'REJECTION_LEDGER.json';self.write(path,c.encoded({'champion':'native104','rejections':[]}));rows[path]=c.ref(self.root,path);new['rejection_ledger']=rows[path];self.rejects(s.checked_final,self.root,rows,new,old,{})
 def test_exposed_dev_history_erasure(self):
  before={'exposed_development_sets':[{'epoch':1}]};after={'exposed_development_sets':[]};self.rejects(s.preserve_history,before,after,s.FINAL_MUTABLE)
 def test_historical_budget_erasure(self):
  before={'cumulative_budget_ledger':{'native_calls':2}};after={'cumulative_budget_ledger':{'native_calls':0}};self.rejects(s.preserve_history,before,after,s.FINAL_MUTABLE)
 def test_open_new_budget_rejected(self):
  rows,new,old,m=self.final_fixture();new['cumulative_budget_ledger']={'epoch28_workers_remaining':1};self.rejects(s.checked_final,self.root,rows,new,old,{})
 def test_missing_current_outcome_rejected(self):
  rows,new,old,m=self.final_fixture();m.pop('status');self.write(s.E+'EPOCH_MANIFEST.json',c.encoded(m,pretty=True));rows[s.E+'EPOCH_MANIFEST.json']=c.ref(self.root,s.E+'EPOCH_MANIFEST.json');new['epoch28_final']['manifest']=rows[s.E+'EPOCH_MANIFEST.json'];self.rejects(s.checked_final,self.root,rows,new,old,{})
 def test_captured_worker_cannot_be_erased(self):
  raw={'epoch':28,'kind':s.KIND,'source_checkpoint':c.BASE_COMMIT,'data_roles':{'train':[],'dev':[],'calibration':[],'confirmation':[]},'counters':{},'errors':[]}
  execution={'epoch':28,'kind':s.KIND,'worker_attempts_reserved':1,'verified_worker_starts':1,'uncertain_start':False,'owned_live_group_members':[],'owned_live_processes_closed':True,'wall_seconds_including_init_cleanup':1,'CPU_affinity':[0,1],'children_user_seconds':1,'children_system_seconds':0,'largest_child_peak_RSS_bytes':123,'allowed_further_epoch28_workers':0,'cleanup_errors':[],'launcher_error':None,'raw_operation_counters':{}}
  execution.update(raw_bytes=2,raw_sha256='1'*64,raw_operation_counters_source='raw.json',operation_counts_complete=True,backend_execution_since_checkpoint='NOT_APPLICABLE_FINAL_RAW')
  actual=s.derive_actual(raw,execution);self.assertEqual(actual['worker_attempts'],1);self.assertEqual(actual['verified_worker_starts'],1)
  execution['raw_operation_counters']={'worker_attempts':0};raw['counters']={'worker_attempts':0};self.rejects(s.derive_actual,raw,execution)
 def test_early_failure_counts_unknown(self):
  execution={'epoch':28,'kind':s.KIND,'status':'WORKER_FAILED_OR_TIMEOUT','worker_attempts_reserved':1,'verified_worker_starts':0,'uncertain_start':True,'owned_live_group_members':[],'owned_live_processes_closed':True,'wall_seconds_including_init_cleanup':1,'CPU_affinity':[0,1],'children_user_seconds':0,'children_system_seconds':0,'largest_child_peak_RSS_bytes':0,'allowed_further_epoch28_workers':0,'cleanup_errors':[],'launcher_error':{'message':'Popen failed'},'raw_operation_counters':None}
  execution.update(raw_operation_counters_source='UNKNOWN',operation_counts_complete=False,backend_execution_since_checkpoint='UNKNOWN')
  actual=s.derive_actual(None,execution);self.assertEqual(actual['worker_attempts'],1);self.assertEqual(actual['verified_worker_starts'],0);self.assertIsNone(actual['errors']);self.assertFalse(actual['operation_counts_complete']);self.assertEqual(actual['known_launcher_cleanup_errors'],1)

if __name__=='__main__':
 TEST_ROOT.mkdir(exist_ok=True);unittest.main()
