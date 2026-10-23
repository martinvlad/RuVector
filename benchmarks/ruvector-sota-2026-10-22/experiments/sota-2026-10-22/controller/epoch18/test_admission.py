"""Pure source/metadata admission regression fixtures; no data or inference."""
import copy
import hashlib
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from unittest import mock

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location('epoch18_admission_tests_loop',HERE/'loop.py')
L = importlib.util.module_from_spec(spec)
spec.loader.exec_module(L)
A = L.AD


def metadata_plan():
    # Historical plan metadata only, never its dataset or annotation contents.
    p = json.loads((L.SOURCE/'epoch17/plan.json').read_text())
    p.update(epoch=18,controller_version=L.CONTROLLER_VERSION,revision=L.STUDY_REVISION,
             study_id='native-microsoft-xlarge-typed-reader-e18',prior_closed_epoch17_native_attempts=0,
             measurement_plan=False,operational_prelabel_only=True)
    p['limits']['seconds_per_decision']=30
    p['datasets']={k:v.replace('epoch17/','epoch18/')for k,v in p['datasets'].items()}
    p['lazy_confirmation']={k:v.replace('epoch17/','epoch18/')if isinstance(v,str)else v
                            for k,v in p['lazy_confirmation'].items()}
    p['runtime_admission'].update(max_DEV_units=1,max_confirmation_units=1,
                                 capacity_pending_label_free_inputs=True)
    names=[A.PREFIX+'benchmark/evaluate.py',A.PREFIX+'benchmark/sources/jevbench_scoring.py',
           A.PREFIX+'benchmark/source-manifest.json',
           'experiments/swarm/jevbench-adapter/sources/jevbench_scoring.py']
    p['pins']=[{'path':name,'sha256':A.sha(L.ROOT/name)}for name in names]
    return p


class FullUnmockedBudget(unittest.TestCase):
    def test_actual_full_chain_accepts_thirty_before_any_new_projection(self):
        p=metadata_plan()
        with tempfile.TemporaryDirectory()as temp:
            file=Path(temp)/'SOURCE_METADATA_ONLY.json';file.write_text(json.dumps(p))
            self.assertEqual(L.require_plan(file),p)

    def test_actual_full_chain_rejects_sixty_and_even_twenty_nine(self):
        for value in (60,29,31,True):
            p=metadata_plan();p['limits']['seconds_per_decision']=value
            with tempfile.TemporaryDirectory()as temp:
                file=Path(temp)/'SOURCE_METADATA_ONLY.json';file.write_text(json.dumps(p))
                with self.assertRaises(ValueError):L.require_plan(file)

    def test_actual_full_chain_checks_real_inherited_pin_hashes(self):
        p=metadata_plan();p['pins'][0]['sha256']='0'*64
        with tempfile.TemporaryDirectory()as temp:
            file=Path(temp)/'SOURCE_METADATA_ONLY.json';file.write_text(json.dumps(p))
            with self.assertRaisesRegex(ValueError,'Frozen identity changed'):L.require_plan(file)

    def test_operational_template_parent_blocks_before_launch_or_popen(self):
        with tempfile.TemporaryDirectory()as temp:
            study=Path(temp);file=study/'SOURCE_METADATA_ONLY.json';file.write_text('{}')
            with mock.patch.object(L,'STUDY',study),mock.patch.object(L,'require_plan',return_value=metadata_plan()),mock.patch.object(L.subprocess,'Popen')as popen:
                with self.assertRaisesRegex(ValueError,'Only the final'):L.parent(file)
                popen.assert_not_called()
            self.assertFalse((study/'launch.json').exists());self.assertFalse((study/'runs').exists())

    def test_operational_template_worker_blocks_before_runtime_import(self):
        with mock.patch.object(L,'require_plan',return_value=metadata_plan()),mock.patch.object(L.importlib,'import_module')as imported:
            with self.assertRaisesRegex(ValueError,'Only the final'):
                L.worker(Path('SOURCE_METADATA_ONLY.json'),'1'*64,1000,'development')
            imported.assert_not_called()


class SourceProof(unittest.TestCase):
    def fixture(self,root):
        files=[]
        for name in ('loop.py','receipts.py','scoring.py','admission.py','operational_preflight.py'):
            file=root/A.PREFIX/'controller/epoch18'/name;file.parent.mkdir(parents=True,exist_ok=True)
            file.write_text('GENERIC_SOURCE_METADATA_FIXTURE_'+name)
            files.append({'path':file.relative_to(root).as_posix(),'bytes':file.stat().st_size,'sha256':A.sha(file)})
        snapshot=root/A.PREFIX/'epoch18/candidate-source-freeze.json';snapshot.parent.mkdir(parents=True)
        snapshot.write_text(json.dumps({'source_checkpoint':A.SOURCE_HEAD,'files':files}))
        return snapshot,files

    def test_actual_file_snapshot_sha_and_all_members_required(self):
        with tempfile.TemporaryDirectory()as temp:
            root=Path(temp);snapshot,files=self.fixture(root)
            A.source_snapshot(root,snapshot,A.sha(snapshot))
            changed=root/files[0]['path'];changed.write_text('CORRUPTED')
            with self.assertRaises(ValueError):A.source_snapshot(root,snapshot,A.sha(snapshot))

    def test_snapshot_cannot_omit_actual_controller_helper(self):
        with tempfile.TemporaryDirectory()as temp:
            root=Path(temp);snapshot,_=self.fixture(root)
            value=json.loads(snapshot.read_text());value['files'].pop();snapshot.write_text(json.dumps(value))
            with self.assertRaises(ValueError):A.source_snapshot(root,snapshot,A.sha(snapshot))

    def test_projection_and_launch_markers_block_prelabel_operation(self):
        for namespace,name in (('legal-transfer/epoch18','dev-inputs-only.json'),('epoch18','launch.json')):
            with tempfile.TemporaryDirectory()as temp:
                root=Path(temp);A.assert_unprojected(root)
                marker=root/A.PREFIX/namespace/name;marker.parent.mkdir(parents=True);marker.write_text('{}')
                with self.assertRaises(ValueError):A.assert_unprojected(root)

    def test_path_escape_and_symlink_refused(self):
        with tempfile.TemporaryDirectory()as temp:
            root=Path(temp);target=root/'regular.json';target.write_text('{}')
            (root/'alias.json').symlink_to(target)
            for name in ('../regular.json','alias.json','/absolute.json','a\\b'):
                with self.assertRaises(ValueError):A.checked(root,name)


