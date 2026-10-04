"""Regression coverage for same-day outcome loss and archive corruption."""

from copy import deepcopy
import json
from pathlib import Path
import sys

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))
from archive import assert_preserved, merge_archive, record_id, validate_archive, write_json
from normalize import ABQNormalizer, normalize_dataset
from recover_history import recover
from test_build_dataset import make_record


def test_legacy_id_collision_preserves_both_outcomes_and_locations():
    approved = make_record('same-legacy-id', '2026-01-09', severity=0)
    approved['inspection']['outcome'] = 'approved'
    conditional = deepcopy(approved)
    conditional['inspection']['outcome'] = 'conditional'
    conditional['score']['severity'] = 2
    other_location = deepcopy(conditional)
    other_location['establishment']['address'] = '456 Other St'
    original = deepcopy([approved, conditional, other_location])
    merged = merge_archive([approved, conditional], [other_location, conditional, other_location])
    assert len(merged) == len({row['id'] for row in merged}) == 3
    for before, after in zip(original, merged):
        assert {k: v for k, v in before.items() if k != 'id'} == {k: v for k, v in after.items() if k != 'id'}
    assert [approved, conditional, other_location] == original
    assert merge_archive(merged, original) == merged


def test_later_same_day_outcome_is_appended_without_rescoring_existing():
    existing = make_record('legacy', '2026-01-09', severity=3)
    updated = deepcopy(existing)
    updated['score']['severity'] = 0
    followup = deepcopy(updated)
    followup['inspection']['outcome'] = 'approved'
    merged = merge_archive([existing], [updated, followup])
    assert len(merged) == 2
    assert merged[0]['score']['severity'] == 3
    assert merged[1]['inspection']['outcome'] == 'approved'


def test_ids_ignore_case_and_whitespace_but_distinguish_identity_fields():
    record = make_record('A Restaurant', '2026-01-09')
    variant = deepcopy(record)
    variant['establishment']['name'] = '  a   RESTAURANT '
    assert record_id(record) == record_id(variant)
    for section, field, value in (
        ('establishment', 'address', 'Another address'),
        ('establishment', 'city', 'Another city'),
        ('inspection', 'outcome', 'approved'),
        ('inspection', 'date', '2026-01-10'),
    ):
        variant = deepcopy(record)
        variant[section][field] = value
        assert record_id(record) != record_id(variant)


def test_guard_catches_lost_outcome_even_if_total_grows():
    before = make_record('legacy', '2026-01-09')
    approved = deepcopy(before)
    approved['inspection']['outcome'] = 'approved'
    replacement = merge_archive([], [approved, make_record('new', '2026-02-01')])
    with pytest.raises(ValueError, match='Archive lost 1'):
        assert_preserved([before], replacement)
    assert_preserved([before], merge_archive([before], replacement))


def test_validator_rejects_duplicate_identity_and_invalid_id():
    records = merge_archive([], [make_record('legacy', '2026-01-09')])
    with pytest.raises(ValueError, match='Duplicate inspection identity'):
        validate_archive(records + records)
    records[0]['id'] = 'legacy'
    with pytest.raises(ValueError, match='Invalid or duplicate inspection ID'):
        validate_archive(records)


def test_failed_json_write_preserves_original_and_removes_temporary_file(tmp_path):
    path = tmp_path / 'archive.json'
    path.write_text('["original"]')
    with pytest.raises(TypeError):
        write_json(path, [object()])
    assert path.read_text() == '["original"]'
    assert list(tmp_path.iterdir()) == [path]


def test_normalization_refuses_partial_fetch(tmp_path):
    path = tmp_path / 'raw.json'
    path.write_text(json.dumps([
        {'name': 'Test', 'address': 'A', 'date': '2026-01-09', 'outcome': 'closed'},
        {'name': 'Broken record'},
    ]))
    with pytest.raises(ValueError, match='refusing partial archive'):
        normalize_dataset(abq_file=str(path))


def test_recovery_is_idempotent_and_preserves_historical_values():
    approved = make_record('legacy', '2026-01-09', severity=0)
    approved['inspection']['outcome'] = 'approved'
    lost = deepcopy(approved)
    lost['inspection']['outcome'] = 'conditional'
    lost['score']['severity'] = 2
    lost['inspection']['violations'] = [{'code': '1', 'critical': False, 'desc': 'Historical evidence'}]
    raw = {'name': 'Raw only', 'address': 'B', 'date': '2026-02-06', 'outcome': 'failed'}
    merged, historical_count, raw_count = recover([approved], [approved, lost], [raw])
    assert (historical_count, raw_count, len(merged)) == (1, 1, 3)
    assert merged[1]['inspection'] == lost['inspection']
    assert merged[1]['score'] == lost['score']
    assert merged[2] == ABQNormalizer.normalize(raw)
    repeated, historical_count, raw_count = recover(merged, [approved, lost], [raw])
    assert repeated == merged
    assert (historical_count, raw_count) == (0, 0)
