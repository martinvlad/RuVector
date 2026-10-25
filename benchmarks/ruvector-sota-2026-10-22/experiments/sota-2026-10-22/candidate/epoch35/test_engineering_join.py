"""AST-isolated authored metadata gate fixtures;48 fake readouts are never ML evidence."""
import ast
import copy
import hashlib
import importlib.util
import json
import math
from pathlib import Path
import unittest
from types import SimpleNamespace

HERE=Path(__file__).resolve().parent

def load(name,path):
    s=importlib.util.spec_from_file_location(name,path);m=importlib.util.module_from_spec(s);s.loader.exec_module(m);return m

class EngineeringJoinFixtures(unittest.TestCase):
    def fixture(self):
        worker=load('e35_authored_gate_worker',HERE/'worker.py');proof=load('e35_authored_gate_proof',HERE/'proof.py')
        oracle=HERE/'engineering.oracle.json';labels=json.loads(oracle.read_text())['expected_labels'];reads=[]
        root=HERE.parents[3]
        fake_C=SimpleNamespace(checked=lambda rel:root/rel,sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest(),
            read=lambda p:(reads.append(p),json.loads(p.read_text()))[1])
        node=next(n for n in ast.parse((HERE/'worker.py').read_text()).body if isinstance(n,ast.FunctionDef) and n.name=='engineering_gate')
        namespace={'C':fake_C,'A':worker.A,'math':math,'file_ref':lambda p:{'path':str(p.relative_to(root)),'bytes':p.stat().st_size,'sha256':fake_C.sha(p)}}
        exec(compile(ast.Module(body=[node],type_ignores=[]),str(HERE/'worker.py'),'exec'),namespace)
        counts=worker.expected_counters();counts.update(engineering_oracle_reads=0,engineering_oracle_expected_labels_accessed=0,engineering_native_predictions_compared=0)
        cases=[]
        for case_id,label in labels.items():
            probabilities=[.05,.05,.05];probabilities[worker.A.LABELS_CANONICAL.index(label)]=.90
            reader={'actual_logits_shape':[1,3],'pair_tokens':15,'full_pair_tokens':15,'max_pair_tokens':512,
                'hidden_truncation':False,'temperature':1.,'calibrated':False,'semantic_decision_override':False,
                'probabilities_E_C_N':probabilities,'native_typed_argmax':label}
            arm={'reader':reader,'joint_pair_tokens':15,'semantic_decision_override':False,
                'context':{'source_provenance':{'selected_source_provenance':[{'AUTHORED_METADATA_ONLY':True}], 'semantic_decision_override':False}},
                'decision':proof.decide('AUTHORED_METADATA_ONLY','AUTHORED_METADATA_ONLY','claim',[[0,1]],reader)}
            cases.append({'id':case_id,'arms':{name:copy.deepcopy(arm) for name in worker.A.ARMS}})
        raw={'counters':counts,'corpora':{'engineering':{'native_child_closed':True,'cases':cases}}}
        plan={'engineering_oracle_path':str(oracle.relative_to(root)),'engineering_oracle_sha256':fake_C.sha(oracle)}
        return namespace['engineering_gate'],raw,plan,reads

    def test_one12label_join_occurs_only_after_all48_fake_readouts(self):
        gate,raw,plan,reads=self.fixture();self.assertTrue(gate(raw,plan,lambda e:None))
        self.assertEqual(len(reads),1);self.assertEqual(raw['counters']['engineering_oracle_expected_labels_accessed'],12)
        self.assertEqual(raw['engineering_gate']['n'],12);self.assertEqual(len(raw['engineering_gate']['expected_labels']),12)
        self.assertAlmostEqual(raw['engineering_gate']['proper_scores_by_arm']['actual_native']['brier'],.015)
        self.assertAlmostEqual(raw['engineering_gate']['proper_scores_by_arm']['actual_native']['nll'],-math.log(.90))
        self.assertTrue(all(v['correct']==4 for v in raw['engineering_gate']['by_class'].values()))

    def test_missing_forward_refuses_before_any_oracle_read(self):
        gate,raw,plan,reads=self.fixture();raw['counters']['NLI_readouts_completed']=47
        with self.assertRaises(ValueError):gate(raw,plan,lambda e:None)
        self.assertEqual(reads,[]);self.assertEqual(raw['counters']['engineering_oracle_expected_labels_accessed'],0)

if __name__=='__main__':unittest.main(verbosity=2)
