from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
import re

import pandas as pd

from propstack.utils.progress import progress_bar


COLUMN_ALIASES = {
    "date": "timestamp",
    "datetime": "timestamp",
    "time": "timestamp",
    "o": "open",
    "h": "high",
    "l": "low",
    "c": "close",
    "v": "volume",
    "vol": "volume",
}

DBN_FILE_RE = re.compile(r".*-(\d{8})-(\d{8})\..*\.dbn(?:\.zst)?$")
SOURCE_ALIASES = {
    "csv": "csv",
    "raw_csv": "csv",
    "parquet": "parquet",
    "raw_parquet": "parquet",
    "databento": "databento_dbn",
    "databento_dbn": "databento_dbn",
    "dbn": "databento_dbn",
}


def normalize_columns(df: pd.DataFrame) -> pd.DataFrame:
    renamed = {}
    for col in df.columns:
        key = col.strip().lower().replace(" ", "_")
        renamed[col] = COLUMN_ALIASES.get(key, key)
    return df.rename(columns=renamed)


def infer_data_source(config: dict) -> str:
    source = config.get("source")
    if not source:
        source = "databento_dbn" if config.get("raw_dir") else "csv"
    normalized = SOURCE_ALIASES.get(str(source).lower())
    if not normalized:
        raise ValueError(f"Unsupported data source: {source}")
    return normalized


def load_raw_data(
    config: dict,
    date_bounds: dict | None = None,
    status_callback: Callable[[str], None] | None = None,
    show_progress: bool = False,
) -> pd.DataFrame:
    source = infer_data_source(config)
    if source == "csv":
        _emit(status_callback, f"Reading CSV source: {config['raw_csv']}")
        return load_raw_csv(
            config["raw_csv"],
            symbol=config.get("symbol", "ES"),
            timezone=config.get("timezone", "America/Chicago"),
            csv_format=config.get("csv_format", "standard"),
            has_header=bool(config.get("has_header", True)),
            timestamp_format=config.get("timestamp_format"),
            date_bounds=date_bounds,
        )
    if source == "parquet":
        raw_parquet = config.get("raw_parquet") or config.get("raw_csv")
        if not raw_parquet:
            raise ValueError("Parquet data source requires data.raw_parquet")
        _emit(status_callback, f"Reading Parquet source: {raw_parquet}")
        return load_raw_parquet(
            raw_parquet,
            symbol=config.get("symbol", "ES"),
            timezone=config.get("timezone", "America/Chicago"),
            date_bounds=date_bounds,
        )
    if source == "databento_dbn":
        return load_databento_dbn(
            config,
            date_bounds=date_bounds,
            status_callback=status_callback,
            show_progress=show_progress,
        )
    raise ValueError(f"Unsupported data source: {source}")


def load_raw_csv(
    path: str,
    symbol: str = "ES",
    timezone: str = "America/Chicago",
    csv_format: str = "standard",
    has_header: bool = True,
    timestamp_format: str | None = None,
    date_bounds: dict | None = None,
) -> pd.DataFrame:
    if csv_format == "yyyymmdd_hhmmss_ohlcv":
        df = pd.read_csv(
            path,
            header=None,
            names=["timestamp", "open", "high", "low", "close", "volume"],
        )
        timestamp_format = timestamp_format or "%Y%m%d %H%M%S"
    else:
        header = 0 if has_header else None
        df = pd.read_csv(path, header=header)
        if not has_header:
            df.columns = ["timestamp", "open", "high", "low", "close", "volume"][: len(df.columns)]
        df = normalize_columns(df)

    required = {"timestamp", "open", "high", "low", "close", "volume"}
    missing = required - set(df.columns)
    if missing:
        raise ValueError(f"CSV missing required columns: {sorted(missing)}")
    df["timestamp"] = pd.to_datetime(df["timestamp"], format=timestamp_format)
    if df["timestamp"].dt.tz is None:
        df["timestamp"] = df["timestamp"].dt.tz_localize(timezone)
    else:
        df["timestamp"] = df["timestamp"].dt.tz_convert(timezone)
    if "symbol" not in df.columns:
        df["symbol"] = symbol
    for col in ["open", "high", "low", "close", "volume"]:
        df[col] = pd.to_numeric(df[col], errors="coerce")
    df = filter_timestamp_bounds(df, date_bounds, timezone)
    return df.sort_values("timestamp").reset_index(drop=True)


