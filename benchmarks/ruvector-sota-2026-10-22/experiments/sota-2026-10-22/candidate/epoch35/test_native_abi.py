"""Pure lossless ABI fixture; exports only, no native addon or helper main invocation."""
import json
from pathlib import Path
import subprocess
import unittest

HERE=Path(__file__).resolve().parent

class NativeABIFixtures(unittest.TestCase):
    def test_twelve_identity_bundle_lossless_float32_and_rejected_wrong_role(self):
        script=r'''
const assert=require('node:assert/strict'),crypto=require('node:crypto');
const helper=require(process.argv[1]);
const bytes=Buffer.alloc(1536);bytes.writeFloatLE(1,0);
const block={encoding:'base64',dtype:'float32le',shape:[1,384],bytes:1536,data_base64:bytes.toString('base64'),sha256:crypto.createHash('sha256').update(bytes).digest('hex')};
assert.deepEqual(helper.vectorBytes(helper.decode(block)[0]),bytes);
const bundle={schema_version:3,epoch:35,phase:'engineering',role:'engineering',kind:'ENGINEERING_QUANTITATIVE_SOURCE_SCOPE_STRESS',vector_encoding:'base64_float32le_c_order',metadata_policy:'insert id and vector only; metadata absent',documents:Array.from({length:12},(_,i)=>({document_id:String(-35001-i),vectors:block,query_vectors:block,queries:[{id:'epoch35:cc0:numeric-scope:'+String(i+1).padStart(2,'0')+'::retrieval:original'}]}))};
assert.equal(helper.validateBundle(bundle,'engineering'),true);
assert.throws(()=>helper.validateBundle({...bundle,phase:'dev'},'engineering'));
assert.throws(()=>helper.validateBundle(bundle,'dev'));
const duplicate=JSON.parse(JSON.stringify(bundle));duplicate.documents[1].document_id=duplicate.documents[0].document_id;assert.throws(()=>helper.validateBundle(duplicate,'engineering'));
assert.throws(()=>helper.decode({...block,sha256:'0'.repeat(64)}));
assert.throws(()=>helper.decode({...block,data_base64:block.data_base64+'\n'}));
assert.equal(Object.keys(require.cache).some(p=>p.endsWith('.node')),false);
process.stdout.write(JSON.stringify({pure_fixture:true,checks:7,actual_native_addon_loads:0,actual_model_tokenizer_calls:0}));
'''
        result=subprocess.run(['node','-e',script,str(HERE/'native_helper.cjs')],capture_output=True,text=True,check=True)
        receipt=json.loads(result.stdout);self.assertTrue(receipt['pure_fixture']);self.assertEqual(receipt['actual_native_addon_loads'],0);self.assertEqual(receipt['checks'],7)

if __name__=='__main__':unittest.main(verbosity=2)
