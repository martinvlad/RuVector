const pref='https://api.github.com/repos/'+repo,base='4d51073072c428b58685e5498337bfdece6aac9b',scopePrefix='benchmarks/ruvector-sota-2026-10-22/';
const approved={'CONTINUATION.json':'e3ece106c1f72c1ee32d1f8b696f4afd3859bbd45b06025674ef23c0d0592385','ACTIVE_RUN.json':'8ef63a878e0986dca49c90d02a67eaf5b06b79ef89e88ba38cd55251bdb1238c'};
const baseline=await read(S+'/actual-git-map.json'),br=await read(S+'/baseline-0.json'),bb=await read(S+'/baseline-1.json');
if(baseline.source_commit!==base||baseline.files.length!==5182||br.sha!=='ea34c8bed31dc30d4ff7f524f142f48165dd632f'||bb.sha!=='efdc4bdc561975c9ff25c49842fcc89675c123c3')throw Error('baseline drift');
if((await get(pref+'/git/ref/heads/'+branch)).object.sha!==base)throw Error('active branch advanced');
const sourceCommit=await get(pref+'/git/commits/'+base);if(sourceCommit.tree.sha!==br.sha)throw Error('parent mismatch');
const expected=new Map(baseline.files.map(x=>[x.path,Object.fromEntries(['path','mode','type','sha','size'].map(k=>[k,x[k]]))]));
const changed=[];
for(const name of ['CONTINUATION.json','ACTIVE_RUN.json']){
 const path=S+'/controls-lease/'+name,pin=await readRequestMeta(path);if(pin.sha256!==approved[name])throw Error('control drift');
 const body=await readText(path);const blob=await mutate('e35-planning-blob-'+name.replace('.json',''),'mcp__codex_apps__github_create_blob',{repository_full_name:repo,encoding:'utf-8',content:body});
 changed.push({path:scopePrefix+name,mode:'100644',type:'blob',sha:blob.sha});expected.set(name,{path:name,mode:'100644',type:'blob',sha:blob.sha,size:pin.bytes});
}
const created=await mutate('e35-planning-tree','mcp__codex_apps__github_create_tree',{repository_full_name:repo,base_tree_sha:br.sha,tree_elements:changed});
const root=await get(pref+'/git/trees/'+created.sha),benchSHA=root.tree.find(x=>x.path==='benchmarks').sha,benchTree=await get(pref+'/git/trees/'+benchSHA),scopeSHA=benchTree.tree.find(x=>x.path==='ruvector-sota-2026-10-22').sha;
for(const [actual,before,key,replacement]of[[root,br,'benchmarks',benchSHA],[benchTree,bb,'ruvector-sota-2026-10-22',scopeSHA]]){
 if(actual.truncated||actual.tree.length!==before.tree.length)throw Error('siblings length');
 for(const row of before.tree){const got=actual.tree.find(x=>x.path===row.path);if(!got||got.mode!==row.mode||got.type!==row.type||got.sha!==(row.path===key?replacement:row.sha))throw Error('sibling mutation');}
}
const full=await get(pref+'/git/trees/'+scopeSHA+'?recursive=1');if(full.truncated)throw Error('truncated');const leaves=full.tree.filter(x=>x.type!=='tree');if(leaves.length!==expected.size)throw Error('leaf count');
for(const leaf of leaves){const wanted=expected.get(leaf.path);if(!wanted||['path','mode','type','sha','size'].some(k=>leaf[k]!==wanted[k]))throw Error('tuple mismatch '+leaf.path);}
if((await get(pref+'/git/ref/heads/'+branch)).object.sha!==base)throw Error('late branch advanced');
const commit=await mutate('e35-planning-commit','mcp__codex_apps__github_create_commit',{repository_full_name:repo,parent_sha:base,tree_sha:created.sha,message:'benchmarks: reserve epoch35 numerical source-scope engineering study without benchmark exposure'});
const actual=await get(pref+'/git/commits/'+commit.sha);if(actual.parents.length!==1||actual.parents[0].sha!==base||actual.tree.sha!==created.sha)throw Error('commit mismatch');
await mutate('e35-planning-ref','mcp__codex_apps__github_update_ref',{repository_full_name:repo,branch_name:branch,expected_sha:base,force:false,sha:commit.sha});
if((await get(pref+'/git/ref/heads/'+branch)).object.sha!==commit.sha)throw Error('post ref mismatch');
const result={phase:'lease',commit:commit.sha,parent:base,root:created.sha,bench:benchSHA,scope:scopeSHA,leaves:leaves.length,verified_actual_full_tree:true,approved_control_sha256:approved};
await tools.apply_patch('*** Begin Patch\n*** Add File: '+S+'/publication-lease.json\n+'+JSON.stringify(result)+'\n*** End Patch');await readRequestMeta(S+'/publication-lease.json');text(result);
