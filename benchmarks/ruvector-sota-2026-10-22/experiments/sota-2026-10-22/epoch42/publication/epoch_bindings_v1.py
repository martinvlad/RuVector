"""Bound E42 publication metadata; no scientific execution is authorized here.

No filesystem, dataset, model, clock, network or environment discovery occurs.
Every production entrypoint must call require_bound before touching inputs.
"""
from pathlib import Path
import re
EPOCH=42
SOURCE_BINDINGS_READY=True
BASE_COMMIT='222874558c0b696f92824e5fce3775494877f821'
BASE_CP_SHA256='588509932b9cc628d2d7263954e42ddc4c24fa34ea068cbb71245ebfeed5da76'
OLD_CP_ROWS=6960
BASE_GIT_LEAVES=7034
BASE_SCOPE_TREE='5a601bc63545b732d6b3b24d9f9fe54bfbe3ec2b'
OWNER_PIN=(125788,29584865,13626)
OWNER_RUN_ID='epoch42-222874558c0b'
OWNER_GENERATION=1
OWNER_EXPIRES_UNIX=1792982946.734674
OWNER_BOOT_ID='4632fb06-b0ef-4df5-b72b-0e875bbad810'
OWNER_PID_NAMESPACE='pid:[4026532200]'
OWNER_LOCK_DEVICE=33
WORK_SCOPE_DIR=Path('/tmp/ruvector-sota-2026-10-22/epoch42-222874558c0b')
OWNER_SCOPE_DIR=WORK_SCOPE_DIR
OWNER_LOCK=WORK_SCOPE_DIR.parent/'exclusive.work.lock'
PRIOR_CORPUS_ATTEMPTS_LOWER_BOUND=36
PRIOR_CORPUS_COMPLETED_LOWER_BOUND=34
PRIOR_BOUNDED_NATIVE_PROCESS_ATTEMPTS=41
CURRENT_HTTP_SUCCESSES=3
CURRENT_HTTP_FAILURES=0
CUMULATIVE_HTTP_SUCCESSES=909
CUMULATIVE_HTTP_FAILURES=2

def require_bound():
 if SOURCE_BINDINGS_READY is not True:
  raise ValueError('DISABLED E42 source template: new actual base/owner/data/model/source bindings have not been reviewed')
 for value,width in ((BASE_COMMIT,40),(BASE_CP_SHA256,64),(BASE_SCOPE_TREE,40)):
  if not isinstance(value,str) or re.fullmatch('[0-9a-f]{%d}'%width,value) is None:raise ValueError('Actual immutable source identities required')
 for value in (OLD_CP_ROWS,BASE_GIT_LEAVES,OWNER_GENERATION,OWNER_LOCK_DEVICE,*OWNER_PIN):
  if type(value)is not int or value<=0:raise ValueError('Actual source/owner integer identities required')
 if type(OWNER_EXPIRES_UNIX) not in (float,int) or not isinstance(OWNER_BOOT_ID,str) or not isinstance(OWNER_PID_NAMESPACE,str):raise ValueError('Actual original physical owner evidence required')
 expected=Path('/tmp/ruvector-sota-2026-10-22')/('epoch42-'+BASE_COMMIT[:12])
 if WORK_SCOPE_DIR!=expected or OWNER_SCOPE_DIR!=expected or OWNER_RUN_ID!=expected.name or OWNER_LOCK!=expected.parent/'exclusive.work.lock':raise ValueError('Exact new isolated epoch42 namespace required')
 for value in (CURRENT_HTTP_SUCCESSES,CURRENT_HTTP_FAILURES,CUMULATIVE_HTTP_SUCCESSES,CUMULATIVE_HTTP_FAILURES):
  if type(value)is not int or value<0:raise ValueError('Actually observed current official refresh counts required')
 return True
