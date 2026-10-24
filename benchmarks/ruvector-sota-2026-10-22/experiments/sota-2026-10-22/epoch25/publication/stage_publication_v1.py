"""Stage reviewed UTF8 epoch25 Git payloads outside the project; no Git calls.

All historical source tuples and checkpoint rows are verified, not inferred
from counts. The inherited decoded RAW22 remains a checkpoint-only artifact,
with its already-published lossless archive/extractor/helper unchanged.
"""
from __future__ import annotations
import sys
sys.dont_write_bytecode = True
import argparse
import copy
import json
from pathlib import Path
import re
from publication_common_v1 import (P, SCOPE, CONTROLS, BASE_COMMIT, OWNER_PIN, author_nli_limits, check_inherited_checkpoint, check_final_manifest,
    check_history, check_ledger_history, check_execution_history, check_transport, content, cp_rows,
    directory, encoded, final_ledger, gitsha, new_output, parse, public_text, ref, relative,
    require, sha, walk_current, write)

MAX_BLOB_JSON = 8 * 1024 * 1024 - 4096
MAX_TREE_JSON = 180000 - 4096
LARGE_FILE_BYTES = 80000
TUPLE_KEYS = ('path', 'mode', 'type', 'sha', 'size')
MUTABLE_CONT = {'prior_published_base_commit', 'checkpoint_manifest_sha256',
    'active_run', 'benchmark_refresh', 'cumulative_budget_ledger',
    'execution_observed', 'epochs', 'next_research_priority', 'latest_learning',
    'rejection_ledger'}
FROZEN_REFS = {'plan': P+'epoch25/plan.json',
               'source_freeze': P+'epoch25/source-freeze.json',
               'PLAN_SPEC': P+'epoch25/PLAN_SPEC.json'}
FINAL_REFS = {'results': P+'epoch25/RESULTS.json',
              'source_manifest': P+'epoch25/SOURCE_MANIFEST.json',
              'used_identities': P+'epoch25/USED_IDENTITIES.json',
              'rejection_ledger': P+'epoch25/REJECTION_LEDGER.json',
              'acceptance_report': P+'audit/epoch25/acceptance-rejection.json',
              'plan': FROZEN_REFS['plan'], 'source_freeze': FROZEN_REFS['source_freeze']}
ROLES = {'train': [], 'dev': [], 'calibration': [], 'confirmation': []}


def checked_ref(project, row, checkpoint, expected_path=None):
    require(isinstance(row, dict) and set(row) == {'path','bytes','sha256'},
            'Canonical three-key reference required')
    path = relative(row['path'])
    require(expected_path is None or path == expected_path, 'Reference names an unexpected source')
    require(checkpoint.get(path) == row and ref(project,path) == row,
            'Reference differs from actual/checkpoint source bytes: '+path)
    return path


