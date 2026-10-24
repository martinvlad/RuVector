"""Epoch31 fixed archived-state DEV replay and one closed-output gold join.

Standard library only. Archived TRAIN provenance is historical; current TRAIN,
calibration and confirmation are empty. No model invocation or fitting occurs.
"""
import argparse
import json
import os
from pathlib import Path
from data_common import require,expected,write_new,SOURCE_SHA,SOURCE_BYTES,NATIVE_ORDER,SOURCE_MAP
from phase_audit import KIND,ROLES,SOURCE,read,ref,checked,source_checks,publisher,phase_integrity,supervisor_closure
from artifact_audit import audit_artifact,canonical_sha,HISTORICAL_TRAIN_IDS
from evidence_audit import audit_evidence
from nli_metrics import reader_check,metrics,diagnostic_gates

ARTIFACT_SHA='46bcb1c9bcf7a6bd9f7491f1233f38b65b1c3672de5370f4d1e1b5db24ae796f'
ORIGINAL_SOURCE_PLAN_SHA='d6c46944bbac2cb8ef65a51e68d927e10b869123004f941d56292cef1e0bd94b'
HISTORICAL_INPUTS_SHA='bf1eff95845e301b56abd1a5284df0dcbbf531b952ea4dd1d89351fef845570a'

def quantile(values,q):
    import math
    a=sorted(values);x=(len(a)-1)*q;lo,hi=math.floor(x),math.ceil(x)
    return a[lo]+(x-lo)*(a[hi]-a[lo])

def archived_lineage(root,plan):
    sealpath=checked(root,plan['archived_model_seal'])
    require(str(sealpath.relative_to(root))==plan['archived_model_seal_path']
            and plan['archived_model_seal']['sha256']==plan['archived_model_seal_sha256'],'Archived seal plan reference differs')
    seal=read(sealpath)
    require(seal['schema_version']==1 and seal['epoch']==31 and seal['kind']==KIND
            and seal['status']=='ARCHIVED_TRAINED_PARAMETER_ARTIFACT_SEALED'
            and seal['source_checkpoint']==SOURCE and seal['data_roles']==ROLES
            and seal['hypotheses']==['nda-17','nda-7','nda-3'],'Wrong current archived-model admission scope')
    require(seal['historical_training_epoch']==30
            and seal['historical_training_document_ids']==HISTORICAL_TRAIN_IDS,'Archived supervision lineage changed')
    for key in ['parameter_artifact','train_raw','train_execution','independent_training_report',
                'original_source_plan','original_source_freeze']:checked(root,seal[key])
    require(seal['parameter_artifact']['bytes']==5950520 and seal['parameter_artifact']['sha256']==ARTIFACT_SHA
            and seal['original_source_plan']['sha256']==ORIGINAL_SOURCE_PLAN_SHA,'Fixed archived model/source changed')
    training=read(checked(root,seal['independent_training_report']))
    require(training['epoch']==30 and training['train_integrity_passed']is True
            and training['checks_passed']is True and training['failures']==[],'Archived TRAIN integrity not accepted')
    for old,new in {'artifact':'parameter_artifact','raw':'train_raw','execution':'train_execution',
                    'plan':'original_source_plan','freeze':'original_source_freeze'}.items():
        require(training['evidence'][old]==seal[new],'Archived report/seal lineage differs: '+old)
    execution=read(checked(root,seal['train_execution']))
    require(execution['epoch']==30 and execution['phase']=='train'and execution['status']=='WORKER_COMPLETED'
            and execution['worker_attempts_reserved']==execution['verified_worker_starts']==1
            and execution['uncertain_start']is False and execution['owned_live_processes_closed']is True
            and execution['owned_live_group_members']==[],'Historical TRAIN was not completely closed')
    require(execution['raw_sha256']==seal['train_raw']['sha256'] and execution['raw_bytes']==seal['train_raw']['bytes']
            and execution['raw_operation_counters']['training_steps']==24,'Archived TRAIN count/raw seal changed')
    artifactpath=checked(root,seal['parameter_artifact'])
    artifact=audit_artifact(artifactpath,ORIGINAL_SOURCE_PLAN_SHA,HISTORICAL_INPUTS_SHA)
    return seal,read(artifactpath),artifact

