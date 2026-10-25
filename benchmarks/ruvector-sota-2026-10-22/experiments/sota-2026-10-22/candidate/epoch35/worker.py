"""One CPU2/600 engineering-only worker;12 authored inputs,48 raw neural readouts."""
import argparse
from datetime import datetime,timezone
import importlib.util
import json
import math
import os
from pathlib import Path
import resource
import signal
import subprocess
import sys
import tempfile
import time
import traceback
HERE=Path(__file__).resolve().parent
_spec=importlib.util.spec_from_file_location('e35_runtime',HERE/'runtime/common.py')
C=importlib.util.module_from_spec(_spec);_spec.loader.exec_module(C)
A=C.load_module('e35_algorithm',HERE/'algorithm.py')

def status(pid):
    result, observed, races = {}, [], []
    try:
        for line in Path('/proc/' + str(pid) + '/status').read_text().splitlines():
            if line.startswith(('VmRSS:', 'VmHWM:')):
                key, value, _unit = line.split()
                result[key.rstrip(':') + '_bytes'] = int(value) * 1024
            elif line.startswith(('Threads:', 'Cpus_allowed_list:', 'NoNewPrivs:', 'Seccomp:', 'Seccomp_filters:')):
                key, value = line.split(':', 1)
                result[key] = value.strip()
        tasks = list((Path('/proc') / str(pid) / 'task').iterdir())
    except FileNotFoundError:
        tasks = []
    for task in sorted(tasks, key=lambda path: int(path.name)):
        try:
            for line in (task / 'status').read_text().splitlines():
                if line.startswith('Cpus_allowed_list:'):
                    literal = line.split(':', 1)[1].strip()
                    cpus = set()
                    for item in literal.split(','):
                        ends = item.split('-')
                        cpus.update(range(int(ends[0]), int(ends[-1]) + 1))
                    observed.append({'tid': int(task.name), 'Cpus_allowed_list': literal,
                        'observed_affinity_within_CPU0_1': bool(cpus) and cpus <= {0, 1}})
                    break
        except FileNotFoundError:
            races.append(int(task.name))
    result.update(observed_thread_affinities=observed, thread_status_disappearance_races=races,
        observability_scope='Read-only current tasks; helper thread count need not equal2.')
    if any(not row['observed_affinity_within_CPU0_1'] for row in observed):
        error = RuntimeError('Observed thread outside fixed kernel CPU0,1 policy')
        error.observed_process_status = result
        raise error
    return result

def checkpoint(raw, out):
    prior = signal.pthread_sigmask(signal.SIG_BLOCK, {signal.SIGALRM, signal.SIGTERM})
    try:
        pending = out / 'raw.partial.pending.json'
        with pending.open('x', encoding='utf-8') as target:
            json.dump(raw, target, ensure_ascii=False, separators=(',', ':'), allow_nan=False)
            target.write('\n')
            target.flush()
            os.fsync(target.fileno())
        os.replace(pending, out / 'raw.partial.json')
        directory = os.open(out, os.O_RDONLY | os.O_DIRECTORY)
        try:
            os.fsync(directory)
        finally:
            os.close(directory)
    finally:
        signal.pthread_sigmask(signal.SIG_SETMASK, prior)


def native_capture_observation(raw):
    """Closure alone cannot make unreturned native operations observable."""
    def exact_ref(row):
        return (isinstance(row,dict) and set(row)=={'path','bytes','sha256'}
            and isinstance(row['path'],str) and type(row['bytes'])is int and row['bytes']>=0
            and isinstance(row['sha256'],str) and len(row['sha256'])==64
            and all(c in '0123456789abcdef' for c in row['sha256']))
    counters=raw.get('counters') if isinstance(raw.get('counters'),dict) else {}
    attempted=counters.get('native_helper_starts_attempted')
    corpora=raw.get('corpora') if isinstance(raw.get('corpora'),dict) else {}
    helpers=[]
    for role in ('engineering',):
        corpus=corpora.get(role)
        if not isinstance(corpus,dict):
            continue
        if corpus.get('native_helper_popen_attempted') is True:
            helpers.append({'role':role,
                'returned_handle':corpus.get('native_helper_returned_handle'),
                'known_child_closed':corpus.get('native_child_closed'),
                'child_exit_code':corpus.get('native_child_exit_code'),
                'final_counter_receipt_validated':corpus.get('native_counter_capture_complete'),
                'final_result':corpus.get('native_result'),
                'Node_guard_counter_receipt':corpus.get('validated_Node_guard_counter_receipt')})
    complete=(type(attempted)is int and attempted>=0 and attempted==len(helpers)
        and all(row['returned_handle'] is True and row['known_child_closed'] is True
            and type(row['child_exit_code'])is int and row['child_exit_code']==0 and row['final_counter_receipt_validated'] is True
            and exact_ref(row['final_result']) and exact_ref(row['Node_guard_counter_receipt']) for row in helpers))
    return {'all_attempted_helpers_closed_and_complete':complete,
        'helper_attempt_counter':attempted,'observed_helper_Popen_boundaries':len(helpers),
        'helpers':helpers,'native_backend_counter_totals_complete':complete,
        'backend_execution_since_checkpoint':'NOT_APPLICABLE_FINAL_RAW' if complete else 'UNKNOWN',
        'captured_native_counter_values':{k:v for k,v in counters.items() if k.startswith('native_')},
        'counter_scope':'Complete only with returned handle, known closure and validated final native counter receipt for every attempted helper. Otherwise captured values are checkpoint observations, not complete backend totals. Physical closure later cannot recover unobserved operations.'}


