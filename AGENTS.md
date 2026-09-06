# Agent instructions — NM Health Code Violations Finder

## Read first

Read [README.md](README.md) and the [documentation index](docs/README.md), then the guide relevant to the task. [Architecture and data](docs/architecture.md) describes current behavior and deferred work; do not treat the original ten-city goal as implemented coverage.

## Working rules

- Keep the site static and lightweight: Jekyll, Liquid, SCSS, vanilla JavaScript, and Alpine.js. Extend the existing stores and components; avoid heavy frameworks and client-side build steps.
- Follow the existing 8px spacing system, semantic SCSS variables, BEM-style classes, and shared mixins in `assets/partials/`.
- Preserve semantic HTML, labeled keyboard-accessible controls, visible focus states, and readable contrast. Progressive enhancement remains a goal; the current results list requires JavaScript.
- Preserve accumulated inspection data when a fetch returns no records. Keep source JSON readable and confine production compaction and asset fingerprinting to the generated site.
- Keep Alpine initialization idempotent, the manifest uncached, and dataset requests versioned by the manifest hash. Maintain pinned Alpine URL/integrity and Actions revisions.
- Use the existing normalizer and frontend grouping paths when changing scoring. They currently calculate different scores; consult the architecture guide before changing either.
- Keep source attribution and the current-status disclaimer. Limit collected information to business listings and inspection records.
- Keep credentials out of source control. Cloudflare automation is scoped to this hostname; zone-wide settings are separate work.
- Preserve unrelated worktree edits. Report local checks separately from CI, deployed-state verification, and browser acceptance.

## Validation and documentation

Use the commands in [development](docs/development.md) and run checks appropriate to the change. Data/parser/scoring changes need meaningful unit coverage; visual changes need a rendered desktop/mobile check. Follow [operations](docs/operations.md) for refreshes and deployment verification.

Update the authoritative guide when behavior changes. Keep this file focused on agent instructions, README focused on onboarding, and longer guides in `docs/`. Keep `docs/` and this file excluded from Jekyll output. Public pages such as `scoring.html`, site configuration, and dependency manifests retain their functional locations.
