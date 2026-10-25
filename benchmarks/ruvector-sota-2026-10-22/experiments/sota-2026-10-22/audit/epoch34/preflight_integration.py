"""Pure authored hybrid/source/native-wire tamper fixtures; no measured data."""
import base64,copy,hashlib,json,re,struct,tempfile
from pathlib import Path
import evidence_audit as E
import query_audit as Q
import decision_proof_audit as D
import group_audit as G
from phase_audit import KIND
HERE=Path(__file__).resolve().parent
CANDIDATE=Path('/workspace/ruvector-e34-candidate-impl/project/experiments/sota-2026-10-22/candidate/epoch34')
checks=[]
def test(n,f):f();checks.append({'name':n,'passed':True})
def req(v):
    if not v:raise AssertionError('Authored fixture expectation failed')
def rejects(f):
    try:f()
    except(ValueError,KeyError,TypeError,AssertionError):return
    raise AssertionError('Invalid wire fixture accepted')
def save(root,n,v):
    b=(json.dumps(v)+'\n').encode();(root/n).write_bytes(b);return {'path':n,'bytes':len(b),'sha256':hashlib.sha256(b).hexdigest()}
def block(n):
    b=struct.pack('<384f',1.,*([0.]*383))*n
    return {'encoding':'base64','dtype':'float32le','shape':[n,384],'bytes':len(b),'sha256':hashlib.sha256(b).hexdigest(),'data_base64':base64.b64encode(b).decode()}
SOURCE='Information may be copied.\nRecipients shall return records within 5 days; however, copies may be retained for 30 days.\nDisputes are governed by Nevada law.'
HYPOTHESIS='Information may be copied.'
def authored_units():
    stops=[m.end()for m in G.SENTENCE.finditer(SOURCE)];units=[];start=0
    for i,end in enumerate(stops):
        units.append({'id':i,'start':start,'end':end,'sentence_id':i,'sentence_span':[start,end],'paragraph_id':0,'group_id':[0,1,1,2][i],'qualifier_attached':i==2,'token_fallback':False});start=end
    req(start==len(SOURCE)and len(units)==4);return units

def context(units,catalogue,ranking,prelude):
    groupids=[];anchors={}
    for u in ranking:
        g=units[u]['group_id']
        if g not in anchors:groupids.append(g);anchors[g]=u
    mandatory=groupids[:2];selected=[];trace=[]
    for j,gid in enumerate(mandatory):
        g=catalogue[gid];selected.extend(g['unit_ids']);trace.append({'group_id':gid,'unit_ids':g['unit_ids'],'role':'mandatory-ranked-group','anchor':anchors[gid],'source_span':[g['start'],g['end']],'candidate_pair_tokens':8*(j+1),'accepted':True,'all_group_units_admitted_together':True})
    spans=G.merged(units,selected);premise='\n\n'.join(SOURCE[a:b]for a,b in spans);omitted=[i for i in range(len(units))if i not in selected];covered=sum(b-a for a,b in spans)
    ctx={'policy':G.POLICY,'source_sentence_groups':catalogue,'qualifier_regex':G.QUALIFIER.pattern,'bullet_regex':G.BULLET.pattern,
        'definition_priority':prelude,'definition_admission_priority':'after-both-mandatory-ranked-groups','optional_definition_group_ids_admitted':[],
        'group_ranking_ids':groupids,'group_ranking_anchor_unit_ids':[anchors[g]for g in groupids],
        'mandatory_ranked_group_ids':mandatory,'mandatory_ranked_anchor_unit_ids':[anchors[g]for g in mandatory],'mandatory_ranked_group_cap':2,'single_group_degenerate':False,
        'selected_group_ids_admission_order':mandatory,'all_selected_groups_complete':True,'ranking_ids_considered':ranking,'ranking_depth':4,'ranked_anchor_candidate_cap':4,'joint_pair_token_cap':512,
        'additional_neighbor_unit_ids_inspected':[],'selected_chunk_ids_rank_order':selected,'selected_chunk_ids_source_order':sorted(selected),'selected_source_spans':spans,
        'omitted_chunk_ids':omitted,'omitted_source_spans':[[units[i]['start'],units[i]['end']]for i in omitted],'total_document_chunks':4,'retained_source_characters':covered,'document_characters':len(SOURCE),'document_character_coverage':covered/len(SOURCE),
        'joint_pair_tokens':16,'selected_token_fallback_unit_ids':[],'packing_attempts':trace,'selected_evidence_truncated':False,'claim_truncated':False,
        'premise_sha256':E.digest(premise.encode()),'hypothesis_sha256':E.digest(HYPOTHESIS.encode())}
    provenance=[{'source_char_start':a,'source_char_end':b,'source_byte_start':len(SOURCE[:a].encode()),'source_byte_end':len(SOURCE[:b].encode()),'text':SOURCE[a:b],'text_sha256':E.digest(SOURCE[a:b].encode())}for a,b in spans]
    literals=[]
    for m in E.NUMBER.finditer(SOURCE):
        a,b=m.span();literals.append({'source_char_start':a,'source_char_end':b,'source_byte_start':len(SOURCE[:a].encode()),'source_byte_end':len(SOURCE[:b].encode()),'text':m.group(),'text_sha256':E.digest(m.group().encode()),'retained':any(x<=a and b<=y for x,y in spans),'lexical_year_candidate':False})
    ctx['source_provenance']={'selected_source_provenance':provenance,'numeric_literals':literals,'numeric_literal_pattern':E.NUMBER.pattern,'numeric_literals_retained':sum(r['retained']for r in literals),'numeric_literals_omitted':sum(not r['retained']for r in literals),'source_text_normalized':False,'semantic_decision_override':False}
    return premise,ctx

