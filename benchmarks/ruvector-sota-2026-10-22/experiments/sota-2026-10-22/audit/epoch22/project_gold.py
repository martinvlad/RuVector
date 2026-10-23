"""Project only fixed role labels after immutable completed predictions/cleanup.

No worker or model imports this module. The source is never opened by preflight
or unit tests; original choices are accessed only inside project() after guards.
"""
from __future__ import annotations
import argparse
from datetime import datetime, timezone
from pathlib import Path
import replay as R

SOURCE_PATH = R.PREFIX + 'legal-transfer/epoch3/sources/original-train.json'
SOURCE_SHA = 'dbceb356cd6203b35b27be94a5fa85e499a81c34c42c89ad53060b39f0257ba5'
SOURCE_BYTES = 7608211
INSTRUCTION = ('Determine whether the agreement entails the supplied hypothesis. '
               'Answer Yes only if entailed. Answer No if the hypothesis is contradicted or not mentioned.')
demand = R.demand


def guard_completed(plan_path, raw_path, execution_path, expected_raw_sha, authorized):
    demand(authorized is True, 'postprediction role-specific root authorization required')
    demand(R.identity(raw_path)['sha256'] == expected_raw_sha, 'sealed raw SHA required before labels')
    plan, protocol = R.plan_replay(plan_path)
    raw, execution = R.read(raw_path), R.read(execution_path)
    phase = raw['phase']
    demand(phase in ('dev','confirmation') and raw['epoch'] == 22
           and raw['status'] == 'COMPLETED_CORPUS_AWAITING_INDEPENDENT_SCORE'
           and raw['plan_sha256'] == R.identity(plan_path)['sha256'] and raw['errors'] == [], 'complete sealed corpus predictions required before source labels')
    state, instance = R.model_replay(raw, protocol)
    R.assets_replay(raw, plan)
    readiness = R.engineering_replay(raw, protocol, state, instance)
    demand(readiness['passed'], 'all semantic readiness checks must pass before source labels')
    R.resources_replay(raw, execution, raw_path, phase, True)
    R.counters_replay(raw, True)
    R.tokenizer_report_replay(raw, raw_path, raw['plan_sha256'], execution_path)
    docs = protocol['data']['DEV_document_ids' if phase == 'dev' else 'CONF_document_ids']
    demand([d['id'] for d in raw['documents']] == docs and all(type(d['id']) is int for d in raw['documents']), 'complete frozen document predictions required before source labels')
    for document in raw['documents']:
        demand(len(document['questions']) == 3, 'all three question predictions required before labels')
        for question, hid in zip(document['questions'], protocol['data']['hypothesis_ids']):
            demand(question['id'] == f'original-contractnli:train:epoch22:{phase}:{document["id"]}:{hid}'
                   and set(question['arms']) == set(R.M.ARMS), 'every fixed matched-arm prediction must be sealed before labels')
            for arm in R.M.ARMS:
                value = question['arms'][arm]
                R.forward_replay(value['forward'], value['premise'], question['hypothesis'], state, instance)
    if phase == 'confirmation':
        admission = R.read(R.member(R.PREFIX + 'epoch22/CONFIRMATION_ADMISSION.json'))
        demand(admission['checks_passed'] is True and admission['independent_DEV_accepted'] is True
               and admission['runtime_gate_passed'] is True and admission['plan_sha256'] == raw['plan_sha256'], 'exact accepted DEV/runtime admission required before CONF labels')
        report_path = R.member(admission['independent_DEV_report_path'])
        demand(R.identity(report_path)['sha256'] == admission['independent_DEV_report_sha256'], 'accepted DEV report identity changed')
        report = R.read(report_path)
        demand(report['phase'] == 'dev' and report['checks_passed'] is True and report['DEV_gate_passed'] is True
               and report['accepted_for_confirmation'] is True and report['runtime_gate_passed'] is True
               and report['plan_sha256'] == raw['plan_sha256'], 'independent DEV report does not authorize CONF labels')
        demand(state == report['model_state_sha256'] == admission['expected_FP32_state_sha256']
               and raw['tokenizer']['backend_sha256'] == report['tokenizer_backend_sha256'] == admission['expected_tokenizer_backend_sha256'], 'CONF changed the accepted DEV state/tokenizer')
    return plan, protocol, raw


