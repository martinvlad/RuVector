"""Predeclared cached-logit binary/threeway diagnostics; no forward or candidate selection."""
from pathlib import Path
from datetime import datetime,timezone
import argparse,hashlib,json,math,statistics,numpy as np
CLASSES=['Entailment','Contradiction','NotMentioned'];ARMS={'ruvector_top2':'ruvector_top2','same_nli_lexical_top2':'lexical_top2','same_nli_positional_first2':'positional_first2'}
def obj(p):return json.loads(p.read_text())
def rows(p):return [json.loads(x) for x in p.read_text().splitlines() if x]
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def probs(z):
 z=np.asarray(z,dtype=np.float64);p=np.exp(z-z.max());return p/p.sum()
def score(p,gold):
 assert set(p) and gold in p and all(math.isfinite(v) and 0<=v<=1 for v in p.values()) and abs(sum(p.values())-1)<1e-10
 pred=min(p,key=lambda k:(-p[k],k));return {'correct':int(pred==gold),'brier':sum((v-float(k==gold))**2 for k,v in p.items()),'nll':-math.log(max(p[gold],1e-15))}
def summary(values):return {'n':len(values),'correct':sum(v['correct'] for v in values),'brier':statistics.mean(v['brier'] for v in values),'nll':statistics.mean(v['nll'] for v in values)}
def run(project):
 s=project/'experiments/sota-2026-10-22';study=s/'epoch8';actual=[]
 for phase in ['development','confirmation']:
  p=study/'runs'/phase/'records.jsonl'
  if p.exists():actual+=rows(p)
 metrics={};threeway={};counts={};proof=[]
 for corpus in ['train','development','confirmation']:
  rs=[r for r in actual if r['measured_phase']==corpus]
  if not rs:continue
  counts[corpus]={'queries':len(rs),'groups':len({r['source_group'] for r in rs}),'scope':'TRAIN rawcollection/in-sample only' if corpus=='train' else 'Public heldoutdiagnostic, notofficialbenchmark'};metrics[corpus]={};threeway[corpus]={}
  have_threeway=all(r['evaluation'].get('original_threeway_label') in CLASSES for r in rs)
  for arm,alias in ARMS.items():
   bvals={k:[] for k in ['actual_runtime_readout','untrained_full_threeway','discard_neutral_reference']};tvals={k:[] for k in ['actual_runtime_threeway','untrained_full_threeway']}
   for r in rs:
    d=r['response']['diagnostics']['decision']['arms'][alias]['decoding'];raw=d['logits'];p=probs([raw[1],raw[0],raw[2]]);conditional=probs([raw[1],raw[0]]);post=d['typed_threeway_probabilities'];rawmap=dict(zip(CLASSES,p))
    for k,v in rawmap.items():assert abs(v-d['raw_threeway_probabilities'][k])<1e-10
    runtime={'Yes':post['Entailment'],'No':post['Contradiction']+post['NotMentioned']};full={'Yes':float(p[0]),'No':float(p[1]+p[2])};discard={'Yes':float(conditional[0]),'No':float(conditional[1])}
    resp=r['response'] if arm=='ruvector_top2' else r['response']['ablation_responses'][arm]
    for k in runtime:assert abs(runtime[k]-resp['answers']['decision']['probabilities'][k])<1e-10
    for k,v in [('actual_runtime_readout',runtime),('untrained_full_threeway',full),('discard_neutral_reference',discard)]:bvals[k].append(score(v,r['evaluation']['gold']))
    if have_threeway:
     label=r['evaluation']['original_threeway_label'];assert r['evaluation']['gold']==('Yes' if label=='Entailment' else 'No');tvals['actual_runtime_threeway'].append(score(post,label));tvals['untrained_full_threeway'].append(score(rawmap,label))
   metrics[corpus][arm]={k:summary(v) for k,v in bvals.items()};threeway[corpus][arm]={k:summary(v) for k,v in tvals.items()} if have_threeway else {'omitted':'No verified original3wayfield; no fabricatedC/Nlabels or extra unusedsourceaccess.'}
 fitted_train={};artifact_path=study/'fitted-head.json'
 if artifact_path.exists():
  artifact=obj(artifact_path)
  for alias in ARMS.values():
   views=[r for r in artifact['cached_training_replay'] if r['arm']==alias];assert len(views)==72;fitted_train[alias]={'binary':summary([score(v['binary_probabilities'],'Yes' if v['original_threeway_label']=='Entailment' else 'No') for v in views]),'threeway':summary([score(v['threeway_probabilities'],v['original_threeway_label']) for v in views]),'scope':'FittedTRAIN cachedposteriors, in-sample only; correlatedviews notindependent216.'}
 return {'schema_version':1,'at':datetime.now(timezone.utc).isoformat(),'checks_passed':True,'contract_sha256':sha(Path(__file__).resolve().parent/'offline-reference-analysis-contract-v2.json'),'binary_metrics':metrics,'threeway_metrics':threeway,'fitted_TRAIN_cached_metrics':fitted_train,'counts':counts,'confirmation_outputs_used':bool(counts.get('confirmation')),'source':'Exactly savedrawpretrained C/E/N logits and actualtypedposterior perview onidenticalinput/evidence, stableT1; no newforwards/optimizer/temperature/threshold or candidate selection.','scope':'Offlinepredeclaredreferenceandmulticlassdiagnostics only. Only actualfrozenheadbinaryDEV/CONFgates matter; no promotingbestreference, no officialCapability/Calibration/rank. TRAINmetrics in-sample, groupscorrelated.','auditor_model_native_calls':0}
if __name__=='__main__':
 ap=argparse.ArgumentParser();ap.add_argument('--project',type=Path,required=True);ap.add_argument('--out',type=Path,required=True);cli=ap.parse_args();assert not cli.out.exists();r=run(cli.project);cli.out.write_text(json.dumps(r,indent=2)+'\n');print(json.dumps({'checks_passed':True,'sha256':sha(cli.out),'binaryDEV':r['binary_metrics'].get('development')}))
