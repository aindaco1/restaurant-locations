#!/usr/bin/env python3
"""Fail closed when the generated site's performance contract regresses."""

import argparse
import gzip
import json
from pathlib import Path
import re


ALPINE_URL = "https://cdn.jsdelivr.net/npm/alpinejs@3.16.3/dist/cdn.min.js"
ALPINE_INTEGRITY = (
    "sha384-GWGIn3FlbC6EIhIhKi0GSHWq/UCqPc7qpVE5J/bsAW8FMyMAyA08W86xYxy+8i5/"
)


def require(condition: bool, message: str) -> None:
    if not condition:
        raise SystemExit(message)


def read(path: Path) -> str:
    require(path.is_file(), f"Missing generated file: {path}")
    return path.read_text(encoding="utf-8")


def fingerprinted_asset(site_dir: Path, pattern: str) -> Path:
    matches = list(site_dir.glob(pattern))
    require(
        len(matches) == 1,
        f"Expected one fingerprinted asset matching {pattern}; found {len(matches)}",
    )
    require(
        re.search(r"\.[0-9a-f]{12}\.[^.]+$", matches[0].name) is not None,
        f"Asset is not content fingerprinted: {matches[0]}",
    )
    return matches[0]


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--site-dir", default="_site", type=Path)
    args = parser.parse_args()

    site_dir = args.site_dir
    index = read(site_dir / "index.html")
    stylesheet_path = fingerprinted_asset(site_dir, "assets/main.*.css")
    app_script_path = fingerprinted_asset(site_dir, "assets/js/app.*.js")
    theme_script_path = fingerprinted_asset(site_dir, "assets/js/theme.*.js")
    logo_path = fingerprinted_asset(
        site_dir, "assets/images/dust-wave-logo.*.svg"
    )
    favicon_path = fingerprinted_asset(site_dir, "favicon.*.svg")
    stylesheet = read(stylesheet_path)
    app_script = read(app_script_path)
    theme_script = read(theme_script_path)
    dataset_path = site_dir / "data" / "violations_latest.json"
    dataset_bytes = dataset_path.read_bytes()
    dataset = json.loads(dataset_bytes)

    require(ALPINE_URL in index, "Generated homepage does not pin Alpine.js")
    require(ALPINE_INTEGRITY in index, "Generated homepage lacks Alpine.js SRI")
    require(
        index.count('data-cfasync="false"') >= 4,
        "Critical scripts are not opted out of Cloudflare Rocket Loader",
    )
    require(
        'x-init="$store.violations.init()"' not in index,
        "Homepage explicitly initializes the Alpine store a second time",
    )
    require(
        'width="1152"' in index and 'height="1052"' in index,
        "Logo dimensions are missing from the generated homepage",
    )
    require('loading="lazy"' in index, "Footer logo is not lazy-loaded")
    for asset_path in (
        stylesheet_path,
        app_script_path,
        theme_script_path,
        logo_path,
        favicon_path,
    ):
        asset_url = f"/{asset_path.relative_to(site_dir).as_posix()}"
        require(asset_url in index, f"Homepage does not reference {asset_url}")
    require(
        not (site_dir / "assets" / "main.css.map").exists(),
        "Production CSS source map should not be deployed",
    )
    require(
        "/assets/main.css" not in index
        and "/assets/js/app.js" not in index
        and "/assets/js/theme.js" not in index,
        "Homepage retains unfingerprinted first-party assets",
    )
    require("@import url(" not in stylesheet, "Compiled CSS retains remote @imports")
    require("initialized: false" in app_script, "Dataset store is not idempotent")
    require("cache: 'force-cache'" in app_script, "Versioned dataset is not cacheable")
    require(
        app_script.count("cache: 'no-store'") == 1,
        "Only the unversioned manifest may bypass browser caching",
    )
    require(isinstance(dataset, list), "Generated dataset must be a JSON array")
    require(b"\n" not in dataset_bytes, "Production dataset was not compacted")

    javascript_bytes = app_script.encode() + theme_script.encode()
    javascript_gzip = len(gzip.compress(javascript_bytes, compresslevel=9))
    dataset_gzip = len(gzip.compress(dataset_bytes, compresslevel=9))

    require(javascript_gzip <= 8_000, "First-party JavaScript exceeds 8 KB gzip")
    require(len(stylesheet.encode()) <= 26_000, "Compiled CSS exceeds 26 KB")
    require(dataset_gzip <= 140_000, "Dataset exceeds 140 KB gzip")

    print(
        "Validated performance contract: "
        f"JS {javascript_gzip:,} B gzip, CSS {len(stylesheet.encode()):,} B, "
        f"dataset {dataset_gzip:,} B gzip across {len(dataset):,} records"
    )


if __name__ == "__main__":
    main()
