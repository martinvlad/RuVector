'use strict';
// Inert engineering tests only: no native library, model or dataset is imported.
const assert=require('node:assert/strict'),crypto=require('node:crypto');
const m=require('./native_helper.cjs');let tests=0;let fakeProgress=null;
const check=(fn)=>{fn();tests++;};
const fails=(fn,code)=>assert.throws(fn,new RegExp(code));
function block(rows=2){const bytes=Buffer.alloc(rows*1536);for(let i=0;i<rows;i++)bytes.writeFloatLE(1,i*1536);
 return {encoding:'base64',dtype:'float32le',shape:[rows,384],bytes:bytes.length,
  sha256:crypto.createHash('sha256').update(bytes).digest('hex'),data_base64:bytes.toString('base64')};}
check(()=>assert.equal(m.decode(block(),2).length,2));
check(()=>fails(()=>m.decode(block(),3),'BUNDLE_F32_SHAPE'));
check(()=>{const b=block();b.dtype='float32';fails(()=>m.decode(b,2),'BUNDLE_F32_SHAPE');});
check(()=>{const b=block();b.sha256='0'.repeat(64);fails(()=>m.decode(b,2),'BUNDLE_F32_IDENTITY');});
check(()=>{const b=block();b.data_base64+='=';fails(()=>m.decode(b,2),'BUNDLE_F32_IDENTITY');});
check(()=>{const b=block(),raw=Buffer.from(b.data_base64,'base64');raw.writeFloatLE(.5,0);
 b.data_base64=raw.toString('base64');b.sha256=crypto.createHash('sha256').update(raw).digest('hex');
 fails(()=>m.decode(b,2),'F32_NORMALIZED');});
check(()=>{const v=m.decode(block(),2);const h=m.compact({id:'doc-B',score:.3,vector:v[1]},v,new Map([['doc-A',0],['doc-B',1]]));
 assert.equal(h.vector_receipt.source_vector_index,1);assert.equal(h.vector_receipt.source_equal_before_stripping,true);});
check(()=>{const v=m.decode(block(),2);v[1][0]=Math.fround(.99999);
 fails(()=>m.compact({id:'doc-A',score:.3,vector:v[1]},v,new Map([['doc-A',0],['doc-B',1]])),'NATIVE_SOURCE_VECTOR_BITS');});
check(()=>{const v=m.decode(block(),2);fails(()=>m.compact({id:'missing',score:.3,vector:v[0]},v,new Map([['doc-A',0]])),'NATIVE_KNOWN_SOURCE_ID');});
check(()=>{const v=m.decode(block(),2);fails(()=>m.compact({id:'doc-A',score:NaN,vector:v[0]},v,new Map([['doc-A',0]])),'NATIVE_SCORE_FINITE');});
check(()=>{const v=m.decode(block(),2);fails(()=>m.compact({id:'doc-A',score:0,vector:v[0],metadata:{}},v,new Map([['doc-A',0]])),'NATIVE_METADATA_ABSENT');});
check(()=>assert.deepEqual(m.returnedTieOrder([{id:'Z',score:3},{id:'B',score:2},{id:'A',score:2},{id:'D',score:1}]).map(x=>x.id),['Z','A','B','D']));
check(()=>assert.deepEqual(m.returnedTieOrder([{id:'Z',score:1},{id:'B',score:2},{id:'A',score:2},{id:'D',score:3}]).map(x=>x.id),['Z','A','B','D']));
check(()=>assert.deepEqual(m.ids(['10','2'],2,'IDS'),['10','2']));
check(()=>fails(()=>m.ids(['1','1'],2,'IDS'),'IDS'));
check(()=>fails(()=>m.ids(['a\nb'],1,'IDS'),'IDS'));
check(()=>{const c=m.makeCounters(()=>{});c.attempt('native_queries','QUERY_BEFORE');fails(()=>c.attempt('native_queries','QUERY_BEFORE'),'NATIVE_OPERATION_CAP_OR_INFLIGHT');});
check(()=>{const c=m.makeCounters(()=>{});fails(()=>c.complete('native_queries'),'NATIVE_COMPLETION_ACCOUNTING');});
check(()=>{const c=m.makeCounters(()=>{});c.attempt('native_len_calls',null);c.complete('native_len_calls');assert.equal(c.counters.native_len_calls_completed,1);});
check(()=>{const c=m.makeCounters(()=>{});c.attempt('native_queries','QUERY_BEFORE');c.complete('native_queries');fails(()=>c.complete('native_queries'),'NATIVE_COMPLETION_ACCOUNTING');});
check(()=>{const rows=[];const c=m.makeCounters(event=>rows.push({event,monotonic_milliseconds:rows.length,counters:{...c.counters}}));
 c.attempt('native_binary_loads','NATIVE_LOAD_BEFORE');c.complete('native_binary_loads');rows.push({event:'NATIVE_LOAD_COMPLETE',monotonic_milliseconds:rows.length,counters:{...c.counters}});
 c.attempt('native_version_calls','NATIVE_VERSION_BEFORE');c.complete('native_version_calls');
 c.attempt('native_index_initializations','INDEX_BEFORE');c.complete('native_index_initializations');
 c.attempt('native_len_calls',null);c.complete('native_len_calls');
 for(let i=0;i<5183;i++){c.attempt('native_insertions','INSERT_BEFORE');c.complete('native_insertions');}
 c.attempt('native_len_calls',null);c.complete('native_len_calls');
 for(let i=0;i<16;i++){c.attempt('native_queries','QUERY_BEFORE');c.complete('native_queries');for(let j=0;j<10;j++)c.hit();rows.push({event:'QUERY_COMPLETE',monotonic_milliseconds:rows.length,counters:{...c.counters}});}
 c.terminal();rows.push({event:'COMPLETE',monotonic_milliseconds:rows.length,counters:{...c.counters}});
 fakeProgress=rows;assert.deepEqual(c.counters,m.EXPECTED);assert.equal(rows.length,5220);assert(Buffer.byteLength(rows.map(r=>JSON.stringify(r)+'\n').join(''))<=4194304);
 fails(()=>c.attempt('native_queries','QUERY_BEFORE'),'NATIVE_OPERATION_CAP_OR_INFLIGHT');fails(()=>c.hit(),'NATIVE_HIT_VALIDATION_CAP');
 const ec=Object.fromEntries([...new Set(rows.map(r=>r.event))].map(e=>[e,rows.filter(r=>r.event===e).length]));
 assert.equal(ec.INSERT_BEFORE,5183);assert.equal(ec.QUERY_BEFORE,16);assert.equal(ec.QUERY_COMPLETE,16);});
check(()=>{const c=m.makeCounters(()=>{});fails(()=>c.terminal(),'NATIVE_EXACT_TERMINAL_COUNTERS');});
check(()=>assert(!Object.keys(require.cache).some(x=>/ruvector\.node|\/node_modules\/|onnxruntime|transformers/.test(x))));
if(process.argv[2])require('node:fs').writeFileSync(process.argv[2],fakeProgress.map(r=>JSON.stringify(r)+'\n').join(''),{flag:'wx'});
console.log(JSON.stringify({inert_tests_passed:tests,native_model_dataset_imports:0,actual_native_calls:0,scope:'Pure encoding, tie ordering and accounting unit tests; no benchmark execution.'}));
