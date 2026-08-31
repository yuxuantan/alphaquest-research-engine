"""Read-only, hash-verified chart and scanner views for governed datasets.

These helpers deliberately do not create executable campaign inputs.  They
provide research inspection parity while keeping every derived bar and
indicator outside the strategy path until it is separately certified.
"""

from __future__ import annotations

from datetime import datetime
import hashlib
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from alphaquest.research.storage import load_storage_layout, resolve_recorded_path
from alphaquest.studio.workspace import list_dataset_manifests


_OHLCV = ("timestamp", "open", "high", "low", "close", "volume")
_RESOLUTIONS = {
    "native": None,
    "5m": "5min",
    "15m": "15min",
    "30m": "30min",
    "60m": "60min",
    "1d": "1D",
}
_CHART_TYPES = {
    "candlestick",
    "ohlc",
    "line",
    "hollow_candlestick",
    "heikin_ashi",
    "cumulative_delta",
}


def research_capability_matrix() -> list[dict[str, Any]]:
    """Return the explicit MultiCharts research-parity contract."""

    return [
        _cap("Multi-resolution charts", "implemented", "Native, 5/15/30/60-minute and daily governed views."),
        _cap("Multiple data series", "implemented", "Hash-verified comparison overlay with timestamp alignment."),
        _cap("OHLC, candle, hollow candle, line", "implemented", "Read-only chart styles over canonical bars."),
        _cap("Heikin-Ashi", "implemented", "Deterministic derived inspection bars; never executable without certification."),
        _cap("Renko, Kagi, Point & Figure, Line Break", "data_required", "Exact construction requires ordered tick paths; OHLC inference is prohibited."),
        _cap("Volume and cumulative delta", "implemented", "Volume is canonical; delta appears only when retained by the dataset."),
        _cap("Volume Profile and TPO", "implemented", "Existing certified order-flow/TPO datasets and mechanics evidence remain the source of truth."),
        _cap("Drawing and measurement tools", "implemented", "Horizontal levels and two-point trend measurements are local inspection annotations."),
        _cap("Market-data playback", "implemented", "Deterministic step, jump, and timed playback over the loaded governed window."),
        _cap("Research scanner", "implemented", "On-demand latest-state scan across governed datasets."),
        _cap("Exhaustive optimization", "implemented", "All predeclared combinations are evaluated under the 8-120 combination governance cap."),
        _cap("Genetic optimization", "superseded", "Exhaustive evaluation is stronger and practical under the governed parameter cap; lossy search is not used."),
        _cap("Custom fitness functions", "implemented", "Frozen stage benchmarks and objective gates provide auditable fitness criteria."),
        _cap("Walk-forward testing", "implemented", "Purged/contiguous windows and stitched unseen OOS evidence."),
        _cap("Tick and quote-aware execution", "implemented", "Certified market, limit, stop, stop-limit, OCO, partial-fill and bid/ask replay."),
        _cap("Performance report", "implemented", "Hash-bound metrics, trades, curves, breakdowns, Monte Carlo and parameter surfaces."),
        _cap("Report/chart synchronization", "implemented", "Trade selection updates the retained execution-level chart and mechanics replay link."),
        _cap("Multi-strategy portfolio backtesting", "deferred", "Explicitly excluded until the user trades multiple strategies."),
        _cap("Live brokers, DOM and manual trading", "out_of_scope", "AlphaQuest remains a research and backtesting system."),
    ]


