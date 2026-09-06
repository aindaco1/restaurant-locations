# Project documentation

For contributors and maintainers. Start with the root [README](../README.md) for the product overview and quick start.

| Document | Owns |
| --- | --- |
| [Architecture and data](architecture.md) | Current implementation, data model, scoring, limitations, and deferred work |
| [Development](development.md) | Local setup, validation commands, and coding conventions |
| [Operations](operations.md) | Scheduled/manual ingestion, Pages deployment, Cloudflare configuration, and recovery |
| [Agent instructions](../AGENTS.md) | Short repository-wide instructions for coding agents |

Each topic has one authoritative guide. Link to it instead of repeating architecture, setup steps, or status checklists in several files. The implementation and workflow files remain the authority for executable behavior; update the corresponding guide when they change. Use the [manifest](../data/manifest.json) for dataset metadata instead of copying changing totals into prose.

`README.md`, `LICENSE`, and `AGENTS.md` stay at the root for discovery. Jekyll pages (`index.html`, `scoring.html`), crawler files, configuration, and dependency manifests are site/build inputs and stay in their functional locations. Contributor guides live here and are excluded from the published site through [_config.yml](../_config.yml).

The earlier planning sketches and duplicated milestone checklists have been consolidated into these guides. Git history retains the original plans.