def write_raw_capture(raw,out):
    """An uncertain native start/exit/capture never creates a final raw seal."""
    observation=native_capture_observation(raw)
    raw['native_backend_capture']=observation
    if observation['all_attempted_helpers_closed_and_complete']:
        C.put(out/'raw.json',raw)
        return 'raw.json'
    if (out/'raw.json').exists():
        raise RuntimeError('Uncertain native capture found an unexpected final raw artifact; no overwrite or retry')
    checkpoint(raw,out)
    return 'raw.partial.json'


def file_ref(path):
    return {'path': str(path.relative_to(C.ROOT)), 'bytes': path.stat().st_size, 'sha256': C.sha(path)}


def expected_counters(full=True):
    # Both semantic acceptance outcomes execute exactly the same one48-forward batch.
    table={key:0 for key in C.phase_zero('engineering')}
    for name in ('model_initializations','tokenizer_initializations','BGE_initializations','ORT_sessions'):
        for suffix in ('_attempted','_completed'):table[name+suffix]=1
    for name,value in [('native_helper_starts',1),('native_binary_loads',1),('native_version_calls',1),
            ('native_index_initializations',12),('native_queries',12),('native_len_calls',24),
            ('NLI_forward_calls',48),('pair_tokenizations',48),('NLI_full_pair_tokenizer_calls',48),
            ('NLI_capped_pair_tokenizer_calls',48),('ENGINEERING_forward_calls',48)]:
        for suffix in ('_attempted','_completed'):table[name+suffix]=value
    table.update(NLI_readouts_completed=48,corpus_batches_attempted=1,corpus_batches_completed=1,
        ENGINEERING_input_bank_reads=1,engineering_oracle_reads=1,
        engineering_oracle_expected_labels_accessed=12,engineering_native_predictions_compared=12,
        ENGINEERING_contexts_completed=48)
    return dict(sorted(table.items()))


def loaded_runtime_libraries(lock):
    members=C.read(C.checked(lock['wheel_members_reference_path']));allowed={str(C.VENV/row['path']):row for row in members}
    paths={line.split()[-1] for line in Path('/proc/self/maps').read_text().splitlines() if line.split() and line.split()[-1].startswith('/')}
    observed=[]
    for name in sorted(paths):
        if '.so' not in name or not any(mark in name for mark in ('onnxruntime','numpy','tokenizers','/torch/')):continue
        row=allowed.get(name)
        if row is None or Path(name).stat().st_size!=row['bytes'] or C.sha(name)!=row['sha256']:raise ValueError('Mapped original runtime library differs from pinned external member')
        observed.append({'path':name,'bytes':row['bytes'],'sha256':row['sha256']})
    if not any('onnxruntime_pybind11_state' in row['path'] for row in observed):raise ValueError('CPU ORT binding not observed mapped')
    if not any('/torch/' in row['path'] for row in observed):raise ValueError('CPU Torch library not observed mapped')
    return observed


def node_events(out,role,counters,baseline,fatal=True):
    path=out/(role+'-node-progress.jsonl');rows=[C.read_json_line(line) for line in path.read_text().splitlines()] if path.exists() else []
    if rows:
        for key in ('Node_network_operations_attempted','native_binary_loads_attempted','native_binary_loads_completed'):
            counters[key]=baseline.get(key,0)+rows[-1][key]
    if fatal and counters['Node_network_operations_attempted']:raise RuntimeError('Persistent native network API violation')
    return rows


