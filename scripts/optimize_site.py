#!/usr/bin/env python3
"""Optimize generated site assets without rewriting readable source data."""

import argparse
import hashlib
import json
from pathlib import Path


FINGERPRINT_TARGETS = (
    Path("assets/main.css"),
    Path("assets/js/app.js"),
    Path("assets/js/theme.js"),
    Path("assets/images/dust-wave-logo.svg"),
    Path("favicon.svg"),
)
REFERENCE_FILE_SUFFIXES = {".html", ".xml"}


def compact_json(path: Path) -> tuple[int, int]:
    """Rewrite JSON atomically using compact separators."""
    before = path.stat().st_size
    payload = json.loads(path.read_text(encoding="utf-8"))
    compact = json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
    temporary_path = path.with_suffix(f"{path.suffix}.tmp")
    temporary_path.write_text(compact, encoding="utf-8")
    temporary_path.replace(path)
    return before, path.stat().st_size


def prepare_stylesheet(site_dir: Path) -> None:
    """Remove the production source-map trailer and its unused map."""
    stylesheet_path = site_dir / "assets" / "main.css"
    stylesheet = stylesheet_path.read_text(encoding="utf-8")
    stylesheet = stylesheet.replace("/*# sourceMappingURL=main.css.map */", "")
    stylesheet_path.write_text(stylesheet, encoding="utf-8")
    (site_dir / "assets" / "main.css.map").unlink(missing_ok=True)


def fingerprint_assets(site_dir: Path) -> dict[str, str]:
    """Rename first-party assets with a digest and update generated pages."""
    replacements: dict[str, str] = {}

    for relative_path in FINGERPRINT_TARGETS:
        source_path = site_dir / relative_path
        if not source_path.is_file():
            raise SystemExit(f"Generated asset not found: {source_path}")

        digest = hashlib.sha256(source_path.read_bytes()).hexdigest()[:12]
        target_path = source_path.with_name(
            f"{source_path.stem}.{digest}{source_path.suffix}"
        )
        source_path.replace(target_path)
        replacements[f"/{relative_path.as_posix()}"] = (
            f"/{target_path.relative_to(site_dir).as_posix()}"
        )

    for generated_path in site_dir.rglob("*"):
        if (
            not generated_path.is_file()
            or generated_path.suffix not in REFERENCE_FILE_SUFFIXES
        ):
            continue

        generated = generated_path.read_text(encoding="utf-8")
        rewritten = generated
        for original, fingerprinted in replacements.items():
            rewritten = rewritten.replace(original, fingerprinted)
        if rewritten != generated:
            generated_path.write_text(rewritten, encoding="utf-8")

    return replacements


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--site-dir", default="_site", type=Path)
    args = parser.parse_args()

    dataset_path = args.site_dir / "data" / "violations_latest.json"
    if not dataset_path.is_file():
        raise SystemExit(f"Generated dataset not found: {dataset_path}")

    before, after = compact_json(dataset_path)
    reduction = before - after
    prepare_stylesheet(args.site_dir)
    replacements = fingerprint_assets(args.site_dir)
    print(
        f"Compacted {dataset_path}: {before:,} -> {after:,} bytes "
        f"({reduction:,} bytes removed)"
    )
    print("Fingerprint assets: " + ", ".join(replacements.values()))


if __name__ == "__main__":
    main()
