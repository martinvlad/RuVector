"""Generic filesystem/derived-control tests; never freeze or render real study."""
import argparse
import importlib.util
import json
import math
import os
from pathlib import Path
import tempfile
import unittest
from datetime import datetime,timezone
from unittest.mock import patch

HERE=Path(__file__).resolve().parent

def module(name):
    spec=importlib.util.spec_from_file_location('reviewed_test_'+name,HERE.parent/'preparation'/name)
    m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m);return m

PLAN=module('build_plan_v2.py');CONTROL=module('build_controls_v2.py')

def put(path,value):
    path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(value))

class Paths(unittest.TestCase):
    def test_plan_identity_rejects_unsafe_paths_symlinks_and_nonregular_members(self):
        with tempfile.TemporaryDirectory()as t:
            p=Path(t);(p/'ok.json').write_text('{}');(p/'linked.json').symlink_to(p/'ok.json');(p/'directory').mkdir()
            self.assertEqual(PLAN.identity(p,'ok.json')['bytes'],2)
            for n in ['../ok.json','./ok.json','/absolute','a//file','a\\file','linked.json','directory']:
                with self.subTest(n=n),self.assertRaises((AssertionError,FileNotFoundError)):PLAN.identity(p,n)
    def test_both_builders_refuse_noncanonical_or_symlink_directory(self):
        with tempfile.TemporaryDirectory()as t:
            p=Path(t);(p/'child').mkdir();(p/'alias').symlink_to(p/'child',target_is_directory=True)
            for m,fn in [(PLAN,PLAN.canonical_dir),(CONTROL,CONTROL.directory)]:
                for x in [p/'child/..',p/'alias']:
                    with self.subTest(module=m.__name__,p=x),self.assertRaises(AssertionError):fn(x)
    def test_plan_outputs_are_exclusive_and_nan_is_rejected(self):
        with tempfile.TemporaryDirectory()as t:
            p=Path(t)/'generic.json';PLAN.write_new(p,{'generic':1});before=p.read_bytes()
            with self.assertRaises(FileExistsError):PLAN.write_new(p,{'generic':2})
            self.assertEqual(p.read_bytes(),before)
            with self.assertRaises(ValueError):PLAN.write_new(Path(t)/'nan.json',{'generic':math.nan})
    def test_control_body_rejects_symlinks_and_relative_escape(self):
        with tempfile.TemporaryDirectory()as t:
            p=Path(t);(p/'ok.json').write_text('{}');(p/'link.json').symlink_to(p/'ok.json');(p/'child').mkdir()
            with self.assertRaises(AssertionError):CONTROL.body(p/'link.json')
            with self.assertRaises(AssertionError):CONTROL.ref(p,'child/../ok.json')
            with self.assertRaises(AssertionError):CONTROL.ref(p,'../escape.json')

