"""Independent stdlib arithmetic replay of already-joined E34 outputs; no source gold I/O."""
from pathlib import Path
import collections, hashlib, json, math, os

W = Path('/workspace/ruvector-epoch34-047dbc740dc2')
R = W / 'project'
A = Path('/workspace/ruvector-e34-independent-audit')
P = 'experiments/sota-2026-10-22/'
CLASSES = ['entailment', 'contradiction', 'not_mentioned']
NATIVE = ['entailment', 'not_mentioned', 'contradiction']
TYPED = ['Entailment', 'NotMentioned', 'Contradiction']
ARMS = {'actual_native':'native', 'native_original':'native_original', 'lexical':'lexical', 'positional':'positional'}
DOCS = [434,367,247,377,220,457,169,449]

def need(ok, msg):
    if not ok: raise ValueError(msg)

def ref(p):
    b=p.read_bytes(); return {'path':str(p),'bytes':len(b),'sha256':hashlib.sha256(b).hexdigest()}

def read(p, sha=None):
    b=p.read_bytes()
    if sha: need(hashlib.sha256(b).hexdigest()==sha, 'Hash differs: '+str(p))
    return json.loads(b)

def close(a,b):
    need(math.isfinite(a) and math.isfinite(b) and abs(a-b)<1e-11, 'Numerical mismatch')

def q(values,p):
    s=sorted(values); pos=(len(s)-1)*p; lo=math.floor(pos); hi=math.ceil(pos)
    return s[lo]+(s[hi]-s[lo])*(pos-lo)

def metrics(rows):
    n=len(rows); confusion={g:dict.fromkeys(CLASSES,0) for g in CLASSES}
    for r in rows: confusion[r['gold']][r['prediction']]+=1
    return {'n':n,'correct':sum(r['correct'] for r in rows),
        'accuracy':sum(r['correct'] for r in rows)/n,
        'Brier':math.fsum(r['Brier'] for r in rows)/n,
        'NLL_clipped_1e-12':math.fsum(r['NLL_clipped_1e-12'] for r in rows)/n,
        'NLL_clip_count':sum(r['NLL_clipped'] for r in rows),
        'unclipped_NLL_finite':all(r['unclipped_NLL_finite'] for r in rows),
        'by_class':{g:{'n':sum(confusion[g].values()),'correct':confusion[g][g]} for g in CLASSES},
        'confusion':confusion}

