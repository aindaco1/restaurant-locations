#!/usr/bin/env python3
"""
Unit tests for severity scoring logic
"""

import sys
from pathlib import Path
from datetime import datetime, timedelta

# Add scripts to path
sys.path.insert(0, str(Path(__file__).parent.parent))

import pytest
from normalize import SeverityCalculator, Inspection, Violation, Score


class TestSeverityCalculator:
    """Test severity scoring rules"""
    
    def test_closure_within_180_days(self):
        """Test Rule 1: +3.0 for closure within 180 days"""
        # Recent closure
        inspection = Inspection(
            date=(datetime.now() - timedelta(days=90)).strftime('%Y-%m-%d'),
            type='routine',
            outcome='closed',
            violations=[]
        )
        
        score = SeverityCalculator.calculate(inspection)
        
        assert score.severity == 3.0
        assert 'closure within 180d' in score.reasons
    
    def test_closure_outside_180_days(self):
        """Closures older than 180 days should not add score"""
        inspection = Inspection(
            date=(datetime.now() - timedelta(days=200)).strftime('%Y-%m-%d'),
            type='routine',
            outcome='closed',
            violations=[]
        )
        
        score = SeverityCalculator.calculate(inspection)
        
        assert score.severity == 0.0
        assert 'closure' not in ' '.join(score.reasons)
    
    def test_conditional_within_180_days(self):
        """Test Rule 2: +2.0 for conditional/failed within 180 days"""
        inspection = Inspection(
            date=(datetime.now() - timedelta(days=60)).strftime('%Y-%m-%d'),
            type='routine',
            outcome='conditional',
            violations=[]
        )
        
        score = SeverityCalculator.calculate(inspection)
        
        assert score.severity == 2.0
        assert 'conditional/failed within 180d' in score.reasons
    
    def test_critical_violations(self):
        """Test Rule 3: +0.5 per critical violation (cap +2.0)"""
        violations = [
            Violation(code='101', critical=True, desc='Critical violation 1'),
            Violation(code='102', critical=True, desc='Critical violation 2'),
            Violation(code='103', critical=False, desc='Non-critical')
        ]
        
        inspection = Inspection(
            date=(datetime.now() - timedelta(days=30)).strftime('%Y-%m-%d'),
            type='routine',
            outcome='approved',
            violations=violations
        )
        
        score = SeverityCalculator.calculate(inspection)
        
        # 2 critical violations = 1.0
        assert score.severity == 1.0
        assert '2 critical violation(s)' in score.reasons
    
    def test_critical_violations_capped(self):
        """Critical violations should be capped at +2.0"""
        violations = [
            Violation(code=f'{i}', critical=True, desc=f'Violation {i}')
            for i in range(10)  # 10 critical violations
        ]
        
        inspection = Inspection(
            date=(datetime.now() - timedelta(days=30)).strftime('%Y-%m-%d'),
            type='routine',
            outcome='approved',
            violations=violations
        )
        
        score = SeverityCalculator.calculate(inspection)
        
        # Should be capped at 2.0 (not 5.0)
        assert score.severity == 2.0
    
    def test_combined_scoring(self):
        """Test combination of multiple rules"""
        violations = [
            Violation(code='101', critical=True, desc='Critical')
        ]
        
        inspection = Inspection(
            date=(datetime.now() - timedelta(days=30)).strftime('%Y-%m-%d'),
            type='routine',
            outcome='conditional',
            violations=violations
        )
        
        score = SeverityCalculator.calculate(inspection)
        
        # Conditional (2.0) + 1 critical (0.5) = 2.5
        assert score.severity == 2.5
        assert len(score.reasons) == 2
    
    def test_approved_no_violations(self):
        """Clean inspection should have score 0"""
        inspection = Inspection(
            date=(datetime.now() - timedelta(days=30)).strftime('%Y-%m-%d'),
            type='routine',
            outcome='approved',
            violations=[]
        )
        
        score = SeverityCalculator.calculate(inspection)
        
        assert score.severity == 0.0
        assert len(score.reasons) == 0


def run_tests():
    """Run all tests"""
    pytest.main([__file__, '-v'])


if __name__ == '__main__':
    run_tests()