def evaluate(args):
    root=Path(args.project).resolve();planpath=Path(args.plan).resolve()
    plan,source=source_checks(root,planpath);pub=publisher(root,plan);planref=ref(root,planpath)
    dev=pub.phase_evidence(root,'dev',planref)
    report={'schema_version':1,'epoch':31,'kind':KIND,'status':'REJECTED_DEV_DIAGNOSTIC',
        'checks_passed':False,'diagnostic_qualified':False,'frozen_DEV_gates_passed':False,
        'archived_training_integrity_passed':False,'metrics':None,'paired_differences':None,
        'diagnostic_checks':{},'failed_integrity_checks':[],'failed_diagnostic_checks':[],
        'reader_timing':None,'actual_execution':pub.aggregate_actual(dev),'source_checks':source,
        'annotation_choices_attempted':0,'annotation_choices_accessed':0,
        'other_role_annotation_choices_accessed':0,'source_evidence_lists_accessed':0,
        'original_annotated_source_json_parsed':False,'current_TRAIN_choices_or_fits':0,
        'benchmark_accepted':False,'champion_promoted':False,'new_submission':False,
        'official_rank':None,'official_SOTA_verified':False,'confirmation':[],'calibration':[],
        'evidence':{'raw':dev['raw'],'execution':dev['execution'],'plan':planref,
                    'freeze':ref(root,root/plan['source_freeze_path']),
                    'archived_model_seal':plan['archived_model_seal'],
                    'scorer_source':ref(root,Path(__file__).resolve())},
        'model_native_tokenizer_calls_by_scorer':0,
        'sampling_scope':'8newDEVdocuments,3correlatedhypotheses each; first fixed archived-state diagnostic only',
        'uncertainty':['Same original2020backbone; no new pretrained model or quality claim before DEV evidence',
                       'Foundation/fuzzy overlap and laterpublisherreselection unknown',
                       'Retrievedexcerpt NotMentioned is not proof of global legalabsence',
                       'NetLoRA+classifier effect; no exclusiveLoRAcausal or officialbenchmark inference']}
    if dev.get('supervisor_observed_closure')is not None:
        report['evidence']['supervisor_observed_closure']=dev['supervisor_observed_closure']
    try:
        seal,value,artifact=archived_lineage(root,plan)
        report['archived_training_integrity_passed']=True
        report['evidence']['parameter_artifact']=seal['parameter_artifact']
        report['archived_model_audit']=artifact
        require(dev['raw_value']is not None and pub.phase_completed(dev),'DEV not fully completed/closed')
        observed_closure=supervisor_closure(root,dev)
        raw,execution=dev['raw_value'],dev['execution_value']
        phase=phase_integrity(root,raw,execution,plan,'dev')
        require(raw['admission']['archived_model_seal']==plan['archived_model_seal']
                and raw['admission']['parameter_artifact']==seal['parameter_artifact'],'Actual archived SOURCE admission differs')
        require(raw['loaded_parameter_artifact']['sha256']==seal['parameter_artifact']['sha256']
                and raw['loaded_parameter_artifact']['bytes']==seal['parameter_artifact']['bytes'],
                'DEV did not load exact archived parameter bytes')
        require(raw['adapted_state_load']['original_baseline_outputs_completed_before_load']==24,
                'Learned tensors decoded before fresh original24 baseline')
        require(raw['model_initialization']['original_head_manifest']==value['original_head_manifest'],
                'Fresh original DEV classifier differs from original historical TRAIN classifier')
        bank=read(root/plan['dev_inputs_path'],plan['dev_inputs_sha256'])
        contexts=audit_evidence(root,raw,bank,'dev',plan)
        headsha=canonical_sha(value['original_head_manifest'])
        learnedmanifest=[{k:t[k]for k in ['name','shape','dtype','numel','bytes','sha256']}for t in value['tensors']]
        learnedsha=canonical_sha(learnedmanifest);prepared=[]
        times={k:[]for k in ['original_native','adapted_native','adapted_lexical','adapted_positional']}
        for case,inp in zip(raw['cases'],bank['records']):
            readers={}
            for armname in ['actual_native','lexical','positional']:
                arm=case['arms'][armname]
                require((arm['reader']['original']is not None)==(armname=='actual_native'),'Only native original comparator allowed')
                for state in (['original','adapted']if armname=='actual_native'else['adapted']):
                    name=('original_native'if state=='original'else'adapted_native'if armname=='actual_native'else'adapted_'+armname)
                    r=arm['reader'][state]
                    readers[name]=reader_check(r,arm['premise'],inp['hypothesis'],arm['joint_pair_tokens'],state,
                        seal['parameter_artifact']['sha256'],headsha,learnedsha)
                    times[name].append(r['latency_seconds'])
                if armname=='actual_native':
                    original,adapted=arm['reader']['original'],arm['reader']['adapted']
                    require(all(original[k]==adapted[k]for k in ['native_pair_input_ids_sha256','premise_sha256','hypothesis_sha256','pair_tokens']),
                            'Original/adapted native pair is not byte/token identical')
            prepared.append({'id':case['id'],'document_id':case['document_id'],'readers':readers})
        require(sum(map(len,times.values()))==96 and raw['counters']['NLI_forward_calls_completed']==96
                and raw['counters']['original_DEV_forward_calls_completed']==24
                and raw['counters']['adapted_DEV_forward_calls_completed']==72,'Complete96genuine paired outputs required')
        # Every above check, including physical closure, precedes annotated source access.
        source_doc=read(Path(args.source),SOURCE_SHA)
        report['original_annotated_source_json_parsed']=True
        require(Path(args.source).stat().st_size==SOURCE_BYTES,'Original source byte size changed')
        docs={d['id']:d for d in source_doc['documents']}
        for inp in bank['records']:
            require(docs[inp['document_id']]['text']==inp['document']
                    and source_doc['labels'][inp['hypothesis_id']]['hypothesis']==inp['hypothesis']
                    and len(docs[inp['document_id']]['annotation_sets'])==1,'Original DEV source authenticity failed')
        here=root/'experiments/sota-2026-10-22/audit/epoch31'
        reservation=here/'DEV_GOLD_JOIN_RESERVATION.json'
        write_new(reservation,{'epoch':31,'kind':KIND,'DEVcases':[r[0]for r in expected('dev')],
            'raw':dev['raw'],'execution':dev['execution'],'complete_predictions':96,'owned_group_closed':True,
            'choices_accessed_before_reservation':0,'no_retry_after_any_choice_access':True})
        access=here/'DEV_GOLD_ACCESS.jsonl'
        with access.open('x',encoding='utf-8')as log:
            for i,(row,inp)in enumerate(zip(prepared,bank['records']),1):
                log.write(json.dumps({'attempt':i,'id':inp['id']})+'\n');log.flush();os.fsync(log.fileno())
                report['annotation_choices_attempted']=i
                choice=docs[inp['document_id']]['annotation_sets'][0]['annotations'][inp['hypothesis_id']]['choice']
                report['annotation_choices_accessed']=i
                require(type(choice)is str and choice in SOURCE_MAP,'Unknown original DEV choice')
                row['gold']=NATIVE_ORDER[SOURCE_MAP[choice]]
        result={name:metrics(prepared,name)for name in times};gates=diagnostic_gates(result)
        paired={name:{'adapted_native_minus_correct':result['adapted_native']['correct']-r['correct'],
                     'other_minus_Brier':r['Brier']-result['adapted_native']['Brier'],
                     'other_minus_NLL':r['NLL_clipped_1e-12']-result['adapted_native']['NLL_clipped_1e-12']}
                for name,r in result.items()if name!='adapted_native'}
        report.update(checks_passed=True,diagnostic_qualified=all(gates.values()),frozen_DEV_gates_passed=all(gates.values()),
            metrics=result,paired_differences=paired,diagnostic_checks=gates,
            failed_diagnostic_checks=[k for k,v in gates.items()if not v],context_audit=contexts,phase_integrity=phase,
            supervisor_physical_closure=observed_closure,
            reader_timing={k:{'n':len(v),'p50_seconds':quantile(v,.5),'p95_seconds':quantile(v,.95),
                'scope':'Pairtokenization/tensorprep/fullmodel/softmax; state verification/init/retrieval separate'}for k,v in times.items()})
        report['status']='DEV_DIAGNOSTIC_QUALIFIED'if report['diagnostic_qualified']else'REJECTED_DEV_DIAGNOSTIC'
        report['evidence']['gold_reservation']=ref(root,reservation);report['evidence']['gold_access_log']=ref(root,access)
    except (ValueError,KeyError,TypeError,IndexError,ZeroDivisionError,OSError)as error:
        report['failed_integrity_checks']=[{'type':type(error).__name__,'message':str(error)}]
    write_new(args.output,report);return report

