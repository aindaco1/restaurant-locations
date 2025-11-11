// Theme switcher for dark/light mode
// Default: dark mode

document.addEventListener('alpine:init', () => {
  Alpine.store('theme', {
    current: 'dark',

    init() {
      // Check localStorage or default to dark
      const saved = localStorage.getItem('theme');
      this.current = saved || 'dark';
      this.apply();
    },

    toggle() {
      this.current = this.current === 'dark' ? 'light' : 'dark';
      this.apply();
      localStorage.setItem('theme', this.current);
    },

    apply() {
      document.documentElement.setAttribute('data-theme', this.current);
    },

    get isDark() {
      return this.current === 'dark';
    }
  });

  // Initialize theme immediately
  Alpine.store('theme').init();
});
