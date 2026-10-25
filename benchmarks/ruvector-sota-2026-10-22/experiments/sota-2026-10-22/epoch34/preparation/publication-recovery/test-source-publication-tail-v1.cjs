// Entirely mocked transport/filesystem. No Git, shell, native or model calls.
const fs=require('fs'),vm=require('vm'),assert=require('assert'),crypto=require('crypto');
const W='/workspace/ruvector-epoch34-047dbc740dc2',OWN='/workspace/ruvector-e34-publication-impl';
const helper=fs.readFileSync(OWN+'/resume-source-publication-tail-v1.js','utf8');
const controller=fs.readFileSync(W+'/controller.js','utf8');
const publisher=fs.readFileSync(W+'/project/experiments/sota-2026-10-22/epoch34/preparation/reviewed_publish_phase.js','utf8');
const mutateText=controller.slice(controller.indexOf('const mutate=')+'const mutate='.length,controller.indexOf('; const readRequestMeta=',controller.indexOf('const mutate=')));
const clone=x=>JSON.parse(JSON.stringify(x)),sha=b=>crypto.createHash('sha256').update(b).digest('hex');
const fileRef=(p,b=fs.readFileSync(p))=>({path:p,bytes:b.length,sha256:sha(b)});
const getJSON=p=>JSON.parse(fs.readFileSync(p,'utf8'));
const stage=getJSON(W+'/stage-source/metadata.json'),expected=getJSON(W+'/stage-source/expected-leaves.json');
const baseRoot=getJSON(W+'/baseline-0.json'),baseBench=getJSON(W+'/baseline-1.json'),newRoot=getJSON(W+'/source-created-root.json'),newBench=getJSON(W+'/source-created-bench.json'),newScope=getJSON(W+'/source-created-scope.json');
const parent='eafd332309fef5873086cf66c911b1787c320820',next='b'.repeat(40),branch='benchmarks/ruvector-sota-2026-10-22';

async function exercise(options={}){
 const memory=new Map(),calls=[],logs=[],reserved=new Set(),gets=[];let head=parent,headReads=0,mainReads=0,intents=0,preflights=0;
 const ref=p=>fileRef(p,memory.has(p)?Buffer.from(memory.get(p)):fs.readFileSync(p));
 const approve={checks_passed:true,helper:ref(OWN+'/resume-source-publication-tail-v1.js'),local_validator:ref(OWN+'/verify-source-publication-tail-inputs-v1.py')};
 memory.set('/workspace/ruvector-e34-independent-audit/source-publication-tail-independent-v1.json',JSON.stringify(approve)+'\n');
 const preflight={checks_passed:true,parent,expected_Git_leaves:5096,all195source_pins_unchanged:true,CP_rows_verified:5022,WAL:{WAL_rows:40,successful_pairs:20,uncertain_mutations:0},guardian:{held:true}};
 function shellCode(cmd){let s=cmd.slice('python3 -c '.length);assert(s.startsWith("'")&&s.endsWith("'"));return s.slice(1,-1).replaceAll("'\\''", "'");}
 const ctx={S:W,repo:'ruvnet/RuVector',branch,q:x=>"'"+x.replaceAll("'","'\\''")+"'",un:x=>x,
 read:async p=>{
  if(p===OWN.replace('ruvector-e34-publication-impl','ruvector-e34-independent-audit')+'/source-publication-tail-independent-v1.json')return options.badApproval?{...approve,checks_passed:false}:approve;
  if(memory.has(p))return JSON.parse(memory.get(p));return getJSON(p);
 },readText:async p=>fs.readFileSync(p,'utf8'),readRequestMeta:async p=>options.badController&&p===W+'/controller.js'?{...ref(p),sha256:'0'.repeat(64)}:ref(p),
 sh:async cmd=>{
  if(cmd.includes('verify-source-publication-tail-inputs-v1.py')&&cmd.endsWith(' preflight')){preflights++;if(options.existingIntent)throw Error('Tail already attempted');return JSON.stringify(options.badWAL?{...preflight,WAL:{...preflight.WAL,successful_pairs:19}}:preflight);}
  if(cmd.includes('verify-source-publication-tail-inputs-v1.py')&&cmd.includes(' intent --observations ')){intents++;assert.strictEqual(intents,1);return JSON.stringify({intent:{path:W+'/source-publication-tail-intent-v1.json',bytes:100,sha256:'a'.repeat(64)},preflight});}
  if(cmd.includes('verify-source-publication-tail-inputs-v1.py')&&cmd.includes(' postflight --commit '))return JSON.stringify({WAL_rows:44,successful_pairs:22,prior40rows_unchanged:true,uncertain_mutations:0});
  if(cmd.includes('/mutation_guard.py')&&cmd.includes(' reserve --id ')){
   const id=cmd.match(/--id '([^']+)'/)[1];assert(!reserved.has(id));reserved.add(id);memory.set(W+'/mutation-requests/'+id+'.json','');return '{}';
  }
  if(cmd.startsWith('python3 -c ')){
   const code=shellCode(cmd);
   if(code.startsWith('import base64;')){
    const literal=code.slice(code.indexOf('base64.b64encode(')+'base64.b64encode('.length,code.indexOf('.encode()).decode())'));
    const text=JSON.parse(literal),o=JSON.parse(text);assert.strictEqual(o.actual_parent_head,parent);assert.strictEqual(o.full_tuples_verified,5096);return Buffer.from(text).toString('base64');
   }
   const path=JSON.parse(code.match(/TARGET_PATH = ("(?:\\.|[^"\\])*")/)[1]);const body=JSON.parse(code.match(/BODY_TEXT = ("(?:\\.|[^"\\])*")/)[1]);assert(!memory.has(path));memory.set(path,body);return JSON.stringify(ref(path));
  }
  throw Error('Unexpected mocked shell '+cmd);
 },log:async(...args)=>logs.push(args),
 get:async url=>{
  gets.push(url);
  if(url.includes('/git/ref/heads/main'))return{object:{sha:(String((++mainReads)%10)).repeat(40)}};
  if(url.includes('/git/ref/heads/'+branch)){
   headReads++;if(options.driftBeforeIntent&&headReads===2)return{object:{sha:'0'.repeat(40)}};
   if(options.driftBeforeRef&&headReads===3)return{object:{sha:'0'.repeat(40)}};return{object:{sha:head}};
  }
  if(url.endsWith('/git/commits/'+parent))return{tree:{sha:baseRoot.sha},parents:[{sha:'047dbc740dc2d4fdbdbad90ac167ebc64b31a49c'}]};
  if(url.endsWith('/git/commits/'+next))return{tree:{sha:options.badCreatedCommit?'0'.repeat(40):newRoot.sha},parents:[{sha:parent}]};
  for(const t of[baseRoot,baseBench,newRoot,newBench])if(url.endsWith('/git/trees/'+t.sha))return clone(t);
  if(url.endsWith('/git/trees/'+newScope.sha+'?recursive=1')){const t=clone(newScope);if(options.badTuple)t.tree.find(r=>r.type==='blob').sha='0'.repeat(40);return t;}
  throw Error('Unexpected mocked GET '+url);
 },tools:{apply_patch:async patch=>{
  const path=patch.match(/\*\*\* Add File: ([^\n]+)/)[1];const b=patch.split('\n').filter(x=>x.startsWith('+')).map(x=>x.slice(1)).join('\n')+'\n';assert(memory.has(path));memory.set(path,b);return{};
 },mcp__codex_apps__github_create_commit:async args=>{calls.push({tool:'commit',args});if(options.commitFailure)throw Error('Mocked certain commit error');return{sha:next};},mcp__codex_apps__github_update_ref:async args=>{calls.push({tool:'ref',args});assert.strictEqual(args.expected_sha,head);assert.strictEqual(args.force,false);head=args.sha;return{success:true};}}};
 vm.createContext(ctx);vm.runInContext('const mutate='+mutateText+';\n'+publisher+'\n'+(options.badTupleKeys?"publisherTupleKeys[0]='altered';\n":'')+helper+'\nthis.run=resumeSourcePublicationTail;this.check=sourceTailCheckMutation;',ctx);
 let result,error;try{result=await ctx.run();}catch(e){error=e;}
 return{result,error,calls,logs,reserved,memory,gets,intents,preflights,head,run:ctx.run,check:ctx.check};
}

