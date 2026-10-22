"""Stronger NLI with native RuVector retrieval and matched singleton controls."""
from __future__ import annotations
import copy
import hashlib
import importlib.metadata
import importlib.util
import json
import os
from pathlib import Path
import resource
import subprocess
import tempfile
import time

HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[3]


def module(name,path):
    spec=importlib.util.spec_from_file_location(name,path);out=importlib.util.module_from_spec(spec);spec.loader.exec_module(out);return out


MODELS=module("epoch4_models",HERE/"models.py")
CONTEXT=module("epoch4_context",HERE/"context.py")
PREVIOUS=module("epoch4_prior_helpers",HERE.parent/"epoch3/runtime.py")


def resource_snapshot(native_pid=None):
    self_usage=resource.getrusage(resource.RUSAGE_SELF);children=resource.getrusage(resource.RUSAGE_CHILDREN)
    result={"self_user_cpu_seconds":self_usage.ru_utime,"self_system_cpu_seconds":self_usage.ru_stime,"self_peak_rss_KiB":self_usage.ru_maxrss,"terminated_children_user_cpu_seconds":children.ru_utime,"terminated_children_system_cpu_seconds":children.ru_stime,"terminated_children_peak_rss_KiB":children.ru_maxrss}
    try:
        for line in Path('/proc/self/status').read_text().splitlines():
            if line.startswith('VmRSS:'):result['self_current_rss_KiB']=int(line.split()[1])
    except OSError:result['self_current_rss_KiB']=None
    if native_pid:
        try:
            fields=Path(f'/proc/{native_pid}/stat').read_text().rsplit(')',1)[1].split();ticks=os.sysconf('SC_CLK_TCK')
            result['native104_live_process']={"pid":native_pid,"user_cpu_seconds":int(fields[11])/ticks,"system_cpu_seconds":int(fields[12])/ticks,"rss_bytes":int(fields[21])*os.sysconf('SC_PAGE_SIZE')}
        except (OSError,ValueError,IndexError):result['native104_live_process']=None
    result['accounting']='Self, already-terminated children and still-live native104 are separate observations; no double-counted total CPU claim.'
    if hasattr(os,'sched_getaffinity'):result['observed_cpu_affinity']=sorted(os.sched_getaffinity(0))
    return result


