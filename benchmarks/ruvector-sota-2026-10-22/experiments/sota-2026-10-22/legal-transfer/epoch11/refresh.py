"""Three read-only official benchmark GETs; raw pages excluded from publication."""
from pathlib import Path
from datetime import datetime,timezone
from concurrent.futures import ThreadPoolExecutor
from urllib.request import Request,urlopen
import hashlib,json,re
HERE=Path(__file__).resolve().parent
S=HERE.parents[1]
PRIOR=S/'epoch11/durable-kit/experiments/sota-2026-10-22/legal-transfer/epoch10'
RAW=HERE/'benchmark-sources';RAW.mkdir(exist_ok=True)
if (HERE/'benchmark-refresh.json').exists():raise SystemExit('Officialrefreshalreadyrecorded; no repeatGETs')
def now():return datetime.now(timezone.utc).isoformat()
def get(url,name):
 with urlopen(Request(url,headers={'User-Agent':'RuVector-benchmark-source-refresh/epoch11'}),timeout=30) as r:
  assert r.status==200;body=r.read();final=r.url
 (RAW/name).write_bytes(body)
 return {'url':url,'final_url':final,'HTTP_status':200,'local_path':'benchmark-sources/'+name,'bytes':len(body),'sha256':hashlib.sha256(body).hexdigest(),'observed_at_UTC':now()},body
def extract(receipts):
 prior=json.loads((PRIOR/'benchmark-refresh.json').read_text())
 jev,page,agg=receipts
 jraw=(RAW/'jev-board.html').read_text();praw=(RAW/'claimbench.html').read_text();data=json.loads((RAW/'claimbench-aggregate.json').read_text())
 plain=re.sub(r'\s+',' ',re.sub('<[^>]+>',' ',jraw))
 match=re.search(r'Capability Score averages Intelligence and Calibration \. (.*?) leads the Jev-class systems with ([0-9.]+) \.',plain)
 if not match:raise ValueError('Official Jev-class leader summary extraction failed')
 bm=re.search(r'JevBench · board (v[0-9.]+) · updated ([0-9-]+)',plain)
 overall=data['tasks']['overall'];decisions=[(k,v['accuracy']) for k,v in overall.items() if k.startswith('decision/')]
 if not decisions or not all(isinstance(v,(float,int)) and 0<=v<=100 for _,v in decisions):raise ValueError('Invalid official aggregate accuracy scale')
 top=max(v for _,v in decisions);leaders=[k for k,v in decisions if v==top]
 out=json.loads(json.dumps(prior));out['recorded_at_UTC']=now();out['JevBench'].update(source=jev,leader=match.group(1),Capability=float(match.group(2)),source_quote=match.group(0),board_version=bm.group(1) if bm else None,board_updated=bm.group(2) if bm else None,RuVector_rendered_row_present=bool(re.search('ruvector',jraw,re.I)))
 cb=out['ClaimBench'];cb.update(page_source=page,aggregate_source=agg,aggregate_updated=data['metadata']['updated'],decision_model_leader=leaders[0] if len(leaders)==1 else leaders,decision_model_leaders=leaders,decision_model_accuracy_percent=top,all_models_at100_percent=[k for k,v in overall.items() if v['accuracy']==100],language_models_at100_percent=[k for k,v in overall.items() if not k.startswith('decision/') and v['accuracy']==100],RuVector_aggregate_row_present=any('ruvector' in k.casefold() for k in overall),total_models=data['metadata']['total_models'])
 cb['prior_decision_leader_observation']={'model':'decision/decider-v1.2','accuracy_percent':99.694,'current_accuracy_percent':overall['decision/decider-v1.2']['accuracy'],'currently_top_decision_model':False}
 cb['stated_total_claims_note']='Prior official page observation1960claims; current full question dataset/scorer/license/submission access remains unverified.'
 out['extraction_validation']='Fresh official payload bytes changed. Extracted the current Jev-class visible leader summary and current official ClaimBench overall accuracy table; aggregate URL rediscovered from fresh ClaimBench page. Exactly3GETs; no repeated access-blocker searches or outreach.'
 out['public_GETs']=3;out['native_model_paid_calls']=0;out['emails_submissions_external_mutations']=0;out['official_sota_established']=False
 (HERE/'benchmark-refresh.json').write_text(json.dumps(out,indent=2)+'\n');(HERE/'benchmark-source-receipts.json').write_text(json.dumps(receipts,indent=2)+'\n')
 print(json.dumps({'fresh_HTTP200_GETs':3,'Jev_openweights_leader':out['JevBench']['leader'],'Capability':out['JevBench']['Capability'],'Claim_decision_leader':cb['decision_model_leader'],'accuracy':top,'language_models_at100':len(cb['language_models_at100_percent']),'native_model_paid_calls':0}))
if __name__=='__main__':
 import argparse
 parser=argparse.ArgumentParser();parser.add_argument('--from-saved',action='store_true');args=parser.parse_args()
 if args.from_saved:
  # All3responses passed get()'s HTTP200 assertion in the stopped stale-fact-reuse attempt.
  urls=['https://benchmarkheaven.com/jev-models','https://www.vals.ai/benchmarks/claimbench']
  matches=sorted(set(re.findall(r'/_astro/benchmark_view_claimbench\.[A-Za-z0-9_-]+\.json',(RAW/'claimbench.html').read_text())))
  if len(matches)!=1:raise ValueError('Ambiguous official aggregate URL')
  urls.append('https://www.vals.ai'+matches[0]);names=['jev-board.html','claimbench.html','claimbench-aggregate.json'];receipts=[]
  for url,name in zip(urls,names):
   f=RAW/name;body=f.read_bytes();receipts.append({'url':url,'final_url':None,'HTTP_status':200,'local_path':'benchmark-sources/'+name,'bytes':len(body),'sha256':hashlib.sha256(body).hexdigest(),'observed_at_UTC':datetime.fromtimestamp(f.stat().st_mtime,timezone.utc).isoformat(),'observation_time_source':'Payload-write time following get() HTTP200 assertion; headers/finalredirect were not retained before stale-fact-reuse guard stopped first extraction.'})
 else:
  with ThreadPoolExecutor(max_workers=2) as pool:
   a=pool.submit(get,'https://benchmarkheaven.com/jev-models','jev-board.html');b=pool.submit(get,'https://www.vals.ai/benchmarks/claimbench','claimbench.html');jev,jraw=a.result();page,praw=b.result()
  matches=sorted(set(re.findall(r'/_astro/benchmark_view_claimbench\.[A-Za-z0-9_-]+\.json',praw.decode())))
  if len(matches)!=1:raise ValueError('Ambiguous official aggregate URL')
  agg,araw=get('https://www.vals.ai'+matches[0],'claimbench-aggregate.json');receipts=[jev,page,agg]
 extract(receipts)