def main():
    replay=read(W/'qualification-replay.json','18416d8eb9f2092bc634398915ba868c11719b5e21f888843e9456c69b1781bd')
    raw=read(R/(P+'epoch34/runs/dev/raw.json'),'86c31223fedcc0d1a83b12becc9bb70b8433db8391f65effe13e64860c0407bd')
    execution=read(R/(P+'epoch34/runs/dev/execution.json'),'48daf6fd3e4292620b609d2abb59d9b7fff7b36f0367a36d993bd3de168d12af')
    closure=read(R/(P+'epoch34/SUPERVISOR_OBSERVED_CLOSURE.json'),'2ae8b02057ca6b1e19bb1fd0a252bbdd7b6554ec8ad34f3ca0fecd653b9ba88a')
    plan=read(R/(P+'epoch34/plan.json'),'53ea8a9341154b3a0612712c7e73fd56d56fba279bd4ec6343471f2c5e052839')
    freeze=read(R/(P+'epoch34/source-freeze.json'),'b9add85c349b8004141054dbadc15bce08338d6c187f53e9b6130323e304e0e9')
    need(replay['checks_passed'] and replay['failed_integrity_checks']==[], 'Scorer integrity did not pass')
    need(plan['data_roles']=={'train':[],'dev':DOCS,'calibration':[],'confirmation':[]}, 'Roles differ')
    need(plan['proof_enabled_roles']==[] and raw['errors']==[], 'Proof or worker errors')
    for row in replay['evidence'].values():
        if row: need(ref(R/row['path'])=={**row,'path':str(R/row['path'])}, 'Replay evidence mismatch')
    gold_rows={name:{r['id']:r for r in replay['metrics'][name]['scores']} for name in ARMS.values()}
    for name in ARMS.values():
        need(set(gold_rows[name])==set(gold_rows['native']), 'Unmatched scored identities')
    computed={}; all_rows={}; timings={}; paired={}; errors={}; regressions={}
    raw_cases=raw['corpora']['dev']['cases']
    need([r['document_id'] for r in raw_cases]==[d for d in DOCS for _ in range(3)], 'Frozen DEV order differs')
    need([r['hypothesis_id'] for r in raw_cases]==['nda-17','nda-7','nda-3']*8, 'Frozen hypotheses differ')
    need(len(raw['corpora']['engineering']['cases'])==6 and len(raw_cases)==24, 'Role case counts differ')
    checked=0
    for role,metric_key,timing_key in [('engineering','engineering_metrics','engineering_timing'),('dev','metrics','reader_timing')]:
        cases=raw['corpora'][role]['cases']; gold={n:{s['id']:s for s in replay[metric_key][n]['scores']} for n in ARMS.values()}
        role_scores={}; role_rows={}
        for arm,name in ARMS.items():
            rows=[]; ts={k:[] for k in ['reader','forward','composite_local','context','native_query']}
            for case in cases:
                a=case['arms'][arm]; reader=a['reader']; decision=a['decision']; scored=gold[name][case['id']]
                logits=reader['raw_logits_E_N_C']; z=max(logits); mass=math.fsum(math.exp(v-z) for v in logits)
                pn=[math.exp(v-z)/mass for v in logits]; pc=[pn[0],pn[2],pn[1]]
                for actual,expected in zip(reader['probabilities_E_C_N'],pc): close(actual,expected)
                for actual,expected in zip(reader['probabilities_E_N_C'],pn): close(actual,expected)
                need(reader['temperature']==1 and reader['calibrated'] is False, 'Calibrated readout')
                idx=max(range(3),key=lambda i:logits[i]); pred=NATIVE[idx]
                need(reader['native_label_index']==idx and reader['native_typed_argmax']==TYPED[idx], 'Typed argmax differs')
                need(scored['prediction']==pred and scored['gold']==gold['native'][case['id']]['gold'], 'Scored mapping/gold differs')
                need(decision['certificate'] is None and decision['semantic_decision_override'] is False, 'Unexpected decision proof')
                need(decision['raw_probabilities_E_C_N']==reader['probabilities_E_C_N']==decision['final_probabilities_E_C_N'], 'Decision changed probability')
                need(decision['raw_typed_argmax']==reader['native_typed_argmax']==decision['final_typed_argmax'], 'Decision changed argmax')
                need(reader['hidden_truncation'] is False and reader['pair_tokens']==reader['full_pair_tokens']==a['joint_pair_tokens']<=512, 'Pair cap/truncation differs')
                need(a['context']['all_selected_groups_complete'] is True and not a['context']['claim_truncated'] and not a['context']['selected_evidence_truncated'], 'Incomplete context')
                need(len(a['context']['mandatory_ranked_group_ids'])==min(2,len(a['context']['source_sentence_groups'])), 'Mandatory group count differs')
                g=scored['gold']; p=dict(zip(CLASSES,pc)); br=math.fsum((p[c]-int(c==g))**2 for c in CLASSES); nl=-math.log(max(p[g],1e-12))
                close(br,scored['Brier']); close(nl,scored['NLL_clipped_1e-12'])
                for c in CLASSES: close(scored['probabilities'][c],p[c])
                row={'id':case['id'],'document_id':case['document_id'],'gold':g,'prediction':pred,'correct':int(pred==g),'Brier':br,'NLL_clipped_1e-12':nl,'NLL_clipped':p[g]<1e-12,'unclipped_NLL_finite':p[g]>0}
                need(row['correct']==scored['correct'], 'Correctness differs'); rows.append(row)
                for k in ['reader','forward']: ts[k].append(reader[k+'_seconds'])
                ts['composite_local'].append(reader['reader_seconds']+a['decision_seconds']); ts['context'].append(a['context_seconds'])
                if a['native_query_seconds'] is not None: ts['native_query'].append(a['native_query_seconds'])
                checked+=1
            result=metrics(rows); reported=replay[metric_key][name]
            for k in ['Brier','NLL_clipped_1e-12','accuracy']: close(result[k],reported[k])
            for k in ['n','correct','NLL_clip_count','unclipped_NLL_finite','by_class','confusion']: need(result[k]==reported[k], 'Aggregate differs '+k)
            for kind,values in ts.items():
                if values:
                    for percentile in [.5,.95]: close(q(values,percentile),replay[timing_key][name][kind+'_p'+str(round(percentile*100))+'_seconds'])
            role_scores[name]=result;role_rows[name]=rows
            if role=='dev':
                timings[name]=replay[timing_key][name]; errors[name]=[r for r in rows if not r['correct']]
        computed[role]=role_scores
        if role=='dev': all_rows=role_rows
    need(checked==120,'Not 120 actual readouts')
    primary=computed['dev']['native']; gates={'every_gold_class_present':all(primary['by_class'][c]['n']>0 for c in CLASSES),'native_one_correct_per_class':all(primary['by_class'][c]['correct']>0 for c in CLASSES)}
    for name in ['native_original','lexical','positional']:
        other=computed['dev'][name]
        for key,good in [('Brier_nonincrease',primary['Brier']<=other['Brier']+1e-12),('NLL_nonincrease',primary['NLL_clipped_1e-12']<=other['NLL_clipped_1e-12']+1e-12),('correct_gain_at_least2',primary['correct']>=other['correct']+2)]:gates[name+':'+key]=good
        groups=[]; improved=[]; regressed=[]; changed=[]
        for doc in DOCS:
            pairs=[(a,b) for a,b in zip(all_rows['native'],all_rows[name]) if a['document_id']==doc]
            need(len(pairs)==3 and all(a['id']==b['id'] and a['gold']==b['gold'] for a,b in pairs),'Paired cluster mismatch')
            groups.append({'document_id':doc,'n':3,'native_minus_correct':sum(a['correct']-b['correct'] for a,b in pairs),'native_minus_Brier_sum':math.fsum(a['Brier']-b['Brier'] for a,b in pairs),'native_minus_NLL_sum':math.fsum(a['NLL_clipped_1e-12']-b['NLL_clipped_1e-12'] for a,b in pairs)})
            for a,b in pairs:
                if a['prediction']!=b['prediction']:changed.append(a['id'])
                if a['correct']>b['correct']:improved.append(a['id'])
                if a['correct']<b['correct']:regressed.append(a['id'])
        reported=replay['paired_differences'][name]
        for actual,old in zip(groups,reported['document_clusters']):
            need(actual['document_id']==old['document_id'] and actual['native_minus_correct']==old['native_minus_correct'],'Document difference differs')
            close(actual['native_minus_Brier_sum'],old['native_minus_Brier_sum']);close(actual['native_minus_NLL_sum'],old['native_minus_NLL_sum'])
        paired[name]={'native_minus_correct':primary['correct']-other['correct'],'native_minus_Brier':primary['Brier']-other['Brier'],'native_minus_NLL':primary['NLL_clipped_1e-12']-other['NLL_clipped_1e-12'],'document_clusters':groups,'case_accuracy_improvements':improved,'case_accuracy_regressions':regressed,'prediction_changes':changed,'cluster_sign_counts':{'positive':sum(x['native_minus_correct']>0 for x in groups),'zero':sum(x['native_minus_correct']==0 for x in groups),'negative':sum(x['native_minus_correct']<0 for x in groups)}}
    gates.update({'raw_native:correct_nondecrease':True,'raw_native:Brier_nonincrease':True,'raw_native:NLL_nonincrease':True})
    need(gates==replay['diagnostic_checks'] and all(gates.values()),'Frozen diagnostic gates differ/fail')
    need(all(computed['engineering'][n]['correct']==6 for n in ARMS.values()),'Engineering regression mismatch')
    need(execution['status']=='WORKER_COMPLETED' and execution['exit_code']==0 and execution['stdout_stderr_capture_completed'] and execution['owned_live_processes_closed'],'Captured execution incomplete')
    need(execution['wall_seconds_including_init_cleanup']<=600 and execution['CPU_affinity']==[0,1], 'Resource budget violation')
    expected_counters={'NLI_forward_calls_completed':120,'NLI_forward_calls_attempted':120,'ENGINEERING_forward_calls_completed':24,'DEV_forward_calls_completed':96,'native_queries_completed':30,'native_queries_attempted':30,'corpus_batches_attempted':2,'corpus_batches_completed':2,'native_index_initializations_completed':14,'native_binary_loads_completed':2,'native_insertions_completed':552,'CONF_input_bank_reads':0,'CONF_annotation_choices_accessed':0,'TRAIN_annotation_choices_accessed':0,'DEV_annotation_choices_accessed':0,'TRAIN_forward_calls_completed':0,'calibration_calls':0,'paid_calls':0,'GPU_calls':0,'HTTP_requests':0,'training_steps':0,'optimizer_steps_completed':0}
    for k,v in expected_counters.items():need(raw['counters'][k]==v and execution['raw_operation_counters'][k]==v,'Counter differs '+k)
    need(raw['model_state_unchanged'] and raw['native_child_closed'] and raw['Python_network_violations']==[], 'State/process/network violation')
    need(closure['physical_closure_passed'] and closure['physical_supervisor_closed'] and closure['owned_worker_group_members']==[] and closure['unknown_physical_ownership'] is False,'Physical closure absent')
    access=[json.loads(x) for x in (R/(P+'audit/epoch34/DEV_GOLD_ACCESS.jsonl')).read_text().splitlines()]
    need([x['attempt'] for x in access]==list(range(1,25)) and [x['id'] for x in access]==[r['id'] for r in raw_cases], 'One-time gold access log differs')
    need(replay['annotation_choices_attempted']==replay['annotation_choices_accessed']==24 and replay['model_native_tokenizer_calls_by_scorer']==0 and replay['other_role_annotation_choices_accessed']==0 and replay['source_evidence_lists_accessed']==0,'Scorer operation scope differs')
    need(not replay['champion_promoted'] and not replay['benchmark_accepted'] and not replay['new_submission'] and not replay['official_SOTA_verified'],'Promotion/official claim mismatch')
    need(replay['confirmation']==[] and replay['calibration']==[], 'Confirmation/calibration not empty')
    report={'schema_version':1,'epoch':34,'kind':raw['kind'],'checks_passed':True,
        'decision':'ACCEPT_DEV_DIAGNOSTIC_ONLY_HOLD_CONFIRMATION_PROMOTION_SUBMISSION',
        'frozen_DEV_gates_passed':True,'engineering_passed':True,'confirmation_eligible':False,
        'champion_promoted':False,'benchmark_accepted':False,'new_submission':False,'official_SOTA_verified':False,
        'scope':'Independent stdlib replay from immutable raw logits and existing scorer-joined per-case scores; no original source/gold annotation read, model, native, tokenizer, EVALUATE, BIND, or Git mutation.',
        'evidence':{n:ref(p) for n,p in {'qualification_replay':W/'qualification-replay.json','raw':R/(P+'epoch34/runs/dev/raw.json'),'execution':R/(P+'epoch34/runs/dev/execution.json'),'physical_closure':R/(P+'epoch34/SUPERVISOR_OBSERVED_CLOSURE.json'),'plan':R/(P+'epoch34/plan.json'),'freeze':R/(P+'epoch34/source-freeze.json'),'independent_source_actual_readback':A/'source-actual-readback-independent-v1.json','audit_source':Path(__file__)}.items()},
        'actual_readouts_independently_replayed':checked,'metrics':computed,'diagnostic_checks':gates,'paired_differences':paired,'errors':errors,'reader_timing':timings,
        'used_confirmation_identities':[],'permanently_exposed_DEV_document_ids':DOCS,'train_ids':[],'calibration_ids':[],
        'resources':{k:execution[k] for k in ['wall_seconds_including_init_cleanup','children_user_seconds','children_system_seconds','largest_child_peak_RSS_bytes','CPU_affinity']},
        'operation_counters_verified':expected_counters,'physical_closure_semantics':{'supervisor_state':'Z','supervisor_absent':False,'supervisor_closed':True,'root_supervisor_exit_code_observed':False},
        'limitations':['Eight correlated source documents, 24 cases; no population superiority or benchmark generalization claim.','Two-correct gain meets the frozen threshold exactly; case regressions and document concentration retained.','All four arms share the NEW E34 complete-source-group packer; native_original is original native ranking under that packer, not reproduction of E33 context.','Same pretrained reader, raw T1 all roles; no stronger-reader benefit or learned model improvement claim.','Incomplete pretrained training lineage keeps confirmation and promotion on HOLD, regardless DEV improvement.','Authored engineering six are exposed regression only; not benchmark validation.','Source-group selection independently audited in frozen scorer; token-budget replay uses observed source-bound counts and does not independently retokenize.','Actual local per-case timings exclude amortized indexing/init/cleanup; inclusive worker wall/RSS reported separately.','No RuVector official JevBench/ClaimBench result, rank or eligibility verified.']}
    target=A/'independent-acceptance-rejection-v1.json';b=(json.dumps(report,sort_keys=True,indent=2,allow_nan=False)+'\n').encode()
    fd=os.open(target,os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,0o600)
    try:
        with os.fdopen(fd,'wb',closefd=False) as f:f.write(b);f.flush();os.fsync(fd)
    finally:os.close(fd)
    d=os.open(A,os.O_RDONLY|os.O_DIRECTORY);os.fsync(d);os.close(d)
    print(json.dumps(ref(target),sort_keys=True))

if __name__=='__main__':main()
