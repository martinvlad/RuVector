"""Outside-project, SOURCE-only bridge for one approved planning transition.

This infrastructure adapter does not change a frozen source, plan, control,
MUTABLE set, scientific gate, or publisher.  The original stager still performs
all input, history, source, CP, transport and expected-tree checks.  Exactly one
BASE->SOURCE history comparison additionally permits the already-approved
next_research_priority transition.  The PLANNING->SOURCE comparison is strict.

Importing this module defines functions only.  main() requires a hash-bound
independent source approval and reserves a single exclusive adapter attempt.
"""
from __future__ import annotations
import sys
sys.dont_write_bytecode = True
import argparse
import copy
from datetime import datetime, timezone
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import re
import stat
import time

ROOT = Path('/workspace/ruvector-epoch34-047dbc740dc2')
PROJECT = ROOT/'project'
STUDY = PROJECT/'experiments/sota-2026-10-22/epoch34'
PUB = STUDY/'publication'
OWN = Path('/workspace/ruvector-e34-publication-impl')
SELF = OWN/'source-stage-transition-adapter-v1.py'
AUDIT = Path('/workspace/ruvector-e34-independent-audit')
APPROVAL = AUDIT/'source-stage-transition-adapter-independent-v1.json'
INTENT = OWN/'source-stage-transition-adapter-intent-v1.json'
EXECUTION = OWN/'source-stage-transition-adapter-execution-v1.json'
PARENT = 'eafd332309fef5873086cf66c911b1787c320820'
TREES = {'root':'821b12fe6f0608aef0afe1dd77b27da3aa6f94b1',
         'bench':'889dcddc771c8712f6210a2a40fa9cb3df20a02d',
         'scope':'f229146613b61b3ca6b38cf8356d428efcf02802'}
PRIORITY = 'next_research_priority'
FROZEN_MODULES = {
    'publication_common_v1': (21658, 'a68994632a38966e15d9083eaa4947cb763b90ad49fd92083c4656caa2acffd8'),
    'phase_schema_v1': (4226, 'c4ed514a4c28fb5dc5bb07712320302f4e33c2f5b86280852eaed56b16bcdb90'),
    'phase_receipts_v1': (22954, '9c758eb573383cda7a8b07980851a33e557428615739ac041446d1fe4eb9be87'),
    'stage_publication_v1': (30200, '490c48353a154e94ea5a95cee36d5609157d888ca972255e1280d168562e9e5e'),
}
INPUTS = {
    ROOT/'kit/CONTINUATION.json': (225218, '10a20d9a31600302adf103fb8385fccaad3e24973f30049f2efd6fe1697f5c4f'),
    ROOT/'kit/CHECKPOINT_MANIFEST.json': (1045614, '2f8babb3303401fc904d51e8806c87d9c9254fe8c2dfc19e22d6f3e58a5abe03'),
    ROOT/'controls-lease/ACTIVE_RUN.json': (1530, '68e7e1b6734634e27f959fb0741684d27a3467fc5f771b0127cb7e623f83114c'),
    ROOT/'controls-lease/CONTINUATION.json': (228405, 'f95a80cdd6e45bf1635185c35d77550ee24a9e6c824ea6b78d491141393fb6de'),
    ROOT/'controls-source/ACTIVE_RUN.json': (1617, '2589dd5f07a99b57a15dc04cb54b27e54bfcc7992bc3b5a07b8083a765962249'),
    ROOT/'controls-source/CONTINUATION.json': (233626, '0550732771dfe07a61d8f318cec43cb7b45902d95f061e4dfbae583bf382eb99'),
    ROOT/'controls-source/CHECKPOINT_MANIFEST.json': (1086301, '4d87b4fcf7fa71061e143868e0b8f2fede634da50990e60aa2b06d0d63dcdba7'),
    ROOT/'reviewed-source-files.json': (40069, '5ecb3feef0515dca12be6ed5ec49592651324ed7080440da259beff1cc6c754f'),
    ROOT/'publication-source-filemap.json': (1449442, '1d6a40f13ac77d1e03eb50097cfe63566633c66edd39a18669796ce947e97f2d'),
    ROOT/'source-stage-prewrite-failure-v1.json': (2592, '373c904ad82b33ef66194259ba652602ccd9aa97f489745e262c478ce5f9ef77'),
    AUDIT/'planning-actual-readback-independent-v1.json': (3793, '9c995ea15a965c12fd63a4971300486d1e9934f97ff7d0d51a13d2dd3e6fea43'),
    AUDIT/'source-controls-independent-v1.json': (2078, 'ce6f93ec1ced35c8aace433b90393e204d279c6bd73d8729b70b43b93d062f2b'),
    STUDY/'plan.json': (61282, '53ea8a9341154b3a0612712c7e73fd56d56fba279bd4ec6343471f2c5e052839'),
    STUDY/'source-freeze.json': (41154, 'b9add85c349b8004141054dbadc15bce08338d6c187f53e9b6130323e304e0e9'),
}


