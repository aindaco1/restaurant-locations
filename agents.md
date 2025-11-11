Agents Overview — NM Health Code Violations Recommender

Goal: Build a lightweight, fast recommendation page that highlights recent restaurant health-code violators in New Mexico’s 10 biggest cities. Rationale: venues recently closed or conditionally approved may be more open to short‑notice, low‑cost filming agreements.

Target cities (top 10 by population): Albuquerque, Las Cruces, Rio Rancho, Santa Fe, Roswell, Farmington, Hobbs, Clovis, Carlsbad, Alamogordo.

⸻

Approach in One Glance
	•	Static site: Jekyll on GitHub Pages (HTML/SCSS/JS), performance‑first “Amp coding” style (see principles below).
	•	Data pipeline: GitHub Actions runs small Python scrapers/fetchers on a schedule; writes normalized JSON into /data/ and commits.
	•	APIs & sources (programmatic where possible):
	•	NMED (New Mexico Environment Department) — statewide restaurant inspections and outcomes. Expect REST endpoints (Apigee) and/or ArcGIS FeatureServer. Use for all cities except Albuquerque/Bernalillo.
	•	City of Albuquerque — publishes weekly Restaurant Inspection Report PDFs; scrape and normalize. (Bernalillo/ABQ has city‑run inspections.)
	•	Edge helpers (optional): Cloudflare Workers to proxy NMED endpoints (CORS + caching) and to serve a compact, versioned JSON manifest.
	•	Scoring: Rule‑based severity score (closures > conditional approvals > multiple criticals).
	•	UI: Single page with city/date filters, quick severity badges, CSV/JSON export.

⸻

Architecture

1) Frontend (Jekyll on GitHub Pages)
	•	Stack: Jekyll, Liquid templates, SCSS, vanilla JS + Alpine.js (or HTMX) for light interactivity. No heavy frameworks.
	•	Structure
	•	/index.html — main finder UI
	•	/_layouts/ — base, page
	•	/_includes/ — header, footer, filter controls, card components
	•	/assets/scss/ — modular SCSS (tokens, layout, components)
	•	/assets/js/ — app.js (filtering/sorting), score.js (shared scoring), store.js (local cache)
	•	/data/ — versioned JSON datasets produced by the pipeline
	•	Hosting: GitHub Pages (project site). Custom domain optional. Automatic builds on push to main.
	•	Performance: ship as a single HTML document, deferred JS, pre‑compressed assets via Actions, immutable cache headers via Worker (optional).

2) Data Pipeline (GitHub Actions)
	•	Jobs
	1.	Fetch NMED: hit Apigee/ArcGIS endpoints for the last 12 months; filter to the 9 non‑ABQ cities; write nmed_YYYY‑MM‑DD.json.
	2.	Scrape ABQ PDFs: parse weekly PDF tables -> abq_YYYY‑WW.json.
	3.	Normalize + Merge: map fields to a shared schema and compute scores -> violations_latest.json and violations_YYYY‑MM.json.
	4.	Publish: commit JSON to /data/, update /data/manifest.json with dataset hashes and dates.
	•	Schedule: nightly (UTC) and on‑demand manual dispatch.
	•	Secrets: API keys (if needed) stored in GitHub Secrets; Actions export to env at runtime.
	•	Reliability: small unit tests for parsers; fail the job if schema drifts.

3) Cloudflare Workers (optional but helpful)
	•	Worker #1 — API Proxy: GET /nmed?q=... → forwards to NMED with API key, sets Cache-Control: s-maxage=3600, adds Access-Control-Allow-Origin: *.
	•	Worker #2 — Dataset Edge Cache: serves /data/manifest.json and /data/violations_latest.json from KV/R2 with a SHORT TTL; fallback to GitHub raw if KV miss.
	•	Cron Triggers (optional): ping GitHub Actions workflow_dispatch for out‑of‑band refresh (e.g., after ABQ posts a new PDF).

