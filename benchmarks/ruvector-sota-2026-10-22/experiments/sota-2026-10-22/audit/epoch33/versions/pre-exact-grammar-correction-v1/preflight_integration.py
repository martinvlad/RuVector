"""Synthetic evidence-wire integration checks; zero native/model/data calls."""
import base64,copy,hashlib,json,struct,tempfile
from pathlib import Path
import evidence_audit as E
import query_audit as Q
import decision_proof_audit as D
from phase_audit import KIND

HERE=Path(__file__).resolve().parent
CANDIDATE=Path('/workspace/ruvector-e33-candidate-impl/project/experiments/sota-2026-10-22/candidate/epoch33')
checks=[]
def test(name,f):f();checks.append({'name':name,'passed':True})
def req(v):
    if not v:raise AssertionError('Fixture failed')
def rejects(f):
    try:f()
    except(ValueError,KeyError,TypeError,AssertionError):return
    raise AssertionError('Invalid integration receipt accepted')
def save(root,name,v):
    body=(json.dumps(v)+'\n').encode();(root/name).write_bytes(body)
    return {'path':name,'bytes':len(body),'sha256':hashlib.sha256(body).hexdigest()}
def block(n):
    body=struct.pack('<384f',1.,*([0.]*383))*n
    return {'encoding':'base64','dtype':'float32le','shape':[n,384],'bytes':len(body),
            'sha256':hashlib.sha256(body).hexdigest(),'data_base64':base64.b64encode(body).decode()}
