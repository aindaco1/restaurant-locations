#!/usr/bin/env python3
"""Verify that Pages and Cloudflare serve the deployed dataset and shell."""

import argparse
import hashlib
import json
import re
import time
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode, urljoin
from urllib.request import Request, urlopen


ALPINE_URL = "https://cdn.jsdelivr.net/npm/alpinejs@3.16.3/dist/cdn.min.js"
FINGERPRINTED_APP_PATTERN = re.compile(
    r'/assets/js/app\.[0-9a-f]{12}\.js'
)
DISALLOWED_CLOUDFLARE_RUNTIME = (
    "cloudflare-static/rocket-loader.min.js",
    "static.cloudflareinsights.com/beacon.min.js",
)


def fetch(url: str) -> bytes:
    request = Request(
        url,
        headers={
            "Cache-Control": "no-cache",
            "User-Agent": "restaurant-locations-deploy-verifier/1.0",
        },
    )
    with urlopen(request, timeout=20) as response:
        if response.status != 200:
            raise RuntimeError(f"{url} returned HTTP {response.status}")
        return response.read()


def verify_homepage(homepage: str) -> None:
    """Confirm that the optimized shell reached the Cloudflare hostname."""
    if ALPINE_URL not in homepage or not FINGERPRINTED_APP_PATTERN.search(homepage):
        raise RuntimeError("Production homepage does not contain the deployed shell")
    for runtime in DISALLOWED_CLOUDFLARE_RUNTIME:
        if runtime in homepage:
            raise RuntimeError(f"Cloudflare injected disallowed runtime: {runtime}")


def verify(base_url: str, expected_hash: str, deployment_id: str) -> None:
    cache_buster = urlencode({"deploy": deployment_id})
    homepage = fetch(f"{base_url}?{cache_buster}").decode("utf-8")
    verify_homepage(homepage)

    manifest_url = urljoin(base_url, f"data/manifest.json?{cache_buster}")
    manifest = json.loads(fetch(manifest_url))
    deployed_hash = manifest.get("datasets", {}).get("latest", {}).get("hash")
    if deployed_hash != expected_hash:
        raise RuntimeError(
            f"Production manifest hash {deployed_hash!r} != {expected_hash!r}"
        )

    dataset_url = urljoin(
        base_url,
        f"data/violations_latest.json?v={expected_hash}&deploy={deployment_id}",
    )
    dataset = json.loads(fetch(dataset_url))
    calculated_hash = hashlib.sha256(
        json.dumps(dataset, sort_keys=True).encode()
    ).hexdigest()[:8]
    if calculated_hash != expected_hash:
        raise RuntimeError(
            f"Production dataset hash {calculated_hash!r} != {expected_hash!r}"
        )

    print(
        f"Verified production shell and {len(dataset):,} records "
        f"at dataset {expected_hash}"
    )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-url", required=True)
    parser.add_argument("--expected-hash", required=True)
    parser.add_argument("--deployment-id", required=True)
    parser.add_argument("--attempts", type=int, default=6)
    parser.add_argument("--retry-delay", type=float, default=5)
    args = parser.parse_args()

    last_error = None
    for attempt in range(1, args.attempts + 1):
        try:
            verify(args.base_url.rstrip("/") + "/", args.expected_hash, args.deployment_id)
            return
        except (
            HTTPError,
            URLError,
            RuntimeError,
            TimeoutError,
            json.JSONDecodeError,
        ) as error:
            last_error = error
            if attempt == args.attempts:
                break
            print(f"Verification attempt {attempt} failed: {error}; retrying")
            time.sleep(args.retry_delay)

    raise SystemExit(f"Production verification failed: {last_error}")


if __name__ == "__main__":
    main()
