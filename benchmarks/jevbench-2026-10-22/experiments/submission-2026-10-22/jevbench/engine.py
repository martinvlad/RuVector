"""Actual pinned native fallback + frozen100 validators + finite exact H1 checks."""
import copy
import hashlib
import importlib.util
import math
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parents[3]
ADAPTER=ROOT/'experiments/swarm/jevbench-adapter'
sys.path.insert(0,str(ADAPTER))
import server

def apply_proof(native,question,proof):
    if proof is None:return copy.deepcopy(native)
    kind=question['type'];labels=server.question_options(question)[0]
    probabilities=proof.get('probabilities')
    if probabilities is not None:
        if set(probabilities)!=set(labels) or not all(type(p) in (int,float) and math.isfinite(p) and 0<=p<=1 for p in probabilities.values()) or abs(sum(probabilities.values())-1)>1e-12:
            raise ValueError('Malformed exact empirical distribution')
        probabilities=dict(probabilities)
    else:
        value=proof['decision']
        if kind=='noul':
            if type(value) is not bool:raise ValueError('Boolean predicate proof required')
            probabilities={'yes':float(value),'no':float(not value)}
        else:
            if str(value) not in labels:raise ValueError('Proof outside exact supplied labels')
            probabilities={label:float(label==str(value)) for label in labels}
    answer={'type':kind,'probabilities':probabilities,'confidence':max(probabilities.values()),'calibrated':False,'head':'explicit-input-proof-validator','symbolic_proof':proof}
    if kind=='noul':answer['noul']=probabilities['yes']
    elif kind=='choice':answer['choice']=min(probabilities,key=lambda label:(-probabilities[label],label))
    else:answer['score']=sum(int(label)*p for label,p in probabilities.items())/(len(labels)-1)
    return answer

class CompositeEngine:
    attribution='Actual native RuVector BGE-small fallback, immutable100 validators and source-linked exact typed joins. Whole-pipeline observed development, not index-only reasoning.'
    def __init__(self,rules_path):
        self.native=server.NativeEngine();spec=importlib.util.spec_from_file_location('frozen_submission_rules',rules_path)
        self.rules=importlib.util.module_from_spec(spec);spec.loader.exec_module(self.rules)
        self.name='ruvector-native-submission-'+Path(rules_path).parent.name
        self.receipt={**self.native.receipt,'generic_rules_sha256':hashlib.sha256(Path(rules_path).read_bytes()).hexdigest(),
            'relation_source_sha256':hashlib.sha256((Path(rules_path).parent/'typed_relations.py').read_bytes()).hexdigest(),
            'frozen100_rules_sha256':hashlib.sha256((ROOT/'experiments/compounding/jevbench/cycle3/round2/rules.py').read_bytes()).hexdigest(),
            'frozen100_probability_source_sha256':hashlib.sha256((ROOT/'experiments/compounding/jevbench/cycle3/round2/probability.py').read_bytes()).hexdigest(),
            'inference_inputs':'Only official normalized state/questions; no evaluation metadata or data files',
            'native_component':'Actual native systemOne executed every request; native original and baseline100 answers retained'}
        self.last_usage=None
    def predict(self,state,questions):
        response=self.native.predict(state,questions);response['model']=self.name;response['attribution']=self.attribution;count=0
        for key,question in questions.items():
            original=copy.deepcopy(response['answers'][key]);base=apply_proof(original,question,self.rules.baseline_proof(state,question));proof=self.rules.solve(state,question)
            answer=apply_proof(original,question,proof);answer['native_original_answer']=original;answer['baseline100_answer']=base;answer['native_fallback_used']=proof is None
            if proof is not None:count+=1
            response['answers'][key]=answer
        response['usage'].update(generic_solver_decisions=count,native_requests=1)
        self.last_usage=response['usage'];return response
    def close(self):self.native.close()
