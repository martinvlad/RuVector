"""Read-only positive physical process closure proofs; no Gold capabilities."""
from pathlib import Path


def snapshot(pid):
    try:
        p=Path('/proc')/str(pid);a=(p/'stat').read_text().rsplit(')',1)[1].split()
        return {'pid':int(pid),'state':a[0],'ppid':int(a[1]),'pgid':int(a[2]),
                'sid':int(a[3]),'ticks':int(a[19]),'exit_wait_status':int(a[49]) if len(a)>=50 else None}
    except (FileNotFoundError,ProcessLookupError):return None


def terminal(pid, expected_ticks=None, require_wait_zero=False):
    first=snapshot(pid)
    if first is None:return {'absent':True,'known_exit_status':None,'terminal_resources_zero':None}
    if expected_ticks is not None and first['ticks']!=expected_ticks:raise RuntimeError('PID_REUSED')
    if first['state']!='Z':raise RuntimeError('OWNED_PROCESS_STILL_LIVE')
    p=Path('/proc')/str(pid)
    status=dict(line.split(':',1)for line in(p/'status').read_text().splitlines()if ':'in line)
    memory=(p/'statm').read_text().split()
    if status.get('FDSize','').strip()!='0' or len(memory)<6 or any(int(x)!=0 for x in memory):
        raise RuntimeError('TERMINAL_RESOURCES_NOT_ZERO')
    second=snapshot(pid)
    if second!=first:raise RuntimeError('PROCESS_CHANGED_ACROSS_FENCES')
    if require_wait_zero and first['exit_wait_status']!=0:raise RuntimeError('ACTUAL_Z_EXIT_NOT_ZERO')
    return {'absent':False,'identity':first,'known_exit_status':first['exit_wait_status'],
            'terminal_resources_zero':True,'FDSize':0,'statm_all_zero':True,'double_stat_stable':True}


def groups_closed(group_ids):
    observations=[]
    for p in Path('/proc').iterdir():
        if not p.name.isdigit():continue
        state=snapshot(int(p.name))
        if state and (state['pgid'] in group_ids or state['sid'] in group_ids):
            proof=terminal(state['pid'],state['ticks'])
            if not proof.get('terminal_resources_zero'):raise RuntimeError('GROUP_CLOSURE_UNKNOWN')
            observations.append(proof)
    return observations
