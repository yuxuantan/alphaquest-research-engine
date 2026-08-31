from __future__ import annotations

import argparse
from pathlib import Path
import re
import subprocess


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
    repository_root, tracked_paths = _tracked_repository_paths()
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
            elif repository_root is not None and not _target_available_in_clean_checkout(
                resolved,
                repository_root=repository_root,
                tracked_paths=tracked_paths,
            ):
                failures.append(f"{document}: local target is not tracked for a clean checkout {target}")
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


def _tracked_repository_paths() -> tuple[Path | None, frozenset[Path]]:
    root_result = subprocess.run(
        ["git", "rev-parse", "--show-toplevel"],
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
        check=False,
    )
    if root_result.returncode != 0:
        return None, frozenset()
    repository_root = Path(root_result.stdout.strip()).resolve()
    tracked_result = subprocess.run(
        ["git", "ls-files", "-z"],
        cwd=repository_root,
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
        check=False,
    )
    if tracked_result.returncode != 0:
        return None, frozenset()
    tracked_paths = frozenset(
        (repository_root / raw.decode("utf-8")).resolve()
        for raw in tracked_result.stdout.split(b"\0")
        if raw
    )
    return repository_root, tracked_paths


def _target_available_in_clean_checkout(
    target: Path,
    *,
    repository_root: Path,
    tracked_paths: frozenset[Path],
) -> bool:
    try:
        target.relative_to(repository_root)
    except ValueError:
        return True
    if target.is_file():
        return target in tracked_paths
    return any(target == tracked or target in tracked.parents for tracked in tracked_paths)


if __name__ == "__main__":
    raise SystemExit(main())