class CandidateEngine:
    name='ruvector-native-evidence-deberta-base-epoch4'
    attribution='Actual native RuVector BGE/core evidence selection plus stronger pretrained DeBERTa-base joint singleton NLI; same-model lexical/positional controls. Native104 reference reads exactly the same selected excerpt, not original full input.'

    def __init__(self,artifact_path=None):
        started=time.perf_counter();initial=resource_snapshot()
        self.counters={key:0 for key in ['requests_attempted','requests_completed','native104_requests_attempted','native104_requests_completed','native_core_searches_attempted','native_core_searches_completed','bge_forward_batches_attempted','bge_forward_batches_completed','bge_texts_attempted','bge_texts_completed','nli_forward_pairs_attempted','nli_forward_pairs_completed','nli_input_tokens_attempted','nli_input_tokens_completed']}
        self.counters.update(bge_forward_wall_seconds=0.,nli_forward_wall_seconds=0.)
        bundle=os.environ.get('RUVECTOR_SOTA_BUNDLE_DIR')
        if not bundle:raise ValueError('RUVECTOR_SOTA_BUNDLE_DIR required')
        self.bundle_directory=Path(bundle).resolve();self.bundle_directory.mkdir(parents=True,exist_ok=True)
        lock=json.loads((HERE/'assets.lock.json').read_text())
        for package,version in lock['python_versions'].items():
            if importlib.metadata.version(package)!=version:raise ValueError('Python version mismatch: '+package)
        for item in lock['assets']:
            p=ROOT/item['path']
            if not p.is_file() or p.stat().st_size!=item['bytes'] or MODELS.sha(p)!=item['sha256']:raise ValueError('Asset identity mismatch: '+item['path'])
        self.config=json.loads((HERE/'config.json').read_text())
        if MODELS.sha(HERE/'config.json')!='54620f15c84d562e1a2ab361acbe0431ffe9ba8278e1d1ca06a1cf685ba02f11':raise ValueError('Frozen epoch4 config changed')
        if artifact_path and json.loads(Path(artifact_path).read_text())!=self.config:raise ValueError('Unfrozen epoch4 configuration')
        plan_path=ROOT/'experiments/submission-2026-10-22/jevbench/round2-v2/plan.json'
        if MODELS.sha(plan_path)!='782db4034b2eb51ad9520a632ee94f7bdbb5bf0e8826ca44a91a055c15971f17':raise ValueError('Native104 source plan changed')
        plan=json.loads(plan_path.read_text())
        for name,expected in plan['source_sha256'].items():
            if MODELS.sha(ROOT/name)!=expected:raise ValueError('Native104 source changed: '+name)
        self.bge=PREVIOUS.MODELS.BgeEncoder(ROOT)
        self.bge.session=MODELS.CountedSession(self.bge.session,self.counters)
        self.nli=MODELS.SingletonNli(HERE/'assets/nli-base',self.counters)
        self.base=PREVIOUS.BASE.CompositeEngine(ROOT/'experiments/submission-2026-10-22/jevbench/round2-v2/rules.py')
        self.native_process=self.base.native.process;self.native_pid=self.native_process.pid
        if self.base.receipt['binary_sha256']!=plan['native_candidate']['binary_sha256']:
            self.base.close();raise ValueError('Native104 binary changed')
        self.core_binary_sha256=lock['native_core_binary_sha256'];self.evidence_cache={};self.last_usage=None
        self.receipt={**self.base.receipt,'architecture':self.attribution,'config':self.config,'nli':self.nli.receipt,'bge':self.bge.receipt,'assets_lock_sha256':MODELS.sha(HERE/'assets.lock.json'),'native_core_binary_sha256':self.core_binary_sha256,'initialization_wall_seconds':time.perf_counter()-started,'resources_before_initialization':initial,'resources_after_initialization':resource_snapshot(self.native_pid),'execution_counters':copy.deepcopy(self.counters),'batch_policy':'Exactly one allowed composite corpus batch shared by DEV24 and conditionally-gated96, total600seconds; caller controls deadline and no retry.'}

    def retrieve(self,chunks,hypothesis):
        key=hashlib.sha256(json.dumps(chunks,ensure_ascii=False,separators=(',',':')).encode()).hexdigest()
        hit=key in self.evidence_cache
        if hit:
            vectors=self.evidence_cache[key];chunk_diag={'cache_hit':True,'elapsed_ms':0.,'examples':[],'model_batches':0}
        else:
            vectors,chunk_diag=self.bge.encode(chunks);chunk_diag['cache_hit']=False
            if len(self.evidence_cache)>=64:self.evidence_cache.pop(next(iter(self.evidence_cache)))
            self.evidence_cache[key]=vectors
        query,query_diag=self.bge.encode([self.config['query_prefix']+hypothesis])
        bundle={'vectors':vectors.tolist(),'query_vectors':query.tolist()}
        literal=json.dumps(bundle,separators=(',',':'),allow_nan=False).encode()
        evidence=PREVIOUS.preserve_bundle(literal,self.bundle_directory)
        started=time.perf_counter();self.counters['native_core_searches_attempted']+=1
        with tempfile.TemporaryDirectory(prefix='ruvector-epoch4-') as directory:
            folder=Path(directory);source=folder/'bundle.json';target=folder/'native.json';source.write_bytes(literal)
            done=subprocess.run(['node',str(ROOT/'retrieval/native-candidates.cjs'),str(source),str(target)],cwd=folder,capture_output=True,text=True,timeout=60)
            if done.returncode:raise RuntimeError('Native retrieval failed: '+done.stderr[-500:])
            native=json.loads(target.read_text())
        if native.get('native') is not True or native.get('package_version')!='0.1.33' or native.get('native_binary_sha256')!=self.core_binary_sha256 or native.get('bundle_sha256')!=evidence['sha256']:raise ValueError('Native search identity mismatch')
        self.counters['native_core_searches_completed']+=1
        ids=native['queries'][0]['ids'][:min(2,len(chunks))]
        if not ids or len(ids)!=len(set(ids)) or any(type(i) is not int or i<0 or i>=len(chunks) for i in ids):raise ValueError('Invalid native search ids')
        return ids,{'native':native,'bundle_evidence':evidence,'embedding':{'chunks':chunk_diag,'query':query_diag,'actual_embedded_texts':1+(0 if hit else len(chunks)),'cached_chunk_vectors':len(chunks) if hit else 0},'native_process_wall_ms':(time.perf_counter()-started)*1000}

    def execution_snapshot(self):return {'counters':copy.deepcopy(self.counters),'resources':resource_snapshot(getattr(self,'native_pid',None))}

    def predict(self,state,questions):
        self.counters['requests_attempted']+=1;started=time.perf_counter();before=self.execution_snapshot()
        if not isinstance(state,str):state=json.dumps(state,ensure_ascii=False,separators=(',',':'))
        self.last_usage={'execution':before,'paid_calls':0}
        try:
            predicates={key:PREVIOUS.validate_question(q) for key,q in questions.items()}
            offsets=self.nli.tokenizer.encode(state,add_special_tokens=False).offsets
            spans=CONTEXT.spans_from_offsets(offsets,len(state),192,32,64);chunks=[state[a:b] for a,b in spans]
            answers={name:{} for name in ['ruvector_top2','lexical_top2','positional_first2']};diag={};baseline_answers={};native_usages={}
            for key,hypothesis in predicates.items():
                ids,retrieval=self.retrieve(chunks,hypothesis)
                selected={'ruvector_top2':ids,'lexical_top2':PREVIOUS.lexical_ids(chunks,hypothesis,min(2,len(chunks))),'positional_first2':list(range(min(2,len(chunks))))}
                contexts={name:CONTEXT.joint_context(state,spans,selection,hypothesis,self.nli.tokenizer) for name,selection in selected.items()}
                control_input={'state':contexts['ruvector_top2'][0],'questions':{key:questions[key]}}
                if len(control_input['state'].encode())>16*1024:raise ValueError('Native evidence exceeds16KiB; no clipping')
                self.counters['native104_requests_attempted']+=1;control_started=time.perf_counter()
                control=self.base.predict(control_input['state'],control_input['questions']);self.counters['native104_requests_completed']+=1
                control_ms=(time.perf_counter()-control_started)*1000
                baseline_answers[key]=copy.deepcopy(control['answers'][key]);native_usages[key]=copy.deepcopy(control.get('usage',{}))
                arms={}
                for name,(premise,coverage) in contexts.items():
                    p,decoding=self.nli.decode(premise,hypothesis)
                    answer=PREVIOUS.answer_for(p);answer.update(model='Xenova/nli-deberta-v3-base@80a99030ce45a69a39ea2a6f50756d03859ff521',head='joint-complete-evidence-singleton-NLI')
                    answers[name][key]=answer
                    arms[name]={'chunk_ids':selected[name],'chunk_spans':[spans[i] for i in selected[name]],'premise':premise,'hypothesis':hypothesis,'coverage':coverage,'decoding':decoding}
                encoded=json.dumps(control_input,ensure_ascii=False,separators=(',',':'),allow_nan=False).encode()
                diag[key]={'state_bytes':len(state.encode()),'total_state_nli_tokens':len(offsets),'total_chunks':len(chunks),'chunk_spans':spans,'retrieval':retrieval,'arms':arms,'baseline_control_label':'native104_on_ruvector_evidence','baseline_control_input':control_input,'baseline_control_input_sha256':hashlib.sha256(encoded).hexdigest(),'baseline_control_input_hash_encoding':"UTF8 JSON ensure_ascii=False separators=(',',':') allow_nan=False",'baseline_control_source_chunk_ids':ids,'baseline_control_state_bytes':len(control_input['state'].encode()),'baseline_control_wall_ms':control_ms}
            baseline={'model':'native104_on_ruvector_evidence','answers':baseline_answers,'usage':{'native_requests':len(native_usages),'per_question_native_usage':native_usages},'attribution':'Native104 reader sees exactly the same complete source-ordered merged native-selected evidence and original question; not submitted full-input104.'}
            self.counters['requests_completed']+=1
            self.last_usage={'native_requests':len(native_usages),'native_core_searches':len(questions),'nli_singleton_pairs':3*len(questions),'per_question_native_usage':native_usages,'execution_before':before,'execution_after':self.execution_snapshot(),'paid_calls':0,'latency_scope':'Request includes all3 matched joint-NLI arms, native104 reference and retrieval; not primary-only deployment latency.'}
            def response(name):return {'model':self.name+'-'+name,'answers':copy.deepcopy(answers[name]),'usage':copy.deepcopy(self.last_usage),'attribution':self.attribution}
            out=response('ruvector_top2');out.update(baseline104_response=baseline,ablation_responses={'same_nli_lexical_top2':response('lexical_top2'),'same_nli_positional_first2':response('positional_first2')},diagnostics=diag,whole_request_wall_ms=(time.perf_counter()-started)*1000)
            return out
        finally:
            self.last_usage.update(execution_terminal=self.execution_snapshot(),request_wall_seconds=time.perf_counter()-started)

    def close(self):
        self.receipt['execution_before_close']=self.execution_snapshot()
        self.base.close()
        self.receipt['execution_after_close']=self.execution_snapshot()
