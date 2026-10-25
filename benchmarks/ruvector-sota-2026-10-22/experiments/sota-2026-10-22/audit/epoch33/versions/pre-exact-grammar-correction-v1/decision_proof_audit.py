"""Independent finite-state replay of the declared controlled legal-atom proof.

No candidate implementation is imported. This verifier scans sentence boundaries
and literal word positions separately from the candidate's regular expressions,
then checks the complete source theory, deduction and full certificate bytes.
It reads no gold label and executes no model/tokenizer/native code.
"""
import hashlib,json,re
from data_common import require,finite,CLASSES

POLICY='proof-carrying-closed-legal-atoms-v1'
TYPED=('Entailment','Contradiction','NotMentioned')
CANON={'Entailment':'entailment','Contradiction':'contradiction','NotMentioned':'not_mentioned'}
FORBIDDEN={'if','unless','except','provided','however','subject','notwithstanding','may','might',
           'either','neither','not','no','or','and','but','whether','approximately'}
WORD_NUMBERS={name:i for i,name in enumerate(
    ['one','two','three','four','five','six','seven','eight','nine','ten','eleven','twelve'],1)}
NUMERIC_ID=('predicate','subject','event','reference','qualifier','unit')

def same(a,b):
    return json.dumps(a,sort_keys=True,ensure_ascii=False,allow_nan=False,separators=(',',':'))==json.dumps(b,sort_keys=True,ensure_ascii=False,allow_nan=False,separators=(',',':'))

def digest(text):return hashlib.sha256(text.encode()).hexdigest()

def positive(value):
    if not isinstance(value,str)or not value.isascii()or not value.isdigit()or not 1<=len(value)<=9 or value[0]=='0':return None
    return int(value)

def primitive(sentence,previous=None,source=False):
    if not isinstance(sentence,str)or not sentence.isascii()or not sentence.endswith('.'):
        return None
    if set(re.findall(r'[A-Za-z0-9_]+',sentence.lower()))&FORBIDDEN:return None
    body=sentence[:-1];words=body.lower().split(' ')
    if (len(words)in(8,10)and words[0]in('this','the')and words[1]in('agreement','contract')
            and words[2]in('terminates','expires')and words[3]=='exactly'
            and positive(words[4])is not None and words[5]in('day','days','month','months','year','years')
            and words[6]=='after'and(words[7:]==['disclosure']or
                (len(words)==10 and words[7]=='the'and words[8]in('effective','execution','start')and words[9]=='date'))):
        return {'predicate':'agreement_termination','subject':' '.join(words[:2]),'event':words[2],
                'reference':' '.join(words[7:]),'qualifier':'exactly','unit':words[5].rstrip('s'),'value':positive(words[4])}
    if (len(words)==21 and words[0]=='the'and words[1]in('receiving','disclosing')
            and words[2:10]==['party','shall','return','all','written','confidential','information','within']
            and words[11:19]==['business','days','after','a','written','request','from','the']
            and words[19]in('receiving','disclosing')and words[20]=='party'):
        delay=WORD_NUMBERS.get(words[10],positive(words[10]))
        if delay is not None:
            return {'predicate':'return_obligation','party':words[1],'modality':'shall',
                    'object':'all written confidential information','delay_business_days':delay,
                    'trigger':'written request','requester':words[19]}
    for subject in('agreement','contract'):
        prefix='disputes under this '+subject+' are governed by the laws of '
        if body.lower().startswith(prefix):
            place=body[len(prefix):]
            if (1<=len(place)<=64 and all(c.isascii()and c.isalpha()for c in place)):
                return {'predicate':'governing_law','subject':'this '+subject,'event':'disputes',
                        'jurisdiction':' '.join(place.lower().split())}
    if (source and sentence.lower()=='the confidentiality obligations also end on that date.'
            and isinstance(previous,dict)and previous.get('predicate')=='agreement_termination'):
        return {'predicate':'confidentiality_end_same_date','subject':previous['subject'],
                'parent_event':previous['event'],'reference':previous['reference'],
                'unit':previous['unit'],'value':previous['value']}
    return None

