#!/usr/bin/env python3
"""Validate the archive and reject loss relative to a committed baseline."""

import argparse
import json
from pathlib import Path
import subprocess

from archive import assert_preserved, validate_archive


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--base-ref', help='Git commit/ref whose inspection identities must survive')
    parser.add_argument('--archive', default='data/violations_latest.json')
    args = parser.parse_args()
    current = json.loads(Path(args.archive).read_text())
    validate_archive(current)
    if args.base_ref:
        baseline = json.loads(subprocess.check_output(
            ['git', 'show', f'{args.base_ref}:{args.archive}'], text=True,
        ))
        assert_preserved(baseline, current)
    print(f'Archive validated: {len(current)} unique inspections; baseline preserved')


if __name__ == '__main__':
    main()
