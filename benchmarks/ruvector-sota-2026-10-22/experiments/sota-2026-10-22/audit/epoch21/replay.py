"""Independent epoch21 source and acceptance replay; no model/tokenizer/native imports."""
from common import *
from model_checks import model_replay, assets_replay, forward_replay
from trace_checks import *

def plan_replay(plan_path):
    p = read(plan_path); protocol = read(PROTOCOL)
    demand(p.get('schema_version') == 1 and p.get('epoch') == 21 and p.get('source_checkpoint') == SOURCE,
           'exact epoch21 source plan required')
    demand(p.get('study_id') == 'native-deberta-v3-fp32-typed-e21' and p.get('actual_project') == str(ROOT), 'exact isolated study required')
    demand(p.get('train') == [] and p.get('calibration') == [], 'explicit empty train/calibration required')
    limits = {'threads': 2, 'interop_threads': 1, 'seconds_per_batch': 600, 'worker_attempts': 2,
              'native_batches': 2, 'candidate_configs': 1, 'paid_calls': 0, 'GPU_calls': 0}
    for k, value in limits.items(): demand(type(p['limits'].get(k)) is int and p['limits'][k] == value, 'frozen limit changed: ' + k)
    pins = p['pins']; demand(type(pins) is list and bool(pins), 'source pins required')
    by_path = {r['path']: r for r in pins}; demand(len(by_path) == len(pins), 'duplicate source pins')
    for row in pins:
        path = member(row['path']); actual = identity(path, row['path'])
        demand(actual['sha256'] == row['sha256'] and ('bytes' not in row or actual['bytes'] == row['bytes']), 'source pin changed: ' + row['path'])
    for path in HERE.glob('*.py'):
        rel = str(path.relative_to(ROOT)); demand(rel in by_path, 'independent checker source unpinned: ' + rel)
    rel = str(PROTOCOL.relative_to(ROOT)); demand(by_path.get(rel, {}).get('sha256') == identity(PROTOCOL)['sha256'], 'independent protocol unpinned')
    demand(p['audit_protocol_path'] == rel and p['audit_protocol_sha256'] == identity(PROTOCOL)['sha256'],
           'plan must explicitly bind the exact active typed DeBERTa source protocol')
    lock = protocol['model']['asset_lock']; demand(by_path.get(lock['path'], {}).get('sha256') == lock['sha256'], 'independent model lock changed')
    demand(identity(member(lock['path']))['sha256'] == lock['sha256'], 'actual independent model lock changed')
    header = protocol['model']['source_header']
    demand(by_path.get(header['path']) == header and identity(member(header['path']),header['path']) == header
           and p['model_header_path'] == header['path'] and p['model_header_sha256'] == header['sha256'],
           'plan must bind the exact independently frozen complete original source-header proof')
    demand(protocol['source_head'] == SOURCE and protocol['model']['repository'] == MODEL
           and protocol['model']['revision'] == REVISION, 'independent scientific contract changed')
    return p, protocol


def latency(values,scope):
    return {'n':len(values),'p50_seconds':M.percentile(values,.5),'p95_seconds':M.percentile(values,.95),'max_seconds':max(values),'scope':scope}


def runtime_replay(raw,plan,mechanical):
    capacity=raw['confirmation_capacity']; expected=read(PROTOCOL)['data']['CONF_document_ids']
    demand(capacity['scope']=='INPUT_ONLY_TOKENIZATION_CAPACITY'and capacity['source_path']==plan['confirmation_capacity_inputs_path']
           and capacity['source_sha256']==plan['confirmation_capacity_inputs_sha256'],'actual input-only confirmation capacity bank changed')
    path=member(capacity['source_path']);demand(identity(path)['sha256']==capacity['source_sha256'],'input-only capacity source bytes changed')
    rows=capacity['document_units'];demand(type(rows)is list and[r['document_id']for r in rows]==expected
        and all(type(r['document_id'])is int and type(r['units'])is int and 1<=r['units']<=192 for r in rows),'exact8 current-tokenizer confirmation unit counts required')
    demand(type(capacity['max_units'])is int and capacity['max_units']==max(r['units']for r in rows),'capacity maximum source units mismatch')
    demand(integer(capacity['model_forwards'])==0 and integer(capacity['annotation_choices_accessed'])==0
           and integer(capacity['confirmation_NLI_predictions'])==0 and capacity['text_previously_published']is True
           and capacity['training_selection_on_confirmation_labels']is False,'capacity scan may only tokenize already-published inputs')
    bank=read(path);allow=read(member(plan['phases']['confirmation']['input_allowlist_path']))
    demand(bank['role']=='confirmation'and len(bank['records'])==len(allow['records'])==24,'exact24 input-only capacity records required')
    expected_hashes={r['input_sha256']for r in allow['records']};actual_hashes=set()
    for row in bank['records']:
        demand(set(row)=={'id','input','input_sha256'}and type(row['id'])is str
               and row['input_sha256']==digest(canonical(row['input'])),'capacity bank must contain only exact source inputs, no choices')
        actual_hashes.add(row['input_sha256'])
    demand(len(actual_hashes)==24 and actual_hashes==expected_hashes,'capacity scan used a different reserved input identity')
    initialization=duration(raw['whole_pipeline_initialization_seconds'])
    demand(initialization>=duration(raw['initialization_elapsed_seconds']),'whole initialization cannot omit reader setup')
    max_document_third=max(mechanical['document_elapsed_seconds'])/3
    dev_units=integer(mechanical['max_source_units'],1);conf_units=capacity['max_units']
    ratio=max(1,conf_units/dev_units)
    forecast=24*max_document_third*ratio+2*initialization+60
    return {'formula_id':'24xDEVmaxDocumentThirdxmax1UnitRatio+2xWholeInit+60-v1',
            'max_DEV_document_seconds_divided_by3':max_document_third,'max_DEV_source_units':dev_units,
            'max_CONFIRMATION_source_units':conf_units,'source_unit_ratio':ratio,
            'whole_pipeline_initialization_seconds':initialization,'projected_confirmation_seconds':forecast,
            'limit_seconds':600,'allowed':forecast<=600,'capacity_receipt':capacity,
            'scope':'Conservative complete-document amortized forecast; no confirmation labels/predictions used and no guarantee of future completion.'}


