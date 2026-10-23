"""Freeze public epoch13 source, official metadata and exact read-only dependencies; never infer."""
from pathlib import Path
import hashlib,json
HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[3]
def sha(path):
 h=hashlib.sha256()
 with path.open('rb') as stream:
  for b in iter(lambda:stream.read(1024*1024),b''):h.update(b)
 return h.hexdigest()
def load(p):return json.loads(p.read_text())
def item(path):return {'path':str(path.relative_to(ROOT)),'bytes':path.stat().st_size,'sha256':sha(path)}
def save(path,value):
 with path.open('x') as stream:json.dump(value,stream,indent=2);stream.write('\n')
def main():
 sources=[item(p) for p in sorted(HERE.iterdir()) if p.is_file() and p.name not in ('proposal-manifest.json','public-allowlist-v1.json') and p.suffix in ('.py','.json','.md','.txt')]
 sources += [item(HERE/'research'/name) for name in ('README.md','config.json','official-api.json')]
 old=load(HERE.parent/'epoch11/proposal-manifest.json');deps={x['path']:x for x in old['read_only_code_dependencies']}
 for name in ('models.py','runtime.py'):
  path=HERE.parent/'epoch11'/name;deps[str(path.relative_to(ROOT))]=item(path)
 for x in deps.values():assert item(ROOT/x['path'])==x
 assets=load(HERE/'assets.lock.json');assert len(assets['assets'])==22
 for x in assets['assets']:assert item(ROOT/x['path'])==x
 choice=load(HERE/'model-choice.json');config=load(HERE/'config.json')
 assert sha(HERE/'config.json') in (HERE/'runtime.py').read_text()
 assert sha(HERE/'model-assets.lock.json') in (HERE/'acquire_assets.py').read_text()
 roles=[item(ROOT/config['data_contract_path'])]
 manifest={'schema_version':1,'candidate_id':'ruvector-native-official-roberta-semantic-threeway-epoch13','status':'SOURCE_FROZEN_PENDING_INDEPENDENT_FINAL_PLAN_ACCEPTANCE',
 'runtime_module':'candidate.epoch13.runtime','runtime_class':'CandidateEngine','runtime_API':'CandidateEngine(artifact_path=None); predict(state,questions); close(); execution_snapshot(); no TRAIN/fit/sanity API',
 'config':item(HERE/'config.json'),'sources':sources,'read_only_code_dependencies':[deps[k] for k in sorted(deps)],'assets_manifest':item(HERE/'assets.lock.json'),'data_role_pins':roles,
 'model_identity':{'repo':choice['repo'],'revision':choice['revision'],'onnx_sha256':'50dbf8939f1fdc45ae31fd6c1e6680489c6560b0f5e37b13da0e7979b8384ad0','onnx_bytes':498911192,'precision':'FP32','labels':{'0':'contradiction','1':'entailment','2':'neutral'},'typed_order':['Entailment','Contradiction','NotMentioned'],'mapping':'Yes=P(E);No=P(C)+P(N);T1;exacthalf-tieNo','layers':12,'hidden_size':768},
 'hypothesis':choice['hypothesis'],'configs_in_grid':1,'training':[],'calibration':[],'training_or_calibration_fit':False,'training_labels_read_by_candidate':False,
 'data_freeze_before_choice':{'data_frozen_at':choice['data_freeze_before_choice']['roles_frozen_at'],'choice_at':choice['chosen_at_utc'],'data_contract_sha256':config['data_contract_sha256']},
 'exact_frozen_context_algorithm_sha256':config['frozen_context_algorithm_sha256'],'unchanged_epoch6_context_algorithm':True,'unchanged_epoch6_context_policy':False,'exact_epoch6_context_strings':False,'active_BPE_token_budget_adapter':True,
 'actual_model_tokenizer_sha256':config['active_context_and_model_tokenizer_sha256'],'ranking_anchor_cap_all_arms':40,'same_neighbor_expansion_and512_token_context_policy':True,'new_decoder_token_guard':512,'batch_size':1,'temperature':1,'padding':False,'truncation':False,
 'native_control':'Native104 on exactly primary packed excerpt, not original full champion','confirmation_separation':config['confirmation_separation'],'tests':load(HERE/'tests-result.json'),'static_model_check':item(HERE/'onnx-static.json'),'static_cpu_feasibility':choice['static_cpu_feasibility'],
 'new_model_forwards':0,'new_native_calls':0,'new_evaluation_inputs_or_labels_read':0,'free_public_model_asset_bytes_verified':sum(x['bytes'] for x in load(HERE/'model-assets.lock.json')['assets']),'paid_calls':0,'GPU':0,
 'execution_authority':'Parent only after independent source/data/runtime acceptance. DEV24 process, conditional unchanged CONF48 process; eachCPU2/600seconds including init/cleanup,max2nonretryable. No TRAIN,fit,calibration,model/native probes or further model choice.'}
 save(HERE/'proposal-manifest.json',manifest)
 save(HERE/'public-allowlist-v1.json',{'schema_version':1,'scope':'Reviewed public source, official card/config/API metadata, static graph report and public acquisition receipt only. Pretrained weights/tokenizers/native binaries and private/raw payloads excluded.','files':sources+[item(HERE/'proposal-manifest.json')]})
 print(json.dumps({'proposal_sha256':sha(HERE/'proposal-manifest.json'),'source_files':len(sources),'readonly_dependencies':len(deps),'asset_pins':len(assets['assets']),'public_allowlist_sha256':sha(HERE/'public-allowlist-v1.json')}))
if __name__=='__main__':main()
