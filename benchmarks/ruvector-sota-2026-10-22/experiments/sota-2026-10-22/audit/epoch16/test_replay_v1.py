"""Synthetic validator fixtures only; no benchmark or native/model measurement.

The exact data-licensing/gold recipe function is injected to avoid reading any
new role gold. Actual replay still uses the unmodified verified real recipe.
"""
from pathlib import Path
from datetime import datetime, timezone
import hashlib
import json
import math
import tempfile
import time
import unittest
from unittest.mock import patch
import replay_scores_v1 as R
import math_v1 as M


def write(path, value, lines=False):
    path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(''.join(json.dumps(x)+'\n' for x in value) if lines else json.dumps(value))


def decode(p, premise, hypothesis, n):
    logits = [math.log(p['Contradiction']),math.log(p['Entailment']),math.log(p['NotMentioned'])]
    return {'logits':logits,'raw_label_indices':{'contradiction':0,'entailment':1,'neutral':2},
        'raw_threeway_probabilities':p,'model_revision':R.MODEL_REV,'onnx_sha256':R.MODEL_SHA,
        'temperature':1,'batch_size':1,'truncated':False,'padding_tokens':0,
        'input_tokens':n,'raw_tokens':n,'used_tokens':n,'actual_model_pair_tokens':n,
        'input_ids':[1]*n,'attention_mask':[1]*n,'token_type_ids':[0]*(n-1)+[1],
        'input_text_sha256':R.text_hash(json.dumps({'premise':premise,'hypothesis':hypothesis},
            ensure_ascii=False,separators=(',',':'),allow_nan=False))}


def answer(p):
    b = M.binary(p)
    return {'probabilities':b,'choice':M.prediction(b),'typed_probabilities':p,'typed_prediction':M.prediction(p)}