def governed_chart_snapshot(
    project_root: str | Path,
    dataset_id: str,
    *,
    resolution: str = "native",
    chart_type: str = "candlestick",
    limit: int = 600,
    compare_dataset_id: str | None = None,
) -> dict[str, Any]:
    root = Path(project_root).resolve()
    if resolution not in _RESOLUTIONS:
        raise ValueError(f"unsupported chart resolution: {resolution}")
    if chart_type not in _CHART_TYPES:
        raise ValueError(f"unsupported chart type: {chart_type}")
    limit = max(50, min(int(limit), 2000))
    manifest = _manifest(root, dataset_id)
    frame, observed_hash = _load_canonical_tail(root, manifest, limit=_source_limit(limit, resolution))
    frame = _resample(frame, resolution)
    if chart_type == "heikin_ashi":
        frame = _heikin_ashi(frame)
    frame = _indicators(frame).tail(limit).reset_index(drop=True)
    compare_rows: list[dict[str, Any]] = []
    compare_meta: dict[str, Any] | None = None
    if compare_dataset_id:
        other = _manifest(root, compare_dataset_id)
        if str(other.get("symbol")) != str(manifest.get("symbol")):
            raise ValueError("comparison overlays require the same symbol")
        compare, compare_hash = _load_canonical_tail(
            root,
            other,
            limit=_source_limit(limit, resolution),
        )
        compare = _resample(compare, resolution).tail(limit)
        aligned = frame[["timestamp"]].merge(
            compare[["timestamp", "close"]].rename(columns={"close": "comparison_close"}),
            on="timestamp",
            how="left",
        )
        base = pd.to_numeric(aligned["comparison_close"], errors="coerce").dropna()
        if not base.empty and float(base.iloc[0]) != 0:
            aligned["comparison_normalized"] = (
                pd.to_numeric(aligned["comparison_close"], errors="coerce")
                / float(base.iloc[0])
                * 100.0
            )
        compare_rows = _json_rows(aligned)
        compare_meta = {
            "dataset_id": compare_dataset_id,
            "canonical_sha256": compare_hash,
            "quality_verdict": other.get("quality_verdict"),
            "normalization": "first aligned close = 100",
        }
    delta_available = "delta" in frame.columns and bool(frame["delta"].notna().any())
    return {
        "dataset": {
            "dataset_id": dataset_id,
            "symbol": manifest.get("symbol"),
            "native_timeframe": manifest.get("timeframe"),
            "quality_verdict": manifest.get("quality_verdict"),
            "canonical_sha256": observed_hash,
            "exchange_timezone": manifest.get("exchange_timezone") or manifest.get("timezone"),
            "timestamp_semantics": manifest.get("timestamp_semantics"),
        },
        "view": {
            "resolution": resolution,
            "chart_type": chart_type,
            "rows": len(frame),
            "read_only": True,
            "executable": False,
            "delta_available": delta_available,
            "warning": (
                "Derived chart bars, indicators, comparisons, and drawings are inspection-only. "
                "They cannot enter a campaign without a certified dataset transformation."
            ),
        },
        "bars": _json_rows(frame),
        "comparison": {"metadata": compare_meta, "rows": compare_rows},
    }


def governed_dataset_scan(project_root: str | Path) -> dict[str, Any]:
    root = Path(project_root).resolve()
    rows: list[dict[str, Any]] = []
    for manifest in list_dataset_manifests(root):
        dataset_id = str(manifest.get("dataset_id") or "")
        try:
            frame, observed_hash = _load_canonical_tail(root, manifest, limit=60)
            values = _indicators(frame)
            latest = values.iloc[-1]
            close = _finite(latest.get("close"))
            sma20 = _finite(latest.get("sma20"))
            previous = _finite(values.iloc[-2].get("close")) if len(values) > 1 else None
            rows.append(
                {
                    "dataset_id": dataset_id,
                    "symbol": manifest.get("symbol"),
                    "timeframe": manifest.get("timeframe"),
                    "quality_verdict": manifest.get("quality_verdict"),
                    "timestamp": _iso(latest.get("timestamp")),
                    "close": close,
                    "one_bar_return": (
                        close / previous - 1.0
                        if close is not None and previous not in {None, 0}
                        else None
                    ),
                    "sma20": sma20,
                    "trend": (
                        "above_sma20"
                        if close is not None and sma20 is not None and close > sma20
                        else "below_sma20"
                        if close is not None and sma20 is not None
                        else "unavailable"
                    ),
                    "volume": _finite(latest.get("volume")),
                    "delta": _finite(latest.get("delta")),
                    "canonical_sha256": observed_hash,
                    "status": "available",
                }
            )
        except (FileNotFoundError, ValueError, OSError) as exc:
            rows.append(
                {
                    "dataset_id": dataset_id,
                    "symbol": manifest.get("symbol"),
                    "timeframe": manifest.get("timeframe"),
                    "quality_verdict": manifest.get("quality_verdict"),
                    "status": "unavailable",
                    "reason": str(exc),
                }
            )
    return {
        "generated_at": datetime.now().astimezone().isoformat(),
        "rows": rows,
        "note": "Scanner values are read-only latest-state diagnostics over hash-verified governed data.",
    }