def run_native(bundle,corpus,raw,args,progress,role):
    counters=raw['counters'];baseline=dict(counters)
    corpus.update(native_helper_popen_attempted=False,native_helper_returned_handle=False,
        native_counter_capture_complete=False)
    source=args.out/(role+'-native-bundle.json');target=args.out/(role+'-native-result.json')
    C.put(source,bundle);corpus['vector_bundle']=file_ref(source)
    reservation=args.out/(role.upper()+'_CORPUS_ATTEMPT_RESERVATION.json')
    C.put(reservation,{'schema_version':1,'epoch':35,'kind':A.KIND,'phase':'engineering','role':role,'plan_sha256':args.expected_plan_sha,
        'corpus_batches_reserved':1,'allowed_further_role_helpers':0,'before_Popen':True,'automatic_retry':False,'at_unix':time.time()})
    directory=os.open(args.out,os.O_RDONLY|os.O_DIRECTORY)
    try:os.fsync(directory)
    finally:os.close(directory)
    raw['corpus_reservations'][role]=file_ref(reservation);corpus['corpus_reservation']=file_ref(reservation)
    counters['corpus_batches_attempted']+=1
    process=identity=None;stdout=stderr=b'';started=time.perf_counter()
    with tempfile.TemporaryDirectory(prefix='e35-'+role+'-native-',dir=C.ROOT.parent) as scratch:
        corpus['native_scratch']={'path':scratch,'outside_public_project':True}
        command=['node','--require='+str(HERE/'runtime/node_guard.cjs'),str(HERE/'native_helper.cjs'),str(source),str(target)]
        env=dict(os.environ,E35_ROLE=role)
        counters['native_helper_starts_attempted']+=1;progress({'event':'NATIVE_HELPER_POPEN_BEFORE','role':role,'argv':command})
        try:
            corpus['native_helper_popen_attempted']=True
            process=subprocess.Popen(command,cwd=scratch,env=env,stdout=subprocess.PIPE,stderr=subprocess.PIPE)
            corpus['native_helper_returned_handle']=True
            counters['native_helper_starts_completed']+=1;identity=C.proc(process.pid)
            if not identity or identity['pgid']!=os.getpgrp() or identity['sid']!=os.getsid(0):raise ValueError('Native helper escaped worker session')
            C.put(args.out/(role+'-native-attempt.json'),{'pid':process.pid,'identity':identity,'argv':command,'role':role,
                'source_sha256':C.sha(HERE/'native_helper.cjs'),'bundle_sha256':C.sha(source),'CPU_policy':'Inherited whole-worker guard, no repeat setaffinity'})
            stdout,stderr=process.communicate(timeout=min(60,C.remaining(args.deadline)))
        except subprocess.TimeoutExpired as error:
            stdout,stderr=error.output or b'',error.stderr or b'';raise
        finally:
            if process is not None and process.poll() is None:
                current=C.proc(process.pid)
                if not identity or not current or current['ticks']!=identity['ticks']:raise RuntimeError('Unproven native child identity for cleanup')
                process.terminate()
                try:stdout,stderr=process.communicate(timeout=3)
                except subprocess.TimeoutExpired:
                    process.kill();stdout,stderr=process.communicate(timeout=1)
            (args.out/(role+'-native.stdout')).write_bytes(stdout);(args.out/(role+'-native.stderr')).write_bytes(stderr)
            corpus['native_child_closed']=(process.poll() is not None) if process is not None else None
            corpus['native_child_exit_code']=process.returncode if process is not None else None
            corpus['Node_guard_events']=node_events(args.out,role,counters,baseline,fatal=False)
            log=args.out/(role+'-native-progress.jsonl')
            if log.exists():
                events=[C.read_json_line(line) for line in log.read_text().splitlines()]
                if events:
                    for key,value in events[-1].items():
                        if key.startswith('native_') and type(value) is int:counters[key]=baseline.get(key,0)+value
            corpus['native_helper_seconds_including_initialization']=time.perf_counter()-started
            corpus['native_scratch']['files_before_owned_cleanup']=[{'path':str(p.relative_to(scratch)),'bytes':p.stat().st_size,'sha256':C.sha(p)} for p in sorted(Path(scratch).rglob('*')) if p.is_file()]
        if process.returncode!=0:
            failure=Path(str(target)+'.failure.json')
            if failure.exists():corpus['native_failure_ref']=file_ref(failure)
            raise RuntimeError('Native role helper failed; literal failure/stdout/stderr retained')
    corpus['native_scratch']['removed_after_child_exit']=not Path(scratch).exists()
    result=C.read(target);corpus['native_result']=file_ref(target)
    if (result.get('epoch')!=35 or result.get('kind')!=A.KIND or result.get('role')!=role or result.get('phase')!='engineering'
            or result.get('native') is not True or result.get('bundle_sha256')!=C.sha(source) or result.get('source_sha256')!=C.sha(HERE/'native_helper.cjs')
            or result.get('native_binary_sha256')!=C.BINARY_SHA or result.get('helper_pid')!=process.pid
            or result.get('package_version')!='0.1.33' or result.get('platform_package_version')!='0.1.31' or result.get('binary_version')!='2.3.0'
            or result.get('compact_schema')!='epoch35-native-context-f32le-v1' or len(result['documents'])!=12 or result.get('errors')!=[]):raise ValueError('Wrong native/source/runtime role receipt')
    if corpus.get('native_child_closed') is not True or process.returncode!=0 or result.get('stage')!='HELPER_COMPLETED':
        raise ValueError('Native final counter receipt requires known successful child closure')
    documents=result['documents'];expected_queries=12
    insertions=hits=0
    for expected_document,actual in zip(bundle['documents'],documents):
        count=1
        if (actual.get('document_id')!=expected_document['document_id']
                or actual.get('initialized_vectors')!=expected_document['vectors']['shape'][0]
                or len(actual.get('queries',[]))!=count
                or [q.get('case_id') for q in actual['queries']]!=[q['id'] for q in expected_document['queries']]):
            raise ValueError('Incomplete native final document/query receipt')
        insertions+=actual['initialized_vectors']
        for query in actual['queries']:
            k=min(40,actual['initialized_vectors'])
            if query.get('requested_k')!=k or len(query.get('ids',[]))!=k or len(query.get('raw_hits',[]))!=k:
                raise ValueError('Incomplete native final hit counter receipt')
            hits+=k
    complete_counters={'native_index_initializations_attempted':len(documents),
        'native_index_initializations_completed':len(documents),
        'native_queries_attempted':expected_queries,'native_queries_completed':expected_queries,
        'native_len_calls_attempted':2*len(documents),'native_len_calls_completed':2*len(documents),
        'native_version_calls_attempted':1,'native_version_calls_completed':1,
        'native_insertions_attempted':insertions,'native_insertions_completed':insertions,
        'native_hit_source_validations':hits}
    if any(type(result.get(k))is not int or result[k]!=v for k,v in complete_counters.items()):
        raise ValueError('Native final operation counter receipt incomplete or invalid')
    for key,value in result.items():
        if key.startswith('native_') and type(value) is int:counters[key]=baseline.get(key,0)+value
    guard_rows=node_events(args.out,role,counters,baseline)
    if (not guard_rows or any(row.get('pid')!=process.pid for row in guard_rows)
            or guard_rows[-1].get('event')!='NATIVE_BINARY_LOAD_AFTER'
            or guard_rows[-1].get('phase')!='engineering' or guard_rows[-1].get('role')!=role
            or any(type(guard_rows[-1].get(key))is not int or guard_rows[-1][key]!=value
                for key,value in {'Node_network_operations_attempted':0,
                    'native_binary_loads_attempted':1,'native_binary_loads_completed':1}.items())):
        raise ValueError('Native final capture lacks complete source-bound Node guard counters')
    corpus['Node_guard_events']=guard_rows
    corpus['validated_Node_guard_counter_receipt']=file_ref(args.out/(role+'-node-progress.jsonl'))
    corpus['native_counter_capture_complete']=True
    corpus['validated_final_native_counters']=complete_counters
    counters['corpus_batches_completed']+=1;progress({'event':'NATIVE_ROLE_CORPUS_CLOSED','role':role})
    return result


