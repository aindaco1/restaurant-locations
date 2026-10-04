"""Stable inspection identity and lossless archive merging."""

from collections import Counter
from copy import deepcopy
from datetime import date
import hashlib
import json
from pathlib import Path
import os
import tempfile


def canonical(value):
    """Ignore case and incidental whitespace, without guessing address aliases."""
    if not isinstance(value, str):
        raise ValueError('Inspection identity fields must be strings')
    return ' '.join(value.casefold().split())


def inspection_key(record):
    establishment, inspection = record['establishment'], record['inspection']
    date.fromisoformat(inspection['date'])
    return tuple(canonical(value) for value in (
        record['source'], establishment['name'], establishment['address'],
        establishment['city'], inspection['date'], inspection['outcome'],
    ))


def record_id(record):
    key = inspection_key(record)
    digest = hashlib.sha256(json.dumps(key, ensure_ascii=True).encode()).hexdigest()[:20]
    return f'{key[0]}:v2:{digest}'


def validate_archive(records, *, require_current_ids=True):
    # Import here so the normalizers can share record_id without an import cycle.
    from normalize import ViolationRecord

    if not isinstance(records, list):
        raise ValueError('Archive must be a JSON array')
    keys, ids = set(), set()
    for index, record in enumerate(records):
        ViolationRecord(**record)
        key = inspection_key(record)
        if key in keys:
            raise ValueError(f'Duplicate inspection identity at record {index}: {key}')
        keys.add(key)
        if require_current_ids:
            if record['id'] != record_id(record) or record['id'] in ids:
                raise ValueError(f'Invalid or duplicate inspection ID at record {index}')
            ids.add(record['id'])


def assert_preserved(before, after):
    """Catch removal of an outcome even when total record counts grow."""
    missing = Counter(map(inspection_key, before)) - Counter(map(inspection_key, after))
    if missing:
        examples = list(missing)[:3]
        raise ValueError(f'Archive lost {sum(missing.values())} inspection(s): {examples}')


def merge_archive(existing, incoming):
    """Retain existing values, migrate IDs, append unseen inspection identities."""
    validate_archive(existing, require_current_ids=False)
    merged = deepcopy(existing)
    seen = {inspection_key(record) for record in merged}
    for record in incoming:
        key = inspection_key(record)
        if key not in seen:
            merged.append(deepcopy(record))
            seen.add(key)
    for record in merged:
        record['id'] = record_id(record)
    validate_archive(merged)
    assert_preserved(existing, merged)
    return merged


def write_json(path, data):
    """Replace a complete JSON file, never truncate the live archive in place."""
    path = Path(path)
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(mode='w', dir=path.parent, delete=False) as stream:
            temporary = Path(stream.name)
            json.dump(data, stream, indent=2)
            stream.flush()
            os.fsync(stream.fileno())
        temporary.replace(path)
    finally:
        if temporary and temporary.exists():
            temporary.unlink()
