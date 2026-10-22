"""Independent input/capacity/official-package checks; never initializes a model."""
from pathlib import Path
from datetime import datetime, timezone
import base64, hashlib, itertools, json, os, subprocess, tarfile
from tokenizers import Tokenizer

OUT = Path(__file__).resolve().parent
STUDY = OUT.parents[1]
PROJECT = STUDY/'epoch5/project'
S = PROJECT/'experiments/sota-2026-10-22'
def sha(p): return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def load(p): return json.loads(Path(p).read_text())
def rows(p): return [json.loads(x) for x in Path(p).read_text().splitlines()]
def canonical(x): return json.dumps(x,ensure_ascii=False,sort_keys=True,separators=(',',':'),allow_nan=False)
def norm(x): return ' '.join(x.casefold().split())
def save(name,obj):
    p=OUT/name
    with p.open('x') as f: json.dump(obj,f,indent=2,ensure_ascii=False,allow_nan=False);f.write('\n')
    print(name,sha(p))

data=STUDY/'legal-transfer/epoch5'
train=load(STUDY/'legal-transfer/epoch3/sources/original-train.json')
assert sha(STUDY/'legal-transfer/epoch3/sources/original-train.json')=='dbceb356cd6203b35b27be94a5fa85e499a81c34c42c89ad53060b39f0257ba5'
registry=load(data/'eligibility-manifest.json')
oldreg=load(STUDY/'legal-transfer/epoch4/eligibility-manifest.json')
assert registry['historical_exclusions']==oldreg['historical_exclusions']
assert registry['consumed_epoch3_dev']==oldreg['consumed_epoch3_dev']
dev3=rows(STUDY/'legal-transfer/epoch3/development24.jsonl')
dev4=rows(STUDY/'legal-transfer/epoch4/development24.jsonl')
ids3={x['provenance']['document_id'] for x in dev3}
ids4={x['provenance']['document_id'] for x in dev4}
assert set(registry['consumed_epoch3_dev']['document_ids'])==ids3
assert set(registry['consumed_epoch4_dev']['document_ids'])==ids4
excluded={x['id'] for x in registry['historical_exclusions']['excluded_documents']}
eligible={x['id'] for x in train['documents']}-excluded-ids3-ids4
assert len(excluded)==77 and len(ids3)==len(ids4)==8 and len(eligible)==330
assert eligible==set(registry['eligible_document_ids'])
draw=[]
for d in train['documents']:
    if d['id'] in eligible:
        textsha=hashlib.sha256(norm(d['text']).encode()).hexdigest()
        key=hashlib.sha256(f"ruvector-original-contractnli-epoch5-dev-v1|{d['id']}|{textsha}".encode()).hexdigest()
        draw.append((key,d))
selected=[d for _,d in sorted(draw,key=lambda z:z[0])[:8]]
records=rows(data/'development24.jsonl')
assert len(records)==24 and len({r['id'] for r in records})==24
hypotheses=['nda-17','nda-7','nda-3']; label={'Entailment':'Yes','Contradiction':'No','NotMentioned':'No'}
instruction='Determine whether the agreement entails the supplied hypothesis. Answer Yes only if entailed. Answer No if the hypothesis is contradicted or not mentioned.'
for i,d in enumerate(selected):
    for j,h in enumerate(hypotheses):
        r=records[i*3+j];hyp=train['labels'][h]['hypothesis']
        inp={'state':d['text'],'questions':{'decision':{'type':'choice','instructions':instruction,'criteria':{'Yes':hyp,'No':'The agreement does not establish the following: '+hyp}}}}
        assert r['id']==f"original-contractnli:train:epoch5:{d['id']}:{h}"
        assert r['input']==inp and r['input_sha256']==hashlib.sha256(canonical(inp).encode()).hexdigest()
        assert r['normalized_input_sha256']==hashlib.sha256(norm(canonical(inp)).encode()).hexdigest()
        assert r['source_group']==r['evaluation']['group']==f"original-contractnli:{d['id']}"
        original=d['annotation_sets'][0]['annotations'][h]['choice']
        assert r['evaluation']['original_threeway_label']==original and r['evaluation']['gold']==label[original]
        assert r['provenance']['normalized_document_sha256']==hashlib.sha256(norm(d['text']).encode()).hexdigest()
