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

    async init() {
      await this.loadViolations();
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
        this.filteredViolations = [...data];
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
        const key = `${v.establishment.name}-${v.establishment.address}`;
        if (!grouped[key]) {
          grouped[key] = {
            name: v.establishment.name,
            address: v.establishment.address,
            city: v.establishment.city,
            inspections: [],
            maxScore: 0
          };
        }
        grouped[key].inspections.push({
          date: v.inspection.date,
          outcome: v.inspection.outcome,
          violations: v.inspection.violations,
          score: v.score.severity,
          reasons: v.score.reasons,
          links: v.links
        });
        grouped[key].maxScore = Math.max(grouped[key].maxScore, v.score.severity);
      });
      
      return Object.values(grouped);
    },

    filterViolations(filters) {
      let result = [...this.violations];

      // Apply filters to individual inspections
      if (filters.cities && filters.cities.length > 0) {
        result = result.filter(v => filters.cities.includes(v.establishment.city));
      }

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

    sortViolations() {
      const sorted = [...this.filteredViolations];
      
      switch (this.sortBy) {
        case 'severity':
          sorted.sort((a, b) => b.maxScore - a.maxScore);
          break;
        case 'date':
          // Sort by most recent inspection
          sorted.sort((a, b) => {
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
        restaurant.inspections.sort((a, b) => new Date(b.date) - new Date(a.date));
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

  // Initialize store data after Alpine is ready
  queueMicrotask(() => {
    Alpine.store('violations').init();
  });

  // Filter controls component
  Alpine.data('filterControls', () => ({
    cities: [
      'Albuquerque',
      'Las Cruces',
      'Rio Rancho',
      'Santa Fe',
      'Roswell',
      'Farmington',
      'Hobbs',
      'Clovis',
      'Carlsbad',
      'Alamogordo'
    ],
    cityFilter: '', // Single city filter (empty = all)
    dateRange: 'all',
    selectedSeverity: [],
    searchQuery: '',

    init() {
      // Start with all severity levels selected
      this.selectedSeverity = ['high', 'medium', 'low'];
    },

    get activeFilterCount() {
      let count = 0;
      if (this.cityFilter !== '') count++;
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

    handleCityFilter() {
      this.applyFilters();
    },

    resetFilters() {
      this.cityFilter = '';
      this.dateRange = 'all';
      this.selectedSeverity = ['high', 'medium', 'low'];
      this.searchQuery = '';
      this.applyFilters();
    },

    applyFilters() {
      // Build cities array based on filter
      const cities = this.cityFilter === '' ? this.cities : [this.cityFilter];
      
      // Update the global store
      Alpine.store('violations').filterViolations({
        cities: cities,
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
      return Alpine.store('violations').filteredViolations;
    },
    get loading() {
      return Alpine.store('violations').loading;
    },
    get error() {
      return Alpine.store('violations').error;
    },
    getSeverityLevel(score) {
      return Alpine.store('violations').getSeverityLevel(score);
    }
  }));
});
