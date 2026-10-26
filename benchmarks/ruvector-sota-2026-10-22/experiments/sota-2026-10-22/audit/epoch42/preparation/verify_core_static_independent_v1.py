"""Independent source/metadata audit; never imports reviewed candidate modules."""
import ast
import hashlib
import json
from pathlib import Path
import re

OWN=Path('/workspace/ruvector-e42-acceptance-audit')
ENG=Path('/workspace/ruvector-e42-engineering-impl')
CORE=ENG/'core-source-v1/project'
PRE=ENG/'asset-preflight-source-v2/project'
R=Path('/tmp/ruvector-sota-2026-10-22/epoch42-222874558c0b/project')
B='experiments/sota-2026-10-22/'
CAN=B+'candidate/epoch42/'
AUD=B+'audit/epoch42/'
E=B+'epoch42/'
OMITTED=CAN+'__pycache__/counters.cpython-312.pyc'
checks=[]
def check(name,value):
    checks.append({'check':name,'passed':value is True})
    if value is not True:raise ValueError(name)
def sha(b):return hashlib.sha256(b).hexdigest()
def ref(path):
    b=path.read_bytes();return {'path':str(path),'bytes':len(b),'sha256':sha(b)}
def load(path):return json.loads(path.read_text())
def literal_assign(path):
    out={}
    for n in ast.parse(path.read_text()).body:
        if isinstance(n,ast.Assign):
            try:v=ast.literal_eval(n.value)
            except (ValueError,TypeError):continue
            for target in n.targets:
                if isinstance(target,ast.Name):out[target.id]=v
                elif isinstance(target,ast.Tuple):
                    for name,value in zip(target.elts,v):out[name.id]=value
    return out
def functions(path):
    return {n.name:ast.dump(n,include_attributes=False)for n in ast.parse(path.read_text()).body if isinstance(n,(ast.FunctionDef,ast.AsyncFunctionDef,ast.ClassDef))}
def put(path,value):
    with path.open('x')as f:json.dump(value,f,indent=2,allow_nan=False);f.write('\n')

ready_path=ENG/'core-source-v1/READY.v1.json';interface_path=ENG/'RUNTIME_PLAN_INTERFACE.v1.json'
ready=load(ready_path);interface=load(interface_path)
check('exact sealed READY',ref(ready_path)['sha256']=='014fc07c6373636d5f40af68f86ff7aa2e1a2cf83d0ba588a3acd7d577727d7d')
check('exact sealed interface',ref(interface_path)['sha256']=='7131086e3459b8c7cab1b7dd9a6f1b1966ed9986451d778e65876ae0d6acea06')
rows=ready['files'];check('unique54 entries',len(rows)==len({x['path']for x in rows})==54)
omitted=[x for x in rows if x['path']==OMITTED];check('exactly one omitted compiled cache entry',omitted==[{'path':OMITTED,'bytes':3049,'sha256':'e8b9af2d8b986859dcdb093b008b0df254b3d6dbcd93c7ce2251bd4b76185507'}])
allowed=[x for x in rows if x['path']!=OMITTED];check('53 regular public sources and metadata',len(allowed)==53)
snapshot=OWN/'core-source-static-v1';snapshot.mkdir(exist_ok=False)
for row in allowed:
    path=CORE/row['path'];check('regular source '+row['path'],path.is_file()and not any(x.is_symlink()for x in[path,*path.parents]))
    b=path.read_bytes();check('exact source '+row['path'],len(b)==row['bytes']and sha(b)==row['sha256'])
    check('no bytecode dependency '+row['path'],b'__pycache__'not in b and b'.pyc'not in b)
    dest=snapshot/row['path'];dest.parent.mkdir(parents=True,exist_ok=True);dest.write_bytes(b)
check('no bytecode interface dependency','__pycache__'not in interface_path.read_text()and'.pyc'not in interface_path.read_text())
by_path={x['path']:x for x in allowed}
for key,row in interface['required_refs'].items():
    p=CORE/row['path']if row['path']in by_path else R/row['path']
    got=ref(p);check('interface exact reference '+key,got['bytes']==row['bytes']and got['sha256']==row['sha256'])
    f=interface['plan_fields']
    for suffix,want in [('_path',row['path']),('_sha256',row['sha256'])]:
        if key+suffix in f:check('interface alias '+key+suffix,f[key+suffix]==want)