def fixture_record(index):
    gold = M.LABELS[index%3]; h = 'Synthetic validator proposition '+str(index)+'.'
    premises = {name:'Synthetic validator source '+str(index//3)+' selected '+name+'.'
                for name in ('ruvector_top2','lexical_top2','positional_first2')}
    p = {'Entailment':.2,'Contradiction':.1,'NotMentioned':.7}
    if gold == 'Entailment': q = {'Entailment':.005,'Contradiction':.99,'NotMentioned':.005}
    elif gold == 'Contradiction': q = {'Entailment':.99,'Contradiction':.005,'NotMentioned':.005}
    else: p = q = {'Entailment':.05,'Contradiction':.05,'NotMentioned':.9}
    neutral = {'Entailment':.1,'Contradiction':.1,'NotMentioned':.8}
    arms = {}; pooled = {}; raw = {}
    for name in ('ruvector_top2','lexical_top2','positional_first2'):
        premise = premises[name]
        a,b = (p,q) if name == 'ruvector_top2' else (neutral,neutral)
        value = M.mirrored_pool(a,b); pooled[name] = answer(value); raw[name] = answer(a)
        arms[name] = {'premise':premise,'hypothesis':h,'counterclaim':R.PREFIX+h,
            'positive_decoding':decode(a,premise,h,6),'counterclaim_decoding':decode(b,premise,R.PREFIX+h,7),
            'pooled_threeway_probabilities':value,'pooled_binary_probabilities':M.binary(value),
            'pooling':{'counterclaim_prefix':R.PREFIX}}
    response = {'answers':{'decision':pooled['ruvector_top2']},
        'baseline104_response':{'answers':{'decision':{'probabilities':{'Yes':.5,'No':.5},'choice':'No'}}},
        'ablation_responses':{'same_nli_lexical_top2':{'answers':{'decision':pooled['lexical_top2']}},
            'same_nli_positional_first2':{'answers':{'decision':pooled['positional_first2']}},
            'same_nli_native_raw_h':{'answers':{'decision':raw['ruvector_top2']}}},
        'semantic_ablation_responses':{'same_nli_native_raw_h':{'answers':{'decision':raw['ruvector_top2']}},
            'same_nli_lexical_raw_h':{'answers':{'decision':raw['lexical_top2']}},
            'same_nli_positional_raw_h':{'answers':{'decision':raw['positional_first2']}}},
        'usage':{'paid_calls':0,'native_requests':1,'native_core_searches':1,
            'nli_singleton_pairs':6,'semantic_control_extra_forwards':0},
        'diagnostics':{'decision':{'arms':arms,'retrieval':{'embedding':{
            'actual_embedded_texts':2,'chunks':{'model_batches':1},'query':{'model_batches':1}}}}}}
    row = {'id':'synthetic-validator:'+str(index),'source_group':'synthetic-doc:'+str(index//3),
        'input':{'state':'\n\n'.join(premises.values()),'questions':{'decision':{'criteria':{'Yes':h}}}},
        'evaluation':{'gold':'Yes' if gold=='Entailment' else 'No','original_threeway_label':gold},
        'response':response,'elapsed_s':15.}
    return row


class SavedReplayTests(unittest.TestCase):
    def fixture(self, root, mode='complete', confirmation=False):
        study = root/'experiments/sota-2026-10-22/epoch16'; now = time.time()
        data = [fixture_record(i) for i in range(24)]
        write(root/'development.jsonl',[{k:v for k,v in r.items() if k not in ('response','elapsed_s')} for r in data],True)
        write(root/'confirmation.jsonl',[{k:v for k,v in r.items() if k not in ('response','elapsed_s')} for r in data],True)
        plan = {'prior_closed_study_native_attempts':17,'limits':{'threads':2,'seconds_per_batch':600,'paid_calls':0,'GPU_calls':0},
            'pins':[],'datasets':{'development':'development.jsonl','confirmation':'confirmation.jsonl'},
            'expected_native_receipt':{},'expected_nli_revision':R.MODEL_REV,'expected_nli_sha256':R.MODEL_SHA,
            'runtime_admission':{'formula_id':'24xDEVmaxHTTPxunitratio+2xDEVinit+60-v1',
                'max_DEV_units':1,'max_confirmation_units':1 if confirmation else 2},'lease_expires_unix':now+20000}
        path = study/'plan.json'; write(path,plan); digest=R.sha(path)
        phases = ['development','confirmation'] if confirmation else ['development']
        metrics = None; typed = None
        for number,phase in enumerate(phases,1):
            folder = study/'runs'/phase; start = now+500*(number-1)
            at = datetime.fromtimestamp(start,timezone.utc).isoformat()
            runtime_at = datetime.fromtimestamp(start+2,timezone.utc).isoformat()
            write(folder/'popen-attempt.json',{'source_plan_sha256':digest,'new_study_native_attempt':number,'at':at})
            write(folder/'attempt.json',{'lifetime_native_attempt':17+number,'pid':999999,
                  'invocation_started_unix':start,'at':at})
            complete = mode=='complete'
            write(folder/'completion.json',{'prior_closed_attempts':17,'source_plan_unchanged':True,
                'wall_seconds_including_model_load':365. if complete else 20.,
                'owned_group_cleanup':{'live_members_after':[],'finished_within_deadline':True},
                'exit_code':0 if complete else 1,'error':None if complete else 'Synthetic fixture failure'})
            if mode!='initialization_failure':
                write(folder/'runtime.json',{'at':runtime_at,'native_child_pids':[999998],
                    'phase_initialization_seconds':2.,'receipt':{'initialization_wall_seconds':1.,
                        'nli':{'revision':R.MODEL_REV,'model_sha256':R.MODEL_SHA}}})
            write(folder/'resources.json',{'allowed_CPU_ids':[0,1],'configured_ORT_threads':2})
            write(folder/'cleanup.json',{'engine_close_called':True,'native_child_pids_absent':True,'cleanup_errors':[]})
            selected = data if complete else data[:1] if mode=='partial' else []
            measured = [{**row,'measured_phase':phase} for row in selected]
            wire=[]; events=[]; starts=[]
            for row in measured:
                request=json.dumps(row['input']);response=json.dumps(row['response'])
                w={'id':row['id'],'phase':phase,'request':request,'response':response,'status':200,
                   'elapsed_s':15.,'request_sha256':R.text_hash(request),'response_sha256':R.text_hash(response)}
                wire.append(w);events.append({'status':200,'ok':True,'request_sha256':w['request_sha256'],'response_sha256':w['response_sha256']})
                starts.append({'id':row['id'],'request':request,'request_sha256':w['request_sha256']})
            write(folder/'records.jsonl',measured,True);write(folder/'wire.jsonl',wire,True)
            write(folder/'server-audit.jsonl',events,True);write(folder/'started-requests.jsonl',starts,True)
            report={'records_sha256':R.sha(folder/'records.jsonl'),'wire_sha256':R.sha(folder/'wire.jsonl')}
            write(folder/'report.json',report)
            if complete:
                metrics={arm:M.summary([M.row_score(R.selected_response(r['response'],arm)['answers']['decision']['probabilities'],r['evaluation']['gold'],['Yes','No']) for r in data]) for arm in M.BINARY_ARMS}
                typed={};confusions={}
                for arm in M.TYPED_ARMS:
                    values=[M.row_score(R.selected_response(r['response'],arm)['answers']['decision']['typed_probabilities'],r['evaluation']['original_threeway_label'],M.LABELS) for r in data]
                    typed[arm]=M.summary(values)
                    typed[arm]['by_class']={label:{'n':8,'correct':sum(v['correct'] for r,v in zip(data,values) if r['evaluation']['original_threeway_label']==label)} for label in M.LABELS}
                    c={}
                    for r in data:
                        key=r['evaluation']['original_threeway_label']+'->'+R.selected_response(r['response'],arm)['answers']['decision']['typed_prediction'];c[key]=c.get(key,0)+1
                    confusions[arm]=c
                write(folder/(phase+'-comparison.json'),{'metrics':metrics,'typed_metrics':typed,
                    'typed_confusions':confusions,'frozen_development_gate_passed':True})
        if mode=='complete':
            forecast=24*15*(1 if confirmation else 2)+4+60
            admission={'at':datetime.fromtimestamp(now+400,timezone.utc).isoformat(),
                'formula_id':plan['runtime_admission']['formula_id'],'projected_confirmation_seconds':forecast,
                'DEV_initialization_seconds':2.,'max_DEV_HTTP_seconds':15.,'allowed':confirmation}
            write(study/'runtime-admission.json',admission)
            if confirmation:
                write(study/'confirmation-selection-lock.json',{'at':admission['at'],'plan_sha256':digest,
                    'development_comparison_sha256':R.sha(study/'runs/development/development-comparison.json'),
                    'runtime_admission_sha256':R.sha(study/'runtime-admission.json')})
        terminal={'actual_native_attempts':len(phases),'lifetime_native_attempts':17+len(phases),
            'allowed_further_attempts_in_closed_study':0,'status':'CONFIRMATION_COMPLETE_AWAITING_INDEPENDENT_REVIEW' if confirmation else 'BLOCKED_CONFIRMATION_RUNTIME_BUDGET' if mode=='complete' else 'FAILED_PRESERVED_EVIDENCE'}
        if mode=='complete':terminal['development_gate_passed']=True
        write(study/'study-completion.json',terminal)
        return path,digest

    def run_case(self, mode='complete', confirmation=False):
        with tempfile.TemporaryDirectory(prefix='epoch16-audit-engineering-') as directory:
            root=Path(directory);path,digest=self.fixture(root,mode,confirmation)
            # This patch is explicit engineering injection, never used in real CLI replay.
            with patch.object(R,'verify_recipe',return_value={'synthetic_engineering_fixture_only':True}):
                return R.audit(root,path,digest)

    def test_complete_DEV_with_frozen_runtime_block(self):
        result=self.run_case();self.assertTrue(result['DEV_gate_passed'])
        self.assertFalse(result['confirmation_consumed']);self.assertFalse(result['internal_confirmation_gate_passed'])
    def test_complete_conditional_confirmation(self):
        result=self.run_case(confirmation=True);self.assertTrue(result['internal_confirmation_gate_passed'])
    def test_partial_failed_phase_preserves_partial_scores(self):
        result=self.run_case(mode='partial');self.assertFalse(result['DEV_gate_passed'])
        self.assertEqual(result['metrics']['development']['ruvector_top2']['n'],1)
    def test_initialization_failure_has_no_fabricated_accuracy(self):
        result=self.run_case(mode='initialization_failure');self.assertFalse(result['DEV_gate_passed'])
        self.assertEqual(result['metrics']['development']['ruvector_top2']['n'],0)
        self.assertIsNone(result['metrics']['development']['ruvector_top2']['brier'])

    def test_same_input_conflicting_logits_is_rejected(self):
        with tempfile.TemporaryDirectory(prefix='epoch16-audit-negative-fixture-') as directory:
            root=Path(directory);path,digest=self.fixture(root,mode='partial')
            folder=root/'experiments/sota-2026-10-22/epoch16/runs/development'
            actual=R.rows(folder/'records.jsonl');row=actual[0]
            d=row['response']['diagnostics']['decision'];primary=d['arms']['ruvector_top2']
            other=d['arms']['lexical_top2'];other['premise']=primary['premise']
            for field,h in [('positive_decoding',other['hypothesis']),('counterclaim_decoding',other['counterclaim'])]:
                other[field]['input_text_sha256']=R.text_hash(json.dumps({'premise':other['premise'],'hypothesis':h},
                    ensure_ascii=False,separators=(',',':'),allow_nan=False))
            wire=R.rows(folder/'wire.jsonl');wire[0]['response']=json.dumps(row['response'])
            wire[0]['response_sha256']=R.text_hash(wire[0]['response'])
            events=R.rows(folder/'server-audit.jsonl');events[0]['response_sha256']=wire[0]['response_sha256']
            write(folder/'records.jsonl',actual,True);write(folder/'wire.jsonl',wire,True);write(folder/'server-audit.jsonl',events,True)
            with patch.object(R,'verify_recipe',return_value={'synthetic_engineering_fixture_only':True}):
                with self.assertRaises(AssertionError):R.audit(root,path,digest)


if __name__=='__main__':unittest.main()
