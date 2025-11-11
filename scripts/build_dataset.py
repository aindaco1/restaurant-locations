#!/usr/bin/env python3
"""
Dataset Builder
Orchestrates the full data pipeline:
1. Fetch NMED data
2. Scrape ABQ PDFs
3. Normalize to unified schema
4. Generate manifest
5. Save to data/ directory
"""

import os
import sys
import json
import hashlib
import logging
from datetime import datetime
from pathlib import Path
from typing import List, Dict

# Add scripts to path for imports
sys.path.insert(0, str(Path(__file__).parent))

from scrape_abq import ABQPDFScraper
from normalize import normalize_dataset

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


class DatasetBuilder:
    """Orchestrates the full data pipeline"""
    
    def __init__(self, output_dir: str = 'data'):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(exist_ok=True)
        
        self.snapshots_dir = self.output_dir / 'snapshots'
        self.snapshots_dir.mkdir(exist_ok=True)
    
    def run_pipeline(self) -> Dict:
        """
        Run the full data pipeline
        
        Returns:
            Pipeline metadata (record counts, timestamps, etc.)
        """
        logger.info("=" * 60)
        logger.info("Starting data pipeline")
        logger.info("=" * 60)
        
        metadata = {
            'timestamp': datetime.now().isoformat(),
            'nmed_records': 0,
            'abq_records': 0,
            'total_records': 0,
            'files_generated': []
        }
        
        # Step 1: Scrape ABQ PDFs (only data source)
        logger.info("\n[1/3] Scraping ABQ PDFs...")
        abq_file = None
        nmed_file = None
        try:
            scraper = ABQPDFScraper()
            abq_records = scraper.fetch_all_inspections()
            abq_file = scraper.save_raw_data(abq_records, str(self.output_dir))
            metadata['abq_records'] = len(abq_records)
        except Exception as e:
            logger.error(f"ABQ scrape failed: {e}")
            logger.warning("Continuing with empty ABQ dataset")
        
        # Step 2: Normalize data
        logger.info("\n[2/3] Normalizing data...")
        normalized = normalize_dataset(nmed_file, abq_file)
        metadata['total_records'] = len(normalized)
        
        # Step 3: Save datasets
        logger.info("\n[3/3] Saving datasets...")
        
        # Save latest dataset
        latest_file = self.output_dir / 'violations_latest.json'
        with open(latest_file, 'w') as f:
            json.dump(normalized, f, indent=2)
        logger.info(f"Saved latest dataset: {latest_file}")
        metadata['files_generated'].append(str(latest_file))
        
        # Save monthly snapshot
        now = datetime.now()
        snapshot_file = self.snapshots_dir / f'violations_{now.strftime("%Y-%m")}.json'
        with open(snapshot_file, 'w') as f:
            json.dump(normalized, f, indent=2)
        logger.info(f"Saved monthly snapshot: {snapshot_file}")
        metadata['files_generated'].append(str(snapshot_file))
        
        # Generate manifest
        logger.info("\nGenerating manifest...")
        manifest = self.generate_manifest(normalized)
        
        manifest_file = self.output_dir / 'manifest.json'
        with open(manifest_file, 'w') as f:
            json.dump(manifest, f, indent=2)
        logger.info(f"Saved manifest: {manifest_file}")
        metadata['files_generated'].append(str(manifest_file))
        
        logger.info("\n" + "=" * 60)
        logger.info("Pipeline complete!")
        logger.info(f"  ABQ records: {metadata['abq_records']}")
        logger.info(f"  Total normalized: {metadata['total_records']}")
        logger.info("=" * 60)
        
        return metadata
    
    def generate_manifest(self, dataset: List[Dict]) -> Dict:
        """
        Generate manifest with dataset metadata
        
        Args:
            dataset: Normalized violation records
        
        Returns:
            Manifest dict
        """
        # Calculate dataset hash
        dataset_json = json.dumps(dataset, sort_keys=True)
        dataset_hash = hashlib.sha256(dataset_json.encode()).hexdigest()[:8]
        
        # Count by city
        city_counts = {}
        for record in dataset:
            city = record['establishment']['city']
            city_counts[city] = city_counts.get(city, 0) + 1
        
        # Count by severity
        severity_counts = {'high': 0, 'medium': 0, 'low': 0}
        for record in dataset:
            score = record['score']['severity']
            if score >= 3.0:
                severity_counts['high'] += 1
            elif score >= 1.5:
                severity_counts['medium'] += 1
            else:
                severity_counts['low'] += 1
        
        manifest = {
            'generated_at': datetime.now().isoformat(),
            'dataset_version': dataset_hash,
            'total_records': len(dataset),
            'cities': city_counts,
            'severity_breakdown': severity_counts,
            'datasets': {
                'latest': {
                    'url': '/data/violations_latest.json',
                    'hash': dataset_hash,
                    'records': len(dataset)
                }
            }
        }
        
        return manifest
    
    def validate_schema(self, dataset: List[Dict]) -> bool:
        """
        Validate that all records conform to expected schema
        
        Args:
            dataset: List of violation records
        
        Returns:
            True if valid, False otherwise
        """
        required_fields = ['id', 'source', 'establishment', 'inspection', 'score', 'links']
        
        for i, record in enumerate(dataset):
            for field in required_fields:
                if field not in record:
                    logger.error(f"Record {i} missing required field: {field}")
                    return False
        
        logger.info(f"Schema validation passed for {len(dataset)} records")
        return True


def main():
    """CLI entry point"""
    import argparse
    
    parser = argparse.ArgumentParser(description='Build violations dataset')
    parser.add_argument('--output', default='data', help='Output directory (default: data)')
    parser.add_argument('--validate', action='store_true', help='Validate schema after build')
    
    args = parser.parse_args()
    
    builder = DatasetBuilder(args.output)
    
    try:
        metadata = builder.run_pipeline()
        
        # Optionally validate
        if args.validate:
            logger.info("\nValidating schema...")
            violations_file = Path(args.output) / 'violations_latest.json'
            with open(violations_file, 'r') as f:
                dataset = json.load(f)
            
            if not builder.validate_schema(dataset):
                logger.error("Schema validation failed!")
                sys.exit(1)
        
        logger.info("\nPipeline successful!")
        sys.exit(0)
        
    except Exception as e:
        logger.error(f"Pipeline failed: {e}", exc_info=True)
        sys.exit(1)


if __name__ == '__main__':
    main()
