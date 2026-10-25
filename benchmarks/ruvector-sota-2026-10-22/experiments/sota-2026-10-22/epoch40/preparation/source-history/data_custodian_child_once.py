"""Once-only approved label-blind custodian; no semantic gold decoding or ML."""
from pathlib import Path
import argparse,hashlib,importlib.util,json,os,signal,sys,time,traceback
sys.dont_write_bytecode=True
W=Path('/tmp/ruvector-sota-2026-10-22/epoch40-2cf5aba60a05')
PLAN_SHA='1fa64499888e21c48075641643a8c013b19b57d0840912c5a69823305158f3fa'
OWNER_SHA='f18924b1456dcf51c461181c233ff4511cd3e479982f48b109a0e4126b5c3af0'
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def put(p,v):
 with Path(p).open('x')as f:json.dump(v,f,indent=2,allow_nan=False);f.write('\n');f.flush();os.fsync(f.fileno())
 d=os.open(Path(p).parent,os.O_RDONLY|os.O_DIRECTORY);os.fsync(d);os.close(d)
def owner():
 assert sha(W/'owner.json')==OWNER_SHA
 o=json.loads((W/'owner.json').read_text());a=Path('/proc/120232/stat').read_text().rsplit(')',1)[1].split();fd=Path('/proc/120232/fd/3');s=fd.stat()
 assert int(a[19])==27979422 and a[0]not in('Z','X')and time.time()<o['expires_unix']and not(W/'release.request').exists()
 assert (s.st_dev,s.st_ino)==(33,13626)and os.readlink(fd)=='/tmp/ruvector-sota-2026-10-22/exclusive.work.lock'
 assert os.sched_getaffinity(0)=={0,1}and os.sched_getaffinity(120232)=={0,1}
 assert Path('/proc/sys/kernel/random/boot_id').read_text().strip()=='4632fb06-b0ef-4df5-b72b-0e875bbad810'and Path('/proc/self/ns/pid').stat().st_ino==4026532200
 assert any(x.split()[1:5]==['FLOCK','ADVISORY','WRITE','120232']and tuple([int(v,16) for v in x.split()[5].split(':')[:2]]+[int(x.split()[5].split(':')[2])])==(os.major(s.st_dev),os.minor(s.st_dev),13626)for x in Path('/proc/locks').read_text().splitlines())
def ref(path):
 p=Path(path);return {'path':str(p),'bytes':p.stat().st_size,'sha256':sha(p)}
def checked(row):
 p=Path(row['path']);assert p.is_absolute()and p==p.resolve()and p.is_file()and not p.is_symlink()
 assert p.stat().st_size==row['bytes']and sha(p)==row['sha256'];return p
def main():
 p=argparse.ArgumentParser();p.add_argument('--review',required=True);p.add_argument('--review-sha',required=True);a=p.parse_args()
 started=time.monotonic();owner();plan_path=W/'DATA_CUSTODIAN_PLAN.v2.json';assert sha(plan_path)==PLAN_SHA;plan=json.loads(plan_path.read_text())
 assert plan['epoch']==40 and plan['source_checkpoint']=='2cf5aba60a050079506a5e9aa5463f44c1efcd5a'and plan['attempts']==1 and plan['allowed_retries']==0
 assert plan['paid_API_calls']==plan['GPU_calls']==plan['model_tokenizer_native_calls']==plan['semantic_gold_decodes_authorized']==0
 review_path=Path(a.review);assert sha(review_path)==a.review_sha;review=json.loads(review_path.read_text())
 assert review['checks_passed']is True and review['wrapper_source_sha256']==sha(W/'data_custodian_outer_once.py')and review['child_source_sha256']==sha(__file__)and review['plan_sha256']==PLAN_SHA
 assert review['approved']is True and review['only_label_blind_custodian_parser_authorized']is True and review['epoch']==40 and review['source_checkpoint']==plan['source_checkpoint']
 assert review['predataseal_sha256']==plan['seal']['sha256']and review['policy_sha256']==plan['policy']['sha256']
 policy=checked(plan['policy']);seal=checked(plan['seal']);checked(plan['root_contract'])
 for row in plan['source_modules']:checked(row)
 module_path=checked(plan['materializer']);assert module_path.name=='contractnli_data.py'
 archive=Path(plan['archive']['path']);assert archive==W/'data-source/opaque/contract-nli-eced6528.zip'
 target=Path(plan['output']);assert target==W/'data-source/materialized-dev-once'and not target.exists()
 assert not any(z.is_symlink()for z in(target,*target.parents))
 put(W/'DATA_CUSTODIAN_E40_ATTEMPT.json',{'schema_version':1,'epoch':40,'plan_sha256':PLAN_SHA,'attempts_reserved':1,'allowed_retries':0,'before_materializer_import_and_call':True,'review_path':a.review,'review_sha256':a.review_sha,'semantic_gold_values_decoded':0,'at_unix':time.time()})
 result={'schema_version':1,'epoch':40,'kind':plan['kind'],'status':'FAILED_STOP_NO_RETRY','plan_sha256':PLAN_SHA,'review_sha256':a.review_sha,'materializer_calls_attempted':0,'materializer_calls_completed':0,'semantic_gold_values_decoded':0,'model_tokenizer_native_calls':0,'paid_API_GPU_calls':0,'network_calls_by_wrapper':0,'errors':[]}
 def alarm(sig,frame):raise TimeoutError('DATA_CUSTODIAN_CHILD_DEADLINE')
 signal.signal(signal.SIGALRM,alarm);signal.setitimer(signal.ITIMER_REAL,170)
 try:
  owner();sys.path.insert(0,str(module_path.parent));spec=importlib.util.spec_from_file_location('e40_exact_reviewed_custodian',module_path);module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
  owner();result['materializer_calls_attempted']=1
  # Exact API passes the SAME independent approval path/hash as outer argv.
  report=module.materialize(str(archive),str(target),str(policy),str(seal),a.review,a.review_sha)
  result['materializer_calls_completed']=1;owner()
  assert report['semantic_gold_values_decoded']==report['model_tokenizer_native_calls']==0
  result.update(custodian_status=report['status'],materialization_report=ref(target/'materialization_report.json'),selected_ids=report['selected_ids'],raw_gold_tokens_copied=report['raw_gold_tokens_copied'],semantic_gold_values_decoded=report['semantic_gold_values_decoded'])
  if report['status']=='READY_LABEL_BLIND_DEV_FEATURES_AND_OPAQUE_VAULT':
   assert len(report['selected_ids'])==len(set(report['selected_ids']))==report['raw_gold_tokens_copied']==12
   result['status']='LABEL_BLIND_CUSTODIAN_COMPLETE_NO_GOLD_DECODE'
 except BaseException as error:
  result['errors'].append({'type':type(error).__name__,'message_sha256':hashlib.sha256(str(error).encode()).hexdigest()})
  (W/'data-custodian-exact-error.private.txt').write_text(traceback.format_exc())
 finally:
  signal.setitimer(signal.ITIMER_REAL,0);result['inner_pre_final_capture_wall_seconds']=time.monotonic()-started;result['source_sha256']=sha(__file__);put(W/'DATA_CUSTODIAN_E40_RESULT.json',result)
 print(json.dumps({'status':result['status'],'materializer_calls_attempted':result['materializer_calls_attempted'],'semantic_gold_values_decoded':result['semantic_gold_values_decoded']}))
 if result['status']!='LABEL_BLIND_CUSTODIAN_COMPLETE_NO_GOLD_DECODE':raise SystemExit(2)
if __name__=='__main__':main()
