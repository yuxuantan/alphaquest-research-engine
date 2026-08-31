from __future__ import annotations

from contextlib import contextmanager
from datetime import datetime, timedelta
from functools import lru_cache
import hashlib
import json
import os
from pathlib import Path
import tempfile
from zoneinfo import ZoneInfo

import fcntl
import numpy as np
import pandas as pd
import pyarrow.parquet as pq

import alphaquest.data.sierra_events as sierra_events_module
from alphaquest.data.sierra_events import (
    SIERRA_EVENT_PRICE_PATH_SEMANTICS,
    SIERRA_TIMESTAMP_PRECISION_NS,
    reconstruct_sierra_trade_events,
)
from alphaquest.research.storage import load_storage_layout
from alphaquest.utils.hashing import object_sha256

SCID_EPOCH = datetime(1899, 12, 30)
ET = ZoneInfo("America/New_York")

SCID_RECORD_COLUMNS = [
    "scid_datetime_us",
    "open",
    "high",
    "low",
    "close",
    "num_trades",
    "volume",
    "bid_volume",
    "ask_volume",
]

SCID_RECORD_PRICE_PATH_SEMANTICS = SIERRA_EVENT_PRICE_PATH_SEMANTICS
SIERRA_CANONICAL_SESSION_CACHE_SCHEMA = "alphaquest.sierra-canonical-session-cache/v1"

_SCID_EXECUTION_COLUMNS = [
    "timestamp",
    "symbol",
    "contract_symbol",
    "open",
    "high",
    "low",
    "close",
    "volume",
    "signed_volume",
    "buy_volume",
    "sell_volume",
    "trades",
    "num_trades",
    "scid_datetime_us",
    "last_scid_datetime_us",
    "source_scid_datetime_us",
    "source_last_scid_datetime_us",
    "source_ordinal",
    "side",
    "component_rows",
    "timestamp_precision_ns",
    "timestamp_uncertainty_ns",
    "quality_capability",
    "execution_granularity",
    "price_path_semantics",
    "raw_scid_open",
    "raw_scid_high",
    "raw_scid_low",
    "raw_scid_close",
]


def load_scid_record_execution_data(
    config: dict,
    *,
    date_bounds: dict | None = None,
) -> pd.DataFrame:
    """Load Databento-validated, reconstructed Sierra trade events.

    Every requested session must pass the configured capability in the quality
    manifest, unless the caller explicitly chooses the ``blackout`` policy.
    Unbundled FIRST/LAST component rows are collapsed before replay.
    """

    parts = [part for _, part in iter_scid_record_execution_sessions(config, date_bounds=date_bounds)]
    if not parts:
        out = pd.DataFrame(columns=_SCID_EXECUTION_COLUMNS)
    else:
        out = pd.concat(parts, ignore_index=True)
        out = out.sort_values(["timestamp", "source_ordinal"], kind="mergesort").reset_index(drop=True)
    out.attrs["detail_granularity"] = "normalized_trade_event"
    out.attrs["price_path_semantics"] = SCID_RECORD_PRICE_PATH_SEMANTICS
    out.attrs["source_quality_label"] = (
        "Databento-compared Sierra trade-event replay after FIRST/LAST unbundled-trade "
        "reconstruction; source order retained; "
        f"timestamp inversion policy={config.get('timestamp_inversion_policy', 'reject')}; "
        "not exchange MBO sequencing."
    )
    out.attrs["required_capability"] = str(config.get("required_capability", "full_strategy_events"))
    out.attrs["timestamp_precision_ns"] = SIERRA_TIMESTAMP_PRECISION_NS
    return out


