"""Pure source/logic/receipt fixtures, never benchmark evidence or model calls."""
from pathlib import Path
import copy,json,math,sys
sys.path.insert(0,str(Path(__file__).resolve().parent))
import decision_proof_audit as D
import query_audit as Q
import nli_metrics as M
from data_common import CLASSES

HERE=Path(__file__).resolve().parent
checks=[]
def test(name,f):f();checks.append({'name':name,'passed':True})
def req(v):
    if not v:raise AssertionError('Fixture failed')
def reject(f):
    try:f()
    except(ValueError,KeyError,TypeError,AssertionError):return
    raise AssertionError('Invalid fixture accepted')
def expanded(h,family):
    value,predicate,terms,why=Q.derive(h)
    req(predicate==family and terms==Q.TERMS[family]and why is None
        and value==h+'\nRetrieval terms: '+' '.join(Q.TERMS[family]))
def original(h,reason):
    value,predicate,terms,why=Q.derive(h);req(value==h and predicate is None and terms==[]and why==reason)
for action in ['copy','duplicate','reproduce','create a copy of']:
    test('query_generic_'+action.replace(' ','_'),lambda action=action:expanded('A licensee may '+action+' material.', 'copy_permission'))
for action in ['share','disclose','communicate','provide']:
    test('query_disclosure_'+action,lambda action=action:expanded('The recipient MAY '+action+' records to an adviser.', 'disclosure_permission'))
for action in ['include','cover','encompass','contain']:
    test('query_oral_'+action,lambda action=action:expanded('The scope may '+action+' spoken records.', 'oral_information_scope'))
for term in sorted(Q.NEGATIVE):
    test('query_preserves_'+term,lambda term=term:original('A recipient may copy records '+term+' authorized.', 'negated_or_conditional_modal'))
test('query_two_modals_no_expansion',lambda:original('A may copy while B may disclose.', 'not_one_positive_may_modal'))
test('query_no_modal_no_expansion',lambda:original('A recipient must copy records.', 'not_one_positive_may_modal'))
test('query_nonASCII_no_expansion',lambda:original('A recipient may copy r\u00e9cords.', 'non_ascii_hypothesis'))
test('query_wrong_action_no_expansion',lambda:original('A recipient may destroy records.', 'unrecognized_or_ambiguous_modal_action'))
test('query_disclosure_missing_recipient_marker',lambda:original('A recipient may share records.', 'unrecognized_or_ambiguous_modal_action'))
test('query_oral_missing_scope_marker',lambda:original('A definition may include records.', 'unrecognized_or_ambiguous_modal_action'))
test('query_action_only_immediately_after_may',lambda:original('A recipient may sometimes copy records.', 'unrecognized_or_ambiguous_modal_action'))

def deduction(document,claim,conclusion=None,reason=None,premise=None,spans=None):
    cert,why=D.deduce(document,document if premise is None else premise,claim,
                      [[0,len(document)]]if spans is None else spans)
    req((cert is None and conclusion is None and why==reason)or
        (cert is not None and cert['conclusion']==conclusion and why is None))
T='The Contract expires exactly 31 days after the Execution Date.'
C='The Contract expires exactly 42 days after the Execution Date.'
R='The Disclosing Party shall return all written Confidential Information within eleven business days after a written request from the Receiving Party.'
L='Disputes under this Contract are governed by the laws of Riverstate.'
test('proof_exact_ground_fact',lambda:deduction(T,T,'Entailment'))
test('proof_generic_exact_value_exclusion',lambda:deduction(T,C,'Contradiction'))
test('proof_generic_value_renaming',lambda:deduction(T.replace('31','999999999'),C.replace('42','12345'),'Contradiction'))
test('proof_unrelated_primitive_open_world',lambda:deduction(R,L,'NotMentioned'))
test('proof_no_cross_unit_guess',lambda:deduction(T,C.replace('days','months'),reason='no_admitted_deduction'))
test('proof_removed_bare_disclosure_anchor_abstains',lambda:deduction(T.replace('the Execution Date','disclosure'),C,reason='unparsed_or_inconsistent_supplied_input'))
for subordinator in ['when','whenever','where','while','until','because','since','despite','although']:
    test('proof_subordinate_law_name_'+subordinator,lambda subordinator=subordinator:deduction(R,L.replace('Riverstate',subordinator.title()),reason='unparsed_claim'))
