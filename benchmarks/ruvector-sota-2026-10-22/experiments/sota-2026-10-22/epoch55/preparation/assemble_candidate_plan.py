from pathlib import Path
import json,hashlib,os
W=Path(__file__).resolve().parent;R=W/'project';C=Path('/dev/shm/ruvector-e55-candidate');P='experiments/sota-2026-10-22/epoch55/';RT='experiments/sota-2026-10-22/runtime/epoch55/'
def h(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def ref(p):return {'path':str(p),'bytes':p.stat().st_size,'sha256':h(p)}
def put(p,x):
 p.parent.mkdir(parents=True,exist_ok=True)
 with p.open('x')as f:json.dump(x,f,indent=2,sort_keys=True,ensure_ascii=False,allow_nan=False);f.write('\n');f.flush();os.fsync(f.fileno())
def cp(src,target):
 b=src.read_bytes();p=R/target;p.parent.mkdir(parents=True,exist_ok=True)
 with p.open('xb')as f:f.write(b);f.flush();os.fsync(f.fileno())
packet=C/'FINAL_SOURCE_PACKET.v2.json';assert h(packet)=='c9274e5ff6aa458bccd9b1ad9beaf90a1221ba17f3d309b5a4e6bf66304690b6';v=json.loads(packet.read_text());assert v['epoch']==55 and v['file_count']==21
for row in v['files']:
 src=Path(row['path']);assert ref(src)=={k:row[k]for k in ('path','bytes','sha256')};cp(src,row['target'])
cp(packet,P+'candidate-source/FINAL_SOURCE_PACKET.v2.json')
oldW='/dev/shm/ruvector-sota-2026-10-22/epoch54-6187205840a9'
def adapt(x):
 if isinstance(x,str):return x.replace(oldW,str(W)).replace('epoch54','epoch55')
 if isinstance(x,list):return [adapt(v)for v in x]
 if isinstance(x,dict):return {k:adapt(v)for k,v in x.items()}
 return x
p=adapt(json.loads((R/'experiments/sota-2026-10-22/epoch54/plan.json').read_text()));p['epoch']=55;p['source_checkpoint']='b27d25773a62ca72f38931f8a007ff0bedc0b89f';p['owner_ref']=ref(W/'owner.json');p['fixtures']=ref(R/(RT+'authored_fixtures.json'))
f=json.loads((R/(RT+'authored_fixtures.json')).read_text());p['roles']=f['roles'];p['phase_roles']={'engineering':{'case_ids':f['roles']['engineering'],'document_ids':[d['document_id']for d in f['documents']]}}
for key,name in [('worker_source','worker.py'),('supervisor_source','supervisor.py')]:p[key]=ref(R/(RT+name))
p['inherited_source_files']=[ref(R/(RT+n))for n in ['inherited_packing.py','inherited_reader.py','inherited_guards.py']]
c=json.loads((C/'SOURCE_CONTRACT.v2.json').read_text());p['metadata_search_policy']=c['metadata_search_policy'];p['engineering_hypothesis']=c['hypothesis']
p['metadata_only_preparation']={'observed_E55_denied_opens':6,'E54_historical_targets_remain':'UNKNOWN','policy_scope':'Remove only exact stat-proven absent standard interpreter ZIP search entry; all five suffix denies remain unchanged.','probe_ref':{'path':P+'preparation/metadata-diagnosis/METADATA_PROBE.actual.v1.json','bytes':16846,'sha256':'4e4ad1c754cd9b74658ab257bcbfa80a2bb434ae59aef52bf5cc7a5a78bc48e2'},'probe_native_tokenizer_BGE_typed_model_Gold_calls':0,'probe_invocations':1,'canonical_stat_capture_invocations':1}
p['minimum_pre_CLI_shared_cgroup_headroom_bytes']=3221225472;p['headroom_policy']='Root reads actual shared cgroup before consuming CLI; worker independently rechecks before search policy, versions, tokenizer/BGE/native. Filesystem free space never substitutes.'
p['engineering_acceptance_gates']+=['exact one absent interpreter ZIP search entry removed with unchanged suffix deny policy','zero denied model/archive suffix open attempts during native qualification; all attempts recorded bounded by64events']
put(R/(P+'plan.json'),p)
put(W/'CANDIDATE_PLAN_ADOPTION.actual.v1.json',{'epoch':55,'packet':ref(packet),'plan':ref(R/(P+'plan.json')),'all21files_full_hash_verified_and_physically_copied':True,'actual_scientific_calls':0})
print(json.dumps({'plan':ref(R/(P+'plan.json')),'roles':p['roles']}))