def prepare_role(raw,plan,args,progress,role,model,engine,evidence,codec,bge):
    if role!='engineering':raise ValueError('All nonengineering roles are frozen empty')
    counters=raw['counters'];file=C.checked(plan[role+'_inputs_path'])
    if C.sha(file)!=plan[role+'_inputs_sha256']:raise ValueError('Changed fixed inputs-only role source')
    counters[role.upper()+'_input_bank_reads']+=1
    records=evidence.validate_inputs(C.read(file),role)
    corpus={'role':role,'input_bank':file_ref(file),'cases':[],'documents':{},'native_child_closed':None}
    raw['corpora'][role]=corpus
    tokenizer=evidence.PairTokenizer(model.tokenizer,counters)
    context,documents,bundle,receipt=engine.prepare(C,records,tokenizer,counters,progress,codec,bge,role)
    bundle['phase']='engineering';corpus['documents']=documents
    native=run_native(bundle,corpus,raw,args,progress,role)
    corpus['cases']=engine.pack_all(records,documents,native,role,context,evidence,tokenizer,counters,progress)
    return corpus,records


def score_role(raw,corpus,model,args,progress,offline,role):
    proof=C.load_module('e35_proof',HERE/'proof.py')
    for case in corpus['cases']:
        for arm_name in A.ARMS:
            C.remaining(args.deadline);offline.assert_clean()
            arm=case['arms'][arm_name];receipt={};arm['reader']=receipt
            model.score(arm['premise'],case['hypothesis'],receipt,role)
            if receipt['pair_tokens']!=arm['joint_pair_tokens']:raise ValueError('Reader/packed full pair budget differs')
            decision_started=time.perf_counter()
            arm['decision']=proof.decide(case['document'],arm['premise'],case['hypothesis'],arm['context']['selected_source_spans'],receipt,enabled=False)
            arm['decision_seconds']=time.perf_counter()-decision_started
            arm['semantic_decision_override']=arm['decision']['semantic_decision_override']
            offline.assert_clean()
    corpus['model_state_unchanged']=model.unchanged()


