"""Generic full final-report output fixtures; no actual study/case/model reads.

The helper's expected plan SHA is set only to each invented temporary plan SHA.
This never substitutes or invokes the actual research admission chain.
"""
from datetime import datetime
import hashlib
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest

P=Path(__file__).resolve().parents[1]


def write(path,value):
    path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(value,indent=2)+'\n')


def digest(path):return hashlib.sha256(path.read_bytes()).hexdigest()


class FullReporting(unittest.TestCase):
    def setUp(self):
        spec=importlib.util.spec_from_file_location('independent_generic_final_report',P/'engine-reporting/build_final.py')
        self.m=importlib.util.module_from_spec(spec);spec.loader.exec_module(self.m)
        self.temp=tempfile.TemporaryDirectory(prefix='e18-final-reporting-review-')
        self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name);self.s=self.root/self.m.PREFIX;self.e=self.s/'epoch18'
        write(self.e/'plan.json',{'pins':[{'path':f'generic/source-{n}.txt','sha256':'0'*64}for n in range(415)]})
        self.m.PLAN_SHA=digest(self.e/'plan.json')
        rows=[]
        for n in range(88):
            f=self.root/f'scientific/generic-{n}.py';f.parent.mkdir(exist_ok=True)
            f.write_text('# Generic public source fixture\n')
            rows.append({'path':f.relative_to(self.root).as_posix(),'bytes':f.stat().st_size,'sha256':digest(f)})
        write(self.e/'candidate-source-freeze.json',{'source_checkpoint':self.m.SOURCE,'files':rows})
        for rel in self.m.RETAIN[:3]:write(self.root/rel,{'generic':'retained metadata failure'})
        readback=self.root/self.m.RETAIN[-2]
        write(readback,{'independent_remote_readback_passed':True,'commit':'GENERIC_PUBLISHED_SOURCE'})
        write(self.root/self.m.RETAIN[-1],{'checks_passed':True,'plan_sha256':self.m.PLAN_SHA,
            'independent_readback_sha256':digest(readback),'source_commit':'GENERIC_PUBLISHED_SOURCE',
            'at':'2026-10-23T12:00:00+00:00'})
        write(self.e/'USED_IDENTITIES.pre-native.json',{
            'development':{'annotation_choices_projected':24,'model_attempted':False,
                           'records':[{'id':'GENERIC_DEV_'+str(n)}for n in range(24)]},
            'confirmation':{'annotation_choices_projected':0,'model_attempted':False,
                            'records':[{'id':'GENERIC_CONF_'+str(n)}for n in range(24)]}})
        write(self.s/'epoch17/EPOCH_MANIFEST.json',{'cumulative_execution':dict(self.m.BASE)})
        write(self.s/'epoch17/REJECTION_LEDGER.json',{'rejections':[]})
        for name in ('benchmark-refresh.json','publisher-status.json'):
            write(self.s/'legal-transfer/epoch18'/name,{'generic':'sanitized public aggregate'})

    def phase(self,name):
        folder=self.e/'runs'/name
        write(folder/'popen-attempt.json',{'source_plan_sha256':self.m.PLAN_SHA})
        write(folder/'attempt.json',{'source_plan_sha256':self.m.PLAN_SHA,
            'invocation_started_unix':datetime.fromisoformat('2026-10-23T12:00:01+00:00').timestamp()})
        write(folder/'completion.json',{'source_plan_sha256':self.m.PLAN_SHA,'native_process_started':True})
        write(folder/'report.json',{name+'_completed':24})
        write(folder/'runtime.json',{'phase_initialization_seconds':3,
            'receipt':{'initialization_wall_seconds':2,'old_base_NLI_session_initialized':True,
                       'new_reader':{'model_initializations':1,'quantization_initializations':1}}})
        counters={key:24 for key in self.m.COUNTERS}
        counters.update(new_reader_forward_pairs_attempted=72,new_reader_forward_pairs_completed=72,
            previous_reader_forward_pairs_attempted=24,previous_reader_forward_pairs_completed=24,
            nli_forward_pairs_attempted=96,nli_forward_pairs_completed=96)
        write(folder/'final-engine.json',{'execution_after_close':{'counters':counters}})
        write(folder/(name+'-comparison.json'),{'metrics':{'GENERIC_ARM':{'correct':11,'n':24}},
            'typed_metrics':{'GENERIC_ARM':{'correct':3,'n':24}},'typed_confusions':{'generic':True}})
        for leaf in ('records.jsonl','started-requests.jsonl'):(folder/leaf).write_text('{}\n'*24)
        (folder/'wire.jsonl').write_text(''.join(json.dumps({'id':'GENERIC_'+str(n),'status':200,
            'elapsed_s':1.25,'response':'OPAQUE_FIXTURE_NEVER_INSPECTED'})+'\n'for n in range(24)))

    def build(self,conf=False):
        self.phase('development')
        if conf:
            self.phase('confirmation')
            write(self.s/'legal-transfer/epoch18/confirmation-materialization.json',{'annotation_choices_projected':24})
            (self.s/'legal-transfer/epoch18/confirmation24.jsonl').write_text('OPAQUE_FIXTURE_NEVER_PARSED\n')
        n=2 if conf else 1
        write(self.e/'study-completion.json',{'actual_native_attempts':n,'allowed_further_attempts_in_closed_study':0})
        decision=self.s/'audit/epoch18/generic-independent-decision.json'
        write(decision,{'checks_passed':True,'plan_sha256':self.m.PLAN_SHA,'accepted':False,
            'status':'GENERIC_REJECTED_DIAGNOSTIC','next_priority':'Generic bounded new hypothesis.',
            'actual_native_process_reservations':n,'verified_worker_starts':n,'confirmation_consumed':conf})
        return self.m.build(self.root,decision)

    def assert_references(self,objects):
        manifest=objects['EPOCH_MANIFEST.json'];ledger=objects['REJECTION_LEDGER.json']
        for key,name in [('results','RESULTS.json'),('used_identities','USED_IDENTITIES.json'),
                         ('rejection_ledger','REJECTION_LEDGER.json')]:
            raw=(json.dumps(objects[name],ensure_ascii=False,indent=2,allow_nan=False)+'\n').encode()
            self.assertEqual(manifest[key]['bytes'],len(raw))
            self.assertEqual(manifest[key]['sha256'],hashlib.sha256(raw).hexdigest())
        self.assertEqual(ledger['used_identity_manifest'],manifest['used_identities'])

    def test_complete_development_updates_nested_roles_and_keeps_unused_confirmation(self):
        objects=self.build();used=objects['USED_IDENTITIES.json'];actual=objects['EPOCH_MANIFEST.json']['actual_execution']
        self.assertTrue(used['development']['model_attempted'])
        self.assertFalse(used['confirmation']['model_attempted'])
        self.assertEqual(used['confirmation']['annotation_choices_projected'],0)
        self.assertEqual(used['development']['annotation_choices_projected'],24)
        self.assertFalse(used['confirmation_retired_forever_DEV'])
        self.assertEqual(actual['native_process_attempts'],1)
        self.assertEqual(actual['successful_HTTP_decisions'],24)
        self.assertEqual(objects['EPOCH_MANIFEST.json']['cumulative_execution']['actual_HTTP_successful_decisions'],885)
        self.assertFalse(objects['EPOCH_MANIFEST.json']['accepted'])
        self.assertIsNone(objects['EPOCH_MANIFEST.json']['official_rank'])
        self.assert_references(objects)

    def test_consumed_confirmation_updates_nested_annotations_and_retirement(self):
        objects=self.build(True);used=objects['USED_IDENTITIES.json']
        self.assertTrue(used['development']['model_attempted'])
        self.assertTrue(used['confirmation']['model_attempted'])
        self.assertEqual(used['confirmation']['annotation_choices_projected'],24)
        self.assertTrue(used['confirmation_retired_forever_DEV'])
        self.assertEqual(used['originaltrain_partition']['reserved_unused'],16)
        self.assert_references(objects)


if __name__=='__main__':unittest.main(verbosity=2)
