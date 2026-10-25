"""Authored full/partial/UNKNOWN canonical receipt projection fixtures only."""
import argparse,copy,json
from pathlib import Path
from data_common import write_new,require
from phase_audit import publisher,ref,KIND,SOURCE,ROLES
def run(root):
    names=['publication_common_v1.py','phase_schema_v1.py','phase_receipts_v1.py']
    pins=[ref(root,root/'experiments/sota-2026-10-22/epoch35/publication'/name)for name in names]
    pub=publisher(root,{'pins':pins});checks=[]
    def req(value):
        if not value:raise AssertionError('Projection fixture expectation failed')
    def rejects(call):
        try:call()
        except (ValueError,KeyError,TypeError,AssertionError):return
        raise AssertionError('Invalid projection fixture accepted')
    def test(name,call):call();checks.append({'name':name,'passed':True})
    def fixture(source='raw.json'):
        counters={'corpus_batches_attempted':1,'corpus_batches_completed':1,'NLI_forward_calls_completed':48,'native_queries_completed':12}
        raw={'epoch':35,'kind':KIND,'phase':'engineering','source_checkpoint':SOURCE,'data_roles':copy.deepcopy(ROLES),'counters':counters,'errors':[]}
        execution={'epoch':35,'kind':KIND,'phase':'engineering','worker_attempts_reserved':1,'verified_worker_starts':1,
            'uncertain_start':False,'owned_live_processes_closed':True,'owned_live_group_members':[],
            'owned_process_closure_observation':'OBSERVED','wall_seconds_including_init_cleanup':10.,
            'children_user_seconds':18.,'children_system_seconds':1.,'largest_child_peak_RSS_bytes':1000000,
            'CPU_affinity':[0,1],'allowed_further_phase_workers':0,'cleanup_errors':[],'launcher_error':None,
            'raw_operation_counters':copy.deepcopy(counters),'raw_operation_counters_source':source,
            'operation_counts_complete':source=='raw.json','backend_execution_since_checkpoint':'NOT_APPLICABLE_FINAL_RAW'if source=='raw.json'else'UNKNOWN',
            'status':'WORKER_COMPLETED'if source=='raw.json'else'WORKER_FAILED_OR_TIMEOUT','exit_code':0 if source=='raw.json' else 2,
            'raw_bytes':32,'raw_sha256':'a'*64,'partial_raw_bytes':16,'partial_raw_sha256':'b'*64,
            'source_plan_unchanged':True,'raw_closure_invariants':{'fixture':True}}
        if source=='UNKNOWN':raw=None;execution['raw_operation_counters']=None
        return raw,execution
    def evidence(raw,execution):
        return {'actual':pub.derive_actual(raw,execution),'execution_value':execution,
            'supervisor_closure_value':{'physical_closure_passed':True,'unknown_physical_ownership':False,'owned_worker_group_members':[],
                'physical_supervisor_absent':True,'observed_supervisor_state':'ABSENT'},
            'supervisor_observed_closure':None,'dispatch_attempt_value':{'verified_launcher_start':True,'uncertain_launcher_start':False},
            'corpus_reservations':{'engineering':None},'corpus_reservation_count':1}
    def complete():
        ev=evidence(*fixture());actual=pub.aggregate_actual(ev)
        req(actual['worker_attempts']==actual['completed_worker_batches']==actual['corpus_batches_attempted']==actual['completed_corpus_batches']==1
            and actual['engineering']['NLI_forward_calls_completed']==48 and actual['engineering']['native_queries_completed']==12)
    test('full_capture_preserves_exact48_12_and_one_worker_corpus',complete)
    def partial():
        raw,execution=fixture('raw.partial.json');raw['counters']['corpus_batches_completed']=0;execution['raw_operation_counters']=copy.deepcopy(raw['counters'])
        actual=pub.aggregate_actual(evidence(raw,execution))
        req(actual['corpus_batches_attempted']is None and actual['completed_corpus_batches']is None
            and actual['known_corpus_batches_attempted_at_last_capture']==1 and actual['known_corpus_batches_completed_at_last_capture']==0
            and actual['engineering']['operation_counts_complete']is False and actual['engineering']['backend_execution_since_checkpoint']=='UNKNOWN')
    test('partial_capture_retains_lower_bound_not_completed_or_fabricated_zero',partial)
    def unknown():
        actual=pub.aggregate_actual(evidence(*fixture('UNKNOWN')))
        req(actual['worker_attempts']==1 and actual['completed_worker_batches']==0 and actual['corpus_batches_attempted']is None
            and actual['completed_corpus_batches']is None and actual['errors']is None)
    test('unknown_raw_preserves_unknown_totals_and_errors',unknown)
    def mutated(which,key,value):
        raw,execution=fixture();(raw if which=='raw'else execution)[key]=value;rejects(lambda:pub.derive_actual(raw,execution))
    for key,value in [('CPU_affinity',[0,2]),('owned_live_processes_closed',False),('operation_counts_complete',False),
                      ('allowed_further_phase_workers',1),('raw_operation_counters',{}),('worker_attempts_reserved',2)]:
        test('reject_projection_'+key,lambda key=key,value=value:mutated('execution',key,value))
    def error_identity():
        raw,execution=fixture();error={'stage':'fixture','reason':'retained'};raw['errors']=[error];execution['launcher_error']=copy.deepcopy(error)
        req(pub.derive_actual(raw,execution)['errors']==1)
    test('identical_retained_error_not_double_counted',error_identity)
    def cumulative():
        value=pub.cumulative_counts(pub.aggregate_actual(evidence(*fixture())));req(value['corpus_attempts']==32
            and value['completed_corpus_batches']==30 and value['bounded_native_process_attempts']==36)
    test('exact_prior31_29_35_plus_actual_one',cumulative)
    return {'schema_version':1,'epoch':35,'checks_passed':True,'checks':checks,'projection_source':pins,
        'counts':{'tests':len(checks),'actual_scientific_evaluate_or_bind':0,'actual_execution_receipts_read':0,
            'model_native_tokenizer_imports_or_calls':0,'authored_or_benchmark_oracle_traversals':0},
        'scope':'Authored metadata values passed through real stdlib receipt projection. Physical closure is fixture metadata, not a measured or actual process-closure claim.'}
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--project',required=True);p.add_argument('--output',required=True);a=p.parse_args()
    report=run(Path(a.project).resolve());write_new(a.output,report);print(json.dumps({'checks_passed':True,'tests':len(report['checks'])}))