def checked_frozen_source(project, cont, checkpoint):
    frozen = cont.get('epoch25_frozen_study')
    require(isinstance(frozen,dict) and set(frozen) == set(FROZEN_REFS),
            'Exact plan/source-freeze/PLAN_SPEC frozen references required')
    for key,path in FROZEN_REFS.items(): checked_ref(project,frozen[key],checkpoint,path)
    refresh = P+'legal-transfer/epoch25/benchmark-refresh.json'
    checked_ref(project,cont.get('epoch25_official_refresh'),checkpoint,refresh)
    require(cont.get('benchmark_refresh') == cont['epoch25_official_refresh'],
            'Current official-refresh continuation references differ')
    plan = parse(project/FROZEN_REFS['plan'])
    spec = parse(project/FROZEN_REFS['PLAN_SPEC'])
    freeze = parse(project/FROZEN_REFS['source_freeze'])
    require(plan.get('epoch') == 25 and spec.get('epoch') == 25
            and plan.get('kind') == 'SOURCE_SCOPE_ENGINEERING'
            and plan.get('source_checkpoint') == spec.get('source_checkpoint') == BASE_COMMIT,
            'Frozen plan/spec differs from immutable source checkpoint')
    require(plan.get('benchmark_roles') == spec.get('benchmark_roles') == ROLES,
            'Frozen source must have empty benchmark roles')
    limits = plan.get('limits',{})
    require(type(limits.get('worker_attempts')) is int and limits['worker_attempts'] == 1
            and limits.get('cpu_threads') == 2 and limits.get('seconds_per_batch') == 600
            and type(limits.get('paid_calls')) is int and limits['paid_calls'] == 0
            and type(limits.get('GPU_calls')) is int and limits['GPU_calls'] == 0,
            'Frozen source does not bind one-worker/CPU2/600s/zero-spend limits')
    require(all(plan.get(key) is False for key in ('champion_promotion_allowed',
                'confirmation_execution_allowed','publisher_submission_allowed')),
            'Frozen plan may not admit confirmation, promotion or submission')
    author_nli_limits(plan)
    pins = plan.get('pins'); entries = freeze.get('source_entries')
    require(isinstance(pins,list) and pins and isinstance(entries,list) and entries,
            'Frozen plan pins and source entries are required')
    for label,rows in (('plan',pins),('freeze',entries)):
        paths = set()
        for row in rows:
            path = checked_ref(project,row,checkpoint)
            require(path not in paths,'Duplicate frozen '+label+' identity')
            paths.add(path)
            if label == 'freeze':
                require(path not in (FROZEN_REFS['plan'],FROZEN_REFS['source_freeze']),
                        'Freeze entries may not recursively include plan/freeze')
    require(frozen['source_freeze'] in pins, 'Plan lacks exact sealed source-freeze pin')
    for path_key,hash_key in (('source_freeze_path','source_freeze_sha256'),):
        if path_key in plan or hash_key in plan:
            require(plan.get(path_key) == frozen['source_freeze']['path']
                    and plan.get(hash_key) == frozen['source_freeze']['sha256'],
                    'Plan source-freeze binding differs')
    if 'source_checkpoint' in freeze:
        require(freeze['source_checkpoint'] == BASE_COMMIT,'Freeze checkpoint differs')
    return plan


def checked_final_evidence(project, cont, old_cont, checkpoint, parent, plan):
    manifest_path = P+'epoch25/EPOCH_MANIFEST.json'
    manifest_ref = ref(project,manifest_path)
    checked_ref(project,manifest_ref,checkpoint,manifest_path)
    manifest = parse(project/manifest_path)
    attempts = check_final_manifest(manifest,plan)
    require(manifest.get('source_checkpoint') == BASE_COMMIT
            and manifest.get('published_frozen_source_commit') == parent,
            'Final manifest differs from frozen checkpoint/publication parent')
    for key,path in FINAL_REFS.items(): checked_ref(project,manifest.get(key),checkpoint,path)
    require(manifest['plan'] == cont['epoch25_frozen_study']['plan']
            and manifest['source_freeze'] == cont['epoch25_frozen_study']['source_freeze'],
            'Final evidence changed published frozen source references')
    results = parse(project/FINAL_REFS['results'])
    acceptance = parse(project/FINAL_REFS['acceptance_report'])
    require(results.get('actual_execution') == manifest['actual_execution'],
            'Final counters differ from the exact runtime results')
    require(type(acceptance.get('engineering_qualified')) is bool
            and acceptance['engineering_qualified'] == manifest['engineering_qualified'],
            'Final qualification differs from independent acceptance verdict')
    require(cont.get('cumulative_budget_ledger') == manifest.get('cumulative_budget_ledger')
            == final_ledger(old_cont['cumulative_budget_ledger'],manifest,project),
            'Final continuation/manifest closed ledger differs')
    check_execution_history(old_cont['execution_observed'],cont.get('execution_observed'),
                            manifest['actual_execution'])
    if 'cumulative_execution' in manifest:
        require(manifest['cumulative_execution'] == cont['execution_observed'],
                'Manifest cumulative observed execution differs')
    require(cont.get('rejection_ledger') == manifest['rejection_ledger'],
            'Continuation rejection ledger reference differs from final evidence')
    checked_ref(project,old_cont['rejection_ledger'],checkpoint)
    check_ledger_history(parse(project/old_cont['rejection_ledger']['path']),
                         parse(project/manifest['rejection_ledger']['path']))
    require(isinstance(cont.get('latest_learning'),dict)
            and cont['latest_learning'].get('manifest') == manifest_ref,
            'Latest-learning manifest reference is not the exact final evidence')
    require(manifest.get('official_rank') is None
            and manifest.get('official_SOTA_verified',False) is False,
            'Engineering evidence cannot assert official placement or SOTA')
    epochs = cont.get('epochs')
    require(isinstance(epochs,list) and len(epochs) == len(old_cont['epochs'])+1
            and epochs[:-1] == old_cont['epochs']
            and epochs[-1].get('epoch') == 25
            and epochs[-1].get('native_worker_attempts') == attempts,
            'Final continuation must append exactly one actual epoch25')
    return manifest