def _cap(name: str, status: str, evidence: str) -> dict[str, str]:
    return {"capability": name, "status": status, "evidence": evidence}


def _manifest(root: Path, dataset_id: str) -> dict[str, Any]:
    value = next(
        (
            item
            for item in list_dataset_manifests(root)
            if str(item.get("dataset_id") or "") == dataset_id
        ),
        None,
    )
    if value is None:
        raise FileNotFoundError(f"governed dataset manifest not found: {dataset_id}")
    return value


def _canonical_path(root: Path, manifest: dict[str, Any]) -> Path:
    relative = str(manifest.get("path") or "").strip()
    if not relative:
        raise ValueError("dataset manifest does not declare a canonical path")
    path = resolve_recorded_path(relative, project_root=root).resolve()
    dataset_root = load_storage_layout(root).dataset_root.resolve()
    if (
        not (path.is_relative_to(dataset_root) or path.is_relative_to(root))
        or not path.is_file()
    ):
        raise FileNotFoundError(
            "canonical dataset path is missing or outside the governed project/dataset roots"
        )
    expected = str(manifest.get("canonical_sha256") or "").strip()
    observed = hashlib.sha256(path.read_bytes()).hexdigest()
    if not expected or observed != expected:
        raise ValueError("canonical dataset hash is missing or stale")
    return path


def _load_canonical_tail(
    root: Path,
    manifest: dict[str, Any],
    *,
    limit: int,
) -> tuple[pd.DataFrame, str]:
    path = _canonical_path(root, manifest)
    observed_hash = str(manifest["canonical_sha256"])
    columns = _available_columns(path)
    required = [name for name in _OHLCV if name in columns]
    missing = sorted(set(_OHLCV) - set(required))
    if missing:
        raise ValueError("canonical chart data is missing: " + ", ".join(missing))
    optional = next(
        (
            name
            for name in ("delta", "bar_delta", "volume_delta", "signed_volume")
            if name in columns
        ),
        None,
    )
    selected = required + ([optional] if optional else [])
    if path.suffix.casefold() in {".parquet", ".pq"}:
        frame = _parquet_tail(path, selected, limit)
    else:
        frame = pd.read_csv(path, usecols=selected).tail(limit)
    if optional and optional != "delta":
        frame = frame.rename(columns={optional: "delta"})
    frame["timestamp"] = pd.to_datetime(frame["timestamp"], utc=True, errors="coerce")
    for column in ("open", "high", "low", "close", "volume", "delta"):
        if column in frame.columns:
            frame[column] = pd.to_numeric(frame[column], errors="coerce")
    frame = frame.dropna(subset=["timestamp", "open", "high", "low", "close"])
    frame = frame.sort_values("timestamp", kind="mergesort").drop_duplicates("timestamp", keep="last")
    return frame.tail(limit).reset_index(drop=True), observed_hash


def _available_columns(path: Path) -> list[str]:
    if path.suffix.casefold() in {".parquet", ".pq"}:
        import pyarrow.parquet as pq

        return list(pq.ParquetFile(path).schema.names)
    return list(pd.read_csv(path, nrows=0).columns)


