"""Stdlib-only independent replay of immutable epoch22 worker evidence.

No candidate, tokenizer, framework, native module or dataset code is imported.
Gold is optional and may only be joined after a complete sealed corpus process.
"""
from __future__ import annotations
import argparse
from collections import Counter
from datetime import datetime, timezone
import hashlib
import json
import math
import os
from pathlib import Path, PurePosixPath
import re
import metrics as M

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
PREFIX = 'experiments/sota-2026-10-22/'
PROTOCOL = HERE / 'protocol.json'
SOURCE = 'c7823614cd5bc59f031445b55682f59230dc1901'
MODEL = 'MoritzLaurer/DeBERTa-v3-large-mnli-fever-anli-ling-wanli'
REVISION = 'b3546ea6b0346eb6f8d5d68b13c7dc6d0376b3d7'
BINARY_SHA = 'ff559e9fac2e3d29a8b32e890fdb047bcd4bd28f389b4731ad72148b221d5a2e'
NATIVE_SCRIPT_SHA = '45efc7fecd2d249aea7bd1f5e7d36bf26cfe57cd6f91de51ffd15adc039ec4a3'
SHA = re.compile(r'^[0-9a-f]{64}$')
NUMBER = re.compile(r'(?<!\w)[+-]?\d+(?:[.,]\d+)*(?:\s*%|\b)')
demand = M.demand


def canonical(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':'), allow_nan=False).encode()


def digest(raw): return hashlib.sha256(raw).hexdigest()


def identity(path, relative=None):
    p = Path(path); b = p.read_bytes()
    return {'path': relative or str(p), 'bytes': len(b), 'sha256': digest(b)}


def read(path): return json.loads(Path(path).read_bytes())


def member(relative, root=ROOT):
    demand(type(relative) is str and relative and '\\' not in relative and not PurePosixPath(relative).is_absolute()
           and all(x not in ('', '.', '..') for x in relative.split('/')), 'safe relative source path required')
    p = Path(root) / relative
    demand(not any(x.is_symlink() for x in [p, *p.parents]) and p.is_file(), 'regular nonsymlink source required: ' + relative)
    return p


def integer(value, minimum=0):
    demand(type(value) is int and value >= minimum, 'literal integer required')
    return value


def duration(value):
    n = M.real(value); demand(n >= 0, 'nonnegative measured duration/resource required'); return n


def sha_value(value):
    demand(type(value) is str and SHA.fullmatch(value), 'actual SHA256 identity required'); return value


