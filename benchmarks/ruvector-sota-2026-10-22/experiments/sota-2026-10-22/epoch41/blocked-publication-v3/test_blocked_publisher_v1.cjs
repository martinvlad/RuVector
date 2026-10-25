'use strict';
const fs=require('fs'),vm=require('vm'),assert=require('assert');
const code=fs.readFileSync(__dirname+'/publish_blocked_final_v1.js','utf8');
const S='/tmp/ruvector-sota-2026-10-22/epoch41-7a40daab6ad7';
const base={epoch:41,kind:'REAL_CONTRACTNLI_MULTI_HYPOTHESIS_CONTEXT_DEV_PILOT',status:'BLOCKED_PRE_DATA_ADMISSION',source_checkpoint:'7a40daab6ad7caf9310f678813bfef42f907bd17',publication_parent:'fa7fb072d4461b4b91f65dc6ed5622090d3fc933',publication_stage_path:S+'/stage-final'};
async function refusal(change){
 let mutations=0;let gets=0;const input=structuredClone(base),meta={stage:'blocked-final',scope:'benchmarks/ruvector-sota-2026-10-22/',blocked_inputs_sha256:'fixture-pin',publication_parent:base.publication_parent,read_only_main_observation:'a'.repeat(40),CAS_guards:{force:false,expected_branch_sha:base.publication_parent}},proof={checks_passed:true,stage:S+'/stage-final',manifest_sha256:'fixture-pin',manifest_bytes:1};
 const state={S,repo:'ruvnet/RuVector',branch:'benchmarks/ruvector-sota-2026-10-22',input,meta,proof};change(state);
 const context={S:state.S,repo:state.repo,branch:state.branch,read:async p=>p.endsWith('BLOCKED_INPUTS.json')?input:p.endsWith('metadata.json')?meta:proof,readRequestMeta:async()=>({sha256:'fixture-pin',bytes:1}),get:async()=>{gets++;throw Error('unexpected connected read');},mutate:async()=>{mutations++;throw Error('mutation prohibited');}};
 vm.createContext(context);vm.runInContext(code+'\nglobalThis.invoke=publishBlockedFinal;',context);
 await assert.rejects(context.invoke('/fixture-proof.json'));assert.equal(mutations,0);assert.equal(gets,0);
}
(async()=>{const cases=[s=>s.S='/wrong',s=>s.repo='wrong/repo',s=>s.branch='main',s=>s.input.epoch=40,s=>s.input.status='ACCEPTED_DEV_PILOT_ONLY',s=>s.input.source_checkpoint='a'.repeat(40),s=>s.input.publication_parent='a'.repeat(40),s=>s.input.publication_stage_path=S+'/other',s=>s.proof.checks_passed=false,s=>s.proof.manifest_sha256='changed',s=>s.meta.CAS_guards.force=true,s=>s.meta.CAS_guards.expected_branch_sha='b'.repeat(40),s=>s.meta.publication_parent='c'.repeat(40),s=>s.meta.blocked_inputs_sha256='changed'];for(const c of cases)await refusal(c);console.log(JSON.stringify({disjoint_publisher_preflight_cases:cases.length,passed:true,external_GETs:0,external_mutations:0}));})().catch(e=>{console.error(e);process.exitCode=1;});
