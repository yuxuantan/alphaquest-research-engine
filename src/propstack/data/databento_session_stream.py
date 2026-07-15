from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta
import json
import shutil
import tempfile
import zipfile
from pathlib import Path
from zoneinfo import ZoneInfo

import databento as db
import numpy as np
import pandas as pd


ET = ZoneInfo("America/New_York")


@dataclass(frozen=True)
class RthSummary:
    session_date: date
    contract_symbol: str
    high: float
    low: float
    close: float


@dataclass(frozen=True)
class DatabentoTradeSession:
    session_date: date
    contract_symbol: str
    previous_rth: RthSummary | None
    overnight_high: float | None
    overnight_low: float | None
    events: pd.DataFrame

    @property
    def event_replay_metadata(self) -> dict[str, object]:
        """Causal session facts safe to expose without the future event frame."""

        return {
            "previous_rth": self.previous_rth,
            "overnight_high": self.overnight_high,
            "overnight_low": self.overnight_low,
        }


def iter_databento_trade_sessions(
    archive_path: str | Path,
    roll_calendar_path: str | Path,
    *,
    start_date: str | date,
    end_date: str | date,
    root_symbol: str = "ES",
    reset_previous_levels_on_roll: bool = True,
):
    """Yield active-contract RTH trade sessions from a full-day Databento ZIP.

    The ZIP is read one UTC day at a time. Only the selected active outright is
    retained. Previous-RTH and overnight levels are therefore derived from the
    same Databento trade-message source as the 09:30-11:00 replay.
    """

    archive_path = Path(archive_path)
    start = pd.Timestamp(start_date).date()
    end = pd.Timestamp(end_date).date()
    active_contract = _active_contract_lookup(roll_calendar_path)
    overnight: dict[date, list[float]] = {}
    rth: dict[date, RthSummary] = {}
    previous_rth_dates: list[date] = []

    with zipfile.ZipFile(archive_path) as archive:
        metadata = json.loads(archive.read("metadata.json"))
        partial_symbols = {str(value) for value in metadata.get("partial", [])}
        members = sorted(name for name in archive.namelist() if name.endswith(".trades.dbn.zst"))
        for member in members:
            utc_date = _member_date(member)
            if utc_date is None or utc_date < start - timedelta(days=2) or utc_date > end:
                continue
            frame = _read_member(archive, member)
            if frame.empty:
                continue
            local_timestamp = pd.to_datetime(frame["ts_event"], utc=True).dt.tz_convert(ET)
            local_date = local_timestamp.dt.date
            evening = local_timestamp.dt.time >= pd.Timestamp("18:00:00").time()
            assigned_session = local_date.where(~evening, (local_timestamp + pd.Timedelta(days=1)).dt.date)
            frame = frame.assign(
                timestamp=local_timestamp,
                session_date=assigned_session,
                _source_ordinal=np.arange(len(frame), dtype=np.int64),
            )

            for session_date in sorted(set(frame["session_date"])):
                if session_date < start or session_date > end:
                    continue
                contract = active_contract(session_date)
                if contract is None:
                    continue
                if contract in partial_symbols:
                    raise ValueError(f"Databento marks active contract {contract} partial for {session_date}.")
                session_rows = frame.loc[
                    frame["session_date"].eq(session_date) & frame["symbol"].astype(str).eq(contract)
                ].copy()
                if session_rows.empty:
                    continue
                time_values = session_rows["timestamp"].dt.time
                overnight_mask = (time_values >= pd.Timestamp("18:00:00").time()) | (
                    time_values < pd.Timestamp("09:30:00").time()
                )
                if bool(overnight_mask.any()):
                    values = pd.to_numeric(session_rows.loc[overnight_mask, "price"], errors="raise")
                    bounds = overnight.setdefault(session_date, [float("inf"), float("-inf")])
                    bounds[0] = min(bounds[0], float(values.min()))
                    bounds[1] = max(bounds[1], float(values.max()))

            current_session = utc_date
            if current_session < start or current_session > end:
                continue
            contract = active_contract(current_session)
            if contract is None:
                continue
            current = frame.loc[
                frame["session_date"].eq(current_session) & frame["symbol"].astype(str).eq(contract)
            ].sort_values(["timestamp", "_source_ordinal"], kind="mergesort").copy()
            if current.empty:
                continue
            time_values = current["timestamp"].dt.time
            rth_mask = (time_values >= pd.Timestamp("09:30:00").time()) & (
                time_values < pd.Timestamp("16:00:00").time()
            )
            if not bool(rth_mask.any()):
                continue
            rth_rows = current.loc[rth_mask]
            prices = pd.to_numeric(rth_rows["price"], errors="raise")
            summary = RthSummary(
                session_date=current_session,
                contract_symbol=contract,
                high=float(prices.max()),
                low=float(prices.min()),
                close=float(prices.iloc[-1]),
            )
            prior = _latest_previous_rth(previous_rth_dates, rth, current_session)
            if reset_previous_levels_on_roll and prior is not None and prior.contract_symbol != contract:
                prior = None
            entry_mask = (time_values >= pd.Timestamp("09:30:00").time()) & (
                time_values < pd.Timestamp("11:00:00").time()
            )
            events = _normalized_events(current.loc[entry_mask], root_symbol, contract)
            rth[current_session] = summary
            previous_rth_dates.append(current_session)
            if events.empty:
                continue
            overnight_bounds = overnight.get(current_session)
            yield DatabentoTradeSession(
                session_date=current_session,
                contract_symbol=contract,
                previous_rth=prior,
                overnight_high=overnight_bounds[1] if overnight_bounds else None,
                overnight_low=overnight_bounds[0] if overnight_bounds else None,
                events=events,
            )


