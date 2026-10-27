// No actual wait, shell, Git, native, model or science call. Mocked metadata only.
const fs=require('fs'),vm=require('vm'),assert=require('assert'),path=require('path');
const source=fs.readFileSync(path.join(__dirname,'recovery-v2/controller.js'),'utf8');
async function scenario(expired=false){
  const events=[],request=JSON.stringify({repository_full_name:'ruvnet/RuVector',encoding:'utf-8',content:'INVENTED_METADATA'});
  let calls=0;
  const tools={exec_command:async({cmd})=>{
    const mode=['reserve','intent','owner','capture-raw','response'].find(k=>cmd.includes("'"+k+"' --phase"));
    if(mode){events.push([mode]);if(mode==='owner'&&expired)return {exit_code:1,output:'INERT_OWNER_EXPIRED'};return {exit_code:0,output:mode==='response'?JSON.stringify({ack_sha:'1'.repeat(40)}):'{}'};}
    if(cmd.includes('print(len(Path('))return {exit_code:0,output:String(request.length)};
    if(cmd.includes('read_text()['))return {exit_code:0,output:request};
    if(cmd.includes('base64.b64encode'))return {exit_code:0,output:'aW5lcnQ='};
    throw Error('Unexpected inert metadata command');
  },mcp__codex_apps__github_create_blob:async args=>{calls++;events.push(['mock-mutation']);assert.equal(args.content,'INVENTED_METADATA');return {isError:false,structuredContent:{sha:'1'.repeat(40)}};}};
  const c=vm.createContext({tools,setTimeout:(callback,ms)=>{events.push(['delay',ms]);callback();}});
  vm.runInContext(source+`\nCONTEXT50={phase:'source',approval:'inert',approvalSHA:'inert'};globalThis.invoke=()=>mutate50({id:'e50-recovery-source-g15-blob-inert',kind:'mcp__codex_apps__github_create_blob'});`,c);
  if(expired){await assert.rejects(c.invoke(),/INERT_OWNER_EXPIRED/);assert.equal(calls,0);assert.deepEqual(events,[['delay',2000],['reserve'],['intent'],['owner']]);}
  else{await c.invoke();assert.equal(calls,1);assert.deepEqual(events,[['delay',2000],['reserve'],['intent'],['owner'],['mock-mutation'],['capture-raw'],['response']]);}
}
(async()=>{await scenario(false);await scenario(true);process.stdout.write(JSON.stringify({checks_passed:true,fixture_kind:'INVENTED_PACING_ORDER_AND_FRESH_OWNER_ONLY',scenarios:2,minimum_pre_mutation_delay_ms:2000,actual_tool_calls:0,mocked_mutations:1,actual_delay_ms:0})+'\n');})().catch(e=>{process.stderr.write(String(e));process.exitCode=1;});
