"""Saved-cache-only independent reconstruction of five fixed TRAIN fits. No ONNX/native calls."""
from pathlib import Path
from datetime import datetime,timezone
import json,hashlib,importlib.util,numpy as np
O=Path(__file__).resolve().parent
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def obj(p):return json.loads(p.read_text())
def rows(p):return [json.loads(x) for x in p.read_text().splitlines() if x]
def canonical(v):return json.dumps(v,ensure_ascii=False,sort_keys=True,separators=(',',':'),allow_nan=False).encode()
def close(a,b,tol=1e-8):assert np.allclose(a,b,rtol=0,atol=tol),(np.shape(a),np.shape(b),float(np.max(np.abs(np.asarray(a)-np.asarray(b)))))
def softmax(z):
 e=np.exp(z-z.max(axis=1,keepdims=True));return e/e.sum(axis=1,keepdims=True)
def sigmoid(z):return np.exp(-np.logaddexp(0.,-z))
def norm(raw,sw):
 mean=np.average(raw,axis=0,weights=sw);scale=np.maximum(np.sqrt(np.average((raw-mean)**2,axis=0,weights=sw)),.1);mean[0]=0;scale[0]=1;return mean,scale
def replay(raw,sw,target,diagnostic,base=None):
 mean,scale=norm(raw,sw);x=(raw-mean)/scale;shape=(raw.shape[1],) if base is None else (raw.shape[1],3)
 def objective(w):
  if base is None:
   z=x@w;nll=np.logaddexp(0.,z)-target*z;g=x.T@((sigmoid(z)-target)*sw)/sw.sum()+.1*w
  else:
   z=base+x@w;maximum=z.max(axis=1);nll=maximum+np.log(np.exp(z-maximum[:,None]).sum(axis=1))-z[np.arange(len(target)),target];d=softmax(z);d[np.arange(len(target)),target]-=1;g=x.T@(d*sw[:,None])/sw.sum()+.1*w
  loss=float(sw@nll/sw.sum()+.05*np.square(w).sum());return loss,g
 w=np.zeros(shape);m=np.zeros_like(w);v=np.zeros_like(w);initial,_=objective(w);history=diagnostic['history'];assert len(history)==400
 close(initial,diagnostic['initial_objective'])
 for step,h in enumerate(history,1):
  loss,g=objective(w);assert h['step']==step;close(loss,h['objective_before_step']);close(np.linalg.norm(g),h['gradient_norm_before_step']);m=.9*m+.1*g;v=.999*v+.001*g*g;w-=.03*(m/(1-.9**step))/(np.sqrt(v/(1-.999**step))+1e-8)
 final,g=objective(w);close(final,diagnostic['final_objective']);close(np.linalg.norm(g),diagnostic['final_gradient_norm']);close(w,diagnostic['last_finite_weights'])
 accepted=bool(np.isfinite(w).all() and final<=initial+1e-8 and np.linalg.norm(g)<=1e-3);assert accepted==diagnostic['fixed_acceptance_criteria_passed']
 return mean,scale,w,{'stage':diagnostic['stage'],'steps':400,'initial':initial,'final':final,'gradient_norm':float(np.linalg.norm(g)),'accepted':accepted}