def iter_scid_record_execution_sessions(
    config: dict,
    *,
    date_bounds: dict | None = None,
):
    """Yield one governed Sierra event frame at a time to bound replay memory."""

    raw_dir = Path(config.get("raw_dir", "data/raw/ES/sierra-es-trades"))
    roll_calendar = Path(
        config.get("roll_calendar", "data/reference/ES/roll_calendars/motivewave_rithmic_roll_calendar.csv")
    )
    root_symbol = str(config.get("root_symbol", config.get("symbol", "ES")))
    timezone = str(config.get("timezone", "America/New_York"))
    rth_start_minute = _time_to_minute(config.get("rth_start", "09:30:00"))
    rth_end_minute = _time_to_minute(config.get("rth_end", "16:00:00"))
    verified_start_minute = _time_to_minute(config.get("verified_window_start", "09:30:00"))
    required_capability = str(
        config.get("required_capability", "full_strategy_events")
    )
    default_verified_end = (
        "16:00:00"
        if required_capability == "full_rth_strategy_events_extrapolated"
        else "11:00:00"
    )
    verified_end_minute = _time_to_minute(
        config.get("verified_window_end", default_verified_end)
    )
    if rth_start_minute < verified_start_minute or rth_end_minute > verified_end_minute:
        raise ValueError(
            "Sierra event replay window exceeds the declared independently "
            f"verified {config.get('verified_window_start', '09:30:00')}-"
            f"{config.get('verified_window_end', default_verified_end)} ET scope."
        )
    quality_manifest = Path(
        config.get(
            "quality_manifest",
            "data/reference/ES/event_quality/sierra_event_capabilities_0930_1100.csv",
        )
    )
    ineligible_policy = str(config.get("ineligible_session_policy", "error")).lower()
    timestamp_inversion_policy = str(
        config.get("timestamp_inversion_policy", "reject")
    )
    max_timestamp_inversion_rate = float(
        config.get("max_timestamp_inversion_rate", 0.0)
    )
    allow_unverified_for_tests = bool(config.get("allow_unverified_for_tests", False))
    raw_manifest_path = Path(str(config.get("raw_manifest") or ""))
    raw_manifest = _load_raw_manifest(raw_manifest_path, raw_dir, allow_unverified_for_tests)
    cache_enabled = _canonical_session_cache_enabled(
        config,
        allow_unverified_for_tests=allow_unverified_for_tests,
    )
    cache_root = (
        _canonical_session_cache_root(config, raw_dir)
        if cache_enabled
        else None
    )

    files = {path.stem.replace("-CME", ""): path for path in raw_dir.glob("*.parquet")}
    if not files:
        raise ValueError(f"No Sierra SCID Parquet files found in {raw_dir}")

    periods = _active_periods(roll_calendar, files, root_symbol)
    start, end = _bounds_to_utc_naive(date_bounds, timezone)
    manifest = _load_quality_manifest(
        quality_manifest,
        required_capability=required_capability,
        allow_unverified_for_tests=allow_unverified_for_tests,
    )
    requested = _requested_manifest_rows(manifest, start=start, end=end, periods=periods)
    ineligible = requested.loc[~requested[required_capability].map(_as_bool)].copy()
    if len(ineligible) and ineligible_policy != "blackout":
        sample = ", ".join(ineligible["session_date"].astype(str).head(8))
        raise ValueError(
            f"{len(ineligible)} requested Sierra sessions fail capability {required_capability!r} "
            f"({sample}). Set ineligible_session_policy=blackout only for explicit session exclusion."
        )
    eligible = requested.loc[requested[required_capability].map(_as_bool)].copy()
    period_by_symbol = {period["symbol"]: period for period in periods}
    for row in eligible.itertuples(index=False):
        period = period_by_symbol.get(str(row.contract))
        if period is None:
            continue
        raw_file_sha256 = _verify_raw_contract_file(period["path"], raw_manifest)
        load_kwargs = {
            "path": period["path"],
            "session_date": str(row.session_date),
            "root_symbol": root_symbol,
            "contract_symbol": str(row.contract),
            "rth_start_minute": rth_start_minute,
            "rth_end_minute": rth_end_minute,
            "required_capability": required_capability,
            "timestamp_inversion_policy": timestamp_inversion_policy,
            "max_timestamp_inversion_rate": max_timestamp_inversion_rate,
        }
        part = (
            _load_cached_session_events(
                **load_kwargs,
                raw_file_sha256=raw_file_sha256,
                cache_root=cache_root,
                timezone=timezone,
            )
            if cache_root is not None
            else _load_session_events(**load_kwargs)
        )
        if not part.empty:
            yield str(row.session_date), part


def _canonical_session_cache_enabled(
    config: dict,
    *,
    allow_unverified_for_tests: bool,
) -> bool:
    raw = config.get("canonical_session_cache")
    explicitly_configured = raw is not None
    if isinstance(raw, dict):
        enabled = bool(raw.get("enabled", True))
    elif raw is None:
        enabled = True
    else:
        enabled = bool(raw)
    # Unit-test fixtures and ungoverned sources should not create persistent
    # cache state unless the caller explicitly requests that behavior.
    if allow_unverified_for_tests and not explicitly_configured:
        return False
    return enabled