def load_raw_parquet(
    path: str,
    symbol: str = "ES",
    timezone: str = "America/Chicago",
    date_bounds: dict | None = None,
) -> pd.DataFrame:
    df = normalize_columns(pd.read_parquet(path))
    required = {"timestamp", "open", "high", "low", "close", "volume"}
    missing = required - set(df.columns)
    if missing:
        raise ValueError(f"Parquet missing required columns: {sorted(missing)}")

    df["timestamp"] = pd.to_datetime(df["timestamp"])
    if df["timestamp"].dt.tz is None:
        df["timestamp"] = df["timestamp"].dt.tz_localize(timezone)
    else:
        df["timestamp"] = df["timestamp"].dt.tz_convert(timezone)
    if "symbol" not in df.columns:
        df["symbol"] = symbol
    numeric_columns = [
        column
        for column in df.columns
        if column not in {"timestamp", "symbol", "contract_symbol", "timestamp_utc", "session_date", "session_label"}
    ]
    for col in numeric_columns:
        df[col] = pd.to_numeric(df[col], errors="coerce")
    df = filter_timestamp_bounds(df, date_bounds, timezone)
    return df.sort_values("timestamp").reset_index(drop=True)


def load_databento_dbn(
    config: dict,
    date_bounds: dict | None = None,
    status_callback: Callable[[str], None] | None = None,
    show_progress: bool = False,
) -> pd.DataFrame:
    raw_dir = config.get("raw_dir")
    if not raw_dir:
        raise ValueError("Databento DBN data source requires data.raw_dir")

    files = list_databento_dbn_files(raw_dir, date_bounds=date_bounds)
    if not files:
        raise ValueError(f"No Databento DBN files found in {raw_dir} for date bounds {date_bounds}")

    _emit(status_callback, f"Selected {len(files):,} Databento files from {raw_dir}.")
    progress = progress_bar(len(files), "data files", enabled=show_progress)
    progress.update(0, force=True)
    frames = []
    for idx, path in enumerate(files, start=1):
        frames.append(_read_cached_dbn_file(path, config))
        progress.update(idx, force=True)
    _emit(status_callback, "Combining loaded data files...")
    df = pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()
    if df.empty:
        return df

    include_spreads = bool(config.get("include_spreads", False))
    if not include_spreads and "contract_symbol" in df.columns:
        _emit(status_callback, "Filtering spread symbols...")
        df = df[~df["contract_symbol"].astype(str).str.contains("-", regex=False)].copy()

    timezone = config.get("timezone", "America/Chicago")
    _emit(status_callback, "Filtering timestamp bounds and sorting raw bars...")
    df = filter_timestamp_bounds(df, date_bounds, timezone)
    return df.sort_values(["timestamp", "contract_symbol"]).reset_index(drop=True)


def list_databento_dbn_files(raw_dir: str | Path, date_bounds: dict | None = None) -> list[Path]:
    root = Path(raw_dir)
    files = sorted([*root.glob("*.dbn"), *root.glob("*.dbn.zst")])
    start_date, end_date = _date_bounds_as_dates(date_bounds)
    selected = []
    for path in files:
        file_bounds = parse_dbn_file_dates(path)
        if not file_bounds:
            continue
        file_start, file_end = file_bounds
        if start_date and file_end < start_date:
            continue
        if end_date and file_start > end_date:
            continue
        selected.append(path)
    return selected


def parse_dbn_file_dates(path: str | Path) -> tuple[pd.Timestamp, pd.Timestamp] | None:
    match = DBN_FILE_RE.match(Path(path).name)
    if not match:
        return None
    return pd.Timestamp(match.group(1)), pd.Timestamp(match.group(2))


def filter_timestamp_bounds(
    df: pd.DataFrame,
    date_bounds: dict | None,
    timezone: str = "America/Chicago",
) -> pd.DataFrame:
    if not date_bounds or df.empty:
        return df

    filtered = df
    if date_bounds.get("start_timestamp"):
        start = _parse_bound_timestamp(date_bounds["start_timestamp"], timezone)
        filtered = filtered[filtered["timestamp"] >= start]
    elif date_bounds.get("start_date"):
        start = _parse_bound_timestamp(date_bounds["start_date"], timezone)
        filtered = filtered[filtered["timestamp"] >= start]

    if date_bounds.get("end_timestamp"):
        end = _parse_bound_timestamp(date_bounds["end_timestamp"], timezone)
        filtered = filtered[filtered["timestamp"] <= end]
    elif date_bounds.get("end_date"):
        end = _parse_bound_timestamp(date_bounds["end_date"], timezone) + pd.Timedelta(days=1)
        filtered = filtered[filtered["timestamp"] < end]

    return filtered.copy()


