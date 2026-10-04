# Architecture and data

For contributors investigating current behavior or planning changes. For commands and releases, see [development](development.md) and [operations](operations.md).

## Scope and components

The implemented source is City of Albuquerque inspection-report PDFs. The other nine target cities—Las Cruces, Rio Rancho, Santa Fe, Roswell, Farmington, Hobbs, Clovis, Carlsbad, and Alamogordo—remain deferred pending NMED bulk access. `NMEDNormalizer` is a template retained for expansion; there is no active NMED fetcher or implemented Cloudflare Worker.

| Location | Responsibility |
| --- | --- |
| [index.html](../index.html), [_layouts/](../_layouts/), [_includes/](../_includes/) | Jekyll page shell and reusable markup |
| [assets/main.scss](../assets/main.scss), [assets/partials/](../assets/partials/) | Styles and design tokens |
| [assets/js/app.js](../assets/js/app.js) | Shared Alpine data store, filtering, grouping, sorting, writeups, and exports |
| [assets/js/theme.js](../assets/js/theme.js) | Persistent theme preference; dark by default |
| [scripts/scrape_abq.py](../scripts/scrape_abq.py) | PDF discovery, parsing, and raw weekly output |
| [scripts/normalize.py](../scripts/normalize.py) | Pydantic models, normalization, and inspection scores |
| [scripts/build_dataset.py](../scripts/build_dataset.py), [scripts/archive.py](../scripts/archive.py) | Stable identity, archive merge, snapshots, and manifest |
| [scripts/validate_archive.py](../scripts/validate_archive.py), [scripts/recover_history.py](../scripts/recover_history.py) | Archive preservation gate and audited historical recovery |
| [scripts/optimize_site.py](../scripts/optimize_site.py), [scripts/dataset_transport.py](../scripts/dataset_transport.py) | Generated JSON compaction, lossless browser transport, and asset fingerprinting |
| [scripts/validate_site.py](../scripts/validate_site.py) | Generated-site performance contract |
| [scripts/verify_production.py](../scripts/verify_production.py) | Remote shell and dataset verification |
| [scripts/sync_cloudflare_config.mjs](../scripts/sync_cloudflare_config.mjs) | Hostname-scoped Cloudflare rules |
| [scoring.html](../scoring.html) | Public scoring explanation |

## Data lifecycle

1. The scraper always tries `chpd_main_inspection_report.pdf` and discovers additional report PDFs from the ABQ documents page. The daily workflow is intended to capture the main report before its weekly replacement. The `--weeks` argument currently does not constrain discovery.
2. Summary pages provide establishments, dates, outcomes, and operational status. Detail pages provide violation categories and observations. For restaurants with at least one adverse inspection in the fetched reports, the scraper retains all fetched inspections, including approved follow-ups.
3. Raw rows are deduplicated by name, address, date, and outcome; a duplicate with more violation details wins. Adverse-inspection eligibility is evaluated per name/address. Successful, nonempty fetches are written to `data/abq_YYYY_WW.json`, replacing that week's raw file on another run.
4. Archive identity is `(source, name, address, city, date, outcome)`, with case and repeated whitespace normalized. IDs are `abq:v2:<20 hex characters>` derived from SHA-256 of that tuple; uniqueness is validated. The builder migrates legacy IDs without changing other values and appends unseen identities. Existing records win and are not rescored or replaced. Same-day outcomes and distinct addresses remain separate; incoming repeats are deduplicated within the same fetch.
5. `data/snapshots/violations_YYYY-MM.json` is overwritten with the current normalized fetch, not the accumulated archive. These snapshots are ignored by Git and uploaded by the data workflow as artifacts with 30-day retention.
6. The manifest describes the merged archive. Its version is the first eight hex characters of SHA-256 over `json.dumps(dataset, sort_keys=True)`. This hashes the logical JSON serialization, not the deployed file bytes.

The checked-in raw NMED file is historical input and is not read by the active builder. The builder reads and validates the archive before fetching. Unreadable archives, failed downloads/parsing, empty eligible fetches, or any normalization failure stop the job before data files are written. Successful writes use atomic file replacement. CI compares inspection identities against the PR base or pre-push archive and again against the committed archive after a refresh; a larger record count does not excuse losing an older outcome. A successful fetch with zero *new* records remains valid and preserves existing values.

## Normalized record

The model definitions in [normalize.py](../scripts/normalize.py) and actual [dataset](../data/violations_latest.json) are the schema reference.

| Field | Current ABQ behavior |
| --- | --- |
| `id`, `source` | Versioned composite-identity ID; source is `ABQ` |
| `operational_status` | Raw `Open`/`Closed` status, default `Open`; added after Pydantic serialization |
| `establishment` | Name, address, city `Albuquerque`, county `Bernalillo`, and city-center coordinates |
| `inspection` | Date, type `routine`, normalized outcome, violations, and empty `writeup` |
| `inspection.violations[]` | `code`, `critical`, `desc`, and `observation`; missing code/critical default to empty/false |
| `score` | Numeric `severity` and textual `reasons` calculated at normalization time |
| `links` | Source department URL and nullable document URL |

