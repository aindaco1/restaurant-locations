# NM Health Code Violations Finder

A lightweight, fast Jekyll site that highlights recent restaurant health-code violators in Albuquerque, NM. Built to help identify venues with recent closures or conditional approvals for filming location scouting.

🔗 **Live Site**: https://healthcode.dustwave.xyz

## Target Cities

**Active**: Albuquerque (Bernalillo County)

**Planned**: Las Cruces, Rio Rancho, Santa Fe, Roswell, Farmington, Hobbs, Clovis, Carlsbad, Alamogordo — pending NMED bulk data access.

## Features

- 🔍 **Smart Filtering**: Date range, severity level, outcome type, text search
- 📊 **Severity Scoring**: Rule-based scoring (closures > conditional > criticals) with [methodology page](/scoring)
- 📋 **Accordion UI**: Expandable per-inspection panels with violation details
- 🏷️ **Smart Name Formatting**: Title case, possessive apostrophes, roman numerals, stripped ID codes
- 📝 **Human-Readable Writeups**: Regulatory violation categories mapped to plain English descriptions
- 🌙 **Dark Mode**: System-aware theme toggle with persistent preference
- 🚫 **Zero-Score Filtering**: Restaurants with 0.0 severity are automatically hidden
- 📥 **Export**: Download filtered results as CSV/JSON
- ♿ **Accessible**: Keyboard navigation, semantic HTML, WCAG compliant
- ⚡ **Performant**: Static site, <8KB first-party JS gzip, cacheable versioned data

## Tech Stack

- **Frontend**: Jekyll 4.x, SCSS (8px unit system), Alpine.js 3.16.3
- **Data Pipeline**: Python 3.11+ (GitHub Actions scheduled)
- **Active Data Source**: City of Albuquerque inspection-report PDFs
- **Planned Expansion**: NMED bulk data for the other nine target cities
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

# Validate the same production performance contract used in CI
bundle exec jekyll build
python3 scripts/optimize_site.py
python3 scripts/validate_site.py
```

## Deployment

### GitHub Pages Setup

1. **Enable GitHub Pages**
   - Go to Settings → Pages
   - Source: "GitHub Actions"
   - Site deploys automatically on push to `main`

2. **Configure Secrets** (Optional - for data pipeline)
   - Go to Settings → Secrets and variables → Actions
   - Add `ABQ_PDF_BASE_URL` only if the City changes the default documents URL

3. **Deploy**
   ```bash
   git add .
   git commit -m "Initial deployment"
   git push origin main
   ```

### Workflows

**Jekyll Deploy** (`.github/workflows/pages.yml`)
- Triggers: pull requests, pushes to `main`, completed data pipelines, or manual runs
- Builds and validates every change; deploys non-PR runs to GitHub Pages
- Compacts the generated dataset and fingerprints first-party assets without rewriting source files
- Optionally reconciles the hostname-scoped Cloudflare configuration after deployment
- Verifies the deployed shell and dataset hash through the production domain

**Data Pipeline** (`.github/workflows/pipeline.yml`)
- Triggers: relevant pull requests, nightly at 2 AM UTC, manual, or data-code pushes
- Runs unit tests on every trigger; non-PR runs fetch, normalize, and commit `/data/`
- Serializes refreshes so scheduled and manual runs cannot push concurrently

### Frontend Performance Contract

The browser runtime keeps Alpine.js because the filtering and export UI uses it
substantially. The CDN URL and integrity hash are pinned, and Alpine store
initialization must remain idempotent so the dataset is fetched and rendered
once. The unversioned manifest bypasses browser caching; the dataset URL includes
the manifest's content hash and is intentionally cacheable.

`scripts/validate_site.py` protects the current first-party JavaScript, CSS, and
compressed dataset budgets. `scripts/optimize_site.py` compacts only the generated
Pages artifact and gives CSS, JS, and images content-hashed filenames, preserving
readable source data and useful Git diffs.

### Cloudflare Configuration

The live `Healthcode performance safeguards` Configuration Rule matches only
`healthcode.dustwave.xyz` and disables Rocket Loader and Real User Monitoring
injection. `scripts/sync_cloudflare_config.mjs` is the idempotent source of truth
for that rule plus immutable caching for fingerprinted assets and the
content-versioned dataset. The unversioned manifest is deliberately excluded.

Run a read-only drift check with a token scoped to the `dustwave.xyz` zone:

```bash
CLOUDFLARE_ZONE_ID=ddfc222a15b5afa8a71ae72f633159af \
  CLOUDFLARE_API_TOKEN="$CLOUDFLARE_API_TOKEN" \
  node scripts/sync_cloudflare_config.mjs --check
