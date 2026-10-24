'use strict';
// One real native index and one genuine search per frozen document query.
// Admission, CPU enforcement and public network guards are preloaded externally.
const fs=require('node:fs'),path=require('node:path'),crypto=require('node:crypto');
const {performance}=require('node:perf_hooks');
const sha=bytes=>crypto.createHash('sha256').update(bytes).digest('hex');
const KIND='REAL_NATIVE_DOCUMENT_IDENTITY_QUALIFICATION';
const BINARY_SHA='ff559e9fac2e3d29a8b32e890fdb047bcd4bd28f389b4731ad72148b221d5a2e';
const ABSENT='{"present":false}',ABSENT_SHA=sha(Buffer.from(ABSENT,'utf8'));
const DIM=384,ROW_BYTES=1536;

function vectorBytes(value){
  if(value===null||typeof value!=='object')throw new Error('Actual native vector is not array/object');
  const keys=Object.keys(value);
  if(keys.length!==DIM||keys.some((key,index)=>key!==String(index)))
    throw new Error('Actual vector keys must be exactly0..383');
  const bytes=Buffer.alloc(ROW_BYTES);
  for(let i=0;i<DIM;i++){
    if(typeof value[i]!=='number'||!Number.isFinite(value[i])||!Object.is(Math.fround(value[i]),value[i]))
      throw new Error('Nonfinite or non-float32 actual native vector');
    bytes.writeFloatLE(value[i],i*4);
  }
  return bytes;
}

function decodeMatrix(block){
  if(!block||block.encoding!=='base64'||block.dtype!=='float32le'||!Array.isArray(block.shape)
      ||block.shape.length!==2||block.shape[0]!==262||block.shape[1]!==DIM
      ||block.bytes!==262*ROW_BYTES||typeof block.data_base64!=='string'
      ||!/^([A-Za-z0-9+/]{4})*([A-Za-z0-9+/]{2}==|[A-Za-z0-9+/]{3}=)?$/.test(block.data_base64))
    throw new Error('Exact262x384 lossless float32le source matrix required');
  const bytes=Buffer.from(block.data_base64,'base64');
  if(bytes.length!==block.bytes||bytes.toString('base64')!==block.data_base64||sha(bytes)!==block.sha256)
    throw new Error('Lossless matrix byte length/base64/hash mismatch');
  const vectors=[];
  for(let row=0;row<262;row++){
    const vector=new Float32Array(DIM);
    for(let col=0;col<DIM;col++){
      const value=bytes.readFloatLE(row*ROW_BYTES+col*4);
      if(!Number.isFinite(value))throw new Error('Nonfinite source embedding');
      vector[col]=value;
    }
    if(!vectorBytes(vector).equals(bytes.subarray(row*ROW_BYTES,(row+1)*ROW_BYTES)))
      throw new Error('Source float32 bits changed while decoding');
    vectors.push(vector);
  }
  return {bytes,vectors};
}

function compactHit(hit,documentIds,vectors,corpus){
  if(!hit||typeof hit.id!=='string'||!/^\d+$/.test(hit.id)||String(Number(hit.id))!==hit.id)
    throw new Error('Original native hit ID must be canonical decimal string');
  const id=Number(hit.id),row=documentIds.indexOf(id);
  if(row<0||!corpus.has(id))throw new Error('Native hit outside exact input index');
  if(typeof hit.score!=='number'||!Number.isFinite(hit.score))throw new Error('Invalid original native score');
  if(Object.prototype.hasOwnProperty.call(hit,'metadata'))throw new Error('Indexed metadata was absent');
  const observed=vectorBytes(hit.vector),source=vectorBytes(vectors[row]);
  if(!observed.equals(source))throw new Error('Native returned vector differs from exact indexed source bits');
  const out={};
  for(const key of Object.keys(hit)){
    if(key==='vector')continue;
    if(typeof hit[key]==='number'&&!Number.isFinite(hit[key]))throw new Error('Nonfinite original native field');
    out[key]=hit[key];
  }
  out.raw_keys=Object.keys(hit);
  out.vector_receipt={source_vector_row:row,dimensions:DIM,dtype:'float32le',sha256:sha(observed),
    source_sha256:sha(source),source_equal_before_stripping:true};
  out.metadata_receipt={present:false,canonical_json:ABSENT,sha256:ABSENT_SHA,source_equal_before_stripping:true};
  return out;
}

