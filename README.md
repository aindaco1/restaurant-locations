# NM Health Code Violations Finder

A lightweight, fast Jekyll site that highlights recent restaurant health-code violators in New Mexico's 10 biggest cities. Built to help identify venues with recent closures or conditional approvals for filming location scouting.

🔗 **Live Site**: `https://aindaco1.github.io/restaurant-locations` (after deployment)

## Target Cities

Albuquerque, Las Cruces, Rio Rancho, Santa Fe, Roswell, Farmington, Hobbs, Clovis, Carlsbad, Alamogordo

## Features

- 🔍 **Smart Filtering**: City, date range, severity level, outcome type
- 📊 **Severity Scoring**: Rule-based scoring (closures > conditional > criticals)
- 📥 **Export**: Download filtered results as CSV/JSON
- ♿ **Accessible**: Keyboard navigation, semantic HTML, WCAG compliant
- ⚡ **Performant**: Static site, <20KB JS, Lighthouse score ≥95

## Tech Stack

- **Frontend**: Jekyll 4.3, SCSS (8px unit system), Alpine.js 3.x
- **Data Pipeline**: Python 3.11+ (GitHub Actions scheduled)
- **Data Sources**: NMED API + Albuquerque PDF scraping
- **Hosting**: GitHub Pages
- **CI/CD**: GitHub Actions

## Quick Start

### Local Development

```bash
# Install Jekyll dependencies
bundle install

# Start Jekyll dev server
bundle exec jekyll serve

# Open http://localhost:4000
```

### Data Pipeline (Optional)

```bash
# Install Python dependencies
pip install -r requirements.txt

# Run data pipeline
python scripts/build_dataset.py

# Run tests
pytest scripts/tests/
```

## Deployment

### GitHub Pages Setup

1. **Enable GitHub Pages**
   - Go to Settings → Pages
   - Source: "GitHub Actions"
   - Site deploys automatically on push to `main`

2. **Configure Secrets** (Optional - for data pipeline)
   - Go to Settings → Secrets and variables → Actions
   - Add these secrets if you have API access:
     - `NMED_API_KEY` - API key for NMED endpoints
     - `NMED_APIGEE_URL` - Custom Apigee endpoint URL
     - `NMED_ARCGIS_URL` - Custom ArcGIS FeatureServer URL
     - `ABQ_PDF_BASE_URL` - Base URL for ABQ PDF reports

3. **Deploy**
   ```bash
   git add .
   git commit -m "Initial deployment"
   git push origin main
   ```

### Workflows

**Jekyll Deploy** (`.github/workflows/pages.yml`)
- Triggers: Push to `main`
- Builds and deploys site to GitHub Pages

**Data Pipeline** (`.github/workflows/pipeline.yml`)
- Triggers: Nightly at 2 AM UTC, manual, or push to scripts/
- Fetches data, normalizes, and commits to `/data/`

## Architecture

```
Frontend (Jekyll)         Data Pipeline (Actions)
┌──────────────┐         ┌─────────────────────┐
│ Static HTML  │────────▶│ Python Scrapers     │
│ SCSS (8px)   │         │ - fetch_nmed.py     │
│ Alpine.js    │◀────────│ - scrape_abq.py     │
│              │         │ - normalize.py      │
│ /data/*.json │         │ → violations.json   │
└──────────────┘         └─────────────────────┘
```

### Data Pipeline Flow

1. **Fetch NMED**: Query statewide inspections (9 cities via API)
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
│   │   ├── _variables.scss  # Design tokens (8px unit system)
│   │   ├── _mixins.scss     # Utilities & breakpoints
│   │   └── _components.scss # Component styles (BEM)
│   └── js/
│       ├── app.js           # Alpine.js app (filters, sort, export)
│       └── score.js         # Severity scoring logic
├── data/
│   ├── violations_latest.json  # Current dataset
│   ├── manifest.json           # Dataset metadata
│   └── snapshots/              # Historical snapshots
├── scripts/
│   ├── fetch_nmed.py        # NMED API fetcher
│   ├── scrape_abq.py        # ABQ PDF scraper
│   ├── normalize.py         # Schema normalization + scoring
│   ├── build_dataset.py     # Pipeline orchestrator
│   └── tests/
│       └── test_scoring.py  # Unit tests
├── .github/workflows/
│   ├── pipeline.yml         # Data refresh workflow
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