pre_ready=load(ENG/'asset-preflight-source-v2/PREFLIGHT_READY.v2.json')
comparison=[]
for rel in [CAN+'runtime/common.py',CAN+'runtime/model_assets_guard.py',CAN+'reader_tasksource.py']:
    check('all function and class AST unchanged from real preflight '+rel,functions(CORE/rel)==functions(PRE/rel))
    comparison.append({'path':rel,'before':ref(PRE/rel),'after':ref(CORE/rel),'all_function_and_class_AST_equal':True})
for rel in [CAN+'runtime/model_assets_guard.py',CAN+'asset_identity.py',CAN+'MODEL_TASKSOURCE_SOURCE.json',CAN+'MODEL_TASKSOURCE_ASSETS.json',CAN+'MODEL_TASKSOURCE_ASSETS.expected.json',CAN+'research/CLASSIC_PREACQUISITION_CATALOG.json']:
    check('byte-identical actual preflight asset authority '+rel,(CORE/rel).read_bytes()==(PRE/rel).read_bytes())
before=load(PRE/(CAN+'MODEL_PROFILES.json'));after=load(CORE/(CAN+'MODEL_PROFILES.json'))
before['profiles']['tasksource']['reader_sha256']=after['profiles']['tasksource']['reader_sha256']
check('only model profile change is new reader source SHA',before==after)
common=literal_assign(CORE/(CAN+'runtime/common.py'));reader=literal_assign(CORE/(CAN+'reader_tasksource.py'))
check('current exact base ROOT owner',common['SOURCE']=='222874558c0b696f92824e5fce3775494877f821'and common['ROOT_CONTRACT_SHA']=='83e7117e336a12497c994aea25f273e3f80456df6373c5d97510ac2936ffd6e2'and(common['OWNER_PID'],common['OWNER_TICKS'],common['LOCK_FD'],common['LOCK_DEVICE'],common['LOCK_INODE'])==(125788,29584865,3,33,13626)and common['OWNER_SHA']=='a5723c70ca695c14212083ba4123d1a26ca4835ffe76833e63a9ef2d2bb36e62')
check('static flags only activated',common['SOURCE_BINDINGS_READY']is True and common['ASSET_PREFLIGHT_BINDINGS_READY']is True and reader['SOURCE_BINDINGS_READY']is True)
check('real preflight false snapshot retained',literal_assign(PRE/(CAN+'runtime/common.py'))['SOURCE_BINDINGS_READY']is False and literal_assign(PRE/(CAN+'reader_tasksource.py'))['SOURCE_BINDINGS_READY']is False)
check('model unchanged exact original F32 identity',reader['WEIGHT_SHA']=='534780ea5d1f76d22be966d10de67cf2690ec25010aeb4b607d4aadcd2649ebc'and reader['CONFIG_SHA']=='ab08ecb517cb2c27f415d2fa9a42cf6b695870edf53d2fb73905dbe39fcecb75')
dispatch=literal_assign(CORE/(E+'preparation/dispatch_once.py'));closure=literal_assign(CORE/(AUD+'closure_metadata.py'))
check('final dispatcher COMMON_SHA pins final common',dispatch['COMMON_SHA']==by_path[CAN+'runtime/common.py']['sha256'])
check('final observer launch pin pins final launcher',closure['PRE_POPEN_LAUNCH_SHA']==by_path[CAN+'runtime/launch.py']['sha256'])
activation=load(CORE/ready['activation_diff']['path']);gate_rows=[]
for row in activation['source_gate_activations']:
    rel=row['path'];body=(CORE/rel).read_text();inverse=re.sub(r'SOURCE_BINDINGS_READY\s*=\s*true','SOURCE_BINDINGS_READY=false',body,count=1)if rel.endswith('.cjs')else re.sub(r'SOURCE_BINDINGS_READY\s*=\s*True','SOURCE_BINDINGS_READY=False',body,count=1)
    if rel in [E+'preparation/dispatch_once.py',AUD+'closure_metadata.py']:
        # The recorded gate-only intermediate precedes separately declared globals.
        # Verify the final pin values above; do not call the intermediate final.
        gate_rows.append({'path':rel,'final_sha256':sha(body.encode()),'recorded_gate_intermediate_sha256':row['after_sha256'],'separate_pin_update_verified':True})
    else:
        check('inverse exact original scalar flag '+rel,len(inverse.encode())==row['before_bytes']and sha(inverse.encode())==row['before_sha256'])
        gate_rows.append({'path':rel,'before_sha256':row['before_sha256'],'final_sha256':sha(body.encode()),'inverse_scalar_exact':True})

