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
        const baseurl = document.querySelector('meta[name="baseurl"]')?.content || '/restaurant-locations';
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
      
      return Object.values(grouped);
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
      return str.toLowerCase().split(' ').map(word => {
        // Keep abbreviations and special cases uppercase
        if (word.match(/^(llc|inc|dba|nw|ne|sw|se)$/i)) {
          return word.toUpperCase();
        }
        // Handle hyphenated words
        if (word.includes('-')) {
          return word.split('-').map(part => 
            part.charAt(0).toUpperCase() + part.slice(1)
          ).join('-');
        }
        return word.charAt(0).toUpperCase() + word.slice(1);
      }).join(' ');
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
    }
  }));
});
