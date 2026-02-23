// Main application logic for NM Health Code Violations Finder
// Uses Alpine.js for reactive UI

document.addEventListener('alpine:init', () => {
  // Global store for violations data (shared between toolbar and list)
  Alpine.store('violations', {
    violations: [],
    filteredViolations: [],
    sortBy: 'severity',
    loading: true,
    error: null,

    init() {
      this.loadViolations();
    },

    async loadViolations() {
      try {
        const baseurl = document.querySelector('meta[name="baseurl"]')?.content || '';
        const response = await fetch(`${baseurl}/data/violations_latest.json`);
        
        if (!response.ok) {
          throw new Error(`HTTP error! status: ${response.status}`);
        }
        
        const data = await response.json();
        this.violations = data;
        // Group immediately after loading
        this.filteredViolations = this.groupByRestaurant(data);
        this.loading = false;
        this.sortViolations();
      } catch (error) {
        console.error('Failed to load violations:', error);
        this.error = error.message;
        this.loading = false;
        this.violations = [];
        this.filteredViolations = [];
      }
    },

    groupByRestaurant(violations) {
      const grouped = {};
      
      violations.forEach(v => {
        const key = `${v.establishment.name.toLowerCase().trim()}`;
        if (!grouped[key]) {
          grouped[key] = {
            name: this.toTitleCase(v.establishment.name),
            address: v.establishment.address,
            city: v.establishment.city,
            inspections: [],
            score: 0,
            isClosed: false
          };
        }
        grouped[key].inspections.push({
          date: v.inspection.date,
          outcome: v.inspection.outcome,
          violations: v.inspection.violations,
          writeup: v.inspection.writeup || '',
          individualScore: v.score.severity,
          reasons: v.score.reasons,
          links: v.links,
          operationalStatus: v.operational_status || 'Open'
        });
      });
      
      // Calculate restaurant-level score and determine closure status
      Object.values(grouped).forEach(restaurant => {
        // Sort inspections by date (most recent first)
        restaurant.inspections.sort((a, b) => new Date(b.date) - new Date(a.date));
        
        // Check if closed using Operational Status from most recent inspection
        const mostRecent = restaurant.inspections[0];
        restaurant.isClosed = mostRecent?.operationalStatus === 'Closed';
        
        // Calculate restaurant score from all inspections
        let totalScore = 0;
        const now = new Date();
        
        restaurant.inspections.forEach(insp => {
          const inspDate = new Date(insp.date);
          const daysAgo = Math.floor((now - inspDate) / (1000 * 60 * 60 * 24));
          
          // Add to score based on recency and severity
          if (insp.outcome === 'closed' && daysAgo <= 180) {
            totalScore += 3.0;
          } else if ((insp.outcome === 'conditional' || insp.outcome === 'failed') && daysAgo <= 180) {
            totalScore += 2.0;
          }
        });
        
        // Major boost if currently operationally closed
        if (restaurant.isClosed) {
          totalScore += 5.0;
        }
        
        restaurant.score = totalScore;
      });
      
      // Remove restaurants with 0.0 score
      return Object.values(grouped).filter(r => r.score > 0);
    },

    filterViolations(filters) {
      let result = [...this.violations];

      // Apply filters to individual inspections (no city filter - all ABQ)
      if (filters.dateRange && filters.dateRange !== 'all') {
        const daysAgo = parseInt(filters.dateRange);
        const cutoffDate = new Date();
        cutoffDate.setDate(cutoffDate.getDate() - daysAgo);
        
        result = result.filter(v => {
          const inspectionDate = new Date(v.inspection.date);
          return inspectionDate >= cutoffDate;
        });
      }

      if (filters.severity && filters.severity.length > 0) {
        result = result.filter(v => {
          const severity = this.getSeverityLevel(v.score.severity);
          return filters.severity.includes(severity);
        });
      }

      if (filters.search && filters.search.trim() !== '') {
        const query = filters.search.toLowerCase();
        result = result.filter(v =>
          v.establishment.name.toLowerCase().includes(query) ||
          v.establishment.address.toLowerCase().includes(query)
        );
      }

      // Group by restaurant
      const groupedRestaurants = this.groupByRestaurant(result);
      this.filteredViolations = groupedRestaurants;
      this.sortViolations();
    },

    getSeverityLevel(score) {
      if (score >= 3.0) return 'high';
      if (score >= 1.5) return 'medium';
      return 'low';
    },

    toTitleCase(str) {
      // Strip trailing ID codes (e.g., "-Pt0160304", "-24051", " #102460")
      str = str.replace(/[-\s](?:pt|id)?\d{4,}$/i, '');
      // Normalize "/DBA" or "/dba" to " DBA "
      str = str.replace(/[/]DBA\b/gi, ' DBA ');
      // Strip trailing store numbers (e.g., " 10386")
      str = str.replace(/\s+\d{4,}$/, '');

      let result = str.toLowerCase().split(' ').map((word, i) => {
        // Known uppercase abbreviations
        if (word.match(/^(llc|inc|dba|nw|ne|sw|se|abq|kfc)$/i)) {
          return word.toUpperCase();
        }
        // Roman numerals (i–xv)
        if (word.match(/^(i{1,3}|iv|vi{0,3}|ix|xi{0,3}|xiv|xv)$/i)) {
          return word.toUpperCase();
        }
        // Lowercase articles/prepositions/conjunctions (not first word)
        // But not single letters next to "&" (initials like "A & V")
        if (i > 0 && word.match(/^(a|an|and|at|by|for|in|of|on|or|the|to|with)$/)) {
          const words = str.toLowerCase().split(' ');
          const prevIsAmp = words[i - 1] === '&';
          const nextIsAmp = words[i + 1] === '&';
          if (word === 'a' && (prevIsAmp || nextIsAmp)) {
            return 'A';
          }
          return word;
        }
        // Handle hyphenated or slash-separated words (e.g., "taco bell/kfc")
        if (word.includes('-') || word.includes('/')) {
          const sep = word.includes('/') ? '/' : '-';
          return word.split(sep).map(part => {
            if (part.match(/^(llc|inc|dba|nw|ne|sw|se|abq|kfc)$/i)) return part.toUpperCase();
            return part.charAt(0).toUpperCase() + part.slice(1);
          }).join(sep);
        }
        // Capitalize first letter, skipping leading punctuation like (
        return word.replace(/([({["']?)(\w)/, (m, p, c) => p + c.toUpperCase());
      }).join(' ');

      // Restore missing apostrophes for known possessive brand names
      result = result.replace(/\b(Applebee|Blake|Cheddar|Church|Denny|Filiberto|Freddy|Lindy|Anita|Ruben|Santiago|Sergio|Spinn|Stacker|Stripe|Wendy|Yasmine|Allsup|Chili|Howie|Sprout|Farmer)s\b/g, "$1's");
      result = result.replace(/\bJimmy Johns\b/g, "Jimmy John's");
      result = result.replace(/\bMoka Joes\b/g, "Moka Joe's");
      result = result.replace(/\bDutch Bros\b/g, "Dutch Bros.");

      return result;
    },

    sortViolations() {
      if (!this.filteredViolations || this.filteredViolations.length === 0) {
        return;
      }

      const sorted = [...this.filteredViolations];
      
      switch (this.sortBy) {
        case 'severity':
          sorted.sort((a, b) => {
            // Primary sort by score
            if (b.score !== a.score) {
              return b.score - a.score;
            }
            // Tie-breaker: closed restaurants first
            if (a.isClosed !== b.isClosed) {
              return b.isClosed ? 1 : -1;
            }
            return 0;
          });
          break;
        case 'date':
          // Sort by most recent inspection
          sorted.sort((a, b) => {
            if (!a.inspections || !b.inspections) return 0;
            const aDate = new Date(Math.max(...a.inspections.map(i => new Date(i.date))));
            const bDate = new Date(Math.max(...b.inspections.map(i => new Date(i.date))));
            return bDate - aDate;
          });
          break;
        case 'name':
          sorted.sort((a, b) => a.name.localeCompare(b.name));
          break;
      }
      
      // Sort inspections within each restaurant by date (most recent first)
      sorted.forEach(restaurant => {
        if (restaurant.inspections) {
          restaurant.inspections.sort((a, b) => new Date(b.date) - new Date(a.date));
        }
      });
      
      this.filteredViolations = sorted;
    },

    exportToCSV() {
      const headers = ['Name', 'City', 'Address', 'Date', 'Outcome', 'Severity Score', 'Violations'];
      const rows = [];
      
      this.filteredViolations.forEach(restaurant => {
        restaurant.inspections.forEach(insp => {
          rows.push([
            restaurant.name,
            restaurant.city,
            restaurant.address,
            insp.date,
            insp.outcome,
            insp.score,
            insp.violations.map(v => v.desc).join('; ')
          ]);
        });
      });

      const csv = [
        headers.join(','),
        ...rows.map(row => row.map(cell => `"${cell}"`).join(','))
      ].join('\n');

      this.downloadFile(csv, 'violations.csv', 'text/csv');
    },

    exportToJSON() {
      const json = JSON.stringify(this.filteredViolations, null, 2);
      this.downloadFile(json, 'violations.json', 'application/json');
    },

    downloadFile(content, filename, mimeType) {
      const blob = new Blob([content], { type: mimeType });
      const url = URL.createObjectURL(blob);
      const link = document.createElement('a');
      link.href = url;
      link.download = filename;
      document.body.appendChild(link);
      link.click();
      document.body.removeChild(link);
      URL.revokeObjectURL(url);
    }
  });

  // No need for queueMicrotask - Alpine handles this

  // Filter controls component
  Alpine.data('filterControls', () => ({
    dateRange: 'all',
    selectedSeverity: [],
    searchQuery: '',

    init() {
      // Start with all severity levels selected
      this.selectedSeverity = ['high', 'medium', 'low'];
    },

    get activeFilterCount() {
      let count = 0;
      if (this.dateRange !== 'all') count++;
      if (this.selectedSeverity.length < 3) count++;
      if (this.searchQuery.trim() !== '') count++;
      return count;
    },

    toggleSeverity(level) {
      const index = this.selectedSeverity.indexOf(level);
      if (index > -1) {
        this.selectedSeverity.splice(index, 1);
      } else {
        this.selectedSeverity.push(level);
      }
      this.applyFilters();
    },

    resetFilters() {
      this.dateRange = 'all';
      this.selectedSeverity = ['high', 'medium', 'low'];
      this.searchQuery = '';
      this.applyFilters();
    },

    applyFilters() {
      // Update the global store (no city filter needed - all ABQ)
      Alpine.store('violations').filterViolations({
        dateRange: this.dateRange,
        severity: this.selectedSeverity,
        search: this.searchQuery
      });
    },

    // Sorting (integrated into filter controls)
    get sortBy() {
      return Alpine.store('violations').sortBy;
    },
    set sortBy(value) {
      Alpine.store('violations').sortBy = value;
    },
    changeSortOrder() {
      Alpine.store('violations').sortViolations();
    },

    // Results count
    get resultsCount() {
      return Alpine.store('violations').filteredViolations.length;
    },

    // Export functions
    exportToCSV() {
      Alpine.store('violations').exportToCSV();
    },
    exportToJSON() {
      Alpine.store('violations').exportToJSON();
    }
  }));



  // Violations list component (simplified - uses store)
  Alpine.data('violationsList', () => ({
    get violations() {
      return Alpine.store('violations')?.filteredViolations || [];
    },
    get loading() {
      return Alpine.store('violations')?.loading || false;
    },
    get error() {
      return Alpine.store('violations')?.error || null;
    },
    getSeverityLevel(score) {
      return Alpine.store('violations')?.getSeverityLevel(score) || 'low';
    },

    formatInspectionHeading(inspection, inspections) {
      const date = inspection.date;
      switch (inspection.outcome) {
        case 'closed':
          return `${date} — Closure Re-Inspection Required`;
        case 'failed':
          return `${date} — Unsatisfactory Re-Inspection Required`;
        case 'conditional':
          return `${date} — Conditional Approved`;
        case 'approved': {
          const thisDate = new Date(inspection.date);
          const hasAdversePrior = inspections.some(i => {
            const iDate = new Date(i.date);
            return iDate < thisDate && ['closed', 'failed', 'conditional'].includes(i.outcome);
          });
          return hasAdversePrior 
            ? `${date} — Passed Follow-Up Inspection`
            : `${date} — Approved`;
        }
        default:
          return `${date} — ${inspection.outcome}`;
      }
    },

    plainCategory(raw) {
      const map = {
        'equipment, food contact surfaces, and utensils clean': 'unclean equipment and food contact surfaces',
        'plumbing': 'plumbing issues',
        'training records': 'missing training records',
        'date marking and disposition': 'improper date marking',
        'surface not clean': 'unclean surfaces',
        'poisonous and toxic/chemical substances': 'improper chemical storage',
        'physical facilities, construction and repair': 'facility repair needed',
        'physical facilities, cleaning': 'unclean facilities',
        'physical facilities': 'facility maintenance issues',
        'ventilation and hood systems': 'ventilation problems',
        'storage': 'improper storage',
        'cold holding': 'improper cold holding temperatures',
        'personal cleanliness': 'personal cleanliness issues',
        'designated areas': 'improper designated areas',
        'pest control': 'pest control issues',
        'use limitations': 'equipment use violations',
        'use limitation': 'equipment use violations',
        'testing devices': 'missing or faulty testing devices',
        'food identification, safe, unadulterated and honestly presented': 'food labeling and safety issues',
        'operation and maintenance': 'operational maintenance issues',
        'maintenance and operation': 'operational maintenance issues',
        'food separation': 'improper food separation',
        'hands clean & properly washed': 'handwashing violations',
        'consumer advisories': 'missing consumer advisories',
        'warewashing temperature and concentration': 'warewashing temperature issues',
        'knowledgeable': 'lack of food safety knowledge',
        'hot holding & reheating': 'improper hot holding or reheating',
        'operations': 'operational violations',
        'cooling': 'improper cooling procedures',
        'surface condition': 'damaged surfaces',
        'lighting': 'inadequate lighting',
        'toilet facilities': 'toilet facility issues',
        'thawing': 'improper thawing procedures',
        'functionality and accuracy': 'equipment accuracy issues',
        'medications and first aid kits': 'medication storage issues',
        'records': 'missing records',
        'installation': 'improper equipment installation',
        'maintenance': 'maintenance issues',
        'preventing contamination from hands': 'bare hand contact with food',
        'hot & cold-water availability & pressure': 'water supply issues',
        'miscellaneous': 'miscellaneous violations',
        'preparation': 'food preparation issues',
        'equipment design': 'equipment design issues',
        'equipment maintenance and design': 'equipment maintenance issues',
      };
      const lower = raw.toLowerCase().trim();
      return map[lower] || lower;
    },

    generateInspectionWriteup(inspection) {
      if (inspection.writeup) return inspection.writeup;
      
      if (!inspection.violations || !Array.isArray(inspection.violations) || inspection.violations.length === 0) {
        return '';
      }
      
      const categories = [];
      inspection.violations.forEach(v => {
        const raw = (v.desc || v || '').toString().trim();
        if (!raw) return;
        const plain = this.plainCategory(raw);
        // Skip if this is a substring of an existing category or vice versa
        const dominated = categories.some(c => c.includes(plain));
        if (dominated) return;
        for (let i = categories.length - 1; i >= 0; i--) {
          if (plain.includes(categories[i])) {
            categories.splice(i, 1);
          }
        }
        categories.push(plain);
      });
      
      if (categories.length === 0) return '';
      if (categories.length === 1) return `Inspectors identified ${categories[0]}.`;
      const last = categories[categories.length - 1];
      const rest = categories.slice(0, -1);
      return `Inspectors identified ${rest.join(', ')}, and ${last}.`;
    }
  }));
});
