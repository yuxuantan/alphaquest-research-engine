from __future__ import annotations

import ast
from collections import Counter
import csv
from pathlib import Path
from typing import Iterable


def generate_code_views(
    *,
    project_root: str | Path = ".",
    output_root: str | Path = "views/code",
) -> dict[str, int]:
    root = Path(project_root).resolve()
    output = _resolve(root, output_root)
    output.mkdir(parents=True, exist_ok=True)
    tools = [_record(root, path, _tool_category(path.name)) for path in sorted((root / "tools").glob("*.py"))]
    tests = [_record(root, path, _test_category(path.name)) for path in sorted((root / "tests").glob("test_*.py"))]
    _write_collection(output / "tools", "Tool Index", tools)
    _write_collection(output / "tests", "Test Index", tests)
    (output / "README.md").write_text(
        "# Code Navigation\n\n"
        f"- [Tools](tools/): {len(tools)}\n"
        f"- [Tests](tests/): {len(tests)}\n\n"
        "These are generated indexes. Existing paths remain stable for historical references.\n",
        encoding="utf-8",
    )
    return {"tools": len(tools), "tests": len(tests)}


def _record(root: Path, path: Path, category: str) -> dict[str, str]:
    return {
        "category": category,
        "name": path.stem,
        "path": str(path.relative_to(root)),
        "description": _description(path),
    }


def _description(path: Path) -> str:
    try:
        module = ast.parse(path.read_text(encoding="utf-8"))
        docstring = ast.get_docstring(module)
    except (OSError, SyntaxError, UnicodeDecodeError):
        docstring = None
    if docstring:
        return " ".join(docstring.split())[:240]
    return path.stem.replace("_", " ")


def _tool_category(name: str) -> str:
    if name.startswith("audit_"):
        return "audit"
    if name.startswith("build_") or name.startswith("convert_"):
        return "data_build"
    if name.startswith(("run_", "rerun_", "stop_widen_", "tp_widen_")):
        return "campaign_execution"
    if name.startswith("cleanup_"):
        return "maintenance"
    if name.startswith(("compare_", "summarize_", "curate_", "qualify_")):
        return "analysis"
    if "registry" in name or "catalog" in name or "status" in name or "store" in name:
        return "repository_navigation"
    return "other"


def _test_category(name: str) -> str:
    value = name.lower()
    if any(token in value for token in ("backtest", "engine", "position_sizing", "equity", "metrics", "contracts")):
        return "backtest"
    if any(token in value for token in ("data", "databento", "sierra", "cache", "source", "features")):
        return "data"
    if any(token in value for token in ("campaign", "preflight", "research", "wfa", "monkey", "monte_carlo", "registry", "run_store")):
        return "research"
    if any(token in value for token in ("validation", "dashboard", "exit_path")):
        return "validation"
    if any(token in value for token in ("prop", "apex", "flatten")):
        return "prop_rules"
    return "strategy_modules"


def _write_collection(path: Path, title: str, rows: list[dict[str, str]]) -> None:
    path.mkdir(parents=True, exist_ok=True)
    columns = ("category", "name", "path", "description")
    with (path / "index.csv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=columns)
        writer.writeheader()
        writer.writerows(rows)
    counts = Counter(row["category"] for row in rows)
    lines = [f"# {title}", "", "| Category | Files |", "| --- | ---: |"]
    lines.extend(f"| {category.replace('_', ' ')} | {count} |" for category, count in sorted(counts.items()))
    lines.extend(["", "See [index.csv](index.csv) for paths and descriptions.", ""])
    (path / "README.md").write_text("\n".join(lines), encoding="utf-8")


def _resolve(root: Path, path: str | Path) -> Path:
    value = Path(path)
    return value if value.is_absolute() else root / value