def replay(plan_path,raw_path,execution_path,gold_path=None):
    plan,protocol=plan_replay(plan_path);raw=read(raw_path);execution=read(execution_path);phase=raw['phase']
    demand(phase in ('dev','confirmation')and raw['schema_version']==1 and raw['epoch']==21 and raw['plan_sha256']==identity(plan_path)['sha256'],'raw scientific/source identity mismatch')
    demand(raw['errors']==[],'actual worker errors prevent acceptance')
    state,instance=model_replay(raw,protocol);assets=assets_replay(raw,plan);engineering=engineering_replay(raw,protocol,state,instance)
    complete=raw['status']=='COMPLETED_CORPUS_AWAITING_INDEPENDENT_SCORE'
    if complete:demand(engineering['passed'],'legal corpus followed failed engineering readiness')
    else:
        demand(raw['status']=='REJECTED_ENGINEERING_QUALIFICATION_NO_LEGAL_INPUTS'and not engineering['passed']and raw['documents']==[],'only completed corpus or valid prelegal engineering rejection can be scored')
        demand(gold_path is None,'engineering failure must not project or join any legal labels')
    resources=resources_replay(raw,execution,raw_path,phase,complete);counters_replay(raw,complete)
    token_proof=tokenizer_report_replay(raw,raw_path,identity(plan_path)['sha256'],execution_path)
    report={'schema_version':1,'epoch':21,'phase':phase,'at':datetime.now(timezone.utc).isoformat(),'checks_passed':True,
            'engineering_qualified':engineering['passed'],'accepted_for_confirmation':False,'DEV_gate_passed':None,'CONF_gate_passed':None,
            'accepted':False,'runtime_gate_passed':False,'plan_sha256':identity(plan_path)['sha256'],
            'raw_receipt':identity(raw_path,str(Path(raw_path).relative_to(ROOT))),
            'execution_receipt':identity(execution_path,str(Path(execution_path).relative_to(ROOT))),
            'engineering':engineering,'model_state_sha256':state,'tokenizer_backend_sha256':raw['tokenizer']['backend_sha256'],
            'asset_runtime_replay':assets,
            'independent_tokenizer_feed_replay':token_proof,
            'actual_counters':raw['counters'],'actual_resources':resources,'champion_promoted':False,'submission_allowed':False,
            'official_score':None,'official_rank':None,'official_SOTA_goal_verified':False,'used_confirmation_identities':[]}
    if not complete:
        for relative in (PREFIX+'legal-transfer/epoch21/inputs.'+phase+'.json',
                         PREFIX+'legal-transfer/epoch21/role-reservation.'+phase+'.json',
                         PREFIX+'legal-transfer/epoch21/inputs.'+phase+'.allowlist.json',
                         PREFIX+'audit/epoch21/gold.'+phase+'.json'):
            demand(not(ROOT/relative).exists(),'engineering failure has unexpected legal input/choice projection')
        report['status']='REJECTED_ENGINEERING_QUALIFICATION_NO_LEGAL_INPUTS';report['metrics']=None
        report['all_remaining_epoch21_slots_must_close']=True;return report
    demand(gold_path is not None,'complete sealed corpus needs independent postprediction gold projection')
    gold=read(gold_path);demand(gold['phase']==phase and gold['raw_receipt_sha256']==report['raw_receipt']['sha256'],'postprediction gold projection is stale/different phase')
    demand(gold['status']=='FIXED_ROLE_GOLD_PROJECTED_AFTER_COMPLETE_SEALED_PREDICTIONS_AND_CLEANUP'
           and gold['plan_sha256'] == raw['plan_sha256'] and integer(gold['annotation_choices_accessed']) == 24
           and integer(gold['other_role_annotation_choices_accessed']) == 0 and integer(gold['old_reserved48_choices_accessed']) == 0
           and gold['labels_used_for_model_fit_calibration_selection'] is False and integer(gold['model_native_paid_GPU_calls']) == 0,
           'exact role-specific postprediction-only gold provenance required')
    rows,mechanical=corpus_replay(raw,protocol,state,instance,gold['records'])
    result=M.gate(rows,phase=='confirmation');report['metrics']=result
    report['mechanical_replays']=mechanical
    report['latency']={'direct_pair':latency(mechanical['direct_pair_seconds'],'72corpus matched-arm direct pair forwards; no engineering cases.'),
                       'direct_all_arm_request':latency(mechanical['direct_all_arm_request_seconds'],'Three matched NLIarms perquestion; document preparation is reported separately.'),
                       'document_amortized':latency([x/3 for x in mechanical['document_elapsed_seconds']],'Complete source partition/embedding/native and3questionsx3NLIarms perdocument, dividedby3; amortized full-document unit, not serving latency.')}
    report['gold_receipt']=identity(gold_path,str(Path(gold_path).relative_to(ROOT)))
    if phase=='dev':
        forecast=runtime_replay(raw,plan,mechanical);report['runtime_forecast']=forecast
        report['DEV_gate_passed']=result['passed'];report['runtime_gate_passed']=forecast['allowed']
        report['accepted_for_confirmation']=result['passed']and forecast['allowed']
        report['status']=('DEV_ACCEPTED_FOR_CONDITIONAL_CONFIRMATION'if report['accepted_for_confirmation']else
                          'REJECTED_DEV_GATE'if not result['passed']else'BLOCKED_CONFIRMATION_RUNTIME_FORECAST')
        report['all_remaining_epoch21_slots_must_close']=not report['accepted_for_confirmation']
    else:
        report['CONF_gate_passed']=result['passed'];report['accepted']=result['passed'];report['status']='LOCAL_MATCHED_RETRIEVAL_RESEARCH_ACCEPTED_ONLY'if result['passed']else'REJECTED_CONFIRMATION_GATE'
        report['used_confirmation_identities']=[r['question_id']for r in rows];report['all_remaining_epoch21_slots_must_close']=True
    return report