def leaf(path, data):
    return {'path': path, 'mode': '100644', 'type': 'blob',
            'sha': gitsha(data), 'size': len(data)}


def tuple_row(row):
    require(isinstance(row, dict) and set(TUPLE_KEYS) <= set(row), 'Incomplete Git tuple')
    row = {key: row[key] for key in TUPLE_KEYS}
    path = row['path']
    require(isinstance(path, str), 'Git path must be text')
    if path.startswith(SCOPE):
        path = path[len(SCOPE):]
    row['path'] = relative(path)
    require(row['mode'] == '100644' and row['type'] == 'blob'
            and re.fullmatch('[0-9a-f]{40}', row['sha'] or '')
            and type(row['size']) is int and row['size'] >= 0,
            'Nonregular/invalid Git tuple')
    return row


def tuple_map(document):
    if isinstance(document, dict) and isinstance(document.get('files'), list):
        if 'scope' in document:
            require(document['scope'] == SCOPE, 'Expected-leaf scope differs')
        rows = document['files']
    elif isinstance(document, dict):
        rows = []
        for key, value in document.items():
            item = tuple_row(value)
            normalized = key[len(SCOPE):] if key.startswith(SCOPE) else key
            require(item['path'] == relative(normalized), 'Expected-map key/path differs')
            rows.append(item)
    else:
        raise ValueError('Expected-leaf document must contain files or a tuple map')
    answer = {}
    for item in rows:
        row = tuple_row(item)
        require(row['path'] not in answer, 'Duplicate expected Git leaf')
        answer[row['path']] = row
    require(CONTROLS <= set(answer), 'Three historical controls required')
    return answer


def verify_baseline(kit, index):
    require(isinstance(index, dict) and re.fullmatch('[0-9a-f]{40}',
            index.get('source_commit', '') or ''), 'Immutable source-filemap commit required')
    require(index['source_commit'] == BASE_COMMIT, 'Source-filemap is not the pinned epoch24 final commit')
    baseline = tuple_map({'files': index['files']})
    for path, row in baseline.items():
        require(leaf(path, content(kit / path)) == row, 'Historical Git bytes changed: ' + path)
    return baseline


def checked_review(document, current):
    rows = document['files'] if isinstance(document, dict) else document
    require(isinstance(rows, list), 'Reviewed exact file allowlist required')
    allowed = {}
    for row in rows:
        path = relative(row['path'])
        require(path not in allowed, 'Duplicate reviewed path')
        allowed[path] = row
    require(set(allowed) == set(current), 'Allowlist must cover all and only current epoch25 files')
    for path, data in current.items():
        row = allowed[path]
        require(type(row.get('bytes')) is int and row['bytes'] == len(data)
                and row.get('sha256') == sha(data), 'Reviewed bytes changed: ' + path)


def checkpoint_extension(old, new, current):
    before, after = cp_rows(old), cp_rows(new)
    require(set(old) <= set(new)
            and all(key.startswith('epoch25_') for key in set(new) - set(old))
            and all(new[key] == value for key, value in old.items() if key != 'project_files'),
            'Historical checkpoint metadata changed or dropped')
    additions = {path: {'path': path, 'bytes': len(body), 'sha256': sha(body)}
                 for path, body in current.items()}
    require(not set(before).intersection(additions)
            and set(after) == set(before) | set(additions)
            and all(after.get(path) == row for path, row in {**before, **additions}.items()),
            'Checkpoint must preserve every inherited identity and append exactly current files')
    return before, after