def wire(root,change=None):
    units=authored_units();catalogue=G.source_groups(SOURCE,units)
    prelude={'policy':G.POLICY+':claim-independent-whole-group-definition-priority','selected_unit_ids':[],'selected_group_ids':[],'selected_source_spans':[],'priority_tokens':3,'priority_token_cap':160,'priority_text_sha256':E.digest(b''),'candidate_attempts':[],'whole_groups_only':True,'token_fallback_admitted':False,'claim_dependent':False,'literal_first_text_guaranteed':False}
    original={'schema_version':1,'epoch':34,'policy':Q.POLICY,'query_source_sha256':'a'*64,'query_policy_sha256':'b'*64,'original_hypothesis_sha256':E.digest(HYPOTHESIS.encode()),'original_query':HYPOTHESIS,'query':HYPOTHESIS,'original_query_sha256':E.digest(HYPOTHESIS.encode()),'query_sha256':E.digest(HYPOTHESIS.encode()),'expansion_applied':False}
    chunks=[SOURCE[u['start']:u['end']]for u in units];words=[set(re.findall(r'\w+',c.casefold()))for c in chunks];qw=set(re.findall(r'\w+',HYPOTHESIS.casefold()));scores=[len(qw&w)/max(1,len(qw|w))for w in words];lex=sorted(range(4),key=lambda i:(-scores[i],i));req(lex[0]==0)
    native_order=[3,1,2,0];hybrid=[0,3,1,2]
    hreceipt={'policy':Q.POLICY,'lexical_anchor_unit_id':0,'lexical_anchor_group_id':0,'native_complement_unit_id':3,'native_complement_group_id':2,'single_group_degenerate':False,'hybrid_ranking':hybrid}
    helper=root/'native_helper.cjs';helper.write_text('// Pure fixture: no actual native helper\n');helper_sha=E.digest(helper.read_bytes());vecsha=E.block_digests(block(4))
    bank={'schema_version':1,'epoch':34,'role':'engineering','records':[]};bundle={'schema_version':3,'epoch':34,'kind':KIND,'phase':'dev','role':'engineering','vector_encoding':'base64_float32le_c_order','metadata_policy':'insert id and vector only; metadata absent','documents':[]}
    native={'epoch':34,'kind':KIND,'phase':'dev','role':'engineering','native':True,'errors':[],'stage':'HELPER_COMPLETED','compact_schema':'epoch34-native-context-f32le-v1','package_version':'0.1.33','platform_package_version':'0.1.31','binary_version':'2.3.0','native_binary_sha256':'ff559e9fac2e3d29a8b32e890fdb047bcd4bd28f389b4731ad72148b221d5a2e','source_sha256':helper_sha,'documents':[]}
    raw={'role':'engineering','cases':[],'documents':{}}
    for i in range(1,7):
        cid=f'epoch32:cc0:engineering:{i}';did=-32000-i;dt=str(did)
        inp={'id':cid,'document_id':did,'hypothesis_id':'eng-'+str(i),'document':SOURCE,'hypothesis':HYPOTHESIS,'input_sha256':'d'*64};bank['records'].append(inp)
        hits=[]
        for idx in native_order:
            hits.append({'id':str(idx),'score':.5,'raw_keys':['id','score','vector'],'vector_receipt':{'source_vector_index':idx,'dimensions':384,'dtype':'float32le','sha256':vecsha[idx],'source_sha256':vecsha[idx],'source_equal_before_stripping':True},'metadata_receipt':{'present':False,'canonical_json':E.ABSENT,'sha256':E.digest(E.ABSENT.encode()),'source_equal_before_stripping':True}})
        q={'case_id':cid+'::retrieval:original','ids':native_order,'raw_hits':hits,'requested_k':4,'query_ms':1.,'native_order_used_without_replacement':True}
        bundle['documents'].append({'document_id':dt,'vectors':block(4),'query_vectors':block(1),'queries':[{'id':q['case_id']}]})
        native['documents'].append({'document_id':dt,'initialized_vectors':4,'initialization_ms':.5,'queries':[q]})
        raw['documents'][dt]={'units':copy.deepcopy(units),'prelude':copy.deepcopy(prelude),'retrieval_queries':{cid:copy.deepcopy(original)},'embedding':{'source_sha256s':[E.digest(x.encode())for x in chunks],'exact_query_texts':[E.PREFIX+HYPOTHESIS]}}
        arms={}
        for n,ranking in {'actual_native':hybrid,'native_original':native_order,'lexical':lex,'positional':[0,1,2,3]}.items():
            premise,ctx=context(units,catalogue,ranking,prelude);arms[n]={'observed_ranking':ranking,'premise':premise,'context':ctx,'joint_pair_tokens':16,'native_query_seconds':.001 if n in('actual_native','native_original')else None,'semantic_decision_override':False}
        nativecase=dict(q,document_id=dt,initialization_ms=.5,initialized_vectors=4)
        raw['cases'].append({'id':cid,'document_id':did,'hypothesis_id':'eng-'+str(i),'input_sha256':'d'*64,'document':SOURCE,'document_sha256':E.digest(SOURCE.encode()),'hypothesis':HYPOTHESIS,'hypothesis_sha256':E.digest(HYPOTHESIS.encode()),'document_preparation_ref':dt,'retrieval_query':copy.deepcopy(original),'native':copy.deepcopy(nativecase),'native_original':copy.deepcopy(nativecase),'hybrid_selection':copy.deepcopy(hreceipt),'lexical_jaccard_scores':scores,'arms':arms})
    native.update(native_index_initializations_attempted=6,native_index_initializations_completed=6,native_queries_attempted=6,native_queries_completed=6,native_len_calls_attempted=12,native_len_calls_completed=12,native_version_calls_attempted=1,native_version_calls_completed=1,native_insertions_attempted=24,native_insertions_completed=24,native_hit_source_validations=24)
    if change:change(raw,bundle,native)
    bp=save(root,'bank.json',bank);vp=save(root,'bundle.json',bundle);native['bundle_sha256']=vp['sha256'];np=save(root,'native.json',native);raw.update(input_bank=bp,vector_bundle=vp,native_result=np)
    plan={'engineering_inputs_path':'bank.json','engineering_inputs_sha256':bp['sha256'],'native_worker_path':'native_helper.cjs','query_source_sha256':'a'*64,'query_policy_sha256':'b'*64}
    return E.audit_evidence(root,raw,bank,'engineering',plan)
