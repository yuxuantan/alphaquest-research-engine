from __future__ import annotations

import argparse
from pathlib import Path
import re


LINK = re.compile(r"\[[^\]]+\]\(([^)]+)\)")
DEFAULT_PATHS = (
    "README.md",
    "START_HERE.md",
    "ARCHITECTURE.md",
    "CONTRIBUTING.md",
    "docs",
    "apps/README.md",
    "campaigns/README.md",
    "config/README.md",
    "data/README.md",
    "tools/README.md",
    "tests/README.md",
)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Validate local links in curated onboarding documentation.")
    parser.add_argument("paths", nargs="*", default=list(DEFAULT_PATHS))
    args = parser.parse_args(argv)
    failures = validate_links(args.paths)
    if failures:
        for failure in failures:
            print(f"FAIL: {failure}")
        return 1
    print(f"PASS: documentation links valid across {len(_markdown_files(args.paths))} files")
    return 0


def validate_links(paths: list[str] | tuple[str, ...]) -> list[str]:
    failures = []
    for document in _markdown_files(paths):
        if document.name == "full-guide.md":
            continue
        content = document.read_text(encoding="utf-8")
        for target in LINK.findall(content):
            normalized = target.strip().strip("<>")
            if not normalized or normalized.startswith(("http://", "https://", "mailto:", "#")):
                continue
            path_part = normalized.split("#", 1)[0]
            if not path_part:
                continue
            resolved = (document.parent / path_part).resolve()
            if not resolved.exists():
                failures.append(f"{document}: missing local target {target}")
    return failures


def _markdown_files(paths: list[str] | tuple[str, ...]) -> list[Path]:
    files = []
    for raw in paths:
        path = Path(raw)
        if path.is_dir():
            files.extend(path.rglob("*.md"))
        elif path.is_file():
            files.append(path)
    return sorted(set(files))


if __name__ == "__main__":
    raise SystemExit(main())