module.exports={vectorBytes,decodeMatrix,compactHit};
if(require.main===module){
  const partial={schema_version:1,epoch:29,kind:KIND,native:true,queries:[],errors:[],
    compact_schema:'epoch29-native-document-identity-f32le-v1',
    native_version_calls_attempted:0,native_version_calls_completed:0,
    native_index_initializations_attempted:0,native_index_initializations_completed:0,
    native_insertions_attempted:0,native_insertions_completed:0,
    native_len_calls_attempted:0,native_len_calls_completed:0,
    native_queries_attempted:0,native_queries_completed:0,native_hit_source_validations:0,
    native_hits_retained:0,native_self_hits_observed:0};
  let fd=null;
  function progress(event){
    partial.stage=event;
    if(fd!==null){
      const counters=Object.fromEntries(Object.entries(partial).filter(([key,value])=>key.startsWith('native_')&&typeof value==='number'));
      fs.writeSync(fd,JSON.stringify({event,at_unix:Date.now()/1000,helper_pid:process.pid,...counters})+'\n');
      fs.fsyncSync(fd);
    }
  }
  (async()=>{
    if(process.argv.length!==4)throw new Error('Exact bundle/output arguments required');
    const root=process.env.E29_PROJECT,source=fs.readFileSync(process.argv[2]);
    const bundle=JSON.parse(source),output=process.argv[3];
    if(!root||bundle.schema_version!==3||bundle.epoch!==29||bundle.kind!==KIND
        ||bundle.vector_encoding!=='base64_float32le_c_order'||bundle.document_ids.length!==262
        ||bundle.corpus_document_ids.length!==261||new Set(bundle.document_ids).size!==262
        ||bundle.document_ids[261]!==548||bundle.corpus_document_ids.some((id,i)=>id!==bundle.document_ids[i])
        ||bundle.corpus_document_ids.some((id,i,ids)=>!Number.isInteger(id)||id<=0||(i&&ids[i-1]>=id))
        ||bundle.corpus_document_ids.includes(548))throw new Error('Wrong exact document identity bundle');
    const {vectors}=decodeMatrix(bundle.vectors),corpus=new Set(bundle.corpus_document_ids);
    fd=fs.openSync(path.join(path.dirname(output),'native-progress.jsonl'),'wx',0o600);
    progress('SOURCE_MATRIX_VALIDATED_BEFORE_NATIVE_IMPORT');
    const binary=path.join(root,'retrieval/node_modules/ruvector-core-linux-x64-gnu/ruvector.node');
    if(sha(fs.readFileSync(binary))!==BINARY_SHA)throw new Error('Original core binary changed');
    const core=require(path.join(root,'retrieval/node_modules/@ruvector/core'));
    partial.native_version_calls_attempted++;progress('NATIVE_VERSION_BEFORE');
    const version=core.version();partial.native_version_calls_completed++;
    Object.assign(partial,{package_version:require(path.join(root,'retrieval/node_modules/@ruvector/core/package.json')).version,
      platform_package_version:require(path.join(root,'retrieval/node_modules/ruvector-core-linux-x64-gnu/package.json')).version,
      binary_version:version,native_binary_sha256:BINARY_SHA,helper_pid:process.pid,
      source_sha256:sha(fs.readFileSync(__filename)),bundle_sha256:sha(source),
      vector_receipt_method:'SHA256 of384 consecutive IEEE754 float32 little-endian values, no prefix; exact equality to indexed row before stripping',
      metadata_receipt_method:'SHA256 UTF8 {"present":false} no newline; indexed id/vector only',
      original_nonvector_fields_preserved:true,original_score_not_renamed:true});
    if(partial.package_version!=='0.1.33'||partial.platform_package_version!=='0.1.31'||version!=='2.3.0')
      throw new Error('Original native package/core version mismatch');
    const started=performance.now();
    partial.native_index_initializations_attempted++;progress('NATIVE_INDEX_BEFORE');
    const db=new core.VectorDb({dimensions:DIM,distanceMetric:core.JsDistanceMetric.Cosine,
      storagePath:path.join(process.cwd(),'ruvector.db')});
    partial.native_index_initializations_completed++;progress('NATIVE_INDEX_AFTER');
    partial.native_len_calls_attempted++;progress('NATIVE_EMPTY_LEN_BEFORE');
    const empty=await db.len();partial.native_len_calls_completed++;
    if(empty!==0)throw new Error('Native index did not start empty');
    for(let i=0;i<261;i++){
      partial.native_insertions_attempted++;progress('NATIVE_INSERT_BEFORE');
      await db.insert({id:String(bundle.corpus_document_ids[i]),vector:vectors[i]});
      partial.native_insertions_completed++;progress('NATIVE_INSERT_AFTER');
    }
    partial.native_len_calls_attempted++;progress('NATIVE_COMPLETE_LEN_BEFORE');
    const count=await db.len();partial.native_len_calls_completed++;
    if(count!==261)throw new Error('Original native index is incomplete');
    partial.initialized_vectors=count;partial.index_initialization_seconds=(performance.now()-started)/1000;
    for(let row=0;row<262;row++){
      const id=bundle.document_ids[row],exclude=corpus.has(id)?id:null,k=exclude===null?16:17;
      partial.active_query={document_id:id,source_vector_row:row,requested_k:k};
      partial.native_queries_attempted++;progress('NATIVE_QUERY_BEFORE');
      const t=performance.now(),hits=await db.search({vector:vectors[row],k});
      const seconds=(performance.now()-t)/1000;
      partial.native_queries_completed++;
      // Preserve the actual unvalidated result on a validation failure. Only
      // successful source-validated vectors are stripped from the final trace.
      partial.active_query.actual_raw_hits_unvalidated=hits;
      progress('NATIVE_QUERY_RETURNED');
      if(!Array.isArray(hits)||hits.length!==k)throw new Error('Native actual hit count differs from request');
      const rawIds=hits.map(hit=>Number(hit.id));
      if(new Set(rawIds).size!==k)throw new Error('Duplicate actual native hit IDs');
      const compact=hits.map(hit=>{const out=compactHit(hit,bundle.document_ids,vectors,corpus);
        partial.native_hit_source_validations++;return out;});
      const retained=rawIds.filter(hitId=>hitId!==exclude).slice(0,16);
      if(retained.length!==16)throw new Error('Actual native self-excluded top16 incomplete');
      const excluded=rawIds.filter(hitId=>hitId===exclude);
      partial.native_self_hits_observed+=excluded.length;partial.native_hits_retained+=retained.length;
      partial.queries.push({document_id:id,exclude_document_id:exclude,raw_ids:rawIds,raw_hits:compact,
        requested_k:k,filtered_top16_ids:retained,excluded_self_hit_ids:excluded,query_seconds:seconds,
        native_order_used_without_replacement:true});
      delete partial.active_query;progress('NATIVE_QUERY_COMPLETED');
    }
    partial.helper_resources=process.resourceUsage();progress('NATIVE_HELPER_COMPLETED');
    fs.writeFileSync(output,JSON.stringify(partial)+'\n',{flag:'wx'});fs.closeSync(fd);
  })().catch(error=>{
    partial.errors.push({name:error.name,message:String(error.message||error),stack:error.stack});
    try{progress('NATIVE_HELPER_FAILED');}catch(ignored){}
    try{fs.writeFileSync(process.argv[3]+'.failure.json',JSON.stringify(partial,(_key,value)=>
      typeof value==='number'&&!Number.isFinite(value)?{nonfinite_number:String(value)}:value)+'\n',{flag:'wx'});}catch(ignored){}
    console.error(error.stack||String(error));process.exitCode=2;
  });
}
