"""One CPU2/600 single-reader worker;12 authored inputs,36 actual neural readouts,60 derived forecasts."""
import argparse
import gc
import weakref
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
_spec=importlib.util.spec_from_file_location('e37_runtime',HERE/'runtime/common.py')
C=importlib.util.module_from_spec(_spec);_spec.loader.exec_module(C)
A=C.load_module('e37_algorithm',HERE/'algorithm.py')

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
    # Same physical work for passing or rejected engineering outcomes; no retry.
    table={key:0 for key in C.phase_zero('engineering')}
    for name,value in [('model_initializations',1),('tokenizer_initializations',1),('BGE_initializations',1),('ORT_sessions',1),
            ('native_helper_starts',1),('native_binary_loads',1),('native_version_calls',1),
            ('native_index_initializations',12),('native_queries',12),('native_len_calls',24),
            ('NLI_forward_calls',36),('pair_tokenizations',36),('NLI_full_pair_tokenizer_calls',36),
            ('NLI_capped_pair_tokenizer_calls',36),('ENGINEERING_forward_calls',36),('model_unloads',1),
            ('source_analysis_calls',48),('certificate_decisions',36)]:
        for suffix in ('_attempted','_completed'):table[name+suffix]=value
    for name,value in [('model_initializations',1),('tokenizer_initializations',1),('forward_calls',36),('model_unloads',1)]:
        for suffix in ('_attempted','_completed'):table['xxlarge_'+name+suffix]=value
    table.update(xxlarge_readouts_completed=36,NLI_readouts_completed=36,derived_forecasts_completed=60,
        corpus_batches_attempted=1,corpus_batches_completed=1,ENGINEERING_input_bank_reads=1,
        engineering_oracle_reads=1,engineering_oracle_expected_labels_accessed=12,engineering_native_predictions_compared=12,
        ENGINEERING_contexts_completed=36,full_source_contexts_completed=12,coverage_contexts_completed=24,
        native_complete_unitset_cases_verified=12,sequential_model_lifecycles_completed=1,readout_reuse_receipts_completed=60)
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
    C.put(reservation,{'schema_version':1,'epoch':37,'kind':A.KIND,'phase':'engineering','role':role,'plan_sha256':args.expected_plan_sha,
        'corpus_batches_reserved':1,'allowed_further_role_helpers':0,'before_Popen':True,'automatic_retry':False,'at_unix':time.time()})
    directory=os.open(args.out,os.O_RDONLY|os.O_DIRECTORY)
    try:os.fsync(directory)
    finally:os.close(directory)
    raw['corpus_reservations'][role]=file_ref(reservation);corpus['corpus_reservation']=file_ref(reservation)
    counters['corpus_batches_attempted']+=1
    process=identity=None;stdout=stderr=b'';started=time.perf_counter()
    with tempfile.TemporaryDirectory(prefix='e37-'+role+'-native-',dir=C.ROOT.parent) as scratch:
        corpus['native_scratch']={'path':scratch,'outside_public_project':True}
        command=['node','--require='+str(HERE/'runtime/node_guard.cjs'),str(HERE/'native_helper.cjs'),str(source),str(target)]
        env=dict(os.environ,E37_ROLE=role)
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
    if (result.get('epoch')!=37 or result.get('kind')!=A.KIND or result.get('role')!=role or result.get('phase')!='engineering'
            or result.get('native') is not True or result.get('bundle_sha256')!=C.sha(source) or result.get('source_sha256')!=C.sha(HERE/'native_helper.cjs')
            or result.get('native_binary_sha256')!=C.BINARY_SHA or result.get('helper_pid')!=process.pid
            or result.get('package_version')!='0.1.33' or result.get('platform_package_version')!='0.1.31' or result.get('binary_version')!='2.3.0'
            or result.get('compact_schema')!='epoch37-native-context-f32le-v1' or len(result['documents'])!=12 or result.get('errors')!=[]):raise ValueError('Wrong native/source/runtime role receipt')
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



