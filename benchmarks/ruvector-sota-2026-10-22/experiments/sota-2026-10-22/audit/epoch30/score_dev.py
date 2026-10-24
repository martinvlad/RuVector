"""Frozen closed-output DEV gold join and final receipt binding. Standard library only."""
import argparse
import json
import os
from pathlib import Path
from data_common import require,expected,write_new,SOURCE_SHA,SOURCE_BYTES,NATIVE_ORDER,SOURCE_MAP
from phase_audit import KIND,SHAS,read,ref,checked,source_checks,publisher,phase_integrity
from artifact_audit import audit_artifact,canonical_sha
from evidence_audit import audit_evidence
from nli_metrics import reader_check,metrics,diagnostic_gates

def quantile(values,q):
    import math
    a=sorted(values);x=(len(a)-1)*q;lo,hi=math.floor(x),math.ceil(x)
    return a[lo]+(x-lo)*(a[hi]-a[lo])

def evaluate(args):
    root=Path(args.project).resolve();plan_path=Path(args.plan).resolve()
    devexec=root/'experiments/sota-2026-10-22/epoch30/runs/dev/execution.json'
    plan,source=source_checks(root,plan_path,'dev'if devexec.exists()else'train')
    pub=publisher(root,plan);planref=ref(root,plan_path)
    tr=pub.phase_evidence(root,'train',planref);dv=pub.phase_evidence(root,'dev',planref)
    training=read(Path(args.train_report));require(training['epoch']==30 and training['kind']==KIND,'Wrong TRAIN report')
    model_path=root/'experiments/sota-2026-10-22/epoch30/MODEL_SEAL.json'
    report={'schema_version':1,'epoch':30,'kind':KIND,'status':'TRAINING_NOT_ACCEPTED_DEV_NOT_STARTED',
        'checks_passed':False,'diagnostic_qualified':False,'frozen_DEV_gates_passed':False,
        'train_integrity_passed':training['train_integrity_passed'],'metrics':None,'paired_differences':None,
        'diagnostic_checks':{},'failed_integrity_checks':[],'failed_diagnostic_checks':[],
        'reader_timing':None,'actual_execution':pub.aggregate_actual(tr,dv),'source_checks':source,
        'annotation_choices_attempted':0,'annotation_choices_accessed':0,'other_role_annotation_choices_accessed':0,'source_evidence_lists_accessed':0,
        'benchmark_accepted':False,'champion_promoted':False,'new_submission':False,'official_rank':None,
        'official_SOTA_verified':False,'confirmation':[],'calibration':[],
        'evidence':{'train_raw':tr['raw'],'train_execution':tr['execution'],'dev_raw':dv['raw'],
                    'dev_execution':dv['execution'],'training_report':ref(root,Path(args.train_report)),
                    'plan':planref,'freeze':ref(root,root/plan['source_freeze_path']),
                    'scorer_source':ref(root,Path(__file__).resolve())},
        'model_native_tokenizer_calls_by_scorer':0,'sampling_scope':'8DEVdocuments,3correlatedhypotheses each; projectdiagnostic only',
        'uncertainty':['Foundation/fuzzy overlap and laterpublisherreselection unknown',
                       'Retrievedexcerpt NotMentioned is not proof of global legalabsence',
                       'NetLoRA+classifier effect; noexclusiveLoRAcausal or officialbenchmark inference']}
    if model_path.exists():report['evidence']['model_seal']=ref(root,model_path)
    if dv['execution_value']is not None:report['status']='REJECTED_DEV_DIAGNOSTIC'
    try:
        require(training['train_integrity_passed']is True,'TRAIN functional integrity not accepted')
        require(model_path.exists(),'No sealed published MODEL')
        model=read(model_path);require(model['epoch']==30 and model['kind']==KIND
            and model['status']=='TRAINED_PARAMETER_ARTIFACT_SEALED','Wrong MODEL seal')
        mappings={'artifact':'parameter_artifact','raw':'train_raw','execution':'train_execution',
                  'plan':'source_plan','freeze':'source_freeze'}
        for key,target in mappings.items():
            require(training['evidence'][key]==model[target],'TRAIN report/MODEL lineage mismatch')
            checked(root,model[target])
        require(model['train_raw']==tr['raw']and model['train_execution']==tr['execution']
                and model['source_plan']==planref,'MODEL differs from current closed TRAIN/source')
        artifact_path=checked(root,model['parameter_artifact']);value=read(artifact_path)
        artifact=audit_artifact(artifact_path,planref['sha256'],SHAS['train'])
        report['evidence']['parameter_artifact']=model['parameter_artifact']
        require(dv['raw_value']is not None and pub.phase_completed(dv),'DEV not fully completed/closed')
        raw,execution=dv['raw_value'],dv['execution_value']
        phase=phase_integrity(root,raw,execution,plan,'dev')
        require(raw['admission']['parameter_artifact']==model['parameter_artifact'],'DEV actual MODEL admission differs')
        require(raw['loaded_parameter_artifact']['sha256']==model['parameter_artifact']['sha256']
                and raw['loaded_parameter_artifact']['bytes']==model['parameter_artifact']['bytes'],
                'DEV did not load exact published learned bytes')
        require(raw['adapted_state_load']['original_baseline_outputs_completed_before_load']==24,
                'Learned tensors decoded before original24 baseline')
        require(raw['model_initialization']['original_head_manifest']==value['original_head_manifest'],
                'Fresh original DEV classifier differs from original TRAIN classifier')
        bank=read(root/plan['dev_inputs_path'],SHAS['dev']);contexts=audit_evidence(root,raw,bank,'dev',plan)
        headsha=canonical_sha(value['original_head_manifest'])
        learnedmanifest=[{k:t[k]for k in ['name','shape','dtype','numel','bytes','sha256']}for t in value['tensors']]
        learnedsha=canonical_sha(learnedmanifest);prepared=[];times={k:[]for k in ['original_native','adapted_native','adapted_lexical','adapted_positional']}
        for case,inp in zip(raw['cases'],bank['records']):
            readers={}
            for armname in ['actual_native','lexical','positional']:
                arm=case['arms'][armname]
                require((arm['reader']['original']is not None)==(armname=='actual_native'),'Only native original comparator allowed')
                for state in (['original','adapted']if armname=='actual_native'else['adapted']):
                    name=('original_native'if state=='original'else'adapted_native'if armname=='actual_native'else'adapted_'+armname)
                    r=arm['reader'][state]
                    readers[name]=reader_check(r,arm['premise'],inp['hypothesis'],arm['joint_pair_tokens'],state,
                        model['parameter_artifact']['sha256'],headsha,learnedsha)
                    times[name].append(r['latency_seconds'])
                if armname=='actual_native':
                    a,b=arm['reader']['original'],arm['reader']['adapted']
                    require(all(a[k]==b[k]for k in ['native_pair_input_ids_sha256','premise_sha256','hypothesis_sha256','pair_tokens']),
                            'Original/adapted native pair is not byte/token identical')
            prepared.append({'id':case['id'],'document_id':case['document_id'],'readers':readers})
        require(sum(map(len,times.values()))==96 and raw['counters']['NLI_forward_calls_completed']==96
                and raw['counters']['original_DEV_forward_calls_completed']==24
                and raw['counters']['adapted_DEV_forward_calls_completed']==72,'Complete96genuine paired outputs required')
        # All integrity checks above precede any original-source gold field read.
        source_doc=read(Path(args.source),SOURCE_SHA)
        require(Path(args.source).stat().st_size==SOURCE_BYTES,'Original annotated source byte size changed')
        docs={d['id']:d for d in source_doc['documents']}
        for inp in bank['records']:
            require(docs[inp['document_id']]['text']==inp['document']
                and source_doc['labels'][inp['hypothesis_id']]['hypothesis']==inp['hypothesis']
                and len(docs[inp['document_id']]['annotation_sets'])==1,'Original DEV source authenticity failed')
        gold_dir=root/'experiments/sota-2026-10-22/audit/epoch30'
        reservation=gold_dir/'DEV_GOLD_JOIN_RESERVATION.json'
        write_new(reservation,{'epoch':30,'kind':KIND,'DEVcases':[r[0]for r in expected('dev')],
            'raw':dv['raw'],'execution':dv['execution'],'complete_predictions':96,'owned_group_closed':True,
            'choices_accessed_before_reservation':0,'no_retry_after_any_choice_access':True})
        access=gold_dir/'DEV_GOLD_ACCESS.jsonl'
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
            failed_diagnostic_checks=[k for k,v in gates.items()if not v],annotation_choices_accessed=24,
            context_audit=contexts,phase_integrity=phase,
            reader_timing={k:{'n':len(v),'p50_seconds':quantile(v,.5),'p95_seconds':quantile(v,.95),
                'scope':'Pairtokenization/tensorprep/fullmodel/softmax;state verification/init/retrieval separate'}for k,v in times.items()})
        report['status']='DEV_DIAGNOSTIC_QUALIFIED'if report['diagnostic_qualified']else'REJECTED_DEV_DIAGNOSTIC'
        report['evidence']['gold_reservation']=ref(root,reservation)
        report['evidence']['gold_access_log']=ref(root,access)
    except (ValueError,KeyError,TypeError,IndexError,ZeroDivisionError,OSError)as error:
        report['failed_integrity_checks']=[{'type':type(error).__name__,'message':str(error)}]
    write_new(args.output,report);return report

