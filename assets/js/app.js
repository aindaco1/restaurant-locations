// Main application logic for NM Health Code Violations Finder
// Uses Alpine.js for reactive UI

document.addEventListener('alpine:init', () => {
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
    selectedCities: [],
    dateRange: '365',
    selectedSeverity: [],
    searchQuery: '',

    init() {
      // Initialize with all cities selected
      this.selectedCities = [...this.cities];
      this.selectedSeverity = ['high', 'medium', 'low'];
    },

    resetFilters() {
      this.selectedCities = [...this.cities];
      this.dateRange = '365';
      this.selectedSeverity = ['high', 'medium', 'low'];
      this.searchQuery = '';
      this.applyFilters();
    },

    applyFilters() {
      // Dispatch custom event for violation list to listen to
      window.dispatchEvent(new CustomEvent('filters-changed', {
        detail: {
          cities: this.selectedCities,
          dateRange: this.dateRange,
          severity: this.selectedSeverity,
          search: this.searchQuery
        }
      }));
    }
  }));

  // Violations list component
  Alpine.data('violationsList', () => ({
    violations: [],
    filteredViolations: [],
    sortBy: 'severity',
    loading: true,
    error: null,

    async init() {
      await this.loadViolations();
      
      // Listen for filter changes
      window.addEventListener('filters-changed', (e) => {
        this.filterViolations(e.detail);
      });
    },

    async loadViolations() {
      try {
        const response = await fetch('/restaurant-locations/data/violations_latest.json');
        
        if (!response.ok) {
          throw new Error(`HTTP error! status: ${response.status}`);
        }
        
        const data = await response.json();
        this.violations = data;
        this.filteredViolations = [...data];
        this.loading = false;
      } catch (error) {
        console.error('Failed to load violations:', error);
        this.error = error.message;
        this.loading = false;
        // Use empty array for demo
        this.violations = [];
        this.filteredViolations = [];
      }
    },

    filterViolations(filters) {
      let result = [...this.violations];

      // Filter by city
      if (filters.cities && filters.cities.length > 0) {
        result = result.filter(v => 
          filters.cities.includes(v.establishment.city)
        );
      }

      // Filter by date range
      if (filters.dateRange && filters.dateRange !== 'all') {
        const daysAgo = parseInt(filters.dateRange);
        const cutoffDate = new Date();
        cutoffDate.setDate(cutoffDate.getDate() - daysAgo);
        
        result = result.filter(v => {
          const inspectionDate = new Date(v.inspection.date);
          return inspectionDate >= cutoffDate;
        });
      }

      // Filter by severity
      if (filters.severity && filters.severity.length > 0) {
        result = result.filter(v => {
          const severity = this.getSeverityLevel(v.score.severity);
          return filters.severity.includes(severity);
        });
      }

      // Filter by search query
      if (filters.search && filters.search.trim() !== '') {
        const query = filters.search.toLowerCase();
        result = result.filter(v =>
          v.establishment.name.toLowerCase().includes(query) ||
          v.establishment.address.toLowerCase().includes(query)
        );
      }

      this.filteredViolations = result;
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
          sorted.sort((a, b) => b.score.severity - a.score.severity);
          break;
        case 'date':
          sorted.sort((a, b) => 
            new Date(b.inspection.date) - new Date(a.inspection.date)
          );
          break;
        case 'name':
          sorted.sort((a, b) => 
            a.establishment.name.localeCompare(b.establishment.name)
          );
          break;
      }
      
      this.filteredViolations = sorted;
    },

    changeSortOrder(order) {
      this.sortBy = order;
      this.sortViolations();
    },

    exportToCSV() {
      const headers = ['Name', 'City', 'Address', 'Date', 'Outcome', 'Severity Score', 'Severity'];
      const rows = this.filteredViolations.map(v => [
        v.establishment.name,
        v.establishment.city,
        v.establishment.address,
        v.inspection.date,
        v.inspection.outcome,
        v.score.severity,
        this.getSeverityLevel(v.score.severity)
      ]);

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
  }));
});
