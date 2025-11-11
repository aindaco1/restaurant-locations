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
        
        # ABQ typically posts weekly reports with standardized naming
        # Format: "RestaurantInspections_YYYY_WW.pdf"
        pdf_urls = []
        
        now = datetime.now()
        for week_offset in range(weeks_back):
            date = now - timedelta(weeks=week_offset)
            year = date.year
            week = date.isocalendar()[1]
            
            # Try common naming patterns
            patterns = [
                f"{self.base_url}/RestaurantInspections_{year}_{week:02d}.pdf",
                f"{self.base_url}/restaurant-inspections-{year}-week{week:02d}.pdf",
                f"{self.base_url}/inspections_{year}_{week:02d}.pdf"
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
            logger.warning("No ABQ PDFs found - URLs may need to be configured")
        
        return pdf_urls
    
    def parse_pdf(self, pdf_url: str) -> List[Dict]:
        """
        Parse a single PDF and extract inspection records
        
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
                for page in pdf.pages:
                    text = page.extract_text()
                    if text:
                        page_records = self._parse_page_text(text)
                        records.extend(page_records)
            
            logger.info(f"Extracted {len(records)} records from {pdf_url}")
            return records
            
        except Exception as e:
            logger.error(f"Failed to parse {pdf_url}: {e}")
            return []
    
    def _parse_page_text(self, text: str) -> List[Dict]:
        """
        Parse text extracted from PDF page
        
        This is a template - actual implementation depends on ABQ PDF format
        Common formats include:
        - Tabular data
        - Line-by-line records
        - Structured sections
        """
        records = []
        
        # Example pattern (adjust based on actual PDF format):
        # "Restaurant Name | Address | Date | Outcome | Violations"
        
        lines = text.split('\n')
        
        for line in lines:
            # Skip headers and empty lines
            if not line.strip() or 'ESTABLISHMENT' in line.upper():
                continue
            
            # Attempt to parse structured data
            # This is a simplified example - real implementation needs PDF analysis
            match = re.match(
                r'(.+?)\s+(\d+\s+\w+.*?)\s+(\d{1,2}/\d{1,2}/\d{2,4})\s+(PASS|FAIL|CONDITIONAL|CLOSED)',
                line,
                re.IGNORECASE
            )
            
            if match:
                name, address, date_str, outcome = match.groups()
                
                # Parse date
                try:
                    inspection_date = datetime.strptime(date_str, '%m/%d/%Y')
                except ValueError:
                    try:
                        inspection_date = datetime.strptime(date_str, '%m/%d/%y')
                    except ValueError:
                        continue
                
                record = {
                    'name': name.strip(),
                    'address': address.strip(),
                    'date': inspection_date.strftime('%Y-%m-%d'),
                    'outcome': outcome.lower(),
                    'city': 'Albuquerque',
                    'county': 'Bernalillo',
                    'violations': []  # Would need additional parsing
                }
                
                records.append(record)
        
        return records
    
    def fetch_all_inspections(self, weeks_back: int = 12) -> List[Dict]:
        """
        Fetch and parse all available inspection PDFs
        
        Args:
            weeks_back: How many weeks back to search
        
        Returns:
            Combined list of all inspection records
        """
        pdf_urls = self.find_recent_pdfs(weeks_back)
        
        all_records = []
        for url in pdf_urls:
            records = self.parse_pdf(url)
            all_records.extend(records)
        
        # Deduplicate by (name, address, date)
        seen = set()
        unique_records = []
        
        for record in all_records:
            key = (record['name'], record['address'], record['date'])
            if key not in seen:
                seen.add(key)
                unique_records.append(record)
        
        logger.info(f"Total unique ABQ records: {len(unique_records)}")
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
