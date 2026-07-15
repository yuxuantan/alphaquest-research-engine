from __future__ import annotations

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
DATABENTO_PRICE_PATH_SEMANTICS = "databento_trade_message_v1"


def load_databento_zip_execution_data(
    config: dict,
    *,
    date_bounds: dict | None = None,
) -> pd.DataFrame:
    """Load active-contract trade messages directly from a Databento job ZIP."""

    archive_path = Path(config["archive"])
    manifest_path = Path(
        config.get(
            "contract_manifest",
            "data/reference/ES/event_quality/sierra_event_capabilities_0930_1100.csv",
        )
    )
    root_symbol = str(config.get("root_symbol", config.get("symbol", "ES")))
    rth_start = str(config.get("rth_start", "09:30:00"))
    rth_end = str(config.get("rth_end", "11:00:00"))
    start_date, end_date = _date_bounds(date_bounds)
    contracts = pd.read_csv(
        manifest_path, dtype={"session_date": "string", "contract": "string"}
    ).drop_duplicates("session_date", keep="last")
    contracts = contracts.set_index("session_date")["contract"].to_dict()
    parts: list[pd.DataFrame] = []
    loaded_dates: list[str] = []
    blackout_dates: list[str] = []
    with zipfile.ZipFile(archive_path) as archive:
        names = set(archive.namelist())
        metadata = json.loads(archive.read("metadata.json"))
        partial = {str(value) for value in metadata.get("partial", [])}
        members = sorted(name for name in names if name.endswith(".trades.dbn.zst"))
        for member in members:
            session_date = _member_date(member)
            if session_date is None or session_date < start_date or session_date > end_date:
                continue
            contract = contracts.get(session_date)
            if not contract:
                blackout_dates.append(session_date)
                continue
            databento_contract = _databento_symbol(contract)
            if databento_contract in partial:
                raise ValueError(
                    f"Databento marks active contract {databento_contract} partial on {session_date}."
                )
            part = _load_member(
                archive,
                member,
                session_date=session_date,
                databento_contract=databento_contract,
                sierra_contract=contract,
                root_symbol=root_symbol,
                rth_start=rth_start,
                rth_end=rth_end,
            )
            if not part.empty:
                parts.append(part)
                loaded_dates.append(session_date)
    if not parts:
        raise ValueError(
            f"No Databento trade messages found for requested dates {start_date} through {end_date}."
        )
    result = pd.concat(parts, ignore_index=True)
    result = result.sort_values(["timestamp", "source_ordinal"], kind="mergesort").reset_index(drop=True)
    result.attrs["detail_granularity"] = "normalized_trade_event"
    result.attrs["price_path_semantics"] = DATABENTO_PRICE_PATH_SEMANTICS
    result.attrs["source_quality_label"] = (
        "Direct Databento GLBX trades messages, filtered to the governed active contract; not MBO."
    )
    result.attrs["eligible_session_dates"] = loaded_dates
    result.attrs["blackout_session_dates"] = blackout_dates
    result.attrs["timestamp_precision_ns"] = 1
    return result


def _load_member(
    archive: zipfile.ZipFile,
    member: str,
    *,
    session_date: str,
    databento_contract: str,
    sierra_contract: str,
    root_symbol: str,
    rth_start: str,
    rth_end: str,
) -> pd.DataFrame:
    with tempfile.NamedTemporaryFile(suffix=".dbn.zst") as temporary:
        with archive.open(member) as source:
            shutil.copyfileobj(source, temporary)
        temporary.flush()
        store = db.DBNStore.from_file(temporary.name)
        partial = {str(value) for value in store.metadata.partial}
        if databento_contract in partial:
            raise ValueError(f"Databento member {member} marks {databento_contract} partial.")
        frame = store.to_df().reset_index()
    timestamp = pd.to_datetime(frame["ts_event"], utc=True)
    start = pd.Timestamp(f"{session_date} {rth_start}", tz=ET).tz_convert("UTC")
    end = pd.Timestamp(f"{session_date} {rth_end}", tz=ET).tz_convert("UTC")
    mask = frame["symbol"].astype(str).eq(databento_contract) & timestamp.ge(start) & timestamp.lt(end)
    frame = frame.loc[mask].copy()
    if frame.empty:
        return pd.DataFrame()
    event_timestamp = pd.to_datetime(frame["ts_event"], utc=True)
    if not event_timestamp.is_monotonic_increasing:
        raise ValueError(
            f"Databento member {member} has a timestamp inversion in source order."
        )
    side = frame["side"].astype(str)
    if not side.isin(["A", "B"]).all():
        raise ValueError(f"Databento member {member} has neutral/unknown active-contract trade side.")
    size = pd.to_numeric(frame["size"], errors="raise").to_numpy(dtype=np.int64)
    price = pd.to_numeric(frame["price"], errors="raise").to_numpy(dtype=float)
    buy = np.where(side.eq("B"), size, 0)
    sell = np.where(side.eq("A"), size, 0)
    source_ordinal = np.arange(len(frame), dtype=np.int64)
    return pd.DataFrame(
        {
            "timestamp": event_timestamp.dt.tz_convert(ET),
            "symbol": root_symbol,
            "contract_symbol": sierra_contract,
            "open": price,
            "high": price,
            "low": price,
            "close": price,
            "volume": size,
            "signed_volume": buy - sell,
            "buy_volume": buy,
            "sell_volume": sell,
            "trades": 1,
            "num_trades": 1,
            "source_ordinal": source_ordinal,
            "side": side.to_numpy(),
            "component_rows": 1,
            "timestamp_precision_ns": 1,
            "timestamp_uncertainty_ns": 0,
            "quality_capability": "direct_databento_trades",
            "execution_granularity": "normalized_trade_event",
            "price_path_semantics": DATABENTO_PRICE_PATH_SEMANTICS,
        }
    )


def _date_bounds(bounds: dict | None) -> tuple[str, str]:
    if not bounds:
        return "0001-01-01", "9999-12-31"
    start = bounds.get("start_date") or bounds.get("start_timestamp") or "0001-01-01"
    end = bounds.get("end_date") or bounds.get("end_timestamp") or "9999-12-31"
    return str(pd.Timestamp(start).date()), str(pd.Timestamp(end).date())


def _member_date(member: str) -> str | None:
    token = Path(member).name.split(".", maxsplit=1)[0].rsplit("-", maxsplit=1)[-1]
    if len(token) != 8 or not token.isdigit():
        return None
    return f"{token[:4]}-{token[4:6]}-{token[6:]}"


def _databento_symbol(sierra_contract: str) -> str:
    digits = "".join(char for char in sierra_contract if char.isdigit())
    if len(digits) != 2:
        raise ValueError(f"Unexpected Sierra contract symbol: {sierra_contract!r}")
    return f"{sierra_contract[:-2]}{digits[-1]}"
