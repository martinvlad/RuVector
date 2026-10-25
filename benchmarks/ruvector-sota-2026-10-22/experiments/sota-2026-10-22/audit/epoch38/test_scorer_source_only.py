"""Unrelated manually specified fixtures; never reads the twelve epoch inputs."""
import copy,hashlib,json,math,unittest
from fractions import Fraction as F
from certificate_audit import source_rows,parse_claim,IndependentCatalog,all_or_none,pair,freeze,sha,audit_analysis,audit_certificate,GRAMMAR
from source_coverage_audit import source_groups,selected_spans
from nli_metrics import log_softmax_source,transposed,permuted_logp

class PureScorer(unittest.TestCase):
 def rejected(self,call):
  with self.assertRaises((ValueError,KeyError,TypeError)):call()
 def test_manual_signed_decimal_unit_period_scope(self):
  source='For "Test Alder" in "P1", "open" is exactly -1.25 million USD.\nFor "Test Alder" in "P1", "credit" is exactly 750 thousand USD.\nFor "Test Alder" in "P1", "closing" equals "open" plus "credit".\nFor "Test Alder" in "P0", "open" is exactly 8 USD.'
  cat=IndependentCatalog(source_rows(source));claim=parse_claim('For "Test Alder" in "P1", "closing" is exactly -500000 USD.')
  lo,hi,deps,d=cat.claim_info(claim);self.assertEqual((lo,hi,deps),(F(-500000),F(-500000),{0,1,2}));self.assertEqual(all_or_none(lo,hi,claim['comparison'],claim['value']),'Entailment')
  bad=parse_claim('For "Test Alder" in "P1", "closing" is exactly -500000 items.');self.rejected(lambda:cat.claim_info(bad))
  bad=parse_claim('For "Test Alder" in "P2", "closing" is exactly -500000 USD.');self.rejected(lambda:cat.claim_info(bad))
 def test_shared_variable_cancels(self):
  s='For "Pure Birch" in "Y", "x" is between 2 and 8 USD inclusive.\nFor "Pure Birch" in "Y", "zero" equals "x" minus "x".'
  c=IndependentCatalog(source_rows(s));lo,hi,_,_=c.claim_info(parse_claim('For "Pure Birch" in "Y", "zero" is exactly 0 USD.'));self.assertEqual((lo,hi),(F(0),F(0)))
 def test_exact_two_set_manual_boundaries(self):
  s='For "Pure Cedar" in "Z", the universe has exactly 17 items.\nFor "Pure Cedar" in "Z", "A" contains exactly 11 items.\nFor "Pure Cedar" in "Z", "B" contains exactly 9 items.'
  cat=IndependentCatalog(source_rows(s));a=parse_claim('For "Pure Cedar" in "Z", the overlap of "B" and "A" contains at least 3 items.');lo,hi,_,_=cat.claim_info(a);self.assertEqual((lo,hi),(F(3),F(9)));self.assertEqual(all_or_none(lo,hi,a['comparison'],a['value']),'Entailment')
  a=parse_claim('For "Pure Cedar" in "Z", the union of "A" and "B" contains less than 11 items.');lo,hi,_,_=cat.claim_info(a);self.assertEqual((lo,hi),(F(11),F(17)));self.assertEqual(all_or_none(lo,hi,a['comparison'],a['value']),'Contradiction')
 def test_unsupported_noisy_and_unbound_sources(self):
  for s in ['For "Noisy" in "T", "a" is exactly 2 USD.\nThe figure may be adjusted.', 'For "Noisy" in "T", "a" is exactly 2 USD. garbage', 'For "Noisy" in "T", "a" is exactly 2 EUR.']:
   self.rejected(lambda:source_rows(s))
  for s in ['For "Cycle" in "T", "a" equals "b" divided by 2.\nFor "Cycle" in "T", "b" equals "a" divided by 2.', 'For "Conflict" in "T", "a" is exactly 2 USD.\nFor "Conflict" in "T", "a" is exactly 3 USD.', 'For "Missing" in "T", "a" equals "b" divided by 2.', 'For "Wrong Unit" in "T", "a" is exactly 2 USD.\nFor "Wrong Unit" in "T", "b" is exactly 2 items.\nFor "Wrong Unit" in "T", "c" equals "a" plus "b".']:
   self.rejected(lambda:IndependentCatalog(source_rows(s)))
 def simple_analysis(self):
  # Manual interval source and independent feasible witnesses: no candidate import.
  doc='For "Pure Fir" in "A", "cash" is between 4 and 8 USD inclusive.';hyp='For "Pure Fir" in "A", "cash" is more than 6 USD.'
  atom={'kind':'interval','entity':'Pure Fir','period':'A','metric':'cash','lower':[4,1],'upper':[8,1],'unit':'USD','dimension':'USD'}
  claim={'kind':'amount','entity':'Pure Fir','period':'A','metric':'cash','comparison':'more than','value':[6,1],'unit':'USD','dimension':'USD'}
  def world(value,yes):return {'claim_truth':yes,'claim_value':[value,1],'amount_variables':[{'binding':['Pure Fir','A','cash'],'value':[value,1],'dimension':'USD','integer_domain':False}],'derived_values':[],'set_tables':[],'all_source_constraints_satisfied':True}
  analysis={'schema_version':1,'epoch':38,'policy':GRAMMAR,'document_sha256':sha(doc),'hypothesis_sha256':sha(hyp),'status':'CERTIFICATE_CANDIDATE','all_supplied_clauses_parsed':True,'source_model_consistent':True,'source_clauses':[{'clause_id':0,'span':[0,len(doc)],'text':doc,'text_sha256':sha(doc),'atom':atom}],'proof':{'conclusion':'NotMentioned','rule':'AFFINE_EXTREMA_OR_EXPLICIT_COMPATIBLE_WORLDS','claim':claim,'lower':[4,1],'upper':[8,1],'derivation':{'kind':'AFFINE_QUANTITY','binding':['Pure Fir','A','cash'],'dimension':'USD','constant':[0,1],'coefficients':[{'binding':['Pure Fir','A','cash'],'coefficient':[1,1]}],'independent_root_domains':[{'binding':['Pure Fir','A','cash'],'lower':[4,1],'upper':[8,1],'integer_domain':False}]},'required_clause_ids':[0],'compatible_worlds':[world(8,True),world(4,False)],'neutral_requires_entire_source_catalog':True},'required_source_spans':[[0,len(doc)]]}
  self.rehash(analysis);return doc,hyp,analysis
 def rehash(self,a):a['analysis_sha256']=sha(json.dumps({k:v for k,v in a.items()if k!='analysis_sha256'},sort_keys=True,separators=(',',':'),ensure_ascii=True))
 def test_manual_neutral_certificate_and_quote(self):
  d,h,a=self.simple_analysis();info=audit_analysis(a,d,h);self.assertEqual(info['conclusion'],'NotMentioned');self.assertEqual(info['worlds_independently_validated'],2)
  cert={'schema_version':1,'epoch':38,'grammar':GRAMMAR,'document_sha256':sha(d),'hypothesis_sha256':sha(h),'premise_sha256':sha(d),'selected_source_spans':[[0,len(d)]],'all_required_source_quotes_covered':True,'full_source_analysis':a,'conclusion':'NotMentioned'}
  self.assertEqual(audit_certificate(cert,d,d,h,[[0,len(d)]])['conclusion'],'NotMentioned');self.rejected(lambda:audit_certificate(cert,d,d,h,[[0,len(d)-1]]))
 def test_invalid_neutral_world_cannot_pass(self):
  d,h,a=self.simple_analysis()
  for key,value in [('claim_truth',False),('claim_value',[9,1])]:
   b=copy.deepcopy(a);b['proof']['compatible_worlds'][0][key]=value;self.rehash(b);self.rejected(lambda:audit_analysis(b,d,h))
  b=copy.deepcopy(a);b['proof']['compatible_worlds'][0]['amount_variables']=[];self.rehash(b);self.rejected(lambda:audit_analysis(b,d,h))
  b=copy.deepcopy(a);b['proof']['required_clause_ids']=[];self.rehash(b);self.rejected(lambda:audit_analysis(b,d,h))
 def test_fractional_derived_items_rejected_by_world(self):
  s='For "Pure Elm" in "A", "items" is exactly 1 items.\nFor "Pure Elm" in "A", "half" equals "items" divided by 2.';cat=IndependentCatalog(source_rows(s));claim=parse_claim('For "Pure Elm" in "A", "half" is exactly 0.5 items.')
  world={'claim_truth':True,'claim_value':[1,2],'amount_variables':[{'binding':['Pure Elm','A','items'],'value':[1,1],'dimension':'items','integer_domain':True}],'derived_values':[{'binding':['Pure Elm','A','half'],'value':[1,2],'dimension':'items'}],'set_tables':[],'all_source_constraints_satisfied':True}
  self.rejected(lambda:cat.witness(world,claim))
 def test_stable_logprob_large_offset_and_underflow(self):
  self.assertEqual(log_softmax_source([1e20,1e20,1e20]),[-math.log(3)]*3)
  lp=log_softmax_source([0,-1000,0]);self.assertTrue(all(math.isfinite(x)for x in lp));self.assertGreater(-lp[2],999);self.assertEqual(math.exp(lp[2]),0)
  for vec in [[1e38,-1e38,0],[-1e38,1e38,0],[0,0,0],[4,1,-2]]:
   lp=log_softmax_source(vec);p=[math.exp(x)for x in lp];native=['Contradiction','NotMentioned','Entailment'][max(range(3),key=lambda i:vec[i])]
   for target in ['Entailment','Contradiction','NotMentioned']:
    pp,label=transposed(p,native,target);ll=permuted_logp(lp,native,target);self.assertEqual(label,target);self.assertEqual(sorted(pp),sorted(p));self.assertEqual(sorted(ll),sorted(lp));self.assertTrue(all(abs(math.exp(x)-y)<1e-12 for x,y in zip(ll,pp)));i=['Entailment','Contradiction','NotMentioned'].index(target);self.assertLessEqual(-ll[i],-lp[i]+1e-12)
 def test_blankline_decimal_source_groups(self):
  s='First 3.25.\n\nSecond 2.5.\n';units=[{'id':0,'start':0,'end':12,'group_id':0,'line_number':0,'source_line_span':[0,12],'nli_tokens':4,'bge_tokens':4,'token_fallback':False},{'id':1,'start':12,'end':len(s),'group_id':1,'line_number':2,'source_line_span':[12,len(s)],'nli_tokens':4,'bge_tokens':4,'token_fallback':False}]
  # Character positions are independently given above rather than parser-generated.
  self.assertEqual(len(s[:12]),12);cat=source_groups(s,units);self.assertEqual(len(cat),2);self.assertEqual(selected_spans(cat,[1,0]),[[0,len(s)]])