def checked_controls(controls, kit, project, current, mode, parent, prior_controls=None):
    require({p.name for p in controls.iterdir()} == CONTROLS,
            'Controls directory must contain exactly three files')
    bodies = {name: content(controls / name) for name in sorted(CONTROLS)}
    for name, body in bodies.items(): public_text(name, body)
    old_cp = parse(kit / 'CHECKPOINT_MANIFEST.json')
    old_cont = parse(kit / 'CONTINUATION.json')
    check_inherited_checkpoint(old_cp); check_history(project, old_cp)
    require(sha(content(kit / 'CHECKPOINT_MANIFEST.json')) == old_cont['checkpoint_manifest_sha256'],
            'Inherited checkpoint/continuation hash binding differs')
    cp, cont, active = (json.loads(bodies[name]) for name in
                       ('CHECKPOINT_MANIFEST.json','CONTINUATION.json','ACTIVE_RUN.json'))
    before, after = checkpoint_extension(old_cp, cp, current)
    require(set(old_cont) <= set(cont)
            and all(key in old_cont or key.startswith('epoch25_') for key in cont),
            'Continuation dropped old metadata or added outside epoch25 namespace')
    mutable = {'active_run','checkpoint_manifest_sha256','prior_published_base_commit',
               'benchmark_refresh'}
    if mode == 'final': mutable |= MUTABLE_CONT
    if mode == 'lease': mutable = {'active_run'}
    require(all(cont[key] == value for key,value in old_cont.items() if key not in mutable),
            'Historical continuation metadata changed')
    require(cont.get('checkpoint_manifest_sha256') == sha(bodies['CHECKPOINT_MANIFEST.json'])
            and cont.get('active_run') == dict(active, path='ACTIVE_RUN.json')
            and cont.get('goal_met') is False, 'New control/hash/status binding differs')
    require(type(active.get('native_allowed')) is int and active['native_allowed'] == 0
            and active.get('experiments_active') is False
            and active.get('OS_lock_held') is True
            and (active.get('owner_pid'), active.get('owner_startticks'), active.get('lock_inode'))
                == OWNER_PIN
            and active.get('checkpoint_parent') == parent,
            'Controls differ from pinned owner, parent or zero immediate execution allowance')
    confirm = active.get('conditional_confirmation_after_independent_DEV_runtime_gates', 0)
    require(type(confirm) is int and confirm == 0, 'Confirmation allowance must remain zero')
    conditional = active.get('native_allowed_after_exact_remote_readback')
    require(type(conditional) is int, 'Explicit conditional native allowance required')
    plan = checked_frozen_source(project,cont,after) if mode != 'lease' else None
    if mode == 'lease':
        require(not current and cp == old_cp and conditional == 0
                and active.get('state') == 'EPOCH25_PLANNING_EXCLUSIVE'
                and set(cont)-set(old_cont) == {'epoch25_planning'}, 'Invalid planning-only lease')
    else:
        require(cont.get('prior_published_base_commit') == parent,
                'Continuation publication parent differs')
        if mode == 'source':
            require(conditional == 1 and active.get('work_active') is True
                    and active.get('state') == 'EPOCH25_SOURCE_FROZEN_PENDING_REMOTE_ADMISSION',
                    'Invalid source-only pending admission state')
            require(P+'epoch25/EPOCH_MANIFEST.json' not in current
                    and P+'epoch25/launch.json' not in current
                    and not any(path.startswith(P+'epoch25/runs/') for path in current),
                    'Source stage contains execution/result artifacts')
        else:
            require(conditional == 0 and active.get('work_active') is False
                    and active.get('state') == 'EPOCH25_CLOSED'
                    and active.get('all_unspent_epoch25_slots_permanently_closed') is True,
                    'Final controls did not close every current slot')
            require(prior_controls is not None, 'Final stage requires actual prior source controls')
    if prior_controls is not None:
        prior_cp = parse(prior_controls/'CHECKPOINT_MANIFEST.json')
        prior_cont = parse(prior_controls/'CONTINUATION.json')
        prior_rows = cp_rows(prior_cp)
        require(set(prior_cp) <= set(cp)
                and all(cp[key] == value for key,value in prior_cp.items() if key!='project_files')
                and all(after.get(path)==row for path,row in prior_rows.items()),
                'Prior published checkpoint metadata/rows changed or disappeared')
        for key in ('epoch25_planning','epoch25_frozen_study','epoch25_official_refresh'):
            if key in prior_cont:
                require(cont.get(key) == prior_cont[key], 'Published frozen continuation field changed: '+key)
        if mode == 'final':
            require('epoch25_frozen_study' in prior_cont
                    and parse(prior_controls/'ACTIVE_RUN.json').get('state')
                        == 'EPOCH25_SOURCE_FROZEN_PENDING_REMOTE_ADMISSION',
                    'Final prior controls are not the published frozen source stage')
    if mode == 'final':
        checked_final_evidence(project,cont,old_cont,after,parent,plan)
    transport = check_transport(project, old_cont, cont, after)
    return bodies, old_cp, cp, cont, active, transport


