from pathlib import Path
import json,hashlib,shutil
from datetime import datetime,timezone
s=Path('/workspace/ruvector-eval/experiments/sota-2026-10-22');e=s/'epoch12';actual=e/'project/experiments/sota-2026-10-22/epoch12'
def h(p):return hashlib.sha256(p.read_bytes()).hexdigest()
assert (actual/'study-completion.json').is_file(),'No terminal study evidence'
assert h(actual/'plan.json')==h(e/'plan.json')
summary=json.loads((actual/'study-completion.json').read_text());assert len(summary['started_phases'])<=2
files=[]
for p in sorted(actual.rglob('*')):
 if not p.is_file() or p.name=='plan.json':continue
 rel=p.relative_to(actual);assert p.suffix in ('.json','.jsonl','.log','.txt'),str(rel)
 dst=e/rel
 if dst.exists():
  assert h(p)==h(dst),'Immutable prior source differs: '+str(rel)
  continue
 dst.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(p,dst);assert h(p)==h(dst)
 files.append({'path':str(rel),'bytes':p.stat().st_size,'sha256':h(p)})
(e/'actual-snapshot.json').write_text(json.dumps({'at':datetime.now(timezone.utc).isoformat(),'actual_project':str(actual.parents[2]),'terminal_summary_sha256':h(actual/'study-completion.json'),'plan_sha256':h(actual/'plan.json'),'actual_attempts':summary['actual_native_attempts'],'files':files},indent=2)+'\n')
print(json.dumps({'snapshotted':len(files),'actual_attempts':summary['actual_native_attempts'],'status':summary['status']}))
