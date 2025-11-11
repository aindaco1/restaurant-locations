// Scoring logic for health code violations
// Shared between frontend display and backend pipeline

const SeverityScore = {
  // Calculate severity score based on inspection data
  calculate(inspection, allInspections = []) {
    let score = 0;
    const reasons = [];
    const now = new Date();
    const inspectionDate = new Date(inspection.date);
    const daysAgo = Math.floor((now - inspectionDate) / (1000 * 60 * 60 * 24));

    // Rule 1: Closure within 180 days (+3.0)
    if (inspection.outcome === 'closed' && daysAgo <= 180) {
      score += 3.0;
      reasons.push('closure within 180d');
    }

    // Rule 2: Conditional/failed within 180 days (+2.0)
    if ((inspection.outcome === 'conditional' || inspection.outcome === 'failed') && daysAgo <= 180) {
      score += 2.0;
      reasons.push('conditional/failed within 180d');
    }

    // Rule 3: Critical violations (+0.5 each, cap at +2.0, within 365 days)
    if (daysAgo <= 365 && inspection.violations) {
      const criticalViolations = inspection.violations.filter(v => v.critical);
      const criticalScore = Math.min(criticalViolations.length * 0.5, 2.0);
      
      if (criticalScore > 0) {
        score += criticalScore;
        reasons.push(`${criticalViolations.length} critical violation(s)`);
      }
    }

    // Rule 4: Two adverse inspections within 365 days (+0.5)
    if (allInspections.length >= 2) {
      const adverseInspections = allInspections.filter(insp => {
        const inspDate = new Date(insp.date);
        const daysSince = Math.floor((now - inspDate) / (1000 * 60 * 60 * 24));
        return daysSince <= 365 && 
               (insp.outcome === 'failed' || insp.outcome === 'conditional' || insp.outcome === 'closed');
      });

      if (adverseInspections.length >= 2) {
        score += 0.5;
        reasons.push('multiple adverse inspections within 365d');
      }
    }

    return {
      severity: parseFloat(score.toFixed(1)),
      reasons
    };
  },

  // Get severity level label
  getLevel(score) {
    if (score >= 3.0) return 'high';
    if (score >= 1.5) return 'medium';
    return 'low';
  },

  // Get color for severity level
  getColor(level) {
    const colors = {
      high: '#d32f2f',
      medium: '#f57c00',
      low: '#fbc02d',
      safe: '#388e3c'
    };
    return colors[level] || colors.low;
  }
};

// Export for use in Node.js (backend) or browser
if (typeof module !== 'undefined' && module.exports) {
  module.exports = SeverityScore;
}
