import pytest
import hashlib
import json

from verify_production import ALPINE_URL, verify_homepage
import verify_production
from dataset_transport import pack_dataset, BROWSER_DATASET_URL


@pytest.mark.parametrize("corrupt", [False, True])
def test_verifier_checks_browser_download_against_public_archive(monkeypatch, corrupt):
    records = [{"inspection": {"violations": [{"observation": "Original text"}]}}]
    expected_hash = hashlib.sha256(json.dumps(records, sort_keys=True).encode()).hexdigest()[:8]
    payload = pack_dataset(records)
    if corrupt:
        payload["observations"][0] = "Changed text"
    requests = []

    def fetch(url):
        requests.append(url)
        if "manifest.json" in url:
            return json.dumps({"datasets": {"latest": {
                "hash": expected_hash, "browser_url": BROWSER_DATASET_URL
            }}}).encode()
        if "violations_latest.json" in url:
            return json.dumps(records).encode()
        if "violations_browser.v1.json" in url:
            return json.dumps(payload).encode()
        return (f'<script src="{ALPINE_URL}"></script>'
                '<script src="/assets/js/app.0123456789ab.js"></script>').encode()

    monkeypatch.setattr(verify_production, "fetch", fetch)
    if corrupt:
        with pytest.raises(RuntimeError, match="does not match the full archive"):
            verify_production.verify("https://example.com/", expected_hash, "sha")
    else:
        verify_production.verify("https://example.com/", expected_hash, "sha")
    assert requests[-1] == f"https://example.com{BROWSER_DATASET_URL}?v={expected_hash}&deploy=sha"


def test_accepts_fingerprinted_production_shell() -> None:
    verify_homepage(
        f'<script src="{ALPINE_URL}"></script>'
        '<script src="/assets/js/app.0123456789ab.js"></script>'
    )


@pytest.mark.parametrize(
    "runtime",
    (
        "cloudflare-static/rocket-loader.min.js",
        "static.cloudflareinsights.com/beacon.min.js",
    ),
)
def test_rejects_provider_runtime_injection(runtime: str) -> None:
    with pytest.raises(RuntimeError, match="injected disallowed runtime"):
        verify_homepage(
            f'<script src="{ALPINE_URL}"></script>'
            '<script src="/assets/js/app.0123456789ab.js"></script>'
            f'<script src="https://example.com/{runtime}"></script>'
        )