confirmation=rows(STUDY/'legal-transfer/epoch3/confirmation96.jsonl')
assert sha(STUDY/'legal-transfer/epoch3/confirmation96.jsonl')=='f01894b231b744c8297344615ce6037524b6eb0794c7548e931839d2936cd79f'
assert {r['source_group'] for r in records}.isdisjoint({r['source_group'] for r in dev3+dev4+confirmation})
assert {norm(r['input']['state']) for r in records}.isdisjoint({norm(r['input']['state']) for r in dev3+dev4+confirmation})
manifest=load(data/'source-manifest.json')
for p in manifest['files']:
    assert sha(data/p['path'])==p['sha256'] and (data/p['path']).stat().st_size==p['bytes']
save('data-independent-v1.json',{'at':datetime.now(timezone.utc).isoformat(),'passed':True,'DEV_sha256':sha(data/'development24.jsonl'),'data_contract_sha256':sha(data/'data-contract.json'),'source_manifest_sha256':sha(data/'source-manifest.json'),'counts':{'source':423,'historic_excluded':77,'prior_epoch3':8,'prior_epoch4':8,'eligible':330,'selected_docs':8,'queries':24},'document_ids':[d['id'] for d in selected],'checks':['text-only salted draw independently rebuilt','exact source hypotheses/text/threeway-to-binary gold/input hashes','all prior declared DEV excluded','source-group and normalized fulltext disjoint from old DEV/confirmation','six source pins verified'],'novelty_limit':'Historical77 novelty inherited from prior audited registry; public source and unknown pretrained-model overlap, not sealed.','native_calls':0,'model_calls':0})

# Independent raw tokenization only. No runtime/model class is imported.
nli_path=S/'candidate/epoch4/assets/nli-base/tokenizer.json'
bge_path=PROJECT/'models/bge-small-en-v1.5/tokenizer.json'
nli=Tokenizer.from_file(str(nli_path));nli.no_padding();nli.no_truncation()
bge=Tokenizer.from_file(str(bge_path));bge.no_padding();bge.no_truncation()
assert sha(nli_path)=='a86f883318afa11c8c10466f1bf4efaeb6ded28a52cbe57217a8fa0d0a2a87df'
assert sha(bge_path)=='d241a60d5e8f04cc1b2b3e9ef7a4921b27bf526d9f6050ab90f9267a1f9e5c66'
prefix=load(S/'candidate/epoch4/config.json')['query_prefix']
maxb=maxn=maxbytes=maxchunks=0;phase_stats={}
for phase,rr in [('development',records),('confirmation',confirmation)]:
    count=0;maxphase=0
    for r in rr:
        text=r['input']['state'];hyp=r['input']['questions']['decision']['criteria']['Yes']
        offsets=nli.encode(text,add_special_tokens=False).offsets
        spans=[]
        for start in range(0,len(offsets),160):
            end=min(start+192,len(offsets));spans.append((offsets[start][0],offsets[end-1][1]))
            if end==len(offsets):break
        assert 1<=len(spans)<=64
        maxchunks=max(maxchunks,len(spans))
        maxb=max(maxb,len(bge.encode(prefix+hyp).ids),*(len(bge.encode(text[a:b]).ids) for a,b in spans))
        choices=itertools.combinations(range(len(spans)),2) if len(spans)>1 else [(0,)]
        for ids in choices:
            merged=[]
            for a,b in sorted(spans[k] for k in ids):
                if merged and a<=merged[-1][1]:merged[-1]=(merged[-1][0],max(b,merged[-1][1]))
                else:merged.append((a,b))
            premise='\n\n'.join(text[a:b] for a,b in merged)
            size=len(nli.encode(premise,hyp).ids)
            count+=1;maxphase=max(maxphase,size);maxn=max(maxn,size);maxbytes=max(maxbytes,len(premise.encode()))
    phase_stats[phase]={'requests':len(rr),'all_possible_top2_contexts':count,'max_joint_NLI_tokens':maxphase}
