from pathlib import Path
S=Path(__file__).resolve().parents[2];src=(S/'audit/epoch9/replay_actual_v2.py').read_text()
def rep(a,b):
 global src
 assert a in src,a[:100];src=src.replace(a,b)
rep('epoch9 replay','epoch10 replay');rep("study=s/'epoch9'","study=s/'epoch10'")
rep("completion['prior_closed_attempts']==11 and completion['lifetime_native_attempt']==11+expected_number","completion['prior_closed_attempts']==12 and completion['lifetime_native_attempt']==12+expected_number")
rep("attempt['lifetime_native_attempt']==11+expected_number","attempt['lifetime_native_attempt']==12+expected_number")
rep("assert completion['exit_code']==0 and completion['error'] is None and completion['source_plan_unchanged']", "assert completion['source_plan_unchanged']")
rep("len(se)==len(st)=={'development':24,'confirmation':48}[phase]","len(se)==len(st)==({'development':96,'confirmation':48}[phase] if completion['exit_code']==0 else len(a))")
rep("assert sha(run/'records.jsonl')==report['records_sha256'] and sha(run/'wire.jsonl')==report['wire_sha256']", "\n  if completion['exit_code']==0:assert sha(run/'records.jsonl')==report['records_sha256'] and sha(run/'wire.jsonl')==report['wire_sha256']")
rep("assert report[phase+'_completed']==len(a)","assert sum(report[k+'_completed'] for k in ['train','development','confirmation'])==len(a)")
rep("summary['lifetime_native_attempts']==11+len(phase_evidence)","summary['lifetime_native_attempts']==12+len(phase_evidence)")
rep("expected={phase:rows(project/path) for phase,path in plan['datasets'].items()};byphase={phase:[x for x in actual if x['measured_phase']==phase] for phase in expected}","expected={phase:rows(project/path) if phase!='confirmation' or 'confirmation' in phase_evidence else [] for phase,path in plan['datasets'].items()};byphase={phase:[x for x in actual if x['measured_phase']==phase] for phase in expected}")
rep("assert len(byphase['development'])==24 and len(byphase['confirmation']) in [0,48]", "assert len(byphase['train'])==72 and len(byphase['development']) in [0,24] and len(byphase['confirmation']) in [0,48]")
rep("ordered=expected['development']+", "ordered=expected['train']+(expected['development'] if byphase['development'] else [])+")
rep("phase_counts={phase:{'BGE_texts':0,'BGE_batches':0,'NLI_tokens':0} for phase in phase_evidence}","phase_counts={phase:{'BGE_texts':0,'BGE_batches':0,'NLI_tokens':0} for phase in expected}")
rep("phase=rec['measured_phase'];run=study/'runs'/phase;ev=phase_evidence[phase]", "phase=rec['measured_phase'];process_phase='development' if phase=='train' else phase;run=study/'runs'/process_phase;ev=phase_evidence[process_phase]")
rep("assert dec['probabilities']==p and dec['temperature']==1.","assert dec['temperature']==1.") if "assert dec['probabilities']==p and dec['temperature']==1." in src else None
# Raw backbone binary prediction is replaced by the shared frozen TRAIN head on fresh evaluation.
a="logits=np.asarray(dec['logits'],dtype=np.float64);assert logits.shape==(3,) and np.isfinite(logits).all();prob=np.exp(logits-logits.max());prob/=prob.sum();close(p['Yes'],prob[0]);close(p['No'],prob[1]+prob[2]);typed={'Entailment':float(prob[0]),'Contradiction':float(prob[2]),'NotMentioned':float(prob[1])};assert dec['raw_threeway_probabilities']==typed and dec['canonical_logits_E_C_N']==[float(logits[i]) for i in (0,2,1)]"
b="""logits=np.asarray(dec['logits'],dtype=np.float64);assert logits.shape==(3,) and np.isfinite(logits).all();prob=np.exp(logits-logits.max());prob/=prob.sum();rawtyped={'Entailment':float(prob[0]),'Contradiction':float(prob[2]),'NotMentioned':float(prob[1])};canonical_logits=[float(logits[i]) for i in (0,2,1)];assert dec['raw_threeway_probabilities']==rawtyped and dec['canonical_logits_E_C_N']==canonical_logits and dec['typed_head_canonical_logits']==canonical_logits
   features=feature_module.extract(premise,hyp,canonical_logits);assert features==dec['typed_head_features'] and dec['typed_head_feature_names']==list(feature_module.FEATURE_NAMES)
   if phase=='train':
    typed=rawtyped;assert dec['typed_head_state']=='TRAIN_COLLECTION' and dec['annotation_overlap_probability'] is None
   else:
    assert fitted_artifact is not None and dec['typed_head_state']=='FROZEN';af=fitted_artifact['auxiliary_final'];r=np.asarray(features);az=((r-np.asarray(af['mean']))/np.asarray(af['scale']))@np.asarray(af['weights']);aux=float(np.exp(-np.logaddexp(0.,-az)));close(aux,dec['annotation_overlap_probability']);b=np.asarray(canonical_logits);z=b-b.mean()+((np.r_[r,aux]-np.asarray(fitted_artifact['mean']))/np.asarray(fitted_artifact['scale']))@np.asarray(fitted_artifact['weights']);t=np.exp(z-z.max());t/=t.sum();typed=dict(zip(['Entailment','Contradiction','NotMentioned'],map(float,t)))
   for k,v in typed.items():close(v,dec['typed_threeway_probabilities'][k])
   close(p['Yes'],typed['Entailment']);close(p['No'],typed['Contradiction']+typed['NotMentioned'])"""
