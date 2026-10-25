// Pure mocked transport exercise: no network, subprocess, models, or Git calls.
const fs = require('fs'), vm = require('vm'), assert = require('assert');
const template = fs.readFileSync(__dirname + '/preparation/reviewed_publish_phase.js', 'utf8');
const W = '/workspace/ruvector-epoch34-047dbc740dc2', stage = W + '/stages/source';
const source = '047dbc740dc2d4fdbdbad90ac167ebc64b31a49c', parent = '1'.repeat(40), root = '2'.repeat(40), bench = '3'.repeat(40), scope = '4'.repeat(40), next = '5'.repeat(40);
const branch = 'benchmarks/ruvector-sota-2026-10-22', active = {run_id:'epoch34-047dbc740dc2',work_active:true,native_allowed:0}, cont = {immutable_history:true};
const expected = {scope:branch+'/',files:['ACTIVE_RUN.json','CONTINUATION.json','CHECKPOINT_MANIFEST.json'].map(path => ({path,mode:'100644',type:'blob',sha:'6'.repeat(40),size:2}))};
const rootTree = {tree:[{path:'benchmarks',mode:'040000',type:'tree',sha:bench},{path:'README.md',mode:'100644',type:'blob',sha:'d'.repeat(40),size:1}]};
const benchTree = {tree:[{path:'ruvector-sota-2026-10-22',mode:'040000',type:'tree',sha:scope}]};
const meta = {source_plan_sha256:'a'.repeat(64),stage:'source',scope:branch+'/',publication_parent:parent,prior_controls_name:'controls-lease',read_only_main_observation:'7'.repeat(40),CAS_guards:{force:false,expected_branch_sha:parent,expected_root_tree:root,expected_benchmarks_tree:bench,expected_scope_tree:scope},expected_Git_leaves:3,expected_leaves:{file:'expected-leaves.json',bytes:100,sha256:'c'.repeat(64),count:3},large_blob_requests:[],create_tree_groups:[]};
let head=parent, mainReads=0;const calls=[];
const ctx = {S:W,repo:'ruvnet/RuVector',branch,read:async path => {
 if(path.endsWith('/plan.json'))return {epoch:34,kind:'REAL_NATIVE_LEXICAL_ANCHOR_NATIVE_COMPLEMENT_NLI_DIAGNOSTIC',source_checkpoint:source,publication_parent:parent,publication_stage_paths:{source:stage}};
 if(path==='/proof.json')return {checks_passed:true,stage,manifest_sha256:'b'.repeat(64),manifest_bytes:200};
 if(path===stage+'/metadata.json')return meta;
 if(path===stage+'/expected-leaves.json')return expected;
 if(path.endsWith('/ACTIVE_RUN.json'))return active;
 if(path.endsWith('/CONTINUATION.json'))return cont;
 if(path.endsWith('/baseline-0.json'))return rootTree;
 if(path.endsWith('/baseline-1.json'))return benchTree;
 throw Error('unexpected read '+path);
},readRequestMeta:async path=> path.endsWith('/plan.json')?{sha256:'a'.repeat(64),bytes:50}:path.endsWith('/metadata.json')?{sha256:'b'.repeat(64),bytes:200}:{sha256:'c'.repeat(64),bytes:100},
 get:async url=> {
 if(url.includes('/git/ref/heads/main'))return {object:{sha: ['8','9','a'][mainReads++].repeat(40)}};
 if(url.includes('/git/ref/heads/'+branch))return {object:{sha:head}};
 if(url.includes('raw.githubusercontent.com'))return url.endsWith('/ACTIVE_RUN.json')?active:cont;
 if(url.endsWith('/git/commits/'+parent))return {tree:{sha:root}};
 if(url.endsWith('/git/commits/'+next))return {parents:[{sha:parent}],tree:{sha:root}};
 if(url.endsWith('/git/trees/'+root))return rootTree;
 if(url.endsWith('/git/trees/'+bench))return benchTree;
 if(url.endsWith('/git/trees/'+scope+'?recursive=1'))return {tree:expected.files};
 throw Error('unexpected get '+url);
 },mutate:async(id,tool,args)=>{calls.push({id,tool,args});if(tool.endsWith('github_create_commit'))return {sha:next};if(tool.endsWith('github_update_ref')){head=args.sha;return {ok:true};}throw Error('unexpected mocked mutation');}};
vm.createContext(ctx);vm.runInContext(template+'\nthis.run=publishPhase;this.checkedMutate=publisherMutate;',ctx);
(async()=> {
 const result=await ctx.run('source','/proof.json');assert.strictEqual(result.commit,next);assert.strictEqual(mainReads,3);assert.strictEqual(result.read_only_main_observations.before,'8'.repeat(40));assert.strictEqual(result.read_only_main_observations.after,'a'.repeat(40));
 assert.strictEqual(calls.length,2);assert.strictEqual(calls[1].args.branch_name,branch);assert.strictEqual(calls[1].args.expected_sha,parent);assert.strictEqual(calls[1].args.force,false);
 await assert.rejects(ctx.checkedMutate('bad','mcp__codex_apps__github_update_ref',{repository_full_name:'ruvnet/RuVector',branch_name:'main',expected_sha:parent,force:false,sha:next}),/main is prohibited/);
 await assert.rejects(ctx.checkedMutate('bad','mcp__codex_apps__github_update_ref',{repository_full_name:'ruvnet/RuVector',branch_name:branch,expected_sha:parent,force:true,sha:next}),/compare-and-set/);
 assert.strictEqual(calls.length,2);console.log(JSON.stringify({mocked_main_advance_publication_passed:true,main_mutation_rejected:true,force_update_rejected:true,actual_Git_or_network_calls:0}));
})().catch(e=>{console.error(e);process.exitCode=1;});
