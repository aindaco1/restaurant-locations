#!/usr/bin/env python3
"""
NMED Data Fetcher
Fetches restaurant inspection data from New Mexico Environment Department API
Supports both Apigee REST endpoints and ArcGIS FeatureServer
"""

import os
import json
import logging
from datetime import datetime, timedelta
from typing import List, Dict, Optional
import requests
from dateutil import parser as date_parser

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Target cities (all except Albuquerque/Bernalillo which uses city system)
TARGET_CITIES = [
    'Las Cruces',
    'Rio Rancho',
    'Santa Fe',
    'Roswell',
    'Farmington',
    'Hobbs',
    'Clovis',
    'Carlsbad',
    'Alamogordo'
]


class NMEDFetcher:
    """Fetches inspection data from NMED APIs"""
    
    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or os.getenv('NMED_API_KEY')
        self.session = requests.Session()
        
        # Try multiple possible NMED endpoints
        self.endpoints = {
            'apigee': os.getenv('NMED_APIGEE_URL', 'https://api.env.nm.gov/v1/inspections'),
            'arcgis': os.getenv('NMED_ARCGIS_URL', 
                'https://services.arcgis.com/NMED/FeatureServer/0/query')
        }
        
        if self.api_key:
            self.session.headers['Authorization'] = f'Bearer {self.api_key}'
    
    def fetch_inspections(
        self, 
        cities: List[str] = TARGET_CITIES,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None
    ) -> List[Dict]:
        """
        Fetch inspections for specified cities and date range
        
        Args:
            cities: List of city names to fetch
            start_date: Start of date range (defaults to 12 months ago)
            end_date: End of date range (defaults to today)
        
        Returns:
            List of raw inspection records
        """
        if not start_date:
            start_date = datetime.now() - timedelta(days=365)
        if not end_date:
            end_date = datetime.now()
        
        logger.info(f"Fetching NMED inspections for {len(cities)} cities from {start_date.date()} to {end_date.date()}")
        
        # Try ArcGIS endpoint first (more commonly available)
        try:
            return self._fetch_from_arcgis(cities, start_date, end_date)
        except Exception as e:
            logger.warning(f"ArcGIS fetch failed: {e}. Trying Apigee...")
            
        # Fallback to Apigee
        try:
            return self._fetch_from_apigee(cities, start_date, end_date)
        except Exception as e:
            logger.error(f"Apigee fetch also failed: {e}")
            logger.warning("Returning empty dataset - API endpoints may not be available yet")
            return []
    
    def _fetch_from_arcgis(
        self, 
        cities: List[str], 
        start_date: datetime, 
        end_date: datetime
    ) -> List[Dict]:
        """Fetch from ArcGIS FeatureServer"""
        url = self.endpoints['arcgis']
        
        # Build WHERE clause for cities and date range
        city_filter = " OR ".join([f"CITY = '{city}'" for city in cities])
        date_filter = f"INSPECTION_DATE >= '{start_date.strftime('%Y-%m-%d')}' AND INSPECTION_DATE <= '{end_date.strftime('%Y-%m-%d')}'"
        where_clause = f"({city_filter}) AND ({date_filter})"
        
        params = {
            'where': where_clause,
            'outFields': '*',
            'f': 'json',
            'resultRecordCount': 5000  # Max per request
        }
        
        logger.info(f"Querying ArcGIS: {url}")
        response = self.session.get(url, params=params, timeout=30)
        response.raise_for_status()
        
        data = response.json()
        
        if 'features' not in data:
            raise ValueError(f"Unexpected ArcGIS response format: {data}")
        
        records = [feature['attributes'] for feature in data['features']]
        logger.info(f"Fetched {len(records)} records from ArcGIS")
        
        return records
    
    def _fetch_from_apigee(
        self, 
        cities: List[str], 
        start_date: datetime, 
        end_date: datetime
    ) -> List[Dict]:
        """Fetch from Apigee REST API"""
        url = self.endpoints['apigee']
        
        params = {
            'cities': ','.join(cities),
            'start_date': start_date.strftime('%Y-%m-%d'),
            'end_date': end_date.strftime('%Y-%m-%d'),
            'limit': 5000
        }
        
        logger.info(f"Querying Apigee: {url}")
        response = self.session.get(url, params=params, timeout=30)
        response.raise_for_status()
        
        data = response.json()
        
        if 'inspections' not in data:
            raise ValueError(f"Unexpected Apigee response format: {data}")
        
        records = data['inspections']
        logger.info(f"Fetched {len(records)} records from Apigee")
        
        return records
    
    def save_raw_data(self, records: List[Dict], output_dir: str = 'data'):
        """Save raw inspection data to JSON file"""
        os.makedirs(output_dir, exist_ok=True)
        
        timestamp = datetime.now().strftime('%Y-%m-%d')
        filename = os.path.join(output_dir, f'nmed_{timestamp}.json')
        
        with open(filename, 'w') as f:
            json.dump(records, f, indent=2, default=str)
        
        logger.info(f"Saved {len(records)} records to {filename}")
        return filename


def main():
    """CLI entry point"""
    import argparse
    
    parser = argparse.ArgumentParser(description='Fetch NMED restaurant inspections')
    parser.add_argument('--days', type=int, default=365, help='Number of days to fetch (default: 365)')
    parser.add_argument('--output', default='data', help='Output directory (default: data)')
    parser.add_argument('--cities', nargs='+', default=TARGET_CITIES, help='Cities to fetch')
    
    args = parser.parse_args()
    
    fetcher = NMEDFetcher()
    
    start_date = datetime.now() - timedelta(days=args.days)
    records = fetcher.fetch_inspections(
        cities=args.cities,
        start_date=start_date
    )
    
    if records:
        fetcher.save_raw_data(records, args.output)
    else:
        logger.warning("No records fetched - this is expected if NMED API is not yet configured")
        logger.info("Creating placeholder file for demo purposes")
        fetcher.save_raw_data([], args.output)


if __name__ == '__main__':
    main()
