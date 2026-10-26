"""Inert invented packing fixtures; no real tokenizer, source bodies or model calls."""
import argparse,ast,hashlib,importlib.util,json,math,os
from pathlib import Path
from types import SimpleNamespace

P='experiments/sota-2026-10-22/'
ARMS=['qwen_native_joint_context','qwen_lexical_joint_context','qwen_source_order_joint_context']
def require(v,why):
 if not v:raise ValueError(why)
def sha(b):return hashlib.sha256(b).hexdigest()
def canonical(v):return json.dumps(v,sort_keys=True,separators=(',',':')).encode()
def load(path):
 spec=importlib.util.spec_from_file_location('inert_compact_packing',path);m=importlib.util.module_from_spec(spec);exec(compile(path.read_bytes(),str(path),'exec'),m.__dict__);return m
class DummyCatalog:
 @staticmethod
 def validate_spans(spans):
  require(type(spans)is list and spans and all(type(s['sentence'])is str and s['sentence'] for s in spans),'INERT_NONEMPTY_SOURCE_UNITS')
class DummyReader:
 def __init__(self,base=120,costs=None,overflow=False):self.base=base;self.costs=costs or {};self.overflow=overflow;self.calls=[]
 def tokenize(self,prompt):
  # A deterministic invented length oracle, never the actual Qwen tokenizer.
  present=[name for name in self.costs if name in prompt]
  count=self.base+sum(self.costs[n]for n in present)
  if self.overflow and len(present)==2:count=321
  tokens=list(range(count));self.calls.append(prompt)
  return tokens,{'inert_receipt_ordinal':len(self.calls),'actual_HTTP_calls':0}
class DummyProtocol:
 SYSTEM='INERT SYSTEM'
 MAX_PROMPT_TOKENS=320
 @staticmethod
 def build_prompt(claim,windows):
  user='SOURCE EXCERPT 1:\n'+windows[0]+'\n\nSOURCE EXCERPT 2:\n'+windows[1]+'\n\nCLAIM:\n'+claim+'\n\nANSWER (N, E, or C):'
  return '<|im_start|>system\n'+DummyProtocol.SYSTEM+'<|im_end|>\n<|im_start|>user\n'+user+'<|im_end|>\n<|im_start|>assistant\n'
