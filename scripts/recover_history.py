#!/usr/bin/env python3
"""Recover the audited February 2026 loss from immutable Git sources."""

import argparse
import json
from pathlib import Path
import subprocess

from archive import inspection_key, merge_archive, write_json
from build_dataset import DatasetBuilder
from normalize import ABQNormalizer


# Last archive before the February 13 name/date deduplication rewrite.
ARCHIVE_REF = '8942a6cd2b102b53e9a070b66f2521e87755a120'
ARCHIVE_PATH = 'data/violations_latest.json'
# Corrected raw parser output; do not replay the initial obsolete failed labels.
RAW_REF = 'd822f3c786680e24f9d2431d571dfd2c65108820'
RAW_PATH = 'data/abq_2026_08.json'


def read_git_json(ref, path):
    return json.loads(subprocess.check_output(['git', 'show', f'{ref}:{path}'], text=True))


def recover(existing, historical, raw):
    # Previously archived records keep their original values and stored scores.
    restored = merge_archive(existing, historical)
    historical_count = len(restored) - len(existing)
    normalized = []
    for record in raw:
        result = ABQNormalizer.normalize(record)
        if result is None:
            raise ValueError('Recovery normalization failed')
        normalized.append(result)
    merged = merge_archive(restored, normalized)
    return merged, historical_count, len(merged) - len(restored)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', default='data')
    parser.add_argument('--apply', action='store_true', help='Write the archive and regenerated manifest')
    args = parser.parse_args()
    output = Path(args.output)
    existing = json.loads((output / 'violations_latest.json').read_text())
    merged, historical_count, raw_count = recover(
        existing, read_git_json(ARCHIVE_REF, ARCHIVE_PATH), read_git_json(RAW_REF, RAW_PATH),
    )
    print(f'Recoverable: {historical_count} archived + {raw_count} raw; {len(merged)} total inspections')
    existing_keys = {inspection_key(record) for record in existing}
    for record in merged:
        if inspection_key(record) not in existing_keys:
            print(record['inspection']['date'], record['inspection']['outcome'], record['establishment']['name'])
    if args.apply:
        write_json(output / 'violations_latest.json', merged)
        write_json(output / 'manifest.json', DatasetBuilder(str(output)).generate_manifest(merged))
        print('Recovery applied; existing values preserved and IDs migrated')
    else:
        print('Dry run; pass --apply to write')


if __name__ == '__main__':
    main()
