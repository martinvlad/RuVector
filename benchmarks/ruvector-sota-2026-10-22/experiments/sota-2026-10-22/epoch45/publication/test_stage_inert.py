"""Actual two-phase stage builder on invented metadata; no publication or science."""
import sys
sys.dont_write_bytecode=True
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
import json,tempfile,unittest
from types import SimpleNamespace
from unittest.mock import patch
import publication_common as c
import build_phase_stage as b
import mutation_guard as g

class StageIntegration(unittest.TestCase):
 def test_actual_stage_source_and_final_ids_are_guard_compatible(self):
  with tempfile.TemporaryDirectory(prefix='e45-stage-inert-')as d:
   w=Path(d)
   def put(name,value):
    p=w/name;c.write(p,value if isinstance(value,bytes)else c.encoded(value));return c.pin(p)
   oldrows=[{'path':f'old/{i}.txt','bytes':1,'sha256':c.sha(b'x')}for i in range(7522)]+[{'path':f'CP-only/{i}.txt','bytes':1,'sha256':c.sha(b'x')}for i in range(70)]
   files=[{'path':r['path'],'mode':'100644','type':'blob','sha':c.git(b'x'),'size':1}for r in oldrows[:7522]]+[{'path':f'Git-only/{i}.txt','mode':'100644','type':'blob','sha':c.git(b'x'),'size':1}for i in range(74)]
   def baselines(name,files,commit):
    scope=c.full_scope_sha(files);bbrows=[{'path':'ruvector-sota-2026-10-22','mode':'040000','type':'tree','sha':scope}];bb={'sha':c.tree_sha(bbrows),'tree':bbrows};rbrows=[{'path':'benchmarks','mode':'040000','type':'tree','sha':bb['sha']}];rb={'sha':c.tree_sha(rbrows),'tree':rbrows}
    return put(name+'-map.json',{'commit':commit,'root':rb['sha'],'scope_sha':scope,'files':files}),put(name+'-root.json',rb),put(name+'-bench.json',bb)
   old={'goal_met':False,'official_rank':None,'champion':{'name':'native104'},'epoch42_archive_recovery':{},'epoch44_publication_recovery9':{'archive_overlay':{'CP_project_files_includes_overlay55':False,'project_additions_AFTER_standard_restore':55,'canonical_members':137}},'epoch44_final':{},'epoch44_frozen_study':{},'epoch44_data_roles':{},'unused_confirmation_sets':[62,321,2],'cumulative_budget_ledger':{'inherited':{'executed':False}}}
   cp=put('CP.json',{'project_files':oldrows,'inherited':{'unchanged':False}});cont=put('CONT.json',old);projection=put('projection.json',{})
   for name,raw in(('CHECKPOINT_MANIFEST.json',c.body(cp['path'])),('CONTINUATION.json',c.body(cont['path'])),('ACTIVE_RUN.json',b'{}')):files.append({'path':name,'mode':'100644','type':'blob','sha':c.git(raw),'size':len(raw)})
   source_map,root_base,bench_base=baselines('base',files,c.BASE)
   reservation={'epoch':45,'generation':10,'owner_sha256':'f'*64,'reservation_token':'9'*64,'pid':42,'startticks':7,'reserved_worker_slots':1,'permanently_burned_at_SOURCE_publication':True,'execution_counts_from_actual_receipts_only':True,'currentepoch_new_invocations_after_owner_loss_forbidden':True,'missing_receipt_after_owner_loss':'UNKNOWN_PERMANENTLY_NO_RERUN'}
   active={'epoch':45,'phase':'source','source_checkpoint':c.BASE,'remaining_allowance':{'TRAIN':0,'DEV':1,'calibration':0,'CONF':0,'paid_calls':0,'GPU_calls':0,'retries':0},'scientific_authorization_requires_actual_SOURCE_readback':True,'second_native_batch_closed':True,'OS_lock_observation_scope':'PREPUBLICATION_SNAPSHOT_NOT_CURRENT_REMOTE_LEASE','work_active':True,'experiments_active':False,'worker_slot_reservation':reservation,'currentepoch_new_invocations_after_owner_loss_forbidden':True,'missing_receipt_after_owner_loss':'UNKNOWN_PERMANENTLY_NO_RERUN'}
   P='experiments/sota-2026-10-22/epoch45/'
   def artifact(name,raw):
    r=put('artifact-'+name.replace('/','-'),raw);return {'path':P+name,'local_path':r['path'],'bytes':r['bytes'],'sha256':r['sha256']}
   dummy=artifact('fixture.txt',b'invented\n');dr={k:dummy[k]for k in('path','bytes','sha256')};frart=artifact('SOURCE_FREEZE.json',c.encoded({'files':[dr]}));fr={k:frart[k]for k in('path','bytes','sha256')};planart=artifact('plan.json',c.encoded({'worker_slot_reservation':reservation,'source_freeze':fr}));plan={k:planart[k]for k in('path','bytes','sha256')}
   preflight=put('preflight.json',{'checks_passed':True,'actual_source_freeze_reference_closure_verified':True,'plan':plan})
   x={'schema_version':1,'epoch':45,'phase':'source','source_checkpoint':c.BASE,'owner_sha256':'f'*64,'parent':c.BASE,'source_map':source_map,'root_baseline':root_base,'bench_baseline':bench_base,'current_CP':cp,'current_CONT':cont,'archive_projection':projection,'artifacts':[dummy,frart,planart],'ACTIVE':active,'CONT_patch':{'epoch45_frozen_study':{'worker_slot_reservation':reservation}},'CP_phase_record':{'fixture':True},'commit_message':'inert fixture only','plan':plan,'source_preflight':preflight}
   def build(phase,x):
    inp=put(phase+'-input.json',x);approval=put(phase+'-prep.json',{'phase_preparation_allowed':True,'phase_input_sha256':inp['sha256']});a=SimpleNamespace(input=Path(inp['path']),expected_input_sha=inp['sha256'],approval=Path(approval['path']),expected_approval_sha=approval['sha256'],out=w/('stage-'+phase));m=b.build(a)
    expected='e45-'+phase+'-g10';self.assertEqual(m['mutation_ID_prefix'],expected);self.assertTrue(all(i.startswith(expected+'-')for i in m['mutation_ID_order']))
    approved=put(phase+'-publication.json',{'checks_passed':True,'publication_phase_allowed':True,'source_and_denylist_review_passed':True,'dual_unknown_denylist_reviewed':True,'stage_metadata_sha256':c.sha(c.body(a.out/'metadata.json')),'expected_final_root_sha':m['expected_final_root'],'phase':phase,'original_blob5_execution':'UNKNOWN_PERMANENTLY','forbidden_Git_object_sha1':c.FORBIDDEN,'forbidden_Git_objects':sorted(c.FORBIDDEN_OBJECTS),'operational_binding_sha256':'e'*64});g.load_stage(SimpleNamespace(phase=phase,approval=Path(approved['path']),expected_approval_sha=approved['sha256']))
    bypath={r['project_path']:json.loads(c.body(a.out/r['file']))['content'].encode()for r in m['blobs']};return m,bypath
   with patch.object(c,'W',w),patch.object(c,'OWNER_SHA','f'*64),patch.object(c,'OWNER_PID',42),patch.object(c,'OWNER_TICKS',7),patch.object(c,'OWNER_GENERATION',10),patch.object(c,'OPERATIONAL_SHA','e'*64),patch.object(c,'verify_70_projection',return_value={'fixture':True}):
    sm,sourcepayloads=build('source',x)
    cp2=put('SOURCE-CP.json',sourcepayloads['CHECKPOINT_MANIFEST.json']);co2=put('SOURCE-CONT.json',sourcepayloads['CONTINUATION.json']);sourcefiles=json.loads(c.body(w/'stage-source/expected-leaves.json'))['files'];smref,rb,bb=baselines('source',sourcefiles,'b'*40)
    sr=put('actual-SOURCE-fixture.json',{'epoch':45,'phase':'source','verified_actual_full_tree':True,'commit':'b'*40})
    closed=[r for r in json.loads(sourcepayloads['CHECKPOINT_MANIFEST.json'])['project_files']if r['path'].startswith(P)]
    eart=artifact('EPOCH_MANIFEST.json',c.encoded({'epoch':45,'source_checkpoint':c.BASE,'no_project_additions_after_manifest':True,'files':closed}));er={k:eart[k]for k in('path','bytes','sha256')}
    fa=dict(active);fa.update({'phase':'final','work_active':False,'remaining_allowance':{k:0 for k in active['remaining_allowance']}})
    fx={**x,'phase':'final','parent':'b'*40,'source_map':smref,'root_baseline':rb,'bench_baseline':bb,'current_CP':cp2,'current_CONT':co2,'artifacts':[eart],'ACTIVE':fa,'CONT_patch':{'epoch45_final':{'fixture':True}},'actual_SOURCE_receipt':sr,'epoch_manifest':er}
    fm,_=build('final',fx);self.assertEqual(fm['source_parent'],'b'*40);self.assertEqual(fm['CP_only_paths'],sm['CP_only_paths']);self.assertTrue(fm['E44_overlay55_remains_separate_from_CP_rows'])
if __name__=='__main__':unittest.main()