def _read_member(archive: zipfile.ZipFile, member: str) -> pd.DataFrame:
    with tempfile.NamedTemporaryFile(suffix=".dbn.zst") as temporary:
        with archive.open(member) as source:
            shutil.copyfileobj(source, temporary)
        temporary.flush()
        store = db.DBNStore.from_file(temporary.name)
        frame = store.to_df().reset_index()
    if frame.empty:
        return frame
    return frame


def _normalized_events(frame: pd.DataFrame, root_symbol: str, contract: str) -> pd.DataFrame:
    if frame.empty:
        return pd.DataFrame()
    side = frame["side"].astype(str)
    price = pd.to_numeric(frame["price"], errors="raise").to_numpy(dtype=float)
    size = pd.to_numeric(frame["size"], errors="raise").to_numpy(dtype=np.int64)
    sequence = pd.to_numeric(frame.get("sequence", pd.Series(np.arange(len(frame)))), errors="raise").to_numpy(
        dtype=np.int64
    )
    out = pd.DataFrame(
        {
            "timestamp": pd.to_datetime(frame["timestamp"]).to_numpy(),
            "source_ordinal": pd.to_numeric(frame["_source_ordinal"], errors="raise").to_numpy(dtype=np.int64),
            "sequence": sequence,
            "symbol": root_symbol,
            "contract_symbol": contract,
            "price": price,
            "size": size,
            "side": side.to_numpy(),
            "signed_size": np.where(side.eq("B"), size, np.where(side.eq("A"), -size, 0)),
            "aggressor_classified": side.isin(["A", "B"]).to_numpy(),
        }
    )
    out["timestamp"] = pd.to_datetime(out["timestamp"], utc=True).dt.tz_convert(ET)
    return out.sort_values(["timestamp", "source_ordinal"], kind="mergesort").reset_index(drop=True)


def _active_contract_lookup(path: str | Path):
    frame = pd.read_csv(path)
    if not {"start_timestamp", "contract_symbol"}.issubset(frame.columns):
        raise ValueError("Roll calendar must contain start_timestamp and contract_symbol.")
    starts = pd.to_datetime(frame["start_timestamp"], utc=True).dt.tz_convert(ET)
    dates = np.asarray(starts.dt.date)
    contracts = frame["contract_symbol"].astype(str).map(_normalize_contract).to_numpy()

    def lookup(session_date: date) -> str | None:
        index = int(np.searchsorted(dates, session_date, side="right") - 1)
        return None if index < 0 else str(contracts[index])

    return lookup


def _normalize_contract(value: str) -> str:
    value = str(value).strip().upper()
    digits = "".join(char for char in value if char.isdigit())
    prefix = value[: len(value) - len(digits)]
    if len(digits) == 2:
        digits = digits[-1]
    if len(digits) != 1:
        raise ValueError(f"Unexpected outright contract symbol: {value!r}")
    return f"{prefix}{digits}"


def _latest_previous_rth(
    ordered_dates: list[date],
    summaries: dict[date, RthSummary],
    current: date,
) -> RthSummary | None:
    for candidate in reversed(ordered_dates):
        if candidate < current:
            return summaries[candidate]
    return None


def _member_date(member: str) -> date | None:
    token = Path(member).name.split(".", maxsplit=1)[0].rsplit("-", maxsplit=1)[-1]
    if len(token) != 8 or not token.isdigit():
        return None
    return pd.Timestamp(f"{token[:4]}-{token[4:6]}-{token[6:]}").date()
