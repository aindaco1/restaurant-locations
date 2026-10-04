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

The Pages workflow records the deployed checkout SHA and dataset hash, then runs [verify_production.py](../scripts/verify_production.py). It checks for the pinned Alpine runtime and fingerprinted app in the served homepage, rejects Rocket Loader/RUM injection, and compares both the manifest and recomputed dataset hash with the expected version. It also fetches the generated browser dataset selected by the manifest and compares its decoded contents with the full public archive. Both dataset URLs are covered by the hostname-scoped versioned-cache rules; the manifest remains excluded.

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

## Actions failure audit — October 4, 2026

The audit enumerated all 458 retained runs: 446 succeeded and 12 failed, all in the Pages workflow. Historical failed runs remain historical records; use a new run of the corrected revision to verify recovery. Do not redeploy an obsolete commit just to change its conclusion.

| Failed runs | Evidence and resolution |
| --- | --- |
| October 1–4: [36836194243](https://github.com/aindaco1/restaurant-locations/actions/runs/36836194243), [36981691593](https://github.com/aindaco1/restaurant-locations/actions/runs/36981691593), [37107238366](https://github.com/aindaco1/restaurant-locations/actions/runs/37107238366), [37187063455](https://github.com/aindaco1/restaurant-locations/actions/runs/37187063455) | All failed `Validate performance contract`: the full 799-record archive was 141,073 bytes gzip. The lossless browser transport reduces it to 122,795 bytes in the local build while preserving the 140,000-byte gate, source archive, public array, and hash. |
| July 4: [28708510729](https://github.com/aindaco1/restaurant-locations/actions/runs/28708510729), [28708673154](https://github.com/aindaco1/restaurant-locations/actions/runs/28708673154) | Pages accepted an artifact, then returned “Deployment failed, try again later.” Each direct push overlapped a successful pipeline-completion deployment. Commit `6c711de` subsequently made push preflight defer pipeline-related deployments to `workflow_run`; that guard remains in place. The overlap is observed, but the provider logs do not identify its internal failure cause. |
| July 6: [28772769987](https://github.com/aindaco1/restaurant-locations/actions/runs/28772769987) | Same provider deployment error after a successful build; the [July 7 deployment](https://github.com/aindaco1/restaurant-locations/actions/runs/28845504108) succeeded. No continuing repository defect is established by this log. For recurrence, retry the current deployment after checking Pages status; keep the production verifier enabled. |
| May 26: [26433497379](https://github.com/aindaco1/restaurant-locations/actions/runs/26433497379) | Retained annotation shows Bundler exit 5 during Ruby setup; full logs expired (HTTP 410). The next commit, `90fdd91`, pinned compatible Sass dependencies and committed the lockfile, followed by a [successful build/deploy](https://github.com/aindaco1/restaurant-locations/actions/runs/26433675828). Those constraints remain. |
| November 11, 2025: [19255894692](https://github.com/aindaco1/restaurant-locations/actions/runs/19255894692) | Retained annotations report Pages configuration HTTP 404. Pages is now configured with `build_type: workflow`, and later deployments succeeded. Full logs expired. |
| November 11, 2025: [19259088095](https://github.com/aindaco1/restaurant-locations/actions/runs/19259088095), [19259150900](https://github.com/aindaco1/restaurant-locations/actions/runs/19259150900), [19262950762](https://github.com/aindaco1/restaurant-locations/actions/runs/19262950762) | Full logs expired; annotations retain only exit 1. Adjacent commits replaced CSS variables used in Sass functions, fixed an undefined theme variable (`1d68112`), and added the missing status-key partial (`b0f5c81`). Subsequent builds succeeded. These are history-supported explanations rather than recovered log diagnoses; the current production build exercises the corrected SCSS. |