def require(value, reason):
    if not value:
        raise ValueError(reason)


def canonical(path):
    path = Path(path).absolute()
    require(path == path.resolve() and not any(p.is_symlink() for p in (path, *path.parents)),
            'Canonical non-symlink path required: '+str(path))
    return path


def file_ref(path, expected=None):
    path = canonical(path)
    require(stat.S_ISREG(path.lstat().st_mode), 'Regular file required')
    body = path.read_bytes()
    row = {'path':str(path), 'bytes':len(body), 'sha256':hashlib.sha256(body).hexdigest()}
    if expected is not None:
        require((row['bytes'], row['sha256']) == tuple(expected), 'Pinned byte identity changed: '+str(path))
    return row


def parse(path):
    return json.loads(canonical(path).read_bytes())


def same_fact(left, right):
    if type(left) is not type(right):
        return False
    if isinstance(left, dict):
        return set(left) == set(right) and all(same_fact(left[key], right[key]) for key in left)
    if isinstance(left, list):
        return len(left) == len(right) and all(same_fact(a,b) for a,b in zip(left,right))
    return left == right


def fixed_arguments(expected_main):
    require(isinstance(expected_main, str) and re.fullmatch('[0-9a-f]{40}', expected_main),
            'Read-only current main observation must be a SHA; it is never a CAS gate')
    return argparse.Namespace(
        phase='source', project=PROJECT, kit=ROOT/'kit', controls=ROOT/'controls-source',
        priorcontrols=ROOT/'controls-lease', source_filemap=ROOT/'publication-source-filemap.json',
        reviewed_files=ROOT/'reviewed-source-files.json',
        parent_readback=AUDIT/'planning-actual-readback-independent-v1.json',
        out=ROOT/'stage-source', prior_expected=None, parent=PARENT,
        expected_main=expected_main, expected_root=TREES['root'],
        expected_bench=TREES['bench'], expected_scope=TREES['scope'])


class SourcePriorityBridge:
    """Exactly one narrow BASE exception, followed by the original parent check."""
    def __init__(self, original, baseline, planning, source, mutable):
        require(callable(original) and isinstance(mutable, set) and PRIORITY not in mutable,
                'Only the original SOURCE mutable set is eligible')
        require(all(isinstance(v, dict) and isinstance(v.get(PRIORITY), str)
                    for v in (baseline, planning, source)), 'Exact priority-bearing snapshots required')
        require(baseline[PRIORITY] != planning[PRIORITY]
                and source[PRIORITY] == planning[PRIORITY],
                'SOURCE must retain the exact authorized planning priority')
        self.original = original
        self.baseline, self.planning, self.source = map(copy.deepcopy, (baseline, planning, source))
        self.mutable = mutable.copy()
        self.trace = []

    def __call__(self, before, after, mutable):
        require(type(mutable) is set and mutable == self.mutable, 'Original SOURCE mutable set changed')
        require(same_fact(after, self.source), 'Only the exact hash-bound SOURCE snapshot is eligible')
        if not self.trace:
            require(same_fact(before, self.baseline), 'First comparison must be the exact hash-bound BASE snapshot')
            self.original(before, after, mutable | {PRIORITY})
            self.trace.append('BASE_TO_SOURCE_EXACT_APPROVED_PRIORITY_ONLY')
        elif len(self.trace) == 1:
            require(same_fact(before, self.planning), 'Second comparison must be the exact approved planning parent')
            self.original(before, after, mutable)
            self.trace.append('PLANNING_TO_SOURCE_ORIGINAL_STRICT_GUARD')
        else:
            raise ValueError('Unexpected extra history comparison; no broader allowance')

    def finish(self):
        require(self.trace == ['BASE_TO_SOURCE_EXACT_APPROVED_PRIORITY_ONLY',
                               'PLANNING_TO_SOURCE_ORIGINAL_STRICT_GUARD'],
                'Exactly one BASE exception and one unchanged parent comparison required')
        return {'BASE_priority_exceptions':1, 'normal_parent_comparisons':1,
                'global_MUTABLE_modified':False, 'trace':self.trace.copy()}


