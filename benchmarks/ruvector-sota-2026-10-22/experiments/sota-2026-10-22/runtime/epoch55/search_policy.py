"""E55 exact absent interpreter-ZIP search policy, preserving all I/O denies.

This avoids repeated metadata discovery probes against one demonstrated absent
interpreter archive. It neither opens an archive nor permits a suffix denied by
io_guard. Existing files, a changed interpreter/path identity, or an out-of-prefix
canonical path fail closed. There is no general sys.path cleanup.
"""
import hashlib
import os
from pathlib import Path
import sys
from io_guard import path_fingerprint, remove_exact_absent_zip_paths


def canonical_fingerprint(path):
    value = path_fingerprint(path)
    canonical = os.path.realpath(path)
    base = os.path.realpath(sys.base_prefix)
    value.update(canonical_path_sha256=hashlib.sha256(os.fsencode(canonical)).hexdigest(),
                 canonical_interpreter_base_prefix_sha256=hashlib.sha256(os.fsencode(base)).hexdigest(),
                 canonical_inside_interpreter_base_prefix=(os.path.isabs(path)
                    and os.path.commonpath([canonical, base]) == base),
                 standard_interpreter_zip_basename=(os.path.basename(path)
                    == 'python%d%d.zip' % sys.version_info[:2]))
    return value


def apply_exact_absent_interpreter_zip_policy(policy):
    if not (type(policy) is dict and policy.get('kind') == 'REMOVE_EXACT_PROVEN_ABSENT_INTERPRETER_ZIP_SEARCH_ENTRY'
            and policy.get('archive_access_authorized') is False
            and policy.get('suffix_denies_unchanged') is True
            and len(policy.get('entries', [])) == 1):
        raise ValueError('EXACT_ABSENT_INTERPRETER_ZIP_POLICY')
    receipts = []
    for row in policy['entries']:
        index = row['sys_path_index']
        if type(index) is not int or not 0 <= index < len(sys.path):
            raise ValueError('EXACT_INTERPRETER_ZIP_SEARCH_INDEX')
        observed = canonical_fingerprint(sys.path[index])
        if not (observed['path_sha256'] == row['path_sha256']
                and observed['canonical_path_sha256'] == row['canonical_path_sha256']
                and observed['canonical_interpreter_base_prefix_sha256'] == row['canonical_interpreter_base_prefix_sha256']
                and observed['exists'] is False and observed['suffix'] == '.zip'
                and observed['inside_interpreter_base_prefix'] is True
                and observed['canonical_inside_interpreter_base_prefix'] is True
                and observed['standard_interpreter_zip_basename'] is True):
            raise ValueError('EXACT_ABSENT_INTERPRETER_ZIP_CANONICAL_IDENTITY')
        receipts.append({'sys_path_index': index, **observed})
    result = remove_exact_absent_zip_paths(policy['entries'])
    return {'policy_kind': policy['kind'], 'canonical_before_removal': receipts,
            'removal_receipt': result, 'all_suffix_matching_opens_still_denied': True,
            'science_runtime_imports_before_policy': 0,
            'scope': 'Search-policy remedy for actual E55 metadata probe; no retroactive E54 target attribution.'}
