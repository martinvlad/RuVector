"""Prepare saved-output-only typed-head replay; source version frozen before outcomes."""
from pathlib import Path
O=Path(__file__).resolve().parent;S=O.parents[1]
x=(S/'audit/epoch7/replay_actual_v2.py').read_text().replace('epoch7 replay','epoch8 replay').replace("study=s/'epoch7'","study=s/'epoch8'")
x=x.replace("assert completion['prior_closed_attempts']==8 and completion['lifetime_native_attempt']==8+expected_number","assert completion['prior_closed_attempts']==9 and completion['lifetime_native_attempt']==9+expected_number")
x=x.replace("attempt['lifetime_native_attempt']==8+expected_number", "attempt['lifetime_native_attempt']==9+expected_number")
x=x.replace("8+len(phase_evidence)","9+len(phase_evidence)")
x=x.replace("  assert runtime['receipt']['old_base_NLI_session_initialized'] is False and runtime['receipt']['unchanged_epoch6_context_policy'] is True\n  assert runtime['receipt']['nli']['classes']==2 and runtime['receipt']['nli']['label_indices']=={'entailment':0,'not_entailment':1}\n", "  assert runtime['receipt']['nli']['label_indices']=={'contradiction':0,'entailment':1,'neutral':2}\n")
x=x.replace("=={'development':24,'confirmation':96}[phase]", "==96")
x=x.replace("assert report[phase+'_completed']==len(a)", "assert report[phase+'_completed']==(24 if phase=='development' else 96)\n  if phase=='development':assert report['train_completed']==72 and report['fit_attempted'] and report['fit_complete']")
x=x.replace("ordered=expected['development']+(expected['confirmation'] if byphase['confirmation'] else [])", "assert len(byphase['train'])==72\n ordered=expected['train']+expected['development']+(expected['confirmation'] if byphase['confirmation'] else [])")
a=x.index(" model_tokenizer=Tokenizer.from_file");b=x.index(" context=module",a)
x=x[:a]+" config=obj(s/'candidate/epoch4/assets/nli-base/config.json');assert config['id2label']=={'0':'contradiction','1':'entailment','2':'neutral'}\n artifact=obj(study/'fitted-head.json');features=module(s/'candidate/epoch8/features.py','epoch8_pure_features');weights=np.asarray(artifact['weights']);headmean=np.asarray(artifact['mean']);headscale=np.asarray(artifact['scale'])\n"+x[b:]
x=x.replace("phase_counts={phase:{'BGE_texts':0,'BGE_batches':0,'NLI_tokens':0} for phase in phase_evidence}", "phase_counts={phase:{'BGE_texts':0,'BGE_batches':0,'NLI_tokens':0} for phase in expected}")
x=x.replace("run=study/'runs'/phase;ev=phase_evidence[phase];", "process_phase='development' if phase in ('train','development') else 'confirmation';run=study/'runs'/process_phase;ev=phase_evidence[process_phase];")
x=x.replace("policy_enc=nli.encode(premise,hyp);enc=model_tokenizer.encode(premise,hyp);dec=ad['decoding'];assert dec['frozen_epoch6_policy_pair_tokens']==len(policy_enc.ids)==coverage['joint_pair_tokens']<=512;assert dec['actual_model_pair_tokens']==len(enc.ids)<=512;", "enc=nli.encode(premise,hyp);dec=ad['decoding'];assert coverage['joint_pair_tokens']==len(enc.ids)<=512;")
a=x.index("   logits=np.asarray(dec['logits']");b=x.index("   h=dec['input_text_sha256']",a)
x=x[:a]+'''   logits=np.asarray(dec['logits'],dtype=np.float64);assert logits.shape==(3,) and np.isfinite(logits).all();prob=np.exp(logits-logits.max());prob/=prob.sum();assert dec['pool']=='One joint evidence premise; no per-chunk maximum';assert answer['model']=='Xenova/nli-deberta-v3-base@80a99030ce45a69a39ea2a6f50756d03859ff521'
   for j,label in config['id2label'].items():close(dec['nli_probabilities'][label],prob[int(j)])
   canonical_logits=np.asarray([logits[1],logits[0],logits[2]]);fv=features.extract(premise,hyp,canonical_logits);assert dec['typed_head_feature_names']==list(features.FEATURE_NAMES) and dec['typed_head_features']==fv;assert dec['typed_head_canonical_logits']==canonical_logits.tolist();classes=['Entailment','Contradiction','NotMentioned']
   for j,label in enumerate(classes):close(dec['raw_threeway_probabilities'][label],prob[[1,0,2][j]])
   if phase=='train':
    assert dec['typed_head_state']=='TRAIN_COLLECTION' and response['typed_head']['artifact_sha256'] is None;post=prob[[1,0,2]]
   else:
    assert dec['typed_head_state']=='FROZEN' and response['typed_head']['artifact_sha256']==sha(study/'fitted-head.json');z=canonical_logits-canonical_logits.mean()+((np.asarray(fv)-headmean)/headscale)@weights;post=np.exp(z-z.max());post/=post.sum()
   for j,label in enumerate(classes):close(dec['typed_threeway_probabilities'][label],post[j])
   close(p['Yes'],post[0]);close(p['No'],post[1]+post[2])
''' +x[b:]
x=x.replace("counters=ev['final-engine']['execution_after_close']['counters'];count=len(byphase[phase]);pc=phase_counts[phase]", "counters=ev['final-engine']['execution_after_close']['counters'];corpora=['train','development'] if phase=='development' else ['confirmation'];count=sum(len(byphase[c]) for c in corpora);pc={k:sum(phase_counts[c][k] for c in corpora) for k in ['BGE_texts','BGE_batches','NLI_tokens']}")
x=x.replace(" for phase,phase_metrics in metrics.items():\n  official=", " for phase,phase_metrics in metrics.items():\n  if phase=='train':continue\n  official=")
x=x.replace("  if not rs:continue\n  groups=", "  if not rs or phase=='train':continue\n  groups=")
x=x.replace("source_counts={phase:max(len(context.partition", "source_counts={phase:max(len(context.partition")
x=x.replace("for phase,records in expected.items()}", "for phase,records in expected.items() if phase!='train'}")
x=x.replace("'phase_counts':phase_counts,'runtime_admission'", "'phase_counts':phase_counts,'training_feature_HTTP_requests':len(byphase['train']),'heldout_candidate_DEV_queries':len(byphase['development']),'train_metrics_scope':'TRAINmetrics are raw prefit collection/in-sample; only24DEV actualfittedcandidate evaluation. No TRAINheldoutclaim.','fitted_head_sha256':sha(study/'fitted-head.json'),'fit_lock_sha256':sha(study/'readout-fit-lock.json'),'runtime_admission'")
x=x.replace("'artifact_pins':[", "'artifact_pins':[")
# A dispatch guard preserves failed/partial phase facts without inventing heldout metrics.
a=x.index(" summary=obj(study/'study-completion.json');");x=x[:a]+x[a:].replace(" summary=obj(study/'study-completion.json');phase_evidence={}", " summary=obj(study/'study-completion.json');\n if summary['status']=='FAILED_PRESERVED_EVIDENCE':\n  result=failure_preservation(project,study,plan,args.expected_plan_sha,summary);args.out.write_text(json.dumps(result,indent=2)+'\\n');print(json.dumps({'checks_passed':True,'preserved_failure':True,'sha256':sha(args.out)}));return\n phase_evidence={}",1)
# failure helper audits partial literal evidence, receipts and exposure; quality remains null.
a=x.index('\ndef main():')
x=x[:a]+'''
def failure_preservation(project,study,plan,plan_sha,summary):
 evidence={};completed={'train':0,'development':0,'confirmation':0};startedcounts=dict(completed);allrecords=[];artifacts=[]
 for phase in ['development','confirmation']:
  folder=study/'runs'/phase
  if not (folder/'attempt.json').exists():continue
  attempt=obj(folder/'attempt.json');completion=obj(folder/'completion.json');assert attempt['source_plan_sha256']==plan_sha and completion['source_plan_unchanged'] and not completion['owned_group_cleanup']['live_members_after'];assert not Path('/proc',str(attempt['pid'])).exists()
  rs=rows(folder/'records.jsonl') if (folder/'records.jsonl').exists() else [];ws=rows(folder/'wire.jsonl') if (folder/'wire.jsonl').exists() else [];begins=rows(folder/'started-requests.jsonl') if (folder/'started-requests.jsonl').exists() else []
  for event in begins:
   startedcounts[event['phase']]+=1;assert hashlib.sha256(event['request'].encode()).hexdigest()==event['request_sha256'];assert set(json.loads(event['request']))=={'state','questions'}
  for event in ws:
   for side in ['request','response']:assert hashlib.sha256(event[side].encode()).hexdigest()==event[side+'_sha256']
  for r in rs:
   completed[r['measured_phase']]+=1;match=next(w for w in ws if w['id']==r['id']);assert match['status']==200 and json.loads(match['response'])==r['response'];assert json.loads(match['request'])==r['input'];expected={v['id']:v for v in rows(project/plan['datasets'][r['measured_phase']])};assert r['evaluation']==expected[r['id']]['evaluation'] and r['input_sha256']==expected[r['id']]['input_sha256'] and hashlib.sha256(canonical(r['input'])).hexdigest()==r['input_sha256']
  engine=obj(folder/'final-engine.json') if (folder/'final-engine.json').exists() else None;resources=obj(folder/'resources.json') if (folder/'resources.json').exists() else None
  if engine:
   for pid in obj(folder/'cleanup.json')['native_child_pids']:assert not Path('/proc',str(pid)).exists()
  evidence[phase]={'attempt':attempt,'completion':completion,'resources':resources,'final_engine':engine};allrecords+=rs
  artifacts += [{'path':str(p.relative_to(project)),'bytes':p.stat().st_size,'sha256':sha(p)} for p in sorted(folder.rglob('*')) if p.is_file()]
 assert summary['actual_native_attempts']==len(evidence) and summary['lifetime_native_attempts']==9+len(evidence) and summary['allowed_further_attempts_in_closed_study']==0
 consumed=startedcounts['confirmation']>0;assert not consumed or summary['confirmation_consumed_or_attempted']
 if not completed['development']:assert not (study/'confirmation-selection-lock.json').exists() and not (study/'runs/confirmation/attempt.json').exists()
 return {'schema_version':1,'at':datetime.now(timezone.utc).isoformat(),'checks_passed':True,'status':'ACTUAL_FAILURE_PRESERVED_NO_PROMOTION','plan_SHA256':plan_sha,'source_pins_verified':len(plan['pins']),'metrics':{'development':None,'confirmation':None},'DEV_gate_passed':False,'internal_confirmation_gate_passed':False,'confirmation_consumed':consumed,'confirmation_now_permanently_exposed_DEV':consumed,'actual_successful_HTTP_by_corpus':completed,'actual_started_HTTP_by_corpus':startedcounts,'training_feature_HTTP_requests':completed['train'],'heldout_candidate_DEV_queries':completed['development'],'actual_requests':len(allrecords),'phase_evidence':evidence,'study_completion':summary,'all_declared32_TRAIN_DEV_groups_retired':True,'quality_scope':'No invented heldout accuracy from incomplete/failedfit. Literalpartial evidence/sourcepins/counter/resource/cleanup/exposure audited; retainedcomplete rows available for deeper versioned numerical replay if needed. Allraw failure evidence preserved.','artifact_pins':artifacts,'auditor_model_native_calls':0,'official_score':None,'official_rank':None,'SOTA_established':False}
''' +x[a:]
(O/'replay_actual.py').write_text(x);compile(x,'replay_actual.py','exec');print('Prepared epoch8 shared-trained-head/three-corpus/two-process/partial-failure saved-output replay')