```

For automatic post-deploy reconciliation, set repository secrets
`CLOUDFLARE_API_TOKEN` and `CLOUDFLARE_ZONE_ID`, then set the repository variable
`CLOUDFLARE_CONFIG_SYNC=true`. The token needs zone-scoped Configuration Rules
edit and Cache Rules edit access, plus the Rulesets permissions Cloudflare lists
for Cache Rules. Never commit the token or put it in `.dev.vars` for this site.

WebMCP remains a separate zone-wide beta setting. It is intentionally not
managed by the hostname-scoped script because changing it affects every
`dustwave.xyz` subdomain.

## Architecture

```
Frontend (Jekyll)         Data Pipeline (Actions)
┌──────────────┐         ┌─────────────────────┐
│ Static HTML  │────────▶│ Python Scrapers     │
│ SCSS (8px)   │         │ - scrape_abq.py     │
│ Alpine.js    │◀────────│ - normalize.py      │
│              │         │ - build_dataset.py  │
│ /data/*.json │         │ → violations.json   │
└──────────────┘         └─────────────────────┘
```

### Data Pipeline Flow

1. **Scrape ABQ**: Parse the current and archived PDF reports
2. **Normalize + Merge**: Map to the shared schema, score, and deduplicate
3. **Publish**: Commit readable JSON to `/data/` and update the manifest hash
4. **Deploy**: Compact only the generated Pages copy and verify it in production

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
│   └── filter-controls.html
├── assets/
│   ├── main.scss            # SCSS entry point
│   ├── partials/
│   │   ├── _variables.scss  # Design tokens (8px unit system)
│   │   ├── _mixins.scss     # Utilities & breakpoints
│   │   ├── _components.scss # Component styles (BEM)
│   │   ├── _dark-mode.scss  # Dark mode overrides
│   │   ├── _theme-toggle.scss # Theme toggle component
│   │   └── _status-key.scss # Status key legend
│   └── js/
│       ├── app.js           # Alpine.js app (filters, sort, export)
│       └── theme.js         # Dark mode theme toggle
├── data/
│   ├── violations_latest.json  # Current dataset
│   ├── manifest.json           # Dataset metadata
│   └── snapshots/              # Historical snapshots
├── scripts/
│   ├── scrape_abq.py        # ABQ PDF scraper
│   ├── normalize.py         # Schema normalization + scoring
│   ├── build_dataset.py     # Pipeline orchestrator
│   ├── optimize_site.py     # Compact data and fingerprint production assets
│   ├── validate_site.py     # Static performance contract
│   ├── verify_production.py # Deployed shell/data verification
│   └── tests/
│       └── test_scoring.py  # Unit tests
├── .github/workflows/
│   ├── pipeline.yml         # Data refresh workflow
│   └── pages.yml            # GitHub Pages deploy
├── index.html               # Main UI
└── scoring.html             # Scoring methodology page
```

## Data Model

```json
{
  "id": "state:city:establishment:inspectionDate",
  "source": "ABQ",
  "operational_status": "Open|Closed",
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
    "writeup": "Human-readable summary of inspection findings",
    "violations": [
      {"code": "21-101", "critical": true, "desc": "...", "observation": "Specific observed issue"}
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
- Keep first-party browser JavaScript **≤ 8KB gzipped**
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

## Data Source

### City of Albuquerque Environmental Health Department

- **Coverage**: Albuquerque & Bernalillo County
- **Format**: Weekly PDF inspection reports
- **Current Data**: Archive begins in September 2025; see
  [`data/manifest.json`](data/manifest.json) for the live record count and version
- **Update Frequency**: Daily automated scraping (2 AM UTC)
- **Archive Mode**: Accumulates all inspections over time
- **Source URL**: https://www.cabq.gov/environmentalhealth/documents/

**Primary PDF Source:**
- `chpd_main_inspection_report.pdf` — scraped daily to capture data before it's overwritten weekly
- `media-report-[dates].pdf` (historical weeks)

**Data Includes:**
- Establishment name, address
- Inspection date and outcome
- Operational status (Open/Closed)
- Violation descriptions
- Only non-approved inspections (Conditional, Unsatisfactory, Closure)

## Expanding Beyond Albuquerque

To add other NM cities, contact **NMED Food Safety Program**:
- Email: NMED.Food.Program@env.nm.gov  
- Phone: (505) 827-2821
- Request: Bulk data export for Las Cruces, Rio Rancho, Santa Fe, etc.

### Optional Enhancements
- [x] Static performance budgets, one-fetch dataset loading, and generated JSON compaction
- [x] Host-scoped Cloudflare rule disables Rocket Loader and Web Analytics injection
- [x] Content-addressed production assets support immutable Cloudflare caching
- [x] Keep the beta WebMCP bridge enabled and outside this hostname-scoped automation
- [ ] Continue toward Lighthouse Perf ≥95 and A11y ≥95 after provider tuning
- [ ] Map view with Leaflet (if geocoding available)
- [ ] Historical trends charts
- [ ] Email alerts for new closures

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
