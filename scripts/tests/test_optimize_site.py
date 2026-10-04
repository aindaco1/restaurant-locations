from pathlib import Path
import json

import optimize_site
from dataset_transport import BROWSER_DATASET_URL, unpack_dataset


def test_browser_artifact_preserves_public_array_and_manifest_version(tmp_path):
    site_dir = tmp_path / "_site"
    (site_dir / "data").mkdir(parents=True)
    records = [{"inspection": {"violations": [{"observation": "test"}]}}]
    source = json.dumps(records, indent=2)
    dataset_path = site_dir / "data/violations_latest.json"
    dataset_path.write_text(source)
    manifest = {"datasets": {"latest": {
        "url": "/data/violations_latest.json", "hash": "12345678", "records": 1
    }}}
    manifest_path = site_dir / "data/manifest.json"
    manifest_path.write_text(json.dumps(manifest))

    browser_path = optimize_site.prepare_browser_dataset(site_dir)

    assert dataset_path.read_text() == source
    assert unpack_dataset(json.loads(browser_path.read_text())) == records
    manifest["datasets"]["latest"]["browser_url"] = BROWSER_DATASET_URL
    assert json.loads(manifest_path.read_text()) == manifest


def test_fingerprints_assets_and_rewrites_generated_pages(tmp_path: Path) -> None:
    site_dir = tmp_path / "_site"
    assets = {
        "assets/main.css": "body{color:#111}/*# sourceMappingURL=main.css.map */",
        "assets/main.css.map": "{}",
        "assets/js/app.js": "console.log('app')",
        "assets/js/theme.js": "console.log('theme')",
        "assets/images/dust-wave-logo.svg": "<svg></svg>",
        "favicon.svg": "<svg></svg>",
    }
    for relative_path, contents in assets.items():
        path = site_dir / relative_path
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(contents, encoding="utf-8")

    index = site_dir / "index.html"
    index.write_text(
        '<link href="/assets/main.css">'
        '<script src="/assets/js/app.js"></script>'
        '<script src="/assets/js/theme.js"></script>'
        '<img src="/assets/images/dust-wave-logo.svg">'
        '<link href="/favicon.svg">',
        encoding="utf-8",
    )

    optimize_site.prepare_stylesheet(site_dir)
    replacements = optimize_site.fingerprint_assets(site_dir)
    rewritten = index.read_text(encoding="utf-8")

    assert len(replacements) == 5
    assert "sourceMappingURL" not in next(site_dir.glob("assets/main.*.css")).read_text()
    assert not (site_dir / "assets/main.css.map").exists()
    for original, fingerprinted in replacements.items():
        assert original not in rewritten
        assert fingerprinted in rewritten
        assert (site_dir / fingerprinted.removeprefix("/")).is_file()
