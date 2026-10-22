"""Independent input/capacity/official-package checks; never initializes a model."""
from pathlib import Path
from datetime import datetime, timezone
import base64, hashlib, itertools, json, os, subprocess, tarfile

OUT = Path(__file__).resolve().parent
STUDY = OUT.parents[1]
PROJECT = STUDY/'epoch7/project'
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

data=STUDY/'legal-transfer/epoch7'
train=load(STUDY/'legal-transfer/epoch3/sources/original-train.json')
assert sha(STUDY/'legal-transfer/epoch3/sources/original-train.json')=='dbceb356cd6203b35b27be94a5fa85e499a81c34c42c89ad53060b39f0257ba5'
registry=load(data/'eligibility-manifest.json')
oldreg=load(STUDY/'legal-transfer/epoch6/eligibility-manifest.json')
assert registry['historical_exclusions']==oldreg['historical_exclusions']
assert registry['consumed_epoch3_dev']==oldreg['consumed_epoch3_dev']
dev3=rows(STUDY/'legal-transfer/epoch3/development24.jsonl')
dev4=rows(STUDY/'legal-transfer/epoch4/development24.jsonl')
dev5=rows(STUDY/'legal-transfer/epoch5/development24.jsonl')
dev6=rows(STUDY/'legal-transfer/epoch6/development24.jsonl')
ids3={x['provenance']['document_id'] for x in dev3}
ids4={x['provenance']['document_id'] for x in dev4}
ids5={x['provenance']['document_id'] for x in dev5}
ids6={x['provenance']['document_id'] for x in dev6}
assert set(registry['consumed_epoch3_dev']['document_ids'])==ids3
assert set(registry['consumed_epoch4_dev']['document_ids'])==ids4
assert set(registry['consumed_epoch5_dev']['document_ids'])==ids5
assert set(registry['consumed_epoch6_dev']['document_ids'])==ids6
excluded={x['id'] for x in registry['historical_exclusions']['excluded_documents']}
eligible={x['id'] for x in train['documents']}-excluded-ids3-ids4-ids5-ids6
assert len(excluded)==77 and len(ids3)==len(ids4)==len(ids5)==len(ids6)==8 and len(eligible)==314
assert eligible==set(registry['eligible_document_ids'])
draw=[]
for d in train['documents']:
    if d['id'] in eligible:
        textsha=hashlib.sha256(norm(d['text']).encode()).hexdigest()
        key=hashlib.sha256(f"ruvector-original-contractnli-epoch7-dev-v1|{d['id']}|{textsha}".encode()).hexdigest()
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
        assert r['id']==f"original-contractnli:train:epoch7:{d['id']}:{h}"
        assert r['input']==inp and r['input_sha256']==hashlib.sha256(canonical(inp).encode()).hexdigest()
        assert r['normalized_input_sha256']==hashlib.sha256(norm(canonical(inp)).encode()).hexdigest()
        assert r['source_group']==r['evaluation']['group']==f"original-contractnli:{d['id']}"
        original=d['annotation_sets'][0]['annotations'][h]['choice']
        assert r['evaluation']['original_threeway_label']==original and r['evaluation']['gold']==label[original]
        assert r['provenance']['normalized_document_sha256']==hashlib.sha256(norm(d['text']).encode()).hexdigest()
confirmation=rows(STUDY/'legal-transfer/epoch3/confirmation96.jsonl')
assert sha(STUDY/'legal-transfer/epoch3/confirmation96.jsonl')=='f01894b231b744c8297344615ce6037524b6eb0794c7548e931839d2936cd79f'
assert {r['source_group'] for r in records}.isdisjoint({r['source_group'] for r in dev3+dev4+dev5+dev6+confirmation})
assert {norm(r['input']['state']) for r in records}.isdisjoint({norm(r['input']['state']) for r in dev3+dev4+dev5+dev6+confirmation})
manifest=load(data/'source-manifest.json')
for p in manifest['files']:
    assert sha(data/p['path'])==p['sha256'] and (data/p['path']).stat().st_size==p['bytes']
save('data-independent-v1.json',{'at':datetime.now(timezone.utc).isoformat(),'passed':True,'DEV_sha256':sha(data/'development24.jsonl'),'data_contract_sha256':sha(data/'data-contract.json'),'source_manifest_sha256':sha(data/'source-manifest.json'),'counts':{'source':423,'historic_excluded':77,'prior_epoch3':8,'prior_epoch4':8,'prior_epoch5':8,'prior_epoch6':8,'eligible':314,'selected_docs':8,'queries':24},'document_ids':[d['id'] for d in selected],'checks':['text-only salted draw independently rebuilt','exact source hypotheses/text/threeway-to-binary gold/input hashes','all prior declared epochs3/4/5/6 DEV excluded','source-group and normalized fulltext disjoint from old DEV/confirmation','seven source pins verified'],'novelty_limit':'Historical77 novelty inherited from prior audited registry; public source and unknown pretrained-model overlap, not sealed.','native_calls':0,'model_calls':0})