def write_new(path,value):
    p=Path(path);demand(not any(x.is_symlink()for x in[p,*p.parents]),'nonsymlink output required')
    with p.open('x')as f:json.dump(M.json_safe(value),f,ensure_ascii=False,sort_keys=True,indent=2,allow_nan=False);f.write('\n');f.flush();os.fsync(f.fileno())


def main():
    ap=argparse.ArgumentParser()
    for key in ('plan','raw','execution','out'):ap.add_argument('--'+key,type=Path,required=True)
    ap.add_argument('--gold',type=Path)
    args=ap.parse_args()
    try:
        report=replay(args.plan,args.raw,args.execution,args.gold)
    except (M.InvalidReceipt,KeyError,TypeError,ValueError,OSError)as exc:
        report={'schema_version':1,'epoch':21,'at':datetime.now(timezone.utc).isoformat(),
                'status':'INCONCLUSIVE_INVALID_OR_INCOMPLETE_EXECUTION','checks_passed':False,
                'engineering_qualified':None,'accepted_for_confirmation':False,'accepted':False,
                'champion_promoted':False,'submission_allowed':False,'official_score':None,'official_rank':None,
                'failures':[{'type':type(exc).__name__,'message':str(exc)}],
                'model_native_calls_by_checker':0,'all_remaining_epoch21_slots_must_close':True,
                'scope':'Retain actual partial/invalid evidence and uncertainty; do not fabricate missing scores/counters or retry.'}
        for label,path in(('plan',args.plan),('raw',args.raw),('execution',args.execution)):
            try:report[label+'_receipt']=identity(path,str(path.relative_to(ROOT)))
            except (OSError,ValueError):report[label+'_receipt']=None
        try:
            actual=read(args.raw);report['phase']=actual.get('phase');report['actual_counters_unverified']=actual.get('counters');report['actual_worker_errors_unverified']=actual.get('errors')
        except (OSError,ValueError):report['phase']=None
    write_new(args.out,report)
    print(json.dumps({k:report[k]for k in('status','checks_passed','engineering_qualified','accepted_for_confirmation','accepted')}))



if __name__ == "__main__": main()
