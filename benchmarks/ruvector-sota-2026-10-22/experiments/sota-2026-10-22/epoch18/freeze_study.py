"""Bind actual label-free capacity and projected DEV after early admission."""
from study_metadata import *
import importlib.util
def module(name,path):
    spec=importlib.util.spec_from_file_location(name,path);m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m);return m
def main():
    freeze,proof=frozen()
    op=E/'operational-plan.json';receipt=S/'audit/epoch18/prelabel-operational-admission-v1.json'
    admission=read(receipt);assert admission['checks_passed']is True and admission['actual_full_require_plan_calls']==1
    assert admission['plan_sha256']==sha(op)and admission['source_freeze_sha256']==sha(freeze)
    assert admission['native_execution_admitted']is False
    absent(S/'legal-transfer/epoch18/confirmation24.jsonl');absent(E/'launch.json')
    materialized=read(S/'legal-transfer/epoch18/dev-materialization.json')
    assert materialized['annotation_choices_projected']==24 and materialized['other_role_annotation_choices_accessed']==0
    assert materialized['root_source_freeze_sha256']==sha(freeze)
    data=S/'legal-transfer/epoch18/development24.jsonl'
    allow=S/'legal-transfer/epoch18/dev-allowlist.json'
    assert sha(data)==materialized['data_sha256'],'DEV data receipt mismatch'
    assert sha(allow)==materialized['allowlist_sha256'],'DEV allowlist receipt mismatch'
    assert read(allow)['data_sha256']==sha(data),'DEV allowlist data mismatch'
    capacity=read(S/'audit/epoch18/context-capacity-independent-v1.json')
    assert capacity['checks_passed']is True and capacity['status']=='INDEPENDENT_LABEL_FREE_BOTH_READER_CAPACITY_PASS'
    assert capacity['model_native_fit_paid_GPU_calls']==0
    du,cu=(capacity['phases'][k]['max_units']for k in ['development','confirmation'])
    assert type(du)is int and type(cu)is int and min(du,cu)>0
    plan=copy.deepcopy(read(op));plan.update(measurement_plan=True,operational_prelabel_only=False,
        prelabel_operational_admission={'path':str(receipt.relative_to(ROOT)),'sha256':sha(receipt)})
    plan['runtime_admission'].update(max_DEV_units=du,max_confirmation_units=cu,capacity_pending_label_free_inputs=False,
        scope='Actual frozen label-free complete source units; conservative fixed24xDEVmaxHTTPxunitratio+2xDEVinit+60; full phase init measured from pre-Popen; no performance guarantee.')
    pins={r['path']:r for r in plan['pins']}
    for row in current_files():
        pins[row['path']]={'path':row['path'],'sha256':row['sha256']}
    plan['pins']=sorted(pins.values(),key=lambda r:r['path'])
    write(E/'plan.json',plan)
    controller=module('epoch18_final_actual_validator',S/'controller/epoch18/loop.py')
    accepted=controller.require_plan(E/'plan.json',sha(E/'plan.json'))
    assert accepted==plan
    controller.verify_measurement_plan(plan)
    write(E/'freeze-receipt.json',{'schema_version':1,'plan':ident(E/'plan.json'),'source_freeze':ident(freeze),
        'operational_plan':ident(op),'early_operational_admission':ident(receipt),'pins':len(plan['pins']),
        'actual_full_final_require_plan_calls':1,'final_operational_contract_verified':True,
        'DEV_annotations_projected':24,'CONF_annotations_projected':0,'model_native_fit_paid_GPU_calls':0,
        'native_execution_admitted':False,'publication_and_exclusive_lock_gates_still_required':True})
    print(__import__('json').dumps({'plan':ident(E/'plan.json'),'pins':len(plan['pins']),
        'runtime_source_units':{'development':du,'confirmation':cu},'full_actual_final_require_plan_passed':True,
        'final_operational_contract_verified':True,'native_execution_admitted':False}))
if __name__=='__main__':main()
