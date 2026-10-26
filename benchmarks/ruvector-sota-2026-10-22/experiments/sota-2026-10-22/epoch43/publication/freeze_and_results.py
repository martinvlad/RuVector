"""Metadata-only source sealing and exact replay publication. Root invokes modes."""
import sys
sys.dont_write_bytecode=True
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
import argparse,copy,json
import publication_common as c
P='experiments/sota-2026-10-22/epoch43/'
PROTECTED={'epoch','source_checkpoint','source_freeze','pins','publication_contract','source_bindings_ready','operational_binding'}
EXTERNAL={'joined_gold':str(c.W/'private/DEV_GOLD_JOINED.json'),'private_features':str(c.W/'private/DEV_FEATURES.json')}
PUBLIC_ABSOLUTE={'data_admission':str(c.W/'project/experiments/sota-2026-10-22/audit/epoch43/DATA_ADMISSION.json'),'protocol':str(c.W/'project/experiments/sota-2026-10-22/runtime/epoch43/PROTOCOL.json')}

def publication_contract(root,contract):
 c.require(c.same(root['publication_contract'],contract),'Publication schema must equal ROOT')
 c.require(c.same(contract['external_custody_evidence_paths'],EXTERNAL)and c.same(contract['public_absolute_evidence_paths'],PUBLIC_ABSOLUTE),'Only exact ROOT two external/public role maps')
 c.require(set(contract['status_ledger_classification'])==set(contract['allowed_statuses']),'Every ROOT status has frozen ledger classification')
 c.require(set(contract['status_ledger_classification'].values())<={'rejections','preparation_blocks','diagnostic_passes_on_hold'},'Only typed outcome collections')
 return contract

def public_ref(project,r):
 p=c.relative(r['path']);b=c.checked(project/p,r);c.public_text(p,b);return b
def verify_pins(project,plan):
 freeze=json.loads(public_ref(project,plan['source_freeze']));c.require(freeze['epoch']==43 and freeze['source_checkpoint']==c.BASE,'Exact source freeze')
 for r in freeze['files']:public_ref(project,r)
 return freeze
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
def freeze_source(project,x):
 c.require_operational();c.require(x['source_bindings_ready']is True,'Source admission still disabled');root=json.loads(public_ref(project,x['root_contract']));c.require(root['epoch']==43,'E43 ROOT');publication_contract(root,x['publication_contract'])
 c.require(root['operational_binding']['sha256']==c.OPERATIONAL_SHA and c.sha(public_ref(project,root['operational_binding']))==c.OPERATIONAL_SHA,'Final ROOT exact operational binding');c.require(root['base_commit']==c.BASE and root['workdir']==str(c.W)and root['owner_sha256']==c.OWNER_SHA,'Final ROOT exact base/workdir/owner')
 c.require(c.same(x['required_roles'],root['source_admission_contract']['required_roles'])and c.same(x['required_review_flags'],root['source_admission_contract']['required_review_flags']),'Exact ROOT SOURCE-before-DATA role/flag contract')
 fragments=[json.loads(c.checked(r['local_path'],r))for r in x['fragments']];m=merge_fragments(fragments)
 c.require(not(PROTECTED&set(m['plan_fields'])),'Protected plan field collision')
 c.require(m['plan_fields']['kind']==root['kind'],'Same new GGUF diagnostic kind')
 if 'root_contract'in m['plan_fields']:c.require(c.same(m['plan_fields']['root_contract'],x['root_contract']),'ROOT fragment mismatch')
 c.require(c.same(m['plan_fields']['worker_slot_reservation'],root['worker_slot_reservation']),'Final ROOT and plan must burn the same exact worker slot')
 for role in x['required_roles']:c.require(role in m['required_refs'],'Missing required source role '+role)
 for r in [*m['required_refs'].values(),*m['inherited_source_refs']]:public_ref(project,r)
 review=json.loads(public_ref(project,x['independent_source_review']))
 for k in x['required_review_flags']:c.require(review.get(k)is True,'Source barrier missing '+k)
 files=all_current_sources(project);expected=review['files'];review_path=x['independent_source_review']['path'];c.require(c.same([r for r in files if r['path']!=review_path],expected),'Exhaustive integrated source inventory differs (review self excluded)')
 files.extend(r for r in m['inherited_source_refs']if r['path']not in {q['path']for q in files});files=sorted(files,key=lambda r:r['path'])
 c.require(not any(r['path']in(P+'plan.json',P+'SOURCE_FREEZE.json')for r in files),'Fresh plan/freeze paths required')
 freeze={'schema_version':1,'epoch':43,'source_checkpoint':c.BASE,'files':files,'source_admission_is_not_execution':True};raw=c.encoded(freeze);ref={'path':P+'SOURCE_FREEZE.json','bytes':len(raw),'sha256':c.sha(raw)}
 plan={**m['plan_fields'],'epoch':43,'source_checkpoint':c.BASE,'root_contract':x['root_contract'],'source_freeze':ref,'required_refs':m['required_refs'],'source_bindings_ready':True,'operational_binding':root['operational_binding'],'publication_contract':copy.deepcopy(x['publication_contract'])}
 c.require(plan.get('data_roles',{}).get('confirmation')==[],'No CONF bank');c.require(plan.get('used_confirmation_identities',[])==[],'No used CONF')
 c.write(project/ref['path'],raw);c.write(project/(P+'plan.json'),c.encoded(plan));return {'plan':c.pin(project/(P+'plan.json')),'freeze':ref}
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
 c.require(not any(isinstance(r,dict)and r.get('epoch')==43 for k in('rejections','preparation_blocks','diagnostic_passes_on_hold')for r in old.get(k,[])),'One E43 outcome only')
 row={'epoch':43,'status':replay['status'],'results':result_ref,'scope':'DEV-only diagnostic; source-frozen design is prospective, completed operations are captured in RESULTS.actual_execution. No confirmation, promotion, submission or benchmark placement.'}
 new.setdefault(collection,[]).append(row);new['epoch43_decision']={'status':replay['status'],'results':result_ref,'native104_champion_preserved':True,'confirmation_used':[],'official_SOTA_verified':False}
 for k,v in old.items():c.require(c.same(new[k][:-1],v)if k==collection else c.same(new[k],v),'Every prior ledger field/type preserved')
 c.require(new.get('official_sota_established')is False and c.same(new['champion'],old['champion']),'No official/champion change')
 c.write(project/(P+'REJECTION_LEDGER.json'),c.encoded(new));return c.pin(project/(P+'REJECTION_LEDGER.json'))