def bind(args):
    root=Path(args.project).resolve();replay=read(Path(args.replay));results=read(Path(args.results))
    require(replay['epoch']==results['epoch']==31 and replay['kind']==results['kind']==KIND,'Wrong final diagnostic scope')
    planpath=checked(root,replay['evidence']['plan']);plan,_=source_checks(root,planpath)
    pub=publisher(root,plan);dev=pub.phase_evidence(root,'dev',replay['evidence']['plan'])
    require(pub.aggregate_actual(dev)==replay['actual_execution']==results['actual_execution'],'Final current actual projection differs')
    for pin in replay['evidence'].values():
        if pin is not None and not Path(pin['path']).is_absolute():checked(root,pin)
    for key in ['status','diagnostic_qualified','frozen_DEV_gates_passed','archived_training_integrity_passed',
                'metrics','paired_differences','diagnostic_checks','failed_integrity_checks','failed_diagnostic_checks','reader_timing']:
        require(results.get(key)==replay.get(key),'Canonical RESULTS differs from original evaluation: '+key)
    require(all(results[k]is False for k in ['benchmark_accepted','champion_promoted','new_submission','official_SOTA_verified'])
            and results['official_rank']is None,'Forbidden benchmark/promotion/rank claim')
    report=json.loads(json.dumps(replay));report['evaluated_integrity_checks_passed']=replay['checks_passed']
    report['publication_binding_checks_passed']=True;report['checks_passed']=True
    report['evidence']['results']=ref(root,Path(args.results));report['evidence']['qualification_replay']=ref(root,Path(args.replay))
    write_new(args.output,report);return report

if __name__=='__main__':
    p=argparse.ArgumentParser();sub=p.add_subparsers(dest='mode',required=True)
    evaluate_parser=sub.add_parser('evaluate')
    for n in ['project','plan','source','output']:evaluate_parser.add_argument('--'+n,required=True)
    bind_parser=sub.add_parser('bind')
    for n in ['project','replay','results','output']:bind_parser.add_argument('--'+n,required=True)
    a=p.parse_args();report=evaluate(a)if a.mode=='evaluate'else bind(a)
    print(json.dumps({'status':report['status'],'diagnostic_qualified':report['diagnostic_qualified'],'checks_passed':report['checks_passed']}))
