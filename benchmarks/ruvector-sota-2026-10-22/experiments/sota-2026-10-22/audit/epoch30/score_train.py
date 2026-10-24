"""Closed TRAIN functional audit. No original TRAIN gold is opened or joined."""
import argparse
import json
import math
from pathlib import Path
from data_common import expected,require,finite,write_new
from phase_audit import KIND,SHAS,read,ref,checked,source_checks,publisher,phase_integrity
from evidence_audit import audit_evidence
from artifact_audit import audit_artifact,canonical_sha,MODULES
from nli_metrics import reader_check

def audit(args):
    root=Path(args.project).resolve();plan_path=Path(args.plan).resolve()
    plan,source=source_checks(root,plan_path,'train');pub=publisher(root,plan);planref=ref(root,plan_path)
    evidence=pub.phase_evidence(root,'train',planref,required=True)
    raw,execution=evidence['raw_value'],evidence['execution_value']
    freeze=ref(root,root/plan['source_freeze_path']);artifactref=raw.get('parameter_artifact')if raw is not None else None
    report={'schema_version':1,'epoch':30,'kind':KIND,'phase':'train','train_integrity_passed':False,
        'checks_passed':False,'status':'TRAIN_INTEGRITY_NOT_ACCEPTED','failures':[],
        'mechanism_flags':{},'actual_execution':evidence['actual'],'source_checks':source,
        'evidence':{'artifact':artifactref,'raw':evidence['raw'],'execution':evidence['execution'],
                    'plan':planref,'freeze':freeze},'TRAIN_source_choice_or_evidence_reads_by_auditor':0,
        'DEV_input_bank_reads_by_auditor':0,'model_native_tokenizer_or_original_weight_loads_by_auditor':0,
        'benchmark_accepted':False,'champion_promoted':False,'new_submission':False,'confirmation':[]}
    try:
        require(raw is not None and pub.phase_completed(evidence),'TRAIN not fully completed/closed')
        phase=phase_integrity(root,raw,execution,plan,'train')
        bank=read(root/plan['train_inputs_path'],SHAS['train'])
        require(raw['phase_input_bank']==ref(root,root/plan['train_inputs_path']),'TRAIN input identity changed')
        contexts=audit_evidence(root,raw,bank,'train',plan)
        require(artifactref is not None,'No complete learned parameter artifact')
        artifact_path=checked(root,artifactref)
        tensors=audit_artifact(artifact_path,planref['sha256'],SHAS['train']);value=read(artifact_path)
        require(raw['model_initialization']['original_head_manifest']==value['original_head_manifest'],
                'Artifact original classifier differs from actual initialized pretrained classifier')
        require(raw['train_integrity']=={k:value[k]for k in ['original_head_manifest','trainable_changes',
                    'frozen_pretrained_proof','effective_lora_delta']}|{'training_steps':24},
                'Closed raw/artifact mechanism and frozen-state provenance differ')
        receipt=raw['choice_read_receipt']
        require(receipt['TRAIN_annotation_choices_accessed']==24 and receipt['DEV_annotation_choices_accessed']==0
                and receipt['CONF_annotation_choices_accessed']==0 and receipt['other_role_annotation_choices_accessed']==0
                and receipt['source_evidence_lists_accessed']==0,'TRAIN selected-choice scope changed')
        require(receipt['selected']==[{k:r[k]for k in ['id','document_id','hypothesis_id','input_sha256']}
                                     for r in bank['records']],'Selected TRAIN choice/input identities changed')
        require(receipt['source']['bytes']==7608211
                and receipt['source']['sha256']=='dbceb356cd6203b35b27be94a5fa85e499a81c34c42c89ad53060b39f0257ba5'
                and receipt['inputs']['sha256']==SHAS['train'],'TRAIN choice source identity differs')
        steps=raw['steps'];require([r['id']for r in steps]==[r[0]for r in expected('train')],'Exactly ordered24 updates required')
        gradients={m:[]for m in MODULES};norms={m:[]for m in MODULES};losses=[];times=[]
        for i,(step,case,inp)in enumerate(zip(steps,raw['cases'],bank['records']),1):
            r=step['reader'];arm=case['arms']['actual_native']
            require(step['context_ref']=={'case_id':case['id'],'arm':'actual_native'}and r['case_id']==case['id']
                    and r['step']==i and 'native_target_index'not in r,'TRAIN step scope/order/target isolation changed')
            reader_check(r,arm['premise'],inp['hypothesis'],arm['joint_pair_tokens'])
            loss=r['unweighted_cross_entropy'];require(finite(loss)and loss>=0,'Nonfinite/invalid TRAIN loss')
            require(r['model_eval']is True and r['class_weights']is None
                    and r['optimizer_configuration']==value['algorithm']['optimizer']
                    and r['all_trainable_parameters_finite']is True,'TRAIN optimizer/model mode changed')
            require(finite(r['gradient_global_norm_before_clip'])and r['gradient_global_norm_before_clip']>=0,
                    'Nonfinite TRAIN gradient norm')
            require([g['module']for g in r['LoRA_B_gradients']]==MODULES,'Four intended B-gradient records required')
            for g in r['LoRA_B_gradients']:
                require(g['finite']is True and type(g['nonzero_entries'])is int and 0<=g['nonzero_entries']<=4096
                        and finite(g['l2_norm'])and g['l2_norm']>=0,'Invalid actual B-gradient evidence')
                if g['nonzero_entries']>0:
                    require(g['l2_norm']>0,'Nonzero B-gradient has zero norm')
                    gradients[g['module']].append(i);norms[g['module']].append(g['l2_norm'])
            require(finite(r['step_seconds'])and r['step_seconds']>=0,'Invalid TRAIN step timing')
            losses.append(loss);times.append(r['step_seconds'])
        for d in value['effective_lora_delta']:
            require(d['B_nonzero_gradient_steps']==gradients[d['module']]and norms[d['module']]
                    and d['max_B_gradient_l2']==max(norms[d['module']]),'Artifact/raw actual gradient provenance mismatch')
        finalmanifest=[{k:t[k]for k in ['name','shape','dtype','numel','bytes','sha256']}for t in value['tensors']]
        require(steps[-1]['reader']['trainable_manifest_sha256_after_step']==canonical_sha(finalmanifest),
                'Artifact differs from the final actual optimizer step')
        for k,n in {'NLI_forward_calls_attempted':24,'NLI_forward_calls_completed':24,'backward_calls_attempted':24,
                    'backward_calls_completed':24,'optimizer_steps_attempted':24,'optimizer_steps_completed':24,
                    'training_steps':24,'TRAIN_input_bank_reads':2,'TRAIN_annotation_choices_accessed':24}.items():
            require(raw['counters'][k]==n,'Independent fixed TRAIN count mismatch: '+k)
        report.update(train_integrity_passed=True,checks_passed=True,status='TRAIN_INTEGRITY_PASSED_ARTIFACT_FROZEN',
            mechanism_flags=tensors['mechanism_flags'],artifact_audit=tensors,context_audit=contexts,
            phase_integrity=phase,training_steps=24,
            loss_summary={'finite':True,'first':losses[0],'last':losses[-1],'mean':math.fsum(losses)/24,
                          'scope':'Observed24pre-update unweighted losses only; no quality/checkpoint-selection gate'},
            step_seconds=times,resources=raw['resources'])
    except (ValueError,KeyError,TypeError,IndexError,ZeroDivisionError,OSError)as error:
        report['failures']=[{'type':type(error).__name__,'message':str(error)}]
    write_new(args.output,report);return report

if __name__=='__main__':
    p=argparse.ArgumentParser()
    for n in ['project','plan','output']:p.add_argument('--'+n,required=True)
    a=p.parse_args();r=audit(a);print(json.dumps({'train_integrity_passed':r['train_integrity_passed'],'status':r['status']}))
