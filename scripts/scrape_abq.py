#!/usr/bin/env python3
"""
Albuquerque PDF Scraper
Parses weekly Restaurant Inspection Report PDFs from City of Albuquerque
"""

import os
import json
import logging
import re
from datetime import datetime, timedelta
from typing import List, Dict, Optional
import requests
import pdfplumber
from io import BytesIO

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


class ABQPDFScraper:
    """Scrapes Albuquerque weekly inspection PDFs"""
    
    def __init__(self):
        self.base_url = os.getenv(
            'ABQ_PDF_BASE_URL',
            'https://www.cabq.gov/environmentalhealth/documents'
        )
        # Known inspection report URL
        self.main_report_url = 'https://www.cabq.gov/environmentalhealth/documents/chpd_main_inspection_report.pdf'
        self.session = requests.Session()
    
    def find_recent_pdfs(self, weeks_back: int = 12) -> List[str]:
        """
        Find recent inspection report PDFs
        
        Args:
            weeks_back: How many weeks back to search
        
        Returns:
            List of PDF URLs
        """
        logger.info(f"Searching for ABQ PDFs from last {weeks_back} weeks")
        
        pdf_urls = []
        
        # Try the main inspection report first
        try:
            response = self.session.head(self.main_report_url, timeout=10)
            if response.status_code == 200:
                pdf_urls.append(self.main_report_url)
                logger.info(f"Found main inspection report: {self.main_report_url}")
        except Exception as e:
            logger.warning(f"Main report not accessible: {e}")
        
        # Try historical weekly reports
        now = datetime.now()
        for week_offset in range(weeks_back):
            date = now - timedelta(weeks=week_offset)
            year = date.year
            week = date.isocalendar()[1]
            
            # Try common naming patterns
            patterns = [
                f"{self.base_url}/RestaurantInspections_{year}_{week:02d}.pdf",
                f"{self.base_url}/restaurant-inspections-{year}-week{week:02d}.pdf",
                f"{self.base_url}/inspections_{year}_{week:02d}.pdf",
                f"{self.base_url}/chpd_main_inspection_report_{year}_{week:02d}.pdf"
            ]
            
            for url in patterns:
                try:
                    response = self.session.head(url, timeout=10)
                    if response.status_code == 200:
                        pdf_urls.append(url)
                        logger.info(f"Found PDF: {url}")
                        break
                except Exception:
                    continue
        
        if not pdf_urls:
            logger.warning("No ABQ PDFs found - trying fallback URL")
        
        return pdf_urls
    
    def parse_pdf(self, pdf_url: str) -> List[Dict]:
        """
        Parse a single PDF and extract inspection records with violations
        
        Args:
            pdf_url: URL to PDF
        
        Returns:
            List of inspection records
        """
        logger.info(f"Parsing PDF: {pdf_url}")
        
        try:
            response = self.session.get(pdf_url, timeout=30)
            response.raise_for_status()
            
            pdf_bytes = BytesIO(response.content)
            records = []
            
            with pdfplumber.open(pdf_bytes) as pdf:
                # First pass: get summary records with establishments and statuses
                summary_records = {}
                for i, page in enumerate(pdf.pages[:2]):  # Summary tables in first 2 pages
                    text = page.extract_text()
                    if text:
                        page_records = self._parse_summary_page(text)
                        for rec in page_records:
                            key = (rec['name'], rec['date'])
                            if key not in summary_records or rec['outcome'] != 'approved':
                                summary_records[key] = rec
                
                # Second pass: extract violations from detail pages
                for page in pdf.pages:
                    text = page.extract_text()
                    if text and 'Violation:' in text:
                        violations = self._extract_violations(text)
                        # Match violations to establishments
                        for key, record in summary_records.items():
                            if record['name'] in text:
                                record['violations'].extend(violations)
                                break
                
                records = list(summary_records.values())
            
            logger.info(f"Extracted {len(records)} records from {pdf_url}")
            return records
            
        except Exception as e:
            logger.error(f"Failed to parse {pdf_url}: {e}")
            return []
    
    def _extract_violations(self, text: str) -> List[str]:
        """Extract violation descriptions from detail page"""
        violations = []
        lines = text.split('\n')
        
        for i, line in enumerate(lines):
            if line.startswith('Violation:'):
                # Get the violation category
                violation_category = line.replace('Violation:', '').strip()
                violations.append(violation_category)
        
        return violations
    
    def _parse_summary_page(self, text: str) -> List[Dict]:
        """Parse ABQ PDF - extracts restaurant name, address, date, outcome"""
        records = []
        lines = text.split('\n')
        
        current_establishment = None
        current_address = None
        
        for line in lines:
            line = line.strip()
            
            # Establishment name pattern: "NAME - ADDRESS"
            if ' - ' in line and not any(x in line for x in ['Inspection', 'Food', 'Permit', 'Operational']):
                parts = line.split(' - ', 1)
                if len(parts) == 2:
                    current_establishment = parts[0].strip()
                    current_address = parts[1].strip()
            
            # Inspection record: starts with date MM/DD/YYYY
            elif re.match(r'\d{1,2}/\d{1,2}/\d{4}', line) and current_establishment:
                date_str = line.split()[0]
                
                status = 'approved'
                if 'Conditional' in line:
                    status = 'conditional'
                elif 'Unsatisfactory' in line or 'Re-Inspection' in line:
                    status = 'failed'
                elif 'Closed' in line:
                    status = 'closed'
                
                try:
                    inspection_date = datetime.strptime(date_str, '%m/%d/%Y')
                    records.append({
                        'name': current_establishment,
                        'address': current_address or '',
                        'date': inspection_date.strftime('%Y-%m-%d'),
                        'outcome': status,
                        'city': 'Albuquerque',
                        'county': 'Bernalillo',
                        'violations': []
                    })
                except ValueError:
                    pass
        
        return records
    
    def fetch_all_inspections(self, weeks_back: int = 12) -> List[Dict]:
        """
        Fetch and parse all available inspection PDFs
        
        Args:
            weeks_back: How many weeks back to search
        
        Returns:
            Combined list of all inspection records (excluding approved-only)
        """
        pdf_urls = self.find_recent_pdfs(weeks_back)
        
        all_records = []
        for url in pdf_urls:
            records = self.parse_pdf(url)
            all_records.extend(records)
        
        # Deduplicate and filter
        seen = set()
        unique_records = []
        
        for record in all_records:
            key = (record['name'], record['address'], record['date'])
            # Only include if not already seen AND not just "approved"
            if key not in seen and record['outcome'] != 'approved':
                seen.add(key)
                unique_records.append(record)
        
        logger.info(f"Total unique ABQ records (non-approved): {len(unique_records)}")
        return unique_records
    
    def save_raw_data(self, records: List[Dict], output_dir: str = 'data'):
        """Save raw inspection data to JSON file"""
        os.makedirs(output_dir, exist_ok=True)
        
        now = datetime.now()
        year, week, _ = now.isocalendar()
        filename = os.path.join(output_dir, f'abq_{year}_{week:02d}.json')
        
        with open(filename, 'w') as f:
            json.dump(records, f, indent=2)
        
        logger.info(f"Saved {len(records)} ABQ records to {filename}")
        return filename


def main():
    """CLI entry point"""
    import argparse
    
    parser = argparse.ArgumentParser(description='Scrape ABQ restaurant inspection PDFs')
    parser.add_argument('--weeks', type=int, default=12, help='Weeks back to search (default: 12)')
    parser.add_argument('--output', default='data', help='Output directory (default: data)')
    
    args = parser.parse_args()
    
    scraper = ABQPDFScraper()
    records = scraper.fetch_all_inspections(weeks_back=args.weeks)
    
    if records:
        scraper.save_raw_data(records, args.output)
    else:
        logger.warning("No ABQ records fetched - PDF URLs may need configuration")
        logger.info("Creating placeholder file for demo purposes")
        scraper.save_raw_data([], args.output)


if __name__ == '__main__':
    main()