def bind_inputs():
    pins = [file_ref(path, expected) for path, expected in INPUTS.items()]
    baseline = parse(ROOT/'kit/CONTINUATION.json')
    planning = parse(ROOT/'controls-lease/CONTINUATION.json')
    source = parse(ROOT/'controls-source/CONTINUATION.json')
    plan = parse(STUDY/'plan.json')
    require(plan['epoch'] == 34 and plan['kind'] == 'REAL_NATIVE_LEXICAL_ANCHOR_NATIVE_COMPLEMENT_NLI_DIAGNOSTIC'
            and plan['publication_parent'] == PARENT and plan['publication_parent_trees'] == TREES
            and plan['publication_stage_paths']['source'] == str(ROOT/'stage-source'),
            'Frozen SOURCE phase, parent, trees or stage path differ')
    source_pins = plan['pins']
    require(isinstance(source_pins, list) and len(source_pins) == 195
            and len({row['path'] for row in source_pins}) == 195, 'Exact 195 frozen source identities required')
    for row in source_pins:
        require(isinstance(row, dict) and set(row) == {'path','bytes','sha256'}
                and isinstance(row['path'], str) and not Path(row['path']).is_absolute()
                and '\\' not in row['path'] and not any(p in ('','.','..') for p in row['path'].split('/')),
                'Canonical frozen relative source pin required')
        file_ref(PROJECT/row['path'], (row['bytes'],row['sha256']))
    parent = parse(AUDIT/'planning-actual-readback-independent-v1.json')
    require(parent.get('checks_passed') is True and parent.get('verified_actual_remote_readback') is True
            and parent['commit'] == PARENT and parent['parent'] == parent['sole_parent'] == '047dbc740dc2d4fdbdbad90ac167ebc64b31a49c'
            and all(parent[key] == value for key,value in TREES.items()),
            'Exact independent actual planning readback required')
    approval = parse(AUDIT/'source-controls-independent-v1.json')
    require(approval.get('checks_passed') is True and approval['parent'] == PARENT
            and approval['source_files_manifest'] == file_ref(ROOT/'reviewed-source-files.json'),
            'Exact independently approved SOURCE controls/inventory required')
    source_control_refs = [file_ref(ROOT/'controls-source'/name) for name in
                           ('ACTIVE_RUN.json','CONTINUATION.json','CHECKPOINT_MANIFEST.json')]
    require(approval['controls'] == source_control_refs, 'Approved SOURCE control byte identities differ')
    failure = parse(ROOT/'source-stage-prewrite-failure-v1.json')
    require(failure.get('phase') == 'source' and failure.get('actual_exit_code') == 1
            and failure.get('stage_output_directory_created') is False
            and failure.get('Git_mutations_by_failed_stage') == 0
            and failure.get('model_native_tokenizer_gold_calls') == 0
            and failure['BASE_next_research_priority'] == baseline[PRIORITY]
            and failure['approved_PLANNING_and_SOURCE_next_research_priority'] == planning[PRIORITY] == source[PRIORITY],
            'Original prewrite refusal provenance or approved transition differs')
    require(not os.path.lexists(ROOT/'stage-source'), 'SOURCE stage output already exists; no replay')
    return baseline, planning, source, pins


