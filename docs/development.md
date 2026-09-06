# Development

For contributors setting up or validating changes. Run commands from the repository root. The [operations guide](operations.md) covers data refreshes and deployment.

## Environment and local preview

CI uses Ruby 3.1, Python 3.11, and Node.js 24. Use compatible local runtimes and the committed `Gemfile.lock`; the Sass dependencies in [Gemfile](../Gemfile) are constrained for CI compatibility.

```bash
bundle install
bundle exec jekyll serve
```

Open [localhost:4000](http://localhost:4000). Use the checked-in data for UI development; a fresh scrape is unnecessary for ordinary page or documentation changes.

For Python tooling, use an ignored virtual environment:

```bash
python3 -m venv venv
source venv/bin/activate
python -m pip install -r requirements.txt
```

## Validation

For changes to Python data processing, normalization, validation, or deployment helpers:

```bash
python -m pytest -q scripts/tests
```

For Cloudflare rule logic:

```bash
node --test scripts/tests/cloudflare_config.test.mjs
```

For site/build changes, run the production sequence used by Pages:

```bash
JEKYLL_ENV=production bundle exec jekyll build
python3 scripts/optimize_site.py
python3 scripts/validate_site.py
```

Start with a fresh Jekyll build each time: the optimizer renames generated assets and is not a standalone repeatable build command. The performance gate checks combined first-party JavaScript ≤8,000 bytes gzip, compiled CSS ≤26,000 bytes, and the latest dataset ≤140,000 bytes gzip, along with pinned Alpine/integrity, asset fingerprints, cache behavior, and other shell checks. These are build assertions, not a Lighthouse or full accessibility audit.

For UI changes, inspect the rendered desktop and mobile layouts, keyboard access, light/dark themes, filters, accordions, and affected exports. For documentation changes, check relative links and confirm contributor docs do not appear in `_site/`.

## Conventions

- Extend existing Alpine stores, filter controls, and Jekyll includes. Avoid heavy frameworks, parallel state paths, and client-side build tooling.
- Keep SCSS modular under `assets/partials/`, with the existing 8px unit system, semantic variables, BEM-style class names, and composable mixins. Use the repository's tokens and breakpoints as the source of truth.
- Keep controls semantic, labeled, keyboard accessible, visibly focused, and legible in both themes. Progressive enhancement is a remaining goal; do not describe the current results list as working without JavaScript.
- Use Python type hints where useful, follow the existing style, and add meaningful parser/scoring tests when behavior changes. Preserve a readable archive during fetch failures.
- Keep source JSON readable. Optimize only generated output, preserve pinned dependency/Actions references, and maintain the caching contract described in [architecture](architecture.md).
- Update the guide that owns the changed behavior; see the [documentation index](README.md). Keep public page files and build inputs in their functional locations.