def _canonical_session_cache_root(config: dict, raw_dir: Path) -> Path:
    raw = config.get("canonical_session_cache")
    if isinstance(raw, dict) and raw.get("directory"):
        path = Path(str(raw["directory"]))
        return path if path.is_absolute() else (_project_root_for_path(raw_dir) / path).resolve()
    project_root = _project_root_for_path(raw_dir)
    return load_storage_layout(project_root).run_store_root / "sierra-canonical-session-cache"


def _project_root_for_path(path: Path) -> Path:
    resolved = path.resolve()
    for candidate in (resolved, *resolved.parents):
        if (candidate / "config" / "storage_layout.yaml").is_file():
            return candidate
    return Path.cwd().resolve()


def _load_cached_session_events(
    *,
    path: Path,
    session_date: str,
    root_symbol: str,
    contract_symbol: str,
    rth_start_minute: int,
    rth_end_minute: int,
    required_capability: str,
    timestamp_inversion_policy: str,
    max_timestamp_inversion_rate: float,
    raw_file_sha256: str,
    cache_root: Path,
    timezone: str,
) -> pd.DataFrame:
    identity = {
        "schema": SIERRA_CANONICAL_SESSION_CACHE_SCHEMA,
        "raw_file": path.name,
        "raw_file_sha256": str(raw_file_sha256),
        "session_date": str(session_date),
        "root_symbol": str(root_symbol),
        "contract_symbol": str(contract_symbol),
        "timezone": str(timezone),
        "rth_start_minute": int(rth_start_minute),
        "rth_end_minute": int(rth_end_minute),
        "required_capability": str(required_capability),
        "timestamp_inversion_policy": str(timestamp_inversion_policy),
        "max_timestamp_inversion_rate": float(max_timestamp_inversion_rate),
        "timestamp_precision_ns": int(SIERRA_TIMESTAMP_PRECISION_NS),
        "price_path_semantics": str(SCID_RECORD_PRICE_PATH_SEMANTICS),
        "reconstruction_implementation_sha256": _reconstruction_implementation_sha256(),
    }
    key = object_sha256(identity)
    cached = _read_canonical_session_cache(cache_root, key, identity)
    if cached is not None:
        return cached

    cache_root.mkdir(parents=True, exist_ok=True)
    lock_root = cache_root / ".locks"
    lock_root.mkdir(parents=True, exist_ok=True)
    with _exclusive_cache_lock(lock_root / f"{key}.lock"):
        cached = _read_canonical_session_cache(cache_root, key, identity)
        if cached is not None:
            return cached
        result = _load_session_events(
            path,
            session_date=session_date,
            root_symbol=root_symbol,
            contract_symbol=contract_symbol,
            rth_start_minute=rth_start_minute,
            rth_end_minute=rth_end_minute,
            required_capability=required_capability,
            timestamp_inversion_policy=timestamp_inversion_policy,
            max_timestamp_inversion_rate=max_timestamp_inversion_rate,
        )
        if result.empty:
            return result
        _write_canonical_session_cache(cache_root, key, identity, result)
        result.attrs["canonical_session_cache"] = {
            "schema": SIERRA_CANONICAL_SESSION_CACHE_SCHEMA,
            "cache_key": key,
            "hit": False,
        }
        return result


def _read_canonical_session_cache(
    cache_root: Path,
    key: str,
    identity: dict,
) -> pd.DataFrame | None:
    entry = cache_root / key[:2] / key
    manifest_path = entry / "manifest.json"
    events_path = entry / "events.parquet"
    if not manifest_path.is_file() or not events_path.is_file():
        return None
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    if (
        manifest.get("schema") != SIERRA_CANONICAL_SESSION_CACHE_SCHEMA
        or manifest.get("cache_key") != key
        or manifest.get("source_identity") != identity
    ):
        return None
    stat = events_path.stat()
    actual_hash = _cached_file_sha256(
        str(events_path.resolve()),
        stat.st_size,
        stat.st_mtime_ns,
    )
    if actual_hash != str(manifest.get("events_sha256") or ""):
        return None
    try:
        frame = pd.read_parquet(events_path)
    except (OSError, ValueError):
        return None
    if (
        len(frame) != int(manifest.get("row_count") or -1)
        or list(frame.columns) != list(manifest.get("columns") or [])
    ):
        return None
    attrs = manifest.get("frame_attrs")
    if isinstance(attrs, dict):
        frame.attrs.update(attrs)
    frame.attrs["canonical_session_cache"] = {
        "schema": SIERRA_CANONICAL_SESSION_CACHE_SCHEMA,
        "cache_key": key,
        "hit": True,
    }
    return frame