def results(project,x):
 plan,replay=setup(project,x);review=json.loads(public_ref(project,x['independent_result_review']));c.require(review.get('checks_passed')is True and review.get('replay')==x['replay'],'Independent exact result review')
 addition=copy.deepcopy(x['publication_checkpoint']);c.require(addition['scientific_source_changed']is False and addition['source_frozen_replay_preserved']is True,'Transport-only addition')
 out=copy.deepcopy(replay);c.require('publication_checkpoint'not in out,'Not previously published');out['publication_checkpoint']=addition;c.require(all(c.same(out[k],v)for k,v in replay.items()),'Every evaluated field/type exact')
 c.require(x['used_confirmation']['used_confirmation_identities']==[],'No CONF');c.write(project/(P+'RESULTS.json'),c.encoded(out));result_ref=c.pin(project/(P+'RESULTS.json'));result_ref['path']=P+'RESULTS.json';ledger=ledger_append(project,plan,replay,x,result_ref);c.write(project/(P+'LEARNINGS.json'),c.encoded(x['learnings']));c.write(project/(P+'USED_CONFIRMATION.json'),c.encoded(x['used_confirmation']));return {'results':result_ref,'ledger':ledger}
def manifest(project,x):
 plan,replay=setup(project,x);results=json.loads(public_ref(project,x['results']));c.require(all(c.same(results[k],v)for k,v in replay.items()),'Manifest cannot rewrite replay')
 binding=json.loads(public_ref(project,x['binding']));c.require(binding.get('publication_binding_passed')is True,'Exact independently checked metadata binding')
 report=json.loads(public_ref(project,x['independent_final_review']));c.require(report.get('checks_passed')is True and report.get('results')==x['results'],'Final exact result approval')
 files=all_current_sources(project);source={'schema_version':1,'epoch':43,'source_checkpoint':c.BASE,'frozen_source':plan['source_freeze'],'files':files,'scientific_source_changed':False};c.write(project/(P+'SOURCE_MANIFEST.json'),c.encoded(source))
 epoch={'schema_version':1,'epoch':43,'source_checkpoint':c.BASE,'plan':x['plan'],'results':x['results'],'replay':x['replay'],'binding':x['binding'],'independent_final_review':x['independent_final_review'],'source_manifest':c.pin(project/(P+'SOURCE_MANIFEST.json')),'files':all_current_sources(project),'no_project_additions_after_manifest':True};c.write(project/(P+'EPOCH_MANIFEST.json'),c.encoded(epoch));return c.pin(project/(P+'EPOCH_MANIFEST.json'))

if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('mode',choices=('freeze','results','manifest'));p.add_argument('--project',type=Path,required=True);p.add_argument('--input',type=Path,required=True);p.add_argument('--expected-input-sha',required=True);p.add_argument('--operational-binding',type=Path,required=True);p.add_argument('--expected-operational-binding-sha',required=True);a=p.parse_args();c.configure(a.operational_binding,a.expected_operational_binding_sha);raw=c.body(a.input);c.require(c.sha(raw)==a.expected_input_sha,'Exact mode input');x=json.loads(raw);project=a.project.resolve();print(json.dumps({'freeze':freeze_source,'results':results,'manifest':manifest}[a.mode](project,x),sort_keys=True))