def engineering_gate(raw,plan,progress):
    counters=raw['counters']
    if any(counters.get(k)!=48 for k in ('ENGINEERING_forward_calls_attempted','ENGINEERING_forward_calls_completed','NLI_forward_calls_attempted','NLI_forward_calls_completed','NLI_readouts_completed')) or counters.get('DEV_forward_calls_completed')!=0:raise ValueError('New authored engineering oracle requires all48 raw neural readouts before the single label join')
    if raw['corpora']['engineering'].get('native_child_closed') is not True:raise ValueError('Engineering native helper must be closed before oracle')
    file=C.checked(plan['engineering_oracle_path'])
    if C.sha(file)!=plan['engineering_oracle_sha256']:raise ValueError('Changed authored engineering oracle')
    counters['engineering_oracle_reads']+=1;oracle=C.read(file)
    if set(oracle)!={'schema_version','epoch','role','expected_labels'} or oracle['schema_version']!=1 or oracle['epoch']!=35 or oracle['role']!='engineering' or set(oracle['expected_labels'])!=set(A.ENG_CASE_IDS):raise ValueError('Wrong authored engineering oracle')
    expected=oracle['expected_labels']
    rows=raw['corpora']['engineering']['cases']
    if len(rows)!=12 or tuple(row['id'] for row in rows)!=A.ENG_CASE_IDS:raise ValueError('Incomplete ordered engineering corpus')
    joined={};scores={arm:{'brier_terms':[],'nll_terms':[],'gold_probabilities':[]} for arm in A.ARMS}
    correct={arm:0 for arm in A.ARMS};by_class={label:{'correct':0,'n':0} for label in A.LABELS_CANONICAL}
    for row in rows:
        label=expected[row['id']];counters['engineering_oracle_expected_labels_accessed']+=1
        if label not in A.LABELS_CANONICAL:raise ValueError('Unknown engineering oracle label')
        joined[row['id']]=label
        for arm_name in A.ARMS:
            arm=row['arms'][arm_name];reader=arm['reader']
            if (not reader or reader['actual_logits_shape']!=[1,3] or reader['pair_tokens']!=arm['joint_pair_tokens']
                    or reader['full_pair_tokens']!=reader['pair_tokens'] or reader['max_pair_tokens']!=512 or reader['hidden_truncation'] is not False
                    or reader['temperature']!=1.0 or reader['calibrated'] is not False or reader['semantic_decision_override'] is not False
                    or len(reader['probabilities_E_C_N'])!=3 or any(not 0<=p<=1 for p in reader['probabilities_E_C_N'])
                    or abs(sum(reader['probabilities_E_C_N'])-1)>1e-12):raise ValueError('Engineering source-pair/probability integrity failed')
            if not arm['context']['source_provenance']['selected_source_provenance'] or arm['context']['source_provenance']['semantic_decision_override'] is not False:raise ValueError('Engineering source/numeric provenance missing')
            decision=arm['decision']
            if decision is None or decision['raw_probabilities_E_C_N']!=reader['probabilities_E_C_N'] or decision['raw_typed_argmax']!=reader['native_typed_argmax']:raise ValueError('Raw/final proof readout attribution differs')
            if (decision['certificate'] is not None or decision['fallback_reason']!='proof_disabled_for_ALL_ROLES'
                    or decision['final_probabilities_E_C_N']!=reader['probabilities_E_C_N']
                    or decision['final_typed_argmax']!=reader['native_typed_argmax']
                    or decision['semantic_decision_override'] is not False or arm['semantic_decision_override'] is not False):
                raise ValueError('ProofdisabledALLroles requires unchanged rawT1 neural readout')
            if decision['policy']!='proof-disabled-all-roles-v1' or len(decision['final_probabilities_E_C_N'])!=3 or any(type(x)not in(int,float) or not 0<=x<=1 for x in decision['final_probabilities_E_C_N']) or abs(sum(decision['final_probabilities_E_C_N'])-1)>1e-12:raise ValueError('Proof decision distribution invalid')
            if arm['semantic_decision_override'] is not (decision['certificate'] is not None) or decision['semantic_decision_override'] is not arm['semantic_decision_override']:raise ValueError('Proof override disclosure inconsistent')
            winner=reader['native_typed_argmax'] if decision['certificate'] is None else decision['certificate']['conclusion']
            if decision['final_typed_argmax']!=winner or decision['final_probabilities_E_C_N'][A.LABELS_CANONICAL.index(winner)]!=max(decision['final_probabilities_E_C_N']):raise ValueError('Final argmax/probability disagreement')
            if decision['certificate'] is None and (decision['final_probabilities_E_C_N']!=reader['probabilities_E_C_N'] or decision['final_typed_argmax']!=reader['native_typed_argmax']):raise ValueError('Fallback must preserve raw neural output')
            probabilities=decision['final_probabilities_E_C_N'];gold=A.LABELS_CANONICAL.index(label)
            scores[arm_name]['brier_terms'].append(math.fsum((p-float(i==gold))**2 for i,p in enumerate(probabilities)))
            scores[arm_name]['nll_terms'].append(-math.log(max(probabilities[gold],1e-12)))
            scores[arm_name]['gold_probabilities'].append(probabilities[gold])
            correct[arm_name]+=int(decision['final_typed_argmax']==label)
        counters['engineering_native_predictions_compared']+=1
        by_class[label]['n']+=1;by_class[label]['correct']+=int(row['arms']['actual_native']['decision']['final_typed_argmax']==label)
    if any(v['n']!=4 for v in by_class.values()):raise ValueError('Frozen engineering requires four of each exact type')
    proper={arm:{'brier':math.fsum(v['brier_terms'])/12,'nll':math.fsum(v['nll_terms'])/12,
        'NLL_clipped_1e-12':math.fsum(v['nll_terms'])/12,'NLL_clip_count':sum(p<1e-12 for p in v['gold_probabilities']),
        'unclipped_NLL_finite':all(p>0 for p in v['gold_probabilities'])} for arm,v in scores.items()}
    nonincrease={arm:{metric:proper['actual_native'][metric]<=proper[arm][metric]+1e-12 for metric in ('brier','nll')}
        for arm in A.ARMS if arm!='actual_native'}
    passed=(correct['actual_native']==12 and all(row=={'correct':4,'n':4} for row in by_class.values())
        and all(all(v.values()) for v in nonincrease.values()))
    gate={'passed':passed,'native_correct':correct['actual_native'],'n':12,'by_class':by_class,'correct_by_arm':correct,
        'proper_scores_by_arm':proper,'proper_score_nonincrease_against_controls':nonincrease,
        'expected_labels':joined,'oracle_label_join_count':12,'oracle_join_after_all48_readouts':True,
        'all48_predictions_completed_before_oracle_read':True,'all48_finite_true_pair_source_numeric_integrity':True,
        'rule':'Authored engineering admission only: primary12/12, four correct per class and Brier/NLL nonincrease against each of three same-model controls. Proof disabled; rawT1 unchanged. No benchmark/generalization claim.',
        'oracle':file_ref(file),'DEV_bank_read_before_gate':False,'benchmark_generalization_claim':False}
    raw['engineering_gate']=gate;progress({'event':'ENGINEERING_GATE_CLOSED','gate':gate})
    return passed


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--phase',choices=('engineering',),required=True)
    for key in ('plan','admission','out'):parser.add_argument('--'+key,type=Path,required=True)
    parser.add_argument('--expected-plan-sha',required=True);parser.add_argument('--deadline',type=float,required=True);args=parser.parse_args()
    if args.out.absolute()!=C.STUDY/'runs/engineering':raise ValueError('Wrong exact worker output')
    C.no_symlink(args.out);started=time.monotonic();counterkeys=set(expected_counters(True))|set(C.phase_zero('engineering'))
    raw={'schema_version':1,'epoch':35,'kind':A.KIND,'phase':'engineering','source_checkpoint':C.SOURCE,'plan_sha256':args.expected_plan_sha,
        'status':'INITIALIZING','worker_pid':os.getpid(),'worker_identity':C.proc(os.getpid()),'corpora':{'engineering':None},
        'corpus_reservations':{'engineering':None},'engineering_gate':None,'errors':[],
        'data_roles':{'train':[],'dev':[],'calibration':[],'confirmation':[]},'confirmation':[],'calibration':[],'engineering_only':True,'used_confirmation_identities':[],
        'benchmark_accepted':False,'champion_promoted':False,'benchmark_accuracy':None,'proper_scores':None,'training_lineage_complete':False,
        'NLI_scope':'New CC0 numeric/source-scope admission12 only. All benchmark TRAIN/DEV/calibration/CONF roles empty. Unchanged E34 primary lexical-anchor/native-distinct-group-complement ranking versus original native/lexical/positional rankings, under the SAME new mandatory2completegroups+optionaldefinitions512jointtokenpacker. Allfour originalunexpandedqueries and Moritz E,N,C head; proofdisabledALLroles so finalequalsrawT1. Native_original controls ranking underunchangedE34packer, notlegacyE33contexts. No CONF/promotion/generalization claim.',
        'counters':{**dict.fromkeys(counterkeys,0),'BGE_forward_calls_attempted':0,'BGE_forward_calls_completed':0,'BGE_texts_attempted':0,
            'BGE_texts_completed':0,'BGE_forward_seconds':0.0,'automatically_extracted_units':0,'native_insertions_attempted':0,
            'native_insertions_completed':0,'native_hit_source_validations':0,'context_tokenizer_calls_attempted':0,'context_tokenizer_calls_completed':0,
            'context_pair_tokenizer_calls_attempted':0,'context_pair_tokenizer_calls_completed':0,'context_single_tokenizer_calls_attempted':0,
            'context_single_tokenizer_calls_completed':0,'Python_literal_loopback_capability_binds_allowed':0}}
    stream=(args.out/'progress.jsonl').open('xb')
    def progress(event):
        row={'at_unix':time.time(),'elapsed_seconds':time.monotonic()-started,'event':event,'counters':dict(raw['counters']),'process':status(os.getpid())}
        stream.write((json.dumps(row,ensure_ascii=False,allow_nan=False)+'\n').encode());stream.flush();os.fsync(stream.fileno());checkpoint(raw,args.out)
    offline=C.load_module('e35_offline',HERE/'runtime/network_guard.py').OfflineGuard(raw['counters'],progress).install()
    def stop(signum,frame):raise TimeoutError('Bounded E35 stop signal '+str(signum))
    signal.signal(signal.SIGTERM,stop);signal.signal(signal.SIGALRM,stop);code=0
    try:
        signal.setitimer(signal.ITIMER_REAL,max(.001,C.remaining(args.deadline)-7))
        cpu=status(os.getpid())
        if os.sched_getaffinity(0)!={0,1} or cpu.get('NoNewPrivs')!='1' or cpu.get('Seccomp')!='2':raise ValueError('Whole worker CPU guard required before ML')
        if args.plan.absolute()!=C.STUDY/'plan.json' or C.sha(args.plan)!=args.expected_plan_sha:raise ValueError('Unknown source plan')
        provisional=C.read(args.plan);admission,owner=C.admission(args.admission,provisional,args.expected_plan_sha,'engineering')
        plan=C.verify_plan(args.plan,args.expected_plan_sha,'engineering');runtime=C.verify_runtime(plan)
        if plan['expected_operation_counters']['engineering']!=expected_counters(True) or plan['engineering_rejected_operation_counters']['engineering']!=expected_counters(False):raise ValueError('Different frozen conditional work counts')
        attempt_path=args.out/'attempt.json'
        while not attempt_path.exists():
            C.remaining(args.deadline)
            if time.monotonic()-started>15:raise RuntimeError('Worker start receipt missing')
            time.sleep(.01)
        attempt,current=C.read(attempt_path),C.proc(os.getpid())
        if attempt.get('pid')!=os.getpid() or attempt.get('pgid')!=os.getpid() or attempt.get('sid')!=os.getpid() or attempt.get('startticks')!=current['ticks'] or current['pgid']!=os.getpid() or current['sid']!=os.getpid():raise ValueError('Wrong worker actual identity')
        cpu_file=args.out/'worker-cpu-preexec.json';raw.update(admission=admission,owner_lock=owner,source_freeze_sha256=plan['source_freeze_sha256'],
            worker_cpu_guard_preexec=C.read(cpu_file),worker_cpu_guard_preexec_artifact=file_ref(cpu_file),CPU_policy_before_model_import=cpu)
        progress({'event':'ALL_SOURCE_MODEL_RUNTIME_CPU_GATES_BEFORE_ML'})
        evidence=C.load_module('e35_evidence',HERE/'evidence.py');codec=C.load_module('e35_vector_codec',HERE/'vector_codec.py');engine=C.load_module('e35_context',HERE/'context_engine.py')
        module=C.load_module('e35_trained_NLI_reader',HERE/'model.py');model=module.FrozenMoritzProofReader(C.MODEL,raw['counters'],progress)
        raw['model_initialization']=model.runtime_checks;offline.assert_clean();bge=engine.initialize(C,raw['counters'],progress);raw['BGE']=bge[2]
        raw['loaded_runtime_libraries']=loaded_runtime_libraries(runtime)
        corpus,_=prepare_role(raw,plan,args,progress,'engineering',model,engine,evidence,codec,bge)
        score_role(raw,corpus,model,args,progress,offline,'engineering')
        raw['status']='ENGINEERING_ADMISSION_PASSED' if engineering_gate(raw,plan,progress) else 'ENGINEERING_ADMISSION_FAILED'
        raw['model_state_unchanged']=model.unchanged();raw['native_child_closed']=all(v is None or v.get('native_child_closed') is True for v in raw['corpora'].values())
        C.verify_plan(args.plan,args.expected_plan_sha,'engineering');C.verify_runtime(plan);C.owner_lock(admission);C.remaining(args.deadline);offline.assert_clean()
        expected=expected_counters()
        if any(raw['counters'][k]!=v for k,v in expected.items()) or any(raw['counters'][k] for k in C.phase_zero('engineering')):raise ValueError('Engineering work/forbidden count closure failed')
    except BaseException as error:
        raw['status']='FAILED_ENGINEERING';raw['errors'].append({'type':type(error).__name__,'message':str(error),'traceback':traceback.format_exc()});code=2
        if hasattr(error,'observed_process_status'):raw['CPU_affinity_violation_snapshot']=error.observed_process_status
    finally:
        signal.signal(signal.SIGALRM,signal.SIG_IGN);signal.signal(signal.SIGTERM,signal.SIG_IGN);signal.setitimer(signal.ITIMER_REAL,0)
        own,child=resource.getrusage(resource.RUSAGE_SELF),resource.getrusage(resource.RUSAGE_CHILDREN)
        raw.update(completed_at=datetime.now(timezone.utc).isoformat(),wall_seconds_including_initialization_cleanup=time.monotonic()-started,
            Python_network_events=offline.events,Python_network_violations=offline.violations,
            resources={'CPU_affinity':sorted(os.sched_getaffinity(0)),'worker':status(os.getpid()),'worker_user_seconds':own.ru_utime,
                'worker_system_seconds':own.ru_stime,'worker_peak_RSS_bytes':own.ru_maxrss*1024,'child_user_seconds':child.ru_utime,
                'child_system_seconds':child.ru_stime,'largest_child_peak_RSS_bytes':child.ru_maxrss*1024,
                'memory_scope':'Separate high-water observations, not simultaneous summedRSS.'})
        raw['native_backend_capture']=native_capture_observation(raw)
        try:progress({'event':'WORKER_FINAL','status':raw['status'],'errors':raw['errors']})
        except BaseException as error:
            raw['status']='FAILED_ENGINEERING';raw['errors'].append({'stage':'final_checkpoint','type':type(error).__name__,'message':str(error)});code=2
        pending=args.out/'raw.partial.pending.json'
        if pending.is_file():raw['leftover_partial_checkpoint']={**file_ref(pending),'retained_without_overwrite':True}
        write_raw_capture(raw,args.out);stream.close()
    return code


if __name__=='__main__':raise SystemExit(main())