def run(project):
 s=project/'experiments/sota-2026-10-22';study=s/'epoch10';run=study/'runs/development';cache=rows(run/'training-cache.jsonl');measured=rows(run/'records.jsonl');train=[r for r in measured if r['measured_phase']=='train'];assert cache==train and len(train)==72
 originals=rows(s/'legal-transfer/epoch10/train72.jsonl');assert [r['id'] for r in train]==[r['id'] for r in originals]
 for r,e in zip(train,originals):assert r['input']==e['input'] and r['evaluation']==e['evaluation'] and r['input_sha256']==e['input_sha256']
 annotations={a['id']:a for a in obj(s/'legal-transfer/epoch10/train-annotations.json')['records']}
 spec=importlib.util.spec_from_file_location('replay10_features',s/'candidate/epoch10/features.py');F=importlib.util.module_from_spec(spec);spec.loader.exec_module(F)
 examples=[];classes=('Entailment','Contradiction','NotMentioned');arms=('ruvector_top2','lexical_top2','positional_first2')
 for r in sorted(train,key=lambda x:x['id']):
  state=r['input']['state'];statehash=hashlib.sha256(state.encode()).hexdigest();hyp=r['input']['questions']['decision']['criteria']['Yes'];ann=annotations[r['id']];assert ann['source_document_sha256']==statehash
  for arm in arms:
   d=r['response']['diagnostics']['decision']['arms'][arm];t=d['decoding'];logits=[t['logits'][j] for j in (0,2,1)];assert t['typed_head_state']=='TRAIN_COLLECTION';close(logits,t['typed_head_canonical_logits']);features=F.extract(d['premise'],hyp,logits);assert features==t['typed_head_features'];spans=d['coverage']['selected_source_spans'];assert d['premise']=='\n\n'.join(state[a:b] for a,b in spans)
   target=float(any(max(a,c)<min(b,d) for a,b in spans for c,d in ann['evidence_spans']))
   examples.append({'id':r['id'],'source_group':r['source_group'],'source_text_sha256':statehash,'input_sha256':r['input_sha256'],'arm':arm,'weight':1/3,'original_threeway_label':r['evaluation']['original_threeway_label'],'canonical_logits':logits,'features':features,'annotation_overlap_target':target})
 raw=np.asarray([e['features'] for e in examples]);sw=np.asarray([e['weight'] for e in examples]);target=np.asarray([e['annotation_overlap_target'] for e in examples]);y=np.asarray([classes.index(e['original_threeway_label']) for e in examples]);base=np.asarray([e['canonical_logits'] for e in examples]);base-=base.mean(axis=1,keepdims=True)
 assert raw.shape==(216,48);close(sw.sum(),72);groups=sorted({e['source_group'] for e in examples},key=lambda g:(next(e['source_text_sha256'] for e in examples if e['source_group']==g),g));assignment={g:i//8 for i,g in enumerate(groups)}
 artifactpath=study/'fitted-head.json';accepted=artifactpath.exists();a=obj(artifactpath) if accepted else None;final=obj(run/'final-engine.json');diagnostics=[];oof=np.full(216,np.nan)
 if accepted:
  assert a['training_examples']==examples and a['fold_assignment']==assignment;models=a['auxiliary_folds']+[a['auxiliary_final']];main=a['fit_diagnostics']
 else:
  failure=final['receipt_after_close']['fit_failure'];d=failure['diagnostics'];models=d.get('completed_auxiliary_fits',[]);main=d if d.get('stage')=='threeway_residual_OOFcoverage' else None
 for k,model in enumerate(models):
  mask=np.asarray([assignment[e['source_group']]!=k for e in examples]) if k<3 else np.ones(216,dtype=bool)
  if k<3:assert set(model['training_groups'])=={g for g in groups if assignment[g]!=k} and set(model['heldout_groups'])=={g for g in groups if assignment[g]==k}
  mean,scale,w,diag=replay(raw[mask],sw[mask],target[mask],model['fit_diagnostics']);close(mean,model['mean']);close(scale,model['scale']);close(w,model['weights']);assert diag['accepted'];diagnostics.append(diag)
  if k<3:oof[~mask]=sigmoid(((raw[~mask]-mean)/scale)@w)
 if accepted:
  close(oof,a['oof_probabilities']);assert np.isfinite(oof).all();aug=np.column_stack((raw,oof));mean,scale,w,diag=replay(aug,sw,y,main,base);close(mean,a['mean']);close(scale,a['scale']);close(w,a['weights']);assert diag['accepted'];diagnostics.append(diag)
  fields=('class_order','feature_names','mean','scale','weights','auxiliary_final','auxiliary_folds','fold_assignment','oof_probabilities');assert a['parameters_sha256']==hashlib.sha256(canonical({k:a[k] for k in fields})).hexdigest()
  lock=obj(study/'readout-fit-lock.json');assert lock['fitted_head_sha256']==sha(artifactpath) and lock['training_cache_sha256']==sha(run/'training-cache.jsonl') and lock['plan_sha256']==sha(study/'plan.json');starts=rows(run/'started-requests.jsonl');dev=[r for r in starts if r['phase']=='development'];assert len(dev)==24 and lock['at']<=dev[0]['at'] and lock['DEV_requests_before_fit_lock']==lock['confirmation_requests_before_fit_lock']==0
 elif main and np.isfinite(oof).all():
  _,_,_,diag=replay(np.column_stack((raw,oof)),sw,y,main,base);assert not diag['accepted'];diagnostics.append(diag)
 return {'schema_version':1,'at':datetime.now(timezone.utc).isoformat(),'checks_passed':True,'fitted_artifact_present':accepted,'fitted_artifact_sha256':sha(artifactpath) if accepted else None,'training_cache_sha256':sha(run/'training-cache.jsonl'),'train_questions':72,'document_groups':24,'correlated_views':216,'total_question_weight':72,'feature_dimensions':48,'main_augmented_dimensions':49,'annotation_targets_independently_reconstructed_from_TRAIN_only':True,'fold_assignment_exclusion_norms_and_OOF_replayed':True,'five_fixed_Adam_histories_and_weights_independently_replayed':accepted,'replayed_fit_stages':diagnostics,'fit_artifact_locked_before_DEV':accepted,'fit_failure_diagnostics':None if accepted else final['receipt_after_close'].get('fit_failure'),'scope':'Postmeasurement saved TRAIN-cache reconstruction only. No models/native calls or newsourcefit. Annotationoverlap target is not sufficiency; runtime allTRAIN auxiliary vsOOF decisionfit shift disclosed.','auditor_model_native_calls':0}
if __name__=='__main__':
 import argparse
 ap=argparse.ArgumentParser();ap.add_argument('--project',type=Path,required=True);ap.add_argument('--out',type=Path,required=True);args=ap.parse_args();assert not args.out.exists();proof=run(args.project);args.out.write_text(json.dumps(proof,indent=2)+'\n');print(json.dumps({'checks_passed':True,'artifact_present':proof['fitted_artifact_present'],'sha256':sha(args.out)}))
