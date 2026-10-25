"""Invented-only E41 integration fixtures; no actual reader/native/case calls."""
import importlib.util
import json
import math
from pathlib import Path
import subprocess
import sys
import types
import unittest
import tempfile
import time
import contextlib
import io
from unittest.mock import patch

HERE=Path(__file__).parent


def load(name):
    spec=importlib.util.spec_from_file_location('pure_e41_'+name,HERE/(name+'.py'))
    module=importlib.util.module_from_spec(spec);sys.modules[spec.name]=module;spec.loader.exec_module(module);return module


class Features(dict):
    def __init__(self,ids,seq,offsets):
        super().__init__(input_ids=ids,attention_mask=[1]*len(ids),offset_mapping=offsets);self.seq=seq
    def sequence_ids(self):return self.seq


class Tokenizer:
    def __call__(self,premise,text_pair,**kwargs):
        import re
        a=list(re.finditer(r'\S+',premise));b=list(re.finditer(r'\S+',text_pair))
        if kwargs.get('truncation')=='only_first':a=a[:max(0,kwargs['max_length']-len(b)-3)]
        ids=[0]+[100+i for i in range(len(a))]+[2]+[900+i for i in range(len(b))]+[2]
        return Features(ids,[None]+[0]*len(a)+[None]+[1]*len(b)+[None],
            [(0,0)]+[(m.start(),m.end())for m in a]+[(0,0)]+[(m.start(),m.end())for m in b]+[(0,0)])