test('proof_no_reference_date_guess',lambda:deduction(T,C.replace('the Execution Date','the Effective Date'),reason='no_admitted_deduction'))
test('proof_no_event_alias_guess',lambda:deduction(T,C.replace('expires','terminates'),reason='no_admitted_deduction'))
test('proof_no_subject_alias_guess',lambda:deduction(T,C.replace('The Contract','This Agreement'),reason='no_admitted_deduction'))
test('proof_source_inconsistency_abstains',lambda:deduction(T+' '+C,T,reason='unparsed_or_inconsistent_supplied_input'))
test('proof_unknown_clause_abstains',lambda:deduction(T+' Additional terms apply.',C,reason='unparsed_or_inconsistent_supplied_input'))
test('proof_conditional_abstains',lambda:deduction(T[:-1]+' unless renewed.',C,reason='unparsed_or_inconsistent_supplied_input'))
test('proof_partial_retrieval_never_neutral',lambda:deduction(R,L,reason='arm_does_not_cover_exact_full_supplied_input',premise=R[:30],spans=[[0,30]]))
test('proof_whitespace_changed_coverage_abstains',lambda:deduction(' '+R,L,reason='arm_does_not_cover_exact_full_supplied_input',premise=R,spans=[[0,len(R)+1]]))
test('proof_unrelated_same_predicate_does_not_neutral',lambda:deduction(R,R.replace('eleven','twelve'),reason='no_admitted_deduction'))
test('proof_jurisdiction_difference_not_exclusive',lambda:deduction(L,L.replace('Riverstate','Lakeprovince'),reason='no_admitted_deduction'))
test('proof_jurisdiction_condition_not_absorbed',lambda:deduction(L[:-1]+' on request.',L,reason='unparsed_or_inconsistent_supplied_input'))
test('proof_multiword_jurisdiction_abstains',lambda:deduction(R,L.replace('Riverstate','New Province'),reason='unparsed_claim'))
test('proof_unicode_case_alias_abstains',lambda:deduction(T.replace('The','Th\u0130s'),C,reason='unparsed_or_inconsistent_supplied_input'))
test('proof_punctuation_never_ignored',lambda:deduction('.'+T,C,reason='unparsed_or_inconsistent_supplied_input'))
test('proof_question_punctuation_abstains',lambda:deduction(T[:-1]+'?',C,reason='unparsed_or_inconsistent_supplied_input'))
test('proof_missing_final_period_abstains',lambda:deduction(T[:-1],C,reason='unparsed_or_inconsistent_supplied_input'))
test('proof_zero_scalar_abstains',lambda:deduction(T.replace('31','0'),C,reason='unparsed_or_inconsistent_supplied_input'))
test('proof_leading_zero_abstains',lambda:deduction(T.replace('31','031'),C,reason='unparsed_or_inconsistent_supplied_input'))
test('proof_decimal_scalar_abstains',lambda:deduction(T.replace('31','31.5'),C,reason='unparsed_or_inconsistent_supplied_input'))
test('proof_huge_scalar_abstains',lambda:deduction(T.replace('31','1234567890'),C,reason='unparsed_or_inconsistent_supplied_input'))
test('proof_link_without_anchor_abstains',lambda:deduction('The confidentiality obligations also end on that date.',C,reason='unparsed_or_inconsistent_supplied_input'))
test('proof_link_with_immediate_anchor',lambda:deduction(T+'\nThe confidentiality obligations also end on that date.',C,'Contradiction'))

def raw_reader():return {'probabilities_E_C_N':[.7,.2,.1],'native_typed_argmax':'Entailment'}
def raw_readout():return {'probabilities':dict(zip(CLASSES,[.7,.2,.1])),'prediction':'entailment'}
def decision(role='engineering'):
    cert,reason=(None,'proof_disabled_for_DEV')if role=='dev'else D.deduce(T,T,C,[[0,len(T)]])
    final='Entailment'if cert is None else cert['conclusion']
    return {'schema_version':1,'epoch':33,'raw_probabilities_E_C_N':[.7,.2,.1],
            'raw_typed_argmax':'Entailment','final_probabilities_E_C_N':[.7,.2,.1]if cert is None else[float(v==final)for v in D.TYPED],
            'final_typed_argmax':final,'policy':D.POLICY,'certificate':cert,'fallback_reason':reason,
            'semantic_decision_override':cert is not None}
def verify(value,role='engineering'):
    return D.decision_check(value,raw_reader(),raw_readout(),T,T,C,[[0,len(T)]],value['semantic_decision_override'],role)
test('proof_final_forecast_exact_onehot',lambda:req(verify(decision())[0]['probabilities']=={'entailment':0.,'contradiction':1.,'not_mentioned':0.}))
test('DEV_proof_explicitly_disabled_even_when_deducible',lambda:req(verify(decision('dev'),'dev')[0]['probabilities']==raw_readout()['probabilities']))
test('DEV_certificate_rejected',lambda:reject(lambda:verify(decision(),'dev')))
def corrupt(path,value):
    d=decision();target=d
    for key in path[:-1]:target=target[key]
    target[path[-1]]=value;reject(lambda:verify(d))
test('proof_forged_witness_rejected',lambda:corrupt(['certificate','witness','claim_positive_exact_value'],7))
test('proof_forged_source_hash_rejected',lambda:corrupt(['certificate','document_sha256'],'0'*64))
test('proof_forged_coverage_rejected',lambda:corrupt(['certificate','coverage','all_supplied_clauses_parsed'],False))
test('proof_bool_integer_alias_rejected',lambda:corrupt(['certificate','source_clauses',0,'atom','value'],True))
test('proof_probability_postselection_rejected',lambda:corrupt(['final_probabilities_E_C_N'],[.1,.8,.1]))
def wrong_onehot_loss():
    rows=[{'id':'unit','document_id':0,'gold':'entailment','readers':{'native':{
        'prediction':'contradiction','probabilities':{'entailment':0.,'contradiction':1.,'not_mentioned':0.}}}}]
    m=M.metrics(rows,'native',expected_n=1)
    req(m['NLL_clip_count']==1 and m['unclipped_NLL_finite']is False and m['Brier']==2.
        and abs(m['NLL_clipped_1e-12']+math.log(1e-12))<1e-12)
test('wrong_onehot_infinite_unclipped_loss_retained',wrong_onehot_loss)

result={'schema_version':1,'epoch':33,'checks_passed':True,'checks':checks,
 'counts':{'tests':len(checks),'source_corpus_parses':0,'actual_benchmark_choice_reads':0,
           'model_native_tokenizer_imports_or_calls':0,'candidate_query_or_proof_module_imports':0},
 'scope':'Pure authored unit strings, grammar/certificate metamorphic and adversarial receipts. This is source correctness evidence only, never benchmark generalization.'}
with(HERE/'query-proof-preflight-v3.json').open('x')as f:json.dump(result,f,indent=2);f.write('\n')
print(json.dumps({'checks_passed':True,'tests':len(checks)}))
