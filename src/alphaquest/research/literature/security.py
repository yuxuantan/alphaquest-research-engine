"""Structural trust boundaries for offline P3 inputs.

Captured source bytes are data.  They are never interpreted as instructions,
paths, tool calls, or configuration by this module.
"""

from __future__ import annotations

from pathlib import Path, PurePosixPath
from typing import Any, Mapping

from alphaquest.research.literature.contracts import (
    LiteratureAuthorityError,
    LiteratureConflictError,
    SourceCaptureRevisionV1,
)


_PNL_FIELD_NAMES = frozenset(
    {
        "pnl",
        "net_profit",
        "profit_factor",
        "expectancy",
        "sharpe",
        "sortino",
        "max_drawdown",
        "trade_log",
        "equity_curve",
        "backtest_result",
        "result_bundle",
        "campaign_result",
    }
)
_PNL_PATH_PREFIXES = (
    "research/evidence/",
    "research/results/",
    "research_artifacts/",
    "run-store/",
    "backtest-campaigns/",
)


def assert_no_pnl_control_fields(value: Any, *, location: str = "$") -> None:
    """Reject PnL/result objects from the P3 control plane by key shape."""

    if isinstance(value, Mapping):
        for key, child in value.items():
            normalized = str(key).strip().lower().replace("-", "_")
            if normalized in _PNL_FIELD_NAMES:
                raise LiteratureAuthorityError(f"PnL-bearing field is outside P3 authority: {location}.{key}")
            assert_no_pnl_control_fields(child, location=f"{location}.{key}")
    elif isinstance(value, (list, tuple)):
        for index, child in enumerate(value):
            assert_no_pnl_control_fields(child, location=f"{location}[{index}]")


def assert_no_pnl_repository_reference(locator: str) -> None:
    """Reject repository-local PnL/result roots while permitting public URLs."""

    normalized = locator.strip().replace("\\", "/")
    if "://" in normalized:
        return
    path = PurePosixPath(normalized.lstrip("./"))
    candidate = path.as_posix().lower()
    if any(candidate == prefix.rstrip("/") or candidate.startswith(prefix) for prefix in _PNL_PATH_PREFIXES):
        raise LiteratureAuthorityError(f"PnL-bearing repository path is outside P3 authority: {locator}")


def codex_workspace_inputs(
    capture: SourceCaptureRevisionV1,
    *,
    destination: str | Path,
) -> tuple[Path, ...]:
    """Stage-1 interface stub; permission is checked before any workspace exists.

    Live/autonomous model execution is deliberately not implemented in Stage 1.
    """

    if capture.external_model_processing_permission != "ALLOWED_EXTERNAL_PROCESSOR":
        raise LiteratureAuthorityError(
            "capture processing permission forbids external-model workspace construction"
        )
    path = Path(destination)
    if path.exists():
        raise LiteratureConflictError("Stage-1 Codex workspace stub will not touch an existing path")
    raise NotImplementedError("autonomous Codex workspace construction is outside P3 Stage 1")


__all__ = [
    "assert_no_pnl_control_fields",
    "assert_no_pnl_repository_reference",
    "codex_workspace_inputs",
]
