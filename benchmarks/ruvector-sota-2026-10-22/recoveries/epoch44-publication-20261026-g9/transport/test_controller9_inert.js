// Actual controller mutate(), fake tool/guard only. No network or real guard main.
const fs=require('fs'),os=require('os'),path=require('path'),vm=require('vm'),cp=require('child_process'),assert=require('assert');
const here=__dirname;
(async()=>{
 for(const scenario of ['valid-own-intent','bad-ACK','owner-loss']){
  const temp=fs.mkdtempSync(path.join(os.tmpdir(),'e44-recovery-inert-')),scope=temp+'/scope';fs.mkdirSync(scope);fs.mkdirSync(scope+'/requests');fs.mkdirSync(scope+'/helpers');fs.copyFileSync(here+'/future_response_protocol.py',scope+'/helpers/future_response_protocol.py');
  const id='e44-recovery-g9-fixture',kind='mcp__codex_apps__github_create_blob',events=[];let rows=[{id:'earlier-new-recovery',phase:'intent'},{id:'earlier-new-recovery',phase:'response',payload:{ok:true}}];
  const reply={structuredContent:scenario==='bad-ACK'?{wrong:true}:{sha:'a'.repeat(40)},content:[]};
  const quoted=(cmd,flag)=>{const m=cmd.match(new RegExp(flag+" '([^']*)'"));return m&&m[1];};
  const tools={exec_command:async({cmd})=>{
   if(cmd.includes('/helpers/mutation_guard9.py')){
    const mode=cmd.match(/mutation_guard9.py' (reserve|intent|response|guard)/)[1];
    if(mode==='reserve'){assert.equal(rows.length%2,0);fs.writeFileSync(scope+'/requests/'+id+'.json',JSON.stringify({repository_full_name:'ruvnet/RuVector',encoding:'utf-8',content:'invented'}),{flag:'wx'});}
    if(mode==='intent'){assert.equal(rows.length%2,0);rows.push({id,phase:'intent',kind});}
    if(mode==='response'){
     events.push('guard-owner-reentry');assert(fs.existsSync(scope+'/requests/'+id+'.raw-tool-return.json'));
     if(scenario==='owner-loss')return {exit_code:1,output:'invented owner loss'};
     const payload=JSON.parse(Buffer.from(quoted(cmd,'--payload'),'base64').toString());assert.equal(rows.at(-1).id,id);assert.equal(rows.at(-1).phase,'intent');assert.equal(rows.length%2,1);events.push('ACK-parse');
     if(scenario==='bad-ACK')return {exit_code:1,output:'invented invalid ACK'};
     assert.equal(payload.result.sha,'a'.repeat(40));rows.push({id,phase:'response',payload});
    }
    return {exit_code:0,output:'{}'};
   }
   if(cmd.includes('capture_raw_reply'))events.push('raw-persist');
   const r=cp.spawnSync('/bin/bash',['-lc',cmd],{encoding:'utf8'});return {exit_code:r.status,output:r.stdout+r.stderr};
  },[kind]:async()=>{events.push('tool-return');return reply;}};
  let code=fs.readFileSync(here+'/controller9.js','utf8').replace("const S='/tmp/ruvector-sota-2026-10-22/epoch44-02ed8c956725/publication-recovery9'",'const S='+JSON.stringify(scope));
  code+='\nglobalThis.fixture=async()=>{publicationPhase="recovery";approvedPath="invented";approvedSHA="0".repeat(64);operationalPath="invented";operationalSHA="1".repeat(64);return mutate('+JSON.stringify(id)+','+JSON.stringify(kind)+');};';
  const context={tools};vm.createContext(context);vm.runInContext(code,context);let failed=false;try{await context.fixture();}catch(e){failed=true;}
  assert.equal(failed,scenario!=='valid-own-intent');assert.deepEqual(JSON.parse(fs.readFileSync(scope+'/requests/'+id+'.raw-tool-return.json','utf8')),reply);assert(events.indexOf('raw-persist')>events.indexOf('tool-return'));assert(events.indexOf('raw-persist')<events.indexOf('guard-owner-reentry'));assert.equal(rows.length,scenario==='valid-own-intent'?4:3);
  if(scenario!=='owner-loss')assert(events.indexOf('ACK-parse')>events.indexOf('raw-persist'));
  fs.rmSync(temp,{recursive:true});
 }
 process.stdout.write('PASS 3 actual-controller inert cases; fake tool/guard only\n');
})().catch(e=>{process.stderr.write(e.stack+'\n');process.exitCode=1;});