def bind(args):
    root=Path(args.project).resolve();replay=read(Path(args.replay));results=read(Path(args.results))
    require(replay['epoch']==results['epoch']==30 and replay['kind']==results['kind']==KIND,'Wrong final diagnostic scope')
    plan_path=checked(root,replay['evidence']['plan']);plan,_=source_checks(root,plan_path,'dev'if replay['evidence']['dev_execution']else'train')
    pub=publisher(root,plan);tr=pub.phase_evidence(root,'train',replay['evidence']['plan']);dv=pub.phase_evidence(root,'dev',replay['evidence']['plan'])
    require(pub.aggregate_actual(tr,dv)==replay['actual_execution']==results['actual_execution'],'Final actual phase projection differs')
    for key,pin in replay['evidence'].items():
        if pin is not None and not Path(pin['path']).is_absolute():checked(root,pin)
    for key in ['status','diagnostic_qualified','frozen_DEV_gates_passed','train_integrity_passed','metrics','paired_differences',
                'diagnostic_checks','failed_integrity_checks','failed_diagnostic_checks','reader_timing']:
        require(results.get(key)==replay.get(key),'Canonical RESULTS differs from frozen evaluation: '+key)
    require(all(results[k]is False for k in ['benchmark_accepted','champion_promoted','new_submission','official_SOTA_verified'])
            and results['official_rank']is None,'Forbidden benchmark/promotion/rank claim')
    report=json.loads(json.dumps(replay));report['evaluated_integrity_checks_passed']=replay['checks_passed']
    report['publication_binding_checks_passed']=True;report['checks_passed']=True
    report['evidence']['results']=ref(root,Path(args.results));report['evidence']['qualification_replay']=ref(root,Path(args.replay))
    write_new(args.output,report);return report

if __name__=='__main__':
    p=argparse.ArgumentParser();sub=p.add_subparsers(dest='mode',required=True)
    e=sub.add_parser('evaluate')
    for n in ['project','plan','train-report','source','output']:e.add_argument('--'+n,required=True)
    b=sub.add_parser('bind')
    for n in ['project','replay','results','output']:b.add_argument('--'+n,required=True)
    a=p.parse_args();r=evaluate(a)if a.mode=='evaluate'else bind(a)
    print(json.dumps({'status':r['status'],'diagnostic_qualified':r['diagnostic_qualified'],'checks_passed':r['checks_passed']}))
