"""Add explicit authoritative review/correction links to derived final controls.
Reporting metadata only: retain original rendered controls and every immutable
research artifact, and create a new external control directory.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path

P = 'experiments/sota-2026-10-22/'
NAMES = {'ACTIVE_RUN.json', 'CONTINUATION.json', 'CHECKPOINT_MANIFEST.json'}


def canonical(p, directory=False):
    p = p.absolute()
    assert p == p.resolve() and not any(x.is_symlink() for x in [p, *p.parents])
    assert p.is_dir() if directory else p.is_file()
    return p


def main():
    ap = argparse.ArgumentParser()
    for n in ('project', 'controls', 'out'): ap.add_argument('--' + n, type=Path, required=True)
    a = ap.parse_args(); root = canonical(a.project, True); old = canonical(a.controls, True)
    out = a.out.absolute()
    assert not out.exists() and out == out.resolve()
    assert not any(x.is_symlink() for x in [out, *out.parents])
    assert not out.is_relative_to(root) and out.parent == old.parent
    assert {p.name for p in old.iterdir()} == NAMES
    blobs = {n: canonical(old / n).read_bytes() for n in NAMES}
    c = json.loads(blobs['CONTINUATION.json'])
    before = json.loads(blobs['CONTINUATION.json'])
    assert c['active_run']['experiments_active'] is False and c['active_run']['native_allowed'] == 0
    assert c['epoch20_final']['all_slots_closed'] is True
    def ref(name):
        b = canonical(root / (P + name)).read_bytes()
        return {'path': P + name, 'bytes': len(b), 'sha256': hashlib.sha256(b).hexdigest()}
    assert c['epoch20_final']['manifest'] == ref('epoch20/EPOCH_MANIFEST.json')
    review_name = 'audit/epoch20/final-record-consistency-independent-v2.json'
    review = json.loads((root / (P + review_name)).read_text())
    assert review['checks_passed'] is True
    correction_name = 'epoch20/post-assembly-narrative-correction-v1.json'
    correction = json.loads((root / (P + correction_name)).read_text())
    analysis_name = 'audit/epoch20/failure-analysis-independent-v2.json'
    assert correction['immutable_epoch_manifest'] == c['epoch20_final']['manifest']
    assert correction['authoritative_narrative'] == ref(analysis_name)
    additions = {
        'independent_final_record_review': ref(review_name),
        'authoritative_failure_analysis': ref(analysis_name),
        'append_only_narrative_correction': ref(correction_name),
    }
    assert not set(additions).intersection(c['epoch20_final'])
    c['epoch20_final'].update(additions)
    stripped = json.loads(json.dumps(c))
    for k in additions: del stripped['epoch20_final'][k]
    assert stripped == before
    blobs['CONTINUATION.json'] = (json.dumps(c, ensure_ascii=False, indent=2, allow_nan=False) + '\n').encode()
    out.mkdir(mode=0o700)
    for n, b in blobs.items():
        with (out / n).open('xb') as f: f.write(b); f.flush(); os.fsync(f.fileno())
    print(json.dumps({'status': 'ADDITIVE_FINAL_REVIEW_LINKS_ONLY', 'controls': str(out),
                      'new_links': additions, 'native_model_calls': 0}))


if __name__ == '__main__': main()

