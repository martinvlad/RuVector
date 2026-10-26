'use strict';
// Invented vector metadata only; never requires or loads native RuVector.
const assert=require('node:assert/strict'),crypto=require('node:crypto');
const h=require('./native_helper.cjs');
const hash=b=>crypto.createHash('sha256').update(b).digest('hex');
const bytes=Buffer.alloc(1536);
for(let i=0;i<384;i++)bytes.writeFloatLE(1/Math.sqrt(384),i*4);
const block={encoding:'base64',dtype:'float32le',shape:[1,384],bytes:1536,
 sha256:hash(bytes),data_base64:bytes.toString('base64')};
const vectors=h.decode(block);assert.equal(vectors.length,1);
assert.equal(h.vectorBytes(vectors[0]).equals(bytes),true);
const compact=h.compact({id:'0',score:.5,vector:vectors[0]},vectors);
assert.equal(compact.vector_receipt.sha256,hash(bytes));assert.equal('vector' in compact,false);
assert.throws(()=>h.decode({...block,shape:[0,384]}));
assert.throws(()=>h.decode({...block,data_base64:block.data_base64+'AA=='}));
assert.throws(()=>h.compact({id:'00',score:.5,vector:vectors[0]},vectors));
assert.throws(()=>h.compact({id:'0',score:.5,vector:vectors[0],metadata:{}},vectors));
const changed=new Float32Array(vectors[0]);changed[0]+=1;
assert.throws(()=>h.compact({id:'0',score:.5,vector:changed},vectors));
assert.equal(Object.keys(require.cache).filter(x=>x.endsWith('.node')).length,0);
console.log(JSON.stringify({invented_metadata_assertions_passed:9,native_modules_loaded:0,
 model_or_tokenizer_initializations:0,benchmark_cases:0}));