def fixture(root,change=None):
    helper=root/'native_helper.cjs';helper.write_text('// synthetic unexecuted helper source\n')
    helper_sha=hashlib.sha256(helper.read_bytes()).hexdigest()
    vec_sha=block(1)['sha256'];source='The recipient shall protect data.'
    hypothesis='A recipient may copy notes.';expanded,family,terms,why=Q.derive(hypothesis)
    query={'schema_version':1,'epoch':33,'policy':Q.POLICY,'query_source_sha256':'a'*64,'query_policy_sha256':'b'*64,
           'original_hypothesis_sha256':E.digest(hypothesis.encode()),'original_query':hypothesis,'expanded_query':expanded,
           'original_query_sha256':E.digest(hypothesis.encode()),'expanded_query_sha256':E.digest(expanded.encode()),
           'recognized_predicate':family,'appended_terms':terms,'expansion_applied':True,'fallback_reason':why}
    bank={'schema_version':1,'epoch':33,'role':'engineering','records':[]}
    bundle={'schema_version':3,'epoch':33,'kind':KIND,'phase':'dev','role':'engineering',
            'vector_encoding':'base64_float32le_c_order','metadata_policy':'insert id and vector only; metadata absent','documents':[]}
    native={'epoch':33,'phase':'dev','role':'engineering','kind':KIND,'native':True,'errors':[],
            'stage':'HELPER_COMPLETED',
            'compact_schema':'epoch33-native-context-f32le-v1','package_version':'0.1.33','platform_package_version':'0.1.31',
            'binary_version':'2.3.0','native_binary_sha256':'ff559e9fac2e3d29a8b32e890fdb047bcd4bd28f389b4731ad72148b221d5a2e',
            'source_sha256':helper_sha,'documents':[]}
    raw={'role':'engineering','cases':[],'documents':{}}
    for i in range(1,7):
        cid=f'epoch32:cc0:engineering:{i}';did=-32000-i;didtext=str(did)
        inp={'id':cid,'document_id':did,'hypothesis_id':'eng-'+str(i),'document':source,'hypothesis':hypothesis,'input_sha256':'d'*64}
        bank['records'].append(inp)
        queries=[]
        for variant in('original','expanded'):
            hit={'id':'0','score':.5,'raw_keys':['id','score','vector'],
                 'vector_receipt':{'source_vector_index':0,'dimensions':384,'dtype':'float32le','sha256':vec_sha,
                                   'source_sha256':vec_sha,'source_equal_before_stripping':True},
                 'metadata_receipt':{'present':False,'canonical_json':E.ABSENT,'sha256':E.digest(E.ABSENT.encode()),'source_equal_before_stripping':True}}
            queries.append({'case_id':cid+'::retrieval:'+variant,'ids':[0],'raw_hits':[hit],'requested_k':1,
                            'query_ms':1.,'native_order_used_without_replacement':True})
        bundle['documents'].append({'document_id':didtext,'vectors':block(1),'query_vectors':block(2),
                                    'queries':[{'id':q['case_id']}for q in queries]})
        native['documents'].append({'document_id':didtext,'initialized_vectors':1,'initialization_ms':.5,'queries':queries})
        raw['documents'][didtext]={'units':[{'id':0,'start':0,'end':len(source)}],'retrieval_queries':{cid:query},
            'embedding':{'source_sha256s':[E.digest(source.encode())],
                         'exact_query_texts':[E.PREFIX+h for h in(hypothesis,expanded)]}}
        words=set(__import__('re').findall(r'\w+',source.casefold()));qw=set(__import__('re').findall(r'\w+',expanded.casefold()))
        score=len(words&qw)/len(words|qw)
        provenance={'source_char_start':0,'source_char_end':len(source),'source_byte_start':0,'source_byte_end':len(source.encode()),
                    'text':source,'text_sha256':E.digest(source.encode())}
        context={'selected_chunk_ids_source_order':[0],'ranking_ids_considered':[0],'selected_source_spans':[[0,len(source)]],
                 'premise_sha256':E.digest(source.encode()),'hypothesis_sha256':E.digest(hypothesis.encode()),
                 'source_provenance':{'selected_source_provenance':[provenance],'numeric_literals':[],
                    'numeric_literal_pattern':E.NUMBER.pattern,'numeric_literals_retained':0,'numeric_literals_omitted':0,
                    'source_text_normalized':False,'semantic_decision_override':False},
                 'selected_evidence_truncated':False,'claim_truncated':False,'joint_pair_tokens':8}
        arms={name:{'observed_ranking':[0],'premise':source,'context':copy.deepcopy(context),
                    'joint_pair_tokens':8,'native_query_seconds':.001 if name in('actual_native','native_original')else None,
                    'semantic_decision_override':False}for name in('actual_native','native_original','lexical','positional')}
        raw['cases'].append({'id':cid,'document_id':did,'hypothesis_id':'eng-'+str(i),'input_sha256':'d'*64,
                            'document':source,'document_sha256':E.digest(source.encode()),'hypothesis':hypothesis,
                            'hypothesis_sha256':E.digest(hypothesis.encode()),'document_preparation_ref':didtext,
                            'retrieval_query':query,'native':dict(queries[1],document_id=didtext,initialization_ms=.5,initialized_vectors=1),
                            'native_original':dict(queries[0],document_id=didtext,initialization_ms=.5,initialized_vectors=1),
                            'lexical_jaccard_scores':[score],'arms':arms})
    native.update(native_index_initializations_attempted=6,native_index_initializations_completed=6,
                  native_queries_attempted=12,native_queries_completed=12,native_len_calls_attempted=12,native_len_calls_completed=12,
                  native_version_calls_attempted=1,native_version_calls_completed=1,
                  native_insertions_attempted=6,native_insertions_completed=6,native_hit_source_validations=12)
    if change:change(raw,bundle,native)
    bankpin=save(root,'bank.json',bank);bundlepin=save(root,'bundle.json',bundle);native['bundle_sha256']=bundlepin['sha256']
    nativepin=save(root,'native.json',native);raw.update(input_bank=bankpin,vector_bundle=bundlepin,native_result=nativepin)
    plan={'engineering_inputs_path':'bank.json','engineering_inputs_sha256':bankpin['sha256'],
          'native_worker_path':'native_helper.cjs','query_source_sha256':'a'*64,'query_policy_sha256':'b'*64}
    return E.audit_evidence(root,raw,bank,'engineering',plan)
