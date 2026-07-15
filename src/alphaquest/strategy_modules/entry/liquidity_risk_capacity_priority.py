from __future__ import annotations

from pathlib import Path
import math

import pandas as pd

from alphaquest.strategy_modules.entry.base import Signal
from alphaquest.utils.time import parse_time


class LiquidityRiskCapacityPriorityEntry:
    name = "liquidity_risk_capacity_priority"

    def __init__(self, params: dict):
        self.params = params
        self.feature_file = Path(params.get("feature_file", "data/external/liquidity_risk_capacity_features.csv"))
        self.direction = str(params.get("direction", "long")).lower()
        self.bar_interval_minutes = float(params.get("bar_interval_minutes", 5))
        self.max_trades_per_day = int(params.get("max_trades_per_day", 1))
        self.priority_order = _parse_priority_order(
            params.get("priority_order", ["cftc_high", "nyfed_rrp", "cftc_broad", "cboe_vx"])
        )

        self.cftc_feature_name = str(params.get("cftc_feature_name", "SPX_open_interest_chg13"))
        self.rrp_feature_name = str(params.get("rrp_feature_name", "reverserepo_total_bil_diff5_z504"))
        self.vx_feature_name = str(params.get("vx_feature_name", "vx_z63"))

        self.cftc_high_threshold = float(params.get("cftc_high_threshold", 98748.0))
        self.cftc_broad_threshold = float(params.get("cftc_broad_threshold", 47442.0))
        self.rrp_threshold = float(params.get("rrp_threshold", 0.5))
        self.vx_threshold = float(params.get("vx_threshold", -1.275))

        self.cftc_high_entry_time = parse_time(params.get("cftc_high_entry_time", "09:35:00"))
        self.cftc_broad_entry_time = parse_time(params.get("cftc_broad_entry_time", "11:00:00"))
        self.rrp_entry_time = parse_time(params.get("rrp_entry_time", "14:30:00"))
        self.vx_entry_time = parse_time(params.get("vx_entry_time", "13:30:00"))

        self.cftc_high_flatten_time = parse_time(params.get("cftc_high_flatten_time", "15:30:00"))
        self.cftc_broad_flatten_time = parse_time(params.get("cftc_broad_flatten_time", "15:30:00"))
        self.rrp_flatten_time = parse_time(params.get("rrp_flatten_time", "15:30:00"))
        self.vx_flatten_time = parse_time(params.get("vx_flatten_time", "15:45:00"))

        self.cftc_high_stop_pct = float(params.get("cftc_high_stop_pct", 0.008))
        self.cftc_broad_stop_pct = float(params.get("cftc_broad_stop_pct", 0.006))
        self.rrp_stop_pct = float(params.get("rrp_stop_pct", 0.012))
        self.vx_stop_pct = float(params.get("vx_stop_pct", 0.012))
        self.cftc_high_target_r_multiple = float(params.get("cftc_high_target_r_multiple", 2.0))
        self.cftc_broad_target_r_multiple = float(params.get("cftc_broad_target_r_multiple", 4.0))
        self.rrp_target_r_multiple = float(params.get("rrp_target_r_multiple", 1.5))
        self.vx_target_r_multiple = float(params.get("vx_target_r_multiple", 3.0))

        self.state_by_day: dict[pd.Timestamp, dict] = {}
        self.features_by_date = _load_feature_rows(
            self.feature_file,
            [self.cftc_feature_name, self.rrp_feature_name, self.vx_feature_name],
        )
        if self.direction not in {"long", "short"}:
            raise ValueError("liquidity_risk_capacity_priority direction must be long or short.")
        if self.bar_interval_minutes <= 0:
            raise ValueError("bar_interval_minutes must be greater than 0.")
        for key in ["cftc_high", "cftc_broad", "nyfed_rrp", "cboe_vx"]:
            stop_pct, target_r = self._risk_params(key)
            if stop_pct <= 0 or target_r <= 0:
                raise ValueError(f"{key} stop_pct and target_r_multiple must be greater than 0.")

    def _state(self, session_date: pd.Timestamp) -> dict:
        return self.state_by_day.setdefault(session_date, self._initial_state(session_date))

    def _initial_state(self, session_date: pd.Timestamp) -> dict:
        row = self.features_by_date.get(session_date)
        selected = None
        if row:
            for key in self.priority_order:
                candidate = self._candidate(key, row)
                if candidate is not None:
                    selected = candidate
                    break
        return {
            "signaled": False,
            "selected": selected,
        }

    def _candidate(self, key: str, row: dict) -> dict | None:
        if key == "cftc_high":
            return self._threshold_candidate(
                key=key,
                source="cftc_tff",
                feature_name=self.cftc_feature_name,
                feature_value=row.get(self.cftc_feature_name),
                operator=">=",
                threshold=self.cftc_high_threshold,
                entry_time=self.cftc_high_entry_time,
                flatten_time=self.cftc_high_flatten_time,
                availability_rule="Tuesday CFTC TFF positions traded no earlier than following Monday RTH.",
            )
        if key == "cftc_broad":
            return self._threshold_candidate(
                key=key,
                source="cftc_tff",
                feature_name=self.cftc_feature_name,
                feature_value=row.get(self.cftc_feature_name),
                operator=">=",
                threshold=self.cftc_broad_threshold,
                entry_time=self.cftc_broad_entry_time,
                flatten_time=self.cftc_broad_flatten_time,
                availability_rule="Tuesday CFTC TFF positions traded no earlier than following Monday RTH.",
            )
        if key == "nyfed_rrp":
            return self._threshold_candidate(
                key=key,
                source="nyfed_rrp",
                feature_name=self.rrp_feature_name,
                feature_value=row.get(self.rrp_feature_name),
                operator=">=",
                threshold=self.rrp_threshold,
                entry_time=self.rrp_entry_time,
                flatten_time=self.rrp_flatten_time,
                availability_rule="NY Fed RRP operation result shifted by one business day before ES eligibility.",
            )
        if key == "cboe_vx":
            return self._threshold_candidate(
                key=key,
                source="cboe_vx_activity",
                feature_name=self.vx_feature_name,
                feature_value=row.get(self.vx_feature_name),
                operator="<=",
                threshold=self.vx_threshold,
                entry_time=self.vx_entry_time,
                flatten_time=self.vx_flatten_time,
                availability_rule="Cboe/CFE daily futures activity shifted by one ES session before eligibility.",
            )
        raise ValueError(f"Unknown liquidity priority key: {key}")

    def _threshold_candidate(
        self,
        *,
        key: str,
        source: str,
        feature_name: str,
        feature_value,
        operator: str,
        threshold: float,
        entry_time,
        flatten_time,
        availability_rule: str,
    ) -> dict | None:
        value = _finite_float(feature_value)
        if value is None:
            return None
        active = value >= threshold if operator == ">=" else value <= threshold
        if not active:
            return None
        stop_pct, target_r = self._risk_params(key)
        return {
            "key": key,
            "source": source,
            "feature_name": feature_name,
            "feature_value": value,
            "operator": operator,
            "threshold": threshold,
            "entry_time": entry_time,
            "flatten_time": flatten_time,
            "availability_rule": availability_rule,
            "stop_pct": stop_pct,
            "target_r_multiple": target_r,
        }

    def _risk_params(self, key: str) -> tuple[float, float]:
        if key == "cftc_high":
            return self.cftc_high_stop_pct, self.cftc_high_target_r_multiple
        if key == "cftc_broad":
            return self.cftc_broad_stop_pct, self.cftc_broad_target_r_multiple
        if key == "nyfed_rrp":
            return self.rrp_stop_pct, self.rrp_target_r_multiple
        if key == "cboe_vx":
            return self.vx_stop_pct, self.vx_target_r_multiple
        raise ValueError(f"Unknown liquidity priority key: {key}")

    def on_bar_close(self, bar: pd.Series, trades_today: int = 0) -> Signal | None:
        if not bool(bar.get("is_rth", False)):
            return None
        if trades_today >= self.max_trades_per_day:
            return None

        session_date = pd.Timestamp(bar["session_date"]).normalize()
        state = self._state(session_date)
        selected = state["selected"]
        if state["signaled"] or selected is None:
            return None

        timestamp = pd.Timestamp(bar["timestamp"])
        bar_close = timestamp + pd.Timedelta(minutes=self.bar_interval_minutes)
        if bar_close.time() != selected["entry_time"]:
            return None

        state["signaled"] = True
        priority_label = ">".join(self.priority_order)
        flatten_label = selected["flatten_time"].strftime("%H:%M:%S")
        report_fields = {
            "academic_source_key": "brunnermeier_pedersen_2009_market_liquidity_funding_liquidity",
            "external_dataset": "cftc_tff_nyfed_rrp_cboe_cfe_vx_activity",
            "external_feature_file": str(self.feature_file),
            "selected_liquidity_leg": selected["key"],
            "selected_liquidity_source": selected["source"],
            "liquidity_priority_order": priority_label,
            "feature_name": selected["feature_name"],
            "feature_operator": selected["operator"],
            "feature_threshold": selected["threshold"],
            "feature_value": selected["feature_value"],
            "feature_trade_date": session_date.date().isoformat(),
            "feature_availability_rule": selected["availability_rule"],
            "signal_stop_pct": selected["stop_pct"],
            "signal_target_r_multiple": selected["target_r_multiple"],
            "signal_flatten_time": flatten_label,
            "signal_timestamp": bar_close,
        }
        return Signal(
            direction=self.direction,
            level_type=f"liquidity_risk_capacity_{selected['key']}",
            swept_level=float(bar["close"]),
            sweep_timestamp=bar_close,
            sweep_high=float(bar["high"]),
            sweep_low=float(bar["low"]),
            reclaim_timestamp=bar_close,
            metadata={
                "confirmation_high": float(bar["high"]),
                "confirmation_low": float(bar["low"]),
                "confirmation_close": float(bar["close"]),
                "selected_liquidity_leg": selected["key"],
                "selected_liquidity_source": selected["source"],
                "feature_name": selected["feature_name"],
                "feature_value": selected["feature_value"],
                "stop_pct": selected["stop_pct"],
                "target_r_multiple": selected["target_r_multiple"],
                "flatten_time": flatten_label,
            },
            report_fields=report_fields,
        )


