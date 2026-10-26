"""Metadata-only source sealing and exact replay publication. Root invokes modes."""
import sys
sys.dont_write_bytecode=True
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
import argparse,copy,json,hashlib,importlib.util
import publication_common as c
P='experiments/sota-2026-10-22/epoch46/'
PROTECTED={'epoch','source_checkpoint','source_freeze','pins','publication_contract','source_bindings_ready','operational_binding'}
EXTERNAL={'joined_gold':str(c.W/'private/DEV_GOLD_JOINED.json'),'private_features':str(c.W/'private/DEV_FEATURES.json')}
PUBLIC_ABSOLUTE={'data_admission':str(c.W/'project/experiments/sota-2026-10-22/audit/epoch46/DATA_ADMISSION.json'),'protocol':str(c.W/'project/experiments/sota-2026-10-22/runtime/epoch46/PROTOCOL.json')}

def publication_contract(root,contract):
 c.require(c.same(root['publication_contract'],contract),'Publication schema must equal ROOT')
 c.require(c.same(contract['external_custody_evidence_paths'],EXTERNAL)and c.same(contract['public_absolute_evidence_paths'],PUBLIC_ABSOLUTE),'Only exact ROOT two external/public role maps')
 c.require(set(contract['status_ledger_classification'])==set(contract['allowed_statuses']),'Every ROOT status has frozen ledger classification')
 c.require(set(contract['status_ledger_classification'].values())<={'rejections','preparation_blocks','diagnostic_passes_on_hold'},'Only typed outcome collections')
 return contract

def public_ref(project,r):
 c.require(type(r)is dict and set(r)=={'path','bytes','sha256'},'Consumer references have exactly three canonical keys');canonical_reference(r)
 p=c.relative(r['path']);b=c.checked(project/p,r);c.public_text(p,b);return b
def public_pin(project,path):
 c.relative(path);ref=c.pin(project/path);ref['path']=path;return ref
def verify_pins(project,plan):
 freeze=json.loads(public_ref(project,plan['source_freeze']));c.require(freeze['epoch']==46 and freeze['source_checkpoint']==c.BASE,'Exact source freeze')
 for r in freeze['files']:public_ref(project,r)
 return freeze

def verify_native_raw_plan_contract(project,plan,freeze):
 """Call only the reviewed pure-stdlib identity validator on the RAW plan.

 This checks public identity metadata; it grants no Node/native/model capability.
 The validator is an exact canonical SOURCE member, never a runtime-view patch.
 """
 ref=plan['native_plan_contract_source'];canonical_reference(ref)
 c.require(set(ref)=={'path','bytes','sha256'}and any(c.same(ref,r)for r in freeze['files']),'Raw-plan validator must be source-frozen')
 raw=public_ref(project,ref);path=project/ref['path']
 spec=importlib.util.spec_from_file_location('e46_frozen_native_identity_contract',path)
 module=importlib.util.module_from_spec(spec);exec(compile(raw,str(path),'exec'),module.__dict__)
 proof=module.validate_native_plan_contract(plan)
 c.require(type(proof)is dict and proof.get('checks_passed')is True and proof.get('execution_authorized')is False and type(proof.get('target_calls'))is int and proof['target_calls']==0,'Pure metadata identity-contract proof required')
 c.require(type(proof.get('documents'))is int and proof['documents']==4 and type(proof.get('cases'))is int and proof['cases']==12 and c.same(proof.get('case_ids_by_document'),plan['case_ids_by_document']),'Exact raw frozen four-document/twelve-case identity map')
 return proof
def merge_fragments(rows):
 merged={'plan_fields':{},'required_refs':{},'inherited_source_refs':[]};inherited={}
 for d in rows:
  c.require(set(d)>=set(merged),'Fragment schema')
  for group in('plan_fields','required_refs'):
   for k,v in d[group].items():
    c.require(k not in merged[group]or c.same(merged[group][k],v),'Typed fragment collision: '+k);merged[group][k]=copy.deepcopy(v)
  for r in d['inherited_source_refs']:
   c.relative(r['path']);c.require(r['path']not in inherited or c.same(inherited[r['path']],r),'Inherited source collision');inherited[r['path']]=r
 merged['inherited_source_refs']=list(inherited.values());return merged
def all_current_sources(project):
 rows=[]
 for root in c.ROOTS:
  base=project/root
  if not base.exists():continue
  c.require(not base.is_symlink(),'Source root symlink')
  for p in sorted(base.rglob('*')):
   c.require(not p.is_symlink(),'Source symlink');
   if p.is_file():
    r=str(p.relative_to(project));b=c.body(p);c.public_text(r,b);rows.append({'path':r,'bytes':len(b),'sha256':c.sha(b)})
 return rows
