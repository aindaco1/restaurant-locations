# Operations

For maintainers refreshing data, deploying the site, or diagnosing stale output. These instructions describe the repository workflows; verify live job/provider state separately.

## Data refreshes

[Data Pipeline](../.github/workflows/pipeline.yml) runs daily at 02:00 UTC, on manual dispatch, and on relevant pushes/pull requests to `main` (`scripts/**`, `requirements.txt`, and the pipeline workflow). It runs Python and Node tests on every trigger. Pull requests stop after tests; other runs fetch/normalize data, validate required top-level fields, commit changed `data/` files, and upload artifacts. Runs are serialized to avoid concurrent refresh pushes.

After completing [Python setup](development.md), refresh locally with:

```bash
python scripts/build_dataset.py --validate
```

This fetches remote PDFs and rewrites the local archive, raw weekly file, monthly snapshot, and manifest. Review `git diff --stat -- data` and the changed records before committing. An empty fetch should preserve the existing readable archive; inspect the logged fetched/new/total counts and report dates rather than treating exit status alone as a freshness check.

To investigate a fetch in a scratch directory without changing the checked-in archive:

```bash
python scripts/build_dataset.py --validate --output /tmp/healthcode-inspection-review
```

Use a fresh output directory for an isolated fetch; the builder merges with any archive already there. The output directory's parent must exist. See [data lifecycle](architecture.md#data-lifecycle) for merge and snapshot semantics.

`ABQ_PDF_BASE_URL` is an optional repository secret used as the base for relative discovered PDF links. It does not override the hardcoded documents page or primary report URL in [scrape_abq.py](../scripts/scrape_abq.py); inspect those values if ABQ moves its reports.

## GitHub Pages

Configure repository Settings → Pages to use GitHub Actions. The custom hostname is specified by [CNAME](../CNAME) and [_config.yml](../_config.yml).

[Deploy Jekyll to GitHub Pages](../.github/workflows/pages.yml) handles:

- Pushes to `main`, pull requests targeting `main`, manual dispatch, and completed Data Pipeline runs.
- A production Jekyll build, generated-output optimization, and the performance gate. Pull requests validate without deploying.
- Successful pipeline completion: `workflow_run` checks out the latest `main`, including the pipeline's data commit. Data commits made by `GITHUB_TOKEN` do not trigger another push workflow. Pushes affecting pipeline paths defer deployment to this completion event.
- Non-PR artifact deployment, optional Cloudflare reconciliation, and verification through the production hostname. An unsuccessful data pipeline is refused by the Pages preflight.

Use the [development build sequence](development.md#validation) to reproduce the artifact checks locally. A local build pass does not establish successful CI or production delivery.

## Cloudflare rules

[sync_cloudflare_config.mjs](../scripts/sync_cloudflare_config.mjs) manages three rules scoped to `healthcode.dustwave.xyz`: disable Rocket Loader/RUM injection, cache fingerprinted assets and versioned datasets for one year, and add immutable cache headers to successful matching responses. The unversioned manifest is excluded.

Set `CLOUDFLARE_API_TOKEN` and `CLOUDFLARE_ZONE_ID` in the environment using a zone-scoped token with access to the managed Configuration/Cache Rules phases. Do not commit credentials or store them in `.dev.vars` for this site.

Read-only drift check:

```bash
node scripts/sync_cloudflare_config.mjs --check
```

Apply the repository's hostname-scoped rules:

```bash
node scripts/sync_cloudflare_config.mjs
```

For automatic post-deploy reconciliation, set the same two repository secrets and the repository variable `CLOUDFLARE_CONFIG_SYNC=true`. Reconciliation is optional; live rule state must be checked rather than inferred from source. The script preserves unrelated rules. Zone-wide WebMCP beta settings are outside this automation.

## Production verification

The Pages workflow records the deployed checkout SHA and dataset hash, then runs [verify_production.py](../scripts/verify_production.py). It checks for the pinned Alpine runtime and fingerprinted app in the served homepage, rejects Rocket Loader/RUM injection, and compares both the manifest and recomputed dataset hash with the expected version.

To verify a deployment against this checkout, after confirming this is the intended deployed revision:

```bash
expected_hash="$(python3 -c 'import json; print(json.load(open("data/manifest.json"))["datasets"]["latest"]["hash"])')"
deployment_id="$(git rev-parse HEAD)"
python3 scripts/verify_production.py \
  --base-url https://healthcode.dustwave.xyz/ \
  --expected-hash "$expected_hash" \
  --deployment-id "$deployment_id"
```

The deployment ID supplies a cache-busting query; the verifier does not prove every served asset matches that Git commit. It retries up to six times, five seconds apart, by default. Successful verification establishes the checked shell and dataset version, not complete browser interaction or data-source freshness.

## Troubleshooting

| Symptom | Inspect and recover |
| --- | --- |
| Jekyll dependency/build failure | Check the Ruby version and `bundle check`; use the committed lockfile and Sass constraints. Rebuild into a fresh destination such as `bundle exec jekyll build --destination /tmp/healthcode-site-review`. Pass that directory through `--site-dir` to both optimizer and validator. |
| No results or fetch error | Inspect browser requests for the manifest/dataset, verify `_config.yml` baseurl, and distinguish loading failure from filters or zero restaurant ranking. |
| Pipeline succeeds without new inspections | Inspect scraper logs, available PDFs, and inspection dates. Review parsed counts and skipped records. `--validate` checks top-level fields, not completeness or freshness. |
| Archive cannot be read | Preserve the current file and inspect Git history before rerunning. The builder can continue without unreadable prior data, so do not use a rerun as archive recovery. |
| Production hash mismatch | Confirm the intended revision and Pages job completed, then compare the deployed manifest and dataset using the verifier. Check Cloudflare drift if the shell is altered or caching is inconsistent. |
| Performance budget failure | Check generated output and recent asset/data growth. Optimize the generated artifact; do not compact readable source JSON to satisfy the build gate. |
