"""Finite public execution archive for successful, partial or failed attempts."""
import hashlib
import io
import json
from pathlib import Path
import re
import sys
import tarfile

ROOT=Path(__file__).resolve().parents[3]
HERE=Path(__file__).resolve().parent
sha=lambda path:hashlib.sha256(Path(path).read_bytes()).hexdigest()

def save(directory):
    archive=directory/'execution-evidence.tgz'
    if archive.exists():raise ValueError('Do not replace preserved attempts')
    plan=json.loads((directory/'plan.json').read_text())
    names=['plan.json','source-manifest.json','tests.json','synthetic-tests.log','launch-receipt.json','native-process.json','native-worker-cleanup.json','state.json','results.json','decisions.jsonl','cold.json','tasks.json','server-audit.jsonl','supervisor-terminal.json']
    files={name:directory/name for name in names if (directory/name).is_file()}
    if (directory/'wire').is_dir():
        for p in (directory/'wire').iterdir():
            if not re.fullmatch(r'(?:warmup|\d{4})\.(?:request|response)\.http',p.name):raise ValueError('Unknown wire artifact')
            files['wire/'+p.name]=p
    for p in directory.glob('failed-attempt-*.json'):
        if not re.fullmatch(r'failed-attempt-\d+\.json',p.name):raise ValueError('Unsafe failure artifact')
        files[p.name]=p
    for relative,digest in plan['source_sha256'].items():
        p=ROOT/relative
        if sha(p)!=digest:raise ValueError('Source changed after premeasurement freeze')
        files['sources/'+relative]=p
    members=[]
    with tarfile.open(archive,'w:gz') as t:
        for name,p in sorted(files.items()):
            if p.is_symlink() or p.stat().st_size>32*1024*1024:raise ValueError('Unsafe public attempt artifact')
            raw=p.read_bytes();info=tarfile.TarInfo(name);info.size=len(raw);info.mode=0o644;t.addfile(info,io.BytesIO(raw));members.append({'path':name,'bytes':len(raw),'sha256':hashlib.sha256(raw).hexdigest()})
    with tarfile.open(archive) as t:
        if t.getnames()!=[m['path'] for m in members]:raise ValueError('Archive membership drift')
        for m in members:
            if hashlib.sha256(t.extractfile(m['path']).read()).hexdigest()!=m['sha256']:raise ValueError('Archive transport failure')
    receipt={'status':'preserved_execution','scientific_verification':'separate pending check, never implied by successful archive','artifact':{'path':str(archive.relative_to(ROOT)),'sha256':sha(archive),'bytes':archive.stat().st_size},'members':members,'new_paid_calls':0}
    (directory/'execution-preservation.json').write_text(json.dumps(receipt,indent=2)+'\n');return receipt

if __name__=='__main__':print(json.dumps(save(HERE/sys.argv[1])['artifact']))
