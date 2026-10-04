#!/usr/bin/env python3
"""
Dataset Builder
Orchestrates the full data pipeline:
1. Scrape ABQ PDFs
2. Normalize to the shared schema
3. Merge with the archive
4. Generate the manifest
5. Save datasets to data/
"""

import sys
import json
import hashlib
import logging
import tempfile
from datetime import datetime
from pathlib import Path
from typing import List, Dict

# Add scripts to path for imports
sys.path.insert(0, str(Path(__file__).parent))

from scrape_abq import ABQPDFScraper
from normalize import normalize_dataset
from archive import merge_archive, validate_archive, write_json

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
        
        # Read and validate before fetching or writing anything. A damaged archive
        # must never be treated as an empty starting point.
        latest_file = self.output_dir / 'violations_latest.json'
        existing_data = json.loads(latest_file.read_text()) if latest_file.exists() else []
        validate_archive(existing_data, require_current_ids=False)
        logger.info(f"Loaded {len(existing_data)} existing records")

        logger.info("[1/3] Scraping ABQ PDFs...")
        scraper = ABQPDFScraper()
        abq_records = scraper.fetch_all_inspections()
        if not abq_records:
            raise ValueError('ABQ scraper returned 0 eligible records; preserving files. Check the source report.')
        metadata['abq_records'] = len(abq_records)

        logger.info("[2/3] Normalizing data...")
        # Validate the entire fetch before overwriting a weekly raw file.
        with tempfile.TemporaryDirectory() as temporary:
            input_file = Path(temporary) / 'abq.json'
            input_file.write_text(json.dumps(abq_records))
            normalized = normalize_dataset(None, str(input_file))
        merged_data = merge_archive(existing_data, normalized)
        logger.info(f"Added {len(merged_data) - len(existing_data)} new records, total: {len(merged_data)}")

        logger.info("[3/3] Saving datasets...")
        scraper.save_raw_data(abq_records, str(self.output_dir))
        write_json(latest_file, merged_data)
        metadata['files_generated'].append(str(latest_file))
        metadata['total_records'] = len(merged_data)

        # Save monthly snapshot
        now = datetime.now()
        snapshot_file = self.snapshots_dir / f'violations_{now.strftime("%Y-%m")}.json'
        write_json(snapshot_file, normalized)
        logger.info(f"Saved monthly snapshot: {snapshot_file}")
        metadata['files_generated'].append(str(snapshot_file))
        
        # Generate manifest
        logger.info("\nGenerating manifest...")
        manifest = self.generate_manifest(merged_data)
        
        manifest_file = self.output_dir / 'manifest.json'
        write_json(manifest_file, manifest)
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
        try:
            validate_archive(dataset)
        except (ValueError, TypeError, KeyError) as error:
            logger.error(f"Archive validation failed: {error}")
            return False
        logger.info(f"Schema and identity validation passed for {len(dataset)} records")
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
