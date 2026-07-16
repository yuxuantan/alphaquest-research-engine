"""Fail-closed local CSV/Parquet intake for completed-bar research."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import shutil
from typing import Literal
from uuid import uuid4
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

import pandas as pd
import numpy as np
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from alphaquest.authoring.models import DatasetManifestV1
from alphaquest.research.storage import load_storage_layout


class DataImportSpec(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    dataset_id: str = Field(pattern=r"^[a-z0-9][a-z0-9_]*$")
    symbol: Literal["ES", "NQ"]
    timeframe: str = Field(pattern=r"^[1-9]\d*[mhd]$")
    timezone: str
    exchange_timezone: str = "America/New_York"
    timestamp_semantics: Literal["bar_open", "bar_close"]
    roll_policy: Literal["single_contract", "explicit_roll_calendar"]
    roll_calendar_path: str | None = None
    timestamp_column: str
    open_column: str
    high_column: str
    low_column: str
    close_column: str
    volume_column: str
    contract_column: str | None = None
    single_contract_confirmed: bool = False

    @field_validator("timezone", "exchange_timezone")
    @classmethod
    def known_timezone(cls, value: str) -> str:
        try:
            ZoneInfo(value)
        except ZoneInfoNotFoundError as exc:
            raise ValueError(f"unknown IANA timezone: {value}") from exc
        return value

    @model_validator(mode="after")
    def executable_roll_contract(self) -> "DataImportSpec":
        if self.roll_policy == "explicit_roll_calendar":
            if not self.contract_column:
                raise ValueError("explicit_roll_calendar requires a mapped contract column")
            if not self.roll_calendar_path:
                raise ValueError("explicit_roll_calendar requires a roll_calendar_path")
        elif self.roll_calendar_path is not None:
            raise ValueError("roll_calendar_path is only valid with explicit_roll_calendar")
        return self

@dataclass(frozen=True)
class DataImportResult:
    manifest: DatasetManifestV1
    manifest_path: Path
    canonical_path: Path
    quarantined_path: Path
    roll_calendar_path: Path | None = None


class DatasetImporter:
    def __init__(self, project_root: str | Path = ".") -> None:
        self.project_root = Path(project_root).resolve()
        layout = load_storage_layout(self.project_root)
        self.dataset_root = Path(getattr(layout, "dataset_root", self.project_root / "research" / "datasets"))
        runtime = Path(getattr(layout, "studio_runtime_root", layout.run_store_root / "studio-runtime"))
        self.quarantine_root = runtime / "raw-attachments"

    def inspect_columns(self, source_path: str | Path) -> list[str]:
        path = Path(source_path).expanduser().resolve()
        if path.suffix.lower() == ".csv":
            return list(pd.read_csv(path, nrows=5).columns)
        if path.suffix.lower() in {".parquet", ".pq"}:
            return list(pd.read_parquet(path).columns)
        raise ValueError("Studio V1 imports only CSV or Parquet files")

    def import_file(self, source_path: str | Path, spec: DataImportSpec) -> DataImportResult:
        source = Path(source_path).expanduser().resolve()
        if not source.is_file():
            raise FileNotFoundError(f"dataset source is missing: {source}")
        suffix = source.suffix.lower()
        if suffix not in {".csv", ".parquet", ".pq"}:
            raise ValueError("Studio V1 imports only CSV or Parquet files")
        destination = self.dataset_root / spec.dataset_id
        if destination.exists():
            raise FileExistsError(f"dataset ID already exists and will not be overwritten: {spec.dataset_id}")

        source_hash = _sha256(source)
        quarantined = self._quarantine(source, spec.dataset_id, source_hash, category="market-data")
        frame = pd.read_csv(quarantined) if suffix == ".csv" else pd.read_parquet(quarantined)
        required = {
            spec.timestamp_column,
            spec.open_column,
            spec.high_column,
            spec.low_column,
            spec.close_column,
            spec.volume_column,
        }
        if spec.contract_column:
            required.add(spec.contract_column)
        missing = sorted(required - set(frame.columns))
        if missing:
            raise ValueError(f"source is missing mapped columns: {', '.join(missing)}")

        row_count = len(frame)
        if row_count < 1:
            raise ValueError("dataset must contain at least one row")
        original_timestamp = frame[spec.timestamp_column]
        if pd.api.types.is_numeric_dtype(original_timestamp.dtype):
            raise ValueError(
                "numeric timestamps are ambiguous; convert them to ISO date-times before Studio import"
            )
        parsed = pd.to_datetime(original_timestamp, errors="coerce")
        invalid_timestamp_mask = parsed.isna()
        valid = frame.loc[~invalid_timestamp_mask].copy()
        valid_timestamps = parsed.loc[~invalid_timestamp_mask]
        if getattr(valid_timestamps.dt, "tz", None) is None:
            try:
                valid_timestamps = valid_timestamps.dt.tz_localize(spec.timezone, ambiguous="NaT", nonexistent="NaT")
            except (TypeError, ValueError) as exc:
                raise ValueError(f"timestamps cannot be localized unambiguously to {spec.timezone}: {exc}") from exc
        valid["timestamp"] = valid_timestamps.dt.tz_convert("UTC")
        localization_invalid = valid["timestamp"].isna()
        invalid_timestamp_count = int(invalid_timestamp_mask.sum() + localization_invalid.sum())
        valid = valid.loc[~localization_invalid].copy()
        if spec.timestamp_semantics == "bar_close":
            valid["timestamp"] = valid["timestamp"] - _timeframe_delta(spec.timeframe)

        canonical = pd.DataFrame(
            {
                "timestamp": valid["timestamp"],
                "open": pd.to_numeric(valid[spec.open_column], errors="coerce"),
                "high": pd.to_numeric(valid[spec.high_column], errors="coerce"),
                "low": pd.to_numeric(valid[spec.low_column], errors="coerce"),
                "close": pd.to_numeric(valid[spec.close_column], errors="coerce"),
                "volume": pd.to_numeric(valid[spec.volume_column], errors="coerce"),
            }
        )
        if spec.contract_column:
            canonical["contract_symbol"] = (
                valid[spec.contract_column].astype("string").str.strip().replace("", pd.NA)
            )
        numeric_values = canonical[["open", "high", "low", "close", "volume"]]
        numeric_missing = numeric_values.isna().any(axis=1)
        non_finite = pd.Series(
            ~np.isfinite(numeric_values.to_numpy(dtype=float)).all(axis=1),
            index=canonical.index,
        )
        invalid_ohlc = numeric_missing | non_finite
        invalid_ohlc |= canonical["high"] < canonical[["open", "close", "low"]].max(axis=1)
        invalid_ohlc |= canonical["low"] > canonical[["open", "close", "high"]].min(axis=1)
        invalid_ohlc |= (canonical[["open", "high", "low", "close"]] <= 0).any(axis=1)
        invalid_ohlc |= canonical["volume"] < 0
        key_columns = ["timestamp", *(["contract_symbol"] if "contract_symbol" in canonical else [])]
        duplicate_count = int(canonical.duplicated(key_columns, keep=False).sum())
        order_group = (
            canonical["contract_symbol"]
            if "contract_symbol" in canonical
            else pd.Series("all", index=canonical.index)
        )
        out_of_order_count = int(
            canonical.assign(_group=order_group)
            .groupby("_group", dropna=False)["timestamp"]
            .transform(lambda values: values.diff().dt.total_seconds().lt(0))
            .sum()
        )
        gap_count = _gap_count(canonical, spec.timeframe, spec.exchange_timezone)
        dropped_row_count = invalid_timestamp_count
        extra_columns = sorted(set(frame.columns) - required)
        contract_missing_count = (
            int(canonical["contract_symbol"].isna().sum()) if "contract_symbol" in canonical else 0
        )
        contract_count = (
            int(canonical["contract_symbol"].dropna().nunique()) if "contract_symbol" in canonical else 1
        )
        cadence_invalid = _cadence_violation_mask(canonical, spec.timeframe)
        cadence_violation_count = int(cadence_invalid.sum())

        quality_notes: list[str] = []
        if invalid_timestamp_count:
            quality_notes.append(f"{invalid_timestamp_count} row(s) have invalid or ambiguous timestamps")
        if int(invalid_ohlc.sum()):
            quality_notes.append(f"{int(invalid_ohlc.sum())} row(s) violate numeric OHLCV constraints")
        if duplicate_count:
            quality_notes.append(f"{duplicate_count} row(s) have duplicate timestamp/contract keys")
        if out_of_order_count:
            quality_notes.append(f"{out_of_order_count} row(s) are out of timestamp order")
        if gap_count:
            quality_notes.append(f"{gap_count} interval gap(s) require researcher review")
        if extra_columns:
            quality_notes.append(
                "Uncertified feature columns were retained only in quarantine and are unavailable to strategies: "
                + ", ".join(extra_columns)
            )
        if contract_missing_count:
            quality_notes.append(f"{contract_missing_count} row(s) have a missing mapped contract value")
        if cadence_violation_count:
            quality_notes.append(
                f"{cadence_violation_count} row(s) are misaligned or overlap the declared {spec.timeframe} cadence"
            )
        roll_unresolved = spec.contract_column is None and not spec.single_contract_confirmed
        if roll_unresolved:
            quality_notes.append(
                "Contract/roll lineage is unresolved: map a contract column or explicitly confirm a single-contract file"
            )
        roll_policy_mismatch = spec.roll_policy == "single_contract" and contract_count != 1
        if roll_policy_mismatch:
            quality_notes.append(
                f"Roll policy {spec.roll_policy!r} is incompatible with {contract_count} preserved contract(s)"
            )
        hard_errors = (
            invalid_timestamp_count
            + int(invalid_ohlc.sum())
            + duplicate_count
            + out_of_order_count
            + contract_missing_count
            + cadence_violation_count
            + int(roll_policy_mismatch)
        )
        verdict = "FAIL" if hard_errors else ("NEEDS MANUAL REVIEW" if gap_count or roll_unresolved else "PASS")

        normalized_roll_calendar: pd.DataFrame | None = None
        if spec.roll_policy == "explicit_roll_calendar":
            source_calendar = Path(str(spec.roll_calendar_path)).expanduser().resolve()
            if not source_calendar.is_file():
                raise FileNotFoundError(f"roll calendar is missing: {source_calendar}")
            calendar_source_hash = _sha256(source_calendar)
            self._quarantine(
                source_calendar,
                spec.dataset_id,
                calendar_source_hash,
                category="roll-calendar",
            )
            normalized_roll_calendar = _validated_roll_calendar(
                source_calendar,
                canonical,
                exchange_timezone=spec.exchange_timezone,
            )

        staging = self.dataset_root / f".{spec.dataset_id}.{uuid4().hex}.staging"
        staging.mkdir(parents=True, exist_ok=False)
        canonical_path = staging / ("bars.csv" if suffix == ".csv" else "bars.parquet")
        # Invalid OHLC rows remain present and explicitly flagged.  A FAIL manifest
        # prevents their use; the source quarantine preserves every original row.
        canonical["timeframe_minutes"] = _timeframe_delta(spec.timeframe) / pd.Timedelta(minutes=1)
        canonical["row_quality_valid"] = ~(invalid_ohlc | cadence_invalid)
        if suffix == ".csv":
            canonical.to_csv(canonical_path, index=False)
        else:
            canonical.to_parquet(canonical_path, index=False)
        roll_calendar_path: Path | None = None
        roll_calendar_sha256: str | None = None
        if normalized_roll_calendar is not None:
            roll_calendar_path = staging / "roll_calendar.csv"
            normalized_roll_calendar.to_csv(roll_calendar_path, index=False)
            roll_calendar_sha256 = _sha256(roll_calendar_path)
        manifest = DatasetManifestV1(
            dataset_id=spec.dataset_id,
            source="csv" if suffix == ".csv" else "parquet",
            path=str((destination / canonical_path.name).relative_to(self.project_root)),
            symbol=spec.symbol,
            timeframe=spec.timeframe,
            timezone=spec.timezone,
            exchange_timezone=spec.exchange_timezone,
            timestamp_semantics="bar_open",
            source_timestamp_semantics=spec.timestamp_semantics,
            source_sha256=source_hash,
            canonical_sha256=_sha256(canonical_path),
            coverage_start=str(canonical["timestamp"].min()),
            coverage_end=str(canonical["timestamp"].max()),
            roll_policy=spec.roll_policy,
            continuous_contract=("none" if spec.roll_policy == "single_contract" else "explicit_roll_calendar"),
            contract_column="contract_symbol" if "contract_symbol" in canonical else None,
            source_contract_column=spec.contract_column,
            contract_count=contract_count,
            roll_calendar=(
                str((destination / "roll_calendar.csv").relative_to(self.project_root))
                if roll_calendar_path is not None
                else None
            ),
            roll_calendar_sha256=roll_calendar_sha256,
            transformations=[
                "mapped user-selected columns to timestamp/OHLCV/contract",
                f"interpreted source timestamps as {spec.timestamp_semantics} in {spec.timezone}",
                "normalized valid timestamps to canonical bar-open UTC timestamps",
                "coerced OHLCV to numeric with invalid rows flagged",
            ],
            row_count=row_count,
            dropped_row_count=dropped_row_count,
            gap_count=gap_count,
            duplicate_count=duplicate_count,
            out_of_order_count=out_of_order_count,
            invalid_ohlc_count=int(invalid_ohlc.sum()),
            cadence_violation_count=cadence_violation_count,
            certified_features=[],
            quality_verdict=verdict,
            quality_notes=quality_notes,
        )
        manifest_path = staging / "dataset_manifest.json"
        manifest_path.write_text(
            json.dumps(manifest.model_dump(mode="json", by_alias=True), indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        destination.parent.mkdir(parents=True, exist_ok=True)
        staging.replace(destination)
        return DataImportResult(
            manifest=manifest,
            manifest_path=destination / manifest_path.name,
            canonical_path=destination / canonical_path.name,
            quarantined_path=quarantined,
            roll_calendar_path=(destination / "roll_calendar.csv") if roll_calendar_path is not None else None,
        )

    def _quarantine(
        self,
        source: Path,
        dataset_id: str,
        source_hash: str,
        *,
        category: str,
    ) -> Path:
        folder = (
            self.quarantine_root
            / dataset_id
            / f"{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}-{uuid4().hex[:8]}"
            / category
        )
        folder.mkdir(parents=True, exist_ok=False)
        target = folder / source.name
        shutil.copy2(source, target)
        if _sha256(target) != source_hash:
            raise RuntimeError("quarantined attachment hash does not match source")
        return target


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _validated_roll_calendar(
    path: Path,
    canonical: pd.DataFrame,
    *,
    exchange_timezone: str,
) -> pd.DataFrame:
    if path.suffix.lower() != ".csv":
        raise ValueError("Studio roll calendars must be CSV files")
    calendar = pd.read_csv(path)
    required = {"start_timestamp", "contract_symbol"}
    missing = sorted(required - set(calendar.columns))
    if missing:
        raise ValueError(f"roll calendar is missing columns: {', '.join(missing)}")
    if calendar.empty:
        raise ValueError("roll calendar must contain at least one row")
    if pd.api.types.is_numeric_dtype(calendar["start_timestamp"].dtype):
        raise ValueError("numeric roll-calendar timestamps are ambiguous")
    timestamps = pd.to_datetime(calendar["start_timestamp"], errors="coerce")
    if timestamps.isna().any():
        raise ValueError("roll calendar contains invalid start_timestamp values")
    if getattr(timestamps.dt, "tz", None) is None:
        timestamps = timestamps.dt.tz_localize(exchange_timezone, ambiguous="NaT", nonexistent="NaT")
    if timestamps.isna().any():
        raise ValueError("roll calendar contains ambiguous or nonexistent local timestamps")
    normalized = pd.DataFrame(
        {
            "start_timestamp": timestamps.dt.tz_convert("UTC"),
            "contract_symbol": calendar["contract_symbol"].astype("string").str.strip().replace("", pd.NA),
        }
    )
    if normalized["contract_symbol"].isna().any():
        raise ValueError("roll calendar contains a missing contract_symbol")
    if normalized["start_timestamp"].duplicated().any():
        raise ValueError("roll calendar contains duplicate start_timestamp values")
    normalized = normalized.sort_values("start_timestamp").reset_index(drop=True)
    available_contracts = set(canonical["contract_symbol"].dropna().astype(str))
    unknown = sorted(set(normalized["contract_symbol"].astype(str)) - available_contracts)
    if unknown:
        raise ValueError("roll calendar references contracts absent from the bars: " + ", ".join(unknown))

    timestamps_to_cover = canonical[["timestamp"]].drop_duplicates().sort_values("timestamp")
    mapped = pd.merge_asof(
        timestamps_to_cover,
        normalized.rename(columns={"contract_symbol": "active_contract_symbol"}),
        left_on="timestamp",
        right_on="start_timestamp",
        direction="backward",
    )
    if mapped["active_contract_symbol"].isna().any():
        first = mapped.loc[mapped["active_contract_symbol"].isna(), "timestamp"].min()
        raise ValueError(f"roll calendar does not cover bars beginning at {first}")
    present = mapped.merge(
        canonical[["timestamp", "contract_symbol"]].drop_duplicates(),
        left_on=["timestamp", "active_contract_symbol"],
        right_on=["timestamp", "contract_symbol"],
        how="left",
    )
    if present["contract_symbol"].isna().any():
        first = present.loc[present["contract_symbol"].isna(), "timestamp"].min()
        raise ValueError(f"active contract from roll calendar has no bar at {first}")
    return normalized


def _gap_count(frame: pd.DataFrame, timeframe: str, exchange_timezone: str) -> int:
    number = int(timeframe[:-1])
    unit = timeframe[-1]
    seconds = number * {"m": 60, "h": 3600, "d": 86400}[unit]
    groups = (
        frame.groupby("contract_symbol", dropna=False)
        if "contract_symbol" in frame
        else [("all", frame)]
    )
    count = 0
    for _name, values in groups:
        timestamps = values["timestamp"].sort_values()
        diffs = timestamps.diff().dt.total_seconds()
        if unit == "d":
            count += int((diffs > seconds * 1.5).sum())
        else:
            local = timestamps.dt.tz_convert(exchange_timezone)
            same_session_date = local.dt.date.eq(local.dt.date.shift(1))
            count += int(((diffs > seconds * 1.5) & same_session_date).sum())
            # Overnight/weekend closures are not bar gaps, but an entirely absent
            # business date is unresolved without an exchange holiday calendar.
            # Count it so long outages cannot disappear behind the old >12h filter.
            unique_dates = pd.DatetimeIndex(pd.Series(local.dt.date).drop_duplicates())
            for previous, current in zip(unique_dates[:-1], unique_dates[1:], strict=False):
                between = pd.bdate_range(previous + pd.Timedelta(days=1), current - pd.Timedelta(days=1))
                count += len(between)
    return count


def _cadence_violation_mask(frame: pd.DataFrame, timeframe: str) -> pd.Series:
    cadence = _timeframe_delta(timeframe)
    mask = pd.Series(False, index=frame.index)
    cadence_ns = int(cadence.value)
    aligned = frame["timestamp"].astype("int64").mod(cadence_ns).eq(0)
    mask |= ~aligned
    groups = frame.groupby("contract_symbol", dropna=False) if "contract_symbol" in frame else [("all", frame)]
    for _name, values in groups:
        differences = values["timestamp"].diff()
        overlap = differences.notna() & differences.gt(pd.Timedelta(0)) & differences.lt(cadence)
        mask.loc[values.index] |= overlap
    return mask


def _timeframe_delta(timeframe: str) -> pd.Timedelta:
    number = int(timeframe[:-1])
    unit = timeframe[-1]
    return pd.Timedelta(seconds=number * {"m": 60, "h": 3600, "d": 86400}[unit])


__all__ = ["DataImportResult", "DataImportSpec", "DatasetImporter"]
