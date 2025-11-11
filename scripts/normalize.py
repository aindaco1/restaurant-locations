#!/usr/bin/env python3
"""
Data Normalizer
Maps raw inspection data from NMED and ABQ to unified schema
Computes severity scores
"""

import json
import logging
from datetime import datetime
from typing import List, Dict, Optional
from pydantic import BaseModel, Field, validator

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


# ===== Data Models =====

class GeoLocation(BaseModel):
    lat: float = 0.0
    lng: float = 0.0


class Establishment(BaseModel):
    name: str
    address: str
    city: str
    county: str
    geo: GeoLocation = Field(default_factory=lambda: GeoLocation(lat=0.0, lng=0.0))


class Violation(BaseModel):
    code: str
    critical: bool
    desc: str


class Inspection(BaseModel):
    date: str  # YYYY-MM-DD
    type: str  # routine|complaint|followup|closure|reopen
    outcome: str  # approved|conditional|failed|closed|reopened
    violations: List[Violation] = Field(default_factory=list)


class Score(BaseModel):
    severity: float
    reasons: List[str]


class ViolationRecord(BaseModel):
    id: str
    source: str  # NMED|ABQ
    establishment: Establishment
    inspection: Inspection
    score: Score
    links: Dict[str, Optional[str]]


# ===== Severity Scoring =====

class SeverityCalculator:
    """Calculates severity scores based on inspection data"""
    
    @staticmethod
    def calculate(inspection: Inspection, all_inspections: List[Inspection] = None) -> Score:
        """
        Calculate severity score
        
        Rules:
        - +3.0 for closure within 180 days
        - +2.0 for conditional/failed within 180 days
        - +0.5 per critical violation (cap +2.0, within 365 days)
        - +0.5 if two adverse inspections within 365 days
        """
        score = 0.0
        reasons = []
        
        now = datetime.now()
        inspection_date = datetime.strptime(inspection.date, '%Y-%m-%d')
        days_ago = (now - inspection_date).days
        
        # Rule 1: Closure within 180 days
        if inspection.outcome == 'closed' and days_ago <= 180:
            score += 3.0
            reasons.append('closure within 180d')
        
        # Rule 2: Conditional/failed within 180 days
        if inspection.outcome in ['conditional', 'failed'] and days_ago <= 180:
            score += 2.0
            reasons.append('conditional/failed within 180d')
        
        # Rule 3: Critical violations (within 365 days)
        if days_ago <= 365:
            critical_violations = [v for v in inspection.violations if v.critical]
            if critical_violations:
                critical_score = min(len(critical_violations) * 0.5, 2.0)
                score += critical_score
                reasons.append(f'{len(critical_violations)} critical violation(s)')
        
        # Rule 4: Multiple adverse inspections within 365 days
        if all_inspections and len(all_inspections) >= 2:
            adverse = [
                insp for insp in all_inspections
                if (now - datetime.strptime(insp.date, '%Y-%m-%d')).days <= 365
                and insp.outcome in ['failed', 'conditional', 'closed']
            ]
            
            if len(adverse) >= 2:
                score += 0.5
                reasons.append('multiple adverse inspections within 365d')
        
        return Score(severity=round(score, 1), reasons=reasons)


# ===== Normalizers =====

class NMEDNormalizer:
    """Normalizes NMED data to unified schema"""
    
    @staticmethod
    def normalize(raw_record: Dict) -> Optional[ViolationRecord]:
        """Map NMED record to ViolationRecord"""
        try:
            # Map NMED fields (adjust based on actual API response)
            # This is a template - actual field names may vary
            
            establishment = Establishment(
                name=raw_record.get('FACILITY_NAME', raw_record.get('name', 'Unknown')),
                address=raw_record.get('ADDRESS', raw_record.get('address', '')),
                city=raw_record.get('CITY', raw_record.get('city', '')),
                county=raw_record.get('COUNTY', raw_record.get('county', '')),
                geo=GeoLocation(
                    lat=float(raw_record.get('LATITUDE', 0) or 0),
                    lng=float(raw_record.get('LONGITUDE', 0) or 0)
                )
            )
            
            # Parse violations if available
            violations = []
            if 'violations' in raw_record:
                for v in raw_record['violations']:
                    violations.append(Violation(
                        code=v.get('code', ''),
                        critical=v.get('critical', False),
                        desc=v.get('description', '')
                    ))
            
            inspection = Inspection(
                date=raw_record.get('INSPECTION_DATE', raw_record.get('date', '')),
                type=raw_record.get('INSPECTION_TYPE', 'routine').lower(),
                outcome=raw_record.get('OUTCOME', 'approved').lower(),
                violations=violations
            )
            
            # Calculate score
            score = SeverityCalculator.calculate(inspection)
            
            # Generate unique ID
            record_id = f"nm:{establishment.city.lower().replace(' ', '')}:{establishment.name.lower().replace(' ', '-')}:{inspection.date}"
            
            return ViolationRecord(
                id=record_id,
                source='NMED',
                establishment=establishment,
                inspection=inspection,
                score=score,
                links={
                    'source': 'https://www.env.nm.gov/',
                    'document': raw_record.get('DOCUMENT_URL')
                }
            )
            
        except Exception as e:
            logger.error(f"Failed to normalize NMED record: {e}")
            logger.debug(f"Raw record: {raw_record}")
            return None