def complete_theory(document):
    if not isinstance(document,str)or not document.isascii()or not 0<len(document)<=8192 or '\0'in document:return None
    # All grammar sentences end in a period. A question/exclamation or an
    # internal/leading period cannot be ignored by this separate scanner.
    rows=[];cursor=0;prior=None
    for end,c in enumerate(document):
        if c not in'.!?':continue
        if c!='.':return None
        raw=document[cursor:end+1];left=len(raw)-len(raw.lstrip());right=len(raw.rstrip())
        text=raw[left:right];atom=primitive(text,prior,True)
        if atom is None:return None
        rows.append({'source_char_start':cursor+left,'source_char_end':cursor+right,
                     'text':text,'text_sha256':digest(text),'atom':atom})
        if len(rows)>16:return None
        prior=atom;cursor=end+1
    if not rows or document[cursor:].strip():return None
    signatures={}
    for row in rows:
        fact=row['atom']
        if fact['predicate']!='agreement_termination':continue
        key=tuple(fact[k]for k in('subject','event','reference','qualifier'));value=(fact['unit'],fact['value'])
        if key in signatures and signatures[key]!=value:return None
        signatures[key]=value
    return rows

def deduce(document,premise,hypothesis,spans):
    if not all(isinstance(v,str)for v in(document,premise,hypothesis)):return None,'invalid_input_type'
    if premise!=document or not same(spans,[[0,len(document)]]):return None,'arm_does_not_cover_exact_full_supplied_input'
    theory=complete_theory(document)
    if theory is None:return None,'unparsed_or_inconsistent_supplied_input'
    claim=primitive(hypothesis)
    if claim is None:return None,'unparsed_claim'
    facts=[row['atom']for row in theory]
    base={'schema_version':1,'grammar':POLICY,'document_sha256':digest(document),
          'premise_sha256':digest(premise),'hypothesis_sha256':digest(hypothesis),
          'coverage':{'premise_equals_full_document':True,'selected_source_spans':[[0,len(document)]],
                      'all_supplied_clauses_parsed':True},'source_clauses':theory,'claim':claim}
    fact_matches=[i for i,fact in enumerate(facts)if same(fact,claim)]
    if fact_matches:
        return {**base,'rule':'EXACT_GROUND_FACT','conclusion':'Entailment',
                'witness':{'source_atom_index':fact_matches[0]}},None
    if claim['predicate']=='agreement_termination':
        exclusive=[i for i,fact in enumerate(facts)if all(same(fact.get(k),claim[k])for k in NUMERIC_ID)]
        if exclusive and all(facts[i]['value']!=claim['value']for i in exclusive):
            i=exclusive[0]
            return {**base,'rule':'DISTINCT_EXACT_SAME_EVENT_VALUE','conclusion':'Contradiction',
                    'witness':{'source_atom_index':i,'identity_fields':list(NUMERIC_ID),
                               'source_positive_exact_value':facts[i]['value'],
                               'claim_positive_exact_value':claim['value']}},None
    predicates={fact['predicate']for fact in facts}
    if claim['predicate']not in predicates:
        # With no cross-predicate axioms and a consistent positive-ground
        # source, explicitly adding either truth value for this new primitive
        # predicate yields a model of every source atom.
        return {**base,'rule':'OPEN_WORLD_UNRELATED_PREDICATE','conclusion':'NotMentioned',
                'witness':{'source_predicates':sorted(predicates),
                           'extensions':[{'all_source_facts':True,'claim_atom':True},
                                         {'all_source_facts':True,'claim_atom':False}],
                           'predicate_relation':'independent_primitive_predicates'}},None
    return None,'no_admitted_deduction'

