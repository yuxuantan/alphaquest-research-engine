from __future__ import annotations

import hashlib
from pathlib import Path
from types import SimpleNamespace

import pandas as pd
import pytest

from alphaquest.studio import analysis


def _dataset(tmp_path: Path) -> tuple[dict, Path]:
    dataset_root = tmp_path / "research" / "datasets"
    path = dataset_root / "es_demo" / "bars.parquet"
    path.parent.mkdir(parents=True)
    timestamp = pd.date_range("2026-01-02 14:30:00+00:00", periods=120, freq="min")
    frame = pd.DataFrame(
        {
            "timestamp": timestamp,
            "open": 100.0 + pd.Series(range(120)) * 0.25,
            "high": 100.5 + pd.Series(range(120)) * 0.25,
            "low": 99.75 + pd.Series(range(120)) * 0.25,
            "close": 100.25 + pd.Series(range(120)) * 0.25,
            "volume": 10 + pd.Series(range(120)),
            "delta": -5 + pd.Series(range(120)),
        }
    )
    frame.to_parquet(path, index=False)
    manifest = {
        "dataset_id": "es_demo",
        "symbol": "ES",
        "timeframe": "1m",
        "quality_verdict": "PASS",
        "path": str(path.relative_to(tmp_path)),
        "canonical_sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
        "exchange_timezone": "America/New_York",
        "timestamp_semantics": "bar_open",
    }
    return manifest, dataset_root


def _patch_catalog(monkeypatch: pytest.MonkeyPatch, manifest: dict, dataset_root: Path) -> None:
    monkeypatch.setattr(analysis, "list_dataset_manifests", lambda _root: [manifest])
    monkeypatch.setattr(
        analysis,
        "load_storage_layout",
        lambda _root: SimpleNamespace(dataset_root=dataset_root),
    )


def test_governed_chart_snapshot_resamples_and_retains_provenance(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    manifest, dataset_root = _dataset(tmp_path)
    _patch_catalog(monkeypatch, manifest, dataset_root)

    result = analysis.governed_chart_snapshot(
        tmp_path,
        "es_demo",
        resolution="15m",
        chart_type="heikin_ashi",
        limit=50,
    )

    assert result["dataset"]["canonical_sha256"] == manifest["canonical_sha256"]
    assert result["view"]["read_only"] is True
    assert result["view"]["executable"] is False
    assert result["view"]["delta_available"] is True
    assert result["bars"]
    assert {"sma20", "ema20", "vwap", "cumulative_delta"} <= set(result["bars"][0])
    assert result["bars"][0]["open"] != 100.0


def test_governed_chart_snapshot_fails_closed_on_hash_drift(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    manifest, dataset_root = _dataset(tmp_path)
    manifest["canonical_sha256"] = "0" * 64
    _patch_catalog(monkeypatch, manifest, dataset_root)

    with pytest.raises(ValueError, match="hash is missing or stale"):
        analysis.governed_chart_snapshot(tmp_path, "es_demo")


def test_scanner_reports_latest_hash_verified_state(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    manifest, dataset_root = _dataset(tmp_path)
    _patch_catalog(monkeypatch, manifest, dataset_root)

    result = analysis.governed_dataset_scan(tmp_path)

    assert result["rows"][0]["status"] == "available"
    assert result["rows"][0]["trend"] == "above_sma20"
    assert result["rows"][0]["canonical_sha256"] == manifest["canonical_sha256"]


def test_parity_contract_keeps_live_and_portfolio_work_out_of_scope() -> None:
    statuses = {
        row["capability"]: row["status"]
        for row in analysis.research_capability_matrix()
    }

    assert statuses["Multi-strategy portfolio backtesting"] == "deferred"
    assert statuses["Live brokers, DOM and manual trading"] == "out_of_scope"
    assert statuses["Genetic optimization"] == "superseded"