def integrated(change=None,valid=False):
    with tempfile.TemporaryDirectory(prefix='unit-wire-',dir=HERE)as tmp:
        if valid:
            v=fixture(Path(tmp),change);req(v['source_query_vectors']==12 and v['source_index_vectors']==6
                                         and v['native_hits_verified']==12 and v['typed_query_expansion_cases']==6)
        else:rejects(lambda:fixture(Path(tmp),change))
test('four_arm_two_query_per_case_receipt_integration',lambda:integrated(valid=True))
test('variant_order_swap_rejected',lambda:integrated(lambda raw,b,n:n['documents'][0]['queries'].reverse()))
test('original_native_context_mislabel_rejected',lambda:integrated(lambda raw,b,n:raw['cases'][0]['native_original'].update(case_id='wrong')))
test('expanded_lexical_wrong_score_rejected',lambda:integrated(lambda raw,b,n:raw['cases'][0].update(lexical_jaccard_scores=[.999])))
test('truncated_full_document_for_proof_rejected',lambda:integrated(lambda raw,b,n:raw['cases'][0].update(document='partial')))
test('native_timing_wrong_arm_attribution_rejected',lambda:integrated(lambda raw,b,n:raw['cases'][0]['arms']['native_original'].update(native_query_seconds=9.)))
test('native_final_counter_underreport_rejected',lambda:integrated(lambda raw,b,n:n.update(native_queries_completed=0)))
test('native_partial_receipt_never_complete_rejected',lambda:integrated(lambda raw,b,n:n.update(stage='QUERY_COMPLETED')))
test('query_policy_declaration_matches_independent_contract',lambda:req(Q.policy_check(json.loads((CANDIDATE/'QUERY_POLICY.json').read_text()))['policy']==Q.POLICY))
test('proof_policy_declaration_matches_independent_contract',lambda:req(D.policy_check(json.loads((CANDIDATE/'PROOF_POLICY.json').read_text()))['policy']==D.POLICY))
def candidate_sources():
    ready=json.loads((CANDIDATE/'SOURCE_READY.json').read_text());manifest=json.loads((CANDIDATE/'SOURCE_MANIFEST.json').read_text())
    project=CANDIDATE.parents[3]
    for row in manifest['files']:
        p=project/row['path'];body=p.read_bytes();req(len(body)==row['bytes']and hashlib.sha256(body).hexdigest()==row['sha256'])
    table=json.loads((CANDIDATE/'EXPECTED_COUNTERS.json').read_text())
    for key,full,n in [('expected_operation_counters',True,120),('engineering_rejected_operation_counters',False,24)]:
        c=table[key]['dev'];req(len(c)==81 and c['NLI_forward_calls_attempted']==c['NLI_forward_calls_completed']==c['NLI_readouts_completed']==n)
        req(c['native_queries_completed']==(60 if full else 12)and c['native_index_initializations_completed']==(14 if full else 6)
            and c['native_binary_loads_completed']==(2 if full else 1)and c['DEV_forward_calls_completed']==(96 if full else 0))
    req(ready['raw_arm_names']==list(('actual_native','native_original','lexical','positional')))
test('sealed_candidate_sources_and_81_exact_counter_tables',candidate_sources)

report={'schema_version':1,'epoch':33,'checks_passed':True,'checks':checks,
        'counts':{'tests':len(checks),'actual_native_model_tokenizer_calls':0,'annotated_source_parses':0,
                  'benchmark_choice_reads':0,'candidate_executable_modules_imported':0},
        'scope':'Synthetic four-arm/native-query vector metadata and source identity integration only. Candidate source files are hashed, never executed; no benchmark generalization claim.'}
with(HERE/'integration-preflight-v3.json').open('x')as f:json.dump(report,f,indent=2);f.write('\n')
print(json.dumps({'checks_passed':True,'tests':len(checks)}))
