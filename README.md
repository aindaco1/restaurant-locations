# NM Health Code Violations Finder

A lightweight, fast Jekyll site that highlights recent restaurant health-code violators in New Mexico's 10 biggest cities. Built to help identify venues with recent closures or conditional approvals for filming location scouting.

🔗 **Live Site**: [GitHub Pages URL]

## Target Cities

Albuquerque, Las Cruces, Rio Rancho, Santa Fe, Roswell, Farmington, Hobbs, Clovis, Carlsbad, Alamogordo

## Features

- 🔍 **Smart Filtering**: City, date range, severity level, outcome type
- 📊 **Severity Scoring**: Rule-based scoring (closures > conditional > criticals)
- 📥 **Export**: Download filtered results as CSV/JSON
- ♿ **Accessible**: Keyboard navigation, semantic HTML, WCAG compliant
- ⚡ **Performant**: Static site, <20KB JS, Lighthouse score ≥95

## Tech Stack

- **Frontend**: Jekyll, SCSS (8px unit system), Alpine.js/HTMX
- **Data Pipeline**: Python (GitHub Actions scheduled)
- **Data Sources**: NMED API + Albuquerque PDF scraping
- **Hosting**: GitHub Pages
- **Optional Edge**: Cloudflare Workers (API proxy, dataset cache)

## Architecture

```
Frontend (Jekyll)         Data Pipeline (Actions)      Optional Edge
┌──────────────┐         ┌─────────────────────┐     ┌──────────────┐
│ Static HTML  │────────▶│ Python Scrapers     │────▶│ CF Workers   │
│ SCSS         │         │ - fetch_nmed.py     │     │ - API proxy  │
│ Vanilla JS   │◀────────│ - scrape_abq.py     │     │ - KV cache   │
│              │         │ - normalize.py      │     └──────────────┘
│ /data/*.json │         │ → violations.json   │
└──────────────┘         └─────────────────────┘
```

## Local Development

### Prerequisites

- Ruby 2.7+ and Bundler
- Python 3.9+
- Git

### Setup

```bash
# Install Jekyll dependencies
bundle install

# Install Python dependencies
pip install -r requirements.txt

# Start Jekyll dev server
bundle exec jekyll serve

# Open http://localhost:4000
```

### Generate Test Data

```bash
# Run data pipeline locally
python scripts/build_dataset.py

# Output: data/violations_latest.json
```

## Data Pipeline

Runs nightly via GitHub Actions:

1. **Fetch NMED**: Query statewide inspections (9 cities)
2. **Scrape ABQ**: Parse weekly PDF reports (Albuquerque/Bernalillo)
3. **Normalize**: Map to shared schema, compute severity scores
4. **Publish**: Commit JSON to `/data/`, update manifest

## Project Structure

```
/
├── _config.yml              # Jekyll configuration
├── _layouts/                # Page templates
│   ├── default.html
│   └── page.html
├── _includes/               # Reusable components
│   ├── head.html
│   ├── header.html
│   ├── footer.html
│   ├── filter-controls.html
│   └── violation-card.html
├── assets/
│   ├── main.scss            # SCSS entry point
│   ├── partials/
│   │   ├── _variables.scss  # Design tokens
│   │   ├── _mixins.scss     # Utilities
│   │   └── _components.scss # Component styles
│   └── js/
│       ├── app.js           # Filtering/sorting
│       ├── score.js         # Scoring logic
│       └── store.js         # Local cache
├── data/
│   ├── manifest.json        # Dataset versioning
│   ├── violations_latest.json
│   └── snapshots/           # Historical data
├── scripts/
│   ├── fetch_nmed.py        # NMED API client
│   ├── scrape_abq.py        # PDF parser
│   ├── normalize.py         # Schema mapping
│   └── build_dataset.py     # Pipeline orchestrator
├── .github/workflows/
│   ├── pipeline.yml         # Data refresh
│   └── pages.yml            # GitHub Pages deploy
└── index.html               # Main UI
```

## Data Model

```json
{
  "id": "state:city:establishment:inspectionDate",
  "source": "NMED|ABQ",
  "establishment": {
    "name": "Restaurant Name",
    "address": "123 Main St",
    "city": "Santa Fe",
    "county": "Santa Fe",
    "geo": {"lat": 35.6870, "lng": -105.9378}
  },
  "inspection": {
    "date": "2025-11-01",
    "type": "routine|complaint|followup|closure|reopen",
    "outcome": "approved|conditional|failed|closed|reopened",
    "violations": [
      {"code": "21-101", "critical": true, "desc": "..."}
    ]
  },
  "score": {
    "severity": 3.5,
    "reasons": ["closure within 180d", ">=2 criticals"]
  },
  "links": {
    "source": "https://...",
    "document": "https://..."
  }
}
```

## Severity Scoring

| Score | Badge | Criteria |
|-------|-------|----------|
| ≥3.0  | 🔴 HIGH | Closure within 180 days |
| 1.5–2.9 | 🟠 MEDIUM | Conditional/failed within 180d |
| <1.5  | 🟡 LOW | Minor violations or clean |

**Rules**:
- +3.0 for closure within 180 days
- +2.0 for conditional/failed within 180 days
- +0.5 per critical violation (cap +2.0, last 365 days)
- +0.5 if two adverse inspections within 365 days

## Contributing

See [agents.md](agents.md) for development guidelines and architecture details.

## Data Sources & Attribution

- **NMED**: New Mexico Environment Department (statewide inspections)
- **ABQ**: City of Albuquerque Environmental Health Department

All data is publicly available. This site provides aggregation and filtering for convenience.

## License

[MIT](LICENSE)

## Disclaimer

This tool is for informational purposes only. Always verify current health inspection status through official channels before making decisions.
