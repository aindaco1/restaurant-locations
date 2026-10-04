"""Scraper identity and failure behavior independent of network availability."""

from copy import deepcopy
from contextlib import nullcontext
from pathlib import Path
import sys
from types import SimpleNamespace

import pytest
import requests

sys.path.insert(0, str(Path(__file__).parent.parent))
from scrape_abq import ABQPDFScraper
import scrape_abq


def test_same_day_outcomes_and_separate_addresses_survive_fetch(monkeypatch):
    scraper = ABQPDFScraper()
    records = scraper._parse_summary_page('''TEST CAFE - 123 Main St
01/09/2026 Approved
01/09/2026 Conditional Approved
TEST CAFE - 456 Other St
01/09/2026 Closure Re-Inspection Required
TEST CAFE - 789 Third St
01/09/2026 Approved
''')
    detailed = deepcopy(records[1])
    detailed['violations'] = [{'category': 'Hand washing', 'observation': 'Observed evidence'}]
    monkeypatch.setattr(scraper, 'find_recent_pdfs', lambda weeks: ['fake.pdf'])
    monkeypatch.setattr(scraper, 'parse_pdf', lambda url: records + [detailed])
    result = scraper.fetch_all_inspections()
    assert [(r['address'], r['outcome']) for r in result] == [
        ('123 Main St', 'approved'), ('123 Main St', 'conditional'), ('456 Other St', 'closed'),
    ]
    assert result[1]['violations'] == detailed['violations']


def test_download_failure_is_not_an_empty_success(monkeypatch):
    scraper = ABQPDFScraper()
    def unavailable(*args, **kwargs):
        raise requests.HTTPError('503')
    monkeypatch.setattr(scraper.session, 'get', unavailable)
    with pytest.raises(requests.HTTPError):
        scraper.parse_pdf('https://example.test/report.pdf')


def test_pdf_summary_dedup_keeps_same_outcome_at_distinct_addresses(monkeypatch):
    scraper = ABQPDFScraper()
    text = '''TEST CAFE - 123 Main St
01/09/2026 Conditional Approved
TEST CAFE - 456 Other St
01/09/2026 Conditional Approved
01/09/2026 Approved
'''
    page = SimpleNamespace(extract_text=lambda: text)
    pdf = SimpleNamespace(pages=[page, page])
    response = SimpleNamespace(content=b'fixture', raise_for_status=lambda: None)
    monkeypatch.setattr(scraper.session, 'get', lambda *args, **kwargs: response)
    monkeypatch.setattr(scrape_abq.pdfplumber, 'open', lambda stream: nullcontext(pdf))
    records = scraper.parse_pdf('https://example.test/report.pdf')
    assert [(r['address'], r['outcome']) for r in records] == [
        ('123 Main St', 'conditional'), ('456 Other St', 'conditional'), ('456 Other St', 'approved'),
    ]


def test_empty_raw_fetch_does_not_create_or_replace_file(tmp_path):
    path = tmp_path / 'preserved.json'
    path.write_text('["evidence"]')
    with pytest.raises(ValueError, match='empty fetch'):
        ABQPDFScraper().save_raw_data([], str(tmp_path))
    assert list(tmp_path.iterdir()) == [path]
    assert path.read_text() == '["evidence"]'
