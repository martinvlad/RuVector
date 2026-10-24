"""Pure stdlib numerical/evidence regression checks; no actual ML/native calls."""
import argparse
import base64
import copy
import json
from pathlib import Path
import struct
import tempfile
import time
import score_identity as S
from identity_common import sha,normalize,model_text,write_new

def main(output):
    checks=[]
    def check(name,fn):
        fn();checks.append({'name':name,'passed':True})
    def rejects(fn):
        try:fn()
        except (ValueError,KeyError,TypeError,IndexError,ZeroDivisionError):return
        raise AssertionError('Expected invariant rejection')
    def eq(a,b):
        if a!=b:raise AssertionError((a,b))
    def block(payload,rows=1):
        return {'encoding':'base64','dtype':'float32le','shape':[rows,384],
                'bytes':len(payload),'sha256':sha(payload),'data_base64':base64.b64encode(payload).decode()}
    started=time.perf_counter()
    unit=[1.0]+[0.0]*383;payload=struct.pack('<384f',*unit);good=block(payload)
    check('historical normalization preserves word separators',lambda:eq(normalize('  A\t B\nC '),'a b c'))
    check('NFKC model input remains separate from source alias hash',lambda:(eq(normalize('Ａ B'),'ａ b'),eq(model_text(normalize('Ａ B')),'a b')))
    check('lossless source f32 matrix accepted',lambda:eq(S.matrix_block(good)[0],[unit]))
    bad=copy.deepcopy(good);bad['sha256']='0'*64
    check('changed source vector digest rejected',lambda:rejects(lambda:S.matrix_block(bad)))
    nan=block(struct.pack('<384f',float('nan'),*([0.0]*383)))
    check('nonfinite float32 vector rejected',lambda:rejects(lambda:S.matrix_block(nan)))
    zero=block(bytes(1536))
    check('zero embedding cannot masquerade as normalized source',lambda:rejects(lambda:S.matrix_block(zero)))
    wrong=copy.deepcopy(good);wrong['shape']=[2,384]
    check('matrix declared length mismatch rejected',lambda:rejects(lambda:S.matrix_block(wrong)))
    vectors={9:unit,2:unit,5:unit}
    check('dense cosine uses numeric ID ties and excludes self',lambda:eq([r['document_id']for r in S.exact_dense(9,[9,5,2],vectors)],[2,5]))
    rows=[{'true_alias_document_ids':[5],'native_top16_ids':[2],'native_confirmed_alias_ids':[]},
          {'true_alias_document_ids':[],'native_top16_ids':[2],'native_confirmed_alias_ids':[]}]
    check('missed known alias remains a measured miss',lambda:eq(S.metrics(rows,'native')['any_alias_query_recall_at16'],0.0))
    check('unresolved count preserves missed and negative query',lambda:eq(S.metrics(rows,'native')['UNRESOLVED_queries'],2))
    check('zero positive denominator yields unknown recall',lambda:eq(S.metrics(rows[1:],'native')['any_alias_query_recall_at16'],None))
    # One full structural positive replay exercises the actual262-query schema,
    # compact native/source-vector receipts, cosine ties and exact-hash status.
    # These vectors and hashes are synthetic unit evidence, never model outputs.
    corpus=list(range(1,261))+[515];qids=corpus+[548]
    orthogonal=[0.0,1.0]+[0.0]*382
    v={i:(orthogonal if i in [515,548]else unit)for i in qids}
    payload262=b''.join(struct.pack('<384f',*v[i])for i in qids)
    _,receipts=S.matrix_block(block(payload262,262));index={i:j for j,i in enumerate(qids)}
    meta={'present':False,'canonical_json':'{"present":false}','sha256':sha(b'{"present":false}'),'source_equal_before_stripping':True}
    queries=[];truth=[];native_queries=[]
    for did in qids:
        ranking=sorted(corpus,key=lambda i:(-S.cosine(v[did],v[i]),i));k=17 if did in corpus else 16
        rawids=ranking[:k];retained=[i for i in rawids if i!=did][:16]
        hits=[]
        for i in rawids:
            receipt={**receipts[index[i]],'source_vector_row':index[i],'source_sha256':receipts[index[i]]['sha256'],'source_equal_before_stripping':True}
            hits.append({'id':str(i),'score':1-S.cosine(v[did],v[i]),'raw_keys':['id','score','vector'],
                         'vector_receipt':receipt,'metadata_receipt':meta})
        n={'document_id':did,'raw_ids':rawids,'raw_hits':hits,'requested_k':k,'filtered_top16_ids':retained,
           'excluded_self_hit_ids':[i for i in rawids if i==did],'query_seconds':0.0,'native_order_used_without_replacement':True}
        targets=[515]if did==548 else[];dense=S.exact_dense(did,corpus,v)[:16]
        sourcehash='alias'if did in [515,548]else str(did)
        q={'query_id':'document:'+str(did),'document_id':did,'exclude_document_id':did if did in corpus else None,
           'normalized_document_sha256':sourcehash,'native':n,
           'dense':{'top16':dense,'candidate_count':260 if did in corpus else 261,'elapsed_seconds':0.0},
           'authoritative_alias_document_ids':targets,'native_confirmed_alias_ids':[i for i in retained if i in targets],
           'dense_confirmed_alias_ids':[r['document_id']for r in dense if r['document_id']in targets],
           'native_status':'CONFIRMED_NORMALIZED_ALIAS'if targets else'UNRESOLVED',
           'dense_status':'CONFIRMED_NORMALIZED_ALIAS'if targets else'UNRESOLVED'}
        queries.append(q);truth.append({'document_id':did,'normalized_document_sha256':sourcehash,'true_alias_document_ids':targets});native_queries.append(n)
    native={'epoch':29,'kind':S.KIND,'package_version':'0.1.33','platform_package_version':'0.1.31','binary_version':'2.3.0',
            'native_binary_sha256':'ff559e9fac2e3d29a8b32e890fdb047bcd4bd28f389b4731ad72148b221d5a2e',
            'bundle_sha256':'synthetic','initialized_vectors':261,'errors':[],'original_nonvector_fields_preserved':True,
            'original_score_not_renamed':True,'queries':native_queries}
    check('complete compact native artifact and source-vector receipts replay',lambda:S.replay_native_artifact({'queries':queries},native,corpus,qids,receipts,{'sha256':'synthetic'}))
    replayed=S.replay_queries(queries,{'query_records':truth},corpus,v,receipts)
    check('complete262query positive schema yields finite known-alias recall',lambda:eq(S.metrics(replayed,'native')['any_alias_query_recall_at16'],1.0))
    clean=copy.deepcopy(queries);clean[0]['native_status']='CLEAN'
    check('ANN absence cannot emit CLEAN even on oracle-negative query',lambda:rejects(lambda:S.replay_queries(clean,{'query_records':truth},corpus,v,receipts)))
    with tempfile.TemporaryDirectory(prefix='score-preflight-',dir=Path(__file__).resolve().parent)as temp:
        folder=Path(temp);final=folder/'raw.json';partial=folder/'raw.partial.json'
        duplicate=folder/'duplicate.json';duplicate.write_text('{"x":1,"x":2}')
        check('duplicate JSON keys rejected',lambda:rejects(lambda:S.read(duplicate)))
        nonfinite=folder/'nonfinite.json';nonfinite.write_text('{"unused":NaN}')
        check('unused nonfinite JSON fields rejected',lambda:rejects(lambda:S.read(nonfinite)))
        raw={'epoch':29,'counters':{'native_queries_attempted':2},'errors':[]}
        final.write_text(json.dumps(raw));pin=S.identity(final)
        ex={'status':'WORKER_COMPLETED','raw_operation_counters_source':'raw.json','operation_counts_complete':True,
            'backend_execution_since_checkpoint':'NOT_APPLICABLE_FINAL_RAW','raw_bytes':pin['bytes'],'raw_sha256':pin['sha256'],
            'raw_operation_counters':raw['counters']}
        check('normal final raw seal selected exactly',lambda:eq(S.selected_raw(final,ex)[2]['mode'],'FINAL'))
        px={**ex,'status':'WORKER_FAILED_OR_TIMEOUT','raw_operation_counters_source':'raw.partial.json',
            'operation_counts_complete':False,'backend_execution_since_checkpoint':'UNKNOWN'}
        partial.write_text(json.dumps(raw));pp=S.identity(partial);px.update(partial_raw_bytes=pp['bytes'],partial_raw_sha256=pp['sha256'])
        check('valid final cannot hide behind partial counter source',lambda:rejects(lambda:S.selected_raw(final,px)))
        final.write_text('{"interrupted":');fp=S.identity(final);px.update(raw_bytes=fp['bytes'],raw_sha256=fp['sha256'])
        check('malformed sealed final plus valid sealed partial retained',lambda:eq(S.selected_raw(final,px)[2]['mode'],'PARTIAL'))
        ux={**px,'raw_operation_counters_source':'UNKNOWN','raw_operation_counters':None}
        check('valid partial counters cannot be erased by UNKNOWN',lambda:rejects(lambda:S.selected_raw(final,ux)))
        saved_partial=partial.read_bytes();partial.unlink()
        unknown_no_partial={**ux,'partial_raw_bytes':None,'partial_raw_sha256':None}
        check('known malformed final without checkpoint retains ref with UNKNOWN parsed counters',
              lambda:(eq(S.selected_raw(final,unknown_no_partial)[0],None),eq(S.selected_raw(final,unknown_no_partial)[1],final),
                      eq(S.selected_raw(final,unknown_no_partial)[2]['unparsed_final_raw'],S.identity(final))))
        partial.write_bytes(saved_partial)
        final.unlink();px.update(raw_bytes=None,raw_sha256=None)
        check('absent final with sealed partial retained',lambda:eq(S.selected_raw(final,px)[2]['mode'],'PARTIAL'))
        partial.unlink();ux.update(raw_bytes=None,raw_sha256=None)
        check('true raw absence keeps operation counts UNKNOWN',lambda:eq(S.selected_raw(final,ux)[0],None))
        forged={**ux,'raw_operation_counters':{'native_queries_attempted':0}}
        check('absent raw cannot invent zero operation counters',lambda:rejects(lambda:S.selected_raw(final,forged)))
    report={'schema_version':1,'epoch':29,'kind':S.KIND,'status':'PASS_STDLIB_SCORER_NUMERICAL_AND_RECEIPT_PREFLIGHT',
            'checks':checks,'check_count':len(checks),'seconds':time.perf_counter()-started,
            'actual_native_model_tokenizer_or_ORT_initializations':0,'actual_inference_calls':0,
            'source_annotation_choice_or_evidence_reads':0,'real_engineering_input_reads':0,
            'synthetic_scope':'Unit/evidence numerical probes only; no authored semantic benchmark or actual native API calls',
            'scorer_source':S.identity(Path(S.__file__).resolve())}
    write_new(output,report);print(json.dumps({'status':report['status'],'checks':len(checks)}))

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--output',required=True);main(p.parse_args().output)
