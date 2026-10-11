import test from 'node:test';
import assert from 'node:assert/strict';
import { mkdtemp, writeFile, rm } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { fileURLToPath } from 'node:url';
import { Client } from '@modelcontextprotocol/sdk/client/index.js';
import { StdioClientTransport } from '@modelcontextprotocol/sdk/client/stdio.js';
test('MCP stdio handshake, tool discovery, query and bounded schema',{timeout:15000},async()=>{
  const dir=await mkdtemp(join(tmpdir(),'constellation-mcp-'));
  const report=join(dir,'report.json');
  await writeFile(report,JSON.stringify({schemaVersion:1,observedAt:'fixture',coverage:{},packages:[{name:'ruvector'}],graph:{edges:[],runtimeCycles:[]},plan:{policy:'fixture',queue:[]}}));
  const client=new Client({name:'test',version:'1.0.0'});
  const transport=new StdioClientTransport({command:process.execPath,args:[fileURLToPath(new URL('../src/cli.mjs',import.meta.url)),'mcp',report],stderr:'pipe'});
  try {
    await client.connect(transport);
    const list=await client.listTools();assert.equal(list.tools.length,3);assert(list.tools.every(t=>t.annotations.readOnlyHint));
    const result=await client.callTool({name:'constellation_packages',arguments:{query:'ruvector',limit:1}});
    assert.equal(JSON.parse(result.content[0].text).packages[0].name,'ruvector');
    const invalid=await client.callTool({name:'constellation_packages',arguments:{limit:10000}});assert.equal(invalid.isError,true);
  } finally {await client.close();await rm(dir,{recursive:true,force:true});}
});
