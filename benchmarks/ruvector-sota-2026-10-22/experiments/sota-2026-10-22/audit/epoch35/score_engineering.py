"""E35 independently replayed engineering admission; pure standard library.

No candidate imports, original benchmark records, oracle traversal, tokenization,
native execution, training, calibration or new measurements. EVALUATE is a
one-use operation authorized only after physical worker/supervisor closure.
"""
import argparse,json,math
from pathlib import Path
from data_common import require,write_new,CLASSES,GOLD_NAMES,expected,canonical,digest,AUTHORED_LABEL_MAP_SHA256
from phase_audit import KIND,ROLES,read,ref,checked,source_checks,phase_integrity,supervisor_closure,physical_ownership_closure,publisher
from model_audit import audit_model,WEIGHT_SHA,WEIGHT_BYTES
from evidence_audit import audit_evidence
from nli_metrics import reader_check,metrics,engineering_gates,paired_differences
from decision_proof_audit import decision_check,policy_check
from query_audit import policy_check as query_policy_check
from policy_lineage_audit import audit as policy_inheritance

ARMS={'actual_native':'native','native_original':'native_original','lexical':'lexical','positional':'positional'}

def quantile(values,q):
    require(bool(values)and all(type(v)in(int,float)and math.isfinite(v)and v>=0 for v in values),'Empty/nonfinite timing')
    a=sorted(values);x=(len(a)-1)*q;lo,hi=math.floor(x),math.ceil(x)
    return a[lo]+(x-lo)*(a[hi]-a[lo])

def pretrained_source(root,plan):
    pin=plan['pretrained_model_source'];value=read(checked(root,pin))
    wanted={'epoch':35,'kind':KIND,'repository':'MoritzLaurer/DeBERTa-v3-large-mnli-fever-anli-ling-wanli',
        'revision':'b3546ea6b0346eb6f8d5d68b13c7dc6d0376b3d7','weights_file':'model.safetensors',
        'weights_bytes':WEIGHT_BYTES,'weights_sha256':WEIGHT_SHA,'training_lineage_complete':False,
        'source_parameter_dtype':'F16','compute_dtype':'F32',
        'native_id2label':{'0':'entailment','1':'neutral','2':'contradiction'},'canonical_E_C_N_to_raw':[0,2,1],
        'confirmation':[],'promotion_allowed':False,'official_eligibility':'HOLD'}
    require(all(value.get(k)==v for k,v in wanted.items()),'Wrong stock generic model or overstated lineage/eligibility')
    checked(root,value['metadata_admission']);pins={p['path']:p for p in plan['pins']}
    require(pins.get(value['metadata_admission']['path'])==value['metadata_admission'],'Unpinned source provenance')
    proof=policy_check(read(root/plan['proof_policy_path'],plan['proof_policy_sha256']))
    query=query_policy_check(read(root/plan['query_policy_path'],plan['query_policy_sha256']))
    return {'status':'PASS_SAME_E34_GENERIC_STOCK_MODEL_AND_POLICY','pretrained_model_source':pin,
        'proof_policy_audit':proof,'query_policy_audit':query,'training_lineage_complete':False,'confirmation_eligibility':'HOLD'}

def role_outputs(root,corpus,bank,plan):
    evidence=audit_evidence(root,corpus,bank,'engineering',plan)
    rows=[];times={n:{'reader':[],'forward':[],'composite_local':[],'context':[],'native_query':[]}for n in ARMS.values()}
    certificates={n:[]for n in ARMS.values()}
    for case,inp in zip(corpus['cases'],bank['records']):
        readers={}
        for armname,name in ARMS.items():
            arm=case['arms'][armname];r=arm['reader'];require(r['role']=='engineering','Nonengineering reader')
            native=reader_check(r,arm['premise'],inp['hypothesis'],arm['joint_pair_tokens'])
            readers[name],proof=decision_check(arm['decision'],r,native,inp['document'],arm['premise'],
                inp['hypothesis'],arm['context']['selected_source_spans'],arm['semantic_decision_override'],'engineering')
            certificates[name].append({'id':case['id'],**proof})
            for key in ['decision_seconds','context_seconds']:
                require(type(arm[key])in(int,float)and math.isfinite(arm[key])and arm[key]>=0,'Invalid measured policy/context timing')
            times[name]['reader'].append(r['reader_seconds']);times[name]['forward'].append(r['forward_seconds'])
            times[name]['composite_local'].append(r['reader_seconds']+arm['decision_seconds'])
            times[name]['context'].append(arm['context_seconds'])
            if arm['native_query_seconds']is not None:times[name]['native_query'].append(arm['native_query_seconds'])
        rows.append({'id':case['id'],'document_id':case['document_id'],'readers':readers})
    require(len(rows)==12 and sum(len(t['reader'])for t in times.values())==48,'Complete48 matched actual predictions required')
    require(all(not c['certificate_applied']and not c['prediction_changed']for cc in certificates.values()for c in cc),'Proof/semantic override applied')
    return rows,times,evidence,certificates