def canonical_reference(row):
 c.require(type(row)is dict and set(row)in({'path','bytes','sha256'},{'path','bytes','sha256','actual_git_blob_sha1'}),'Exact public reference and separate Git provenance')
 c.require(type(row['path'])is str and type(row['bytes'])is int and row['bytes']>=0 and type(row['sha256'])is str and len(row['sha256'])==64 and all(x in '0123456789abcdef'for x in row['sha256']),'Typed canonical public reference')
 c.relative(row['path']);canonical={k:row[k]for k in('path','bytes','sha256')}
 git=row.get('actual_git_blob_sha1')
 if 'actual_git_blob_sha1'in row:c.require(type(git)is str and len(git)==40 and all(x in '0123456789abcdef'for x in git),'Typed Git provenance')
 return canonical,git

def canonical_freeze_references(project,current,inherited):
 files={};provenance=[]
 for original in current:
  row,git=canonical_reference(original);c.require(git is None,'Current source inventory has canonical reference fields only')
  c.require(row['path']not in files,'Duplicate current source path');files[row['path']]=row
 for original in inherited:
  row,git=canonical_reference(original);body=public_ref(project,row)
  c.require(row['path']not in files or c.same(files[row['path']],row),'Inherited canonical source collision')
  if git is not None:
   actual=hashlib.sha1(b'blob '+str(len(body)).encode()+b'\0'+body).hexdigest()
   c.require(actual==git,'Inherited source actual Git blob identity')
   provenance.append({'path':row['path'],'actual_git_blob_sha1':git,'payload_git_blob_identity_verified':True})
  files[row['path']]=row
 return sorted(files.values(),key=lambda row:row['path']),sorted(provenance,key=lambda row:row['path'])

def freeze_source(project,x):
 c.require_operational();c.require(x['source_bindings_ready']is True,'Source admission still disabled');root=json.loads(public_ref(project,x['root_contract']));c.require(root['epoch']==46,'E46 ROOT');publication_contract(root,x['publication_contract'])
 c.require(root['operational_binding']['sha256']==c.OPERATIONAL_SHA and c.sha(public_ref(project,root['operational_binding']))==c.OPERATIONAL_SHA,'Final ROOT exact operational binding');c.require(root['base_commit']==c.BASE and root['workdir']==str(c.W)and root['owner_sha256']==c.OWNER_SHA,'Final ROOT exact base/workdir/owner')
 c.require(c.same(x['required_roles'],root['source_admission_contract']['required_roles'])and c.same(x['required_review_flags'],root['source_admission_contract']['required_review_flags']),'Exact ROOT SOURCE-before-DATA role/flag contract')
 fragments=[json.loads(c.checked(r['local_path'],r))for r in x['fragments']];m=merge_fragments(fragments)
 c.require(not(PROTECTED&set(m['plan_fields'])),'Protected plan field collision')
 c.require(m['plan_fields']['kind']==root['kind'],'Same new GGUF diagnostic kind')
 if 'root_contract'in m['plan_fields']:c.require(c.same(m['plan_fields']['root_contract'],x['root_contract']),'ROOT fragment mismatch')
 c.require(c.same(m['plan_fields']['worker_slot_reservation'],root['worker_slot_reservation']),'Final ROOT and plan must burn the same exact worker slot')
 for role in x['required_roles']:c.require(role in m['required_refs'],'Missing required source role '+role)
 for r in m['required_refs'].values():public_ref(project,r)
 for r in m['inherited_source_refs']:public_ref(project,canonical_reference(r)[0])
 review=json.loads(public_ref(project,x['independent_source_review']))
 for k in x['required_review_flags']:c.require(review.get(k)is True,'Source barrier missing '+k)
 files=all_current_sources(project);expected=review['files'];review_path=x['independent_source_review']['path'];c.require(c.same([r for r in files if r['path']!=review_path],expected),'Exhaustive integrated source inventory differs (review self excluded)')
 files,inherited_provenance=canonical_freeze_references(project,files,m['inherited_source_refs'])
 c.require(not any(r['path']in(P+'plan.json',P+'SOURCE_FREEZE.json')for r in files),'Fresh plan/freeze paths required')
 freeze={'schema_version':1,'epoch':46,'source_checkpoint':c.BASE,'files':files,'inherited_source_provenance':inherited_provenance,'source_admission_is_not_execution':True};raw=c.encoded(freeze);ref={'path':P+'SOURCE_FREEZE.json','bytes':len(raw),'sha256':c.sha(raw)}
 plan={**m['plan_fields'],'epoch':46,'source_checkpoint':c.BASE,'root_contract':x['root_contract'],'source_freeze':ref,'required_refs':m['required_refs'],'source_bindings_ready':True,'operational_binding':root['operational_binding'],'publication_contract':copy.deepcopy(x['publication_contract'])}
 c.require(type(plan.get('schema_version'))is int and plan['schema_version']==1 and plan.get('phase')=='dev'and plan.get('kind')==root['kind'],'Exact plan envelope');c.require(plan.get('data_roles',{}).get('confirmation')==[],'No CONF bank');c.require(plan.get('used_confirmation_identities',[])==[],'No used CONF')
 verify_native_raw_plan_contract(project,plan,freeze)
 c.write(project/ref['path'],raw);c.write(project/(P+'plan.json'),c.encoded(plan));return {'plan':public_pin(project,P+'plan.json'),'freeze':ref}