class ABQNormalizer:
    """Normalizes ABQ PDF data to unified schema"""
    
    @staticmethod
    def normalize(raw_record: Dict) -> Optional[ViolationRecord]:
        """Map ABQ record to ViolationRecord"""
        try:
            establishment = Establishment(
                name=raw_record['name'],
                address=raw_record['address'],
                city='Albuquerque',
                county='Bernalillo',
                geo=GeoLocation(lat=35.0844, lng=-106.6504)  # ABQ center
            )
            
            # Map outcome (pass through most, standardize variations)
            outcome_map = {
                'pass': 'approved',
                'approved': 'approved',
                'fail': 'failed',
                'failed': 'failed',
                'conditional': 'conditional',
                'closed': 'closed'
            }
            
            # Convert violations list (if strings) to Violation objects
            violations_list = []
            for v in raw_record.get('violations', []):
                if isinstance(v, str):
                    violations_list.append(Violation(code='', critical=False, desc=v))
                else:
                    violations_list.append(Violation(
                        code=v.get('code', ''),
                        critical=v.get('critical', False),
                        desc=v.get('desc', '')
                    ))
            
            inspection = Inspection(
                date=raw_record['date'],
                type='routine',
                outcome=outcome_map.get(raw_record['outcome'], 'approved'),
                violations=violations_list
            )
            
            score = SeverityCalculator.calculate(inspection)
            
            # Add violations to reasons for better display
            if violations_list and not score.reasons:
                score.reasons = [v.desc for v in violations_list[:3]]
            
            record_id = f"abq:{establishment.name.lower().replace(' ', '-')}:{inspection.date}"
            
            record = ViolationRecord(
                id=record_id,
                source='ABQ',
                establishment=establishment,
                inspection=inspection,
                score=score,
                links={
                    'source': 'https://www.cabq.gov/environmentalhealth',
                    'document': raw_record.get('pdf_url')
                }
            )
            
            # Add operational status as custom field
            record_dict = record.dict()
            record_dict['operational_status'] = raw_record.get('operational_status', 'Open')
            
            return record_dict
            
        except Exception as e:
            logger.error(f"Failed to normalize ABQ record: {e}")
            logger.debug(f"Raw record: {raw_record}")
            return None


def normalize_dataset(nmed_file: str = None, abq_file: str = None) -> List[Dict]:
    """
    Normalize raw data files to unified schema
    
    Args:
        nmed_file: Path to NMED JSON
        abq_file: Path to ABQ JSON
    
    Returns:
        List of normalized ViolationRecord dicts
    """
    normalized = []
    
    # Process NMED data
    if nmed_file:
        try:
            with open(nmed_file, 'r') as f:
                nmed_data = json.load(f)
            
            logger.info(f"Normalizing {len(nmed_data)} NMED records")
            for record in nmed_data:
                normalized_record = NMEDNormalizer.normalize(record)
                if normalized_record:
                    normalized.append(normalized_record.dict())
        except Exception as e:
            logger.error(f"Failed to process NMED file: {e}")
    
    # Process ABQ data
    if abq_file:
        try:
            with open(abq_file, 'r') as f:
                abq_data = json.load(f)
            
            logger.info(f"Normalizing {len(abq_data)} ABQ records")
            for record in abq_data:
                normalized_record = ABQNormalizer.normalize(record)
                if normalized_record:
                    normalized.append(normalized_record.dict())
        except Exception as e:
            logger.error(f"Failed to process ABQ file: {e}")
    
    logger.info(f"Total normalized records: {len(normalized)}")
    return normalized


if __name__ == '__main__':
    import argparse
    
    parser = argparse.ArgumentParser(description='Normalize inspection data')
    parser.add_argument('--nmed', help='Path to NMED JSON file')
    parser.add_argument('--abq', help='Path to ABQ JSON file')
    parser.add_argument('--output', default='data/normalized.json', help='Output file')
    
    args = parser.parse_args()
    
    normalized = normalize_dataset(args.nmed, args.abq)
    
    with open(args.output, 'w') as f:
        json.dump(normalized, f, indent=2)
    
    logger.info(f"Saved normalized data to {args.output}")