Coordinates are placeholders, not individual restaurant geocodes. The current PDF parser supplies categories and observations but does not populate critical flags or attach a `pdf_url` to each record, so those fields cannot be assumed complete. The frontend generates readable writeups from violation categories.

## Scoring and grouping

There are two calculations, with different consumers.

**Stored inspection scores** come from `SeverityCalculator`:

| Rule | Points | Window at calculation time |
| --- | --- | --- |
| Closure | +3.0 | 180 days |
| Conditional/failed outcome | +2.0 | 180 days |
| Each critical violation | +0.5, capped at +2.0 | 365 days |
| Two or more adverse inspections | +0.5 | 365 days; requires history supplied to the calculator |

The active normalizers call the calculator without inspection history, so the repeated-adverse bonus is not applied by the pipeline. Existing archive entries retain their original scores as they age. Manifest severity counts and the browser's severity filter use these stored scores. Thresholds are high at ≥3.0, medium at ≥1.5 and <3.0, and low below 1.5.

**Restaurant ranking** is recalculated by `groupByRestaurant()` in the browser. It groups by trimmed, lowercased name, orders inspections newest first, and sums +3 for each closure and +2 for each conditional/failed outcome within 180 days. It adds +5 when the latest included inspection's operational status is exactly `Closed`. It does not sum stored inspection scores or add their critical/history bonuses. Restaurants with zero ranking points are hidden.

Date, severity, and name/address filters run on inspections before grouping. Consequently the ranking and inferred closed status reflect the filtered inspection set. The public scoring explanation currently combines these concepts more broadly than the implementation; align them when scoring behavior is next revised.

## Browser behavior and caching

The visible controls offer date presets (all time, 30, 90, 180, and 365 days), severity selection, name/address search, and severity/date/name sorting. City and outcome controls are not implemented. JSON export contains the grouped filtered restaurants; CSV emits an inspection row per restaurant inspection.

Alpine initialization is idempotent. The browser requests the manifest with `cache: 'no-store'`, then fetches a dataset URL containing `?v=<manifest hash>` with `cache: 'force-cache'`. If the manifest cannot be loaded, a timestamp supplies the version fallback. Results and accordions require Alpine/JavaScript; there is no rendered no-JavaScript results fallback.

Production optimization retains the complete JSON array at `data/violations_latest.json` and generates `data/violations_browser.v1.json`. The browser file contains `{format: "observations-v1", observations: [...], records: [...]}`: observation strings are deduplicated and sorted together so HTTP compression can reuse phrases across reports; only existing `inspection.violations[].observation` fields become integer indexes. Record order, missing fields, and all other values are preserved. The loader restores strings before the existing filtering, grouping, and export paths run. No inspection is removed or rescored.

Only the generated manifest gains `datasets.latest.browser_url`. The browser prefers that URL, keeps the same manifest hash in `?v=`, and still accepts the ordinary array for local previews, older manifests, or a failed manifest request. The public array URL and logical dataset hash remain unchanged. Build validation compares the entire decoded browser file with the public array and its manifest hash, and applies the 140,000-byte gzip budget to the browser download. Change the format identifier and filename version together if the transport contract changes; immutable caches use the logical data hash rather than an encoding hash.

The optimizer also fingerprints the stylesheet, app/theme scripts, logo, and favicon with 12-character content hashes. Generated HTML/XML references are updated, and the CSS source map is removed. Source JSON and asset filenames remain readable and stable. Cloudflare rule management and deployment verification are described in [operations](operations.md).

## Follow-up work

These items are deferred or observed implementation limitations, not completed milestones:

- Obtain NMED bulk access before statewide ingestion; adapt and validate the retained normalizer against the actual feed.
- Align stored scoring, browser ranking, and the public scoring page. Revisit aging scores, missing critical flags, and inspection-history bonuses together.
- Capture source inspection/permit identifiers to distinguish multiple inspections with the same address/date/outcome. Current composite identity preserves distinct outcomes but does not claim one row per permit. Browser restaurant grouping still uses name alone.
- Expand PDF discovery beyond the first documents page and recognize `.pdf/view` links. The main weekly report remains the reliable daily source; the October 2026 recovery used Git history plus separately checked older PDFs.
- Add a no-JavaScript results fallback and continue rendered accessibility/performance work. Lighthouse targets remain performance ≥95, accessibility ≥95, and SEO ≥90; they are not certified results.
- Restore per-report document provenance. Review CSV score output: the exporter reads `insp.score`, while grouping currently stores `individualScore`.
- Consider geocoding, maps/clustering, distance sorting, historical trends, scouting contact-sheet exports, closure alerts, and immediate refresh triggers after the core data contract is strengthened.
- Reconsider Workers only if an API proxy becomes necessary. Treat zone-wide WebMCP settings separately from hostname-scoped caching.