def policy_check(policy):
    require(policy['schema_version']==1 and policy['epoch']==33 and policy['policy']==POLICY,
            'Wrong frozen proof policy version')
    require(policy['maximum_document_characters']==8192 and policy['maximum_clauses']==16
            and policy['regex_flags']==['IGNORECASE','ASCII']and policy['case_or_document_identity_used_by_policy']is False,
            'Proof grammar caps/ASCII/identity scope differs')
    require(policy['grammar_patterns']['governing_law']==r'Disputes under (?P<subject>this (?:Agreement|Contract)) are governed by the laws of (?P<jurisdiction>[A-Za-z]{1,64})\.',
            'Opaque jurisdiction grammar permits unsupported conditions or modifiers')
    require(policy['logical_model']['primitive_predicates_independent']is True
            and policy['numeric_identity_fields']==list(NUMERIC_ID)
            and policy['rules_order']==['EXACT_GROUND_FACT','DISTINCT_EXACT_SAME_EVENT_VALUE','OPEN_WORLD_UNRELATED_PREDICATE','ABSTAIN'],
            'Proof deduction semantics differ')
    require(policy['coverage']['premise_equals_full_document']is True
            and policy['coverage']['retrieval_miss_implies_not_mentioned']is False
            and policy['confirmation']==[] and policy['training_lineage_complete']is False
            and policy['official_eligibility']=='HOLD','Proof coverage/eligibility scope overstated')
    return {'policy':POLICY,'independent_implementation':'Literal-position finite-state parser; candidate proof module never imported',
            'scope':'Controlled positive ground facts and exact scalar exclusivity over complete ASCII supplied source only'}

def decision_check(decision,reader,raw_readout,document,premise,hypothesis,spans,arm_override,role):
    require(type(decision)is dict and set(decision)=={'schema_version','epoch','raw_probabilities_E_C_N',
            'raw_typed_argmax','final_probabilities_E_C_N','final_typed_argmax','policy','certificate',
            'fallback_reason','semantic_decision_override'},'Exact composite decision schema required')
    require(decision['schema_version']==1 and decision['epoch']==33 and decision['policy']==POLICY,
            'Wrong composite decision scope')
    require(same(decision['raw_probabilities_E_C_N'],reader['probabilities_E_C_N'])
            and decision['raw_typed_argmax']==reader['native_typed_argmax'],'Composite raw readout changed')
    require(role in('engineering','dev'),'Unknown proof application role')
    cert,reason=(None,'proof_disabled_for_DEV')if role=='dev'else deduce(document,premise,hypothesis,spans)
    require(same(decision['certificate'],cert)and decision['fallback_reason']==reason,
            'Independent complete-input deduction/certificate replay failed')
    applied=cert is not None
    require(type(arm_override)is bool and arm_override is applied
            and type(decision['semantic_decision_override'])is bool
            and decision['semantic_decision_override']is applied,'Composite override discriminator differs')
    final=reader['native_typed_argmax']if not applied else cert['conclusion']
    probabilities=list(reader['probabilities_E_C_N'])if not applied else[float(label==final)for label in TYPED]
    require(same(decision['final_probabilities_E_C_N'],probabilities)and decision['final_typed_argmax']==final,
            'Frozen onehot-certificate/unchanged-raw final forecast differs')
    require(all(finite(v)and 0<=v<=1 for v in probabilities),'Invalid composite probabilities')
    result={'probabilities':dict(zip(CLASSES,probabilities)),'prediction':CANON[final],
            'binary_yes_probability':probabilities[0],'binary_prediction':'Yes'if probabilities[0]>.5 else'No'}
    return result,{'certificate_applied':applied,'rule':None if not applied else cert['rule'],
                   'conclusion':final,'raw_prediction':raw_readout['prediction'],
                   'final_prediction':result['prediction'],'prediction_changed':result['prediction']!=raw_readout['prediction'],
                   'full_supplied_input_coverage':premise==document and same(spans,[[0,len(document)]]),
                   'fallback_reason':reason}