def main(a):
 root=Path(a.public_project);file=root/P/'runtime/epoch47/packing.py';m=load(file)
 C=SimpleNamespace(require=require,sha_json=lambda v:sha(canonical(v)))
 def record(names):
  start=0;units=[]
  for name in names:
   units.append({'sentence':name,'start':start,'end':start+len(name)});start+=len(name)+1
  return {'id':'invented-metadata-only','claim':'INERT CLAIM - exactly 17.5 on 2031-01-02','evidence':units}
 cases=[];calls=0
 def build(name,names,costs,rank=None,base=120,overflow=False,arm=ARMS[0]):
  nonlocal calls
  r=record(names);reader=DummyReader(base,costs,overflow);journal=[];calls+=1
  try:value=m.build(C,DummyProtocol,DummyCatalog,r,rank if rank is not None else list(range(len(names))),arm,reader,journal);error=None
  except ValueError as e:value=None;error=str(e)
  return r,reader,journal,value,error
 for arm in ARMS:
  r,reader,j,value,error=build('skip_long_first',['UNIT_TOO_LONG','UNIT_SECOND','UNIT_THIRD'],{'UNIT_TOO_LONG':101,'UNIT_SECOND':80,'UNIT_THIRD':90},arm=arm)
  require(error is None and [w['source_unit_ids']for w in value['windows']]==[[1],[2]],'FIRST_ADMISSIBLE_SINGLETONS')
  require(value['packing_policy']=='TWO_DISJOINT_WHOLE_SOURCE_UNIT_ANCHORS'and value['no_truncation']is True and value['full_claim_preserved']is True,'POLICY_AND_TEXT_PRESERVED')
  require(value['prompt_token_count']==290 and all(r['claim']in p for p in reader.calls),'EXACT_WHOLE_CLAIM_ALL_PROBES')
  require([x['stage']for x in j]==['EMPTY_WINDOWS_BASE','WHOLE_UNIT_PROPOSAL','WHOLE_UNIT_PROPOSAL','WHOLE_UNIT_PROPOSAL','WHOLE_UNIT_PROPOSAL','FINAL_COMBINED_PROMPT'],'EXACT_SCANNED_PROPOSAL_ORDER')
  require(all(len(w['source_unit_ids'])==len(w['source_spans'])==1 and w['duplicate_first']is False for w in value['windows']),'SINGLETON_DISJOINT_NO_DUPLICATION')
  require(all(d['group_unit_ids']==d['proposed_unit_ids']==[d['anchor']]for w in value['windows']for d in w['selection_decisions']),'NO_NEIGHBOR_GROUP')
  require([d['accepted']for d in value['windows'][0]['selection_decisions']]==[False,True]and [d['accepted']for d in value['windows'][1]['selection_decisions']]==[False,True],'STOP_AFTER_FIRST_ACCEPTED')
  cases.append({'name':'same_policy_all_arms:'+arm,'checks_passed':True})
 r,reader,j,value,error=build('exact_boundary',['BOUNDARY_A','BOUNDARY_B'],{'BOUNDARY_A':100,'BOUNDARY_B':100})
 require(error is None and value['prompt_token_count']==320,'INCLUSIVE320_BOUNDARY');cases.append({'name':'inclusive320_boundary','checks_passed':True})
 _,_,_,_,error=build('no_first',['LARGE_A','LARGE_B'],{'LARGE_A':101,'LARGE_B':102})
 require(error=='NO_WHOLE_SOURCE_UNIT_FITS','FIRST_WINDOW_FAILURE_NO_FALLBACK');cases.append({'name':'no_first_whole_unit','checks_passed':True})
 _,_,_,_,error=build('no_second',['SMALL_A','LARGE_B'],{'SMALL_A':80,'LARGE_B':101})
 require(error=='NO_SECOND_DISJOINT_WHOLE_SOURCE_UNIT_FITS','NO_DUPLICATE_FIRST_FALLBACK');cases.append({'name':'second_disjoint_failure_no_duplicate','checks_passed':True})
 _,_,_,_,error=build('claim_too_large',['SMALL_A','SMALL_B'],{'SMALL_A':1,'SMALL_B':1},base=320)
 require(error=='FULL_CLAIM_INSTRUCTIONS_CANNOT_FIT','FULL_CLAIM_BUDGET_FAILURE');cases.append({'name':'base_exhausts_full_cap','checks_passed':True})
 _,_,_,_,error=build('combined_overflow',['SMALL_A','SMALL_B'],{'SMALL_A':80,'SMALL_B':90},overflow=True)
 require(error=='COMBINED_PROMPT_OVERFLOW_NO_TRUNCATION_OR_RETRY','COMBINED_FAIL_NO_TRUNCATION');cases.append({'name':'final_combined_overflow_no_retry','checks_passed':True})
 for name,rank in [('duplicate_rank',[0,0]),('foreign_rank',[0,2]),('boolean_rank',[False,1])]:
  _,reader,j,_,error=build(name,['SMALL_A','SMALL_B'],{'SMALL_A':80,'SMALL_B':90},rank=rank)
  require(error=='EXACT_RANKING_REQUIRED'and reader.calls==[]and j==[],'RANK_REJECTED_BEFORE_ORACLE');cases.append({'name':name,'checks_passed':True})
 r,reader,j,value,error=build('one_unit',['ONLY_A'],{'ONLY_A':80})
 require(error=='NO_SECOND_DISJOINT_WHOLE_SOURCE_UNIT_FITS','ONE_UNIT_HAS_NO_DUPLICATE_FALLBACK');cases.append({'name':'single_source_unit_stops','checks_passed':True})
 r,reader,j,value,error=build('rank_order',['ANCHOR_A','ANCHOR_B','ANCHOR_C'],{'ANCHOR_A':10,'ANCHOR_B':10,'ANCHOR_C':10},rank=[2,0,1])
 require(error is None and [w['source_unit_ids']for w in value['windows']]==[[2],[0]],'EXACT_RANK_ORDER_NOT_SOURCE_ORDER');cases.append({'name':'ranking_order_selects_first_two','checks_passed':True})
 common=ast.parse((root/P/'runtime/epoch47/common.py').read_text());admit=next(n for n in common.body if isinstance(n,ast.FunctionDef)and n.name=='admit');literal_checks=[n for n in ast.walk(admit)if isinstance(n,ast.Constant)and n.value=='PLAN_COMPACT_WHOLE_UNIT_CONTEXT_POLICY'];require(len(literal_checks)==1,'COMPACT_POLICY_EARLY_ADMISSION')
 result={'schema_version':1,'epoch':47,'kind':'REAL_CONTRACTNLI_QWEN_COMPACT_EVIDENCE_DEV_PILOT','checks_passed':True,'source_only':True,'invented_fixture_count':len(cases),'cases':cases,'packing_function_calls_on_invented_metadata':calls,'actual_case_body_or_label_reads':0,'actual_tokenizer_or_HTTP_calls':0,'Node_native_BGE_model_or_Gold_calls':0,'source_packing':{'path':P+'runtime/epoch47/packing.py','bytes':file.stat().st_size,'sha256':sha(file.read_bytes())},'execution_authorized':False,'benchmark_quality_or_real_token_fit_claim':False,'scope':'Pure control-flow and exact invented-length boundary fixtures only. No actual tokenizer, model, selected source bank, benchmark labels or target runtime. Actual SOURCE readback/DATA/postDATA/runtime and physical acceptance remain mandatory.'}
 out=Path(a.out);require(out.is_absolute()and not out.exists(),'NEW_RESULT_REQUIRED');b=(json.dumps(result,sort_keys=True,indent=2)+'\n').encode()
 with out.open('xb')as f:f.write(b);f.flush();os.fsync(f.fileno())
 print(json.dumps({'checks_passed':True,'invented_fixtures':len(cases),'target_calls':0}))
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--public-project',required=True);p.add_argument('--out',required=True);main(p.parse_args())
