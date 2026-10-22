"""Prepare epoch7 independent saved-output-only replay from prior reviewed method."""
from pathlib import Path
O=Path(__file__).resolve().parent;S=O.parents[1]
x=(S/'audit/epoch6/replay_actual.py').read_text().replace('epoch6 replay','epoch7 replay')
a=x.index(" project=args.project;");b=x.index(" bge=Tokenizer.from_file",a)
x=x[:a]+''' project=args.project;s=project/'experiments/sota-2026-10-22';study=s/'epoch7';plan=obj(study/'plan.json');assert sha(study/'plan.json')==args.expected_plan_sha
 for item in plan['pins']:assert sha(project/item['path'])==item['sha256'],item['path']
 summary=obj(study/'study-completion.json');phase_evidence={};actual=[];wire=[];server=[];started=[]
 for phase in ['development','confirmation']:
  run=study/'runs'/phase
  if not (run/'attempt.json').exists():continue
  ev={k:obj(run/(k+'.json')) for k in ['report','completion','runtime','cleanup','final-engine','resources','attempt']};phase_evidence[phase]=ev
  report=ev['report'];completion=ev['completion'];runtime=ev['runtime'];cleanup=ev['cleanup'];attempt=ev['attempt']
  assert completion['exit_code']==0 and completion['error'] is None and completion['source_plan_unchanged'] and not completion['owned_group_cleanup']['live_members_after']
  expected_number=1 if phase=='development' else 2
  assert completion['prior_closed_attempts']==8 and completion['lifetime_native_attempt']==8+expected_number
  assert attempt['new_study_native_attempt']==expected_number and attempt['lifetime_native_attempt']==8+expected_number and attempt['source_plan_sha256']==args.expected_plan_sha
  assert cleanup['engine_close_called'] and not cleanup['cleanup_errors'] and cleanup['native_child_pids_absent'];assert not any(Path('/proc',str(p)).exists() for p in [attempt['pid'],*runtime['native_child_pids']])
  assert len(ev['resources']['allowed_CPU_ids'])<=2 and runtime['receipt']['nli']['batch_size']==1 and not runtime['receipt']['nli']['padding'] and not runtime['receipt']['nli']['truncation']
  for k,v in plan['expected_native_receipt'].items():assert runtime['receipt'][k]==v
  assert runtime['receipt']['nli']['revision']==plan['expected_nli_revision'] and runtime['receipt']['nli']['model_sha256']==plan['expected_nli_sha256']
  assert runtime['receipt']['old_base_NLI_session_initialized'] is False and runtime['receipt']['unchanged_epoch6_context_policy'] is True
  assert runtime['receipt']['nli']['classes']==2 and runtime['receipt']['nli']['label_indices']=={'entailment':0,'not_entailment':1}
  assert attempt['model_deadline_unix']==runtime['deadline_unix'] and attempt['hard_cleanup_deadline_unix']-attempt['model_deadline_unix']>=4.9
  assert completion['wall_seconds_including_model_load']<=plan['limits']['seconds_per_batch']+1
  a,w,se,st=[rows(run/f) for f in ['records.jsonl','wire.jsonl','server-audit.jsonl','started-requests.jsonl']]
  assert len(a)==len(w)==len(se)==len(st)=={'development':24,'confirmation':96}[phase]
  assert sha(run/'records.jsonl')==report['records_sha256'] and sha(run/'wire.jsonl')==report['wire_sha256']
  assert report[phase+'_completed']==len(a)
  actual+=a;wire+=w;server+=se;started+=st
 assert list(phase_evidence) in [['development'],['development','confirmation']]
 assert summary['actual_native_attempts']==len(phase_evidence) and summary['lifetime_native_attempts']==8+len(phase_evidence) and summary['allowed_further_attempts_in_closed_study']==0
 expected={phase:rows(project/path) for phase,path in plan['datasets'].items()};byphase={phase:[x for x in actual if x['measured_phase']==phase] for phase in expected}
 assert len(byphase['development'])==24 and len(byphase['confirmation']) in [0,96]
 ordered=expected['development']+(expected['confirmation'] if byphase['confirmation'] else []);assert [r['id'] for r in actual]==[r['id'] for r in ordered]
''' +x[b:]
x=x.replace("config=obj(s/'candidate/epoch4/assets/nli-base/config.json');assert config['id2label']=={'0':'contradiction','1':'entailment','2':'neutral'}", "model_tokenizer=Tokenizer.from_file(str(s/'candidate/epoch7/assets/nli-large/tokenizer.json'));model_tokenizer.no_padding();model_tokenizer.no_truncation()\n config=obj(s/'candidate/epoch7/assets/nli-large/config.json');assert config['id2label']=={'0':'entailment','1':'not_entailment'}")
x=x.replace("scores={phase:{name:[] for name in ARMS} for phase in expected};proofs=[];sameinputs={};repeatdrift=0.;text_count=bge_batches=nli_tokens=0", "scores={phase:{name:[] for name in ARMS} for phase in expected};proofs=[];sameinputs={};repeatdrift=0.;text_count=bge_batches=nli_tokens=0;phase_counts={phase:{'BGE_texts':0,'BGE_batches':0,'NLI_tokens':0} for phase in phase_evidence}")
x=x.replace("phase=rec['measured_phase'];assert phase", "phase=rec['measured_phase'];run=study/'runs'/phase;ev=phase_evidence[phase];runtime=ev['runtime'];attempt=ev['attempt'];assert phase")
x=x.replace("attempt['deadline_unix']", "attempt['model_deadline_unix']")
x=x.replace("text_count+=len(texts);bge_batches+=embedding['chunks']['model_batches']+embedding['query']['model_batches']", "text_count+=len(texts);bge_batches+=embedding['chunks']['model_batches']+embedding['query']['model_batches'];phase_counts[phase]['BGE_texts']+=len(texts);phase_counts[phase]['BGE_batches']+=embedding['chunks']['model_batches']+embedding['query']['model_batches']")
x=x.replace("enc=nli.encode(premise,hyp);dec=ad['decoding'];", "policy_enc=nli.encode(premise,hyp);enc=model_tokenizer.encode(premise,hyp);dec=ad['decoding'];assert dec['frozen_epoch6_policy_pair_tokens']==len(policy_enc.ids)==coverage['joint_pair_tokens']<=512;assert dec['actual_model_pair_tokens']==len(enc.ids)<=512;")
x=x.replace("==coverage['joint_pair_tokens']==len(enc.ids)", "==len(enc.ids)")
x=x.replace("assert logits.shape==(3,)", "assert logits.shape==(2,)")
x=x.replace("close(p['Yes'],prob[1]);close(p['No'],prob[0]+prob[2]);assert dec['pool']=='One joint evidence premise; no per-chunk maximum'", "close(p['Yes'],prob[0]);close(p['No'],prob[1]);assert dec['pool']=='One unchanged epoch6 joint evidence premise; no per-chunk maximum';assert answer['model']==plan['expected_nli_repo']+'@'+plan['expected_nli_revision']")
x=x.replace("nli_tokens+=len(enc.ids);overlap", "nli_tokens+=len(enc.ids);phase_counts[phase]['NLI_tokens']+=len(enc.ids);overlap")
a=x.index(" counters=engine[");b=x.index(" metrics=",a)
x=x[:a]+''' N=len(actual)
 for phase,ev in phase_evidence.items():
  counters=ev['final-engine']['execution_after_close']['counters'];count=len(byphase[phase]);pc=phase_counts[phase]
  for key in ['requests','native104_requests','native_core_searches','context_partitions']:assert counters[key+'_attempted']==counters[key+'_completed']==count
  assert counters['context_packs_attempted']==counters['context_packs_completed']==count*3
  assert counters['bge_texts_attempted']==counters['bge_texts_completed']==pc['BGE_texts'] and counters['bge_forward_batches_attempted']==counters['bge_forward_batches_completed']==pc['BGE_batches']
  assert counters['nli_forward_pairs_attempted']==counters['nli_forward_pairs_completed']==count*3 and counters['nli_input_tokens_attempted']==counters['nli_input_tokens_completed']==pc['NLI_tokens']
''' +x[b:]
x=x.replace("dev=obj(run/'development-comparison.json');", "dev=obj(study/'runs/development/development-comparison.json');report=phase_evidence['development']['report'];")
x=x.replace("official=obj(run/('development-comparison.json' if phase=='development' else 'confirmation-comparison.json'))['metrics']", "official=obj(study/'runs'/phase/(phase+'-comparison.json'))['metrics']")
a=x.index(" if byphase['confirmation']:\n  assert devgate;");b=x.index(" assert repeatdrift",a)
x=x[:a]+''' admission=obj(study/'runtime-admission.json');initialization=phase_evidence['development']['runtime']['receipt']['initialization_wall_seconds'];devmax=max(r['elapsed_s'] for r in byphase['development']);source_counts={phase:max(len(context.partition(r['input']['state'],nli,bge,target=128,nli_cap=160,bge_cap=256,max_units=192)) for r in records) for phase,records in expected.items()}
 assert source_counts['development']==plan['runtime_admission']['max_DEV_units']==admission['max_DEV_units'] and source_counts['confirmation']==plan['runtime_admission']['max_confirmation_units']==admission['max_confirmation_units']
 projected=96*devmax*max(1,source_counts['confirmation']/source_counts['development'])+2*initialization+60;close(projected,admission['projected_confirmation_seconds']);close(initialization,admission['DEV_initialization_seconds']);close(devmax,admission['max_DEV_HTTP_seconds'])
 remaining=plan['lease_expires_unix']-datetime.fromisoformat(admission['at']).timestamp();assert admission['allowed']==(projected<=600 and remaining>=projected+30)
 if byphase['confirmation']:
  assert devgate and admission['allowed'];lock=obj(study/'confirmation-selection-lock.json');assert lock['plan_sha256']==sha(study/'plan.json') and lock['development_comparison_sha256']==sha(study/'runs/development/development-comparison.json') and lock['runtime_admission_sha256']==sha(study/'runtime-admission.json');assert lock['at']<=phase_evidence['confirmation']['attempt']['at']<=next(r['at'] for r in started if r['phase']=='confirmation')
  holdout_pass=gate(metrics['confirmation']) and all(uncertainty['confirmation'][name]['accuracy']['ci95'][0]>0 for name in ['same_nli_lexical_top2','same_nli_positional_first2']) and all(uncertainty['confirmation'][name][key]['ci95'][0]>=-1e-12 for name in uncertainty['confirmation'] for key in ['brier','nll'])
 else:
  assert not (study/'confirmation-selection-lock.json').exists() and not (study/'runs/confirmation/attempt.json').exists() and not any(r['phase']=='confirmation' for r in started)
  assert not devgate or not admission['allowed'];assert summary['status']==('REJECTED_DEV_GATE' if not devgate else 'BLOCKED_CONFIRMATION_RUNTIME_BUDGET')
 resources={phase:ev['resources'] for phase,ev in phase_evidence.items()};completion={phase:ev['completion'] for phase,ev in phase_evidence.items()}
''' +x[b:]
x=x.replace("sha(s/'epoch6/plan.json')", "sha(study/'plan.json')")
x=x.replace("'resources':resources,'completion':completion", "'resources':resources,'completion':completion,'phase_counts':phase_counts,'runtime_admission':admission,'study_completion':summary")
x=x.replace("for p in sorted(run.rglob('*'))", "for p in sorted(study.rglob('*')) if 'runs' in p.parts or p.name in ['runtime-admission.json','study-completion.json','confirmation-selection-lock.json']")
# Avoid referring to unspecified convenience repo field: actual receipt is independently pinned/checked.
x=x.replace("plan['expected_nli_repo']", "'onnx-community/deberta-v3-large-zeroshot-v2.0-ONNX'")
(O/'replay_actual.py').write_text(x)
compile(x,'replay_actual.py','exec');print('Prepared epoch7 independent separate-phase binary saved-output replay; no model calls')