def timing_summary(times):
    return {name:{'n':len(v['reader']),**{key+'_p'+str(int(q*100))+'_seconds':quantile(v[key],q)
                for key in ['reader','forward','composite_local','context']for q in [.5,.95]},
            'native_query_n':len(v['native_query']),
            'native_query_p50_seconds':quantile(v['native_query'],.5)if v['native_query']else None,
            'native_query_p95_seconds':quantile(v['native_query'],.95)if v['native_query']else None,
            'scope':'Actual singleton observations. Reader includes pair preparation/model/readout; composite_local adds measured disabled-decision interval. Context/native search separate; embedding/index/init/cleanup excluded here and reported in whole-worker wall/resources. Forward is not an isolated CPU kernel.'}
        for name,v in times.items()}

def engineering_replay(rows,gate):
    labels=gate['expected_labels'];require(type(labels)is dict and set(labels)=={r[0]for r in expected('engineering')},'Exact12 retained joined labels required')
    require(digest(canonical(labels).encode())==AUTHORED_LABEL_MAP_SHA256,'Retained identity/label mapping differs from premeasurement authored semantic review')
    require(all(v in GOLD_NAMES for v in labels.values()),'Unknown retained authored label')
    require({c:sum(GOLD_NAMES[v]==c for v in labels.values())for c in CLASSES}==dict.fromkeys(CLASSES,4),'Exactly4E4C4N authored labels required')
    require([r['id']for r in rows]==[r[0]for r in expected('engineering')],'Retained label/output ordering differs')
    for row in rows:row['gold']=GOLD_NAMES[labels[row['id']]]
    scores={name:metrics(rows,name,expected_n=12)for name in ARMS.values()}
    checks=engineering_gates(scores);return all(checks.values()),scores,checks

def numeric_context_summary(corpus):
    rows=[]
    for case in corpus['cases']:
        for armname,arm in case['arms'].items():
            context=arm['context'];numeric=context['source_provenance'];literals=numeric['numeric_literals']
            rows.append({'id':case['id'],'arm':ARMS[armname],'source_characters':context['document_characters'],
                'retained_source_characters':context['retained_source_characters'],'source_character_coverage':context['document_character_coverage'],
                'numeric_occurrences':len(literals),'numeric_retained':numeric['numeric_literals_retained'],
                'numeric_omitted':numeric['numeric_literals_omitted'],
                'lexical_year_candidates':sum(n['lexical_year_candidate']for n in literals),
                'lexical_year_candidates_retained':sum(n['lexical_year_candidate']and n['retained']for n in literals),
                'joint_pair_tokens_observed':arm['joint_pair_tokens'],'full_supplied_input_context':arm['premise']==case['document']})
    aggregate={}
    for name in ARMS.values():
        rr=[r for r in rows if r['arm']==name];cov=[r['source_character_coverage']for r in rr]
        aggregate[name]={'contexts':len(rr),'coverage_min':min(cov),'coverage_p50':quantile(cov,.5),'coverage_max':max(cov),
            'full_supplied_input_contexts':sum(r['full_supplied_input_context']for r in rr),
            'observed_pair_tokens_min':min(r['joint_pair_tokens_observed']for r in rr),
            'observed_pair_tokens_max':max(r['joint_pair_tokens_observed']for r in rr),
            **{k:sum(r[k]for r in rr)for k in ['numeric_occurrences','numeric_retained','numeric_omitted','lexical_year_candidates','lexical_year_candidates_retained']}}
    return {'aggregate':aggregate,'observations':rows,'scope':'Exact source/UTF8/number provenance independently replayed by evidence audit, not arithmetic competence. Repeated per-context counts are not unique-document totals. Selected-source omission/retrieval miss cannot establish absence or insufficient evidence. True token counts are worker observations, not independently retokenized.'}