class FinalMeasurementProof(unittest.TestCase):
    def fixture(self,root):
        p=metadata_plan();p['actual_project']=str(root)
        epoch=root/A.PREFIX/'epoch18';epoch.mkdir(parents=True)
        inherited=root/A.PREFIX/'controller/epoch3_loop.py';inherited.parent.mkdir(parents=True);inherited.write_text('GENERIC_INHERITED_SOURCE')
        controller=inherited.parent/'epoch18/loop.py';controller.parent.mkdir();controller.write_text('GENERIC_CONTROLLER_SOURCE')
        snapshot=epoch/'candidate-source-freeze.json';snapshot.write_text('{}')
        p['lazy_confirmation']['source_freeze_path']=snapshot.relative_to(root).as_posix()
        p['lazy_confirmation']['source_freeze_sha256']=A.sha(snapshot)
        op=epoch/'operational-plan.json';op.write_text(json.dumps(p))
        receipt={k:v for k,v in dict(checks_passed=True,status=A.STATUS,operational_prelabel_only=True,
                 native_execution_admitted=False,actual_full_require_plan_calls=1,
                 original_case_inputs_or_annotation_choices_projected=0,
                 model_native_fit_paid_GPU_calls=0).items()}
        receipt.update(plan_path=op.relative_to(root).as_posix(),plan_sha256=A.sha(op),
                       source_freeze_path=p['lazy_confirmation']['source_freeze_path'],
                       source_freeze_sha256=A.sha(snapshot),controller_source_sha256=A.sha(controller),
                       inherited_verifier_sha256=A.sha(inherited),
                       operational_contract_sha256=A.operational_contract(p))
        file=root/A.RECEIPT;file.parent.mkdir(parents=True);file.write_text(json.dumps(receipt))
        p.update(measurement_plan=True,operational_prelabel_only=False,
                 prelabel_operational_admission={'path':A.RECEIPT,'sha256':A.sha(file)})
        p['runtime_admission'].update(max_DEV_units=37,max_confirmation_units=20,
                                     capacity_pending_label_free_inputs=False)
        p['pins']=[{'path':r,'sha256':A.sha(root/r)}for r in (A.RECEIPT,receipt['plan_path'])]
        return p,controller,file

    def test_final_proof_binds_exact_prelabel_receipt_sources_and_contract(self):
        with tempfile.TemporaryDirectory()as temp:
            p,controller,_=self.fixture(Path(temp));A.verify_measurement_plan(p,Path(temp),controller)
            p['limits']['seconds_per_decision']=29
            with self.assertRaises(ValueError):A.verify_measurement_plan(p,Path(temp),controller)

    def test_research_and_acceptance_references_cannot_drift_after_admission(self):
        for field in ('research_plan_sha256','acceptance_contract'):
            with self.subTest(field=field),tempfile.TemporaryDirectory()as temp:
                root=Path(temp);p,controller,_=self.fixture(root)
                A.verify_measurement_plan(p,root,controller)
                if field=='research_plan_sha256':p[field]='0'*64
                else:p[field]=dict(p[field],sha256='0'*64)
                with self.assertRaisesRegex(ValueError,'contract drifted'):
                    A.verify_measurement_plan(p,root,controller)

    def test_missing_or_changed_receipt_and_op_plan_pins_rejected(self):
        for change in ('receipt_pin','op_pin','receipt_bytes','controller_bytes'):
            with tempfile.TemporaryDirectory()as temp:
                root=Path(temp);p,controller,receipt=self.fixture(root)
                if change=='receipt_pin':p['pins']=p['pins'][1:]
                if change=='op_pin':p['pins']=p['pins'][:1]
                if change=='receipt_bytes':receipt.write_text('{}')
                if change=='controller_bytes':controller.write_text('CHANGED')
                with self.assertRaises(ValueError):A.verify_measurement_plan(p,root,controller)

    def test_model_calls_or_non_single_unmocked_call_never_admit(self):
        for field,value in (('model_native_fit_paid_GPU_calls',1),('actual_full_require_plan_calls',2),
                            ('native_execution_admitted',True),('checks_passed',False)):
            with tempfile.TemporaryDirectory()as temp:
                root=Path(temp);p,controller,receipt=self.fixture(root)
                r=json.loads(receipt.read_text());r[field]=value;receipt.write_text(json.dumps(r))
                p['prelabel_operational_admission']['sha256']=A.sha(receipt);p['pins'][0]['sha256']=A.sha(receipt)
                with self.assertRaises(ValueError):A.verify_measurement_plan(p,root,controller)


if __name__=='__main__':unittest.main()
