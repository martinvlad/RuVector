"""Metadata-only exact binding renderer. Never stage, call Git, or run science.

Recovery binds actual ad86 and Guardian15. Standard transport binds only a later
independent actual recovery readback. Existing E49 donor algorithms are retained.
"""
import sys
sys.dont_write_bytecode = True
from pathlib import Path
import hashlib, json, re

HERE=Path(__file__).resolve().parent
LEASE='/dev/shm/ruvector-sota-2026-10-22/epoch50-ad86e60e2402'
PREFIX='recoveries/epoch49-stop-publication-20261027-g15/'
BASE='ad86e60e240281c0439429b02746c2239a39c0d3'
DENY=['486888de9602bbb5d817a55f707b4fcfd11c65e0','3d5a61f9068acf2dabd2ae5c6bd531d9a9b464c5','a68b7ba587332f176f65d0348de3e910aa16e77a']
EXPECTED={'guard.py':'c27843776e9387704fb9cda4d2f5636e131b0885289a448b71f61765efff0291','stagebuilder.py':'944a00e24d87a509073c183274427bb5ad2879c6f23b69190b62c31f543ddc4b','controller.js':'2ec7b78c99654e93c4ce8d96555b126dc9b5d5783c800f7650505187489b6b65'}
def digest(b):return hashlib.sha256(b).hexdigest()
def encoded(x):return (json.dumps(x,sort_keys=True,indent=2)+'\n').encode()
def exclusive(p,b):
    p.parent.mkdir(parents=True,exist_ok=True)
    with p.open('xb') as f:f.write(b)
def donor_bytes(name):
    donor=HERE/'donors'/name
    if not donor.exists():
        canonical='experiments/sota-2026-10-22/epoch49/publication/'+name
        donor=next((p/canonical for p in HERE.parents if (p/canonical).is_file()),None)
    assert donor is not None,'restore the reviewed separate E49 overlay first'
    return donor.read_bytes()
