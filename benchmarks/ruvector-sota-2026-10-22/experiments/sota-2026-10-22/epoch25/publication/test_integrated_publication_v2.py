"""Integrated author-synthetic controls fixtures; no science input or model calls.

Each test traverses the real checked_controls path with all3465 inherited rows,
real temporary source bytes, sealed references and prior source controls. Empty
historical files share one inode to keep the test's disk footprint small.
"""
from __future__ import annotations
import sys
sys.dont_write_bytecode = True
import copy
import os
from pathlib import Path
import shutil
import tempfile
import unittest
from types import SimpleNamespace
import publication_common_v1 as c
import stage_publication_v1 as s


def save(path, value):
    path.parent.mkdir(parents=True,exist_ok=True)
    path.write_bytes(c.encoded(value,pretty=True))


def row(path, data):
    return {'path':path,'bytes':len(data),'sha256':c.sha(data)}


class IntegratedPublicationControls(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory(prefix='e24-publication-integrated-')
        cls.root = Path(cls.tmp.name)
        cls.project = cls.root/'project';cls.project.mkdir()
        cls.kit = cls.root/'kit';cls.kit.mkdir()
        cls.source = cls.root/'source-controls';cls.source.mkdir()
        cls.final = cls.root/'final-controls';cls.final.mkdir()
        cls.old_rejections = {'rejections':[{'epoch':23,'status':'closed'}],
            'preparation_blocks':['inherited blocker'],'epoch24_decision':{'accepted':False}}
        files = {'history/rejection.json':c.encoded(cls.old_rejections),
            'history/archive.txt':b'lossless archive\n',
            'history/extractor.py':b'# inherited extractor\n',
            'history/publication.py':b'# inherited archive helper\n',
            'history/raw.json':b'{}\n'}
        rows = []
        for path,data in files.items():
            target=cls.project/path;target.parent.mkdir(parents=True,exist_ok=True)
            target.write_bytes(data);rows.append(row(path,data))
        empty=cls.root/'empty';empty.write_bytes(b'')
        for i in range(c.OLD_CP_ROWS-len(rows)):
            path='history/empty-%04d.json'%i
            os.link(empty,cls.project/path);rows.append(row(path,b''))
        cls.old_cp={'schema_version':1,'old_nullable_metadata':None,
            'epoch24_owner_recovery':{'generation':2,'unchanged':True},
            'project_files':sorted(rows,key=lambda r:r['path'])}
        save(cls.kit/'CHECKPOINT_MANIFEST.json',cls.old_cp)
        transport={'format':'gzip+base64','required_before_bootstrap':True}
        for key,path in [('archive','history/archive.txt'),('extractor','history/extractor.py'),
                         ('publication_helper','history/publication.py'),('restored_artifact','history/raw.json')]:
            transport[key]=c.ref(cls.project,path)
        transport['standalone_Git_leaf_omitted']='history/raw.json'
        cls.old_budget={key:0 for key in c.FINAL_ZERO_ALLOWANCES}
        cls.old_budget.update(current_epoch_closed=True,scope='ALL_EPOCHS_CLOSED_THROUGH24',
            cumulative_qualification_attempts=2,
            cumulative_native_process_attempts_including_qualification=24,
            cumulative_corpus_attempts_current=22,
            epoch24_closed_qualification={'used':1,'cap':1,'allowed_further':0})
        cls.old_observed={'actual_HTTP_decisions':885,'epoch24_note':'inherited engineering',
            'native_qualification_attempts':2,
            'cumulative_bounded_native_process_attempts_including_qualification':24}
        cls.old_cont={'schema_version':1,'goal_met':False,'official_rank':None,
            'champion':'SubmittedNative104/RRF10 unchanged','used_confirmation_sets':[],
            'unused_confirmation_sets':['unused'],'exposed_development_sets':['historicalDEV'],
            'old_nullable_metadata':None,'epoch24_owner_recovery':{'generation':2},
            'artifact_transport':transport,'active_run':{'state':'EPOCH24_CLOSED'},
            'checkpoint_manifest_sha256':c.sha(c.content(cls.kit/'CHECKPOINT_MANIFEST.json')),
            'prior_published_base_commit':c.BASE_COMMIT,
            'cumulative_budget_ledger':cls.old_budget,'execution_observed':cls.old_observed,
            'epochs':[{'epoch':23,'status':'closed'}],
            'rejection_ledger':c.ref(cls.project,'history/rejection.json'),
            'latest_learning':{'prior':True},'next_research_priority':'inherited',
            'benchmark_refresh':{'prior':True}}
        save(cls.kit/'CONTINUATION.json',cls.old_cont)
        save(cls.kit/'ACTIVE_RUN.json',{'state':'EPOCH24_CLOSED'})
        for item in cls.old_cp['project_files']:
            if item['path'] == 'history/raw.json': continue
            target=cls.kit/item['path'];target.parent.mkdir(parents=True,exist_ok=True)
            os.link(cls.project/item['path'],target)
        cls.baseline={item['path']:s.leaf(item['path'],c.content(cls.kit/item['path']))
            for item in cls.old_cp['project_files'] if item['path']!='history/raw.json'}
        cls.baseline.update({name:s.leaf(name,c.content(cls.kit/name)) for name in c.CONTROLS})

    @classmethod
    def tearDownClass(cls):cls.tmp.cleanup()

    def active(self, final=False):
        return {'state':'EPOCH25_CLOSED' if final else 'EPOCH25_SOURCE_FROZEN_PENDING_REMOTE_ADMISSION',
            'run_id':'author-synthetic','work_active':not final,'experiments_active':False,
            'native_allowed':0,'native_allowed_after_exact_remote_readback':0 if final else 1,
            'conditional_confirmation_after_independent_DEV_runtime_gates':0,
            'owner_pid':c.OWNER_PIN[0],'owner_startticks':c.OWNER_PIN[1],
            'lock_inode':c.OWNER_PIN[2],'OS_lock_held':True,
            'checkpoint_parent':self.source_parent if final else self.lease_parent,
            'all_unspent_epoch25_slots_permanently_closed':final}

    def collect(self):return c.walk_current(self.project)

    def checkpoint(self, current, final=False):
        cp=copy.deepcopy(self.old_cp)
        cp['epoch25_prelaunch']={'source_checkpoint':c.BASE_COMMIT}
        if final:cp['epoch25_final']={'closed':True}
        cp['project_files'] += [row(path,data) for path,data in sorted(current.items())]
        return cp

    def controls(self, directory, cont, current, final=False):
        cp=self.checkpoint(current,final)
        save(directory/'CHECKPOINT_MANIFEST.json',cp)
        cont['checkpoint_manifest_sha256']=c.sha(c.content(directory/'CHECKPOINT_MANIFEST.json'))
        save(directory/'CONTINUATION.json',cont)
        save(directory/'ACTIVE_RUN.json',self.active(final))

    def seal_source(self, cont):
        spec={'epoch':25,'source_checkpoint':c.BASE_COMMIT,'benchmark_roles':copy.deepcopy(s.ROLES)}
        save(self.project/s.FROZEN_REFS['PLAN_SPEC'],spec)
        freeze={'schema_version':1,'epoch':25,'source_checkpoint':c.BASE_COMMIT,
            'source_entries':[c.ref(self.project,path) for path in
                (c.P+'candidate/epoch25/worker.py',s.FROZEN_REFS['PLAN_SPEC'],
                 c.P+'legal-transfer/epoch25/benchmark-refresh.json')]}
        save(self.project/s.FROZEN_REFS['source_freeze'],freeze)
        plan={'epoch':25,'kind':'SOURCE_SCOPE_ENGINEERING','source_checkpoint':c.BASE_COMMIT,
            'expected_actual_native_queries':24,'benchmark_roles':copy.deepcopy(s.ROLES),
            'champion_promotion_allowed':False,'confirmation_execution_allowed':False,
            'publisher_submission_allowed':False,
            'limits':{'worker_attempts':1,'cpu_threads':2,'seconds_per_batch':600,'paid_calls':0,'GPU_calls':0,'NLI_model_initializations':1,'NLI_forward_pairs':18},
            'pins':[c.ref(self.project,s.FROZEN_REFS['source_freeze'])]+freeze['source_entries']}
        save(self.project/s.FROZEN_REFS['plan'],plan)
        cont['epoch25_frozen_study']={key:c.ref(self.project,path) for key,path in s.FROZEN_REFS.items()}
        cont['epoch25_official_refresh']=c.ref(self.project,c.P+'legal-transfer/epoch25/benchmark-refresh.json')
        cont['benchmark_refresh']=cont['epoch25_official_refresh']

    def setUp(self):
        for rel in c.ROOTS:
            path=self.project/rel
            if path.exists():shutil.rmtree(path)
        self.lease_parent='b'*40;self.source_parent='a'*40
        worker=self.project/(c.P+'candidate/epoch25/worker.py')
        worker.parent.mkdir(parents=True,exist_ok=True);worker.write_text('# author-synthetic source\n')
        save(self.project/(c.P+'legal-transfer/epoch25/benchmark-refresh.json'),{'no_official_result':True})
        self.source_cont=copy.deepcopy(self.old_cont)
        self.source_cont.update(active_run=dict(self.active(),path='ACTIVE_RUN.json'),
            prior_published_base_commit=self.lease_parent,epoch25_planning={'source_only':True})
        self.seal_source(self.source_cont)
        self.source_current=self.collect()
        self.controls(self.source,self.source_cont,self.source_current)
        self.actual={key:0 for key in c.COUNT_COUNTERS+c.ZERO_COUNTERS}
        self.actual.update(worker_attempts=1,verified_worker_starts=1,BGE_initializations=1,
            BGE_forwards=2,BGE_texts=3,native_index_initializations=2,
            native_searches_completed=2,native_engineering_batches=1,
            NLI_model_initializations=1,NLI_forward_pairs_attempted=18,
            NLI_forward_pairs_completed=18,NLI_forwards=18,
            owned_live_processes_closed=True,CPU_affinity=[0,1],wall_seconds_including_init_cleanup=1.0)
        self.results={'actual_execution':self.actual,'metrics':None}
        self.acceptance={'engineering_qualified':True,'scope':'author-synthetic publication metadata'}
        self.rejections=copy.deepcopy(self.old_rejections)
        self.rejections['rejections'].append({'epoch':25,'scope':'engineering'})
        self.ledger=copy.deepcopy(self.old_budget)
        self.ledger.update(scope='ALL_EPOCHS_CLOSED_THROUGH25',
            cumulative_qualification_attempts=3,
            cumulative_native_process_attempts_including_qualification=25,
            epoch25_closed_qualification={'used':1,'cap':1,'allowed_further':0,'benchmark_corpora':0})
        self.observed=copy.deepcopy(self.old_observed)
        self.observed.update(native_qualification_attempts=3,
            cumulative_bounded_native_process_attempts_including_qualification=25,
            epoch25_bounded_worker_attempts=1)
        self.manifest={'epoch':25,'kind':'SOURCE_SCOPE_ENGINEERING','all_slots_closed':True,
            'champion_promoted':False,'new_submission':False,'benchmark_accepted':False,
            'engineering_qualified':True,'actual_execution':self.actual,'data_roles':copy.deepcopy(s.ROLES),
            'source_checkpoint':c.BASE_COMMIT,'published_frozen_source_commit':self.source_parent,
            'cumulative_budget_ledger':self.ledger,'cumulative_execution':self.observed,
            'benchmark_accuracy':None,'proper_scores':None,'official_rank':None,'official_SOTA_verified':False}
        self.cont=copy.deepcopy(self.source_cont)
        self.cont.update(active_run=dict(self.active(True),path='ACTIVE_RUN.json'),
            prior_published_base_commit=self.source_parent,cumulative_budget_ledger=self.ledger,
            execution_observed=self.observed,
            epochs=copy.deepcopy(self.old_cont['epochs'])+[{'epoch':25,'native_worker_attempts':1}])
        self.rebind()

    def rebind(self):
        save(self.project/s.FINAL_REFS['results'],self.results)
        save(self.project/s.FINAL_REFS['source_manifest'],{'source_checkpoint':c.BASE_COMMIT})
        save(self.project/s.FINAL_REFS['used_identities'],{'roles':copy.deepcopy(s.ROLES)})
        save(self.project/s.FINAL_REFS['rejection_ledger'],self.rejections)
        save(self.project/s.FINAL_REFS['acceptance_report'],self.acceptance)
        for key,path in s.FINAL_REFS.items():self.manifest[key]=c.ref(self.project,path)
        save(self.project/(c.P+'epoch25/EPOCH_MANIFEST.json'),self.manifest)
        self.cont['latest_learning']={'manifest':c.ref(self.project,c.P+'epoch25/EPOCH_MANIFEST.json')}
        self.cont['rejection_ledger']=self.manifest['rejection_ledger']
        self.current=self.collect();self.controls(self.final,self.cont,self.current,True)

    def check_final(self):
        return s.checked_controls(self.final,self.kit,self.project,self.current,
                                  'final',self.source_parent,self.source)

    def check_source(self):
        return s.checked_controls(self.source,self.kit,self.project,self.source_current,
                                  'source',self.lease_parent)

    def test_integrated_positive_source_final_and_failed_outcome(self):
        self.check_source();self.check_final()
        self.manifest['engineering_qualified']=False
        self.acceptance['engineering_qualified']=False
        self.actual['errors']=1;self.actual['native_searches_completed']=1
        self.rebind();self.check_final()
        self.assertEqual(self.results['actual_execution']['native_searches_completed'],1)

    def test_integrated_all_forbidden_zeros_missing_or_nonzero(self):
        for key in c.ZERO_COUNTERS:
            with self.subTest(counter=key,kind='missing'):
                del self.actual[key];self.rebind()
                with self.assertRaisesRegex(ValueError,'forbidden counter'):self.check_final()
            self.actual[key]=1;self.rebind()
            with self.subTest(counter=key,kind='nonzero'):
                with self.assertRaisesRegex(ValueError,'forbidden counter'):self.check_final()
            self.actual[key]=0

    def test_integrated_current_allowances_and_promotions_rejected(self):
        for key in c.FINAL_ZERO_ALLOWANCES:
            self.ledger[key]=1;self.rebind()
            with self.subTest(allowance=key):
                with self.assertRaisesRegex(ValueError,'allowance not closed'):self.check_final()
            self.ledger[key]=0
        for key in ('champion_promoted','new_submission','benchmark_accepted'):
            self.manifest[key]=True;self.rebind()
            with self.subTest(promotion=key):
                with self.assertRaisesRegex(ValueError,'promotion scope'):self.check_final()
            self.manifest[key]=False

    def test_integrated_observed_rejection_and_budget_history_rejected(self):
        self.observed['actual_HTTP_decisions']=886;self.rebind()
        with self.assertRaisesRegex(ValueError,'Historical observed execution changed'):self.check_final()
        self.observed['actual_HTTP_decisions']=885
        self.rejections['rejections'][0]['status']='rewritten';self.rebind()
        with self.assertRaisesRegex(ValueError,'Historical ledger sequence changed'):self.check_final()
        self.rejections=copy.deepcopy(self.old_rejections)
        self.rejections['rejections'].append({'epoch':25})
        self.ledger['epoch24_closed_qualification']['used']=2;self.rebind()
        with self.assertRaisesRegex(ValueError,'Historical closed/corpus budget changed'):self.check_final()

    def test_integrated_missing_frozen_refs_and_plan_freeze_pin_rejected(self):
        original=copy.deepcopy(self.source_cont)
        for key in s.FROZEN_REFS:
            self.source_cont=copy.deepcopy(original)
            del self.source_cont['epoch25_frozen_study'][key]
            save(self.source/'CONTINUATION.json',self.source_cont)
            with self.subTest(reference=key):
                with self.assertRaisesRegex(ValueError,'frozen references required'):self.check_source()
        self.source_cont=copy.deepcopy(original)
        plan=c.parse(self.project/s.FROZEN_REFS['plan'])
        plan['pins']=[r for r in plan['pins'] if r['path']!=s.FROZEN_REFS['source_freeze']]
        save(self.project/s.FROZEN_REFS['plan'],plan)
        self.source_cont['epoch25_frozen_study']['plan']=c.ref(self.project,s.FROZEN_REFS['plan'])
        self.source_current={path:c.content(self.project/path) for path in self.source_current}
        self.controls(self.source,self.source_cont,self.source_current)
        with self.assertRaisesRegex(ValueError,'sealed source-freeze pin'):self.check_source()

    def test_integrated_author_nli_caps_alias_and_benchmark_scope(self):
        self.check_source();self.check_final()
        original=copy.deepcopy(self.actual)
        for key,value in (('NLI_model_initializations',2),
                          ('NLI_forward_pairs_attempted',19),
                          ('NLI_forward_pairs_completed',19),('NLI_forwards',17)):
            self.actual.clear();self.actual.update(original);self.actual[key]=value
            self.rebind()
            with self.subTest(counter=key):
                with self.assertRaisesRegex(ValueError,'Author-only NLI counters'):self.check_final()
        for key in c.AUTHOR_NLI_COUNTERS:
            self.actual.clear();self.actual.update(original);del self.actual[key]
            self.rebind()
            with self.subTest(missing=key):
                with self.assertRaisesRegex(ValueError,'explicit actual counter'):self.check_final()
        self.actual.clear();self.actual.update(original)
        self.manifest['benchmark_accuracy']=0.75;self.rebind()
        with self.assertRaisesRegex(ValueError,'engineering status'):self.check_final()
        self.manifest['benchmark_accuracy']=None
        self.manifest['proper_scores']={'scope':'benchmark','brier':0.2};self.rebind()
        with self.assertRaisesRegex(ValueError,'engineering status'):self.check_final()

    def test_integrated_final_cannot_reseal_published_source(self):
        worker=self.project/(c.P+'candidate/epoch25/worker.py');worker.write_text('# modified after publication\n')
        self.seal_source(self.cont);self.rebind()
        with self.assertRaisesRegex(ValueError,'Prior published checkpoint'):self.check_final()

    def test_integrated_final_verdict_runtime_and_reference_bindings(self):
        self.acceptance['engineering_qualified']=False;self.rebind()
        with self.assertRaisesRegex(ValueError,'acceptance verdict'):self.check_final()
        self.acceptance['engineering_qualified']=True
        self.results['actual_execution']=dict(self.actual,native_searches_completed=1);self.rebind()
        with self.assertRaisesRegex(ValueError,'exact runtime results'):self.check_final()
        self.results['actual_execution']=self.actual;self.rebind()
        self.cont['rejection_ledger']=c.ref(self.project,'history/rejection.json')
        save(self.final/'CONTINUATION.json',self.cont)
        with self.assertRaisesRegex(ValueError,'rejection ledger reference differs'):self.check_final()

    def test_prepare_runs_integrated_guards_and_pins_transport(self):
        index=self.root/'source-filemap.json';review=self.root/'reviewed-files.json'
        prior_file=self.root/'prior-expected.json'
        save(index,{'source_commit':c.BASE_COMMIT,'files':list(self.baseline.values())})
        prior=copy.deepcopy(self.baseline)
        prior.update({path:s.leaf(path,data) for path,data in self.source_current.items()})
        prior.update({name:s.leaf(name,c.content(self.source/name)) for name in c.CONTROLS})
        save(prior_file,{'scope':c.SCOPE,'files':list(prior.values())})
        save(review,{'files':[row(path,data) for path,data in self.current.items()]})
        args=SimpleNamespace(project=self.project,kit=self.kit,controls_dir=self.final,
            prior_controls_dir=self.source,out=self.root/'synthetic-stage',source_filemap=index,
            reviewed_files=review,prior_expected=prior_file,mode='final',parent=self.source_parent,
            expected_main='1'*40,expected_root='2'*40,expected_bench='3'*40,expected_scope='4'*40)
        result=s.prepare(args)
        self.assertEqual(result['old_CP_rows'],3465)
        meta=c.parse(args.out/'metadata.json')
        self.assertEqual(meta['Git_mutations'],0)
        self.assertTrue(meta['old_CP_metadata_preserved'])
        for request in meta['create_tree_groups']:
            data=c.content(args.out/request['file'])
            self.assertEqual(len(data),request['bytes']);self.assertEqual(c.sha(data),request['sha256'])
            self.assertLess(len(data)+4096,180000)
        prior['CONTINUATION.json']['sha']='0'*40
        save(prior_file,{'scope':c.SCOPE,'files':list(prior.values())})
        args.out=self.root/'rejected-stage'
        with self.assertRaisesRegex(ValueError,'actual published prior tuple'):s.prepare(args)
        self.assertFalse(args.out.exists())


if __name__=='__main__':unittest.main()