def integrated(change=None,valid=False):
    with tempfile.TemporaryDirectory(prefix='unit-hybrid-wire-',dir=HERE)as temp:
        if valid:
            report=wire(Path(temp),change);req(report['source_query_vectors']==6 and report['native_hits_verified']==24 and report['query_expansions']==0 and all(r['hybrid_ranking_differs_native_only']for r in report['hybrid_selection_observations']))
        else:rejects(lambda:wire(Path(temp),change))
test('hybrid_original_query_shared_six_case_wire',lambda:integrated(valid=True))
test('query_expansion_rejected',lambda:integrated(lambda r,b,n:r['cases'][0]['retrieval_query'].update(query=HYPOTHESIS+' copy')))
test('second_native_query_rejected',lambda:integrated(lambda r,b,n:n['documents'][0]['queries'].append(copy.deepcopy(n['documents'][0]['queries'][0]))))
test('hybrid_wrong_complement_group_rejected',lambda:integrated(lambda r,b,n:r['cases'][0]['hybrid_selection'].update(native_complement_group_id=1)))
test('hybrid_equals_native_without_anchor_rejected',lambda:integrated(lambda r,b,n:r['cases'][0]['arms']['actual_native'].update(observed_ranking=[3,1,2,0])))
test('native_control_wrong_reuse_rejected',lambda:integrated(lambda r,b,n:r['cases'][0]['native_original'].update(query_ms=9.)))
test('qualifier_group_omission_rejected',lambda:integrated(lambda r,b,n:r['documents']['-32001']['units'][2].update(group_id=2)))
test('mandatory_group_drop_rejected',lambda:integrated(lambda r,b,n:r['cases'][0]['arms']['actual_native']['context'].update(mandatory_ranked_group_ids=[0])))
test('neighbor_filler_injection_rejected',lambda:integrated(lambda r,b,n:r['cases'][0]['arms']['actual_native']['context'].update(additional_neighbor_unit_ids_inspected=[1])))
test('numeric_literal_retention_lie_rejected',lambda:integrated(lambda r,b,n:r['cases'][0]['arms']['actual_native']['context']['source_provenance']['numeric_literals'][0].update(retained=True)))
test('false_group_token_fit_rejected',lambda:integrated(lambda r,b,n:r['cases'][0]['arms']['actual_native']['context']['packing_attempts'][0].update(candidate_pair_tokens=513)))
test('underreported_native_query_count_rejected',lambda:integrated(lambda r,b,n:n.update(native_queries_completed=12)))
test('partial_native_stage_rejected',lambda:integrated(lambda r,b,n:n.update(stage='QUERY_COMPLETED')))
test('candidate_query_policy_matches_contract',lambda:req(Q.policy_check(json.loads((CANDIDATE/'QUERY_POLICY.json').read_bytes()))['policy']==Q.POLICY))
test('candidate_all_role_disabled_proof_policy_matches_contract',lambda:req(D.policy_check(json.loads((CANDIDATE/'PROOF_POLICY.json').read_bytes()))['policy']==D.POLICY))
def complement_cases():
    units=[{'group_id':0}for _ in range(40)]+[{'group_id':1}]
    rejects(lambda:Q.hybrid_check(list(range(41)),list(range(40)),units,{}))
    units=[{'group_id':0}];receipt={'policy':Q.POLICY,'lexical_anchor_unit_id':0,'lexical_anchor_group_id':0,'native_complement_unit_id':None,'native_complement_group_id':None,'single_group_degenerate':True,'hybrid_ranking':[0]}
    req(Q.hybrid_check([0],[0],units,receipt)[0]==[0])
