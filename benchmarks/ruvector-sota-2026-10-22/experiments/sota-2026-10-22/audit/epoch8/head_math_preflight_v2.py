"""Independent finite-difference and invariance checks using only synthetic arrays/text."""
from pathlib import Path
from datetime import datetime,timezone
import hashlib,importlib.util,json,numpy as np
O=Path(__file__).resolve().parent;S=O.parents[1];P=S/'candidate/epoch8/head.py'
s=importlib.util.spec_from_file_location('epoch8_head_pure',P);H=importlib.util.module_from_spec(s);s.loader.exec_module(H)
rng=np.random.default_rng(20261022);x=rng.normal(size=(17,29));x[:,0]=1;base=rng.normal(size=(17,3));w=rng.normal(scale=.07,size=(29,3));y=rng.integers(0,3,size=17);sample=np.asarray([1/3]*17);loss,grad=H.objective(w,x,base,y,sample);errors=[];eps=1e-6
for i in range(29):
 for j in range(3):
  delta=np.zeros_like(w);delta[i,j]=eps
  finite=(H.objective(w+delta,x,base,y,sample)[0]-H.objective(w-delta,x,base,y,sample)[0])/(2*eps);errors.append(abs(finite-grad[i,j]))
assert max(errors)<1e-8
shift=np.asarray([[25.*i] for i in range(len(base))]);shiftloss,shiftgrad=H.objective(w,x,base+shift,y,sample);assert abs(loss-shiftloss)<1e-12 and np.max(abs(grad-shiftgrad))<1e-12
for p,h in [('Recipient may share records unless written consent is withheld.','Recipient may disclose some records.'),('Copying is prohibited except if required by law; retain3 copies for30days.','The recipient must retain2copies.'),('No permission exists.','No disclosure is permitted.')]:
 a=H.FEATURES.extract(p,h,[.1,-2,.3]);b=H.FEATURES.extract(p,h,[100.1,98.,100.3]);assert np.max(abs(np.asarray(a)-b))<1e-12 and len(a)==29
assert H.ALGORITHM['steps']==400 and H.ALGORITHM['learning_rate']==.03 and H.ALGORITHM['residual_l2']==.1 and H.ALGORITHM['final_gradient_norm_max']==1e-3 and H.ALGORITHM['scale_floor']==.1
assert H.FEATURES.CLASSES==('Entailment','Contradiction','NotMentioned')
result={'schema_version':1,'at':datetime.now(timezone.utc).isoformat(),'checks_passed':True,'head_sha256':hashlib.sha256(P.read_bytes()).hexdigest(),'feature_sha256':hashlib.sha256((S/'candidate/epoch8/features.py').read_bytes()).hexdigest(),'synthetic_gradient_coordinates_checked':87,'max_central_finite_difference_error':max(errors),'synthetic_objective_logitshift_invariant':True,'three_generic_legal_feature_examples_logitshift_invariant':True,'canonical_target_order':list(H.FEATURES.CLASSES),'fixed_algorithm':H.ALGORITHM,'observations':['WeightedCEgradient matchesindependentfinite differences includingfullW L2penalty; no omittedbiaspenalty.','Rawlogitfeaturescentered; residualsoftmax invariant tocommonlogitshift.','Train-onlyweightednormalization mean/variance floor.1, biasraw1leftmean0scale1; sameartifactallarms.','400fixedAdam steps pluspredeclared finalobjective<=initial+1e-8/gradientnorm<=1e-3; iffailurestop,no extraiterations/retry.','Featureextractor genericinference-text29features, no role/IDs/labels/annotations/selectoridentity orstoredanswers.'],'scope':'Pure software/mathchecks only; no actualcorpus inputs/labels fitted, no model/session/native execution or performanceclaim.','new_model_native_calls':0}
p=O/'head-math-independent-v2.json';p.write_text(json.dumps(result,indent=2)+'\n');print(json.dumps({'checks_passed':True,'sha256':hashlib.sha256(p.read_bytes()).hexdigest(),'max_gradient_error':max(errors)}))
