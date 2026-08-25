import pytest

from verify_production import ALPINE_URL, verify_homepage


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
