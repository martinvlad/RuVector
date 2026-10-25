"""Source-only audit-protocol interface checks; no evaluator or oracle calls."""
import argparse,ast,json
from pathlib import Path
from data_common import require,read,identity,write_new,expected,AUTHORED_LABEL_MAP_SHA256,SOURCE_CHECKPOINT
from phase_audit import KIND,ROLES,ENGINEERING_GATE
from nli_metrics import ARMS,PROFILES,PRIMARY
from model_audit import LEGACY_FORMAT,XXL_METADATA_SHA,LEGACY_PLAN_SHA
from source_coverage_audit import FULL_POLICY
from lifecycle_audit import EVENTS

def literal(node,values):
    if isinstance(node,ast.Constant):return node.value
    if isinstance(node,(ast.List,ast.Tuple)):return [literal(n,values)for n in node.elts]
    if isinstance(node,ast.Dict):return {literal(k,values):literal(v,values)for k,v in zip(node.keys,node.values)}
    if isinstance(node,ast.Name)and node.id in values:return values[node.id]
    if isinstance(node,ast.Call)and isinstance(node.func,ast.Name)and node.func.id=='list'and len(node.args)==1 and not node.keywords:return list(literal(node.args[0],values))
    raise ValueError('Nonliteral publication schema expression')

