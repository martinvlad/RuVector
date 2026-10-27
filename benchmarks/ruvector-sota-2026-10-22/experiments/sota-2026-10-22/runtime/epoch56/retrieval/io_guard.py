"""Bounded deny-before-I/O evidence; no model, tokenizer or native imports.

No denied pathname is emitted. SHA256 identifies exact pathname bytes, and
stat-only classification plus standard-library frames describe each attempt.
The guard never allows a matching suffix, including after path remediation.
"""
import hashlib
import os
from pathlib import Path
import stat
import sys

SUFFIXES = ('.safetensors', '.bin', '.pt', '.pth', '.zip')
SAFE_MODULES = {'__main__', 'io_guard', 'worker', 'pathlib', 'os', 'zipfile',
                'importlib.metadata', 'importlib.metadata._adapters',
                'importlib.abc', 'importlib._bootstrap',
                'importlib._bootstrap_external'}


def path_fingerprint(path):
    raw = os.fsencode(path)
    value = {'path_sha256': hashlib.sha256(raw).hexdigest(),
             'suffix': next((x for x in SUFFIXES if os.fsdecode(raw).endswith(x)), None),
             'path_is_absolute': os.path.isabs(path),
             'inside_interpreter_base_prefix': (os.path.isabs(path)
                 and os.path.commonpath([os.path.abspath(path), os.path.abspath(sys.base_prefix)])
                 == os.path.abspath(sys.base_prefix))}
    try:
        s = os.stat(path, follow_symlinks=False)
        value.update(exists=True, is_directory=stat.S_ISDIR(s.st_mode),
                     is_regular=stat.S_ISREG(s.st_mode), is_symlink=stat.S_ISLNK(s.st_mode))
    except FileNotFoundError:
        value.update(exists=False, is_directory=False, is_regular=False, is_symlink=False)
    except OSError as exc:
        value.update(exists=None, stat_errno=exc.errno)
    return value


class DeniedOpenAudit:
    def __init__(self, counters, maximum_events=64):
        self.counters = counters
        self.maximum_events = maximum_events
        self.stage = 'installed'
        self.events = []
        self.overflow = 0

    def set_stage(self, value):
        self.stage = value

    def __call__(self, event, args):
        if event != 'open' or not args or not isinstance(args[0], (str, bytes, os.PathLike)):
            return
        path = os.fsdecode(args[0])
        if not path.endswith(SUFFIXES):
            return
        self.counters['forbidden_model_or_archive_file_access_attempts'] += 1
        if len(self.events) < self.maximum_events:
            row = path_fingerprint(path)
            row.update(stage=self.stage, denied_before_OS_open=True,
                       sys_path_indices=[i for i, x in enumerate(sys.path) if x == path])
            frame = sys._getframe(1)
            frames = []
            for _ in range(16):
                if frame is None:
                    break
                module = str(frame.f_globals.get('__name__', ''))
                frames.append({'module': module if module in SAFE_MODULES else 'OTHER_MODULE',
                               'function': frame.f_code.co_name if module in SAFE_MODULES else 'REDACTED'})
                frame = frame.f_back
            row['frames'] = frames
            self.events.append(row)
        else:
            self.overflow += 1
        raise RuntimeError('ENGINEERING_MODEL_WEIGHTS_AND_CORPUS_ARCHIVES_FORBIDDEN')

    def receipt(self):
        return {'schema_version': 1, 'deny_before_OS_open': True,
                'suffixes': list(SUFFIXES), 'events': self.events,
                'event_overflow': self.overflow,
                'denied_attempts': self.counters['forbidden_model_or_archive_file_access_attempts']}


def remove_exact_absent_zip_paths(expected):
    """Remove only previously frozen, absent .zip search entries, never allow I/O.

    Existing ZIP files, symlinks, directories and entries not exactly identified
    by frozen index and pathname SHA are rejected. No archive is opened.
    """
    original = list(sys.path)
    removed = []
    for row in expected:
        i = row['sys_path_index']
        if type(i) is not int or not 0 <= i < len(original):
            raise ValueError('FROZEN_ABSENT_ZIP_INDEX')
        path = original[i]
        observed = path_fingerprint(path)
        if not (observed['path_sha256'] == row['path_sha256']
                and observed['suffix'] == '.zip' and observed['path_is_absolute']
                and observed['inside_interpreter_base_prefix']
                and observed['exists'] is False):
            raise ValueError('FROZEN_ABSENT_ZIP_IDENTITY_AND_STAT')
        removed.append({'sys_path_index': i, **observed})
    if len({r['sys_path_index'] for r in removed}) != len(removed):
        raise ValueError('UNIQUE_ABSENT_ZIP_PATHS')
    indices = {r['sys_path_index'] for r in removed}
    sys.path[:] = [x for i, x in enumerate(original) if i not in indices]
    return {'removed': removed, 'only_absent_search_entries_removed': True,
            'guard_suffixes_unchanged': list(SUFFIXES), 'archive_open_authorized': False}
