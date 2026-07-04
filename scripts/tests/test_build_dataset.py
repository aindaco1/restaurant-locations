#!/usr/bin/env python3
"""
Unit tests for dataset build orchestration
"""

import json
import sys
from pathlib import Path

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