def _parquet_tail(path: Path, columns: list[str], limit: int) -> pd.DataFrame:
    import pyarrow.parquet as pq

    parquet = pq.ParquetFile(path)
    groups: list[int] = []
    rows = 0
    for index in range(parquet.num_row_groups - 1, -1, -1):
        groups.append(index)
        rows += parquet.metadata.row_group(index).num_rows
        if rows >= limit:
            break
    groups.reverse()
    return parquet.read_row_groups(groups, columns=columns).to_pandas().tail(limit)


def _source_limit(limit: int, resolution: str) -> int:
    factor = {"native": 1, "5m": 6, "15m": 16, "30m": 31, "60m": 61, "1d": 420}.get(
        resolution,
        1,
    )
    return min(max(limit * factor, limit), 120_000)


def _resample(frame: pd.DataFrame, resolution: str) -> pd.DataFrame:
    rule = _RESOLUTIONS[resolution]
    if rule is None or frame.empty:
        return frame.copy()
    indexed = frame.set_index("timestamp")
    aggregation: dict[str, str] = {
        "open": "first",
        "high": "max",
        "low": "min",
        "close": "last",
        "volume": "sum",
    }
    if "delta" in indexed.columns:
        aggregation["delta"] = "sum"
    return (
        indexed.resample(rule, label="left", closed="left")
        .agg(aggregation)
        .dropna(subset=["open", "high", "low", "close"])
        .reset_index()
    )


def _heikin_ashi(frame: pd.DataFrame) -> pd.DataFrame:
    if frame.empty:
        return frame.copy()
    result = frame.copy()
    close = frame[["open", "high", "low", "close"]].mean(axis=1)
    opens = np.empty(len(frame), dtype=float)
    opens[0] = (float(frame.iloc[0]["open"]) + float(frame.iloc[0]["close"])) / 2.0
    for index in range(1, len(frame)):
        opens[index] = (opens[index - 1] + float(close.iloc[index - 1])) / 2.0
    result["open"] = opens
    result["close"] = close
    result["high"] = pd.concat(
        [frame["high"].reset_index(drop=True), pd.Series(opens), close.reset_index(drop=True)],
        axis=1,
    ).max(axis=1)
    result["low"] = pd.concat(
        [frame["low"].reset_index(drop=True), pd.Series(opens), close.reset_index(drop=True)],
        axis=1,
    ).min(axis=1)
    return result


def _indicators(frame: pd.DataFrame) -> pd.DataFrame:
    result = frame.copy()
    if result.empty:
        return result
    close = pd.to_numeric(result["close"], errors="coerce")
    result["sma20"] = close.rolling(20, min_periods=1).mean()
    result["ema20"] = close.ewm(span=20, adjust=False).mean()
    volume = pd.to_numeric(result["volume"], errors="coerce").fillna(0.0)
    typical = result[["high", "low", "close"]].mean(axis=1)
    cumulative_volume = volume.cumsum()
    result["vwap"] = (typical * volume).cumsum() / cumulative_volume.replace(0, np.nan)
    if "delta" in result.columns:
        result["cumulative_delta"] = pd.to_numeric(
            result["delta"],
            errors="coerce",
        ).fillna(0.0).cumsum()
    return result


def _json_rows(frame: pd.DataFrame) -> list[dict[str, Any]]:
    clean = frame.copy()
    for column in clean.columns:
        if pd.api.types.is_datetime64_any_dtype(clean[column]):
            clean[column] = clean[column].map(_iso)
    clean = clean.replace([np.inf, -np.inf], np.nan)
    return clean.where(pd.notna(clean), None).to_dict(orient="records")


def _iso(value: Any) -> str | None:
    if value is None or pd.isna(value):
        return None
    return pd.Timestamp(value).isoformat()


def _finite(value: Any) -> float | None:
    try:
        numeric = float(value)
    except (TypeError, ValueError):
        return None
    return numeric if np.isfinite(numeric) else None


__all__ = [
    "governed_chart_snapshot",
    "governed_dataset_scan",
    "research_capability_matrix",
]
