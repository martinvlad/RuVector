"""Replay a source-only prelaunch revised mechanism finding on already exposed DEV13.

The exact revised context implementation is preserved as text. No model/native
session/forward occurs. This is a mechanical coverage check, not benchmark gain.
"""
from pathlib import Path
from datetime import datetime,timezone
from tokenizers import Tokenizer
import argparse,hashlib,json,types
HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[3]
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def main():
 ap=argparse.ArgumentParser();ap.add_argument('--out',type=Path,required=True);a=ap.parse_args();assert not a.out.exists()
 saved=HERE/'reviewed-context-v2.py.txt';assert sha(saved)=='9bf168e90511708c2aa5e6248d1806c57e5fc48ffa1c97ceab218c757e5f76fb'
 original=ROOT/'experiments/sota-2026-10-22/candidate/epoch15/context.py';c=types.ModuleType('audit15_prelaunch_initial_context');c.__file__=str(original);exec(compile(saved.read_text(),str(original),'exec'),c.__dict__)
 asset=ROOT/'experiments/sota-2026-10-22/candidate/epoch15/assets/official-deberta-v3-large/tokenizer.json';nli=Tokenizer.from_file(str(asset));bge=Tokenizer.from_file(str(ROOT/'models/bge-small-en-v1.5/tokenizer.json'))
 for t in [nli,bge]:t.no_padding();t.no_truncation()
 source=ROOT/'experiments/sota-2026-10-22/epoch13/runs/development/records.jsonl';rows=[json.loads(x) for x in source.read_text().splitlines() if x];seen=set();out=[]
 for r in rows:
  if r['source_group'] in seen:continue
  seen.add(r['source_group']);state=r['input']['state'];units=c.partition(state,nli,bge,target=128,nli_cap=160,bge_cap=256,max_units=192);pre=c.select_prelude(state,units,nli)
  out.append({'source_group':r['source_group'],'source_state_SHA256':hashlib.sha256(state.encode()).hexdigest(),'source_unit_count':len(units),'selected_unit_ids':pre['selected_unit_ids'],'priority_tokens':pre['priority_tokens'],'candidate_attempts':pre['candidate_attempts']})
 explicit=sum('explicit-definition-marker' in x['triggers'] and x['accepted'] for g in out for x in g['candidate_attempts']);nonempty=sum(bool(g['selected_unit_ids']) for g in out)
 assert len(out)==8 and explicit>=1 and nonempty==8
 bygroup={x['source_group']:x for x in out};assert bygroup['original-contractnli:324']['priority_tokens']==155 and bygroup['original-contractnli:419']['priority_tokens']==153
 assert [x['span'] for x in bygroup['original-contractnli:324']['candidate_attempts'] if x['accepted']]==[[0,688]]
 assert [x['span'] for x in bygroup['original-contractnli:419']['candidate_attempts'] if x['accepted']]==[[0,643]]
 result={'schema_version':1,'at':datetime.now(timezone.utc).isoformat(),'status':'PRELAUNCH_SOURCE_MECHANISM_ENGAGES_ON_EXPOSED_SUPPORTING_EXAMPLES','scope':'Only permanently exposed epoch13DEV source tokenization. No new DEV/CONF labels, model/native/session calls or benchmark generalization.','reviewed_context_SHA256':sha(saved),'model_tokenizer_SHA256':sha(asset),'old_records_SHA256':sha(source),'groups':out,'summary':{'groups':8,'groups_with_priority_units':nonempty,'groups_without_priority_units':8-nonempty,'admitted_explicit_definition_marker_units':explicit,'admitted_initial_party_units':sum('initial-party-declaration' in x['triggers'] and x['accepted'] for g in out for x in g['candidate_attempts'])},'finding':'The revised160token exact-source whole-unit selector preserves the missing source-prefix linkage on exposed324[0,688]/155tokens and419[0,643]/153tokens. All eight old groups receive priority spans. This verifies mechanical engagement, not semantic accuracy or sufficient evidence.','interpretation':'Root authorized this single revision before new roles/labels or model outputs. Mechanical engagement is now verified, while prior generic-reader semantic failures remain unresolved; admission still requires the complete separate prelaunch audit and frozen gates.','new_model_native_fit_paid_GPU_calls':0,'new_DEV_or_confirmation_labels_accessed':False}
 raw=(json.dumps(result,indent=2)+'\n').encode()
 with a.out.open('xb') as f:f.write(raw)
 print(json.dumps({'status':result['status'],'bytes':len(raw),'sha256':hashlib.sha256(raw).hexdigest(),'summary':result['summary']}))
if __name__=='__main__':main()
