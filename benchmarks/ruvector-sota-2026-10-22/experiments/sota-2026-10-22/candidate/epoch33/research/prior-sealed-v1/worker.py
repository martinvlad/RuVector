"""One CPU2/600 worker: exposed engineering24, then conditional fresh DEV96."""
import argparse
from datetime import datetime,timezone
import importlib.util
import json
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
_spec=importlib.util.spec_from_file_location('e33_runtime',HERE/'runtime/common.py')
C=importlib.util.module_from_spec(_spec);_spec.loader.exec_module(C)
A=C.load_module('e33_algorithm',HERE/'algorithm.py')

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

def file_ref(path):
    return {'path': str(path.relative_to(C.ROOT)), 'bytes': path.stat().st_size, 'sha256': C.sha(path)}


def expected_counters(full=True):
    helpers=2 if full else 1;indexes=14 if full else 6;queries=60 if full else 12;pairs=120 if full else 24
    table={key:0 for key in C.phase_zero('dev')}
    for name in ('model_initializations','tokenizer_initializations','BGE_initializations','ORT_sessions'):
        for suffix in ('_attempted','_completed'):table[name+suffix]=1
    for name,value in [('native_helper_starts',helpers),('native_binary_loads',helpers),('native_version_calls',helpers),
            ('native_index_initializations',indexes),('native_queries',queries),('native_len_calls',2*indexes),
            ('NLI_forward_calls',pairs),('pair_tokenizations',pairs),('NLI_full_pair_tokenizer_calls',pairs),('NLI_capped_pair_tokenizer_calls',pairs),('ENGINEERING_forward_calls',24),('DEV_forward_calls',96 if full else 0)]:
        for suffix in ('_attempted','_completed'):table[name+suffix]=value
    table['NLI_readouts_completed']=pairs
    table.update(corpus_batches_attempted=helpers,corpus_batches_completed=helpers,ENGINEERING_input_bank_reads=1,
        engineering_oracle_reads=1,engineering_oracle_expected_labels_accessed=6,engineering_native_predictions_compared=6,
        DEV_input_bank_reads=int(full),DEV_reads=int(full),ENGINEERING_contexts_completed=24,DEV_contexts_completed=96 if full else 0)
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
    source=args.out/(role+'-native-bundle.json');target=args.out/(role+'-native-result.json')
    C.put(source,bundle);corpus['vector_bundle']=file_ref(source)
    reservation=args.out/(role.upper()+'_CORPUS_ATTEMPT_RESERVATION.json')
    C.put(reservation,{'schema_version':1,'epoch':33,'kind':A.KIND,'phase':'dev','role':role,'plan_sha256':args.expected_plan_sha,
        'corpus_batches_reserved':1,'allowed_further_role_helpers':0,'before_Popen':True,'automatic_retry':False,'at_unix':time.time()})
    directory=os.open(args.out,os.O_RDONLY|os.O_DIRECTORY)
    try:os.fsync(directory)
    finally:os.close(directory)
    raw['corpus_reservations'][role]=file_ref(reservation);corpus['corpus_reservation']=file_ref(reservation)
    counters['corpus_batches_attempted']+=1
    process=identity=None;stdout=stderr=b'';started=time.perf_counter()
    with tempfile.TemporaryDirectory(prefix='e33-'+role+'-native-',dir=C.ROOT.parent) as scratch:
        corpus['native_scratch']={'path':scratch,'outside_public_project':True}
        command=['node','--require='+str(HERE/'runtime/node_guard.cjs'),str(HERE/'native_helper.cjs'),str(source),str(target)]
        env=dict(os.environ,E33_ROLE=role)
        counters['native_helper_starts_attempted']+=1;progress({'event':'NATIVE_HELPER_POPEN_BEFORE','role':role,'argv':command})
        try:
            process=subprocess.Popen(command,cwd=scratch,env=env,stdout=subprocess.PIPE,stderr=subprocess.PIPE)
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
    if (result.get('epoch')!=33 or result.get('kind')!=A.KIND or result.get('role')!=role or result.get('phase')!='dev'
            or result.get('native') is not True or result.get('bundle_sha256')!=C.sha(source) or result.get('source_sha256')!=C.sha(HERE/'native_helper.cjs')
            or result.get('native_binary_sha256')!=C.BINARY_SHA or result.get('helper_pid')!=process.pid
            or result.get('package_version')!='0.1.33' or result.get('platform_package_version')!='0.1.31' or result.get('binary_version')!='2.3.0'
            or result.get('compact_schema')!='epoch33-native-context-f32le-v1' or len(result['documents'])!=(6 if role=='engineering' else 8) or result.get('errors')!=[]):raise ValueError('Wrong native/source/runtime role receipt')
    for key,value in result.items():
        if key.startswith('native_') and type(value) is int:counters[key]=baseline.get(key,0)+value
    node_events(args.out,role,counters,baseline)
    counters['corpus_batches_completed']+=1;progress({'event':'NATIVE_ROLE_CORPUS_CLOSED','role':role})
    return result


