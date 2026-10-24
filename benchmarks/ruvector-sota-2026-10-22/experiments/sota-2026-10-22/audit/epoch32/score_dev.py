"""Frozen Epoch32 authored-engineering gate and one closed90-output DEV gold join.

Pure standard library. No model/tokenizer/native execution, fitting, recalibration,
or source evidence-list access. Partial and unknown execution remains unscored.
"""
import argparse,json,math,os
from pathlib import Path
from data_common import require,expected,write_new,SOURCE_SHA,SOURCE_BYTES,NATIVE_ORDER,SOURCE_MAP,CLASSES
from phase_audit import KIND,ROLES,SOURCE,read,ref,checked,source_checks,publisher,phase_integrity,supervisor_closure
from model_audit import audit_model,WEIGHT_SHA,WEIGHT_BYTES
from evidence_audit import audit_evidence
from nli_metrics import reader_check,metrics,diagnostic_gates,paired_differences

ARMS={'actual_native':'native','lexical':'lexical','positional':'positional'}
GOLD_NAMES={'Entailment':'entailment','Contradiction':'contradiction','NotMentioned':'not_mentioned'}

def quantile(values,q):
    a=sorted(values);x=(len(a)-1)*q;lo,hi=math.floor(x),math.ceil(x)
    return a[lo]+(x-lo)*(a[hi]-a[lo])

def pretrained_source(root,plan):
    pin=plan['pretrained_model_source'];value=read(checked(root,pin))
    expected_source={'epoch':32,'kind':KIND,'repository':'sileod/deberta-v3-large-tasksource-nli',
        'revision':'212de447184bda8fb9415a2e5697846864ddf304','weights_file':'model.safetensors',
        'weights_bytes':WEIGHT_BYTES,'weights_sha256':WEIGHT_SHA,'training_lineage_complete':False,
        'native_id2label':{'0':'entailment','1':'neutral','2':'contradiction'},'canonical_E_C_N_to_raw':[0,2,1],
        'confirmation':[],'promotion_allowed':False,'official_eligibility':'HOLD'}
    require(all(value.get(k)==v for k,v in expected_source.items()),'Wrong pretrained head or overstated source/CONF eligibility')
    checked(root,value['metadata_admission'])
    require(value['metadata_admission']['sha256']=='978b7e07c64b28c456a00a11c2ff5c278721f3f270de26be0e12701883b38669',
            'Different model provenance research')
    return {'status':'PASS_FIXED_NEW_PRETRAINED_SOURCE_DIAGNOSTIC_ONLY','pretrained_model_source':pin,
            'training_lineage_complete':False,'confirmation_eligibility':'HOLD'}

def role_outputs(root,corpus,bank,role,plan):
    evidence=audit_evidence(root,corpus,bank,role,plan)
    rows=[];times={name:{'reader':[],'forward':[]}for name in ARMS.values()}
    for case,inp in zip(corpus['cases'],bank['records']):
        readers={}
        for armname,name in ARMS.items():
            arm=case['arms'][armname];r=arm['reader']
            require(r['role']==role,'Reader role differs from actual source corpus')
            readers[name]=reader_check(r,arm['premise'],inp['hypothesis'],arm['joint_pair_tokens'])
            times[name]['reader'].append(r['reader_seconds']);times[name]['forward'].append(r['forward_seconds'])
        rows.append({'id':case['id'],'document_id':case['document_id'],'readers':readers})
    require(sum(len(t['reader'])for t in times.values())==(18 if role=='engineering'else 72),'Missing complete actual role predictions')
    return rows,times,evidence

def timing_summary(times):
    return {k:{'n':len(v['reader']),'reader_p50_seconds':quantile(v['reader'],.5),
            'reader_p95_seconds':quantile(v['reader'],.95),'forward_p50_seconds':quantile(v['forward'],.5),
            'forward_p95_seconds':quantile(v['forward'],.95),
            'scope':'Actual singleton call samples; reader includes pair-tokenization/tensor-preparation/model/readout; forward interval is model invocation, not isolated CPU kernel. Initialization/retrieval/cleanup separate.'}
            for k,v in times.items()}