test('no_native_complement_multigroup_fails_single_group_disclosed',complement_cases)
def disabled_decision_mutations():
    p=[.7,.2,.1];reader={'probabilities_E_C_N':p,'native_typed_argmax':'Entailment'};raw={'probabilities':dict(zip(['entailment','contradiction','not_mentioned'],p)),'prediction':'entailment','binary_yes_probability':.7,'binary_prediction':'Yes'}
    decision={'schema_version':1,'epoch':34,'policy':D.POLICY,'raw_probabilities_E_C_N':p,'raw_typed_argmax':'Entailment','final_probabilities_E_C_N':p,'final_typed_argmax':'Entailment','certificate':None,'fallback_reason':'proof_disabled_for_ALL_ROLES','semantic_decision_override':False}
    for role in('engineering','dev'):req(D.decision_check(decision,reader,raw,'document','premise','claim',[[0,3]],False,role)[0]==raw)
    for key,value in [('certificate',{}),('semantic_decision_override',True),('final_probabilities_E_C_N',[1.,0.,0.]),('fallback_reason','proof_disabled_for_DEV')]:
        changed=copy.deepcopy(decision);changed[key]=value;rejects(lambda:D.decision_check(changed,reader,raw,'document','premise','claim',[[0,3]],False,'engineering'))
test('both_roles_raw_equality_proof_and_onehot_rejected',disabled_decision_mutations)
report={'schema_version':1,'epoch':34,'checks_passed':True,'checks':checks,'counts':{'tests':len(checks),'actual_native_model_tokenizer_calls':0,'annotated_source_parses':0,'benchmark_choice_reads':0,'candidate_executable_modules_imported':0},'scope':'Authored four-arm shared-query native-wire integrity mutations, qualifier/group/number preservation and all-role raw T1 equality only. No benchmark data or measured output is used.'}
with(HERE/'integration-preflight-v1.json').open('x')as f:json.dump(report,f,indent=2);f.write('\n')
print(json.dumps({'checks_passed':True,'tests':len(checks)}))