Scores are calculated based on inspection outcomes and violations:

| Score | Badge | Criteria |
|-------|-------|----------|
| ≥3.0  | 🔴 HIGH | Closure within 180 days |
| 1.5–2.9 | 🟠 MEDIUM | Conditional/failed within 180d |
| <1.5  | 🟡 LOW | Minor violations or clean |

**Scoring Rules:**
- +3.0 for closure within 180 days
- +2.0 for conditional/failed within 180 days
- +0.5 per critical violation (cap at +2.0, within 365 days)
- +0.5 if two adverse inspections within 365 days

## Development Guidelines

### SCSS/CSS
- Use **8px unit system**: all spacing = multiples of `$size--unit`
- Follow **BEM naming**: `.component`, `.component__element`, `.component--modifier`
- Use **semantic variables**: `$color--danger`, not `$red`
- **Mobile-first** responsive design with breakpoint mixins

### JavaScript
- Keep bundle **< 20KB gzipped**
- **Progressive enhancement** (works without JS)
- Use **Alpine.js** for reactivity, avoid heavy frameworks
- No client-side build steps

### Python
- Follow **PEP 8** style guide
- Add **type hints** where appropriate
- Write **unit tests** for scoring logic
- Handle API failures gracefully (return empty datasets)

## Troubleshooting

### Jekyll Build Fails
```bash
# Clear cache and rebuild
rm -rf _site .jekyll-cache
bundle exec jekyll build
```

### Python Pipeline Errors
```bash
# Check dependencies
pip install -r requirements.txt

# Run with validation
python scripts/build_dataset.py --validate
```

### No Data Showing
- Ensure `data/violations_latest.json` exists
- Check browser console for fetch errors
- Verify `baseurl` in `_config.yml` matches deployment

## Data Sources

### ✅ City of Albuquerque (ACTIVE)
- **Coverage**: Albuquerque & Bernalillo County
- **Format**: Weekly PDF reports
- **Current Data**: 88 inspections from 5 weeks (Sept-Nov 2025)
- **Update**: Automated scraping via GitHub Actions
- **URL**: https://www.cabq.gov/environmentalhealth/documents/

### ⏸️ NMED (Pending - 9 Other Cities)
- **Coverage**: Las Cruces, Rio Rancho, Santa Fe, Roswell, Farmington, Hobbs, Clovis, Carlsbad, Alamogordo
- **Status**: NMED API portal does not include food inspection data
- **Next Step**: Contact NMED Food Safety Program for data access
- **Contact**: NMED.Food.Program@env.nm.gov or (505) 827-2821

## Next Steps

### API Configuration
Once you have API access:
1. Update endpoint URLs in scripts
2. Add API keys to GitHub Secrets
3. Test pipeline: `python scripts/build_dataset.py`
4. Monitor GitHub Actions for nightly runs

### Optional Enhancements
- [ ] Cloudflare Workers for API proxy and edge caching
- [ ] Lighthouse optimization (target: Perf ≥95, A11y ≥95)
- [ ] Map view with Leaflet (if geocoding available)
- [ ] Historical trends charts

## Contributing

See [agents.md](agents.md) for detailed architecture and development guidelines.

## License

[MIT](LICENSE)

## Disclaimer

This tool is for informational purposes only. Always verify current health inspection status through official channels before making decisions.

---

**Data Sources:**
- [NMED](https://www.env.nm.gov/)
- [ABQ Environmental Health](https://www.cabq.gov/environmentalhealth)
