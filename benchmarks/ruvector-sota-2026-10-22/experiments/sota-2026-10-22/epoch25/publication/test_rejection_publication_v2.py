"""Synthetic rejection-publication guard tests; no science, oracle or model runs."""
from __future__ import annotations
import sys
sys.dont_write_bytecode = True
import copy
import json
from pathlib import Path
from types import SimpleNamespace
import tempfile
import unittest
import publication_common_v1 as c
import stage_publication_v1 as original_stage
import publication_rejection_v2 as r
from test_publication_guards_v1 import final_manifest, plan


class RejectedPublicationGuards(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix='epoch25-rejection-publisher-')
        self.project = Path(self.tmp.name)
        self.manifest = final_manifest()
        self.manifest['engineering_qualified'] = False
        self.actual = self.manifest['actual_execution']
        self.actual.update(BGE_initializations=1, BGE_forwards=12, BGE_texts=18,
            native_index_initializations=6, native_searches_completed=6,
            native_engineering_batches=1, errors=1,
            Python_network_operations_attempted=1, wall_seconds_including_init_cleanup=2.5)
        counters = {name: 0 for name in c.ZERO_COUNTERS+r.EXTRA_RAW_ZERO_COUNTERS}
        for key, source in r.RAW_ALIASES.items():counters[source] = self.actual[key]
        counters.update(NLI_model_initializations_completed=1,
            NLI_forward_calls_attempted=18,NLI_forward_calls_completed=18)
        self.raw = {'epoch':25,'status':'FAILED_ENGINEERING_PROCESS',
            'accuracy':None,'proper_scores':None,'benchmark_results':None,
            'roles_used':copy.deepcopy(original_stage.ROLES),'counters':counters,
            'errors':[{'type':'ValueError','message':'Forbidden operation counter nonzero'}],
            'worker_pid':42}
        self.outer = {'epoch':25,'phase':'engineering','status':'WORKER_FAILED_OR_TIMEOUT',
            'exit_code':2,'uncertain_start':False,'owned_live_processes_closed':True,
            'owned_live_group_members':[],'cleanup_errors':[],
            'allowed_further_epoch25_workers':0,'worker_attempts_reserved':1,
            'verified_worker_starts':1,'CPU_affinity':[0,1],
            'wall_seconds_including_init_cleanup':2.5,'Popen_returned_pid':42}
        self.progress = [{'worker_pid':42,'event':{'event':'OFFLINE_NETWORK_REFUSAL',
            'audit_event':'socket.bind'},'counters':{r.NETWORK:1}}]
        self.acceptance = {'engineering_qualified':False,
            'status':'REJECTED_AUTHORED_ENGINEERING_QUALIFICATION',
            'benchmark_accepted':False,'champion_promoted':False}

    def tearDown(self):
        self.tmp.cleanup()

    def rejected(self, function, *args):
        with self.assertRaises((ValueError, UnicodeDecodeError)):
            function(*args)

    def documents(self):
        return r.validate_rejected_documents(self.raw,self.outer,self.progress,
                                             self.actual,self.acceptance)

    def save(self, path, value, lines=False):
        file=self.project/path;file.parent.mkdir(parents=True,exist_ok=True)
        body=b''.join(c.encoded(row,pretty=False)+b'\n' for row in value) if lines else c.encoded(value,pretty=True)
        file.write_bytes(body)
        return c.ref(self.project,path)

    def synthetic_provenance(self):
        # Only the synthetic validator's private globals use synthetic identities.
        # Production incident constants and all original publisher globals stay intact.
        identities={}
        identities['raw_receipt']=self.save(r.INCIDENT_REFS['raw_receipt']['path'],self.raw)
        self.outer['raw_bytes']=identities['raw_receipt']['bytes']
        self.outer['raw_sha256']=identities['raw_receipt']['sha256']
        identities['outer_receipt']=self.save(r.INCIDENT_REFS['outer_receipt']['path'],self.outer)
        identities['progress_receipt']=self.save(r.INCIDENT_REFS['progress_receipt']['path'],self.progress,True)
        acceptance=self.save(original_stage.FINAL_REFS['acceptance_report'],self.acceptance)
        self.manifest['acceptance_report']=acceptance
        self.manifest['rejected_execution_provenance']={**copy.deepcopy(identities),
            'reason':'Frozen zero-attempt publisher cannot publish the unchanged failed incident.',
            'publication_scope':r.PUBLICATION_SCOPE,'audit_event':'socket.bind',
            'attempted_operations':1,'destination_and_initiator':'NOT_RECORDED'}
        checkpoint={row['path']:row for row in [*identities.values(),acceptance]}
        validator=r._clone(r.validate_rejected_provenance,
                           {'INCIDENT_REFS':identities,'ACCEPTANCE_REF':acceptance})
        return validator,checkpoint,identities

    def test_false_verdict_and_honest_counter_publish_without_normalization(self):
        before=copy.deepcopy(self.manifest)
        self.assertEqual(r.check_rejected_manifest(self.manifest,plan(6)),1)
        self.assertTrue(self.documents())
        self.assertEqual(self.manifest,before)
        validator,checkpoint,_=self.synthetic_provenance()
        validator(self.project,self.manifest,checkpoint)
        self.assertEqual(self.actual[r.NETWORK],1)

    def test_original_publisher_still_rejects_both_false_and_true_qualification(self):
        self.rejected(c.check_final_manifest,self.manifest,plan(6))
        qualified=copy.deepcopy(self.manifest);qualified['engineering_qualified']=True
        self.rejected(c.check_final_manifest,qualified,plan(6))
        self.rejected(r.check_rejected_manifest,qualified,plan(6))
        self.assertIs(original_stage.check_final_manifest,c.check_final_manifest)
        self.assertIn(r.NETWORK,c.ZERO_COUNTERS)

    def test_zero_masking_missing_boolean_or_larger_network_count_rejected(self):
        for value in (0,2,True):
            bad=copy.deepcopy(self.manifest);bad['actual_execution'][r.NETWORK]=value
            self.rejected(r.check_rejected_manifest,bad,plan(6))
        bad=copy.deepcopy(self.manifest);del bad['actual_execution'][r.NETWORK]
        self.rejected(r.check_rejected_manifest,bad,plan(6))

    def test_all_other_sixteen_zeros_and_budget_overflows_remain_forbidden(self):
        self.assertEqual(len(r.REJECTION_ZERO_COUNTERS),16)
        for key in r.REJECTION_ZERO_COUNTERS:
            bad=copy.deepcopy(self.manifest);bad['actual_execution'][key]=1
            with self.subTest(counter=key):self.rejected(r.check_rejected_manifest,bad,plan(6))
            bad=copy.deepcopy(self.manifest);del bad['actual_execution'][key]
            self.rejected(r.check_rejected_manifest,bad,plan(6))
        for key,value in (('worker_attempts',2),('NLI_model_initializations',2),
                          ('NLI_forward_pairs_attempted',19),('native_searches_completed',7)):
            bad=copy.deepcopy(self.manifest);bad['actual_execution'][key]=value
            self.rejected(r.check_rejected_manifest,bad,plan(6))

    def test_failed_raw_outer_and_independent_verdict_cannot_be_relabelled(self):
        for document,key,value in ((self.raw,'status','ENGINEERING_PROCESS_COMPLETED'),
            (self.outer,'status','WORKER_COMPLETED'),(self.outer,'exit_code',0),
            (self.outer,'uncertain_start',True),(self.acceptance,'engineering_qualified',True),
            (self.acceptance,'status','ACCEPTED'),(self.acceptance,'benchmark_accepted',True),
            (self.acceptance,'champion_promoted',True)):
            old=document[key];document[key]=value
            with self.subTest(field=key):self.rejected(self.documents)
            document[key]=old
        del self.acceptance['benchmark_accepted'];self.rejected(self.documents)

    def test_raw_paid_gpu_counters_and_canonical_aliases_cannot_disagree(self):
        for key in ('paid_API_calls','GPU_calls',r.NETWORK,'NLI_forward_calls_completed'):
            old=self.raw['counters'][key];self.raw['counters'][key]=old+1
            with self.subTest(counter=key):self.rejected(self.documents)
            self.raw['counters'][key]=old
        for key in ('BGE_forwards','native_searches_completed','errors',r.NETWORK):
            old=self.actual[key];self.actual[key]=0
            with self.subTest(alias=key):self.rejected(self.documents)
            self.actual[key]=old
        self.actual['wall_seconds_including_init_cleanup']=3.0;self.rejected(self.documents)

    def test_exactly_one_nested_socket_bind_refusal_required(self):
        original=copy.deepcopy(self.progress)
        for replacement in ([],original+original,
            [{'worker_pid':42,'event':{'event':'OFFLINE_NETWORK_REFUSAL',
              'audit_event':'socket.connect'},'counters':{r.NETWORK:1}}],
            [{'worker_pid':42,'event':{'event':'OFFLINE_NETWORK_REFUSAL',
              'audit_event':'socket.bind'},'counters':{r.NETWORK:0}}]):
            self.progress=replacement;self.rejected(self.documents)
        self.progress=original;self.progress[0]['worker_pid']=43;self.rejected(self.documents)

    def test_receipt_bytes_refs_checkpoint_and_unknown_destination_are_exact(self):
        validator,checkpoint,identities=self.synthetic_provenance()
        validator(self.project,self.manifest,checkpoint)
        receipt_identities={**identities,'oracle_receipt':self.manifest['acceptance_report']}
        for key,identity in receipt_identities.items():
            path=self.project/identity['path'];body=path.read_bytes();path.write_bytes(body+b'\n')
            with self.subTest(receipt=key):self.rejected(validator,self.project,self.manifest,checkpoint)
            path.write_bytes(body)
        bad=copy.deepcopy(self.manifest);bad['rejected_execution_provenance']['raw_receipt']['sha256']='0'*64
        self.rejected(validator,self.project,bad,checkpoint)
        bad=copy.deepcopy(self.manifest);bad['rejected_execution_provenance']['destination_and_initiator']='inferred IPC'
        self.rejected(validator,self.project,bad,checkpoint)
        broken=copy.deepcopy(checkpoint);del broken[identities['progress_receipt']['path']]
        self.rejected(validator,self.project,self.manifest,broken)

    def test_private_clones_preserve_all_other_original_guard_globals_and_code(self):
        pairs=[(r._frozen_manifest_checks,c.check_final_manifest,'ZERO_COUNTERS'),
            (r._frozen_final_evidence,original_stage.checked_final_evidence,'check_final_manifest'),
            (r._checked_controls,original_stage.checked_controls,'checked_final_evidence'),
            (r._prepare,original_stage.prepare,'checked_controls')]
        for private,original,exception in pairs:
            self.assertIs(private.__code__,original.__code__)
            self.assertIsNot(private.__globals__,original.__globals__)
            for key,value in original.__globals__.items():
                if key!=exception:self.assertIs(private.__globals__[key],value)
        self.assertIs(r._prepare.__globals__['checked_controls'],r._checked_controls)
        self.assertIs(original_stage.checked_controls.__globals__['checked_final_evidence'],
                      original_stage.checked_final_evidence)

    def test_rejection_entrypoint_cannot_publish_source_or_lease(self):
        for mode in ('source','lease'):
            self.rejected(r.prepare_rejected,SimpleNamespace(mode=mode))

    def test_new_and_frozen_helpers_obey_public_text_and_frozen_hashes(self):
        r.verify_frozen_helpers()
        for name in ('publication_rejection_v2.py','stage_rejected_publication_v2.py',
                     'test_rejection_publication_v2.py'):
            c.public_text(c.P+'epoch25/publication/'+name,(r.DIRECTORY/name).read_bytes())


if __name__=='__main__':
    unittest.main()