def prepare_role(raw,plan,args,progress,role,model,engine,evidence,codec,bge):
    counters=raw['counters'];file=C.checked(plan[role+'_inputs_path'])
    if C.sha(file)!=plan[role+'_inputs_sha256']:raise ValueError('Changed fixed inputs-only role source')
    counters[role.upper()+'_input_bank_reads']+=1
    if role=='dev':counters['DEV_reads']+=1
    records=evidence.validate_inputs(C.read(file),role)
    corpus={'role':role,'input_bank':file_ref(file),'cases':[],'documents':{},'native_child_closed':None}
    raw['corpora'][role]=corpus
    tokenizer=evidence.PairTokenizer(model.tokenizer,counters)
    context,documents,bundle,receipt=engine.prepare(C,records,tokenizer,counters,progress,codec,bge,role)
    bundle['phase']='dev';corpus['documents']=documents
    native=run_native(bundle,corpus,raw,args,progress,role)
    corpus['cases']=engine.pack_all(records,documents,native,role,context,evidence,tokenizer,counters,progress)
    return corpus,records


def score_role(raw,corpus,model,args,progress,offline,role):
    proof=C.load_module('e33_proof',HERE/'proof.py')
    for case in corpus['cases']:
        for arm_name in A.ARMS:
            C.remaining(args.deadline);offline.assert_clean()
            arm=case['arms'][arm_name];receipt={};arm['reader']=receipt
            model.score(arm['premise'],case['hypothesis'],receipt,role)
            if receipt['pair_tokens']!=arm['joint_pair_tokens']:raise ValueError('Reader/packed full pair budget differs')
            decision_started=time.perf_counter()
            arm['decision']=proof.decide(case['document'],arm['premise'],case['hypothesis'],arm['context']['selected_source_spans'],receipt,enabled=role=='engineering')
            arm['decision_seconds']=time.perf_counter()-decision_started
            arm['semantic_decision_override']=arm['decision']['semantic_decision_override']
            offline.assert_clean()
    corpus['model_state_unchanged']=model.unchanged()


