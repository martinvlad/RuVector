"""All-layer static identity admission fixtures, never live dispatch or observer."""
import ast
import hashlib
import importlib.util
from pathlib import Path
import unittest

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[3]
def load(file):
    s=importlib.util.spec_from_file_location('e35_stdlib_identity',file);m=importlib.util.module_from_spec(s);s.loader.exec_module(m);return m

class RuntimeIdentityFixtures(unittest.TestCase):
    def test_all_owner_layers_bind_one_current_scope_and_no_stale_identity(self):
        c=load(HERE/'runtime/common.py');self.assertEqual((c.OWNER_PID,c.OWNER_TICKS,c.OWNER_EXPIRY,c.LOCK_FD,c.LOCK_DEVICE,c.LOCK_INODE),(104231,23176792,1792918866.0067315,3,33,13626))
        self.assertEqual(c.PHASES,('engineering',));self.assertEqual(c.TRAIN_IDS,[]);self.assertEqual(c.DEV_IDS,[])
        node=(HERE/'runtime/node_guard.cjs').read_text();observer=(ROOT/'experiments/sota-2026-10-22/audit/epoch35/observe_supervisor_closure.py').read_text()
        dispatcher=(ROOT/'experiments/sota-2026-10-22/epoch35/preparation/dispatch_once.py').read_text()
        for source in (node,observer,dispatcher):
            self.assertIn('epoch35-4d51073072c4',source)
            self.assertNotRegex(source,r'\b(?:100799|22293151|1792910029\.5943027)\b')
            self.assertNotIn('runs/dev',source)
        self.assertIn("'owner_pid': 104231, 'owner_startticks': 23176792",observer)
        self.assertIn('value.owner_pid!==104231',node);self.assertIn('owner.expires_unix!==1792918866.0067315',node)
        self.assertIn("'engineering'",dispatcher);self.assertNotIn("'dev'",dispatcher)
        self.assertIn("PRE_POPEN_LAUNCH_SHA = '"+hashlib.sha256((HERE/'runtime/launch.py').read_bytes()).hexdigest()+"'",observer)
        self.assertIn("COMMON_SHA = '"+hashlib.sha256((HERE/'runtime/common.py').read_bytes()).hexdigest()+"'",dispatcher)

    def test_BGE_and_context_constants_equal_frozen_source_dependencies(self):
        engine=load(HERE/'context_engine.py')
        self.assertEqual(engine.BGE_SHA,hashlib.sha256((ROOT/engine.BGE_SOURCE).read_bytes()).hexdigest())
        self.assertEqual(engine.CONTEXT_SHA,hashlib.sha256((ROOT/engine.CONTEXT_SOURCE).read_bytes()).hexdigest())
        self.assertEqual(engine.BGE_SHA,'c5cf3500a89837e71adc754f0dc96d090e172068031545fc55ee349e80210716')

    def test_role_boundaries_have_no_conditional_benchmark_native_branch(self):
        native=(HERE/'native_helper.cjs').read_text();node=(HERE/'runtime/node_guard.cjs').read_text()
        self.assertIn('const IDS={engineering:Array.from({length:12}',native)
        self.assertNotIn("role==='dev'",node);self.assertNotIn("dev_inputs_path",node)
        self.assertIn("phase!=='engineering'",native);self.assertIn("phase!=='engineering'",node)
        self.assertIn('plan.limits.native_corpus_batches!==1',node)
        worker=load(HERE/'worker.py');counts=worker.expected_counters()
        self.assertEqual(counts,worker.expected_counters(False))
        for k,v in {'native_queries_completed':12,'native_index_initializations_completed':12,'NLI_forward_calls_completed':48,'corpus_batches_completed':1,'native_binary_loads_completed':1,'engineering_oracle_reads':1,'engineering_oracle_expected_labels_accessed':12}.items():self.assertEqual(counts[k],v)
        self.assertTrue(all(counts[k]==0 for k in worker.C.phase_zero('engineering')))

if __name__=='__main__':unittest.main(verbosity=2)