def prepare_shared_role(raw,plan,args,progress,reader,engine,evidence,codec):
    counters=raw['counters'];file=C.checked(plan['engineering_inputs_path'])
    if C.sha(file)!=plan['engineering_inputs_sha256']:raise ValueError('Changed fixed label-free inputs')
    counters['ENGINEERING_input_bank_reads']+=1;records=evidence.validate_inputs(C.read(file),'engineering')
    corpus={'role':'engineering','input_bank':file_ref(file),'cases':[],'documents':{},'native_child_closed':None,
        'model_states_unchanged':{},'shared_partition_model':'xxlarge'}
    raw['corpora']['engineering']=corpus
    pair=evidence.PairTokenizer(reader.tokenizer,counters)
    bge=engine.initialize(C,counters,progress);raw['BGE']=bge[3]
    raw['loaded_runtime_libraries']=loaded_runtime_libraries(C.read(C.checked(plan['runtime_assets_lock_path'])))
    context,documents,bundle,_=engine.prepare(C,records,pair,counters,progress,codec,bge,'engineering')
    bundle['phase']='engineering';corpus['documents']=documents
    native=run_native(bundle,corpus,raw,args,progress,'engineering')
    corpus['cases']=engine.initialize_cases(records,documents,native,evidence,counters)
    return corpus,records,context


def score_model_role(raw,corpus,reader,args,progress,offline,tag):
    if tag!='xxlarge':raise ValueError('Single exact original reader only')
    proof=C.load_module('e37_source_proof',HERE/'proof.py');counters=raw['counters']
    for case in corpus['cases']:
        for name in A.RAW_CONTEXTS:
            C.remaining(args.deadline);offline.assert_clean();physical=case['readouts'][name]
            receipt={};physical['reader']=receipt;reader.score(physical['premise'],case['hypothesis'],receipt,'engineering')
            receipt['model_tag']=tag;receipt['native_label_order']=list(A.NATIVE_LABELS[tag]);receipt['canonical_E_C_N_from_raw']=[2,0,1]
            if receipt['raw_logits']!=receipt['raw_logits_C_N_E']or receipt['probabilities_native_order']!=receipt['probabilities_C_N_E']:
                raise ValueError('Immutable original C,N,E aliases differ')
            receipt['model_repository']=A.MODEL_REPOSITORIES[tag];receipt['model_revision']=A.MODEL_REVISIONS[tag]
            if receipt['pair_tokens']!=physical['joint_pair_tokens']or receipt['model_weights_sha256']!=A.MODEL_WEIGHT_SHA[tag]:
                raise ValueError('Original reader/true-pair source identity differs')
        for arm_name in A.ARMS:
            name=A.READOUT_REUSE_MAP[arm_name];physical=case['readouts'][name];receipt=physical['reader']
            before=json.dumps(receipt,sort_keys=True,separators=(',',':'),allow_nan=False);started=time.perf_counter()
            if arm_name.endswith('_verified'):
                counters['certificate_decisions_attempted']+=1;counters['source_analysis_calls_attempted']+=1
                decision=proof.decide(case['document'],physical['premise'],case['hypothesis'],physical['context']['selected_source_spans'],receipt)
                counters['source_analysis_calls_completed']+=1;counters['certificate_decisions_completed']+=1
            else:decision=proof.raw_decision(receipt)
            # Stable shifted log-softmax retains unbounded NLL even when exp underflows.
            native=receipt['raw_logits_C_N_E'];peak=max(native);shifted=[x-peak for x in native]
            logsum=math.log(math.fsum(math.exp(x)for x in shifted));native_lp=[x-logsum for x in shifted]
            canonical_lp=[native_lp[i]for i in (2,0,1)]
            decision['raw_log_probabilities_E_C_N']=canonical_lp
            decision['final_log_probabilities_E_C_N']=[canonical_lp[i]for i in decision['permutation']]
            decision['NLL_policy']='STABLE_SHIFTED_SOURCE_LOGSOFTMAX_THEN_EXACT_FINAL_PERMUTATION'
            after=json.dumps(receipt,sort_keys=True,separators=(',',':'),allow_nan=False)
            if before!=after:raise ValueError('Derived forecast mutated immutable physical raw readout')
            case['arms'][arm_name]={'model_tag':tag,'measured_context':name,'neural_readout_ref':physical['readout_id'],
                'reader':receipt,'premise':physical['premise'],'context':physical['context'],'joint_pair_tokens':physical['joint_pair_tokens'],
                'context_seconds':physical['context_seconds'],'native_query_seconds':physical['native_query_seconds'],
                'decision':decision,'decision_seconds':time.perf_counter()-started,'extra_neural_readouts':0,
                'semantic_decision_override':decision['semantic_decision_override'],
                'readout_reuse_receipt':{'actual_readout_id':physical['readout_id'],'raw_reader_canonical_sha256':C.text_sha(before),
                    'physical_reader_unchanged':True,'derived_forecast_did_not_call_model':True}}
            counters['derived_forecasts_completed']+=1;counters['readout_reuse_receipts_completed']+=1
            offline.assert_clean();progress({'event':'DERIVED_FORECAST_COMPLETED','id':case['id'],'arm':arm_name,'readout_ref':physical['readout_id']})