def checked_evidence(project,plan,key,r):
 private=plan['publication_contract']['external_custody_evidence_paths']
 if key in private:
  c.require(set(r)=={'path','bytes','sha256'}and r['path']==private[key],'Only exact two private custody descriptors');c.require(Path(r['path']).is_absolute()and not Path(r['path']).is_relative_to(project),'Private custody outside public project');c.checked(r['path'],r);return r
 public_abs=plan['publication_contract']['public_absolute_evidence_paths']
 if key in public_abs and Path(r['path']).is_absolute():
  declared=Path(public_abs[key]);c.require(r['path']==str(declared)and declared.is_relative_to(project),'Exact role-bound canonical public absolute path');rel=c.relative(str(declared.relative_to(project)));public_ref(project,{**r,'path':rel});return r
 public_ref(project,r);return r
def setup(project,x):
 c.require_operational();plan=json.loads(public_ref(project,x['plan']));c.require(plan['operational_binding']['sha256']==c.OPERATIONAL_SHA,'Frozen plan current operational binding');verify_pins(project,plan);replay=json.loads(public_ref(project,x['replay']))
 publication_contract(json.loads(public_ref(project,plan['root_contract'])),plan['publication_contract'])
 for key,r in replay.get('evidence',{}).items():
  if r is not None:checked_evidence(project,plan,key,r)
 c.require(replay['status']in plan['publication_contract']['allowed_statuses'],'Source-frozen status map');c.require(replay.get('used_confirmation_identities',[])==[],'No CONF exposure')
 for key in plan['publication_contract']['always_false_flags']:c.require(replay[key]is False,'Diagnostic HOLD flag '+key)
 c.require(replay.get('benchmark_accuracy')is None,'No benchmark placement/accuracy')
 c.require(replay.get('official_rank')is None,'No official rank')
 return plan,replay
def ledger_append(project,plan,replay,x,result_ref):
 old=json.loads(public_ref(project,x['prior_ledger']));new=copy.deepcopy(old);collection=plan['publication_contract']['status_ledger_classification'][replay['status']]
 c.require(not any(isinstance(r,dict)and r.get('epoch')==46 for k in('rejections','preparation_blocks','diagnostic_passes_on_hold')for r in old.get(k,[])),'One E46 outcome only')
 row={'epoch':46,'status':replay['status'],'results':result_ref,'scope':'DEV-only diagnostic; source-frozen design is prospective, completed operations are captured in RESULTS.actual_execution. No confirmation, promotion, submission or benchmark placement.'}
 new.setdefault(collection,[]).append(row);new['epoch46_decision']={'status':replay['status'],'results':result_ref,'native104_champion_preserved':True,'confirmation_used':[],'official_SOTA_verified':False}
 for k,v in old.items():c.require(c.same(new[k][:-1],v)if k==collection else c.same(new[k],v),'Every prior ledger field/type preserved')
 c.require(new.get('official_sota_established')is False and c.same(new['champion'],old['champion']),'No official/champion change')
 c.write(project/(P+'REJECTION_LEDGER.json'),c.encoded(new));return public_pin(project,P+'REJECTION_LEDGER.json')