def run(args):
    folder=Path(__file__).resolve().parent;path=Path(args.protocol).resolve();root=Path(args.candidate_project).resolve()
    protocol=read(path);candidate=root/'experiments/sota-2026-10-22/candidate/epoch36';core=read(candidate/'ENGINEERING_PROTOCOL.json');checks=[]
    def check(name,value):require(value,name);checks.append({'name':name,'passed':True})
    def exact(file,pin):return {**identity(file),'path':pin['path']}==pin
    check('exact_epoch_kind_phase_source',protocol['schema_version']==1 and protocol['epoch']==36 and protocol['kind']==KIND and protocol['phase']=='engineering'and protocol['source_checkpoint']==SOURCE_CHECKPOINT)
    check('all_benchmark_roles_and_used_confirmations_empty',protocol['data_roles']==ROLES and all(protocol[k]==[]for k in ['training_ids','development_ids','calibration_ids','confirmation_ids','used_confirmation_identities']))
    check('exact_nine_authored_case_ids_and_frozen_label_identity',protocol['engineering_case_ids']==[r[0]for r in expected('engineering')]and protocol['authored_label_mapping_sha256']==AUTHORED_LABEL_MAP_SHA256)
    check('exact_six_identity_mapped_arms',protocol['raw_arms']==protocol['metric_arms']==ARMS and protocol['raw_to_metric_arm']=={a:a for a in ARMS}and protocol['primary']==PRIMARY)
    check('unchanged_structured_9_class3_gain2_proper_score_gates',protocol['engineering_gate']==ENGINEERING_GATE)
    check('candidate_source_protocol_identity',exact(candidate/'ENGINEERING_PROTOCOL.json',protocol['candidate_protocol']))
    check('candidate_case_role_arm_primary_order_interfaces_match',core['data_roles']==ROLES and core['engineering_case_ids']==protocol['engineering_case_ids']and core['raw_arms']==ARMS and core['primary']==PRIMARY and core['model_order']==protocol['model_execution_order']==['b354','xxlarge'])
    check('candidate_runtime_54_18_36_9_1_CPU2_600_interfaces_match',all(protocol['runtime'][k]==v for k,v in core['runtime'].items())and protocol['runtime']['CPU_threads']==2 and protocol['runtime']['additional_worker_or_retry_allowed']is False)
    check('exact_sealed_core_manifest_and_READY_refs',all(exact(root/pin['path'],pin)for pin in [protocol['core_source_manifest'],protocol['core_source_ready']]))
    prior=read(folder/'SOURCE_READY_v1.json');check('all_14_prior_scorer_sources_unchanged',len(prior['sources'])==14 and all(identity(Path(pin['path']))==pin for pin in prior['sources'])and exact(folder/'SOURCE_READY_v1.json',protocol['scorer_source_ready_v1']))
    wanted={'KIND','ROLES','ARM_NAMES','PRIMARY_ARM','GATE_CONTROLS','ENGINEERING_GATE','MODEL_EXECUTION_ORDER','MODEL_FORWARD_COUNTS','ENGINEERING_CASES','TOTAL_MAX_NLI_FORWARD_CALLS','ENGINEERING_NATIVE_QUERIES','SOURCE_SERIALIZATION_FORMAT','SOURCE_PARAMETER_DTYPE','COMPUTE_DTYPE'};values={}
    for node in ast.parse(Path(args.publication_schema).read_bytes()).body:
        if isinstance(node,ast.Assign)and len(node.targets)==1 and isinstance(node.targets[0],ast.Name)and node.targets[0].id in wanted:values[node.targets[0].id]=literal(node.value,values)
    check('publication_roles_arms_primary_gate_interfaces_match',values['KIND']==KIND and values['ROLES']==ROLES and values['ARM_NAMES']==ARMS and values['PRIMARY_ARM']==PRIMARY and values['ENGINEERING_GATE']==ENGINEERING_GATE)
    check('publication_fixed_work_and_source_dtype_interfaces_match',values['MODEL_EXECUTION_ORDER']==['b354','xxlarge']and values['MODEL_FORWARD_COUNTS']=={'b354':18,'xxlarge':36}and values['ENGINEERING_CASES']==9 and values['TOTAL_MAX_NLI_FORWARD_CALLS']==54 and values['ENGINEERING_NATIVE_QUERIES']==9 and values['SOURCE_SERIALIZATION_FORMAT']==LEGACY_FORMAT and values['SOURCE_PARAMETER_DTYPE']=='F16'and values['COMPUTE_DTYPE']=='F32')
    check('exact_source_profile_weights_revisions_and_label_maps',all(protocol['model_profiles'][tag]=={'repository':v['repository'],'revision':v['revision'],'original_weights_bytes':v['bytes'],'original_weights_sha256':v['sha'],'native_label_order':v['order'],'canonical_E_C_N_from_raw':v['canonical']}for tag,v in PROFILES.items()))
    source=protocol['xxlarge_original_source'];check('approved_legacy_header_loadplan_no_source_I64_or_position_buffer',source['original_metadata_sha256']==XXL_METADATA_SHA and source['legacy_original_load_plan_sha256']==LEGACY_PLAN_SHA and source['source_state_tensor_count']==782 and source['source_I64_tensors']==0 and source['source_position_ids_present']is False and source['weights_only']is True and source['mmap']is False and source['actual_loader_map_location']=='cpu')
    policy=protocol['source_policy'];check('full_source_exact_coverage_and_retrieval_absence_boundary',policy['full_source_policy']==FULL_POLICY and policy['full_source_character_and_numeric_coverage']==1 and policy['joint_pair_cap_each_reader']==512 and policy['complete_actual_native_unique_unitset_required']is True and policy['native_two_cross_model_bytes_and_spans_identical']is True and policy['retrieval_miss_can_prove_source_absence_or_insufficient_evidence']is False)
    oracle=protocol['oracle_policy'];check('all54_then_once9_join_and_no_scorer_oracle_traversal',oracle['all_finite_actual_readouts_required_before_join']==54 and oracle['worker_label_join_reads']==1 and oracle['worker_labels_joined']==9 and oracle['scorer_oracle_traversals']==0 and oracle['both_readers_unloaded_and_native_child_closed_before_join']is True and protocol['lifecycle_policy']['events_per_profile']==EVENTS)
    check('no_benchmark_generalization_promotion_or_eligibility_admission',protocol['engineering_only']is True and protocol['benchmark_accuracy']is None and protocol['benchmark_generalization_claim']is False and protocol['promotion_allowed']is False and protocol['training_lineage_complete']is False and protocol['official_eligibility']=='HOLD')
    for file in folder.glob('*.py'):
        tree=ast.parse(file.read_bytes());imports=[]
        for node in ast.walk(tree):
            if isinstance(node,ast.Import):imports.extend(n.name.split('.')[0]for n in node.names)
            elif isinstance(node,ast.ImportFrom):imports.append((node.module or '').split('.')[0])
        require(not set(imports)&{'torch','transformers','numpy','tokenizers','safetensors','onnxruntime'},'ML import in scorer source')
    check('all15_scorer_fixture_sources_AST_and_no_ML_imports',len(list(folder.glob('*.py')))==15)
    return {'schema_version':1,'epoch':36,'checks_passed':True,'checks':checks,'protocol':identity(path),'candidate_protocol':identity(candidate/'ENGINEERING_PROTOCOL.json'),'publication_schema':identity(Path(args.publication_schema)),'preserved_scorer_READY_v1':identity(folder/'SOURCE_READY_v1.json'),'counts':{'tests':len(checks),'actual_EVALUATE_or_BIND':0,'model_tokenizer_native_calls':0,'original_weight_reads':0,'oracle_or_benchmark_label_traversals':0},'scope':'Static independent audit-protocol/core/publication/scorer schema consistency only. No measurement, source freeze, scientific evaluation, model execution or acceptance claim.'}

if __name__=='__main__':
    parser=argparse.ArgumentParser()
    for key in ['protocol','candidate-project','publication-schema','output']:parser.add_argument('--'+key,required=True)
    args=parser.parse_args();report=run(args);write_new(args.output,report);print(json.dumps({'checks_passed':True,'tests':len(report['checks'])}))