def evaluate(args):
    root=Path(args.project).resolve();planpath=Path(args.plan).resolve();plan,source=source_checks(root,planpath);planref=ref(root,planpath)
    rawpath=Path(args.raw).resolve();executionpath=Path(args.execution).resolve();closurepath=Path(args.closure).resolve()
    report={'schema_version':1,'epoch':35,'kind':KIND,'status':'REJECTED_ENGINEERING_INTEGRITY',
        'checks_passed':False,'engineering_passed':False,'readiness_qualified':False,'diagnostic_qualified':False,'engineering_only':True,'engineering_metrics':None,'engineering_checks':{},
        'benchmark_accuracy':None,'benchmark_accepted':False,'champion_promoted':False,'new_submission':False,
        'official_rank':None,'official_SOTA_verified':False,'training':[],'development':[],'calibration':[],'confirmation':[],
        'used_confirmation_identities':[],'failed_integrity_checks':[],'failed_engineering_checks':[],
        'original_annotated_source_json_parsed':False,'annotation_choices_accessed':0,
        'original_benchmark_oracle_traversals_by_scorer':0,'authored_oracle_traversals_by_scorer':0,
        'model_native_tokenizer_calls_by_scorer':0,'source_checks':source,
        'sampling_scope':'New authored CC0 engineering stress:12 distinct fictional supplied sources,4E4C4N. No benchmark, development, calibration or fresh-confirmation score.',
        'uncertainty':['No proof/override/onehot certificate; final forecasts equal measured raw T1.',
            'Same generic pretrained b354 and same E34 selector/packer; this tests engineering readiness, not a newly stronger model.',
            'Model training/selection/calibration and foundation lineage incomplete; confirmation/promotion/submission remain HOLD.',
            'Authored and intentionally class-balanced challenges are not representative benchmark estimates or independent publisher evaluation.',
            'Native retrieval is limited to supplied excerpts; missing retrieved evidence cannot prove source absence or insufficient evidence.'],
        'evidence':{'plan':ref(root,planpath),'raw':ref(root,rawpath)if rawpath.is_file()else None,'execution':ref(root,executionpath),
            'supervisor_observed_closure':ref(root,closurepath),'pretrained_model_source':plan['pretrained_model_source'],
            'scorer_source':ref(root,Path(__file__).resolve())}}
    try:
        # Every physical/execution/source check precedes interpreting retained labels.
        execution=read(executionpath);proof=read(closurepath)
        require(execution['plan_sha256']==planref['sha256'],'Captured execution differs from exact current frozen plan bytes')
        report['observed_execution_before_integrity_audit']=execution
        report['captured_execution']=execution
        observed=supervisor_closure(root,{'supervisor_observed_closure':ref(root,closurepath),'supervisor_closure_value':proof})
        report['supervisor_physical_closure']=observed
        report['physical_ownership_closure']=physical_ownership_closure(execution)
        # Raw JSON retains the already joined authored labels, so even parsing
        # this raw capture waits until both physical closure checks pass.
        pub=publisher(root,plan);phase=pub.phase_evidence(root,'engineering',planref,required=True)
        report['actual_execution']=pub.aggregate_actual(phase)
        require(phase['raw']==report['evidence']['raw']and phase['execution']==ref(root,executionpath)
                and phase['supervisor_observed_closure']==ref(root,closurepath),'Canonical receipt projection differs from explicit supplied evidence')
        raw=phase['raw_value']
        if raw is not None:
            report['observed_raw_counters_before_integrity_audit']=raw.get('counters')
            report['observed_raw_errors_before_integrity_audit']=raw.get('errors')
            report['observed_raw_status_before_integrity_audit']=raw.get('status')
        require(pub.phase_completed(phase),'Canonical captured engineering phase incomplete/unknown')
        require(type(raw)is dict and raw['plan_sha256']==planref['sha256'],'Captured raw differs from exact current frozen plan bytes')
        require(raw['corpora']['engineering']['corpus_reservation']==phase['corpus_reservations']['engineering'],
                'Actual engineering corpus is not bound to the durable one-use reservation')
        integrity=phase_integrity(root,raw,execution,plan);model=audit_model(raw);pretrained=pretrained_source(root,plan)
        inheritance=policy_inheritance(root)
        bank=read(root/plan['engineering_inputs_path'],plan['engineering_inputs_sha256'])
        rows,times,evidence,certificates=role_outputs(root,raw['corpora']['engineering'],bank,plan)
        require(raw['counters']['native_insertions_completed']==evidence['source_index_vectors']
                and raw['counters']['native_hit_source_validations']==evidence['native_hits_verified'],'Native source vector/hit totals differ')
        gate=raw['engineering_gate']
        require(gate['all48_predictions_completed_before_oracle_read']is True
                and gate['all48_finite_true_pair_source_numeric_integrity']is True
                and gate['DEV_bank_read_before_gate']is False and gate['benchmark_generalization_claim']is False,
                'Single post-readout authored label join provenance not established')
        oracle_ref={p['path']:p for p in plan['pins']}[plan['engineering_oracle_path']]
        require(gate['oracle']==oracle_ref and gate['n']==12,'Authored oracle hash/size/case count binding differs')
        require(raw['counters']['engineering_oracle_expected_labels_accessed']==12
                and raw['counters']['engineering_oracle_reads']==1 and raw['counters']['engineering_native_predictions_compared']==12,'Authored oracle exactly-once12-label join differs')
        passed,scores,checks=engineering_replay(rows,gate)
        for armname,name in ARMS.items():
            worker=gate['proper_scores_by_arm'][armname];independent=scores[name]
            require(all(type(worker[key])in(int,float)and math.isfinite(worker[key])
                        and abs(worker[key]-independent[target])<=1e-12
                        for key,target in [('brier','Brier'),('nll','NLL_clipped_1e-12'),('NLL_clipped_1e-12','NLL_clipped_1e-12')])
                    and worker['NLL_clip_count']==independent['NLL_clip_count']
                    and worker['unclipped_NLL_finite']is independent['unclipped_NLL_finite'],
                    'Worker/independent proper score or clipping differs: '+armname)
        require(gate['passed']is passed and gate['native_correct']==scores['native']['correct']
                and gate['correct_by_arm']=={arm:scores[name]['correct']for arm,name in ARMS.items()}
                and gate['by_class']=={label:scores['native']['by_class'][gold]for label,gold in GOLD_NAMES.items()},
                'Worker/independent authored gate counts differ')
        require(raw['status']==('ENGINEERING_ADMISSION_PASSED'if passed else'ENGINEERING_ADMISSION_FAILED'),'Runtime semantic status differs from frozen independent gate')
        report.update(checks_passed=True,engineering_passed=passed,readiness_qualified=passed,
            status='ACCEPTED_ENGINEERING_ADMISSION_ONLY'if passed else'REJECTED_ENGINEERING_ADMISSION',
            engineering_metrics=scores,engineering_checks=checks,failed_engineering_checks=[k for k,v in checks.items()if not v],
            paired_differences=paired_differences(scores),engineering_timing=timing_summary(times),
            engineering_context_audit=evidence,numeric_context=numeric_context_summary(raw['corpora']['engineering']),
            raw_T1_decision_certificates=certificates,pretrained_model_audit=model,pretrained_source_audit=pretrained,
            unchanged_E34_policy_inheritance=inheritance,
            phase_integrity=integrity,supervisor_physical_closure=observed,
            actual_operation_counters=raw['counters'],actual_resources=raw['resources'],
            authored_labels_recomputed_from_existing_joined_records=12,
            errors_by_arm={name:[r for r in m['scores']if not r['correct']]for name,m in scores.items()})
    except (ValueError,KeyError,TypeError,IndexError,FileNotFoundError)as error:
        report['failed_integrity_checks'].append(type(error).__name__+': '+str(error))
    write_new(args.output,report);return report