def engineering_replay(rows,oracle):
    require(oracle['schema_version']==1 and oracle['epoch']==32 and oracle['role']=='engineering','Wrong authored oracle scope')
    labels=oracle['expected_labels'];require(set(labels)=={r['id']for r in rows},'Authored oracle/cases differ')
    require(all(v in GOLD_NAMES for v in labels.values()),'Unknown authored label')
    expected_counts={c:sum(GOLD_NAMES[v]==c for v in labels.values())for c in CLASSES}
    require(expected_counts==dict.fromkeys(CLASSES,2),'Exactly2E2C2N authored engineering cases required')
    for row in rows:row['gold']=GOLD_NAMES[labels[row['id']]]
    scores={name:metrics(rows,name,expected_n=6)for name in ARMS.values()}
    passed=scores['native']['correct']==6
    return passed,scores,{'native_all6_correct':passed,'authored_expected_class_counts':expected_counts,
        'gate_scope':'Only native6/6 is a semantic gate; lexical and positional correctness descriptive. All18 readout/evidence integrity checks remain mandatory.'}

def refusal_closed_integrity(phase):
    """An expected semantic refusal is closed, but never a positive DEV phase."""
    e=phase['execution_value'];a=phase['actual'];dispatch=phase.get('dispatch_attempt_value')
    require(type(e)is dict and e['status']=='WORKER_ENGINEERING_REJECTED' and e['exit_code']==2,
            'Authored engineering refusal is not the exact expected closed exit2')
    require(type(dispatch)is dict and dispatch.get('verified_launcher_start')is True
            and dispatch.get('uncertain_launcher_start')is False,'Authored refusal dispatch not verified')
    require(a.get('verified_worker_starts')==1 and a.get('uncertain_start')is False
            and a.get('owned_live_processes_closed')is True and a.get('operation_counts_complete')is True
            and a.get('errors')==0 and a.get('wall_seconds_including_init_cleanup',601)<=600,
            'Authored refusal captured execution incomplete/unknown/errored')
    require(e.get('source_plan_unchanged')is True and type(e.get('raw_closure_invariants'))is dict
            and bool(e['raw_closure_invariants'])and all(v is True for v in e['raw_closure_invariants'].values()),
            'Authored refusal raw/source closure failed')
    return True

