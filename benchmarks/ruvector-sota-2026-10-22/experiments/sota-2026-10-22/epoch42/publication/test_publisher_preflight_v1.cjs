// Pure in-memory publisher preflight test. No tool, filesystem mutation, or network.
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const source = fs.readFileSync(path.join(__dirname, '../preparation/reviewed_publish_phase.js'), 'utf8');
const S = '/tmp/ruvector-sota-2026-10-22/epoch42-222874558c0b';
const sha = c => c.repeat(40);
const scope = 'benchmarks/ruvector-sota-2026-10-22/';
const parent = sha('1'), root = sha('2'), bench = sha('3'), scoped = sha('4');
const leaf = {path:'ACTIVE_RUN.json', mode:'100644', type:'blob', sha:sha('5'), size:2};
const rootTree = {truncated:false,tree:[{path:'benchmarks',mode:'040000',type:'tree',sha:bench},{path:'stable',mode:'100644',type:'blob',sha:sha('6')}]};
const benchTree = {truncated:false,tree:[{path:'ruvector-sota-2026-10-22',mode:'040000',type:'tree',sha:scoped}]};
const basePlan = {epoch:42,kind:'REAL_CONTRACTNLI_MULTI_HYPOTHESIS_CONTEXT_DEV_PILOT',source_checkpoint:'222874558c0b696f92824e5fce3775494877f821',publication_parent:parent,publication_stage_paths:{source:S+'/stage-source'}};
const active = {run_id:'epoch42-222874558c0b',work_active:true,native_allowed:0};
const cont = {active_run:active};
async function run(missing) {
 let mutations=0;
 const reads=[];
 const meta = {source_plan_sha256:'plan',stage:'source',scope,publication_parent:parent,read_only_main_observation:sha('7'),prior_controls_name:'controls-lease',CAS_guards:{force:false,expected_branch_sha:parent,expected_root_tree:root,expected_benchmarks_tree:bench,expected_scope_tree:scoped},expected_leaves:{file:'expected-leaves.json',bytes:11,sha256:'leaves',count:1},expected_Git_leaves:1,large_blob_requests:[{file:'transport/blob-000.json',bytes:9,sha256:'blob',expected_blob_sha1:sha('5')}],create_tree_groups:[]};
 const proof={checks_passed:true,stage:S+'/stage-source',manifest_sha256:'meta',manifest_bytes:10};
 const jsons = new Map([[S+'/project/experiments/sota-2026-10-22/epoch42/plan.json',basePlan],[S+'/stage-source/metadata.json',meta],[S+'/stage-source/expected-leaves.json',{scope,files:[leaf]}],['proof',proof],[S+'/controls-lease/ACTIVE_RUN.json',active],[S+'/controls-lease/CONTINUATION.json',cont],[S+'/baseline-0.json',rootTree],[S+'/baseline-1.json',benchTree]]);
 jsons.delete(S+'/'+missing);
 const context={S,repo:'ruvnet/RuVector',branch:'benchmarks/ruvector-sota-2026-10-22',
  read:async p=>{reads.push(p);if(!jsons.has(p))throw Error('missing baseline fixture '+p);return jsons.get(p);},
  readRequestMeta:async p=>p.endsWith('/plan.json')?{sha256:'plan'}:p.endsWith('/metadata.json')?{sha256:'meta',bytes:10}:{sha256:'leaves',bytes:11},
  get:async url=>{
   if(url.includes('/git/ref/heads/'))return{object:{sha:url.endsWith('/main')?sha('7'):parent}};
   if(url.includes('/git/commits/'))return{tree:{sha:root}};
   if(url.endsWith('/git/trees/'+root))return rootTree;
   if(url.endsWith('/git/trees/'+bench))return benchTree;
   if(url.endsWith('/ACTIVE_RUN.json'))return active;
   if(url.endsWith('/CONTINUATION.json'))return cont;
   throw Error('Unexpected stub read '+url);
  },mutate:async()=>{mutations++;throw Error('unexpected mutation');}};
 vm.createContext(context);vm.runInContext(source+'\nthis.invoke=publishPhase;',context);
 await assert.rejects(context.invoke('source','proof'),/missing baseline fixture/);
 assert.equal(mutations,0,'missing baseline must fail before all Git object writes');
 assert(reads.includes(S+'/'+missing));
}
async function mutationGuards() {
 let mutations=0;
 const context={mutate:async()=>{mutations++;throw Error('UNCERTAIN_EXTERNAL_MUTATION_STOP');}};
 vm.createContext(context);vm.runInContext(source+'\nthis.invokeMutation=publisherMutate;',context);
 const tool='mcp__codex_apps__github_update_ref';
 const good={repository_full_name:'ruvnet/RuVector',branch_name:'benchmarks/ruvector-sota-2026-10-22',force:false,expected_sha:parent,sha:root};
 const bad=[{...good,branch_name:'main'},{...good,nested:{branch:'refs/heads/main'}},{...good,branch_name:'other'},{...good,force:true},{...good,expected_sha:undefined},{...good,repository_full_name:'other/repo'}];
 for(const args of bad)await assert.rejects(context.invokeMutation('fixture',tool,args));
 await assert.rejects(context.invokeMutation('fixture','unapproved',good));
 assert.equal(mutations,0);
 await assert.rejects(context.invokeMutation('fixture',tool,good),/UNCERTAIN_EXTERNAL_MUTATION_STOP/);
 assert.equal(mutations,1,'one uncertain mutation must propagate; helper cannot retry');
}
(async()=>{await run('baseline-0.json');await run('baseline-1.json');await mutationGuards();process.stdout.write('10 publisher guard scenarios passed; 0 external calls, 1 in-memory uncertain mutation stub\n');})().catch(e=>{process.stderr.write(String(e.stack)+'\n');process.exitCode=1;});
