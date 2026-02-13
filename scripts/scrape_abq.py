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
        self.documents_page = 'https://www.cabq.gov/environmentalhealth/documents'
        # Main report that's always current
        self.main_report = 'https://www.cabq.gov/environmentalhealth/documents/chpd_main_inspection_report.pdf'
        self.session = requests.Session()
    
    def discover_pdf_links(self) -> List[str]:
        """
        Scrape the ABQ documents page to find all inspection report PDFs
        
        Returns:
            List of PDF URLs
        """
        logger.info(f"Discovering PDFs from {self.documents_page}")
        pdf_urls = [self.main_report]
        
        try:
            response = self.session.get(self.documents_page, timeout=30)
            response.raise_for_status()
            
            # Find all PDF links that look like inspection reports
            # Patterns: media-report-*, inspection*, chpd*
            patterns = [
                r'href="([^"]*media-report[^"]*\.pdf)"',
                r'href="([^"]*inspection[^"]*\.pdf)"',
                r'href="([^"]*chpd[^"]*\.pdf)"',
            ]
            
            for pattern in patterns:
                matches = re.findall(pattern, response.text, re.IGNORECASE)
                for match in matches:
                    if match.startswith('http'):
                        url = match
                    elif match.startswith('/'):
                        url = f"https://www.cabq.gov{match}"
                    else:
                        url = f"{self.base_url}/{match}"
                    
                    if url not in pdf_urls:
                        pdf_urls.append(url)
                        logger.info(f"Discovered: {url}")
            
        except Exception as e:
            logger.warning(f"Could not scrape documents page: {e}")
        
        return pdf_urls
    
    def find_recent_pdfs(self, weeks_back: int = 12) -> List[str]:
        """
        Find recent inspection report PDFs.
        
        The main report (chpd_main_inspection_report.pdf) is always current
        and is the primary data source. Additional PDFs are discovered from
        the documents page if available.
        
        Args:
            weeks_back: How many weeks back to search (used for date-based discovery)
        
        Returns:
            List of PDF URLs
        """
        logger.info("Searching for ABQ PDFs")
        
        # Start with the main report (always current)
        pdf_urls = [self.main_report]
        
        # Try to discover additional PDFs from the documents page
        try:
            discovered = self.discover_pdf_links()
            for url in discovered:
                if url not in pdf_urls:
                    pdf_urls.append(url)
        except Exception as e:
            logger.warning(f"PDF discovery failed, using main report only: {e}")
        
        logger.info(f"Found {len(pdf_urls)} PDF(s) to process")
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
                # Parse ALL pages for summaries (not just first 2)
                for i, page in enumerate(pdf.pages):
                    text = page.extract_text()
                    if text:
                        page_records = self._parse_summary_page(text)
                        for rec in page_records:
                            # Include outcome in key to allow multiple inspections same day
                            key = (rec['name'], rec['date'], rec['outcome'])
                            if key not in summary_records:
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
        """Parse ABQ PDF - extracts restaurant name, address, date, outcome, operational status"""
        records = []
        lines = text.split('\n')
        
        current_establishment = None
        current_address = None
        current_operational_status = 'Open'
        
        for line in lines:
            line = line.strip()
            
            # Establishment name pattern: "NAME - ADDRESS"
            if ' - ' in line and not any(x in line for x in ['Inspection', 'Food', 'Permit', 'Operational']):
                parts = line.split(' - ', 1)
                if len(parts) == 2:
                    current_establishment = parts[0].strip()
                    current_address = parts[1].strip()
                    current_operational_status = 'Open'  # Reset
            
            # Capture operational status
            elif 'Operational Status' in line:
                if 'Closed' in line:
                    current_operational_status = 'Closed'
                else:
                    current_operational_status = 'Open'
            
            # Inspection record: starts with date MM/DD/YYYY
            elif re.match(r'\d{1,2}/\d{1,2}/\d{4}', line) and current_establishment:
                date_str = line.split()[0]
                
                status = 'approved'
                if 'Closure' in line:
                    status = 'closed'
                elif 'Closed' in line:
                    status = 'closed'
                elif 'Conditional' in line:
                    status = 'conditional'
                elif 'Unsatisfactory' in line or 'Re-Inspection' in line:
                    status = 'failed'
                
                try:
                    inspection_date = datetime.strptime(date_str, '%m/%d/%Y')
                    records.append({
                        'name': current_establishment,
                        'address': current_address or '',
                        'date': inspection_date.strftime('%Y-%m-%d'),
                        'outcome': status,
                        'operational_status': current_operational_status,
                        'city': 'Albuquerque',
                        'county': 'Bernalillo',
                        'violations': []
                    })
                except ValueError:
                    pass
        
        return records
    
    def fetch_all_inspections(self, weeks_back: int = 52) -> List[Dict]:
        """
        Fetch and parse all available inspection PDFs
        
        Returns ALL inspections, including approved follow-ups.
        Frontend will group by restaurant and determine status.
        Accumulates historical data over time.
        """
        pdf_urls = self.find_recent_pdfs(weeks_back)
        
        all_records = []
        for url in pdf_urls:
            records = self.parse_pdf(url)
            all_records.extend(records)
        
        # Group by restaurant to filter out approved-only
        restaurant_inspections = {}
        
        for record in all_records:
            key = record['name'].lower().strip()
            if key not in restaurant_inspections:
                restaurant_inspections[key] = []
            restaurant_inspections[key].append(record)
        
        # Only include restaurants that have at least one non-approved inspection
        filtered_records = []
        for name, inspections in restaurant_inspections.items():
            has_issue = any(i['outcome'] != 'approved' for i in inspections)
            if has_issue:
                # Include ALL inspections for this restaurant
                filtered_records.extend(inspections)
        
        # Deduplicate by (name, date, outcome) - allows multiple inspections same day
        seen = set()
        unique_records = []
        
        for record in filtered_records:
            key = (record['name'].lower().strip(), record['date'], record['outcome'])
            
            if key not in seen:
                seen.add(key)
                unique_records.append(record)
            else:
                # If exact duplicate, keep the one with more violations
                for i, existing in enumerate(unique_records):
                    if (existing['name'].lower().strip(), existing['date'], existing['outcome']) == key:
                        if len(record['violations']) > len(existing['violations']):
                            unique_records[i] = record
                        break
        
        logger.info(f"Total unique inspection records: {len(unique_records)}")
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