def evaluate(args):
    root=Path(args.project).resolve();planpath=Path(args.plan).resolve()
    plan,source=source_checks(root,planpath);pub=publisher(root,plan);planref=ref(root,planpath)
    phase=pub.phase_evidence(root,'dev',planref)
    report={'schema_version':1,'epoch':32,'kind':KIND,'status':'REJECTED_DEV_DIAGNOSTIC',
        'checks_passed':False,'engineering_passed':False,'diagnostic_qualified':False,'frozen_DEV_gates_passed':False,
        'engineering_metrics':None,'engineering_checks':{},'metrics':None,'paired_differences':None,
        'diagnostic_checks':{},'failed_integrity_checks':[],'failed_engineering_checks':[],'failed_diagnostic_checks':[],
        'engineering_timing':None,'reader_timing':None,'actual_execution':pub.aggregate_actual(phase),'source_checks':source,
        'annotation_choices_attempted':0,'annotation_choices_accessed':0,'other_role_annotation_choices_accessed':0,
        'source_evidence_lists_accessed':0,'original_annotated_source_json_parsed':False,
        'current_TRAIN_choices_or_fits':0,'benchmark_accepted':False,'champion_promoted':False,'new_submission':False,
        'official_rank':None,'official_SOTA_verified':False,'confirmation':[],'calibration':[],
        'evidence':{'raw':phase['raw'],'execution':phase['execution'],'plan':planref,
            'freeze':ref(root,root/plan['source_freeze_path']),'pretrained_model_source':plan['pretrained_model_source'],
            'scorer_source':ref(root,Path(__file__).resolve())},'model_native_tokenizer_calls_by_scorer':0,
        'sampling_scope':'Six authored engineering cases separate; realDEV eight document clusters ×three correlated hypotheses.',
        'uncertainty':['New pretrained model quality remains a hypothesis until this fixedDEV evidence.',
            'Reported600/514/200 task counts and exact training/selection/calibration lineage incomplete; literal ContractNLI absence does not prove exclusion.',
            'Foundation/fuzzy/semantic and record-level supervised overlap unknown; CONF/official eligibility HOLD.',
            'Selected excerpt NotMentioned is not proof of legal absence in the full contract.',
            'Eight document clusters, unknown class imbalance; no24-independent-case or officialSOTA/champion claim.']}
    if phase.get('supervisor_observed_closure')is not None:report['evidence']['supervisor_observed_closure']=phase['supervisor_observed_closure']
    try:
        source_model=pretrained_source(root,plan);report['pretrained_source_audit']=source_model
        require(phase['raw_value']is not None,'Combined worker raw unavailable')
        raw,execution=phase['raw_value'],phase['execution_value']
        full=raw['status']=='COMPLETED_DEV_AWAITING_INDEPENDENT_GOLD_JOIN'
        if full:require(pub.phase_completed(phase),'FullDEV worker not completely captured/closed')
        else:
            require(raw['status']=='ENGINEERING_REJECTED_DEV_NOT_STARTED','Neither completedDEV nor exact authored refusal')
            refusal_closed_integrity(phase)
            require(pub.phase_completed(phase)is False,'Authored refusal cannot be a positiveDEV phase')
        observed=supervisor_closure(root,phase)
        integrity=phase_integrity(root,raw,execution,plan,'dev',full)
        model=audit_model(raw)
        engineering_bank=read(root/plan['engineering_inputs_path'],plan['engineering_inputs_sha256'])
        oracle=read(root/plan['engineering_oracle_path'],plan['engineering_oracle_sha256'])
        eng_rows,eng_times,eng_evidence=role_outputs(root,raw['corpora']['engineering'],engineering_bank,'engineering',plan)
        engineering,eng_scores,eng_checks=engineering_replay(eng_rows,oracle)
        report.update(engineering_passed=engineering,engineering_metrics=eng_scores,engineering_checks=eng_checks,
            engineering_timing=timing_summary(eng_times),pretrained_model_audit=model,phase_integrity=integrity,
            supervisor_physical_closure=observed,engineering_context_audit=eng_evidence)
        gate=raw['engineering_gate']
        require(gate['passed']is engineering and gate['native_correct']==eng_scores['native']['correct'] and gate['n']==6,
                'Worker/frozen independent engineering semantic gate differs')
        require(gate['correct_by_arm']=={arm:eng_scores[name]['correct']for arm,name in ARMS.items()}
                and gate['by_class']=={label:eng_scores['native']['by_class'][gold]for label,gold in GOLD_NAMES.items()},
                'Authored engineering summary class/arm counts differ')
        require(gate['all18_predictions_completed_before_oracle_read']is True
                and gate['all18_finite_true_pair_source_numeric_integrity']is True
                and gate['DEV_bank_read_before_gate']is False and gate['benchmark_generalization_claim']is False
                and gate['oracle']==ref(root,root/plan['engineering_oracle_path']),
                'Authored engineering gate provenance differs')
        require(raw['corpus_reservations']==phase['corpus_reservations']
                and all(receipt is None or receipt['corpus_reservation']==phase['corpus_reservations'][role]
                        for role,receipt in raw['corpora'].items()),'Actual corpus reservation/ref provenance differs')
        require(full is engineering,'Engineering refusal/conditional DEV execution differs')
        if not engineering:
            require(raw['corpora']['dev']is None and raw['counters']['DEV_input_bank_reads']==0
                    and raw['counters']['DEV_forward_calls_completed']==0,'DEV consumed after authored engineering refusal')
            require(raw['counters']['NLI_forward_calls_completed']==18,'Complete18 authored predictions required for honest refusal')
            require(raw['counters']['native_insertions_completed']==eng_evidence['source_index_vectors']
                    and raw['counters']['native_hit_source_validations']==eng_evidence['native_hits_verified'],'Engineering native count closure differs')
            report.update(checks_passed=True,status='ENGINEERING_REJECTED_DEV_NOT_STARTED',
                failed_engineering_checks=['native_all6_correct'],DEV_semantic_bank_reads_by_scorer=0)
            write_new(args.output,report);return report
        # The current realDEV bank is semantically parsed only after engineering passes.
        bank=read(root/plan['dev_inputs_path'],plan['dev_inputs_sha256'])
        prepared,times,contexts=role_outputs(root,raw['corpora']['dev'],bank,'dev',plan)
        require(raw['counters']['NLI_forward_calls_completed']==90 and raw['counters']['ENGINEERING_forward_calls_completed']==18
                and raw['counters']['DEV_forward_calls_completed']==72,'Complete90genuine outputs required before any originalDEV choice')
        require(raw['counters']['native_insertions_completed']==eng_evidence['source_index_vectors']+contexts['source_index_vectors']
                and raw['counters']['native_hit_source_validations']==eng_evidence['native_hits_verified']+contexts['native_hits_verified'],
                'Actual role/native vector-hit count closure differs')
        # All90 output, source, numerical and actual physical-closure checks precede original annotated source parse.
        source_doc=read(Path(args.source),SOURCE_SHA)
        report['original_annotated_source_json_parsed']=True
        require(Path(args.source).stat().st_size==SOURCE_BYTES,'Original source byte size changed')
        docs={d['id']:d for d in source_doc['documents']}
        for inp in bank['records']:
            require(docs[inp['document_id']]['text']==inp['document']
                    and source_doc['labels'][inp['hypothesis_id']]['hypothesis']==inp['hypothesis']
                    and len(docs[inp['document_id']]['annotation_sets'])==1,'OriginalDEV source identity differs')
        here=root/'experiments/sota-2026-10-22/audit/epoch32';reservation=here/'DEV_GOLD_JOIN_RESERVATION.json'
        write_new(reservation,{'epoch':32,'kind':KIND,'DEVcases':[r[0]for r in expected('dev')],
            'raw':phase['raw'],'execution':phase['execution'],'engineering_passed':True,'complete_predictions':90,
            'owned_group_closed':True,'choices_accessed_before_reservation':0,'no_retry_after_any_choice_access':True})
        access=here/'DEV_GOLD_ACCESS.jsonl'
        with access.open('x',encoding='utf-8')as log:
            for i,(row,inp)in enumerate(zip(prepared,bank['records']),1):
                log.write(json.dumps({'attempt':i,'id':inp['id']})+'\n');log.flush();os.fsync(log.fileno())
                report['annotation_choices_attempted']=i
                choice=docs[inp['document_id']]['annotation_sets'][0]['annotations'][inp['hypothesis_id']]['choice']
                report['annotation_choices_accessed']=i
                require(type(choice)is str and choice in SOURCE_MAP,'Unknown originalDEV choice')
                row['gold']=NATIVE_ORDER[SOURCE_MAP[choice]]
        scores={name:metrics(prepared,name)for name in ARMS.values()};gates=diagnostic_gates(scores)
        report.update(checks_passed=True,diagnostic_qualified=all(gates.values()),frozen_DEV_gates_passed=all(gates.values()),
            metrics=scores,paired_differences=paired_differences(scores),diagnostic_checks=gates,
            failed_diagnostic_checks=[k for k,v in gates.items()if not v],context_audit=contexts,
            reader_timing=timing_summary(times),DEV_semantic_bank_reads_by_scorer=1)
        report['status']='DEV_DIAGNOSTIC_QUALIFIED'if report['diagnostic_qualified']else'REJECTED_DEV_DIAGNOSTIC'
        report['evidence']['gold_reservation']=ref(root,reservation);report['evidence']['gold_access_log']=ref(root,access)
    except (ValueError,KeyError,TypeError,IndexError,ZeroDivisionError,OSError)as error:
        report['failed_integrity_checks']=[{'type':type(error).__name__,'message':str(error)}]
    write_new(args.output,report);return report

