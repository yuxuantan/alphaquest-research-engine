"""Causal Sierra session adapter for the generic canonical-event runner."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Iterator

import pandas as pd

from alphaquest.data.databento_session_stream import RthSummary
from alphaquest.data.scid_execution import iter_scid_record_execution_sessions


@dataclass(frozen=True)
class SierraTradeSession:
    session_date: date
    contract_symbol: str
    previous_rth: RthSummary | None
    overnight_high: float | None
    overnight_low: float | None
    events: pd.DataFrame

    @property
    def event_replay_metadata(self) -> dict[str, object]:
        return {
            "previous_rth": self.previous_rth,
            "overnight_high": self.overnight_high,
            "overnight_low": self.overnight_low,
            "source_quality_label": (
                "Governed Sierra SCID events reconstructed from FIRST/LAST groups; "
                "prior-RTH and ETH confluences use completed-bar OHLC levels."
            ),
        }


def iter_sierra_trade_sessions(
    execution_config: dict,
    *,
    start_date: str | date,
    end_date: str | date,
) -> Iterator[SierraTradeSession]:
    """Yield Sierra entry-window events with precomputed causal OHLC levels."""

    levels_path = Path(str(execution_config.get("session_levels") or ""))
    if not levels_path.is_file():
        raise FileNotFoundError(f"governed Sierra session-level file is missing: {levels_path}")
    levels = pd.read_parquet(levels_path)
    required_levels = {
        "session_date",
        "contract_symbol",
        "previous_rth_session_date",
        "previous_rth_contract_symbol",
        "previous_rth_high",
        "previous_rth_low",
        "previous_rth_close",
        "overnight_high",
        "overnight_low",
    }
    missing = sorted(required_levels - set(levels.columns))
    if missing:
        raise ValueError(f"Sierra session-level file is missing columns: {missing}")
    levels["session_date"] = pd.to_datetime(levels["session_date"]).dt.date
    levels = levels.set_index("session_date", verify_integrity=True)

    policy = str(execution_config.get("ineligible_session_policy") or "error").lower()
    for session_date_text, part in iter_scid_record_execution_sessions(
        execution_config,
        date_bounds={"start_date": str(start_date), "end_date": str(end_date)},
    ):
        session_date = pd.Timestamp(session_date_text).date()
        if session_date not in levels.index:
            if policy == "blackout":
                continue
            raise ValueError(f"Sierra session {session_date} has no governed prior-RTH/ETH levels")
        level = levels.loc[session_date]
        contract = str(part["contract_symbol"].iloc[0])
        if str(level["contract_symbol"]) != contract:
            raise ValueError(
                f"Sierra session-level contract mismatch on {session_date}: "
                f"{level['contract_symbol']} versus {contract}"
            )
        prior = None
        if pd.notna(level["previous_rth_session_date"]):
            prior = RthSummary(
                session_date=pd.Timestamp(level["previous_rth_session_date"]).date(),
                contract_symbol=str(level["previous_rth_contract_symbol"]),
                high=float(level["previous_rth_high"]),
                low=float(level["previous_rth_low"]),
                close=float(level["previous_rth_close"]),
            )
        canonical = part.rename(
            columns={
                "close": "price",
                "volume": "size",
                "signed_volume": "signed_size",
            }
        )[
            [
                "timestamp",
                "source_ordinal",
                "contract_symbol",
                "price",
                "size",
                "side",
                "signed_size",
            ]
        ].copy()
        yield SierraTradeSession(
            session_date=session_date,
            contract_symbol=contract,
            previous_rth=prior,
            overnight_high=float(level["overnight_high"]),
            overnight_low=float(level["overnight_low"]),
            events=canonical,
        )


__all__ = ["SierraTradeSession", "iter_sierra_trade_sessions"]