def results(project,x):
 plan,replay=setup(project,x);review=json.loads(public_ref(project,x['independent_result_review']));c.require(review.get('checks_passed')is True and review.get('replay')==x['replay'],'Independent exact result review')
 addition=copy.deepcopy(x['publication_checkpoint']);c.require(addition['scientific_source_changed']is False and addition['source_frozen_replay_preserved']is True,'Transport-only addition')
 out=copy.deepcopy(replay);c.require('publication_checkpoint'not in out,'Not previously published');out['publication_checkpoint']=addition;c.require(all(c.same(out[k],v)for k,v in replay.items()),'Every evaluated field/type exact')
 c.require(x['used_confirmation']['used_confirmation_identities']==[],'No CONF');c.write(project/(P+'RESULTS.json'),c.encoded(out));result_ref=c.pin(project/(P+'RESULTS.json'));result_ref['path']=P+'RESULTS.json';ledger=ledger_append(project,plan,replay,x,result_ref);c.write(project/(P+'LEARNINGS.json'),c.encoded(x['learnings']));c.write(project/(P+'USED_CONFIRMATION.json'),c.encoded(x['used_confirmation']));return {'results':result_ref,'ledger':ledger}
def manifest(project,x):
 plan,replay=setup(project,x);results=json.loads(public_ref(project,x['results']));c.require(all(c.same(results[k],v)for k,v in replay.items()),'Manifest cannot rewrite replay')
 c.require(set(results)==set(replay)|{'publication_checkpoint'},'RESULTS adds only publication_checkpoint')
 binding=json.loads(public_ref(project,x['binding']));c.require(binding.get('publication_binding_passed')is True,'Exact independently checked metadata binding')
 report=json.loads(public_ref(project,x['independent_final_review']));c.require(report.get('checks_passed')is True and report.get('results')==x['results'],'Final exact result approval')
 files=all_current_sources(project);source={'schema_version':1,'epoch':46,'source_checkpoint':c.BASE,'frozen_source':plan['source_freeze'],'files':files,'scientific_source_changed':False};c.write(project/(P+'SOURCE_MANIFEST.json'),c.encoded(source))
 sm=public_pin(project,P+'SOURCE_MANIFEST.json')
 epoch={'schema_version':1,'epoch':46,'source_checkpoint':c.BASE,'plan':x['plan'],'results':x['results'],'replay':x['replay'],'binding':x['binding'],'independent_final_review':x['independent_final_review'],'source_manifest':sm,'files':all_current_sources(project),'no_project_additions_after_manifest':True};c.write(project/(P+'EPOCH_MANIFEST.json'),c.encoded(epoch));return public_pin(project,P+'EPOCH_MANIFEST.json')

def preflight(project,x):
 """Read-only metadata closure check, invoked on ACTUAL frozen output before SOURCE."""
 c.require_operational();plan=json.loads(public_ref(project,x['plan']));freeze=verify_pins(project,plan)
 c.require(type(plan.get('schema_version'))is int and plan['schema_version']==1 and plan.get('epoch')==46 and plan.get('phase')=='dev','Exact frozen plan envelope')
 for row in freeze['files']:c.require(set(row)=={'path','bytes','sha256'},'Every frozen consumer reference has exactly three keys');canonical_reference(row)
 c.require(len({r['path']for r in freeze['files']})==len(freeze['files']),'Unique frozen source references')
 for row in plan['required_refs'].values():public_ref(project,row)
 root=json.loads(public_ref(project,plan['root_contract']));publication_contract(root,plan['publication_contract']);c.require(c.same(plan['worker_slot_reservation'],root['worker_slot_reservation']),'Same source capability')
 identity=verify_native_raw_plan_contract(project,plan,freeze)
 return {'schema_version':1,'epoch':46,'checks_passed':True,'actual_source_freeze_reference_closure_verified':True,'actual_raw_native_plan_contract_verified':True,'raw_native_plan_contract_receipt':identity,'source_freeze':plan['source_freeze'],'plan':x['plan'],'source_rows':len(freeze['files']),'private_or_selected_new_case_bodies_read':0,'inherited_public_payload_hashing_may_include_prior_exposed_DEV_bank':True,'scientific_functions_called':0,'writes':0}

if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('mode',choices=('freeze','preflight','results','manifest'));p.add_argument('--project',type=Path,required=True);p.add_argument('--input',type=Path,required=True);p.add_argument('--expected-input-sha',required=True);p.add_argument('--operational-binding',type=Path,required=True);p.add_argument('--expected-operational-binding-sha',required=True);a=p.parse_args();c.configure(a.operational_binding,a.expected_operational_binding_sha);raw=c.body(a.input);c.require(c.sha(raw)==a.expected_input_sha,'Exact mode input');x=json.loads(raw);project=a.project.resolve();print(json.dumps({'freeze':freeze_source,'preflight':preflight,'results':results,'manifest':manifest}[a.mode](project,x),sort_keys=True))
