"""Create immutable epoch15 result metadata from actual independently audited evidence.

No inference, model loading, training, selection, publication, or source editing.
"""
from pathlib import Path
from datetime import datetime, timezone
import argparse, hashlib, json, os

ROOT = Path(__file__).resolve().parents[3]
S = ROOT / 'experiments/sota-2026-10-22'
E = S / 'epoch15'
PLAN_SHA = '82cfe2fd0ab18ad1c7c1f6372df97925061832d6e809701cfcc9a53a37dcfc3f'

def read(p): return json.loads(Path(p).read_text())
def sha(p): return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def ident(p):
    p = Path(p)
    return {'path': str(p.relative_to(ROOT)), 'bytes': p.stat().st_size, 'sha256': sha(p)}
def write(p, value):
    raw = (json.dumps(value, ensure_ascii=False, indent=2) + chr(10)).encode()
    with Path(p).open('xb') as f:
        f.write(raw); f.flush(); os.fsync(f.fileno())

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--independent-decision', type=Path, required=True)
    a = ap.parse_args()
    decision = read(a.independent_decision)
    scores_path = S/'audit/epoch15/actual-scores-independent-v1.json'
    context_path = S/'audit/epoch15/actual-context-independent-v1.json'
    roles_path = S/'legal-transfer/epoch15/postrun-identity-retirement-v1.json'
    analysis_path = S/'candidate/epoch15/postrun-error-analysis-v1.json'
    scores, context = read(scores_path), read(context_path)
    completion = read(E/'study-completion.json')
    assert scores['checks_passed'] and context['checks_passed']
    assert scores['plan_SHA256'] == context['plan_SHA256'] == sha(E/'plan.v2.json') == PLAN_SHA
    assert decision.get('independent_replay_checks_passed') is True
    assert decision.get('plan', {}).get('sha256') == PLAN_SHA
    assert decision.get('decision') == 'REJECTED_DEV_GATE_AND_CONFIRMATION_RUNTIME_ADMISSION'
    assert decision.get('candidate_accepted') is False and decision.get('champion_promoted') is False
    assert completion['status'] == scores['status'] == 'REJECTED_DEV_GATE'
    assert completion['actual_native_attempts'] == 1 and completion['development_completed'] == 24
    assert not completion['confirmation_consumed_or_attempted'] and not scores['confirmation_consumed']
    assert not scores['DEV_gate_passed'] and not scores['internal_confirmation_gate_passed']
    assert completion['allowed_further_attempts_in_closed_study'] == 0
    assert roles_path.is_file() and analysis_path.is_file()
    analysis = read(analysis_path)
    false_negatives = analysis['six_nda3_high_confidence_false_negatives']['cases']
    assert len(false_negatives) == 6
    assert all(x['family']=='nda-3' and x['gold_threeway']=='Entailment' and
               x['predicted_threeway']=='NotMentioned' for x in false_negatives)
    error_verification_path = S/'audit/epoch15/postrun-error-verification-v1.json'
    assert sha(error_verification_path) == '9df7f1c1a72ebb097df4746706d7a80ff88983caac12275c13f12f416ed73230'
    run = E/'runs/development'
    saved = [json.loads(x) for x in (run/'records.jsonl').read_text().splitlines()]
    row155 = next(x for x in saved if x['id'].endswith(':155:nda-3'))
    assert 'any and all oral and written proprietary information' in row155['response']['diagnostics']['decision']['arms']['ruvector_top2']['premise']
    measured = scores['metrics']['development']
    assert {k:v['correct'] for k,v in measured.items()} == {
        'ruvector_top2':14, 'same_nli_lexical_top2':10,
        'same_nli_positional_first2':13, 'native104_on_ruvector_evidence':12}
    assert all(x['n']==24 and x['errors']==0 for x in measured.values())
    resources = read(run/'resources.json'); phase = read(run/'completion.json')
    cleanup = read(run/'cleanup.json')
    assert phase['exit_code']==0 and phase['wall_seconds_including_model_load']<600
    assert phase['owned_group_cleanup']['live_members_after']==[]
    assert cleanup['native_child_pids_absent'] and not cleanup['cleanup_errors']
    assert resources['allowed_CPU_ids']==[0,1] and resources['configured_ORT_threads']==2
    now = datetime.now(timezone.utc).isoformat()
    used = read(E/'USED_IDENTITIES.pre-native.json')
    used.update(kind='CLOSED_EPOCH15_ACTUAL_IDENTITY_RETIREMENT', native_attempts=1,
                prior_used_manifest='experiments/sota-2026-10-22/epoch14/USED_IDENTITIES.json',
                development_permanently_exposed=True, confirmation_attempts=0,
                confirmation_project_model_unused=True, confirmation_globally_retired=False,
                independent_retirement=ident(roles_path), all_prior_exposures_preserved=True)
    write(E/'USED_IDENTITIES.json', used)
    direction = ('Native vector rankings exactly matched saved-vector cosine on24/24; stop ANN grids. '
                 'The typed reader made no contradiction predictions and missed six oral-information entailments, '
                 'including an explicit oral/written clause retained in its actual premise. '
                 'Prioritize legally grounded typed decisions and confidence reliability with verified nonoverlapping '
                 'licensed train/DEV/confirmation and a feasible CPU runtime; do not train/select on these DEV cases '
                 'or the unused confirmation labels. Definition retention alone did not establish acceptance.')
    ledger = read(S/'epoch14/REJECTION_LEDGER.json')
    ledger['rejections'].append({'epoch':15,'status':'REJECTED_DEV_GATE',
        'candidate':'native RuVector + official DeBERTa-v3-large QUINT8 + shared source-definition priority',
        'DEV_n':24,'DEV_candidate':14,'DEV_same_model_lexical':10,
        'DEV_same_model_positional':13,'DEV_native104_same_excerpt':12,
        'Brier':measured['ruvector_top2']['brier'],'NLL':measured['ruvector_top2']['nll'],
        'reason':'Accuracy gain vs positional is1, below frozen2; Brier/NLL worse than evidence-conditioned104. All paired document accuracy intervals cross0. Runtime confirmation forecast657.8187s also exceeds600s.',
        'confirmation_consumed':False,'source_report':ident(a.independent_decision),
        'scope':'DEV diagnostic only; no full submitted-champion, cross-epoch causal, official benchmark or SOTA claim'})
    ledger['epoch15_budget']={'native_attempts':1,'completed_corpora':1,'HTTP_success':24,
        'HTTP_failed':0,'NLI_pairs':72,'paid_GPU_calls':0,'all_attempts_closed':True,
        'confirmation_attempts':0,'lifetime_native_attempts':17}
    ledger['next_research_priority']=direction
    ledger['used_identity_manifest']='experiments/sota-2026-10-22/epoch15/USED_IDENTITIES.json'
    write(E/'REJECTION_LEDGER.json',ledger)
    cumulative = read(ROOT.parent/'stage-pre-native/CONTINUATION.json')['execution_observed']
    for key in ('native_corpus_batches','native_corpus_batches_completed'): cumulative[key]+=1
    cumulative['native_corpus_attempts_including_failed_request']+=1
    for key in ('actual_HTTP_decisions','actual_HTTP_successful_decisions','actual_HTTP_evaluation_diagnostic_decisions'): cumulative[key]+=24
    manifest={'schema_version':1,'epoch':15,'status':'REJECTED_DEV_GATE','recorded_at':now,
        'resolved_source_commit':'0a6379a108919c9aa5ab52966ce1a9aacab8a0f4',
        'exclusive_lease_commit':'4b8999f776906ecc85e5a91d605be5cd75cb0d4f',
        'frozen_study_commit':'1692519a843102ad1493e35148a10957ac127b4a',
        'plan':ident(E/'plan.v2.json'),'model_qualification':ident(S/'candidate/epoch15/MODEL_QUALIFICATION.json'),
        'model_assets_lock':ident(S/'candidate/epoch15/assets.lock.json'),
        'source_manifest':'experiments/sota-2026-10-22/epoch15/SOURCE_MANIFEST.json',
        'execution':{'native_attempts':1,'completed_corpora':1,'successful_HTTP':24,'failed_HTTP':0,
            'native_core_searches':24,'native104_requests':24,'NLI_pairs':72,'NLI_tokens':34448,
            'BGE_texts':159,'BGE_batches':44,'training_calibration_fits':0,'paid_API_calls':0,'GPU_calls':0,
            'wall_seconds_including_model_initialization_and_cleanup':phase['wall_seconds_including_model_load'],
            'owned_native_process_cleanup_verified':True,'all_further_epoch15_attempts_closed':True},
        'metrics':measured,'typed_metrics':scores['multiclass_metrics']['development'],
        'latency':scores['latency_by_phase_seconds']['development'],'resources':resources,
        'paired_document_uncertainty':scores['paired_doc_bootstrap']['development'],
        'nominal_intervals_not_familywise':True,'independent_score_audit':ident(scores_path),
        'independent_context_audit':ident(context_path),'independent_decision':ident(a.independent_decision),
        'independent_identity_retirement':ident(roles_path),'postrun_error_analysis':ident(analysis_path),
        'independent_postrun_error_verification':ident(error_verification_path),
        'used_identities':ident(E/'USED_IDENTITIES.json'),'rejection_ledger':ident(E/'REJECTION_LEDGER.json'),
        'cumulative_execution':cumulative,'confirmation':{'attempted':False,'model_consumed':False,
            'annotation_choices_used':0,'project_model_unused':True,'globally_retired':False,
            'sha256':'850b1f1d61d81ee83227ff3e62696011a9571b9349cbf926d61243bfacadbf50',
            'runtime_admission':read(E/'runtime-admission.json')},
        'data_roles':{'train':[],'calibration':[],'DEV_groups':8,'DEV_queries':24,
            'originaltrain_exposed_groups':197,'unreserved':210,'reserved_unused_CONFIRMATION':16,
            'all_easy48_Legal96_f018_forever_DEV':True},
        'interpretation':{'full_benchmark_generalization':False,'causal_model_vs_context_effect':False,
            'matched_same_model_retrieval':True,'reliable_retrieval_gain_established':False,
            'numerical_retention_not_arithmetic_truth':True,'unknown_pretraining_fuzzy_overlap':True},
        'official_refresh':ident(S/'legal-transfer/epoch15/benchmark-refresh.json'),
        'publisher_status':ident(S/'legal-transfer/epoch15/publisher-status.json'),
        'acceptance':{'DEV':False,'confirmation':'NOT_ATTEMPTED','champion_promoted':False,
            'champion':'SubmittedNative104/RRF10 preserved','new_submission':False,
            'official_score':None,'official_rank':None,'official_SOTA_verified':False},
        'next_priority':direction,'main_merge_release_packages_changed':False,
        'credentials_private_data_raw_mail_published':False}
    write(E/'EPOCH_MANIFEST.json',manifest)
    lines=['Epoch15 rejected on frozen DEV gates.','',
        '| Reader / evidence | Correct | Binary Brier | Binary NLL |',
        '|---|---:|---:|---:|']
    for k,v in measured.items(): lines.append('| '+k+' | '+str(v['correct'])+'/24 | '+format(v['brier'],'.6f')+' | '+format(v['nll'],'.6f')+' |')
    lines+=['','Typed primary:13/24; no contradiction predictions. All paired8-document accuracy-gain intervals cross zero.',
        'Native rankings matched exact saved-vector cosine in24/24 requests; exact source/token/context replay passed.',
        'Whole all-arm HTTP p50=4.556526s, p95=5.965351s; process119.714843s including initialization/cleanup; CPU[0,1]; peak worker RSS2263527424bytes;0request errors.',
        'Confirmation was not attempted. Frozen runtime forecast657.818735s independently also exceeds600s. No retry or second DEV process.',
        'All new24DEV queries/8documents remain DEV forever; existing48confirmation queries remain model-unused. Train/calibration none; paid/GPU0.',
        '',direction,'',
        'This licensed originalContractNLI diagnostic is not an official JevBench, full LegalBench, or ClaimBench score. SubmittedNative104 is unchanged.',
        'Official JevBench open-weights Capability leader observed Chon-1.0-12B85.336; submission7FEA2738 has no verified result/rank.115 was its original queue position.',
        'Official ClaimBench aggregate observed d1-ultra100.0%, DeciderV1.2 99.694%, four language models100%. No RuVector score or qualified full-dataset pilot.']
    with (E/'RESULTS.md').open('x') as f: f.write(chr(10).join(lines)+chr(10))
    files=[]
    for rel in ['candidate/epoch15','audit/epoch15','legal-transfer/epoch15','controller/epoch15','epoch15']:
        for f in sorted((S/rel).rglob('*')):
            if f.is_file() and '__pycache__' not in f.parts and '/candidate/epoch15/assets/' not in str(f):
                files.append(f)
    write(E/'SOURCE_MANIFEST.json',{'schema_version':1,'epoch':15,'kind':'FINAL_PUBLIC_SOURCE_AND_ACTUAL_EVIDENCE',
        'files':[ident(f) for f in sorted(set(files))], 'excludes':['This manifest','Model assets and caches','Derived checkpoint controls'],
        'frozen_plan':ident(E/'plan.v2.json'),'official_score':None,'official_rank':None})
    print(json.dumps({'manifest':ident(E/'EPOCH_MANIFEST.json'),'source_manifest':ident(E/'SOURCE_MANIFEST.json'),
        'new_actual_corpus':1,'cumulative':cumulative}))

if __name__=='__main__': main()