class GenericControlClosure(unittest.TestCase):
    def setUp(self):
        self.t=tempfile.TemporaryDirectory(prefix='e20-generic-controls-');self.addCleanup(self.t.cleanup)
        self.base=Path(self.t.name);self.project=self.base/'project';self.kit=self.base/'kit';self.scope=self.base/'scope'
        for p in [self.project,self.kit,self.scope]:p.mkdir()
        self.p=CONTROL.P
        helper=self.p+'epoch20/publication/generic_helper.py'
        f=self.project/helper;f.parent.mkdir(parents=True);f.write_text("def walk_current(root):\n    return {p.relative_to(root).as_posix():p.read_bytes() for p in root.rglob('*') if p.is_file()}\n")
        h={'path':helper,'bytes':f.stat().st_size,'sha256':CONTROL.sha(f.read_bytes())}
        put(self.project/(self.p+'epoch20/PLAN_SPEC.json'),{'publication_helper':h})
        for rel in ['epoch20/plan.json','epoch20/candidate-source-freeze.json','audit/epoch20/protocol.json','legal-transfer/epoch20/input-recipe.json','legal-transfer/epoch20/model-assets.lock.json']:
            put(self.project/(self.p+rel),{'generic':rel})
        put(self.project/(self.p+'legal-transfer/epoch20/benchmark-refresh.json'),{'JevBench':{'leader':'GENERIC','Capability':0,'headline_display':0,'source':{'at':'GENERIC'}},'ClaimBench':{'decision_leader':{'model':'GENERIC','accuracy_percent':0},'language_models_at100':[],'official_aggregate':{'at':'GENERIC'}}})
        put(self.project/(self.p+'epoch20/preparation/publisher-status.json'),{'official_result':{'scope':'GENERIC','score':None,'rank':None,'verified':False}})
        put(self.scope/'owner.json',{'run_id':'GENERIC','pid':os.getpid(),'started_at':'2026-01-01T00:00:00+00:00','expires_unix':2000000000})
        put(self.kit/'CHECKPOINT_MANIFEST.json',{'project_files':[{'path':f'historical/{n}.txt','bytes':0,'sha256':'0'*64}for n in range(2813)]})
        put(self.kit/'CONTINUATION.json',{'benchmark_targets':{'JevBench':{},'ClaimBench':{}},'cumulative_budget_ledger':{'cumulative_native_attempts':19,'total_historical_attempts':19},'epochs':[],'exposed_development_sets':[],'unused_confirmation_sets':[{'document_ids':[308,159,284,501,267,494,261,313],'globally_retired':False}]})
        self.cp_sha=CONTROL.sha((self.kit/'CHECKPOINT_MANIFEST.json').read_bytes())
    def args(self,name,mode='source'):
        return argparse.Namespace(project=self.project,kit=self.kit,scope=self.scope,out=self.base/name,mode=mode,parent='GENERIC')
    def render(self,args):
        with patch.object(CONTROL,'OLD_CP',self.cp_sha):return CONTROL.build(args)
    def test_source_is_active_zero_immediate_and_one_conditional_each(self):
        a=self.args('source');self.render(a);active=json.loads((a.out/'ACTIVE_RUN.json').read_bytes());cont=json.loads((a.out/'CONTINUATION.json').read_bytes())
        self.assertTrue(active['experiments_active']);self.assertEqual(active['native_allowed'],0)
        self.assertEqual(active['native_allowed_after_exact_remote_readback'],1)
        self.assertEqual(active['conditional_confirmation_after_independent_DEV_runtime_gates'],1)
        self.assertEqual(cont['active_run']['native_allowed'],0)
        self.assertEqual(cont['cumulative_budget_ledger']['publication_period_native_calls_allowed'],0)
    def test_final_retires_inputs_without_inventing_annotation_or_NLI_reads(self):
        manifest={'actual_execution':{'worker_attempts':2,'owned_live_processes_closed':True},'all_slots_closed':True,'status':'GENERIC_REJECTION','engineering_qualified':True,'benchmark_accepted':False,'data_roles':{'confirmation_retired':True,'confirmation_model_consumed':False,'confirmation_annotation_choices_used':0,'confirmation_NLI_forward_pairs':0,'DEV_inputs_projected':True,'DEV_retirement_statement':'GENERIC_ONLY'},'cumulative_execution':{'native_corpus_attempts_including_failed_request':21},'next_research_priority':'GENERIC','finished_at':'2026-01-01T00:01:00+00:00'}
        for n in ['RESULTS.json','USED_IDENTITIES.json','SOURCE_MANIFEST.json','REJECTION_LEDGER.json']:put(self.project/(self.p+'epoch20/'+n),{'generic':n})
        put(self.project/(self.p+'epoch20/EPOCH_MANIFEST.json'),manifest)
        a=self.args('final','final');self.render(a);active=json.loads((a.out/'ACTIVE_RUN.json').read_bytes());cont=json.loads((a.out/'CONTINUATION.json').read_bytes());ledger=cont['cumulative_budget_ledger'];bank=cont['unused_confirmation_sets'][0]
        self.assertFalse(active['experiments_active']);self.assertEqual(active['native_allowed'],0);self.assertEqual(active['native_allowed_after_exact_remote_readback'],0);self.assertEqual(active['conditional_confirmation_after_independent_DEV_runtime_gates'],0)
        self.assertEqual(ledger['cumulative_native_process_attempts_including_qualification'],22);self.assertEqual(ledger['cumulative_native_attempts'],21);self.assertEqual(ledger['total_historical_attempts'],21)
        self.assertTrue(bank['globally_retired']);self.assertTrue(bank['epoch20_model_unused']);self.assertEqual(bank['epoch20_annotation_choices_used'],0);self.assertEqual(bank['epoch20_NLI_forward_pairs'],0)
    def test_new_output_and_exact_helper_identity_are_required(self):
        a=self.args('used');a.out.mkdir()
        with self.assertRaises(AssertionError):self.render(a)
        p=self.project/(self.p+'epoch20/PLAN_SPEC.json');spec=json.loads(p.read_bytes());spec['publication_helper']['sha256']='0'*64;put(p,spec)
        a=self.args('wrong-helper')
        with self.assertRaises(AssertionError):self.render(a)
        self.assertFalse(a.out.exists())

if __name__=='__main__':unittest.main(verbosity=2)