class Pipeline(unittest.TestCase):
    def test_preworker_asset_refusal_captured_without_counter_invention(self):
        spec=importlib.util.spec_from_file_location('e41_capture_fixture',HERE/'runtime/launch.py');L=importlib.util.module_from_spec(spec);spec.loader.exec_module(L)
        K=load('counters');A=load('algorithm')
        with tempfile.TemporaryDirectory(prefix='e41-fake-capture-')as temporary:
            base=Path(temporary);root=base/'project';study=root/'study';study.mkdir(parents=True);scope=base/'scope';scope.mkdir()
            plan={'expected_operation_counters':{'dev':K.expected(4)},'data_roles':{'dev':['audit'+str(i)for i in range(12)]},'arms':list(A.ARMS)}
            planfile=study/'plan.json';planfile.write_text(json.dumps(plan));admission=study/'SOURCE_ADMISSION.json';admission.write_text('{}');sha=L.C.sha(planfile)
            claim={'dispatch_monotonic_seconds':time.monotonic(),'dispatch_unix_seconds':time.time()}
            for name in ['DISPATCH_RESERVATION.json','DISPATCH_ATTEMPT.json']:(study/name).write_text('{}')
            identity={'pid':12345,'ticks':54321,'pgid':12345,'sid':12345,'ppid':1,'state':'R'}
            argv=['launch.py','--plan',str(planfile),'--admission',str(admission),'--scope',str(scope),'--expected-plan-sha',sha,'--phase','dev']
            with patch.object(L.sys,'argv',argv),patch.object(L.C,'SCOPE',scope),patch.object(L.C,'STUDY',study),patch.object(L.C,'ROOT',root),patch.object(L.C,'owner_lock'),patch.object(L.C,'dispatch_proof',return_value=(claim,{})),patch.object(L.C,'admission',return_value=({},{})),patch.object(L.C,'verify_plan',return_value=plan),patch.object(L.C,'verify_runtime',side_effect=ValueError('invented asset refusal')),patch.object(L.C,'proc',return_value=identity),patch.object(L.os,'getpid',return_value=12345),patch.object(L.os,'sched_setaffinity'),patch.object(L.os,'sched_getaffinity',return_value={0,1}),patch.object(L.subprocess,'Popen',side_effect=AssertionError('NO_POPEN'))as boundary,contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(L.main(),2);boundary.assert_not_called()
            result=json.loads((study/'runs/dev/execution.json').read_text())
            self.assertFalse(result['worker_popen_attempted']);self.assertTrue(result['owned_live_processes_closed'])
            self.assertEqual(result['raw_operation_counters_source'],'UNKNOWN');self.assertIsNone(result['raw_operation_counters'])
            self.assertFalse(result['operation_counts_complete']);self.assertIsNone(result['runtime_asset_verification'])
            self.assertEqual(json.loads((study/'SUPERVISOR_COMPLETION.json').read_text())['plan_sha256'],sha)

    def test_inherited_asset_wrapper_keeps_old_lock_origin_and_new_envelope(self):
        spec=importlib.util.spec_from_file_location('e41_asset_origin_fixture',HERE/'runtime/model_assets_guard.py');G=importlib.util.module_from_spec(spec);spec.loader.exec_module(G)
        profile={'model_directory':'/invented/old/model','public_lock_path':'/invented/public.json','public_lock_sha256':'a'*64,'expected_catalog_path':'/invented/expected.json','expected_catalog_sha256':'b'*64}
        receipt={'actual_payload_files_verified':9,'ordinary_Git_payloads_verified':7,'canonical_LFS_pointers_verified':2}
        with patch.object(G,'validate_tasksource_catalog'),patch.object(G,'validate_model_assets',return_value=receipt)as called:
            actual=G.validate_inherited_tasksource_profile({'tasksource':profile},root=Path('/invented/project'),current_epoch=41,current_kind='E41_FIXTURE',current_source_checkpoint='c'*40)
        self.assertEqual(called.call_args.kwargs['epoch'],40)
        self.assertEqual(called.call_args.kwargs['source_checkpoint'],'2cf5aba60a050079506a5e9aa5463f44c1efcd5a')
        self.assertEqual(actual['epoch'],41);self.assertEqual(actual['actual_payload_files_verified'],9)
        self.assertEqual(actual['profiles']['tasksource'],receipt)

    def test_source_completion_requires72physical_and36derived(self):
        path=HERE/'runtime/launch.py';spec=importlib.util.spec_from_file_location('e41_launch_fixture',path)
        L=importlib.util.module_from_spec(spec);spec.loader.exec_module(L)
        K=load('counters');A=load('algorithm');ids=[f'audit-only:{i}'for i in range(12)]
        expected=K.expected(4);counters={**expected,'packing_pair_tokenizer_calls_attempted':7,'packing_pair_tokenizer_calls_completed':7}
        forecasts=[i+'::'+a for i in ids for a in A.ARMS]
        physical=[f+'::window:'+str(w)for f in forecasts for w in range(2)]
        raw={'phase':'dev','status':'DEV_FORECASTS_COMPLETE_NO_GOLD','counters':counters,'errors':[],
            'required_readout_ids':physical,'completed_readout_ids':list(physical),
            'required_forecast_ids':forecasts,'completed_forecast_ids':list(forecasts),
            'offline_policy':{'clean':True,'literal_capability_bind_closed':True},
            'closure_facts':{'native_child_closed':True,'model_profiles_disposed':['tasksource'],'all_forecasts_closed_before_gold':True}}
        plan={'data_roles':{'dev':ids},'arms':list(A.ARMS),'expected_operation_counters':{'dev':expected}}
        self.assertTrue(all(L.completion_invariants(raw,plan,'dev').values()))
        raw['completed_readout_ids'].pop()
        self.assertFalse(L.completion_invariants(raw,plan,'dev')['all72_unique_physical_windows'])
        self.assertFalse(all(L.completion_invariants({},plan,'dev').values()))

    def test_observer_stable_z_wait0_survives_and_missing_execution_stays_unknown(self):
        path=HERE.parents[1]/'audit/epoch41/observe_supervisor_closure.py'
        spec=importlib.util.spec_from_file_location('e41_observer_fixture',path);O=importlib.util.module_from_spec(spec);spec.loader.exec_module(O)
        supervisor={'pid':200,'startticks':1000,'pgid':200,'sid':200}
        worker={'pid':201,'ticks':1001,'pgid':201,'sid':201,'ppid':200,'state':'S'}
        row={'pid':200,'ticks':1000,'pgid':200,'sid':200,'ppid':1,'state':'Z'}
        evidence={'wait_status':0,'field':52,'source':'PROC_STAT_FIELD52_EXACT_STABLE_ZOMBIE','raw_stat_sha256':'e'*64}
        refs={key:{'path':value,'bytes':1,'sha256':'1'*64}for key,value in O.PATHS.items()}
        execution={'uncertain_start':False,'verified_worker_starts':1,'status':'WORKER_COMPLETED',
            'worker_popen_attempted':True,'worker_popen_attempts':1,'worker_start_boundary':'WORKER_POPEN_ATTEMPTED',
            'worker_identity':worker,'recovered_preexec_child_identity':None,'owned_live_processes_closed':True,
            'owned_live_group_members':[],'owned_process_closure_observation':'OBSERVED'}
        docs={'execution':execution,'dispatch_attempt':{'verified_launcher_start':True}}
        snap={'scan_error':False,'rows':[row],'processes':{200:{'absent':False,'row':row,'closed':True,'exit_status_evidence':evidence},201:{'absent':True,'row':None,'closed':True}}}
        with patch.object(O,'snapshot',side_effect=AssertionError('NO_LIVE_PROC_FIXTURE')):
            actual=O.evaluate('2'*64,refs,docs,supervisor,[worker],snap,True)
            self.assertTrue(actual['physical_closure_passed']);self.assertEqual(actual['observed_supervisor_exit_wait_status'],0)
            self.assertEqual(actual['supervisor_exit_status_source'],'PROC_STAT_FIELD52_EXACT_STABLE_ZOMBIE')
            docs['execution']=None;refs['execution']=None
            missing=O.evaluate('2'*64,refs,docs,supervisor,[],snap,True)
            self.assertTrue(missing['unknown_physical_ownership']);self.assertFalse(missing['physical_closure_passed'])

    def test_counter_meanings_unique_document_and_repeated_query_hits(self):
        K=load('counters');row=K.expected(4)
        self.assertEqual(row['native_index_initializations_completed'],4)
        self.assertEqual(row['native_insertions_completed'],4)
        self.assertEqual(row['native_hit_source_validations'],12)
        self.assertEqual(row['NLI_readouts_completed'],72)
        self.assertEqual(row['derived_forecasts_completed'],36)
        self.assertEqual(row['BGE_texts_completed'],16)
        self.assertEqual(row['model_initializations_completed'],1)
        self.assertNotIn('b354_forward_calls_completed',row)

    def test_NLI_complete_claim_and_no_premise_truncation_allowed(self):
        N=load('nli');_,audit,_,_=N.prepare(Tokenizer(),'Prior sentence. Final sentence.','Full unchanged claim',[0,1])
        self.assertTrue(audit['claim_complete']);self.assertFalse(audit['premise_truncated'])
        with self.assertRaisesRegex(ValueError,'WHOLE_CLAIM_OR512'):
            N.prepare(Tokenizer(),' '.join(['long']*600),'Full claim',[0])

    def test_canonical_logit_ties_and_unclipped_logprob(self):
        N=load('nli');tie=N.decisions([8.,8.,-1000.],'tasksource')
        self.assertEqual(tie['primary_label'],'NotMentioned')
        self.assertLess(tie['log_probabilities_N_E_C'][2],-1000.)

    def test_four_shared_indexes_three_hypotheses_context_wire(self):
        C=load('context');W=load('context_windows');records=[];native={'documents':[]};prepared={}
        for doc in [901,902,903,904]:
            spans=W.sentence_catalog('Audit source alpha. Audit source beta.')
            observed={'document_id':doc,'initialized_vectors':len(spans),'initialization_ms':1.,'queries':[]}
            for hyp in range(3):
                identity=f'audit-only:{doc}:hyp{hyp}'
                record={k:'0'*64 for k in ['input_sha256','source_group_sha256','source_document_sha256','normalized_document_sha256','source_filename_key_sha256']}
                record.update(id=identity,record_ordinal=doc,document_id=doc,hypothesis_id=str(hyp),claim='Audit claim beta',evidence=spans)
                records.append(record);observed['queries'].append({'case_id':identity+'::retrieval:original','ids':[1,0],'requested_k':2,'query_ms':1.})
                prepared[identity]={'source_preparation_started_monotonic_seconds':1.,'unit_embedding_seconds_shared_three_hypotheses':.1,'query_embedding_seconds':.01}
            native['documents'].append(observed)
        caller=types.SimpleNamespace(load_module=lambda name,path:W,CANDIDATE=HERE)
        private,public=C.orders_and_premises(caller,records,native,prepared)
        self.assertEqual(len(private),12);self.assertEqual(len(public),12)
        self.assertEqual(public[0]['native_order_ids'],[1,0])
        self.assertEqual(list(private.values())[0]['orders']['tasksource_source_order_two_windows'],[0,1])
        native['documents'][0]['queries'].pop()
        with self.assertRaisesRegex(ValueError,'THREE_NATIVE_QUERIES'):C.orders_and_premises(caller,records,native,prepared)

    def test_real_source_entrypoint_help_under_isolation(self):
        result=subprocess.run([sys.executable,'-I','-B',str(HERE/'worker.py'),'--help'],capture_output=True,text=True,timeout=10)
        self.assertEqual(result.returncode,0,result.stderr);self.assertIn('--expected-plan-sha',result.stdout)

    def test_native_helper_pure_configuration_and1024_transport(self):
        code=r'''
const m=require(process.argv[1]),crypto=require('node:crypto');
const docs=[901,902,903,904],links={};for(const d of docs)links[String(d)]=[0,1,2].map(h=>'audit:'+d+':'+h);
const cases=docs.flatMap(d=>links[String(d)]);m.configureIdentities({dev_document_ids:docs,case_ids_by_document:links,data_roles:{dev:cases}});
const block=n=>{const b=Buffer.alloc(n*1536);return {encoding:'base64',dtype:'float32le',shape:[n,384],bytes:b.length,data_base64:b.toString('base64'),sha256:crypto.createHash('sha256').update(b).digest('hex')}};
const bundle={schema_version:1,epoch:41,phase:'dev',role:'dev',kind:'REAL_CONTRACTNLI_MULTI_HYPOTHESIS_CONTEXT_DEV_PILOT',vector_encoding:'base64_float32le_c_order',metadata_policy:'insert id and vector only; metadata absent',documents:docs.map(d=>({document_id:d,vectors:block(1),query_vectors:block(3),queries:links[String(d)].map(id=>({id:id+'::retrieval:original'}))}))};
if(!m.validateBundle(bundle,'dev')||m.decode(block(1024)).length!==1024)throw Error('pure fullwire failure');
let denied=false;try{m.decode(block(1025));}catch(e){denied=true;}if(!denied)throw Error('1025boundary accepted');
bundle.documents[0].queries.pop();denied=false;try{m.validateBundle(bundle,'dev');}catch(e){denied=true;}if(!denied)throw Error('2queries accepted');
console.log('PURE_HELPER_4DOC_12QUERY_1024_BOUNDARY_PASS_NO_NATIVE');
'''
        result=subprocess.run(['node','-e',code,str(HERE/'native_helper.cjs')],capture_output=True,text=True,timeout=10)
        self.assertEqual(result.returncode,0,result.stderr)
        self.assertIn('NO_NATIVE',result.stdout)


if __name__=='__main__':unittest.main()
