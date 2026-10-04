#!/usr/bin/env python3
"""
Unit tests for dataset build orchestration
"""

import json
import sys
from pathlib import Path
import pytest

# Add scripts to path
sys.path.insert(0, str(Path(__file__).parent.parent))

import build_dataset


def make_record(record_id, date, severity=2.0, city='Albuquerque'):
    """Create a minimal normalized record."""
    return {
        'id': record_id,
        'source': 'ABQ',
        'operational_status': 'Open',
        'establishment': {
            'name': record_id,
            'address': '123 Test St',
            'city': city,
            'county': 'Bernalillo',
            'geo': {'lat': 35.0844, 'lng': -106.6504},
        },
        'inspection': {
            'date': date,
            'type': 'routine',
            'outcome': 'conditional',
            'writeup': '',
            'violations': [],
        },
        'score': {
            'severity': severity,
            'reasons': ['conditional/failed within 180d'],
        },
        'links': {
            'source': 'https://www.cabq.gov/environmentalhealth',
            'document': None,
        },
    }


class FakeScraper:
    """Avoid network and PDF parsing in orchestration tests."""

    def fetch_all_inspections(self):
        return [{'name': 'NEW RECORD'}]

    def save_raw_data(self, records, output_dir):
        path = Path(output_dir) / 'abq_fake.json'
        path.write_text(json.dumps(records))
        return str(path)


def test_pipeline_manifest_describes_merged_latest_dataset(tmp_path, monkeypatch):
    data_dir = tmp_path / 'data'
    data_dir.mkdir()

    existing_record = make_record('existing-record', '2026-06-01', severity=3.0)
    latest_file = data_dir / 'violations_latest.json'
    latest_file.write_text(json.dumps([existing_record]))

    new_record = make_record('new-record', '2026-07-01', severity=2.0)

    monkeypatch.setattr(build_dataset, 'ABQPDFScraper', lambda: FakeScraper())
    monkeypatch.setattr(
        build_dataset,
        'normalize_dataset',
        lambda nmed_file, abq_file: [new_record],
    )

    builder = build_dataset.DatasetBuilder(str(data_dir))
    builder.run_pipeline()

    latest = json.loads(latest_file.read_text())
    manifest = json.loads((data_dir / 'manifest.json').read_text())

    assert len(latest) == 2
    assert manifest['total_records'] == 2
    assert manifest['datasets']['latest']['records'] == 2
    assert manifest['cities']['Albuquerque'] == 2


@pytest.mark.parametrize('failure', ['corrupt_archive', 'empty_fetch', 'fetch_error', 'normalize_error'])
def test_failed_refresh_preserves_all_existing_files(tmp_path, monkeypatch, failure):
    archive = [make_record('existing', '2026-01-09')]
    files = {
        'violations_latest.json': '{broken' if failure == 'corrupt_archive' else json.dumps(archive),
        'manifest.json': '{"original": true}',
        'abq_fake.json': '["original raw"]',
        'snapshots/violations_previous.json': '["original snapshot"]',
    }
    for name, content in files.items():
        path = tmp_path / name
        path.parent.mkdir(exist_ok=True)
        path.write_text(content)

    class FailingScraper(FakeScraper):
        def fetch_all_inspections(self):
            if failure == 'corrupt_archive':
                pytest.fail('Must reject corrupted archive before fetching')
            if failure == 'fetch_error':
                raise RuntimeError('Source unavailable')
            return [] if failure == 'empty_fetch' else super().fetch_all_inspections()

    monkeypatch.setattr(build_dataset, 'ABQPDFScraper', FailingScraper)
    # The fake fetch is intentionally not a valid raw record, so actual
    # normalization raises instead of silently dropping it.
    with pytest.raises((ValueError, RuntimeError)):
        build_dataset.DatasetBuilder(str(tmp_path)).run_pipeline()
    assert {str(path.relative_to(tmp_path)): path.read_text() for path in tmp_path.rglob('*.json')} == files
