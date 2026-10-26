// Invented metadata and unavailable tool proxy. No native/model/scientific call.
const fs=require('fs'),vm=require('vm'),assert=require('assert'),path=require('path');
const source=fs.readFileSync(path.join(__dirname,'controller.js'),'utf8');
let toolCalls=0;
const tools=new Proxy({}, {get(){toolCalls++;throw Error('Actual tools forbidden in inert fixture');}});
const context=vm.createContext({tools});
vm.runInContext(source+'\nglobalThis.checkInert=checkLeaves48;',context);
const scope='1'.repeat(40),a={path:'a.txt',mode:'100644',type:'blob',sha:'2'.repeat(40),size:1},b={...a,path:'b.txt',sha:'3'.repeat(40)};
const expected={scope:'benchmarks/ruvector-sota-2026-10-22/',files:[a,b]};
assert.equal(context.checkInert({sha:scope,truncated:false,tree:[a,b]},expected,scope),2);
assert.throws(()=>context.checkInert({sha:scope,truncated:false,tree:[a,a]},expected,scope));
assert.throws(()=>context.checkInert({sha:'4'.repeat(40),truncated:false,tree:[a,b]},expected,scope));
assert.throws(()=>context.checkInert({sha:scope,truncated:true,tree:[a,b]},expected,scope));
assert.equal(toolCalls,0);
process.stdout.write(JSON.stringify({fixture_kind:'INVENTED_CONTROLLER_SCOPE_METADATA_ONLY',checks_passed:true,scenarios:4,actual_tool_calls:toolCalls,native_model_or_corpus_runs:0})+'\n');