def verify_prior(prior, baseline, expected):
    require(set(baseline) <= set(prior), 'Published prior dropped a historical Git leaf')
    for path, row in baseline.items():
        if path not in CONTROLS:
            require(prior[path] == row, 'Prior historical tuple differs: ' + path)
    for path, row in prior.items():
        if path not in CONTROLS:
            require(expected.get(path) == row, 'Published source changed/disappeared: ' + path)


def transport_groups(changed):
    entries, blobs, groups = [], [], []
    for path, body in sorted(changed.items()):
        text = public_text(path, body)
        entry = {'path': SCOPE + path, 'mode': '100644', 'type': 'blob'}
        if len(body) > LARGE_FILE_BYTES:
            payload = {'content': text, 'encoding': 'utf-8'}
            require(len(encoded(payload)) < MAX_BLOB_JSON,
                    'Blob JSON plus4096 reserve must be strictly below8MiB')
            blobs.append((path, body, payload)); entry['sha'] = gitsha(body)
        else:
            entry['content'] = text
        require(len(encoded({'tree_elements': [entry]})) < MAX_TREE_JSON,
                'One tree entry exceeds180000-byte request bound')
        entries.append(entry)
    batch = []
    for entry in entries:
        if len(encoded({'tree_elements': batch + [entry]})) >= MAX_TREE_JSON:
            require(batch, 'Empty group cannot accommodate one tree entry')
            groups.append(batch); batch = []
        batch.append(entry)
    if batch:
        groups.append(batch)
    return blobs, groups


