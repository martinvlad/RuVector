"""Independent label-free source/token context capacity; no model/native calls."""
from pathlib import Path
from datetime import datetime,timezone
import argparse,hashlib,importlib.util,json,re
from tokenizers import Tokenizer
import context_math_v1 as independent
HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[3]
CONTEXT_SHA='9bf168e90511708c2aa5e6248d1806c57e5fc48ffa1c97ceab218c757e5f76fb'
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def module(p,name):
 spec=importlib.util.spec_from_file_location(name,p);m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m);return m

def inputs(root):
 p=root/'experiments/sota-2026-10-22/epoch15/preparation/preflight-inputs.json';assert sha(p)=='eb2fa9bafb2ab41f5ec540b93b2b3707888b832974f8ed2322eb13448040e934';return p,json.loads(p.read_text())
def lexical(units,state,hyp):
 q=set(re.findall(r'\w+',hyp.casefold()));out=[]
 for i,u in enumerate(units):
  w=set(re.findall(r'\w+',state[u['start']:u['end']].casefold()));out.append((-len(q&w)/max(1,len(q|w)),i))
 return [i for _,i in sorted(out)[:40]]
def main():
 ap=argparse.ArgumentParser();ap.add_argument('--out',type=Path,required=True);a=ap.parse_args();assert not a.out.exists();s=ROOT/'experiments/sota-2026-10-22';cp=s/'candidate/epoch15/context.py';assert sha(cp)==CONTEXT_SHA;c=module(cp,'audit15_context_capacity_candidate')
 p,data=inputs(ROOT);assert set(data)>={'development','confirmation'};assets=s/'candidate/epoch15/assets/official-deberta-v3-large';nli=Tokenizer.from_file(str(assets/'tokenizer.json'));bge=Tokenizer.from_file(str(ROOT/'models/bge-small-en-v1.5/tokenizer.json'))
 for t in [nli,bge]:t.no_padding();t.no_truncation()
 cfg=json.loads((assets/'config.json').read_text());assert cfg['id2label']=={'0':'contradiction','1':'entailment','2':'neutral'} and cfg['hidden_size']==1024 and cfg['num_hidden_layers']==24
 static=json.loads((s/'candidate/epoch15/onnx-static.json').read_text());assert [(x['name'],x['tensor_element_type']) for x in static['inputs']]==[('input_ids',7),('attention_mask',7)] and len(static['outputs'])==1 and static['outputs'][0]['name']=='logits' and static['outputs'][0]['dimensions'][-1]['value']==3 and not static['external_initializers']
 cache={};result={};totalpacks=0
 for phase,expected in [('development',24),('confirmation',48)]:
  records=data[phase];assert len(records)==expected;observations=[]
  for row in records:
   assert 'evaluation' not in row and 'gold' not in row and 'annotations' not in row
   state=row['input']['state'];hyp=row['input']['questions']['decision']['criteria']['Yes'];sh=hashlib.sha256(state.encode()).hexdigest()
   canonical=json.dumps(row['input'],sort_keys=True,separators=(',',':'),ensure_ascii=False).encode();assert hashlib.sha256(canonical).hexdigest()==row['input_sha256']
   if sh not in cache:
    us=c.partition(state,nli,bge,target=128,nli_cap=160,bge_cap=256,max_units=192);assert us[0]['start']==0 and us[-1]['end']==len(state) and all(x['end']==y['start'] for x,y in zip(us,us[1:]))
    assert ''.join(state[u['start']:u['end']] for u in us)==state
    for u in us:assert u['nli_tokens']==len(nli.encode(state[u['start']:u['end']],add_special_tokens=False).ids)<=160 and u['bge_tokens']==len(bge.encode(state[u['start']:u['end']]).ids)<=256
    pr=independent.priority(state,us,nli);independent.check_priority(c.select_prelude(state,us,nli),pr);cache[sh]=(us,pr)
   us,pr=cache[sh];assert len(nli.encode('',hyp).ids)<=512 and len(bge.encode('Represent this sentence for searching relevant passages: '+hyp).ids)<=256
   orders=[list(range(min(40,len(us)))),lexical(us,state,hyp),list(reversed(range(len(us))))[:40],sorted(range(len(us)),key=lambda i:(i%2,i))[:40],sorted(range(len(us)),key=lambda i:(-(i%2),i))[:40]]
   orders += [[i] for i in range(len(us))]
   max_pair=0
   for order in orders:
    premise,coverage=c.pack(state,us,order,hyp,nli,prelude=c.select_prelude(state,us,nli));expect=independent.pack(state,us,order,hyp,nli,pr['selected_unit_ids']);pseudo={'coverage':coverage,'chunk_ids':coverage['selected_chunk_ids_rank_order'],'chunk_spans':[[us[i]['start'],us[i]['end']] for i in coverage['selected_chunk_ids_rank_order']],'premise':premise,'hypothesis':hyp,'ranking_ids':order}
    independent.check_pack(pseudo,expect,state,us,order,hyp,nli,pr);enc=nli.encode(premise,hyp);assert len(enc.ids)<=512 and enc.ids[0]==1 and enc.ids[-1]==2 and all(v==1 for v in enc.attention_mask) and enc.type_ids[0]==0 and enc.type_ids[-1]==1;assert len(premise.encode())<=16*1024
    max_pair=max(max_pair,len(enc.ids));totalpacks+=1
   observations.append({'id':row['id'],'input_sha256':row['input_sha256'],'source_state_SHA256':sh,'source_units':len(us),'definition_priority_unit_ids':pr['selected_unit_ids'],'definition_priority_tokens':pr['priority_tokens'],'orders_checked':len(orders),'max_checked_pair_tokens':max_pair})
  result[phase]={'n':expected,'unique_documents':len({r['source_state_SHA256'] for r in observations}),'max_units':max(r['source_units'] for r in observations),'priority_nonempty_queries':sum(bool(r['definition_priority_unit_ids']) for r in observations),'rows':observations}
 out={'schema_version':1,'at':datetime.now(timezone.utc).isoformat(),'status':'INDEPENDENT_LABEL_FREE_CONTEXT_CAPACITY_PASS','context_SHA256':sha(cp),'independent_math_SHA256':sha(HERE/'context_math_v1.py'),'label_free_inputs_SHA256':sha(p),'model_tokenizer_SHA256':sha(assets/'tokenizer.json'),'BGE_tokenizer_SHA256':sha(ROOT/'models/bge-small-en-v1.5/tokenizer.json'),'phases':result,'actual_tokenization_pack_checks':totalpacks,'scope':'All fixed DEV/metadata-reconstructedCONF inputs,complete partition and allsingleanchor+neighbors plus5 fullrankorders checked. Not all40!orders; runtime hardguard still mandatory. No annotation choices or model/native/session calls, no generalization score.','auditor_model_native_session_fit_paid_GPU_calls':0,'confirmation_gold_jsonl_parsed':False}
 raw=(json.dumps(out,indent=2)+'\n').encode()
 with a.out.open('xb') as f:f.write(raw)
 print(json.dumps({'status':out['status'],'sha256':hashlib.sha256(raw).hexdigest(),'phases':{p:{k:v for k,v in x.items() if k!='rows'} for p,x in result.items()},'actual_tokenization_pack_checks':totalpacks}))
if __name__=='__main__':main()