start=src.index("   logits=np.asarray(dec['logits']");end=src.index("\n   typedgold=",start)
src=src[:start]+'   '+b+src[end:]
rep("context=module(s/'candidate/epoch6/context.py'", "feature_module=module(s/'candidate/epoch10/features.py','epoch10_saved_features');fitted_artifact=obj(study/'fitted-head.json') if (study/'fitted-head.json').exists() else None\n context=module(s/'candidate/epoch6/context.py'")
rep("count=len(byphase[phase]);pc=phase_counts[phase]", "count=len(byphase[phase])+(len(byphase['train']) if phase=='development' else 0);pc={k:phase_counts[phase][k]+(phase_counts['train'][k] if phase=='development' else 0) for k in phase_counts[phase]}")
# Replace all aggregate/gate/result logic after the independently verified raw request loop.
src=src[:src.index(" metrics={phase:")]+'''
 allmetrics={phase:{name:{'n':len(vals),'correct':sum(x['correct'] for x in vals),'brier':statistics.mean(x['brier'] for x in vals),'nll':statistics.mean(x['nll'] for x in vals),'errors':0,'strict_valid':len(vals)} for name,vals in arm.items()} for phase,arm in scores.items() if byphase[phase]}
 metrics={k:v for k,v in allmetrics.items() if k!='train'};trainmetrics=allmetrics.get('train');devgate=gate(metrics['development'],development=True) if 'development' in metrics else False
 for phase,phase_metrics in metrics.items():
  official=obj(study/'runs'/phase/(phase+'-comparison.json'))['metrics']
  for name,values in phase_metrics.items():
   for key,value in values.items():close(official[name][key],value)
 if byphase['development']:
  assert devgate==phase_evidence['development']['report']['development_gate_passed']==obj(study/'runs/development/development-comparison.json')['frozen_development_gate_passed']
 uncertainty={};holdout_pass=False
 for phase,rs in byphase.items():
  if not rs or phase=='train':continue
  groups=sorted({x['source_group'] for x in rs});assert len(groups)==(8 if phase=='development' else 16);assert all(sum(x['source_group']==g for x in rs)==3 for g in groups);uncertainty[phase]={}
  for name in ARMS:
   if name=='ruvector_top2':continue
   gains={key:[] for key in ['accuracy','brier','nll']}
   for g in groups:
    ix=[i for i,x in enumerate(rs) if x['source_group']==g]
    gains['accuracy'].append(statistics.mean(int(scores[phase]['ruvector_top2'][i]['correct'])-int(scores[phase][name][i]['correct']) for i in ix))
    for key in ['brier','nll']:gains[key].append(statistics.mean(scores[phase][name][i][key]-scores[phase]['ruvector_top2'][i][key] for i in ix))
   uncertainty[phase][name]={key:paired_bootstrap_interval(v) for key,v in gains.items()}
 admission=obj(study/'runtime-admission.json') if (study/'runtime-admission.json').exists() else None
 if admission:
  initialization=phase_evidence['development']['runtime']['receipt']['initialization_wall_seconds'];devmax=max(r['elapsed_s'] for r in byphase['development']);devunits=max(len(context.partition(r['input']['state'],nli,bge,target=128,nli_cap=160,bge_cap=256,max_units=192)) for r in expected['development']);assert devunits==plan['runtime_admission']['max_DEV_units']==admission['max_DEV_units']==23 and plan['runtime_admission']['max_confirmation_units']==admission['max_confirmation_units']==57
  projected=48*devmax*max(1,57/23)+2*initialization+60;close(projected,admission['projected_confirmation_seconds']);close(initialization,admission['DEV_initialization_seconds']);close(devmax,admission['max_DEV_HTTP_seconds']);remaining=plan['lease_expires_unix']-datetime.fromisoformat(admission['at']).timestamp();assert admission['allowed']==(projected<=600 and remaining>=projected+30)
 if byphase['confirmation']:
  assert devgate and admission['allowed'];lock=obj(study/'confirmation-selection-lock.json');assert lock['plan_sha256']==sha(study/'plan.json') and lock['development_comparison_sha256']==sha(study/'runs/development/development-comparison.json') and lock['runtime_admission_sha256']==sha(study/'runtime-admission.json') and lock['fitted_head_sha256']==sha(study/'fitted-head.json') and lock['fit_lock_sha256']==sha(study/'readout-fit-lock.json');assert lock['at']<=phase_evidence['confirmation']['attempt']['at']<=next(r['at'] for r in started if r['phase']=='confirmation')
  holdout_pass=gate(metrics['confirmation']) and all(uncertainty['confirmation'][name]['accuracy']['ci95'][0]>0 for name in uncertainty['confirmation']) and all(uncertainty['confirmation'][name][key]['ci95'][0]>=-1e-12 for name in uncertainty['confirmation'] for key in ['brier','nll'])
 else:
  assert not (study/'confirmation-selection-lock.json').exists() and not (study/'runs/confirmation/attempt.json').exists() and not any(r['phase']=='confirmation' for r in started)
  if byphase['development']:assert not devgate or not admission['allowed'];assert summary['status']==('REJECTED_DEV_GATE' if not devgate else 'BLOCKED_CONFIRMATION_RUNTIME_BUDGET')
  else:assert summary['status']=='FAILED_PRESERVED_EVIDENCE' and not phase_evidence['development']['report']['fit_complete']
 resources={phase:ev['resources'] for phase,ev in phase_evidence.items()};completion={phase:ev['completion'] for phase,ev in phase_evidence.items()}
 assert repeatdrift<1e-5
 fit_verifier=module(HERE/'verify_fit.py','epoch10_independent_saved_fits');fitproof=fit_verifier.run(project)
 result={'schema_version':1,'at':datetime.now(timezone.utc).isoformat(),'checks_passed':True,'status':summary['status'],'plan_SHA256':sha(study/'plan.json'),'source_pins_verified':len(plan['pins']),'metrics':{'development':metrics.get('development'),'confirmation':metrics.get('confirmation')},'train_prefit_metrics':trainmetrics,'multiclass_metrics':{phase:{name:{'n':len(vals),'correct':sum(x['correct'] for x in vals),'brier':statistics.mean(x['brier'] for x in vals),'nll':statistics.mean(x['nll'] for x in vals)} for name,vals in arms.items()} for phase,arms in threeway_scores.items() if byphase[phase]},'actual_successful_HTTP_by_corpus':{phase:len(rs) for phase,rs in byphase.items()},'training_feature_HTTP_requests':len(byphase['train']),'DEV_gate_passed':devgate,'internal_confirmation_gate_passed':holdout_pass,'confirmation_consumed':'confirmation' in phase_evidence,'confirmation_now_permanently_exposed_DEV':'confirmation' in phase_evidence,'paired_doc_bootstrap':uncertainty,'bootstrap_scope':'2000paired doc-group draws seed20261022, nominal unadjusted intervals; gainsaccuracy primary-control, properlosscontrol-primary','headfitdiagnostics':fitproof,'max_same_context_singleton_logit_drift':repeatdrift,'ANN_exact_top2_set_agreement_count':sum(x['exact_top2_set_agreement'] for x in proofs),'ANN_exact_candidate_set_agreement_count':sum(x['exact_candidate_set_agreement'] for x in proofs),'ANN_full_order_agreement_count':sum(x['native_ranking_ids']==x['exact_cosine_ranking_ids'] for x in proofs),'arm_name_scope':'Legacytop2names alias40rankedanchors+neighbors under512; allsamehead/model; excerpt104differentreader.','actual_requests':N,'actual_NLI_singleton_pairs':N*3,'actual_NLI_input_tokens':nli_tokens,'actual_BGE_texts':text_count,'actual_BGE_batches':bge_batches,'resources':resources,'completion':completion,'phase_counts':phase_counts,'runtime_admission':admission,'study_completion':summary,'latency_by_phase_seconds':{phase:{'p50':statistics.median(x['elapsed_s'] for x in rs),'p95':float(np.percentile([x['elapsed_s'] for x in rs],95)),'max':max(x['elapsed_s'] for x in rs),'scope':'WholeHTTPall3NLIarms+native104excerpt+embedding/index, notprimarydeployment'} for phase,rs in byphase.items() if rs},'rows':proofs,'official_rank':None,'official_score':None,'SOTA_established':False,'generic_submitted_Jev104_RRF10_champions_unchanged':True,'auditor_native_calls':0,'auditor_ONNX_calls':0,'artifact_pins':[{'path':str(p.relative_to(project)),'bytes':p.stat().st_size,'sha256':sha(p)} for p in sorted(study.rglob('*')) if 'runs' in p.parts or p.name in ['fitted-head.json','readout-fit-lock.json','runtime-admission.json','study-completion.json','confirmation-selection-lock.json'] if p.is_file()]}
 args.out.write_text(json.dumps(result,indent=2)+'\\n');print(json.dumps({'checks_passed':True,'sha256':sha(args.out),'metrics':metrics,'DEV_gate':devgate,'confirmation_gate':holdout_pass,'confirmation_consumed':'confirmation' in phase_evidence}))

if __name__=='__main__':main()
'''
(S/'audit/epoch10/replay_actual.py').write_text(src)
