"""Independent all-role disabled proof boundary: every final forecast is raw T1."""
import json
from data_common import require,finite,CLASSES
POLICY='proof-disabled-all-roles-v1'
CANON={'Entailment':'entailment','Contradiction':'contradiction','NotMentioned':'not_mentioned'}
def same(a,b):return json.dumps(a,sort_keys=True,allow_nan=False,separators=(',',':'))==json.dumps(b,sort_keys=True,allow_nan=False,separators=(',',':'))
def policy_check(policy):
    require(policy['schema_version']==1 and policy['epoch']==36 and policy['policy']==POLICY,'Wrong frozen disabled-proof policy')
    require(policy['kind']=='ENGINEERING_PAIRED_READER_SOURCE_COVERAGE'
            and policy['proof_enabled_roles']==[]and policy['certificate']is None
            and policy['fallback_reason']=='proof_disabled_for_ALL_ROLES'and policy['semantic_decision_override']is False
            and policy['train']==policy['calibration']==policy['confirmation']==[]
            and policy['official_eligibility']=='HOLD'and policy['promotion_allowed']is False,
            'Proof policy must disable every role and preserve eligibility HOLD')
    return {'policy':POLICY,'scope':'DISABLED_ALL_ROLES; certificate must be null and final must equal raw T1','independent_implementation':'Exact disabled-policy/no-override/raw-distribution equality; no candidate module import'}
def decision_check(decision,reader,raw_readout,document,premise,hypothesis,spans,arm_override,role):
    require(type(decision)is dict and set(decision)=={'schema_version','epoch','raw_probabilities_E_C_N','raw_typed_argmax','final_probabilities_E_C_N','final_typed_argmax','policy','certificate','fallback_reason','semantic_decision_override'},'Exact all-role raw decision schema required')
    require(role=='engineering' and decision['schema_version']==1 and decision['epoch']==36 and decision['policy']==POLICY,'Wrong all-role decision scope')
    require(decision['certificate']is None and decision['semantic_decision_override']is False and arm_override is False
            and decision['fallback_reason']=='proof_disabled_for_ALL_ROLES','Proof, override or inconsistent disabled discriminator')
    probs=reader['probabilities_E_C_N'];label=reader['native_typed_argmax']
    require(same(decision['raw_probabilities_E_C_N'],probs)and same(decision['final_probabilities_E_C_N'],probs)
            and decision['raw_typed_argmax']==decision['final_typed_argmax']==label,
            'Every final forecast and argmax must equal original raw T1')
    require(all(finite(v)and 0<=v<=1 for v in probs),'Nonfinite raw probability')
    result={'probabilities':dict(zip(CLASSES,probs)),'prediction':CANON[label],
            'binary_yes_probability':probs[0],'binary_prediction':'Yes'if probs[0]>.5 else'No'}
    require(result==raw_readout,'Independent raw/final numerical readout changed')
    return result,{'certificate_applied':False,'rule':None,'conclusion':label,
        'raw_prediction':raw_readout['prediction'],'final_prediction':result['prediction'],'prediction_changed':False,
        'full_supplied_input_coverage':premise==document and same(spans,[[0,len(document)]]),'fallback_reason':'proof_disabled_for_ALL_ROLES'}
