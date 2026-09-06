# NM Health Code Violations Finder

A lightweight Jekyll site for finding Albuquerque restaurants with recent health-code violations, built for filming location scouting.

[Open the finder](https://healthcode.dustwave.xyz) · [Documentation](docs/README.md) · [Scoring page source](scoring.html)

## Current scope

The active pipeline collects City of Albuquerque inspection-report PDFs and accumulates an inspection archive. Expansion to Las Cruces, Rio Rancho, Santa Fe, Roswell, Farmington, Hobbs, Clovis, Carlsbad, and Alamogordo is deferred pending NMED bulk data access.

The finder provides:

- Name/address search, date and severity filters, and severity/date/name sorting.
- Restaurant cards with per-inspection accordions and plain-English writeups.
- CSV/JSON export of filtered results.
- Persistent light/dark mode, defaulting to dark.

Results require JavaScript and Alpine.js. The stack is Jekyll 4.x, SCSS, Alpine.js, and Python, with GitHub Actions for data refreshes and GitHub Pages deployment. See [architecture and data](docs/architecture.md) for the implementation and known limitations.

The checked-in [manifest](data/manifest.json) records the archive's generation time, record count, and content hash. Those values describe this checkout; check the deployed manifest and workflow runs when assessing production freshness.

## Quick start

Run from the repository root with Ruby/Bundler installed:

```bash
bundle install
bundle exec jekyll serve
```

Open [localhost:4000](http://localhost:4000). The checked-in dataset is sufficient for local UI work.

For Python setup, tests, and the production build checks, use the [development guide](docs/development.md). A data refresh fetches remote PDFs and rewrites data files; its commands and recovery steps are in [operations](docs/operations.md).

## Documentation

| Guide | Purpose |
| --- | --- |
| [Documentation index](docs/README.md) | Where each topic belongs |
| [Architecture and data](docs/architecture.md) | Current scope, data lifecycle, schema, scoring, and deferred work |
| [Development](docs/development.md) | Setup, checks, and coding conventions |
| [Operations](docs/operations.md) | Data refreshes, deployment, Cloudflare, and troubleshooting |
| [Agent instructions](AGENTS.md) | Repository instructions for coding agents |

## Attribution and license

Inspection data comes from the [City of Albuquerque Environmental Health Department](https://www.cabq.gov/environmentalhealth). NMED is a planned source, not an active feed.

For informational purposes only. Verify current inspection and operating status through official channels before making decisions.

Code is licensed under the [MIT License](LICENSE).