assert maxb<=256 and maxn<=512 and maxbytes<=16384
save('all-context-capacity-independent-v1.json',{'at':datetime.now(timezone.utc).isoformat(),'passed':True,'phases':phase_stats,'max_NLI_pair_tokens':maxn,'max_BGE_sequence_tokens':maxb,'max_native104_context_bytes':maxbytes,'max_source_chunks':maxchunks,'DEV_sha256':sha(data/'development24.jsonl'),'confirmation_sha256':sha(STUDY/'legal-transfer/epoch3/confirmation96.jsonl'),'NLI_tokenizer_sha256':sha(nli_path),'BGE_tokenizer_sha256':sha(bge_path),'model_or_native_calls':0,'scope':'All possible top2sourceordermerged contexts. Rawtokenizer-only; no prediction or model initialization. Serialized full evidence retained, no clipping.'})

specpath=STUDY/'epoch4/runtime-repair/official-package-closure.json';spec=load(specpath)
assert sha(specpath)=='3efc9666b549da8f70a22b0fca285dca68112f6835c767d08fd7f5946fc31726'
archives=['ruvector--core.tgz','ruvector-core-linux-x64-gnu.tgz'];files=[]
lock=load(PROJECT/'retrieval/package-lock.json')
for pkg,archive in zip(spec['packages'],archives):
    path=STUDY/'epoch4/runtime-repair'/archive;raw=path.read_bytes()
    assert len(raw)==pkg['tarball_bytes'] and hashlib.sha256(raw).hexdigest()==pkg['tarball_sha256']
    assert 'sha512-'+base64.b64encode(hashlib.sha512(raw).digest()).decode()==pkg['npm_integrity']
    assert lock['packages']['node_modules/'+pkg['package']]['integrity']==pkg['npm_integrity']
    with tarfile.open(path) as tar:
        members=[m for m in tar.getmembers() if m.isfile()]
        assert len(members)==len(pkg['files'])
        for item in pkg['files']:
            target=PROJECT/item['path'];member=tar.getmember('package/'+target.name)
            assert member.isfile() and not target.is_symlink() and target.resolve().is_relative_to(PROJECT.resolve())
            assert member.size==item['bytes']==target.stat().st_size
            assert hashlib.sha256(tar.extractfile(member).read()).hexdigest()==item['sha256']==sha(target)
            files.append(item)
js="""const path=require('node:path');let attempts=0;process.dlopen=()=>{attempts++;throw Error('forbidden')};const root=process.argv[1];const names=['@ruvector/core','ruvector-core-linux-x64-gnu','ruvector-core-linux-x64-gnu/ruvector.node'];let resolved=names.map(package=>({package,resolved:require.resolve(package,{paths:[path.join(root,'retrieval')]})}));if(attempts)throw Error('addon attempted');process.stdout.write(JSON.stringify({resolved,package_imports_executed:0,native_addon_load_attempts:attempts}));"""
env=dict(os.environ);env.pop('NODE_OPTIONS',None);env.pop('NODE_PATH',None)
done=subprocess.run(['node','--no-addons','--no-global-search-paths','-e',js,str(PROJECT)],env=env,capture_output=True,text=True,check=True,timeout=10)
witness=json.loads(done.stdout)
for item,relative in zip(witness['resolved'],['retrieval/node_modules/@ruvector/core/index.js','retrieval/node_modules/ruvector-core-linux-x64-gnu/index.js','retrieval/node_modules/ruvector-core-linux-x64-gnu/ruvector.node']):
    assert Path(item['resolved']).resolve()==(PROJECT/relative).resolve()
save('actual-executor-native-closure-independent-v1.json',{'at':datetime.now(timezone.utc).isoformat(),'passed':True,'project':str(PROJECT),'official_spec_sha256':sha(specpath),'official_archives_SHA512_SRI_and_SHA256_verified':2,'package_lock_integrity_verified':True,'actual_regular_files_verified':files,'witness':witness,'native_calls':0,'model_calls':0,'scope':'Actual final execution project resolution only with addons disabled. Verifies full8-file closure, not search/inference correctness.'})