4) Data Model (Normalized)

{
  "id": "state:city:establishment:inspectionDate",
  "source": "NMED|ABQ",
  "establishment": {
    "name": "string",
    "address": "string",
    "city": "string",
    "county": "string",
    "geo": {"lat": 0, "lng": 0}
  },
  "inspection": {
    "date": "YYYY-MM-DD",
    "type": "routine|complaint|followup|closure|reopen",
    "outcome": "approved|conditional|failed|closed|reopened",
    "violations": [{"code": "string", "critical": true, "desc": "string"}]
  },
  "score": {
    "severity": 0.0,
    "reasons": ["closure within 180d", ">=2 criticals"]
  },
  "links": {"source": "url", "document": "url"}
}

5) Scoring (v1, deterministic)
	•	Start at 0. Add:
	•	+3.0 for any closure within last 180 days.
	•	+2.0 for conditional/failed outcome within 180 days.
	•	+0.5 per critical violation (cap +2.0) within 365 days.
	•	+0.5 if two adverse inspections within 365 days.
	•	Severity badge:
	•	score >= 3.0 → HIGH (red)
	•	1.5 ≤ score < 3.0 → MEDIUM (amber)
	•	< 1.5 → LOW (green)

⸻

“Amp coding” principles (for this project)
	•	Performance‑first: tiny JS (<20KB gz), no runtime dependencies beyond Alpine/HTMX (pick one), no client‑side build steps.
	•	Progressive enhancement: basic results render without JS; JS adds filtering/sorting.
	•	Static‑friendly: generate JSON at build time; the page fetches /data/violations_latest.json.
	•	Simple components: HTML templates with small, isolated CSS; avoid global CSS bloat; utility classes allowed.
	•	Accessibility: keyboard‑navigable filters, semantic HTML, visible focus states, color‑contrast safe badges.

⸻

Styling Reference (dust-wave-shop patterns)

Reference repo: https://github.com/aindaco1/dust-wave-shop

1) SCSS Architecture
	•	Partial-based structure: main.scss imports partials/_variables, _mixins, _components, _overrides
	•	8px unit system: all spacing/sizing derives from $size--unit: 8px
	•	Semantic naming: double-dash for variants ($color--primary, $btn--pad-y)
	•	BEM-inspired components: .component, .component__element, .component--modifier

2) Key Patterns to Adopt
	•	Composable mixins: separate concerns (core styles, padding, hover effects)
	•	Responsive-first: mobile styles in @include sm {}, desktop as default
	•	Layout helper: @mixin fit-to-layout-and-center (max-width container with responsive padding)
	•	Component frames: consistent card/panel styling via mixin

3) Variables Template (adapted for health inspections)
	•	Colors: $color--danger (#d32f2f), $color--warning (#f57c00), $color--caution (#fbc02d), $color--safe (#388e3c)
	•	Typography: Inter font family, unit-based scale (h1: $size--unit * 7, body: $size--unit * 2.5)
	•	Spacing: multiples of $size--unit (4px, 8px, 16px, 24px, 32px, etc.)
	•	Layout: $layout--max-width: 1200px (wider than shop for data density)

4) Component Naming Convention
	•	.violation-card, .violation-card__header, .violation-card__severity
	•	.filter-panel, .filter-panel__group, .filter-panel__option
	•	.restaurant-header, .inspection-timeline

⸻

Repo Layout

/ (repo root)
├─ _config.yml
├─ _layouts/
├─ _includes/
├─ assets/
│  ├─ scss/
│  └─ js/
├─ data/
│  ├─ manifest.json
│  ├─ violations_latest.json
│  └─ snapshots/
├─ scripts/
│  ├─ fetch_nmed.py
│  ├─ scrape_abq.py
│  ├─ normalize.py
│  └─ build_dataset.py
├─ .github/workflows/
│  ├─ pipeline.yml
│  └─ pages.yml
├─ workers/
│  ├─ api-proxy.js
│  └─ dataset-cache.js
└─ index.html