(async()=>{
 let tests=0;
 const good=await exercise();assert.ifError(good.error);assert.strictEqual(good.result.commit,next);assert.strictEqual(good.result.leaves,5096);assert.deepStrictEqual(good.calls.map(x=>x.tool),['commit','ref']);assert.deepStrictEqual([...good.reserved],['e34-source-commit','e34-source-ref']);assert.strictEqual(good.logs.length,4);assert.strictEqual(good.intents,1);assert.strictEqual(good.head,next);assert.strictEqual(JSON.parse(good.memory.get(W+'/source-publication-tail-execution-v1.json')).blob_or_tree_replays,0);assert.strictEqual(JSON.parse(good.memory.get(W+'/publication-source.json')).commit,next);tests++;
 await assert.rejects(good.run(),/already invoked/);assert.strictEqual(good.calls.length,2);tests++;
 for(const option of['badApproval','badController','badWAL','existingIntent','badTupleKeys','badTuple','driftBeforeIntent']){
  const r=await exercise({[option]:true});assert(r.error,option);assert.strictEqual(r.calls.length,0,option);assert.strictEqual(r.intents,0,option);tests++;
 }
 for(const option of['badCreatedCommit','driftBeforeRef','commitFailure']){
  const r=await exercise({[option]:true});assert(r.error,option);assert.deepStrictEqual(r.calls.map(x=>x.tool),['commit']);assert.strictEqual(r.intents,1);assert.strictEqual(r.head,parent);assert.strictEqual(JSON.parse(r.memory.get(W+'/source-publication-tail-execution-v1.json')).further_tail_attempts,0);tests++;
 }
 const commitArgs={repository_full_name:'ruvnet/RuVector',parent_sha:parent,tree_sha:newRoot.sha,message:'benchmarks: freeze epoch34 lexical-anchor native-complement NLI source and engineering-gated DEV roles'};
 for(const tool of['mcp__codex_apps__github_create_blob','mcp__codex_apps__github_create_tree']){assert.throws(()=>good.check(0,'e34-source-commit',tool,commitArgs,null));tests++;}
 assert.throws(()=>good.check(0,'e34-source-commit','mcp__codex_apps__github_create_commit',{...commitArgs,tree_sha:baseRoot.sha},null));tests++;
 const refArgs={repository_full_name:'ruvnet/RuVector',branch_name:branch,expected_sha:parent,force:false,sha:next};
 for(const bad of[{...refArgs,force:true},{...refArgs,branch_name:'main'},{...refArgs,expected_sha:'0'.repeat(40)}]){assert.throws(()=>good.check(1,'e34-source-ref','mcp__codex_apps__github_update_ref',bad,next));tests++;}
 assert.throws(()=>good.check(2,'e34-source-ref','mcp__codex_apps__github_update_ref',refArgs,next));tests++;
 console.log(JSON.stringify({mocked_tail_checks_passed:tests,success_mutations_exactly:['e34-source-commit','e34-source-ref'],blob_tree_full_publisher_replays:0,actual_Git_shell_model_native_calls:0}));
})().catch(e=>{console.error(e);process.exitCode=1;});