def bind(args):
    root=Path(args.project).resolve();replay=read(Path(args.replay).resolve());results=read(Path(args.results).resolve())
    require(replay['epoch']==35 and replay['kind']==KIND,'Wrong engineering qualification replay')
    for key,value in replay.items():require(results.get(key)==value,'Result differs from frozen engineering replay: '+key)
    require(results['benchmark_accuracy']is None and results['used_confirmation_identities']==[]
            and all(results[k]is False for k in ['benchmark_accepted','champion_promoted','new_submission','official_SOTA_verified'])
            and results['official_rank']is None,'Forbidden benchmark/promotion/confirmation claim')
    for pin in replay['evidence'].values():
        if pin is not None:checked(root,pin)
    report=json.loads(json.dumps(replay));report['evaluated_integrity_checks_passed']=replay['checks_passed']
    report['publication_binding_checks_passed']=True;report['checks_passed']=True
    report['evidence']['results']=ref(root,Path(args.results).resolve());report['evidence']['qualification_replay']=ref(root,Path(args.replay).resolve())
    write_new(args.output,report);return report

if __name__=='__main__':
    p=argparse.ArgumentParser();sub=p.add_subparsers(dest='mode',required=True)
    ev=sub.add_parser('evaluate')
    for n in ['project','plan','raw','execution','closure','output']:ev.add_argument('--'+n,required=True)
    bi=sub.add_parser('bind')
    for n in ['project','replay','results','output']:bi.add_argument('--'+n,required=True)
    a=p.parse_args();r=evaluate(a)if a.mode=='evaluate'else bind(a)
    print(json.dumps({'status':r['status'],'checks_passed':r['checks_passed'],'engineering_passed':r['engineering_passed']}))