def load_frozen_stager():
    for name, expected in FROZEN_MODULES.items():
        require(name not in sys.modules, 'Fresh interpreter must not preload frozen publication modules')
        file_ref(PUB/(name+'.py'), expected)
    old_path = sys.path.copy()
    try:
        sys.path.insert(0, str(PUB))
        spec = importlib.util.spec_from_file_location('stage_publication_v1', PUB/'stage_publication_v1.py')
        stage = importlib.util.module_from_spec(spec)
        sys.modules['stage_publication_v1'] = stage
        spec.loader.exec_module(stage)
    finally:
        sys.path[:] = old_path
    for name, expected in FROZEN_MODULES.items():
        module = sys.modules[name]
        require(Path(module.__file__).absolute() == PUB/(name+'.py'), 'Unexpected imported publication module')
        file_ref(module.__file__, expected)
    return stage


def write_new(path, value):
    path = canonical(path)
    require(not os.path.lexists(path), 'Exclusive new adapter receipt required')
    with path.open('x', encoding='utf-8') as target:
        json.dump(value, target, ensure_ascii=False, allow_nan=False, indent=2)
        target.write('\n'); target.flush(); os.fsync(target.fileno())
    fd = os.open(path.parent, os.O_RDONLY | os.O_DIRECTORY)
    try: os.fsync(fd)
    finally: os.close(fd)


def main(argv=None):
    cli = argparse.ArgumentParser(description=__doc__)
    cli.add_argument('--expected-main', required=True)
    options = cli.parse_args(argv)
    require(Path(__file__).absolute() == SELF and canonical(SELF) == SELF,
            'Only the independently reviewed outside-project adapter may run')
    args = fixed_arguments(options.expected_main)
    require(not os.path.lexists(INTENT) and not os.path.lexists(EXECUTION),
            'Adapter already attempted; stop rather than replay')
    independent = parse(APPROVAL)
    require(independent.get('checks_passed') is True and independent.get('adapter') == file_ref(SELF),
            'Hash-bound independent adapter source approval required before execution')
    baseline, planning, source, pins = bind_inputs()
    stage = load_frozen_stager()
    stage.live_owner(ROOT)
    original = stage.preserve_history
    strict_mutable = stage.MUTABLE.copy()
    bridge = SourcePriorityBridge(original, baseline, planning, source, stage.MUTABLE)
    write_new(INTENT, {'schema_version':1, 'epoch':34, 'phase':'source', 'publication_only':True,
        'parent':PARENT, 'adapter':file_ref(SELF), 'independent_approval':file_ref(APPROVAL),
        'frozen_input_pins':pins, 'before_stage_prepare':True, 'further_adapter_attempts':0,
        'created_at':datetime.now(timezone.utc).isoformat(), 'model_native_tokenizer_gold_Git_calls':0})
    started = time.monotonic()
    stage.preserve_history = bridge
    try:
        result = stage.prepare(args)
        observation = bridge.finish()
        require(stage.MUTABLE == strict_mutable, 'Global original SOURCE MUTABLE set changed')
        for path, expected in INPUTS.items(): file_ref(path, expected)
        for row in parse(STUDY/'plan.json')['pins']:
            file_ref(PROJECT/row['path'], (row['bytes'],row['sha256']))
    except BaseException as error:
        write_new(EXECUTION, {'schema_version':1, 'epoch':34, 'phase':'source', 'status':'FAILED_NO_REPLAY',
            'error_type':type(error).__name__, 'error':str(error), 'history_trace':bridge.trace,
            'stage_output_exists':os.path.lexists(args.out), 'further_adapter_attempts':0,
            'wall_seconds':time.monotonic()-started, 'model_native_tokenizer_gold_Git_calls':0})
        raise
    finally:
        stage.preserve_history = original
    receipt = {'schema_version':1, 'epoch':34, 'phase':'source', 'status':'SOURCE_STAGE_CREATED_PUBLICATION_TRANSITION_ONLY',
        'result':result, 'history_comparisons':observation, 'adapter':file_ref(SELF),
        'intent':file_ref(INTENT), 'independent_approval':file_ref(APPROVAL),
        'metadata':file_ref(args.out/'metadata.json'), 'expected_leaves':file_ref(args.out/'expected-leaves.json'),
        'frozen_plan_source_and_control_bytes_unchanged':True, 'scientific_retry':False,
        'wall_seconds':time.monotonic()-started, 'further_adapter_attempts':0,
        'model_native_tokenizer_gold_Git_calls':0}
    write_new(EXECUTION, receipt)
    print(json.dumps(receipt, sort_keys=True))


if __name__ == '__main__':
    main()