def _read_cached_dbn_file(path: Path, config: dict) -> pd.DataFrame:
    cache_path = _dbn_cache_path(path, config)
    if cache_path.exists() and cache_path.stat().st_mtime >= path.stat().st_mtime:
        return _convert_cached_timestamps(pd.read_parquet(cache_path), config)

    df = _read_databento_dbn_file(path, config)
    cache_path.parent.mkdir(parents=True, exist_ok=True)
    df.to_parquet(cache_path, index=False)
    return df


def _convert_cached_timestamps(df: pd.DataFrame, config: dict) -> pd.DataFrame:
    if df.empty or "timestamp" not in df.columns:
        return df
    out = df.copy()
    timezone = config.get("timezone", "America/Chicago")
    out["timestamp"] = pd.to_datetime(out["timestamp"], utc=True).dt.tz_convert(timezone)
    return out


def _read_databento_dbn_file(path: Path, config: dict) -> pd.DataFrame:
    try:
        import databento as db
    except ModuleNotFoundError as exc:
        raise ModuleNotFoundError(
            "Databento DBN data requires the official databento package. "
            "Install project dependencies or run: python3 -m pip install databento"
        ) from exc

    store = db.DBNStore.from_file(path)
    df = store.to_df()
    df = df.reset_index()
    if "ts_event" in df.columns:
        df = df.rename(columns={"ts_event": "timestamp"})
    elif "index" in df.columns:
        df = df.rename(columns={"index": "timestamp"})

    required = {"timestamp", "open", "high", "low", "close", "volume"}
    missing = required - set(df.columns)
    if missing:
        raise ValueError(f"DBN file {path} missing required OHLCV columns: {sorted(missing)}")

    timezone = config.get("timezone", "America/Chicago")
    df["timestamp"] = pd.to_datetime(df["timestamp"], utc=True).dt.tz_convert(timezone)
    if "symbol" not in df.columns:
        df["symbol"] = config.get("symbol", "ES")
    df["contract_symbol"] = df["symbol"].astype(str)
    if "instrument_id" in df.columns:
        df = df.rename(columns={"instrument_id": "contract_instrument_id"})

    for col in ["open", "high", "low", "close", "volume"]:
        df[col] = pd.to_numeric(df[col], errors="coerce")

    columns = ["timestamp", "open", "high", "low", "close", "volume", "symbol", "contract_symbol"]
    if "contract_instrument_id" in df.columns:
        columns.append("contract_instrument_id")
    return df[columns].sort_values(["timestamp", "contract_symbol"]).reset_index(drop=True)


def _dbn_cache_path(path: Path, config: dict) -> Path:
    cache_dir = config.get("cache_dir")
    if cache_dir:
        root = Path(cache_dir)
    else:
        root = Path("data") / "cache" / "databento" / Path(config["raw_dir"]).name
    name = path.name
    if name.endswith(".zst"):
        name = name[:-4]
    if name.endswith(".dbn"):
        name = name[:-4]
    return root / f"{name}.parquet"


def _date_bounds_as_dates(date_bounds: dict | None) -> tuple[pd.Timestamp | None, pd.Timestamp | None]:
    if not date_bounds:
        return None, None
    start_value = date_bounds.get("start_date") or date_bounds.get("start_timestamp")
    end_value = date_bounds.get("end_date") or date_bounds.get("end_timestamp")
    start = pd.Timestamp(start_value).normalize() if start_value else None
    end = pd.Timestamp(end_value).normalize() if end_value else None
    if start is not None and start.tzinfo is not None:
        start = start.tz_convert(None).normalize()
    if end is not None and end.tzinfo is not None:
        end = end.tz_convert(None).normalize()
    return start, end


def _parse_bound_timestamp(value, timezone: str) -> pd.Timestamp:
    ts = pd.Timestamp(value)
    if ts.tzinfo is None:
        return ts.tz_localize(timezone)
    return ts.tz_convert(timezone)


def _emit(callback: Callable[[str], None] | None, message: str) -> None:
    if callback:
        callback(message)