def _write_canonical_session_cache(
    cache_root: Path,
    key: str,
    identity: dict,
    frame: pd.DataFrame,
) -> None:
    entry = cache_root / key[:2] / key
    entry.mkdir(parents=True, exist_ok=True)
    events_path = entry / "events.parquet"
    manifest_path = entry / "manifest.json"
    data_fd, data_name = tempfile.mkstemp(prefix=".events-", suffix=".parquet", dir=entry)
    manifest_fd, manifest_name = tempfile.mkstemp(prefix=".manifest-", suffix=".json", dir=entry)
    os.close(data_fd)
    os.close(manifest_fd)
    temporary_events = Path(data_name)
    temporary_manifest = Path(manifest_name)
    try:
        frame.to_parquet(temporary_events, index=False)
        event_stat = temporary_events.stat()
        events_sha256 = _cached_file_sha256(
            str(temporary_events.resolve()),
            event_stat.st_size,
            event_stat.st_mtime_ns,
        )
        manifest = {
            "schema": SIERRA_CANONICAL_SESSION_CACHE_SCHEMA,
            "cache_key": key,
            "source_identity": identity,
            "events_sha256": events_sha256,
            "row_count": int(len(frame)),
            "columns": list(frame.columns),
            "frame_attrs": _json_safe_mapping(frame.attrs),
        }
        temporary_manifest.write_text(
            json.dumps(manifest, sort_keys=True, separators=(",", ":")),
            encoding="utf-8",
        )
        os.replace(temporary_events, events_path)
        os.replace(temporary_manifest, manifest_path)
    finally:
        temporary_events.unlink(missing_ok=True)
        temporary_manifest.unlink(missing_ok=True)


@contextmanager
def _exclusive_cache_lock(path: Path):
    with path.open("a+b") as handle:
        fcntl.flock(handle.fileno(), fcntl.LOCK_EX)
        try:
            yield
        finally:
            fcntl.flock(handle.fileno(), fcntl.LOCK_UN)


def _json_safe_mapping(value: dict) -> dict:
    def convert(item):
        if isinstance(item, dict):
            return {str(key): convert(child) for key, child in item.items()}
        if isinstance(item, (list, tuple)):
            return [convert(child) for child in item]
        if isinstance(item, np.generic):
            return item.item()
        if isinstance(item, (pd.Timestamp, datetime)):
            return item.isoformat()
        if item is None or isinstance(item, (str, int, float, bool)):
            return item
        return str(item)

    return convert(dict(value))


@lru_cache(maxsize=1)
def _reconstruction_implementation_sha256() -> str:
    paths = [Path(__file__), Path(str(sierra_events_module.__file__))]
    records = []
    for path in paths:
        stat = path.stat()
        records.append(
            {
                "path": path.name,
                "sha256": _cached_file_sha256(
                    str(path.resolve()),
                    stat.st_size,
                    stat.st_mtime_ns,
                ),
            }
        )
    return object_sha256(records)


def _load_raw_manifest(path: Path, raw_dir: Path, allow_unverified_for_tests: bool) -> dict[str, dict]:
    if allow_unverified_for_tests:
        return {}
    if not path.is_file():
        raise ValueError(f"Sierra raw-file manifest not found: {path}")
    try:
        document = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"Sierra raw-file manifest is invalid: {path}: {exc}") from exc
    if document.get("schema") != "alphaquest.sierra-raw-manifest/v1":
        raise ValueError("Sierra raw-file manifest schema is missing or unsupported")
    if Path(str(document.get("raw_dir") or "")).resolve() != raw_dir.resolve():
        raise ValueError("Sierra raw-file manifest does not bind the configured raw_dir")
    files = document.get("files")
    if not isinstance(files, list) or not files:
        raise ValueError("Sierra raw-file manifest contains no files")
    records: dict[str, dict] = {}
    for item in files:
        if not isinstance(item, dict) or not item.get("name") or not item.get("sha256"):
            raise ValueError("Sierra raw-file manifest contains an invalid file record")
        records[str(item["name"])] = item
    return records