def prepare(args):
    project, kit, controls = map(directory, (args.project, args.kit, args.controls_dir))
    prior_controls = directory(args.prior_controls_dir) if args.prior_controls_dir else None
    forbidden = (project, kit, controls) + ((prior_controls,) if prior_controls else ())
    out = new_output(args.out, forbidden)
    for name in ('parent','expected_main','expected_root','expected_bench','expected_scope'):
        require(re.fullmatch('[0-9a-f]{40}',getattr(args,name) or ''), 'Exact Git guard SHA required: '+name)
    source_bytes = content(args.source_filemap); index = json.loads(source_bytes)
    baseline = verify_baseline(kit, index)
    current = {} if args.mode == 'lease' else walk_current(project)
    review_bytes = content(args.reviewed_files)
    checked_review(json.loads(review_bytes), current)
    bodies, old_cp, cp, cont, active, reconstruction = checked_controls(
        controls, kit, project, current, args.mode, args.parent, prior_controls)
    prior_bytes = content(args.prior_expected); prior = tuple_map(json.loads(prior_bytes))
    if prior_controls:
        require({p.name for p in prior_controls.iterdir()} == CONTROLS,
                'Prior controls must be exactly three files')
        for name in CONTROLS:
            require(leaf(name,content(prior_controls/name)) == prior.get(name),
                    'Prior control bytes are not the actual published prior tuple: '+name)
        prior_cont = parse(prior_controls/'CONTINUATION.json')
        require(prior_cont['checkpoint_manifest_sha256'] == sha(content(prior_controls/'CHECKPOINT_MANIFEST.json')),
                'Prior control checkpoint/hash binding differs')
    expected = copy.deepcopy(baseline)
    for path, body in {**current, **bodies}.items():
        require(path not in baseline or path in CONTROLS, 'Inherited Git leaf overwrite: '+path)
        expected[path] = leaf(path,body)
    verify_prior(prior, baseline, expected)
    check_transport(project,parse(kit/'CONTINUATION.json'),cont,cp_rows(cp),set(expected))
    changed = {path:body for path,body in {**current,**bodies}.items() if prior.get(path)!=expected[path]}
    require(changed, 'No branch changes; duplicate publication refused')
    blobs, groups = transport_groups(changed)
    metadata = {'schema_version':1,'stage':args.mode,'scope':SCOPE,
        'source_checkpoint':BASE_COMMIT,'publication_parent':args.parent,
        'CAS_guards':{'expected_main':args.expected_main,'expected_root_tree':args.expected_root,
                      'expected_benchmarks_tree':args.expected_bench,'expected_scope_tree':args.expected_scope,
                      'expected_branch_sha':args.parent,'force':False},
        'source_filemap_sha256':sha(source_bytes),'prior_expected_sha256':sha(prior_bytes),
        'reviewed_files_sha256':sha(review_bytes),'historical_Git_leaves':len(baseline),
        'old_CP_rows':len(cp_rows(old_cp)),'new_CP_rows':len(cp_rows(cp)),
        'new_epoch25_public_files':len(current),'prior_Git_leaves':len(prior),
        'expected_Git_leaves':len(expected),'changed_files':[],
        'old_noncontrol_tuples_preserved':True,'old_CP_metadata_preserved':True,
        'inherited_archive_transport_unchanged':reconstruction,
        'Git_mutations':0,'native_or_model_or_corpus_calls':0,
        'controller_requirements':{'fresh_exact_guardian_and_FLOCK_before_every_mutation':True,
          'fresh_main_and_root_bench_siblings_invariance':True,'nonforce_parent_CAS':True,
          'actual_remote_readback_before_execution_admission_or_unlock':True},
        'large_blob_requests':[],'create_tree_groups':[],
        'transport_limits':{'blob_JSON_exclusive_bytes':MAX_BLOB_JSON,
                            'tree_JSON_exclusive_bytes':MAX_TREE_JSON,'tool_metadata_reserve_bytes':4096}}
    out.mkdir(mode=0o700);(out/'transport').mkdir(mode=0o700)
    for path,body in sorted(changed.items()):
        metadata['changed_files'].append({'path':path,'bytes':len(body),'sha256':sha(body),
                                          'git_blob_sha1':gitsha(body)})
    for number,(path,body,payload) in enumerate(blobs):
        filename='transport/blob-%03d.json'%number;data=encoded(payload);write(out/filename,data)
        metadata['large_blob_requests'].append({'path':path,'file':filename,'bytes':len(data),
                  'sha256':sha(data),'expected_blob_sha1':gitsha(body),'must_verify_before_tree':True})
    for number,group in enumerate(groups):
        filename='transport/tree-%03d.json'%number;data=encoded({'tree_elements':group})
        require(len(data)<MAX_TREE_JSON,'Serialized tree request cap exceeded');write(out/filename,data)
        metadata['create_tree_groups'].append({'file':filename,'bytes':len(data),
                                               'sha256':sha(data),'entries':len(group)})
    leaves=encoded({'schema_version':1,'scope':SCOPE,'source_checkpoint':BASE_COMMIT,
                    'files':[expected[path] for path in sorted(expected)]})
    write(out/'expected-leaves.json',leaves)
    metadata['expected_leaves']={'file':'expected-leaves.json','bytes':len(leaves),
                                  'sha256':sha(leaves),'count':len(expected)}
    write(out/'metadata.json',encoded(metadata,pretty=True))
    return {key:metadata[key] for key in ('stage','publication_parent','old_CP_rows','new_CP_rows',
             'new_epoch25_public_files','expected_Git_leaves','expected_leaves','Git_mutations')}


def main():
    cli=argparse.ArgumentParser(description=__doc__)
    for name in ('project','kit','source-filemap','controls-dir','out','reviewed-files','prior-expected'):
        cli.add_argument('--'+name,type=Path,required=True)
    cli.add_argument('--prior-controls-dir',type=Path)
    cli.add_argument('--mode',choices=['lease','source','final'],required=True)
    for name in ('parent','expected-main','expected-root','expected-bench','expected-scope'):
        cli.add_argument('--'+name,required=True)
    print(json.dumps(prepare(cli.parse_args()),sort_keys=True))

if __name__=='__main__':main()