def _load_feature_rows(path: Path, required_columns: list[str]) -> dict[pd.Timestamp, dict]:
    df = pd.read_csv(path, parse_dates=["trade_date"])
    missing = {"trade_date", *required_columns} - set(df.columns)
    if missing:
        raise ValueError(f"Liquidity feature file is missing column(s): {sorted(missing)}")
    df = df.sort_values("trade_date").drop_duplicates("trade_date", keep="last")
    rows: dict[pd.Timestamp, dict] = {}
    for _, row in df.iterrows():
        trade_date = pd.Timestamp(row["trade_date"]).normalize()
        rows[trade_date] = {column: row[column] for column in required_columns}
    return rows


def _parse_priority_order(value) -> list[str]:
    if isinstance(value, str):
        raw = value.replace(">", ",").split(",")
    else:
        raw = list(value)
    out = [str(item).strip() for item in raw if str(item).strip()]
    allowed = {"cftc_high", "nyfed_rrp", "cftc_broad", "cboe_vx"}
    unknown = sorted(set(out) - allowed)
    if unknown:
        raise ValueError(f"Unknown liquidity priority key(s): {unknown}")
    if not out:
        raise ValueError("priority_order must include at least one liquidity priority key.")
    return out


def _finite_float(value) -> float | None:
    try:
        out = float(value)
    except (TypeError, ValueError):
        return None
    return out if math.isfinite(out) else None