def _verify_raw_contract_file(path: Path, manifest: dict[str, dict]) -> str:
    if not manifest:
        stat = path.stat()
        return _cached_file_sha256(str(path.resolve()), stat.st_size, stat.st_mtime_ns)
    record = manifest.get(path.name)
    if record is None:
        raise ValueError(f"Sierra raw-file manifest does not declare {path.name}")
    stat = path.stat()
    if int(record.get("size") or -1) != stat.st_size:
        raise ValueError(f"Sierra raw contract file size drift: {path}")
    actual = _cached_file_sha256(str(path.resolve()), stat.st_size, stat.st_mtime_ns)
    if actual != str(record.get("sha256") or ""):
        raise ValueError(f"Sierra raw contract file hash drift: {path}")
    return actual


@lru_cache(maxsize=128)
def _cached_file_sha256(path: str, size: int, mtime_ns: int) -> str:
    del size, mtime_ns
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for block in iter(lambda: handle.read(4 * 1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _load_session_events(
    path: Path,
    *,
    session_date: str,
    root_symbol: str,
    contract_symbol: str,
    rth_start_minute: int,
    rth_end_minute: int,
    required_capability: str,
    timestamp_inversion_policy: str,
    max_timestamp_inversion_rate: float,
) -> pd.DataFrame:
    day = pd.Timestamp(session_date, tz=ET)
    start_et = day + pd.Timedelta(minutes=rth_start_minute)
    end_et = day + pd.Timedelta(minutes=rth_end_minute)
    start_utc = start_et.tz_convert("UTC").tz_localize(None).to_pydatetime()
    end_utc = end_et.tz_convert("UTC").tz_localize(None).to_pydatetime()
    buffer_us = 1_000_000
    raw = pq.read_table(
        path,
        columns=SCID_RECORD_COLUMNS,
        filters=[
            ("scid_datetime_us", ">=", _datetime_to_scid_us(start_utc) - buffer_us),
            ("scid_datetime_us", "<", _datetime_to_scid_us(end_utc) + buffer_us),
        ],
    ).to_pandas()
    if raw.empty:
        return pd.DataFrame(columns=_SCID_EXECUTION_COLUMNS)
    raw["source_ordinal"] = np.arange(len(raw), dtype=np.int64)
    events, reconstruction_stats = reconstruct_sierra_trade_events(
        raw,
        timestamp_inversion_policy=timestamp_inversion_policy,
        max_timestamp_inversion_rate=max_timestamp_inversion_rate,
    )
    in_window = events["scid_datetime_us"].between(
        _datetime_to_scid_us(start_utc), _datetime_to_scid_us(end_utc), inclusive="left"
    )
    events = events.loc[in_window].copy()
    if events.empty:
        return pd.DataFrame(columns=_SCID_EXECUTION_COLUMNS)
    timestamps = pd.to_datetime(
        [SCID_EPOCH + timedelta(microseconds=int(value)) for value in events["scid_datetime_us"]]
    ).tz_localize("UTC").tz_convert(ET)
    price = events["price"].to_numpy(dtype=float)
    result = pd.DataFrame(
        {
            "timestamp": timestamps,
            "symbol": root_symbol,
            "contract_symbol": contract_symbol,
            "open": price,
            "high": price,
            "low": price,
            "close": price,
            "volume": events["volume"].to_numpy(dtype=np.int64),
            "signed_volume": events["signed_volume"].to_numpy(dtype=np.int64),
            "buy_volume": events["buy_volume"].to_numpy(dtype=np.int64),
            "sell_volume": events["sell_volume"].to_numpy(dtype=np.int64),
            "trades": np.ones(len(events), dtype=np.int64),
            "num_trades": np.ones(len(events), dtype=np.int64),
            "scid_datetime_us": events["scid_datetime_us"].to_numpy(dtype=np.int64),
            "last_scid_datetime_us": events["last_scid_datetime_us"].to_numpy(dtype=np.int64),
            "source_scid_datetime_us": events["source_scid_datetime_us"].to_numpy(
                dtype=np.int64
            ),
            "source_last_scid_datetime_us": events[
                "source_last_scid_datetime_us"
            ].to_numpy(dtype=np.int64),
            "source_ordinal": events["source_ordinal"].to_numpy(dtype=np.int64),
            "side": events["side"].to_numpy(),
            "component_rows": events["component_rows"].to_numpy(dtype=np.int64),
            "timestamp_precision_ns": SIERRA_TIMESTAMP_PRECISION_NS,
            "timestamp_uncertainty_ns": SIERRA_TIMESTAMP_PRECISION_NS,
            "quality_capability": required_capability,
            "execution_granularity": "normalized_trade_event",
            "price_path_semantics": SCID_RECORD_PRICE_PATH_SEMANTICS,
            "raw_scid_open": price,
            "raw_scid_high": price,
            "raw_scid_low": price,
            "raw_scid_close": price,
        }
    )
    result = result[_SCID_EXECUTION_COLUMNS]
    result.attrs["timestamp_reconstruction"] = reconstruction_stats
    result.attrs["source_quality_label"] = (
        "Governed Sierra SCID events reconstructed in stored source order with "
        f"timestamp inversion policy={timestamp_inversion_policy}."
    )
    return result


def _load_quality_manifest(
    path: Path,
    *,
    required_capability: str,
    allow_unverified_for_tests: bool,
) -> pd.DataFrame:
    if allow_unverified_for_tests:
        return pd.DataFrame(
            columns=["session_date", "contract", required_capability]
        )
    if not path.exists():
        raise ValueError(f"Sierra event quality manifest not found: {path}")
    manifest = pd.read_csv(path, dtype={"session_date": "string", "contract": "string"})
    required = {"session_date", "contract", required_capability}
    missing = sorted(required - set(manifest.columns))
    if missing:
        raise ValueError(f"Sierra quality manifest is missing columns: {missing}")
    return manifest


def _requested_manifest_rows(
    manifest: pd.DataFrame,
    *,
    start: datetime | None,
    end: datetime | None,
    periods: list[dict],
) -> pd.DataFrame:
    if manifest.empty:
        dates = pd.date_range(
            pd.Timestamp(start).date(),
            (pd.Timestamp(end) - pd.Timedelta(microseconds=1)).date(),
            freq="B",
        )
        rows = []
        for date in dates:
            session_date = pd.Timestamp(date).date()
            period = next(
                (
                    item
                    for item in periods
                    if item["start"].date() <= session_date <= item["end"].date()
                ),
                None,
            )
            if period:
                rows.append(
                    {
                        "session_date": str(session_date),
                        "contract": period["symbol"],
                        next(
                            column
                            for column in manifest.columns
                            if column not in {"session_date", "contract"}
                        ): True,
                    }
                )
        return pd.DataFrame(rows, columns=manifest.columns)
    result = manifest.copy()
    dates = pd.to_datetime(result["session_date"])
    if start is not None:
        result = result.loc[dates >= pd.Timestamp(start).normalize()]
        dates = pd.to_datetime(result["session_date"])
    if end is not None:
        result = result.loc[dates < pd.Timestamp(end).normalize()]
    return result.reset_index(drop=True)


def _as_bool(value) -> bool:
    if isinstance(value, str):
        return value.strip().lower() in {"1", "true", "yes"}
    return bool(value)


def _load_period_records(
    path: Path,
    *,
    root_symbol: str,
    contract_symbol: str,
    start: datetime,
    end: datetime,
    batch_size: int,
    rth_start_minute: int,
    rth_end_minute: int,
) -> pd.DataFrame:
    start_us = _datetime_to_scid_us(start)
    end_us = _datetime_to_scid_us(end)
    parts = []
    pf = pq.ParquetFile(path)
    for batch in pf.iter_batches(batch_size=batch_size, columns=SCID_RECORD_COLUMNS):
        part = _records_from_batch(
            batch,
            root_symbol=root_symbol,
            contract_symbol=contract_symbol,
            start_us=start_us,
            end_us=end_us,
            rth_start_minute=rth_start_minute,
            rth_end_minute=rth_end_minute,
        )
        if not part.empty:
            parts.append(part)
    if not parts:
        return pd.DataFrame()
    return pd.concat(parts, ignore_index=True)


def _records_from_batch(
    batch,
    *,
    root_symbol: str,
    contract_symbol: str,
    start_us: int,
    end_us: int,
    rth_start_minute: int,
    rth_end_minute: int,
) -> pd.DataFrame:
    ts = batch.column(batch.schema.get_field_index("scid_datetime_us")).to_numpy(zero_copy_only=False).astype(
        np.int64, copy=False
    )
    raw_open = batch.column(batch.schema.get_field_index("open")).to_numpy(zero_copy_only=False)
    raw_high = batch.column(batch.schema.get_field_index("high")).to_numpy(zero_copy_only=False)
    raw_low = batch.column(batch.schema.get_field_index("low")).to_numpy(zero_copy_only=False)
    close = batch.column(batch.schema.get_field_index("close")).to_numpy(zero_copy_only=False)
    volume = batch.column(batch.schema.get_field_index("volume")).to_numpy(zero_copy_only=False)
    bid = batch.column(batch.schema.get_field_index("bid_volume")).to_numpy(zero_copy_only=False)
    ask = batch.column(batch.schema.get_field_index("ask_volume")).to_numpy(zero_copy_only=False)
    trades = batch.column(batch.schema.get_field_index("num_trades")).to_numpy(zero_copy_only=False)

    mask = (
        (ts >= start_us)
        & (ts < end_us)
        & np.isfinite(close)
        & (close > 0)
        & np.isfinite(volume)
        & (volume > 0)
    )
    if not mask.any():
        return pd.DataFrame(columns=_SCID_EXECUTION_COLUMNS)

    ts = ts[mask]
    raw_open = np.where(np.isfinite(raw_open[mask]), raw_open[mask], np.nan).astype(np.float64, copy=False)
    raw_high = np.where(np.isfinite(raw_high[mask]), raw_high[mask], np.nan).astype(np.float64, copy=False)
    raw_low = np.where(np.isfinite(raw_low[mask]), raw_low[mask], np.nan).astype(np.float64, copy=False)
    close = close[mask].astype(np.float64, copy=False)
    volume = volume[mask].astype(np.int64, copy=False)
    bid = bid[mask].astype(np.int64, copy=False)
    ask = ask[mask].astype(np.int64, copy=False)
    trades = trades[mask].astype(np.int64, copy=False)
    trades = np.where(trades <= 0, 1, trades)

    order = np.argsort(ts, kind="stable")
    ts = ts[order]
    raw_open = raw_open[order]
    raw_high = raw_high[order]
    raw_low = raw_low[order]
    close = close[order]
    volume = volume[order]
    bid = bid[order]
    ask = ask[order]
    trades = trades[order]
    signed = ask - bid
    timestamps = pd.Series(pd.to_datetime([SCID_EPOCH + timedelta(microseconds=int(value)) for value in ts]))
    timestamps = timestamps.dt.tz_localize("UTC").dt.tz_convert(ET)
    minute_of_day = timestamps.dt.hour * 60 + timestamps.dt.minute
    rth_mask = (minute_of_day >= rth_start_minute) & (minute_of_day < rth_end_minute)
    if not bool(rth_mask.any()):
        return pd.DataFrame(columns=_SCID_EXECUTION_COLUMNS)
    ts = ts[rth_mask.to_numpy()]
    timestamps = timestamps[rth_mask].reset_index(drop=True)
    close = close[rth_mask.to_numpy()]
    raw_open = raw_open[rth_mask.to_numpy()]
    raw_high = raw_high[rth_mask.to_numpy()]
    raw_low = raw_low[rth_mask.to_numpy()]
    volume = volume[rth_mask.to_numpy()]
    bid = bid[rth_mask.to_numpy()]
    ask = ask[rth_mask.to_numpy()]
    trades = trades[rth_mask.to_numpy()]
    signed = signed[rth_mask.to_numpy()]
    traded_open = close.copy()
    traded_high = close.copy()
    traded_low = close.copy()

    return pd.DataFrame(
        {
            "timestamp": timestamps,
            "symbol": root_symbol,
            "contract_symbol": contract_symbol,
            "open": traded_open,
            "high": traded_high,
            "low": traded_low,
            "close": close,
            "volume": volume,
            "signed_volume": signed,
            "buy_volume": ask,
            "sell_volume": bid,
            "trades": trades,
            "num_trades": trades,
            "scid_datetime_us": ts,
            "execution_granularity": "scid_record",
            "price_path_semantics": SCID_RECORD_PRICE_PATH_SEMANTICS,
            "raw_scid_open": raw_open,
            "raw_scid_high": raw_high,
            "raw_scid_low": raw_low,
            "raw_scid_close": close,
        }
    )


def _active_periods(roll_calendar: Path, files: dict[str, Path], root_symbol: str) -> list[dict]:
    calendar = pd.read_csv(roll_calendar)
    starts_utc = pd.to_datetime(calendar["start_timestamp"], utc=True)
    starts_et = starts_utc.dt.tz_convert(ET)
    calendar = (
        calendar.assign(
            start_utc=starts_utc.dt.tz_localize(None),
            start_et=starts_et.dt.tz_localize(None),
        )
        .sort_values("start_utc")
        .reset_index(drop=True)
    )
    calendar["end_utc"] = calendar["start_utc"].shift(-1)
    calendar["symbol"] = [
        _roll_contract_to_file_symbol(start, contract, root_symbol)
        for start, contract in zip(calendar["start_et"], calendar["contract_symbol"], strict=False)
    ]

    periods = []
    for row in calendar.itertuples(index=False):
        path = files.get(row.symbol)
        if path is None or _is_bar_like_contract(row.symbol, path):
            continue
        file_start, file_end = _parquet_timestamp_bounds(path)
        start = max(row.start_utc.to_pydatetime(), file_start)
        end = min(row.end_utc.to_pydatetime() if pd.notna(row.end_utc) else file_end, file_end)
        if start < end:
            periods.append({"symbol": row.symbol, "path": path, "start": start, "end": end})
    return periods


def _is_bar_like_contract(symbol: str, path: Path) -> bool:
    if symbol in {"ESM10", "ESU10", "ESZ10"}:
        return True
    return pq.ParquetFile(path).metadata.num_rows < 1_000_000


def _roll_contract_to_file_symbol(start: pd.Timestamp, contract: str, root_symbol: str) -> str:
    month = _contract_month_code(contract)
    year = start.year + 1 if month == "H" else start.year
    return f"{root_symbol}{month}{year % 100:02d}"


def _contract_month_code(contract: str) -> str:
    for char in str(contract):
        if char in {"H", "M", "U", "Z"}:
            return char
    raise ValueError(f"Could not infer quarterly month code from contract symbol: {contract!r}")


def _parquet_timestamp_bounds(path: Path) -> tuple[datetime, datetime]:
    pf = pq.ParquetFile(path)
    lo = hi = None
    for row_group in range(pf.num_row_groups):
        stats = pf.metadata.row_group(row_group).column(0).statistics
        if stats is None or stats.min is None or stats.max is None:
            continue
        lo = int(stats.min) if lo is None else min(lo, int(stats.min))
        hi = int(stats.max) if hi is None else max(hi, int(stats.max))
    if lo is None or hi is None:
        raise ValueError(f"No timestamp statistics available in {path}")
    return SCID_EPOCH + timedelta(microseconds=lo), SCID_EPOCH + timedelta(microseconds=hi)


def _bounds_to_utc_naive(bounds: dict | None, timezone: str) -> tuple[datetime | None, datetime | None]:
    if not bounds:
        return None, None
    tz = ZoneInfo(timezone)
    start = bounds.get("start_timestamp") or bounds.get("start_date")
    end = bounds.get("end_timestamp")
    if not end and bounds.get("end_date"):
        end = pd.Timestamp(bounds["end_date"]) + pd.Timedelta(days=1)
    return _bound_to_utc_naive(start, tz), _bound_to_utc_naive(end, tz)


def _bound_to_utc_naive(value, timezone: ZoneInfo) -> datetime | None:
    if value is None:
        return None
    ts = pd.Timestamp(value)
    if ts.tzinfo is None:
        ts = ts.tz_localize(timezone)
    else:
        ts = ts.tz_convert(timezone)
    return ts.tz_convert("UTC").tz_localize(None).to_pydatetime()


def _datetime_to_scid_us(value: datetime) -> int:
    return int((value - SCID_EPOCH).total_seconds() * 1_000_000)


def _time_to_minute(value) -> int:
    ts = pd.Timestamp(f"2000-01-01 {value}")
    return int(ts.hour * 60 + ts.minute)