⸻

GitHub Actions (pipeline.yml, sketch)
	•	Triggers: schedule: nightly, workflow_dispatch, push to scripts/.
	•	Steps:
	1.	Checkout
	2.	Setup Python
	3.	Install deps (pdfplumber, requests, pydantic, lxml)
	4.	Run scripts/build_dataset.py → writes /data files
	5.	JSON schema check
	6.	Commit & push (skip if no changes)

⸻

Frontend UI (MVP)
	•	Filters: city (multi‑select), date range (last 30/90/365), severity (LOW/MED/HIGH), outcome type.
	•	List: cards with name, city, last inspection date, outcome, severity badge, and “why” tooltip.
	•	Sort: by severity (desc), most recent, alphabetically.
	•	Export: Download CSV/JSON of current filtered set.
	•	(Optional) Map view with Leaflet if geocodes available.

⸻

Todos (Actionable)

Milestone 0 — Bootstrap (1 day)
	•	Create repo with Jekyll scaffold and GH Pages workflow
	•	Decide Alpine or HTMX; wire minimal filter UI
	•	Add SCSS tokens (colors, spacing, badges)

Milestone 1 — Data Ingestion (2–3 days)
	•	Implement fetch_nmed.py with date, city filters; write raw JSON
	•	Implement scrape_abq.py to parse latest weekly PDF → structured rows
	•	Implement normalize.py to map fields + compute scores
	•	Compose build_dataset.py to orchestrate & emit /data/violations_latest.json
	•	Add unit tests for parsers and scoring
	•	Set up pipeline.yml with nightly schedule + secrets

Milestone 2 — UI MVP (1–2 days)
	•	Fetch /data/violations_latest.json and render cards (server‑side include fallback)
	•	Filters: city, severity, date presets; client‑side search by name
	•	Sort controls and sticky toolbar
	•	CSV/JSON export of filtered results
	•	Basic a11y pass (labels, focus, contrast)

Milestone 3 — Edge & Polish (2 days)
	•	Cloudflare Worker #1 (API proxy with cache + CORS)
	•	Cloudflare Worker #2 (dataset cache from KV/R2)
	•	Add ETag/versioned URLs via manifest.json
	•	Lighthouse target: Perf ≥ 95, SEO ≥ 90, A11y ≥ 95
	•	Add sitemap.xml + robots.txt

Nice‑to‑Haves
	•	Map view with clustering and per‑city heat toggles
	•	Simple contact‑sheet export (PDF) for scouting
	•	Webhook/cron to refresh immediately when a new ABQ PDF appears
	•	Historical trends chart per city (last 12 months)
	•	Geocoding pass (Nominatim with caching) to enable map + distance sort

⸻

Risks & Mitigations
	•	ABQ PDFs change format → Keep parser tolerant; log anomalies, unit tests with fixture PDFs.
	•	NMED schema or auth changes → Abstract fetcher; feature-flag Apigee vs ArcGIS; document .env requirements.
	•	Rate limits / CORS → Use Worker proxy with caching; stagger Actions jobs.
	•	Data quality → Show source links on each card; emit a disclaimer; allow user feedback mailto.

⸻

Ops & Maintenance
	•	Monitoring: GitHub Actions badges for failures (optional)
	•	Versioning: Each dataset snapshot stored in /data/snapshots/ with date stamp
	•	Documentation: Keep this agents.md updated per milestone; add CONTRIBUTING.md with local dev steps

⸻

License & Compliance
	•	Attribution to data sources on About page; verify any usage policies on NMED/ABQ sites.
	•	No personal data beyond business listings/addresses.

⸻

Quick Start (Local Dev)
	1.	bundle install && bundle exec jekyll serve
	2.	Open http://localhost:4000 and verify UI loads
	3.	Run python scripts/build_dataset.py to generate /data/violations_latest.json
	4.	Commit and push to trigger Pages deploy