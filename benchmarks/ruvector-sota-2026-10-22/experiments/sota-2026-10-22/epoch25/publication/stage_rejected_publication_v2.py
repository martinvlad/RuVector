"""Stage only the exact failed epoch25 incident as a rejected final publication.

All Git mutations remain the external controller's responsibility. The frozen
source publisher remains unchanged and still rejects this offline counter.
"""
from __future__ import annotations
import sys
sys.dont_write_bytecode = True
import argparse
import json
from pathlib import Path
from publication_rejection_v2 import prepare_rejected


def main():
    cli = argparse.ArgumentParser(description=__doc__)
    for name in ('project','kit','source-filemap','controls-dir','out',
                 'reviewed-files','prior-expected'):
        cli.add_argument('--'+name, type=Path, required=True)
    cli.add_argument('--prior-controls-dir', type=Path, required=True)
    cli.add_argument('--mode', choices=['final'], required=True)
    for name in ('parent','expected-main','expected-root','expected-bench','expected-scope'):
        cli.add_argument('--'+name, required=True)
    print(json.dumps(prepare_rejected(cli.parse_args()), sort_keys=True))


if __name__ == '__main__':
    main()