def render(mode,out,readback=None):
    assert mode in ('recovery','standard')
    out=Path(out);assert not out.exists()
    if mode=='standard':
        assert isinstance(readback,dict) and readback['checks_passed'] is True and readback['verified_actual_remote_readback'] is True
        assert readback['publication_role']=='ARCHIVE_RECOVERY_NO_SCI' and readback['original_parent']==BASE
        for k in ('commit','root','bench','scope'):assert re.fullmatch('[0-9a-f]{40}',readback[k]) and readback[k] not in DENY
        assert type(readback['Git_leaves']) is int and readback['Git_leaves']>8128
        assert type(readback['CP_rows']) is int and readback['CP_rows']>8121
        assert readback['Git_leaves']-8128==readback['CP_rows']-8121
        binding=dict(base=readback['commit'],root=readback['root'],bench=readback['bench'],scope=readback['scope'],Git_leaves=readback['Git_leaves'],CP_rows=readback['CP_rows'])
    else:binding=dict(base=BASE,root='eeb006ec097af4da05ad8417f1a63306cad9d3b8',bench='9fd1f5ad06fcf6e66e1552419b23bcfb9c032074',scope='be644f9a05cfb615e5d75bf8c4017a101590cb0f',Git_leaves=8128,CP_rows=8121)
    opsroot=LEASE+'/recovery-transport' if mode=='recovery' else LEASE
    changes=[]
    for name,expected in EXPECTED.items():
        original=donor_bytes(name);assert digest(original)==expected
        text=original.decode();ops=[]
        def swap(a,b,required=True):
            nonlocal text
            n=text.count(a)
            assert n or not required,(name,a)
            if n:text=text.replace(a,b);ops.append(dict(old=a,new=b,count=n))
        swap('E49','E50')
        swap('epoch49-ad86e60e2402','epoch50-ad86e60e2402',False)
        swap('e49-','e50-recovery-' if mode=='recovery' else 'e50-',False)
        swap('-g14','-g15',False)
        swap('afbdfb4622cf7db889a9d340e0bad4dcfc5157f0c449af065a1cf458ba660f9e','2854df82624e7c7c236b45b799c383a3555673a6268d7500858f1b9bc18410bc',False)
        swap('157193','158817',False);swap('38125900','38479788',False);swap('guardian14','guardian15',False)
        swap("'3d5a61f9068acf2dabd2ae5c6bd531d9a9b464c5'","'3d5a61f9068acf2dabd2ae5c6bd531d9a9b464c5','a68b7ba587332f176f65d0348de3e910aa16e77a'",False)
        if name.endswith('.py'):
            for a,b in [('== 49','== 50'),('== 14','== 15')]:
                text,n=re.subn(re.escape(a)+r'(?![0-9])',b,text)
                if n:ops.append(dict(old=a,new=b,count=n,numeric_token=True))
            swap("'epoch': 49","'epoch': 50",False);swap("'generation': 14","'generation': 15",False)
            swap("'bytes': 703","'bytes': 711",False)
            if name=='guard.py':
                swap("W = Path('"+LEASE+"')","W = Path('"+opsroot+"')")
                swap("R = W / 'project'","R = Path('"+LEASE+"/project')")
                swap("str(W / 'owner.json')","'"+LEASE+"/owner.json'")
                swap("(W / 'release.request')","(Path('"+LEASE+"') / 'release.request')")
                swap("BASE = '"+BASE+"'","BASE = '"+binding['base']+"'")
                for key,old in [('ROOT','eeb006ec097af4da05ad8417f1a63306cad9d3b8'),('BENCH','9fd1f5ad06fcf6e66e1552419b23bcfb9c032074'),('SCOPE','be644f9a05cfb615e5d75bf8c4017a101590cb0f')]:swap("BASE_"+key+" = '"+old+"'","BASE_"+key+" = '"+binding[key.lower()]+"'")
                roots="ROOTS = tuple('experiments/sota-2026-10-22/' + p for p in ('epoch49/', 'audit/epoch49/', 'runtime/epoch49/'))"
                swap(roots,"ROOTS = ('"+PREFIX+"',)" if mode=='recovery' else roots.replace('epoch49/','epoch50/'))
            else:
                if mode=='recovery':
                    swap("source_keys = {'epoch49_source', 'epoch49_frozen_study', 'epoch49_data_roles'}","source_keys = {'epoch49_publication_recovery15', 'cumulative_budget_ledger'}")
                    swap("key = 'epoch49_' + phase","key = 'epoch49_publication_recovery15'")
                else:swap('epoch49_','epoch50_')
                swap('len(oldgit) == 8128','len(oldgit) == '+str(binding['Git_leaves']))
                swap('len(oldrows) == 8121','len(oldrows) == '+str(binding['CP_rows']))
        else:
            ids=sorted(set(re.findall(r'\b[A-Za-z_][A-Za-z_0-9]*49\b',text)))
            for ident in ids:swap(ident,ident[:-2]+'50')
            swap('epoch:49','epoch:50')
            swap("const W50='"+LEASE+"'","const W50='"+opsroot+"'")
            swap("  await guard50('reserve'","  await new Promise(resolve=>setTimeout(resolve,2000));\n  await guard50('reserve'")
        if mode=='recovery':
            swap('REAL_CONTRACTNLI_ROBERTA_FAITHFUL_MMAP_TRANSFER_PILOT','ARCHIVE_RECOVERY_NO_SCI',False)
            swap("['source','final']","['source']",False)
            swap("('source', 'final')","('source',)",False)
            swap("['source', 'final']","['source']",False)
            if name=='controller.js':
                swap('publishE50Phase','publishE50Recovery');swap('persistE50Receipt','persistE50RecoveryReceipt')
                swap('publication_only:true','publication_role:\'ARCHIVE_RECOVERY_NO_SCI\',publication_only:true')
            if name=='stagebuilder.py':swap("'publication_only': True","'publication_role': 'ARCHIVE_RECOVERY_NO_SCI', 'publication_only': True")
        result=text.encode();exclusive(out/name,result)
        changes.append(dict(file=name,donor_sha256=expected,result_sha256=digest(result),operations=ops))
    exclusive(out/'BINDING_REPORT.json',encoded(dict(schema_version=1,mode=mode,binding=binding,owner_epoch=50,owner_generation=15,changes=changes,readback=readback,actual_Git_or_SCI_calls=0)))
    return changes

# No implicit renderer execution. Root imports reviewed definitions and explicitly
# invokes one mode only with pinned input; standard mode requires actual readback.