f=interface['plan_fields'];counter=load(CORE/(CAN+'EXPECTED_COUNTERS.json'));units=[61,64,35,15]
check('fixed72 physical36 derived12 cases four document clusters',f['actual_NLI_forwards']==72 and f['derived_forecasts']==36 and f['DEV_cases']==12 and f['document_clusters']==4 and f['native_indexes']==4 and f['native_queries']==12 and f['windows_per_case_arm']==2)
check('source units and BGE mathematical work',sum(units)==175 and f['source_units_total']==175 and f['expanded_pair_source_units']==525 and f['expected_BGE_texts']==187 and f['expected_BGE_forward_calls']==sum((n+7)//8 for n in units)+12==35 and counter['expected_BGE_forward_calls']==35)
check('68 fixed plus5 variable counters',len(counter['dev'])==68 and len(counter['observed_variable_counter_keys'])==5 and f['expected_operation_counters']['dev']==counter['dev'])
check('fixed counts no hidden model/gold/paid work',counter['dev']['NLI_forward_calls_attempted']==72 and counter['dev']['derived_forecasts_completed']==36 and counter['dev']['native_insertions_completed']==175 and counter['dev']['native_hit_source_validations']==525 and all(counter['dev'][k]==0 for k in ['gold_reader_calls','semantic_gold_labels_decoded','paid_calls','GPU_calls','TRAIN_input_reads','CONF_input_reads','calibration_calls','full104_requests']))
check('roles DEV only with held champion',f['data_roles']['train']==f['data_roles']['calibration']==f['data_roles']['confirmation']==[]and f['used_confirmation_identities']==[]and f['champion_promoted']is False)

launch_tree=ast.parse((CORE/(CAN+'runtime/launch.py')).read_text());return_keys=[];additional_keys=[]
for n in ast.walk(launch_tree):
    if isinstance(n,ast.FunctionDef)and n.name=='completion_invariants':
        for z in ast.walk(n):
            if isinstance(z,ast.Return)and isinstance(z.value,ast.Dict):return_keys=[ast.literal_eval(k)for k in z.value.keys]
    if isinstance(n,ast.Assign):
        for z in n.targets:
            if isinstance(z,ast.Subscript)and isinstance(z.value,ast.Name)and z.value.id=='invariants':additional_keys.append(ast.literal_eval(z.slice))
emitted=set(return_keys+additional_keys);check('launcher15 actual emitted closure invariants',len(return_keys)==14 and additional_keys==['whole_worker_CPU_guard_before_exec']and len(emitted)==15)
qpath=Path('/workspace/ruvector-e42-data-scorer/scorer-source-v2/project')/(AUD+'e42_qualification.py');qkeys=literal_assign(qpath)['INVARIANTS']
blocker={'scope':'sealed scorer V2 exactset differs from real launcher','emitted_count':len(emitted),'scorer_V2_count':len(qkeys),'missing_in_scorer_V2':sorted(emitted-qkeys),'extra_in_scorer_V2':sorted(qkeys-emitted),'requires_prospective_versioned_scorer_fix_before_SOURCE':True}

source_strings=[]
for row in allowed:
    p=CORE/row['path']
    if p.suffix in['.py','.cjs','.js']:
        text=p.read_text();source_strings.extend(re.findall(r'[A-Za-z0-9_./-]*(?:__pycache__|\.pyc)[A-Za-z0-9_./-]*',text))
check('no active source bytecode import or dependency',not source_strings)
work={'schema_version':1,'scope':'SOURCE_ONLY_NO_CANDIDATE_IMPORT_OR_EXECUTION','checks':checks,'checks_passed':all(x['passed']for x in checks),'ready':ref(ready_path),'runtime_interface':ref(interface_path),'public_copy_allowed_rows':allowed,'public_copy_omitted_rows':omitted,'omitted_body_read_or_executed':False,'active_dependency_on_omitted_entry':False,'original_READY_is_retained_historical_package_inventory':True,'exact_public_copy_rule':'53 exact allowed entries only; original54 entry READY remains unchanged metadata; do not turn omission into broad missing-reference allowance.','preflight_function_AST_comparisons':comparison,'activation_gate_rows':gate_rows,'closure_invariant_emitted_keys':sorted(emitted),'scorer_V2_integration_blocker':blocker,'actual_SOURCE_or_NLI_permission_from_this_workpaper':False,'actual_model_tokenizer_native_guard_case_or_scorer_calls_by_reviewer':0,'tests_repeated':0}
put(OWN/'CORE_STATIC_VERIFICATION.v1.json',work)
print(json.dumps({'checks':len(checks),'checks_passed':work['checks_passed'],'emitted_closure_count':len(emitted),'scorerV2count':len(qkeys),'proof':ref(OWN/'CORE_STATIC_VERIFICATION.v1.json')},indent=2))
