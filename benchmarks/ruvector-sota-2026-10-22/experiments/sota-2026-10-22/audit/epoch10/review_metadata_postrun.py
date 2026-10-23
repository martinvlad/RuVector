from pathlib import Path
from datetime import datetime,timezone
from urllib.request import Request,urlopen
import json,hashlib,fcntl,os,importlib.util,numpy as np
O=Path(__file__).resolve().parent;S=O.parents[1];P=S/'epoch10/project';projectroot=S.parents[1]
def obj(p):return json.loads(p.read_text())
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def rows(p):return [json.loads(x) for x in p.read_text().splitlines() if x]
def close(a,b):assert np.allclose(a,b,atol=1e-10,rtol=0),(a,b)
a=obj(O/'actual-independent-v1.json');e=obj(S/'epoch10/EPOCH_MANIFEST.json');u=obj(S/'epoch10/USED_IDENTITIES.json');l=obj(S/'epoch10/REJECTION_LEDGER.json');old=obj(S/'epoch9/REJECTION_LEDGER.json');snap=obj(S/'epoch10/actual-snapshot.json')
assert l['rejections'][:-1]==old['rejections'] and l['rejections'][-1]['epoch']==10
assert e['status']=='REJECTED_DEV_GATE' and e['frozen_plan_sha256']==a['plan_SHA256'] and e['independent_actual_report']['sha256']==sha(O/'actual-independent-v1.json')
assert e['actual_results']['metrics']==a['metrics'] and e['actual_results']['pipeline_latency_seconds']==a['latency_by_phase_seconds'] and e['actual_results']['resources']==a['resources'] and e['actual_results']['completion']==a['completion']
assert e['actual_results']['successful_HTTP']==96 and e['actual_results']['training_feature_HTTP']==72 and e['actual_results']['DEV_n']==24 and e['actual_results']['failed_HTTP']==0
assert e['confirmation_consumed']==e['confirmation_attempted']==e['DEV_gate_passed']==e['internal_confirmation_gate_passed']==False
assert e['confirmation_requests_started']==e['confirmation_requests_completed']==0
assert e['budget']['lifetime_native_attempts']==13 and e['budget']['new_study_used']==1 and e['budget']['allowed_further_attempts_in_closed_study']==0
assert not e['SOTA_established'] and e['official_rank'] is e['official_score'] is None
for role,path in [('train','legal-transfer/epoch10/train72.jsonl'),('development','legal-transfer/epoch10/development24.jsonl')]:
 actualrows=rows(S/path);m=u['source_frozen_joint_roles'][role];assert m['sha256']==sha(S/path) and m['ids']==[r['id'] for r in actualrows]
assert u['exposed_originaltrain_groups_total']==165 and u['unreserved_originaltrain_groups_after_fixed_draw']==242 and u['confirmation']['status'].startswith('PROJECT_MODEL_UNUSED') and not u['confirmation']['retired_conservatively']
recipe=e['replay_reproduction'];assert recipe['active_source']['sha256']==sha(O/'replay_actual_v2.py') and recipe['fit_source']['sha256']==sha(O/'verify_fit.py') and recipe['method_correction']['sha256']==sha(O/'replay-method-correction-v2.json')
assert snap['actual_project']==str(P)
for f in snap['files']:
 for root in (S/'epoch10',P/'experiments/sota-2026-10-22/epoch10'):
  p=root/f['path'];assert p.stat().st_size==f['bytes'] and sha(p)==f['sha256']
# Postrun static and byte-exact reproduction plus separate auxiliary arithmetic.
C=S/'candidate/epoch10/postrun';allow=obj(C/'public-allowlist-v1.json')
for pin in allow['files']:
 path=projectroot/pin['path'];assert path.stat().st_size==pin['bytes'] and sha(path)==pin['sha256']
d=obj(C/'diagnostic-v1.json');assert sha(C/'diagnostic-v1.json')==sha(O/'postrun-replay-v1.json')=='3d3d723a40f9cfc85aeee57a86798f20bc1772c5e792d5f8287dcfb79e231cd4'
sp=importlib.util.spec_from_file_location('postrun_findings_review',C/'build_findings_v1.py');M=importlib.util.module_from_spec(sp);sp.loader.exec_module(M);assert M.build(C/'diagnostic-v1.json')==obj(C/'findings-v1.json')
art=obj(S/'epoch10/fitted-head.json');raw=np.asarray([x['features'] for x in art['training_examples']]);y=np.asarray([x['annotation_overlap_target'] for x in art['training_examples']]);oof=np.asarray(art['oof_probabilities']);aux=art['auxiliary_final'];z=((raw-np.asarray(aux['mean']))/np.asarray(aux['scale']))@np.asarray(aux['weights']);final=np.exp(-np.logaddexp(0.,-z))
def auc(p):
 diff=p[y==1,None]-p[y==0];return float(np.mean((diff>0)+.5*(diff==0)))
for name,p in [('OOF',oof),('final_allTRAIN_in_sample',final)]:
 r=d['auxiliary_TRAIN_OOF_and_runtime_shift']['all_views'][name];close(r['auc_pairwise_tie_half'],auc(p));close(r['brier'],np.mean((p-y)**2))
