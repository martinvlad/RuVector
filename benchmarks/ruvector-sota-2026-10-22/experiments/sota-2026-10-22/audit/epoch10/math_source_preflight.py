from pathlib import Path
import importlib.util,json,hashlib,inspect,ast
from datetime import datetime,timezone
from unittest.mock import patch
import numpy as np
O=Path(__file__).resolve().parent;S=O.parents[1];C=S/'candidate/epoch10'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def module(p,n):
 sp=importlib.util.spec_from_file_location(n,p);m=importlib.util.module_from_spec(sp);sp.loader.exec_module(m);return m
H=module(C/'head.py','audit_e10_head')
rng=np.random.default_rng(20261023);x=rng.normal(size=(11,5));x[:,0]=1;sw=rng.uniform(.2,2,11);base=rng.normal(size=(11,3));y=rng.integers(0,3,11);target=rng.integers(0,2,11)
checks=[]
for name,shape,fn in [('CE_L2',(5,3),lambda w:H.objective(w,x,base,y,sw)),('BCE_L2',(5,),lambda w:H.aux_objective(w,x,target,sw))]:
 w=rng.normal(size=shape)*.2;loss,g=fn(w); numerical=np.zeros_like(w)
 for index in np.ndindex(w.shape):
  a=w.copy();b=w.copy();a[index]+=1e-6;b[index]-=1e-6;numerical[index]=(fn(a)[0]-fn(b)[0])/2e-6
 err=float(np.max(np.abs(g-numerical)));assert err<1e-8;checks.append({'objective':name,'max_gradient_absolute_error':err,'finite_difference_epsilon':1e-6})
# Independent synthetic TRAIN-shaped arrays only, no source/corpus records read.
examples=[];records=[];width=len(H.FEATURES.FEATURE_NAMES)
for group in range(24):
 for q in range(3):
  label=H.FEATURES.CLASSES[q];identity=f'synthetic-query-{group}-{q}';records.append({'evaluation':{'original_threeway_label':label}})
  for arm in H.ARMS:
   features=rng.normal(size=width)*.05;features[0]=1
   examples.append({'id':identity,'source_group':f'synthetic-doc-{group}','source_text_sha256':hashlib.sha256(f'synthetic-{group}'.encode()).hexdigest(),'input_sha256':'synthetic','arm':arm,'weight':1/3,'original_threeway_label':label,'canonical_logits':rng.normal(size=3).tolist(),'features':features.tolist(),'annotation_overlap_target':float((group+q)%2)})
with patch.object(H,'collect',return_value=examples):
 artifact=H.fit(records,{},'synthetic-config','synthetic-allow',{'synthetic':True},{},'synthetic-annotations')
raw=np.asarray([e['features'] for e in examples]);weights=np.asarray([e['weight'] for e in examples]);oof=np.asarray(artifact['oof_probabilities'])
for fold in artifact['auxiliary_folds']:
 fitmask=np.asarray([e['source_group'] in fold['training_groups'] for e in examples]);held=~fitmask
 assert set(fold['training_groups']).isdisjoint(fold['heldout_groups']) and fitmask.sum()==144 and held.sum()==72
 mean,scale=H.normalize_fit(raw[fitmask],weights[fitmask]);assert np.array_equal(mean,fold['mean']) and np.array_equal(scale,fold['scale'])
 assert np.array_equal(H.predict_aux(fold,raw[held]),oof[held])
aug=np.column_stack((raw,oof));mean,scale=H.normalize_fit(aug,weights)
assert np.array_equal(mean,artifact['mean']) and np.array_equal(scale,artifact['scale'])
assert artifact['training_total_weight']==72
models=artifact['auxiliary_folds']+[artifact['auxiliary_final']]
assert len(models)==4 and all(m['fit_diagnostics']['steps_completed']==400 for m in models)
assert artifact['fit_diagnostics']['steps_completed']==400
head=H.FrozenHead(artifact,'synthetic-config','synthetic-allow',{'synthetic':True})
for e in examples:
 got=head.predict(e['features'],e['canonical_logits']);r=np.asarray(e['features']);aux=float(H.predict_aux(artifact['auxiliary_final'],r));b=np.asarray(e['canonical_logits']);z=b-b.mean()+((np.r_[r,aux]-mean)/scale)@np.asarray(artifact['weights']);p=np.exp(z-z.max());p/=p.sum()
 assert np.allclose(list(got.values()),p,atol=1e-15,rtol=0)
# Membership never enters inference feature function; selected text/logits only.
F=module(C/'features.py','audit_e10_features');assert list(inspect.signature(F.extract).parameters)==['premise','hypothesis','canonical_logits']
manifest=json.loads((C/'proposal-manifest.json').read_text())
proof={'schema_version':1,'at':datetime.now(timezone.utc).isoformat(),'checks_passed':True,'candidate_manifest_sha256':sha(C/'proposal-manifest.json'),'final_sources':{p.name:sha(p) for p in C.glob('*.py')},'config_sha256':sha(C/'config.json'),'finite_difference_checks':checks,'synthetic_document_crossfit':{'documents':24,'queries':72,'correlated_arm_views':216,'five_fits_steps_each':400,'fold_only_normalization_verified':True,'heldout_documents_excluded':True,'main_normalization_uses_OOF_probability_only':True,'runtime_uses_allTRAIN_auxiliary_probability':True,'distribution_shift_disclosed':True,'all216_inference_math_replayed':True},'candidate_synthetic_tests_passed':11,'controller_mock_tests_passed':18,'source_review':{'TRAIN72_source_and_annotation_only_at_fit':True,'exact_source_label_and_input_guard':True,'raw_training_cache_and_fit_artifact_lock_before_DEV_open':True,'same_frozen_artifact_verified_before_CONFIRM_constructor':True,'no_refit_or_fallback_after_failure':True,'five_optimizer_failure_diagnostics_preserved':True,'weak_overlap_target_is_not_sufficiency_or_absence':True,'same_features_auxiliary_head_and_model_all_three_selectors':True,'source_group_IDs_only_membership_not_inference_features':True,'proper_loss_signs_and_strict_DEV_plus2_all3_controls':True,'CONF_attempt_retirement_before_completed_measurements':True},'limits':'Empirical fixed optimizer criteria, not a convergence proof. Synthetic checks do not predict real fit convergence or benchmark gain. Generic lexical relation features do not establish legal semantics. Upstream conversion training provenance/contamination and mixed dataset-license caveats remain.','real_corpus_reads_for_this_script':0,'real_TRAIN_fit_model_init_forward_native_paid_calls':0}
out=O/'math-source-independent-v1.json';out.write_text(json.dumps(proof,indent=2)+'\n');print(json.dumps({'checks_passed':True,'sha256':sha(out),'derivatives':checks}))