class ReplayBoundaries(unittest.TestCase):
 rejected=PureScorer.rejected
 simple_analysis=PureScorer.simple_analysis
 rehash=PureScorer.rehash
 def fixture(self,verified=True):
  from data_common import canonical
  doc,hyp,a=self.simple_analysis();p=[.1,.8,.1];rawlp=[math.log(x)for x in p];reader={'immutable':'toy physical raw readout'};context={'selected_source_spans':[[0,len(doc)]]};physical={'readout_id':'toy-only::NLI:native_coverage','reader':reader,'premise':doc,'context':context,'joint_pair_tokens':20,'context_seconds':.01,'native_query_seconds':.002};cert={'schema_version':1,'epoch':38,'grammar':GRAMMAR,'document_sha256':sha(doc),'hypothesis_sha256':sha(hyp),'premise_sha256':sha(doc),'selected_source_spans':context['selected_source_spans'],'all_required_source_quotes_covered':True,'full_source_analysis':a,'conclusion':'NotMentioned'}
  decision={'schema_version':1,'epoch':38,'policy':'SOURCE_CERTIFIED_RAW_MAX_MASS_TRANSPOSITION'if verified else'RAW_T1_CONTROL_NO_CERTIFICATE','raw_probabilities_E_C_N':p,'raw_typed_argmax':'Contradiction','final_probabilities_E_C_N':[.1,.1,.8]if verified else p,'final_typed_argmax':'NotMentioned'if verified else'Contradiction','permutation':[0,2,1]if verified else[0,1,2],'certificate':cert if verified else None,'certificate_applied':verified,'fallback_reason':None if verified else'raw_control_certificate_not_applied','semantic_decision_override':verified,'probabilities_changed':verified,'extra_NLI_calls':0,'fitting':False,'calibrated_posterior_claim':False,'argmax_policy':'Valid certificate class first among equal final maxima; otherwise original provided C,N,E raw-logit first maximum'if verified else'Original provided C,N,E raw-logit first maximum','source_analysis':{'status':'CERTIFICATE_CANDIDATE','sha256':a['analysis_sha256']},'raw_log_probabilities_E_C_N':rawlp,'final_log_probabilities_E_C_N':[rawlp[i]for i in([0,2,1]if verified else[0,1,2])],'NLL_policy':'STABLE_SHIFTED_SOURCE_LOGSOFTMAX_THEN_EXACT_FINAL_PERMUTATION'}
  arm={**physical,'model_tag':'xxlarge','measured_context':'native_coverage','neural_readout_ref':physical['readout_id'],'decision':decision,'decision_seconds':.0001,'extra_neural_readouts':0,'semantic_decision_override':verified,'readout_reuse_receipt':{'actual_readout_id':physical['readout_id'],'raw_reader_canonical_sha256':sha(canonical(reader)),'physical_reader_unchanged':True,'derived_forecast_did_not_call_model':True}}
  raw={'canonical':p,'canonical_log_probabilities':rawlp,'native_label':'Contradiction','prediction':'contradiction'};case={'id':'toy-only','document':doc,'hypothesis':hyp,'source_analysis':a};return arm,physical,raw,case
 def test_retained_readout_certificate_replay(self):
  from decision_proof_audit import decision_check
  arm,physical,raw,case=self.fixture();out,info=decision_check('native_verified',arm,physical,raw,case);self.assertEqual(out['probabilities'],{'entailment':.1,'contradiction':.1,'not_mentioned':.8});self.assertEqual(out['prediction'],'not_mentioned');self.assertEqual(info['extra_neural_calls'],0)
  arm,physical,raw,case=self.fixture(False);out,info=decision_check('native_raw',arm,physical,raw,case);self.assertEqual(out['prediction'],'contradiction');self.assertFalse(info['certificate_applied'])
 def test_fake_readout_or_extra_forward_rejected(self):
  from decision_proof_audit import decision_check
  for mutation in ['extra','ref','reader','logp','permutation']:
   arm,physical,raw,case=self.fixture();arm=copy.deepcopy(arm)
   if mutation=='extra':arm['extra_neural_readouts']=1
   if mutation=='ref':arm['neural_readout_ref']='new fake readout'
   if mutation=='reader':arm['reader']['immutable']='changed'
   if mutation=='logp':arm['decision']['final_log_probabilities_E_C_N'][2]=0
   if mutation=='permutation':arm['decision']['permutation']=[0,1,2]
   self.rejected(lambda:decision_check('native_verified',arm,physical,raw,case))
 def test_wrong_certificate_cannot_be_hidden_by_gold(self):
  from decision_proof_audit import decision_check
  arm,physical,raw,case=self.fixture();arm=copy.deepcopy(arm);arm['decision']['certificate']['conclusion']='Entailment';self.rejected(lambda:decision_check('native_verified',arm,physical,raw,case))
 def test_uniform_metrics_and_actual_underflow(self):
  from nli_metrics import metrics,CLASSES
  rows=[{'id':'unrelated-pure-'+str(i),'document_id':i,'gold':CLASSES[i//4],'readers':{'test':{'probabilities':dict.fromkeys(CLASSES,1/3),'log_probabilities':dict.fromkeys(CLASSES,-math.log(3)),'prediction':'entailment'}}}for i in range(12)]
  m=metrics(rows,'test');self.assertEqual(m['correct'],4);self.assertAlmostEqual(m['Brier'],2/3);self.assertAlmostEqual(m['NLL'],math.log(3));self.assertEqual(m['NLL_clip_count'],0)
  rows[0]['readers']['test']['probabilities']={'entailment':0.,'contradiction':.5,'not_mentioned':.5};rows[0]['readers']['test']['log_probabilities']={'entailment':-1000.,'contradiction':-math.log(2),'not_mentioned':-math.log(2)}
  m=metrics(rows,'test');self.assertEqual(m['scores'][0]['NLL'],1000.);self.assertLess(m['scores'][0]['NLL_clipped_1e-12'],28.);self.assertEqual(m['display_probability_underflow_count'],1)
 def test_stable_gate_not_clipped_loss(self):
  from nli_metrics import engineering_gates,ARMS,CLASSES
  def outcome(correct,nll):return {'correct':correct,'Brier':.2,'NLL':nll,'NLL_clipped_1e-12':.01,'by_class':{c:{'n':4,'correct':4}for c in CLASSES}}
  results={a:outcome(9,2.)for a in ARMS};results['native_verified']=outcome(12,1.);self.assertTrue(all(engineering_gates(results).values()))
  results['native_verified']['NLL']=3.;self.assertFalse(engineering_gates(results)['full_raw:NLL_nonincrease'])
  results['native_verified']['NLL']=1.;results['full_raw']['correct']=11;g=engineering_gates(results);self.assertFalse(g['prospective_full_raw_ceiling']);self.assertFalse(g['accuracy_gain_at_least2_vs_full_raw'])


class TypedAssetMetadataBoundaries(unittest.TestCase):
 def fixture(self):
  import hashlib
  from model_audit import independent_asset_identity,ASSET_FILENAMES
  ordinary={'config.json':b'{"toy":1}','tokenizer_config.json':b'{}','LICENSE':b'CC0 toy'};payloads={'spm.model':b'toy tokenizer payload','pytorch_model.bin':b'toy weight payload'};declarations=[];observed=[];results=[]
  for name in sorted(ASSET_FILENAMES):
   body=ordinary.get(name,payloads.get(name));digest=hashlib.sha256(body).hexdigest();isordinary=name in ordinary
   pointer=f'version https://git-lfs.github.com/spec/v1\noid sha256:{digest}\nsize {len(body)}\n'.encode();objectbody=body if isordinary else pointer;git=hashlib.sha1(b'blob '+str(len(objectbody)).encode()+b'\0'+objectbody).hexdigest()
   d={'path':name,'bytes':len(body),'source_url':'https://example.invalid/disjoint-pure/'+name,'upstream_git_blob_sha1':git,'metadata_body_sha256'if isordinary else'upstream_sha256':digest};declarations.append(d);observed.append({'path':name,'bytes':len(body),'source_url':d['source_url'],'upstream_git_blob_sha1':git,'sha256':digest});identity=independent_asset_identity(d)
   results.append({**identity,'payload_size_and_SHA256_verified':True,'raw_payload_git_sha1_verified':isordinary,'LFS_pointer_SHA1_compared_to_payload_SHA1':False,'actual_payload_bytes_hashed':len(body),'actual_payload_sha256':digest,'actual_ordinary_payload_git_blob_sha1':git if isordinary else None,'actual_full_payload_scan':True,'payload_git_SHA1_computed':isordinary,'LFS_payload_git_SHA1_not_required':not isordinary})
  reference=lambda name:{'path':'disjoint-pure/'+name,'bytes':1,'sha256':'a'*64};refs={n:reference(n)for n in ['common_source','validator_source','identity_helper_source','expected_catalog','public_model_assets_lock']};lock=refs['public_model_assets_lock'];directory='/disjoint-pure/reader'
  leaf={'schema_version':1,'epoch':38,'kind':'ENGINEERING_SOURCE_BOUND_NUMERIC_CERTIFICATES','source_checkpoint':'7c50ba99848f6a13707eeec6c4947291a8478e5c','status':'ALL_FIVE_REAL_MODEL_ASSETS_VERIFIED_WITH_TYPED_SOURCE_IDENTITIES','validator_function':'model_assets_guard.validate_model_assets',**refs,'repository':'microsoft/deberta-v2-xxlarge-mnli','revision':'8f8b43ddfc6f5e93a7abd1d1506d606b080a4c06','model_directory':directory,'directory_inventory':sorted(ASSET_FILENAMES|{'asset-lock.json'}),'external_direct_lock':{'path':directory+'/asset-lock.json','bytes':lock['bytes'],'sha256':lock['sha256'],'byte_identical_to_public':True},'actual_payload_files_verified':5,'actual_payload_bytes_hashed':sum(r['bytes']for r in declarations),'ordinary_Git_payloads_verified':3,'canonical_LFS_pointers_verified':2,'files':results,'stubs_used':False,'monkeypatches':[],'model_native_tokenizer_initializations_or_calls':0,'case_oracle_reads':0,'network_calls':0,'wall_seconds_hash_validation_only':.001}
  return leaf,declarations,observed,refs,directory
 def test_disjoint_typed_metadata_replay(self):
  from model_audit import asset_guard_leaf_check
  args=self.fixture();result=asset_guard_leaf_check(*args);self.assertEqual(result['ordinary_Git_payloads_verified'],3);self.assertEqual(result['canonical_LFS_pointers_verified'],2)
 def test_pointer_payload_confusion_and_observed_authority_rejected(self):
  from model_audit import independent_asset_identity,asset_guard_leaf_check
  leaf,decl,observed,refs,directory=self.fixture();lfs=next(r for r in decl if 'upstream_sha256'in r);bad=copy.deepcopy(lfs);bad['upstream_git_blob_sha1']='f'*40
  with self.assertRaises(ValueError):independent_asset_identity(bad)
  bad=copy.deepcopy(lfs);bad['sha256']=bad.pop('upstream_sha256')
  with self.assertRaises(ValueError):independent_asset_identity(bad)
  leaf['files'][-1]['LFS_pointer_SHA1_compared_to_payload_SHA1']=True
  with self.assertRaises(ValueError):asset_guard_leaf_check(leaf,decl,observed,refs,directory)
 def test_envelope_uses_exact_real_function_calls_field(self):
  from model_audit import asset_guard_envelope_check
  leaf,_,_,refs,_=self.fixture();envelope={'schema_version':1,'epoch':38,'source_checkpoint':'7c50ba99848f6a13707eeec6c4947291a8478e5c','status':'PASS_UNSTUBBED_FULL_REAL_ASSET_GUARD_BEFORE_SOURCE_FREEZE','function':'C.verify_model_assets','function_calls':1,**refs,'stubs_used':False,'monkeypatches':[],'model_native_tokenizer_initializations_or_calls':0,'case_oracle_reads':0,'result':{'xxlarge':leaf}}
  self.assertTrue(asset_guard_envelope_check(envelope));bad=copy.deepcopy(envelope);bad['calls']=bad.pop('function_calls')
  with self.assertRaises(ValueError):asset_guard_envelope_check(bad)
  bad=copy.deepcopy(envelope);bad['function_calls']=True
  with self.assertRaises(ValueError):asset_guard_envelope_check(bad)
 def test_mock_partial_or_changed_source_not_real_admission(self):
  from model_audit import asset_guard_leaf_check
  for kind in ['mock','partial','source','ordinary_git']:
   leaf,decl,observed,refs,directory=self.fixture()
   if kind=='mock':leaf['stubs_used']=True
   if kind=='partial':leaf['files'][0]['actual_payload_bytes_hashed']=0
   if kind=='source':leaf['validator_source']={'path':'changed','bytes':1,'sha256':'a'*64}
   if kind=='ordinary_git':next(r for r in leaf['files']if r['raw_payload_git_sha1_verified'])['actual_ordinary_payload_git_blob_sha1']='0'*40
   with self.assertRaises(ValueError):asset_guard_leaf_check(leaf,decl,observed,refs,directory)


if __name__=='__main__':unittest.main()
