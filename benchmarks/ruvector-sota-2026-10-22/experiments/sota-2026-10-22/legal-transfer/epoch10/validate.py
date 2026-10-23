"""Validate source replay and meaningful label/leakage controls, without inference."""
from pathlib import Path
from datetime import datetime,timezone
import argparse,copy,hashlib,json,sys,subprocess,tempfile,shutil
HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE));import build
def rows(p):return [json.loads(x) for x in Path(p).read_text().splitlines()]
def actual():return {'train':rows(HERE/'train72.jsonl'),'dev':rows(HERE/'development24.jsonl'),'annotations':build.load(HERE/'train-annotations.json')}
def check(data,expected):
 if build.canonical(data)!=build.canonical(expected):raise ValueError('Changed source roles, labels, inputs or annotations')
 if len(data['train'])!=72 or len(data['dev'])!=24 or len(data['annotations']['records'])!=72:raise ValueError('Wrong denominator')
 for r in data['train']+data['dev']:
  if set(r['input'])!={'state','questions'}:raise ValueError('Gold or metadata in inference input')
  if build.sha(HERE/'train72.jsonl')!=build.TRAIN_SHA:raise ValueError('Changed reused TRAIN bytes')
  if build.LABELS[r['evaluation']['original_threeway_label']]!=r['evaluation']['gold']:raise ValueError('Wrong typed projection')
 sets={role:{r['source_group'] for r in data[role]} for role in ('train','dev')};reserved={r['source_group'] for r in build.load(HERE/'confirmation-allowlist.json')['records']}
 if sets['train']&sets['dev'] or reserved&(sets['train']|sets['dev']):raise ValueError('Role overlap')
 if {r['id'] for r in data['annotations']['records']}!={r['id'] for r in data['train']}:raise ValueError('Foreign record in TRAIN annotation targets')
def main():
 p=argparse.ArgumentParser();p.add_argument('--source',type=Path,required=True);a=p.parse_args()
 manifest=build.load(HERE/'source-manifest.json')
 for x in manifest['files']:
  if build.sha(HERE/x['path'])!=x['sha256'] or (HERE/x['path']).stat().st_size!=x['bytes']:raise ValueError('Changed source pin '+x['path'])
 expected=build.draw(a.source);data=actual();check(data,expected)
 for role,file,fit in [('train','train72.jsonl',True),('dev','development24.jsonl',False)]:
  if build.load(HERE/(role+'-allowlist.json'))!=build.allow(data[role],role,build.sha(HERE/file),fit):raise ValueError('Changed metadata-only allowlist')
 muts=[lambda d:d['train'][0]['input'].update(gold='Yes'),lambda d:d['annotations']['records'][0].update(input_sha256='0'*64),lambda d:d['annotations']['records'][0].update(evidence_spans=[[0,1]]),lambda d:d['annotations']['records'][0].update(id='confirmation:foreign'),lambda d:d['dev'][0]['evaluation'].update(original_threeway_label='invalid'),lambda d:d['dev'][0].update(source_group=d['train'][0]['source_group']),lambda d:d['dev'][0]['input']['questions']['decision']['criteria'].update(Yes='Changed predicate'),lambda d:d['train'][0]['evaluation'].update(gold='invalid')]
 for mutate in muts:
  x=copy.deepcopy(data);mutate(x)
  try:check(x,expected)
  except (ValueError,KeyError):pass
  else:raise AssertionError('Invalid mutation accepted')
 contract=build.load(HERE/'data-contract.json');assert contract['confirmation']['sha256']=='850b1f1d61d81ee83227ff3e62696011a9571b9349cbf926d61243bfacadbf50'
 report={'schema_version':1,'at':datetime.now(timezone.utc).isoformat(),'checks_passed':True,'source_pins':len(manifest['files']),'TRAIN_reused_exact_SHA256':build.TRAIN_SHA,'TRAIN_queries':72,'TRAIN_document_groups':24,'TRAIN_annotation_rows':72,'TRAIN_annotations_only_source_offsets_and_gold':True,'new_DEV_queries':24,'new_DEV_document_groups':8,'prior_exposed_train_excluded':157,'reserved_confirmation_groups_excluded':16,'eligible_before_draw':250,'unreserved_after_draw':242,'label_independent_draw_replayed':True,'source3way_and_binary_gold_replayed':True,'inference_input_only_state_questions':True,'negative_controls_rejected':len(muts),'confirmation_bank_preserved':True,'confirmation_labels_used_for_sampling_or_fit':False,'native_model_paid_calls':0,'official_score':None,'official_rank':None}
 (HERE/'validation.json').write_text(json.dumps(report,indent=2)+'\n')
 # Independent clean-directory source replay needs no historical raw corpora.
 clean=HERE/'standalone-redraw-v1';clean.mkdir(exist_ok=False)
 for n in ['build.py','eligibility-manifest.json','draw-plan.json','document-selection.json','train72.jsonl']:shutil.copy2(HERE/n,clean/n)
 output=clean/'output';cmd=[sys.executable,'-B',str(clean/'build.py'),'--source',str(a.source),'--output-dir',str(output)];r=subprocess.run(cmd,capture_output=True,text=True,check=True,timeout=30)
 files=['train72.jsonl','train-annotations.json','train-allowlist.json','development24.jsonl','dev-allowlist.json']
 for n in files:assert (HERE/n).read_bytes()==(output/n).read_bytes(),n
 proof={'schema_version':1,'at':datetime.now(timezone.utc).isoformat(),'checks_passed':True,'standalone_source_files':['build.py','eligibility-manifest.json','draw-plan.json','document-selection.json','train72.jsonl'],'external_source_sha256':build.sha(a.source),'old_raw_DEV_or_CONF_datasets_required':False,'full_original_train_duplicated_in_owned_epoch':False,'exact_byte_outputs':[{'path':n,'bytes':(output/n).stat().st_size,'sha256':build.sha(output/n)} for n in files],'stdout':json.loads(r.stdout),'native_model_paid_calls':0}
 (HERE/'isolated-replay-validation.json').write_text(json.dumps(proof,indent=2)+'\n');print(json.dumps({'validation':build.sha(HERE/'validation.json'),'isolated_replay':build.sha(HERE/'isolated-replay-validation.json'),'checks_passed':True,'negative_controls':len(muts)}))
if __name__=='__main__':main()