def engineering_gate(raw,plan,progress):
    counters=raw['counters']
    if any(counters.get(k)!=24 for k in ('ENGINEERING_forward_calls_attempted','ENGINEERING_forward_calls_completed','NLI_forward_calls_attempted','NLI_forward_calls_completed','NLI_readouts_completed')) or counters.get('DEV_forward_calls_completed')!=0:raise ValueError('Exposed engineering oracle requires all24 raw neural readouts before access')
    if raw['corpora']['engineering'].get('native_child_closed') is not True:raise ValueError('Engineering native helper must be closed before oracle')
    file=C.checked(plan['engineering_oracle_path'])
    if C.sha(file)!=plan['engineering_oracle_sha256']:raise ValueError('Changed authored engineering oracle')
    counters['engineering_oracle_reads']+=1;oracle=C.read(file)
    if set(oracle)!={'schema_version','epoch','role','expected_labels'} or oracle['schema_version']!=1 or oracle['epoch']!=33 or oracle['role']!='engineering' or set(oracle['expected_labels'])!=set(A.ENG_CASE_IDS):raise ValueError('Wrong authored engineering oracle')
    expected=oracle['expected_labels']
    if sorted(expected.values())!=sorted(['Entailment']*2+['Contradiction']*2+['NotMentioned']*2):raise ValueError('Engineering must contain two of each exact type')
    rows=raw['corpora']['engineering']['cases']
    if len(rows)!=6 or tuple(row['id'] for row in rows)!=A.ENG_CASE_IDS:raise ValueError('Incomplete ordered engineering corpus')
    correct={arm:0 for arm in A.ARMS};by_class={label:{'correct':0,'n':0} for label in A.LABELS_CANONICAL}
    for row in rows:
        label=expected[row['id']];counters['engineering_oracle_expected_labels_accessed']+=1
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
            if decision['policy']!='proof-carrying-closed-legal-atoms-v1' or len(decision['final_probabilities_E_C_N'])!=3 or any(type(x)not in(int,float) or not 0<=x<=1 for x in decision['final_probabilities_E_C_N']) or abs(sum(decision['final_probabilities_E_C_N'])-1)>1e-12:raise ValueError('Proof decision distribution invalid')
            if arm['semantic_decision_override'] is not (decision['certificate'] is not None) or decision['semantic_decision_override'] is not arm['semantic_decision_override']:raise ValueError('Proof override disclosure inconsistent')
            winner=reader['native_typed_argmax'] if decision['certificate'] is None else decision['certificate']['conclusion']
            if decision['final_typed_argmax']!=winner or decision['final_probabilities_E_C_N'][A.LABELS_CANONICAL.index(winner)]!=max(decision['final_probabilities_E_C_N']):raise ValueError('Final argmax/probability disagreement')
            if decision['certificate'] is None and (decision['final_probabilities_E_C_N']!=reader['probabilities_E_C_N'] or decision['final_typed_argmax']!=reader['native_typed_argmax']):raise ValueError('Fallback must preserve raw neural output')
            correct[arm_name]+=int(decision['final_typed_argmax']==label)
        counters['engineering_native_predictions_compared']+=1
        by_class[label]['n']+=1;by_class[label]['correct']+=int(row['arms']['actual_native']['decision']['final_typed_argmax']==label)
    passed=correct['actual_native']==6 and all(row=={'correct':2,'n':2} for row in by_class.values())
    gate={'passed':passed,'native_correct':correct['actual_native'],'n':6,'by_class':by_class,'correct_by_arm':correct,
        'all24_predictions_completed_before_oracle_read':True,'all24_finite_true_pair_source_numeric_integrity':True,
        'rule':'EXPOSED_DEV_REGRESSION only: final native6/6 and two correct per class; lexical/positional semantic accuracy descriptive. Original raw NLI retained plus source-bound proof decision.',
        'oracle':file_ref(file),'DEV_bank_read_before_gate':False,'benchmark_generalization_claim':False}
    raw['engineering_gate']=gate;progress({'event':'ENGINEERING_GATE_CLOSED','gate':gate})
    return passed


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--phase',choices=('dev',),required=True)
    for key in ('plan','admission','out'):parser.add_argument('--'+key,type=Path,required=True)
    parser.add_argument('--expected-plan-sha',required=True);parser.add_argument('--deadline',type=float,required=True);args=parser.parse_args()
    if args.out.absolute()!=C.STUDY/'runs/dev':raise ValueError('Wrong exact worker output')
    C.no_symlink(args.out);started=time.monotonic();counterkeys=set(expected_counters(True))|set(C.phase_zero('dev'))
    raw={'schema_version':1,'epoch':33,'kind':A.KIND,'phase':'dev','source_checkpoint':C.SOURCE,'plan_sha256':args.expected_plan_sha,
        'status':'INITIALIZING','worker_pid':os.getpid(),'worker_identity':C.proc(os.getpid()),'corpora':{'engineering':None,'dev':None},
        'corpus_reservations':{'engineering':None,'dev':None},'engineering_gate':None,'errors':[],
        'data_roles':{'train':[],'dev':list(A.DEV_DOCUMENT_IDS),'calibration':[],'confirmation':[]},'confirmation':[],'calibration':[],
        'benchmark_accepted':False,'champion_promoted':False,'benchmark_accuracy':None,'proper_scores':None,'training_lineage_complete':False,
        'NLI_scope':'Primary treatment: typed-modal query expansion with original-native causal control and matched expanded lexical/positional retrieval. Same original Moritz E,N,C head in all four arms. Proof applies only to exposed engineering regression; DEV final equals raw T1. No proof efficacy, confirmation, promotion or generalization claim.',
        'counters':{**dict.fromkeys(counterkeys,0),'BGE_forward_calls_attempted':0,'BGE_forward_calls_completed':0,'BGE_texts_attempted':0,
            'BGE_texts_completed':0,'BGE_forward_seconds':0.0,'automatically_extracted_units':0,'native_insertions_attempted':0,
            'native_insertions_completed':0,'native_hit_source_validations':0,'context_tokenizer_calls_attempted':0,'context_tokenizer_calls_completed':0,
            'context_pair_tokenizer_calls_attempted':0,'context_pair_tokenizer_calls_completed':0,'context_single_tokenizer_calls_attempted':0,
            'context_single_tokenizer_calls_completed':0,'Python_literal_loopback_capability_binds_allowed':0}}
    stream=(args.out/'progress.jsonl').open('xb')
    def progress(event):
        row={'at_unix':time.time(),'elapsed_seconds':time.monotonic()-started,'event':event,'counters':dict(raw['counters']),'process':status(os.getpid())}
        stream.write((json.dumps(row,ensure_ascii=False,allow_nan=False)+'\n').encode());stream.flush();os.fsync(stream.fileno());checkpoint(raw,args.out)
    offline=C.load_module('e33_offline',HERE/'runtime/network_guard.py').OfflineGuard(raw['counters'],progress).install()
    def stop(signum,frame):raise TimeoutError('Bounded E33 stop signal '+str(signum))
    signal.signal(signal.SIGTERM,stop);signal.signal(signal.SIGALRM,stop);code=0
    try:
        signal.setitimer(signal.ITIMER_REAL,max(.001,C.remaining(args.deadline)-7))
        cpu=status(os.getpid())
        if os.sched_getaffinity(0)!={0,1} or cpu.get('NoNewPrivs')!='1' or cpu.get('Seccomp')!='2':raise ValueError('Whole worker CPU guard required before ML')
        if args.plan.absolute()!=C.STUDY/'plan.json' or C.sha(args.plan)!=args.expected_plan_sha:raise ValueError('Unknown source plan')
        provisional=C.read(args.plan);admission,owner=C.admission(args.admission,provisional,args.expected_plan_sha,'dev')
        plan=C.verify_plan(args.plan,args.expected_plan_sha,'dev');runtime=C.verify_runtime(plan)
        if plan['expected_operation_counters']['dev']!=expected_counters(True) or plan['engineering_rejected_operation_counters']['dev']!=expected_counters(False):raise ValueError('Different frozen conditional work counts')
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
        evidence=C.load_module('e33_evidence',HERE/'evidence.py');codec=C.load_module('e33_vector_codec',HERE/'vector_codec.py');engine=C.load_module('e33_context',HERE/'context_engine.py')
        module=C.load_module('e33_trained_NLI_reader',HERE/'model.py');model=module.FrozenMoritzProofReader(C.MODEL,raw['counters'],progress)
        raw['model_initialization']=model.runtime_checks;offline.assert_clean();bge=engine.initialize(C,raw['counters'],progress);raw['BGE']=bge[2]
        raw['loaded_runtime_libraries']=loaded_runtime_libraries(runtime)
        corpus,_=prepare_role(raw,plan,args,progress,'engineering',model,engine,evidence,codec,bge)
        score_role(raw,corpus,model,args,progress,offline,'engineering')
        if engineering_gate(raw,plan,progress):
            corpus,_=prepare_role(raw,plan,args,progress,'dev',model,engine,evidence,codec,bge)
            score_role(raw,corpus,model,args,progress,offline,'dev');raw['status']='COMPLETED_DEV_AWAITING_INDEPENDENT_GOLD_JOIN'
        else:raw['status']='ENGINEERING_REJECTED_DEV_NOT_STARTED';code=2
        if raw['corpora']['dev'] is not None and C.sha(C.checked(plan['dev_inputs_path']))!=plan['dev_inputs_sha256']:raise ValueError('DEV source changed after admitted read')
        raw['model_state_unchanged']=model.unchanged();raw['native_child_closed']=all(v is None or v.get('native_child_closed') is True for v in raw['corpora'].values())
        C.verify_plan(args.plan,args.expected_plan_sha,'dev');C.verify_runtime(plan);C.owner_lock(admission);C.remaining(args.deadline);offline.assert_clean()
        expected=expected_counters(raw['status']=='COMPLETED_DEV_AWAITING_INDEPENDENT_GOLD_JOIN')
        if any(raw['counters'][k]!=v for k,v in expected.items()) or any(raw['counters'][k] for k in C.phase_zero('dev')):raise ValueError('Conditional work/forbidden count closure failed')
    except BaseException as error:
        raw['status']='FAILED_DEV';raw['errors'].append({'type':type(error).__name__,'message':str(error),'traceback':traceback.format_exc()});code=2
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
        try:progress({'event':'WORKER_FINAL','status':raw['status'],'errors':raw['errors']})
        except BaseException as error:
            raw['status']='FAILED_DEV';raw['errors'].append({'stage':'final_checkpoint','type':type(error).__name__,'message':str(error)});code=2
        pending=args.out/'raw.partial.pending.json'
        if pending.is_file():raw['leftover_partial_checkpoint']={**file_ref(pending),'retained_without_overwrite':True}
        C.put(args.out/'raw.json',raw);stream.close()
    return code


if __name__=='__main__':raise SystemExit(main())
