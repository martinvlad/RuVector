"""Independent NumPy-only reconstruction of the one fixed TRAIN fit; no models."""
from pathlib import Path
from datetime import datetime,timezone
import argparse,hashlib,importlib.util,json,math,numpy as np
O=Path(__file__).resolve().parent;S=O.parents[1]
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def obj(p):return json.loads(p.read_text())
def rows(p):return [json.loads(x) for x in p.read_text().splitlines() if x]
def canonical(v):return json.dumps(v,ensure_ascii=False,sort_keys=True,separators=(',',':'),allow_nan=False).encode()
def close(a,b,tol=1e-9):assert np.max(np.abs(np.asarray(a)-np.asarray(b)))<=tol,(a,b)
def softmax(x):
 e=np.exp(x-np.max(x,axis=1,keepdims=True));return e/e.sum(axis=1,keepdims=True)
def run(project):
 s=project/'experiments/sota-2026-10-22';study=s/'epoch8';run=study/'runs/development';artifact=obj(study/'fitted-head.json');cache=rows(run/'training-cache.jsonl');measured=rows(run/'records.jsonl');train=[r for r in measured if r['measured_phase']=='train'];assert cache==train and len(train)==72
 actualtrain=rows(s/'legal-transfer/epoch8/train72.jsonl');assert [r['id'] for r in train]==[r['id'] for r in actualtrain]
 for r,e in zip(train,actualtrain):assert r['input']==e['input'] and r['evaluation']==e['evaluation'] and r['input_sha256']==e['input_sha256']
 sp=importlib.util.spec_from_file_location('fitcheck_features',s/'candidate/epoch8/features.py');F=importlib.util.module_from_spec(sp);sp.loader.exec_module(F)
 examples=[];classes=('Entailment','Contradiction','NotMentioned');arms=('ruvector_top2','lexical_top2','positional_first2')
 for r in sorted(train,key=lambda x:x['id']):
  hyp=r['input']['questions']['decision']['criteria']['Yes']
  for arm in arms:
   d=r['response']['diagnostics']['decision']['arms'][arm];t=d['decoding'];logits=t['logits'];canonical_logits=[logits[1],logits[0],logits[2]];close(t['typed_head_canonical_logits'],canonical_logits,1e-12)
   assert t['typed_head_state']=='TRAIN_COLLECTION' and t['typed_head_feature_names']==list(F.FEATURE_NAMES)
   features=F.extract(d['premise'],hyp,canonical_logits);assert features==t['typed_head_features']
   examples.append({'id':r['id'],'source_group':r['source_group'],'input_sha256':r['input_sha256'],'arm':arm,'original_threeway_label':r['evaluation']['original_threeway_label'],'weight':1/3,'canonical_logits':canonical_logits,'features':features})
 assert artifact['training_examples']==examples and artifact['class_order']==list(classes) and artifact['training_questions']==72 and artifact['training_document_groups']==24 and artifact['training_arm_examples']==216
 raw=np.asarray([e['features'] for e in examples],dtype=np.float64);base=np.asarray([e['canonical_logits'] for e in examples],dtype=np.float64);base-=base.mean(axis=1,keepdims=True);target=np.asarray([classes.index(e['original_threeway_label']) for e in examples]);sample=np.asarray([e['weight'] for e in examples]);close(sample.sum(),72,1e-12)
 mean=(sample[:,None]*raw).sum(axis=0)/sample.sum();variance=(sample[:,None]*(raw-mean)**2).sum(axis=0)/sample.sum();scale=np.maximum(np.sqrt(variance),.1);mean[0]=0.;scale[0]=1.;close(mean,artifact['mean']);close(scale,artifact['scale']);x=(raw-mean)/scale
 def loss_gradient(w):
  z=base+x@w;p=softmax(z);nll=(np.max(z,axis=1)+np.log(np.exp(z-np.max(z,axis=1,keepdims=True)).sum(axis=1))-z[np.arange(len(target)),target]);loss=float((sample*nll).sum()/sample.sum()+.05*(w*w).sum());delta=p.copy();delta[np.arange(len(target)),target]-=1;g=x.T@(sample[:,None]*delta)/sample.sum()+.1*w;return loss,g
 w=np.zeros((29,3));moment=np.zeros_like(w);second=np.zeros_like(w);initial,_=loss_gradient(w);history=artifact['fit_diagnostics']['history'];assert len(history)==400
 for step in range(1,401):
  loss,g=loss_gradient(w);h=history[step-1];assert h['step']==step;close(loss,h['objective_before_step']);close(np.linalg.norm(g),h['gradient_norm_before_step']);moment=.9*moment+.1*g;second=.999*second+.001*g*g;w-=.03*(moment/(1-.9**step))/(np.sqrt(second/(1-.999**step))+1e-8)
 final,g=loss_gradient(w);close(w,artifact['weights'],1e-8);close(initial,artifact['fit_diagnostics']['initial_objective']);close(final,artifact['fit_diagnostics']['final_objective']);close(np.linalg.norm(g),artifact['fit_diagnostics']['final_gradient_norm']);assert final<=initial+1e-8 and np.linalg.norm(g)<=1e-3
 assert artifact['feature_source_sha256']==sha(s/'candidate/epoch8/features.py') and artifact['trainer_source_sha256']==sha(s/'candidate/epoch8/head.py')
 assert artifact['parameters_sha256']==hashlib.sha256(canonical({k:artifact[k] for k in ['class_order','feature_names','mean','scale','weights']})).hexdigest()
 lock=obj(study/'readout-fit-lock.json');assert lock['fitted_head_sha256']==sha(study/'fitted-head.json') and lock['training_cache_sha256']==sha(run/'training-cache.jsonl');starts=rows(run/'started-requests.jsonl');devstarts=[r for r in starts if r['phase']=='development'];assert len(devstarts)==24 and lock['at']<=devstarts[0]['at'];assert lock['DEV_requests_before_fit_lock']==lock['confirmation_requests_before_fit_lock']==0
 return {'schema_version':1,'at':datetime.now(timezone.utc).isoformat(),'checks_passed':True,'fitted_artifact_sha256':sha(study/'fitted-head.json'),'fit_lock_sha256':sha(study/'readout-fit-lock.json'),'training_cache_sha256':sha(run/'training-cache.jsonl'),'train_questions':72,'train_groups':24,'correlated_arm_views':216,'source_query_total_weight':1,'total_weight':float(sample.sum()),'train_mean_scale_independently_recomputed':True,'all400Adam_steps_objective_gradient_replayed':True,'max_reconstructed_weight_error':float(np.max(abs(w-np.asarray(artifact['weights'])))),'initial_objective':initial,'final_objective':final,'final_gradient_norm':float(np.linalg.norm(g)),'fixed_acceptance_passed':True,'artifact_locked_before_first_DEV_request':True,'fit_uses_only_frozenTRAIN_labels_features':True,'canonical_target_order':list(classes),'scope':'Source/train-view/cache/optimizer/artifact replay only. No newtrainingcorpus/model/nativecalls; reconstructs fixed smallhead solely fromsavedTRAINfeatures. DEV/CONF labels notused forfit/replaynormalization.','auditor_model_native_calls':0}
if __name__=='__main__':
 ap=argparse.ArgumentParser();ap.add_argument('--project',type=Path,required=True);ap.add_argument('--out',type=Path,required=True);cli=ap.parse_args();assert not cli.out.exists();r=run(cli.project);cli.out.write_text(json.dumps(r,indent=2)+'\n');print(json.dumps({'checks_passed':True,'sha256':sha(cli.out),'final_gradient_norm':r['final_gradient_norm']}))