def bind(args):
    root=Path(args.project).resolve();replay=read(Path(args.replay));results=read(Path(args.results))
    require(replay['epoch']==results['epoch']==32 and replay['kind']==results['kind']==KIND,'Wrong finaldiagnostic scope')
    planpath=checked(root,replay['evidence']['plan']);plan,_=source_checks(root,planpath)
    pub=publisher(root,plan);phase=pub.phase_evidence(root,'dev',replay['evidence']['plan'])
    require(pub.aggregate_actual(phase)==replay['actual_execution']==results['actual_execution'],'Final actualreceipt projection differs')
    for pin in replay['evidence'].values():
        if pin is not None:checked(root,pin)
    # The reviewed result builder copies every original evaluation field unchanged.
    for key,value in replay.items():require(results.get(key)==value,'Canonical RESULTS differs from frozen evaluation: '+key)
    require(all(results[k]is False for k in ['benchmark_accepted','champion_promoted','new_submission','official_SOTA_verified'])
            and results['official_rank']is None,'Forbidden benchmark/promotion/rank claim')
    report=json.loads(json.dumps(replay));report['evaluated_integrity_checks_passed']=replay['checks_passed']
    report['publication_binding_checks_passed']=True;report['checks_passed']=True
    report['evidence']['results']=ref(root,Path(args.results));report['evidence']['qualification_replay']=ref(root,Path(args.replay))
    write_new(args.output,report);return report

if __name__=='__main__':
    p=argparse.ArgumentParser();sub=p.add_subparsers(dest='mode',required=True)
    ev=sub.add_parser('evaluate')
    for n in ['project','plan','source','output']:ev.add_argument('--'+n,required=True)
    binding=sub.add_parser('bind')
    for n in ['project','replay','results','output']:binding.add_argument('--'+n,required=True)
    a=p.parse_args();report=evaluate(a)if a.mode=='evaluate'else bind(a)
    print(json.dumps({'status':report['status'],'engineering_passed':report['engineering_passed'],
        'diagnostic_qualified':report['diagnostic_qualified'],'checks_passed':report['checks_passed']}))
