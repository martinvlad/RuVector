"""Independent retained decision and readout reuse replay, with no gold access."""
from data_common import require,canonical,digest,CLASSES,CANONICAL_LABELS,GOLD_NAMES,finite
from nli_metrics import REUSE,transposed,permuted_logp
from certificate_audit import audit_certificate,sha
POLICY='SOURCE_CERTIFIED_RAW_MAX_MASS_TRANSPOSITION'
def same(a,b):return canonical(a)==canonical(b)
def span_check(document,premise,spans):
 require(type(spans)is list and spans,'Nonempty original source spans required');end=0
 for r in spans:
  require(type(r)is list and len(r)==2 and all(type(x)is int for x in r)and end<=r[0]<r[1]<=len(document),'Disjoint ascending exact source span required');end=r[1]
 require(premise=='\n\n'.join(document[a:b]for a,b in spans),'Measured context is not exact quoted source')
def decision_check(arm_name,arm,physical,raw,case):
 require(arm_name in REUSE and arm['measured_context']==REUSE[arm_name],'Wrong actual neural context')
 require(physical['readout_id']==case['id']+'::NLI:'+REUSE[arm_name]and arm['neural_readout_ref']==physical['readout_id'],'Derived forecast has no matching actual readout')
 for k in ['reader','premise','context','joint_pair_tokens','context_seconds','native_query_seconds']:
  require(same(arm[k],physical[k]),'Derived arm altered immutable physical '+k)
 require(arm['extra_neural_readouts']==0 and type(arm['extra_neural_readouts'])is int and arm['model_tag']=='xxlarge','Unexpected additional model work')
 reuse=arm['readout_reuse_receipt'];require(reuse['actual_readout_id']==physical['readout_id']and reuse['raw_reader_canonical_sha256']==sha(canonical(physical['reader']))and reuse['physical_reader_unchanged']is True and reuse['derived_forecast_did_not_call_model']is True,'Readout reuse receipt differs')
 require(finite(arm['decision_seconds'])and arm['decision_seconds']>=0,'Invalid measured decision time')
 decision=arm['decision'];reader=physical['reader'];spans=physical['context']['selected_source_spans'];span_check(case['document'],physical['premise'],spans)
 require(decision['schema_version']==1 and decision['epoch']==38,'Wrong decision epoch')
 require(same(decision['raw_probabilities_E_C_N'],raw['canonical'])and decision['raw_typed_argmax']==raw['native_label'],'Raw forecast or provided winner changed')
 require(decision['extra_NLI_calls']==0 and type(decision['extra_NLI_calls'])is int and decision['fitting']is False and decision['calibrated_posterior_claim']is False,'Extra neural call or fitted confidence')
 cert=decision['certificate'];info=None;target=None
 if arm_name.endswith('_verified'):
  require(decision['policy']==POLICY,'Wrong verified probability policy')
  if cert is not None:
   info=audit_certificate(cert,case['document'],physical['premise'],case['hypothesis'],spans);target=info['conclusion'];require(decision['fallback_reason']is None,'Applied certificate has fallback reason')
   require(decision['source_analysis']=={'status':'CERTIFICATE_CANDIDATE','sha256':cert['full_source_analysis']['analysis_sha256']},'Certificate/source analysis reference differs')
  else:
   require(type(decision['fallback_reason'])is str and decision['fallback_reason'],'Silent source-certificate abstention')
   analysis=case['source_analysis'];require(decision['source_analysis']=={'status':analysis['status'],'sha256':analysis['analysis_sha256']},'Abstaining source recomputation differs')
   require(analysis['status']=='ABSTAIN'and decision['fallback_reason']==analysis['reason'],'Covered certificate was silently suppressed or inconsistent fallback')
  require(decision['argmax_policy']=='Valid certificate class first among equal final maxima; otherwise original provided C,N,E raw-logit first maximum','Certificate tie policy changed')
 else:
  require(decision['policy']=='RAW_T1_CONTROL_NO_CERTIFICATE'and cert is None and decision['fallback_reason']=='raw_control_certificate_not_applied','Raw control applied a source proof')
  require(decision['argmax_policy']=='Original provided C,N,E raw-logit first maximum','Raw tie policy changed')
 p,label=transposed(raw['canonical'],raw['native_label'],target);lp=permuted_logp(raw['canonical_log_probabilities'],raw['native_label'],target);permutation=[0,1,2]
 if target is not None:
  i=CANONICAL_LABELS.index(raw['native_label']);j=CANONICAL_LABELS.index(target);permutation[i],permutation[j]=permutation[j],permutation[i]
 require(type(decision['permutation'])is list and all(type(i)is int for i in decision['permutation'])and decision['permutation']==permutation,'Final permutation differs')
 require(same(decision['raw_log_probabilities_E_C_N'],raw['canonical_log_probabilities'])and same(decision['final_log_probabilities_E_C_N'],lp),'Unclipped shifted log probability replay differs')
 require(decision['NLL_policy']=='STABLE_SHIFTED_SOURCE_LOGSOFTMAX_THEN_EXACT_FINAL_PERMUTATION','Gate NLL binding changed')
 require(same(decision['final_probabilities_E_C_N'],p)and decision['final_typed_argmax']==label,'Independent certified final forecast replay differs')
 applied=cert is not None;overridden=label!=raw['native_label'];changed=p!=raw['canonical']
 require(decision['certificate_applied']is applied and decision['semantic_decision_override']is overridden and arm['semantic_decision_override']is overridden and decision['probabilities_changed']is changed,'Decision discriminators changed')
 result={'probabilities':dict(zip(CLASSES,p)),'log_probabilities':dict(zip(CLASSES,lp)),'prediction':GOLD_NAMES[label]}
 return result,{'certificate_applied':applied,'conclusion':label,'raw_prediction':raw['prediction'],'final_prediction':result['prediction'],'prediction_changed':overridden,'probabilities_changed':changed,'neural_readout_ref':physical['readout_id'],'extra_neural_calls':0,'independently_validated_source_certificate':info,'fallback_reason':decision['fallback_reason']}