def engineering_gate(raw,plan,progress,lifecycle):
    counters=raw['counters'];corpus=raw['corpora']['engineering']
    if any(counters.get(k)!=36 for k in('ENGINEERING_forward_calls_attempted','ENGINEERING_forward_calls_completed',
            'NLI_forward_calls_attempted','NLI_forward_calls_completed','NLI_readouts_completed'))or counters.get('derived_forecasts_completed')!=60:
        raise ValueError('All36 actual neural readouts and60 derived forecasts required before oracle')
    if (corpus.get('native_child_closed')is not True or counters['sequential_model_lifecycles_completed']!=1
            or raw.get('models_sequentially_unloaded')is not True or set(raw['model_states_unchanged'])!={'xxlarge'}):
        raise ValueError('Single model/tokenizer and native child must close before labels')
    lifecycle(None,'ALL_MODEL_PHASES_CLOSED_BEFORE_ORACLE',unloaded_profiles=list(A.MODEL_ORDER))
    file=C.checked(plan['engineering_oracle_path'])
    if C.sha(file)!=plan['engineering_oracle_sha256']:raise ValueError('Changed authored oracle')
    lifecycle(None,'ENGINEERING_ORACLE_JOIN_BEFORE',unloaded_profiles=list(A.MODEL_ORDER))
    counters['engineering_oracle_reads']+=1;oracle=C.read(file)
    if (set(oracle)!={'schema_version','epoch','expected_labels'}or oracle['schema_version']!=1
            or oracle['epoch']!=37 or set(oracle['expected_labels'])!=set(A.ENG_CASE_IDS)):
        raise ValueError('Wrong exact12case authored oracle')
    rows=corpus['cases']
    if len(rows)!=12 or tuple(r['id']for r in rows)!=A.ENG_CASE_IDS:raise ValueError('Incomplete ordered12case corpus')
    joined={};terms={a:{'brier':[],'nll':[],'clipped_nll':[],'gold_p':[],'latencies':[]}for a in A.ARMS}
    correct={a:0 for a in A.ARMS};by_class={l:{'correct':0,'n':0}for l in A.LABELS_CANONICAL}
    for row in rows:
        label=oracle['expected_labels'][row['id']];counters['engineering_oracle_expected_labels_accessed']+=1
        if label not in A.LABELS_CANONICAL:raise ValueError('Invalid authored label')
        joined[row['id']]=label;gold=A.LABELS_CANONICAL.index(label)
        for name in A.ARMS:
            arm=row['arms'][name];receipt=arm['reader'];decision=arm['decision'];physical=row['readouts'][A.READOUT_REUSE_MAP[name]]
            if (receipt!=physical['reader']or arm['neural_readout_ref']!=physical['readout_id']or arm['extra_neural_readouts']!=0
                    or receipt['actual_logits_shape']!=[1,3]or receipt['pair_tokens']!=arm['joint_pair_tokens']
                    or receipt['full_pair_tokens']!=receipt['pair_tokens']or receipt['max_pair_tokens']!=512
                    or receipt['hidden_truncation']is not False or receipt['temperature']!=1.0 or receipt['calibrated']is not False
                    or receipt['semantic_decision_override']is not False or decision['raw_probabilities_E_C_N']!=receipt['probabilities_E_C_N']
                    or decision['raw_typed_argmax']!=receipt['native_typed_argmax']):raise ValueError('Immutable physical rawT1/readout reuse integrity failed')
            p=decision['final_probabilities_E_C_N'];lp=decision['final_log_probabilities_E_C_N']
            if (len(p)!=3 or any(not math.isfinite(v)or not 0<=v<=1 for v in p)or abs(math.fsum(p)-1)>1e-12
                    or len(lp)!=3 or any(not math.isfinite(v)or v>1e-12 for v in lp)):
                raise ValueError('Invalid finite final probability/logprob distribution')
            terms[name]['brier'].append(math.fsum((v-float(i==gold))**2 for i,v in enumerate(p)))
            terms[name]['nll'].append(-lp[gold]);terms[name]['clipped_nll'].append(-math.log(max(p[gold],1e-12)));terms[name]['gold_p'].append(p[gold])
            terms[name]['latencies'].append(receipt['forward_seconds']+arm['context_seconds']+arm['decision_seconds'])
            correct[name]+=int(decision['final_typed_argmax']==label)
        counters['engineering_native_predictions_compared']+=1;by_class[label]['n']+=1
        by_class[label]['correct']+=int(row['arms'][A.PRIMARY]['decision']['final_typed_argmax']==label)
    if any(v['n']!=4 for v in by_class.values()):raise ValueError('Exactly4cases perclass required')
    def percentile(values,q):
        x=sorted(values);k=(len(x)-1)*q;lo=int(k);hi=min(lo+1,len(x)-1);return x[lo]+(x[hi]-x[lo])*(k-lo)
    proper={a:{'brier':math.fsum(v['brier'])/12,'nll':math.fsum(v['nll'])/12,
        'NLL_stable_logsoftmax':math.fsum(v['nll'])/12,'NLL_clipped_1e-12':math.fsum(v['clipped_nll'])/12,
        'NLL_clip_count':sum(p<1e-12 for p in v['gold_p']),'probability_underflow_zero_count':sum(p==0 for p in v['gold_p']),
        'p50_seconds':percentile(v['latencies'],.5),'p95_seconds':percentile(v['latencies'],.95),
        'latency_scope':'Forward+packing+derived-decision component sum only. Excludes reader tokenization,BGE/source preparation,native index/query,model initialization; not end-to-end or publisher timing.'}for a,v in terms.items()}
    controls=A.ENGINEERING_GATE['proper_nonincrease_against']
    nonincrease={a:{m:proper[A.PRIMARY][m]<=proper[a][m]+1e-12 for m in('brier','nll')}for a in controls}
    gain=correct[A.PRIMARY]-correct['full_raw'];ceiling=correct['full_raw']>10
    passed=correct[A.PRIMARY]==12 and all(v=={'correct':4,'n':4}for v in by_class.values())and gain>=2 and not ceiling and all(all(v.values())for v in nonincrease.values())
    gate={'passed':passed,'primary_arm':A.PRIMARY,'primary_correct':correct[A.PRIMARY],'native_correct':correct[A.PRIMARY],
        'n':12,'by_class':by_class,'correct_by_arm':correct,'proper_scores_by_arm':proper,
        'proper_score_nonincrease_against_controls':nonincrease,'accuracy_gain_over_full_raw':gain,'baseline_ceiling_rejection':ceiling,
        'expected_labels':joined,'oracle_label_join_count':12,'oracle_join_after_all36_readouts_and60_forecasts':True,
        'all36_predictions_completed_before_oracle_read':True,'all60_forecasts_completed_before_oracle_read':True,
        'readers_unloaded_before_oracle':True,'single_reader_lifecycle_closed_before_oracle':True,
        'oracle':file_ref(file),'DEV_bank_read_before_gate':False,'benchmark_generalization_claim':False,
        'native_causal_gain_established':False,'native_causal_gain_scope':'No native causal gain claim when full/lexical verified controls equal',
        'frozen_rule':A.ENGINEERING_GATE,'rule':'Engineering only:12/12and4/class,+2overfull_raw,Brier/stableNLLnonincrease against allfourfrozencontrols. No benchmark generalization,confirmation,promotion.'}
    raw['engineering_gate']=gate;lifecycle(None,'ENGINEERING_ORACLE_JOIN_AFTER',joined_labels=12,unloaded_profiles=list(A.MODEL_ORDER))
    progress({'event':'ENGINEERING_GATE_CLOSED','gate':gate});return passed


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--phase',choices=('engineering',),required=True)
    for key in('plan','admission','out'):parser.add_argument('--'+key,type=Path,required=True)
    parser.add_argument('--expected-plan-sha',required=True);parser.add_argument('--deadline',type=float,required=True);args=parser.parse_args()
    if args.out.absolute()!=C.STUDY/'runs/engineering':raise ValueError('Wrong exact worker output')
    C.no_symlink(args.out);started=time.monotonic();counterkeys=set(expected_counters())|set(C.phase_zero('engineering'))
    raw={'schema_version':1,'epoch':37,'kind':A.KIND,'phase':'engineering','source_checkpoint':C.SOURCE,
        'plan_sha256':args.expected_plan_sha,'status':'INITIALIZING','worker_pid':os.getpid(),'worker_identity':C.proc(os.getpid()),
        'corpora':{'engineering':None},'corpus_reservations':{'engineering':None},'engineering_gate':None,'errors':[],
        'data_roles':{'train':[],'dev':[],'calibration':[],'confirmation':[]},'confirmation':[],'calibration':[],
        'engineering_only':True,'used_confirmation_identities':[],'benchmark_accepted':False,'champion_promoted':False,
        'benchmark_accuracy':None,'proper_scores':None,'training_lineage_complete':False,
        'model_initializations':{},'model_states_unchanged':{},'reader_lifecycle':[],'models_sequentially_unloaded':False,
        'NLI_scope':'Twelve new CC0 controlled-financial engineering sources. One original XXL,36 actual full/native-coverage/lexical-coverage readouts reused for60 five-armforecasts; complete source-bound exact certificates only. One12-labeljoin after model/tokenizer disposal. No benchmark/ClaimBench/generalization/training/calibration/confirmation/promotion.',
        'counters':{**dict.fromkeys(counterkeys,0),'BGE_forward_calls_attempted':0,'BGE_forward_calls_completed':0,
            'BGE_texts_attempted':0,'BGE_texts_completed':0,'BGE_forward_seconds':0.0,'automatically_extracted_units':0,
            'native_insertions_attempted':0,'native_insertions_completed':0,'native_hit_source_validations':0,
            'context_tokenizer_calls_attempted':0,'context_tokenizer_calls_completed':0,
            'context_pair_tokenizer_calls_attempted':0,'context_pair_tokenizer_calls_completed':0,
            'context_single_tokenizer_calls_attempted':0,'context_single_tokenizer_calls_completed':0,
            'Python_literal_loopback_capability_binds_allowed':0}}
    stream=(args.out/'progress.jsonl').open('xb');active={'tag':None,'base':{}}
    def sync_profile():
        tag=active['tag']
        if tag is not None:
            for source,dest in [('model_initializations_attempted','model_initializations_attempted'),
                    ('model_initializations_completed','model_initializations_completed'),
                    ('tokenizer_initializations_attempted','tokenizer_initializations_attempted'),
                    ('tokenizer_initializations_completed','tokenizer_initializations_completed'),
                    ('NLI_forward_calls_attempted','forward_calls_attempted'),('NLI_forward_calls_completed','forward_calls_completed'),
                    ('NLI_readouts_completed','readouts_completed')]:
                raw['counters'][tag+'_'+dest]=raw['counters'][source]-active['base'][source]
    def progress(event):
        sync_profile();row={'at_unix':time.time(),'elapsed_seconds':time.monotonic()-started,'event':event,
            'counters':dict(raw['counters']),'process':status(os.getpid())}
        stream.write((json.dumps(row,ensure_ascii=False,allow_nan=False)+'\n').encode());stream.flush();os.fsync(stream.fileno());checkpoint(raw,args.out)
    def lifecycle(tag,event,**extra):
        sync_profile();raw['reader_lifecycle'].append(dict(model_tag=tag,event=event,monotonic_seconds=time.monotonic(),
            global_readouts_completed=raw['counters']['NLI_readouts_completed'],
            profile_readouts_completed=raw['counters'].get(str(tag)+'_readouts_completed')if tag else None,
            process_status=status(os.getpid()),**extra));progress({'event':event,'model_tag':tag})
    offline=C.load_module('e37_offline',HERE/'runtime/network_guard.py').OfflineGuard(raw['counters'],progress).install()
    def stop(signum,frame):raise TimeoutError('Bounded E37 stop signal '+str(signum))
    signal.signal(signal.SIGTERM,stop);signal.signal(signal.SIGALRM,stop);code=0
    try:
        signal.setitimer(signal.ITIMER_REAL,max(.001,C.remaining(args.deadline)-7));cpu=status(os.getpid())
        if os.sched_getaffinity(0)!={0,1}or cpu.get('NoNewPrivs')!='1'or cpu.get('Seccomp')!='2':raise ValueError('Whole-worker CPU guard required before ML')
        if args.plan.absolute()!=C.STUDY/'plan.json'or C.sha(args.plan)!=args.expected_plan_sha:raise ValueError('Unknown source plan')
        provisional=C.read(args.plan);admission,owner=C.admission(args.admission,provisional,args.expected_plan_sha,'engineering')
        plan=C.verify_plan(args.plan,args.expected_plan_sha,'engineering');runtime=C.verify_runtime(plan)
        if plan['expected_operation_counters']['engineering']!=expected_counters()or plan['engineering_rejected_operation_counters']['engineering']!=expected_counters(False):raise ValueError('Different fixed single-reader work counts')
        while not(args.out/'attempt.json').exists():
            C.remaining(args.deadline)
            if time.monotonic()-started>15:raise RuntimeError('Worker start receipt missing')
            time.sleep(.01)
        attempt,current=C.read(args.out/'attempt.json'),C.proc(os.getpid())
        if any(attempt.get(k)!=v for k,v in{'pid':os.getpid(),'pgid':os.getpid(),'sid':os.getpid(),'startticks':current['ticks']}.items())or current['pgid']!=os.getpid()or current['sid']!=os.getpid():raise ValueError('Worker actual identity differs')
        raw.update(admission=admission,owner_lock=owner,source_freeze_sha256=plan['source_freeze_sha256'],
            worker_cpu_guard_preexec=C.read(args.out/'worker-cpu-preexec.json'),worker_cpu_guard_preexec_artifact=file_ref(args.out/'worker-cpu-preexec.json'),CPU_policy_before_model_import=cpu)
        progress({'event':'ALL_SINGLE_READER_SOURCE_MODEL_RUNTIME_CPU_GATES_BEFORE_ML'})
        evidence=C.load_module('e37_evidence',HERE/'evidence.py');codec=C.load_module('e37_vector_codec',HERE/'vector_codec.py');engine=C.load_module('e37_context',HERE/'context_engine.py')
        corpus=records=context=None;unloaded=[]
        for tag in A.MODEL_ORDER:
            active['tag']=tag;active['base']={k:raw['counters'][k]for k in('model_initializations_attempted','model_initializations_completed','tokenizer_initializations_attempted','tokenizer_initializations_completed','NLI_forward_calls_attempted','NLI_forward_calls_completed','NLI_readouts_completed')}
            lifecycle(tag,'MODEL_PHASE_START',earlier_profiles_disposed=list(unloaded))
            module=C.load_module('e37_'+tag+'_reader',HERE/'xxlarge_model.py')
            reader=module.FrozenMicrosoftXXLargeReader(C.MODEL,raw['counters'],progress,
                C.checked(plan['xxlarge_weight_metadata_path']),plan['xxlarge_weight_metadata_sha256'],
                C.checked(plan['legacy_original_load_plan_path']),plan['legacy_original_load_plan_sha256'])
            sync_profile();raw['model_initializations'][tag]=json.loads(json.dumps(reader.runtime_checks))
            lifecycle(tag,'MODEL_INITIALIZATION_COMPLETED',model_initialization_key=tag)
            offline.assert_clean()
            corpus,records,context=prepare_shared_role(raw,plan,args,progress,reader,engine,evidence,codec)
            pair=evidence.PairTokenizer(reader.tokenizer,raw['counters'])
            engine.pack_for_model(corpus['cases'],records,corpus['documents'],'engineering',context,evidence,pair,raw['counters'],progress,tag)
            del pair;score_model_role(raw,corpus,reader,args,progress,offline,tag)
            sync_profile();state=reader.unchanged();raw['model_states_unchanged'][tag]=state;corpus['model_states_unchanged'][tag]=state
            expected=36
            if raw['counters'][tag+'_readouts_completed']!=expected:raise ValueError('Incomplete model phase readouts')
            lifecycle(tag,'MODEL_READOUTS_COMPLETED',expected_readouts=expected,model_state_unchanged=state)
            raw['counters']['model_unloads_attempted']+=1;raw['counters'][tag+'_model_unloads_attempted']+=1
            references={'reader':weakref.ref(reader),'model':weakref.ref(reader.model),'tokenizer':weakref.ref(reader.tokenizer)}
            lifecycle(tag,'MODEL_UNLOAD_BEFORE')
            del reader;del module;collected=gc.collect()
            dead={name+'_weakref_dead':ref()is None for name,ref in references.items()}
            lifecycle(tag,'MODEL_UNLOAD_AFTER_GC',**dead,gc_collected_objects=collected,
                release_scope='Python reader/nn.Module/tokenizer instances disposed; allocator/page cache/shared libraries may remain.')
            if not all(dead.values()):raise ValueError('Reader/model/tokenizer object remains; next model forbidden')
            raw['counters']['model_unloads_completed']+=1;raw['counters'][tag+'_model_unloads_completed']+=1
            raw['counters']['sequential_model_lifecycles_completed']+=1;unloaded.append(tag);active['tag']=None
        raw['models_sequentially_unloaded']=unloaded==list(A.MODEL_ORDER)
        raw['status']='ENGINEERING_ADMISSION_PASSED'if engineering_gate(raw,plan,progress,lifecycle)else'ENGINEERING_ADMISSION_FAILED'
        raw['native_child_closed']=corpus['native_child_closed']is True
        C.verify_plan(args.plan,args.expected_plan_sha,'engineering');C.verify_runtime(plan);C.owner_lock(admission);C.remaining(args.deadline);offline.assert_clean()
        if any(raw['counters'][k]!=v for k,v in expected_counters().items())or any(raw['counters'][k]for k in C.phase_zero('engineering')):
            raise ValueError('Single-reader fixed work/forbidden counters fail closure')
    except BaseException as error:
        sync_profile();raw['status']='FAILED_ENGINEERING';raw['errors'].append({'type':type(error).__name__,'message':str(error),'traceback':traceback.format_exc()});code=2
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
