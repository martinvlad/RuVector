"""Metadata-only recovery checks. No current stage, owner, Git, or science mode."""
import sys
sys.dont_write_bytecode=True
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
import copy,importlib.util,json,tempfile,unittest
import render_transports as renderer
import restore_e49_overlay as overlay
HERE=Path(__file__).resolve().parent
spec=importlib.util.spec_from_file_location('guard',HERE/'recovery-v2/guard.py');g=importlib.util.module_from_spec(spec);spec.loader.exec_module(g);sys.modules['guard']=g
spec=importlib.util.spec_from_file_location('stage',HERE/'recovery-v2/stagebuilder.py');s=importlib.util.module_from_spec(spec);spec.loader.exec_module(s)
class RecoveryMetadata(unittest.TestCase):
    def test_three_retired_objects_deny_requests(self):
        self.assertEqual(g.DENY,set(renderer.DENY))
        for denied in renderer.DENY:
            with self.assertRaises(ValueError):g.validate_request(g.TOOLS['ref'],dict(repository_full_name=g.REPO,branch_name=g.BRANCH,sha=denied,expected_sha='1'*40,force=False))
    def test_bound_separate_recovery_and_original_owner(self):
        self.assertEqual(str(g.W),renderer.LEASE+'/recovery-transport');self.assertEqual(str(g.R),renderer.LEASE+'/project')
        self.assertEqual(g.OWNER['path'],renderer.LEASE+'/owner.json');self.assertEqual(g.OWNER['bytes'],711)
        self.assertEqual(g.KIND,'ARCHIVE_RECOVERY_NO_SCI');self.assertEqual(g.ROOTS,(renderer.PREFIX,))
        guard=(HERE/'recovery-v2/guard.py').read_text();stage=(HERE/'recovery-v2/stagebuilder.py').read_text()
        self.assertIn("o['lock_inode'] == 13626",guard);self.assertIn("overlay['canonical_members'] == 137",stage)
        self.assertIn("key = 'epoch49_publication_recovery15'",stage)
    def test_archive_all_members_and_project_overlay_verified(self):
        files=overlay.verified(HERE/'PUBLIC_RECOVERY.envelope.v1.json',HERE/'ARCHIVE_OVERLAY.v1.json')
        self.assertEqual(len(files),76);self.assertTrue(all(p.startswith(overlay.PREFIXES) for p in files))
        self.assertNotIn('operational/publication/mutation-journal.jsonl',files)
    def test_historical_controls_and_separate_overlay_rows(self):
        cont=dict(goal_met=False,official_rank=None,champion={'id':'native104'},unused_confirmation_sets=[],active_run={'epoch':48},checkpoint_manifest_sha256='old',epoch48_final={'doc48':48,'BGE_dimensions':384},cumulative_budget_ledger={'epoch48_actual_execution':{'old':True}})
        cp=dict(project_files=[dict(path='old.json',bytes=1,sha256='1'*64)],epoch48_final={'prior_ACK':117})
        record=json.loads((HERE/'RECOVERY_RECORD.v1.json').read_text())
        x=dict(phase='source',CONT_patch={'epoch49_publication_recovery15':record},CP_phase_record=record,ACTIVE=dict(epoch=50,phase='source',source_checkpoint=g.BASE,owner_sha256=g.OWNER['sha256'],kind=g.KIND,work_active=True,experiments_active=False,OS_lock_observation_scope='PREPUBLICATION_SNAPSHOT_NOT_CURRENT_REMOTE_LEASE',publication_is_not_scientific_authorization=True))
        newcont,newcp,_=s.preserve_controls(cont,cp,x,[dict(path=renderer.PREFIX+'envelope.json',bytes=2,sha256='2'*64)])
        self.assertTrue(g.same(newcont['epoch48_final'],cont['epoch48_final']));self.assertTrue(g.same(newcp['epoch48_final'],cp['epoch48_final']))
        self.assertEqual(len(newcp['project_files']),2);self.assertFalse(any('/epoch49/' in r['path'] for r in newcp['project_files']))
        self.assertEqual(newcp['epoch49_publication_recovery15']['original_E49_publication']['UNKNOWN'],1)
    def test_bad_readback_cannot_render_standard(self):
        with tempfile.TemporaryDirectory(dir=HERE) as td:
            with self.assertRaises(AssertionError):renderer.render('standard',Path(td)/'out',{'checks_passed':False})
    def test_factual_success_ack_and_uncertainty_stop(self):
        request=dict(sha='1'*40);fresh=dict(ref='refs/heads/'+g.BRANCH,object={'sha':'1'*40})
        self.assertIsNone(g.acknowledge(g.TOOLS['ref'],request,{'success':True},fresh_ref=fresh))
        with self.assertRaises(ValueError):g.clean([dict(phase='intent',id='e50-recovery-source-g15-test',kind='tree')])
if __name__=='__main__':
    result=unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(RecoveryMetadata))
    print(json.dumps(dict(checks_passed=result.wasSuccessful(),tests=result.testsRun,failures=len(result.failures),errors=len(result.errors),actual_Git_or_SCI_calls=0,actual_current_owner_or_stage_modes=0,archive_verification_only=True),sort_keys=True));raise SystemExit(not result.wasSuccessful())
