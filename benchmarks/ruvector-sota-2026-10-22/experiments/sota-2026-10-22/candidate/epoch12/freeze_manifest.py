"""Freeze public epoch12 source and explicit inherited dependencies; never infer."""
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
 assert len(sources)==17
 old=load(HERE.parent/'epoch11/proposal-manifest.json')
 deps={x['path']:x for x in old['read_only_code_dependencies']}
 for name in ('model-assets.lock.json','proposal-manifest.json','model-choice.json','provenance.json'):
  path=HERE.parent/'epoch11'/name;deps[str(path.relative_to(ROOT))]=item(path)
 for x in deps.values():assert item(ROOT/x['path'])==x
 assets=load(HERE/'assets.lock.json');assert len(assets['assets'])==23
 for x in assets['assets']:assert item(ROOT/x['path'])==x
 choice=load(HERE/'model-choice.json');config=load(HERE/'config.json')
 assert sha(HERE/'config.json') in (HERE/'runtime.py').read_text()
 assert sha(HERE/'model-assets.lock.json') in (HERE/'acquire_assets.py').read_text()
 roles=[item(ROOT/config['training_allowlist_path']),item(ROOT/config['training_contract_path'])]
 manifest={'schema_version':1,'candidate_id':'ruvector-native-fixed-FP32-large-threeway-variant-fidelity-epoch12','status':'SOURCE_FROZEN_PENDING_INDEPENDENT_FINAL_PLAN_ACCEPTANCE',
 'runtime_module':'candidate.epoch12.runtime','runtime_class':'CandidateEngine',
 'runtime_API':'CandidateEngine(artifact_path=None, enable_training_sanity=False); predict_train_sanity(state,questions,example_id); finish_training_sanity(); predict(state,questions); close(); execution_snapshot()',
 'config':item(HERE/'config.json'),'sources':sources,'read_only_code_dependencies':[deps[k] for k in sorted(deps)],'assets_manifest':item(HERE/'assets.lock.json'),'data_role_pins':roles,
 'model_identity':{'repo':choice['repo'],'revision':choice['revision'],'onnx_sha256':choice['onnx_sha256'],'onnx_bytes':choice['onnx_bytes'],'precision':'FP32','labels':{'0':'entailment','1':'neutral','2':'contradiction'},'typed_order':['Entailment','Contradiction','NotMentioned'],'mapping':choice['binary_mapping'],'layers':24,'hidden_size':1024},
 'TRAIN_only_diagnostic_model':choice['quantized_diagnostic'],'hypothesis':choice['hypothesis'],'configs_in_grid':1,'fitting_training':[],'calibration':[],'training_or_calibration_fit':False,'TRAIN_sanity_n':6,'TRAIN_already_exposed_groups':['original-contractnli:288','original-contractnli:239'],'training_labels_read_by_candidate':False,'precision_fixed_before_TRAIN_outputs':True,'quantized_session_only_phase1_then_released_before_DEV':True,
 'data_freeze_before_choice':{'data_frozen_at':choice['data_frozen_at'],'choice_at':choice['selected_at'],'data_contract_sha256':choice['data_contract_sha256']},
 'exact_frozen_context_policy_sha256':'28bceb95282ec3e3e938f3211ccad04d2369fa29e1f191f187566339ae3b44d2',
 'unchanged_policy_tokenizer_sha256':config['frozen_context_tokenizer_sha256'],'actual_model_tokenizer_sha256':config['actual_model_tokenizer_sha256'],'ranking_anchor_cap_all_arms':40,'same_neighbor_expansion_and512_token_context_policy':True,'new_decoder_token_guard':512,'batch_size':1,'temperature':1,'padding':False,'truncation':False,
 'native_control':'Native104 on exactly primary packed excerpt, not original full champion','confirmation_separation':config['confirmation_separation'],'tests':load(HERE/'tests-result.json'),'static_model_check':item(HERE/'onnx-static.json'),'variant_provenance_limit':choice['variant_provenance_limit'],
 'new_model_forwards':0,'new_native_calls':0,'new_evaluation_inputs_or_labels_read':0,'free_public_FP32_asset_bytes_verified':1741989392,'paid_calls':0,'GPU':0,
 'execution_authority':'Parent only after independent source/data/runtime acceptance. One combined initialization+TRAIN6+INT8release+DEV24 process; conditional fixedFP32 CONF48 process; each CPU2/600s inclcleanup, max2nonretryable. No model/native probes or fitting outside these processes.'}
 save(HERE/'proposal-manifest.json',manifest)
 allow={'schema_version':1,'scope':'Reviewed public source/provenance/static metadata/exact acquisition receipts only. Pretrained weights, native binaries, tokenizers and private/raw payloads excluded.','files':sources+[item(HERE/'proposal-manifest.json')]}
 save(HERE/'public-allowlist-v1.json',allow)
 print(json.dumps({'proposal_sha256':sha(HERE/'proposal-manifest.json'),'source_files':len(sources),'readonly_dependencies':len(deps),'asset_pins':len(assets['assets']),'public_allowlist_sha256':sha(HERE/'public-allowlist-v1.json')}))
if __name__=='__main__':main()