def project(plan_path, raw_path, execution_path, expected_raw_sha, authorized=False):
    plan, protocol, raw = guard_completed(plan_path, raw_path, execution_path, expected_raw_sha, authorized)
    phase = raw['phase']; ids = protocol['data']['DEV_document_ids' if phase == 'dev' else 'CONF_document_ids']
    input_path = R.member(R.PREFIX + 'legal-transfer/epoch22/inputs.' + phase + '.json')
    inputs = R.read(input_path)
    expected_ids = [f'original-contractnli:train:epoch22:{phase}:{d}:{h}' for d in ids for h in protocol['data']['hypothesis_ids']]
    demand(inputs['role'] == phase and [r['id'] for r in inputs['records']] == expected_ids, 'exact immutable phase input projection required')
    demand(all(set(r) == {'id','input','input_sha256'} for r in inputs['records']), 'only source inputs, no worker labels permitted')
    for row in inputs['records']:
        demand(row['input_sha256'] == R.digest(R.canonical(row['input'])), 'source input byte identity mismatch')
    source_path = R.member(SOURCE_PATH)
    source_identity = R.identity(source_path,SOURCE_PATH)
    demand(source_identity == {'path':SOURCE_PATH,'bytes':SOURCE_BYTES,'sha256':SOURCE_SHA}, 'exact source-licensed original training corpus required')
    # FIRST original corpus parse and annotation choice access in this module.
    source = R.read(source_path)
    documents = source['documents']; demand(len(documents) == 423 and all(type(d['id']) is int for d in documents), 'original423 literal document identity set required')
    by_id = {d['id']:d for d in documents}; demand(len(by_id) == 423, 'duplicate original source document ID')
    records=[]; input_index=0
    for document_id, prediction in zip(ids,raw['documents']):
        document=by_id[document_id]
        demand(document['text'] == prediction['state'] and len(document['annotation_sets']) == 1, 'exact original source state and unique annotation set required')
        for hid, question in zip(protocol['data']['hypothesis_ids'],prediction['questions']):
            row=inputs['records'][input_index]; input_index+=1
            hypothesis=source['labels'][hid]['hypothesis']
            expected={'state':document['text'],'questions':{'decision':{'type':'choice','instructions':INSTRUCTION,
                      'criteria':{'Yes':hypothesis,'No':'The agreement does not establish the following: '+hypothesis}}}}
            demand(row['input']==expected and row['id']==question['id'] and row['input_sha256']==question['input_sha256']
                   and question['hypothesis']==hypothesis, 'model input differs from exact fixed original source claim')
            label=document['annotation_sets'][0]['annotations'][hid]['choice']
            demand(type(label) is str and label in R.M.ORDER, 'unknown original typed annotation')
            records.append({'id':row['id'],'document_id':document_id,'hypothesis_id':hid,
                            'original_threeway_label':label,'gold':'Yes' if label=='Entailment' else 'No',
                            'input_sha256':row['input_sha256']})
    demand(len(records)==24,'exact24 postprediction annotations required')
    return {'schema_version':1,'epoch':22,'phase':phase,'at':datetime.now(timezone.utc).isoformat(),
            'status':'FIXED_ROLE_GOLD_PROJECTED_AFTER_COMPLETE_SEALED_PREDICTIONS_AND_CLEANUP',
            'raw_receipt_sha256':expected_raw_sha,'execution_receipt':R.identity(execution_path,str(Path(execution_path).relative_to(R.ROOT))),
            'plan_sha256':R.identity(plan_path)['sha256'],'source':source_identity,
            'source_revision':'stanfordnlp/contract-nli@eced6528dd3c1d14d73f9a87df8f7bdbc03126f9/train.json',
            'input_receipt':R.identity(input_path,str(input_path.relative_to(R.ROOT))),
            'annotation_choices_accessed':24,'other_role_annotation_choices_accessed':0,
            'old_reserved48_choices_accessed':0,'labels_used_for_model_fit_calibration_selection':False,
            'model_native_paid_GPU_calls':0,'records':records}


def main():
    ap=argparse.ArgumentParser()
    for key in ('plan','raw','execution','out'):ap.add_argument('--'+key,type=Path,required=True)
    ap.add_argument('--expected-raw-sha256',required=True)
    ap.add_argument('--authorized-after-completed-predictions',action='store_true')
    a=ap.parse_args();v=project(a.plan,a.raw,a.execution,a.expected_raw_sha256,a.authorized_after_completed_predictions);R.write_new(a.out,v)
    print({'status':v['status'],'phase':v['phase'],'annotation_choices_accessed':24,'model_native_calls':0})


if __name__=='__main__':main()
