"""Independent exact-source/priority/token/native-vector saved-output replay.

No model/native sessions, extra forwards, network or fits. Prepared prelaunch.
"""
from pathlib import Path
from datetime import datetime,timezone
import argparse,hashlib,importlib.util,json,math
import numpy as np
from tokenizers import Tokenizer
import context_math_v1 as M
from context_preflight_v1 import lexical
HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[3]
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def obj(p):return json.loads(Path(p).read_text())
def rows(p):return [json.loads(x) for x in Path(p).read_text().splitlines() if x]
def module(p,n):
 sp=importlib.util.spec_from_file_location(n,p);m=importlib.util.module_from_spec(sp);sp.loader.exec_module(m);return m

def main():
 ap=argparse.ArgumentParser();ap.add_argument('--project',type=Path,required=True);ap.add_argument('--expected-plan-sha',required=True);ap.add_argument('--out',type=Path,required=True);a=ap.parse_args();assert not a.out.exists();root=a.project.resolve();s=root/'experiments/sota-2026-10-22';study=s/'epoch15';assert sha(study/'plan.json')==a.expected_plan_sha;plan=obj(study/'plan.json')
 for pin in plan['pins']:assert sha(root/pin['path'])==pin['sha256'],pin['path']
 base=s/'candidate/epoch6/context.py';assert sha(base)=='28bceb95282ec3e3e938f3211ccad04d2369fa29e1f191f187566339ae3b44d2';partition=module(base,'independent15_reviewed_partition').partition
 asset=s/'candidate/epoch15/assets/official-deberta-v3-large';assert sha(asset/'tokenizer.json')=='5124ef2ead1a10a717703bc436de7f353da76d6340e4587719b42b1693707964';nli=Tokenizer.from_file(str(asset/'tokenizer.json'));bge=Tokenizer.from_file(str(root/'models/bge-small-en-v1.5/tokenizer.json'))
 for t in [nli,bge]:t.no_padding();t.no_truncation()
 proofs=[];counts={'requests':0,'NLI_pairs':0,'NLI_tokens':0,'BGE_texts':0,'BGE_batches':0};phasecounts={};nativeagreements={'full_order':0,'candidate_set':0,'top2_set':0};priorities={};subsets={}
 for phase,n in [('development',24),('confirmation',48)]:
  run=study/'runs'/phase
  if not (run/'attempt.json').exists():continue
  actual=rows(run/'records.jsonl');expected=rows(root/plan['datasets'][phase]);assert len(actual)==len(expected)==n
  runtime=obj(run/'runtime.json');receipt=runtime['receipt'];assert receipt['nli']['label_indices']=={'contradiction':0,'entailment':1,'neutral':2} and receipt['nli']['model_sha256']=='821dc4407d10a9d25c20c57fcb742ddc20c09bc55c8093557091efb825256754'
  assert receipt['nli']['tokenizer_sha256']==receipt['nli']['policy_tokenizer_sha256']==sha(asset/'tokenizer.json') and receipt['nli']['precision']=='OFFICIAL_QUINT8_AVX2' and receipt['old_base_NLI_session_initialized'] is False
  assert receipt['active_Unigram_token_budget_adapter'] and receipt['definition_priority_token_cap']==160 and receipt['definition_priority_claim_independent'] and receipt['final_global_source_order']
  phasecounts[phase]={'requests':0,'NLI_pairs':0,'NLI_tokens':0,'BGE_texts':0,'BGE_batches':0}
  for e,r in zip(expected,actual):
   assert e['id']==r['id'] and r['input']==e['input'];state=r['input']['state'];hyp=r['input']['questions']['decision']['criteria']['Yes'];d=r['response']['diagnostics']['decision'];assert d['source_state']==state and d['source_state_sha256']==hashlib.sha256(state.encode()).hexdigest()
   units=partition(state,nli,bge,target=128,nli_cap=160,bge_cap=256,max_units=192);assert d['source_units']==units and d['full_source_partition'] and not d['source_partition_has_overlap'];assert ''.join(state[u['start']:u['end']] for u in units)==state
   spans=[[u['start'],u['end']] for u in units];assert d['chunk_spans']==spans and d['total_chunks']==len(units) and d['ranking_candidate_depth']==min(40,len(units))
   pre=M.priority(state,units,nli);M.check_priority(d['definition_priority'],pre)
   sh=hashlib.sha256(state.encode()).hexdigest()
   if sh in priorities:assert priorities[sh]==pre
   else:priorities[sh]=pre
   retrieval=d['retrieval'];evidence=retrieval['bundle_evidence'];bundlepath=run/'bundles'/evidence['relativefilename'];assert bundlepath.name==evidence['sha256']+'.json' and not bundlepath.is_symlink() and bundlepath.stat().st_size==evidence['bytes'] and sha(bundlepath)==evidence['sha256']==retrieval['native']['bundle_sha256']
   bundle=obj(bundlepath);vectors=np.asarray(bundle['vectors'],dtype=np.float64);query=np.asarray(bundle['query_vectors'],dtype=np.float64);assert vectors.shape==(len(units),384) and query.shape==(1,384) and np.isfinite(vectors).all() and np.isfinite(query).all();assert np.max(np.abs(np.linalg.norm(vectors,axis=1)-1))<1e-5 and abs(np.linalg.norm(query)-1)<1e-5
   native=retrieval['native'];assert native['native'] and native['package_version']=='0.1.33' and native['native_binary_sha256']==receipt['native_core_binary_sha256'] and native['vectors']==len(units)
   ids=native['queries'][0]['ids'];assert len(ids)==len(set(ids))==min(40,len(units)) and all(type(i) is int and 0<=i<len(units) for i in ids);assert retrieval['ranking_scope']['actual_returned_ids']==ids and retrieval['ranking_scope']['requested']==min(40,len(units))
   cosine=(vectors@query[0])/(np.linalg.norm(vectors,axis=1)*np.linalg.norm(query[0]));exact=sorted(range(len(units)),key=lambda i:(-cosine[i],i))[:min(40,len(units))];nativeagreements['full_order']+=ids==exact;nativeagreements['candidate_set']+=set(ids)==set(exact);nativeagreements['top2_set']+=set(ids[:2])==set(exact[:2])
   embedding=retrieval['embedding'];chunks=[state[u['start']:u['end']] for u in units];texts=([] if embedding['chunks']['cache_hit'] else chunks)+['Represent this sentence for searching relevant passages: '+hyp];examples=embedding['chunks']['examples']+embedding['query']['examples'];assert embedding['actual_embedded_texts']==len(texts) and len(examples)==len(texts)
   for text,tok in zip(texts,examples):
    count=len(bge.encode(text).ids);assert count<=256 and tok=={'raw_tokens':count,'used_tokens':count,'truncated':False}
   orders={'ruvector_top2':ids,'lexical_top2':lexical(units,state,hyp),'positional_first2':list(range(min(40,len(units))))};proof={'id':r['id'],'phase':phase,'priority_ids':pre['selected_unit_ids'],'priority_tokens':pre['priority_tokens'],'native_ranking_ids':ids,'exact_cosine_order':exact,'arms':{}}
   for name,order in orders.items():
    arm=d['arms'][name];expect=M.pack(state,units,order,hyp,nli,pre['selected_unit_ids']);counter=M.check_pack(arm,expect,state,units,order,hyp,nli,pre);enc=nli.encode(expect['premise'],hyp);dec=arm['decoding']
    assert dec['input_ids']==enc.ids and dec['attention_mask']==enc.attention_mask and dec['token_type_ids']==enc.type_ids and all(x==1 for x in enc.attention_mask)
    assert enc.ids[0]==1 and enc.ids[-1]==2 and enc.type_ids[0]==0 and enc.type_ids[-1]==1 and dec['actual_graph_inputs']==['attention_mask','input_ids']
    assert dec['active_Unigram_policy_pair_tokens']==dec['actual_model_pair_tokens']==len(enc.ids)<=512 and not dec['truncated'] and dec['padding_tokens']==0 and not arm['coverage']['claim_truncated']
    assert dec['model_repo']=='cross-encoder/nli-deberta-v3-large' and dec['model_revision']==plan['expected_nli_revision'] and dec['onnx_sha256']==plan['expected_nli_sha256']
    phasecounts[phase]['NLI_pairs']+=1;phasecounts[phase]['NLI_tokens']+=len(enc.ids);proof['arms'][name]={'selected_unit_ids':expect['selected'],'source_spans':expect['spans'],'pair_tokens':expect['tokens'],'source_character_count':expect['chars'],'numeric_retained':sum(x['retained'] for x in expect['numbers']),'no_priority_source_comparison':counter}
   primary=d['arms']['ruvector_top2'];control={'state':primary['premise'],'questions':r['input']['questions']};assert d['baseline_control_input']==control and d['baseline_control_source_chunk_ids']==primary['chunk_ids'] and d['baseline_control_label']=='native104_on_ruvector_evidence'
   raw=json.dumps(control,ensure_ascii=False,separators=(',',':'),allow_nan=False).encode();assert hashlib.sha256(raw).hexdigest()==d['baseline_control_input_sha256'];assert len(primary['premise'].encode())<=16*1024
   phasecounts[phase]['requests']+=1;phasecounts[phase]['BGE_texts']+=len(texts);phasecounts[phase]['BGE_batches']+=embedding['chunks']['model_batches']+embedding['query']['model_batches'];proofs.append(proof)
  for k,v in phasecounts[phase].items():counts[k]+=v
  terminal=obj(run/'final-engine.json');counters=terminal.get('execution_counters',terminal.get('counters',{}));subsets[phase]={'final_engine_counter_keys':sorted(counters)}
 assert phasecounts and counts['NLI_pairs']==counts['requests']*3
 result={'schema_version':1,'at':datetime.now(timezone.utc).isoformat(),'checks_passed':True,'scope':'Actual saved phase exact-source, sharedpriority,tokenizer,matchedselector andnative-vector bundle verification. No extra model/native calls. No-priority context is tokenization-only, never an accuracy ablation.','plan_SHA256':a.expected_plan_sha,'independent_math_SHA256':sha(HERE/'context_math_v1.py'),'counts':counts,'phase_counts':phasecounts,'native_exact_agreement_counts':nativeagreements,'shared_claim_independent_priority_documents':len(priorities),'rows':proofs,'resource_counter_metadata':subsets,'semantic_sufficiency_or_numeric_truth_established':False,'official_score':None,'official_rank':None,'SOTA_established':False,'auditor_model_native_session_fit_paid_GPU_calls':0}
 raw=(json.dumps(result,indent=2)+'\n').encode()
 with a.out.open('xb') as f:f.write(raw)
 print(json.dumps({'checks_passed':True,'sha256':hashlib.sha256(raw).hexdigest(),'counts':counts,'native_exact_agreements':nativeagreements}))
if __name__=='__main__':main()