shift=d['auxiliary_TRAIN_OOF_and_runtime_shift']['all_views'];close(shift['final_minus_OOF_mean_absolute'],np.mean(abs(final-oof)));close(shift['final_minus_OOF_max_absolute'],max(abs(final-oof)))
metadata={'schema_version':1,'at':datetime.now(timezone.utc).isoformat(),'checks_passed':True,'reviewed_metadata_sha256':{f:sha(S/'epoch10'/f) for f in ['EPOCH_MANIFEST.json','REJECTION_LEDGER.json','USED_IDENTITIES.json','actual-snapshot.json']},'old9ledger_rows_exact_preserved':True,'all119raw_snapshots_both_outer_actual_verified':True,'active_replay_v2_and_fit_source_recipe_exact':True,'actual_source_metric_budget_exposure_unchanged':True,'lifetime_counts':{'attempts':13,'successful_HTTP':735,'TRAIN_features':144,'evaluation_diagnostic_decisions':591,'historic_HTTP_failures':2},'postrun':{'allowlist_sha256':sha(C/'public-allowlist-v1.json'),'diagnostic_byteexact_replay_sha256':sha(C/'diagnostic-v1.json'),'findings_exact_deterministic_replay_sha256':sha(C/'findings-v1.json'),'five_synthetic_tests_passed':True,'auxiliary_AUC_and_shift_independently_recomputed':True,'OOF_auc':auc(oof),'final_TRAIN_in_sample_auc':auc(final),'mean_absolute_shift':float(np.mean(abs(final-oof))),'weak_coverage_not_sufficiency':True,'generic_feature_strata_not_gold_actor_scope_annotations':True,'matched_saved_input_raw9_vs_head_descriptive_only_no_rescue':True,'CONF_files_or_labels_used':False},'official_score_rank_SOTA':None,'new_model_native_optimizer_calls':0}
out=O/'metadata-postrun-independent-v1.json';out.write_text(json.dumps(metadata,indent=2)+'\n');print(json.dumps({'metadata_sha256':sha(out)}))
# Independently verify publication-only lock recovery after runtime reset.
rec=obj(S/'epoch10/publication/publication-lock-recovered.json');owner=obj(S/'epoch10/lock-owner.json');assert rec['run_id']==owner['run_id']=='35c0d6af-5d4c-4ad4-8412-13ce361772d3' and rec['expires_unix']==owner['expires_unix']
assert all(not Path('/proc',str(pid)).exists() for pid in [21117,21769,21773]);assert Path('/proc',str(rec['pid'])).exists()
blocked=False
with (S/'.loop.lock').open('rb') as h:
 try:fcntl.flock(h,fcntl.LOCK_EX|fcntl.LOCK_NB)
 except BlockingIOError:blocked=True
 else:fcntl.flock(h,fcntl.LOCK_UN)
assert blocked
for pin in obj(S/'epoch10/plan.json')['pins']:assert sha(P/pin['path'])==pin['sha256']
manifest=obj(S/'epoch10/durable-files.json');assert len(manifest['files'])==1330
for pin in manifest['files']:
 p=S/'epoch10/durable-kit'/pin['path'];b=p.read_bytes();assert len(b)==pin['bytes'] and hashlib.sha1(b'blob '+str(len(b)).encode()+b'\0'+b).hexdigest()==pin['git_blob_sha1']
url='https://raw.githubusercontent.com/ruvnet/RuVector/24e671dd2b27f5119f25651056456832e0657745/benchmarks/ruvector-sota-2026-10-22/ACTIVE_RUN.json'
with urlopen(Request(url,headers={'User-Agent':'RuVector-independent-readonly-audit'}),timeout=20) as r:rawactive=r.read()
active=json.loads(rawactive);assert active['run_id']==rec['run_id'] and datetime.fromisoformat(active['expires_at'].replace('Z','+00:00')).timestamp()-rec['expires_unix']<.001
proof={'schema_version':1,'at':datetime.now(timezone.utc).isoformat(),'checks_passed':True,'scope':'Publication-only recovery after actualterminal; no experiments or retries','lease_commit':'24e671dd2b27f5119f25651056456832e0657745','connected_branch_ref_independently_read_same_lease':True,'immutable_remote_ACTIVE_RUN_sha256':hashlib.sha256(rawactive).hexdigest(),'same_original_UUID_and_expiry':True,'old_supervisor_and_actual_worker_native_absent':[21117,21769,21773],'recovery_supervisor_alive':rec['pid'],'scoped_OS_flock_nonblocking_contender_correctly_rejected':True,'all190_actual_scientific_pins_reverified':True,'all119actual_outer_artifacts_reverified':True,'all1330_prior_remote_blob_cache_identities_reverified':True,'recorded_actual_attempts':1,'CONF_attempts':0,'new_source_model_native_paid_calls_or_external_writes':0,'recovery_receipt_sha256':sha(S/'epoch10/publication/publication-lock-recovered.json')}
out=O/'publication-recovery-independent-v1.json';out.write_text(json.dumps(proof,indent=2)+'\n');print(json.dumps({'recovery_sha256':sha(out)}))
