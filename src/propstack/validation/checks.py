"""Consistency checks for validation-dashboard artifacts."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pandas as pd

from propstack.validation.schema import VALIDATION_CHECK_COLUMNS, VALIDATION_CHECKS_FILENAME, normalize_columns

PASS = "PASS"
WARNING = "WARNING"
ERROR = "ERROR"


def run_validation_checks(
    trades: pd.DataFrame,
    condition_snapshots: pd.DataFrame,
    bar_windows: pd.DataFrame,
    tick_windows: pd.DataFrame | None = None,
    exit_audits: pd.DataFrame | None = None,
    metadata: dict[str, Any] | None = None,
) -> pd.DataFrame:
    checker = _ValidationChecker(
        trades=trades,
        conditions=condition_snapshots,
        bars=bar_windows,
        ticks=tick_windows if tick_windows is not None else pd.DataFrame(),
        exits=exit_audits if exit_audits is not None else pd.DataFrame(),
        metadata=metadata or {},
    )
    return checker.run()


def write_validation_checks_report(report: pd.DataFrame, run_dir: str | Path) -> None:
    output_path = Path(run_dir) / VALIDATION_CHECKS_FILENAME
    output_path.parent.mkdir(parents=True, exist_ok=True)
    normalize_columns(report, VALIDATION_CHECK_COLUMNS).to_parquet(output_path, index=False)


def load_validation_checks_report(run_dir: str | Path) -> pd.DataFrame:
    path = Path(run_dir) / VALIDATION_CHECKS_FILENAME
    if not path.exists():
        return pd.DataFrame(columns=VALIDATION_CHECK_COLUMNS)
    return normalize_columns(pd.read_parquet(path), VALIDATION_CHECK_COLUMNS)


class _ValidationChecker:
    def __init__(
        self,
        *,
        trades: pd.DataFrame,
        conditions: pd.DataFrame,
        bars: pd.DataFrame,
        ticks: pd.DataFrame,
        exits: pd.DataFrame,
        metadata: dict[str, Any],
    ) -> None:
        self.trades = trades.copy()
        self.conditions = conditions.copy()
        self.bars = bars.copy()
        self.ticks = ticks.copy()
        self.exits = exits.copy()
        self.metadata = metadata
        self.rows: list[dict[str, Any]] = []
        self._counter = 0

    def run(self) -> pd.DataFrame:
        self._check_trade_ids_unique()
        for _, trade in self.trades.iterrows():
            trade_id = trade.get("trade_id")
            condition = _row_for_trade(self.conditions, trade_id)
            exit_audit = _row_for_trade(self.exits, trade_id)
            bars = _rows_for_trade(self.bars, trade_id)
            ticks = _rows_for_trade(self.ticks, trade_id)

            self._check_trade_identity(trade, condition)
            self._check_time_ordering(trade, condition)
            self._check_price_logic(trade)
            self._check_filters(trade, condition, bars)
            self._check_exits(trade, condition, exit_audit)
            self._check_data_quality(trade, condition, bars, ticks)
        return normalize_columns(pd.DataFrame(self.rows), VALIDATION_CHECK_COLUMNS)

    def _add(
        self,
        *,
        check_name: str,
        category: str,
        status: str,
        description: str,
        trade_id: Any = None,
        expected: Any = None,
        actual: Any = None,
        details: Any = None,
    ) -> None:
        self._counter += 1
        self.rows.append(
            {
                "check_id": f"{category}.{check_name}.{self._counter}",
                "check_name": check_name,
                "category": category,
                "status": status,
                "severity": status,
                "description": description,
                "trade_id": trade_id,
                "expected": _format(expected),
                "actual": _format(actual),
                "details": _format(details),
            }
        )

    def _assert(
        self,
        condition: bool,
        *,
        check_name: str,
        category: str,
        description: str,
        trade_id: Any = None,
        expected: Any = None,
        actual: Any = None,
        fail_status: str = ERROR,
        details: Any = None,
    ) -> None:
        self._add(
            check_name=check_name,
            category=category,
            status=PASS if condition else fail_status,
            description=description,
            trade_id=trade_id,
            expected=expected,
            actual=actual,
            details=details,
        )

    def _check_trade_ids_unique(self) -> None:
        if self.trades.empty or "trade_id" not in self.trades.columns:
            self._add(
                check_name="unique_trade_id",
                category="identity",
                status=ERROR,
                description="Every trade must expose a trade_id column.",
                expected="trade_id column present",
                actual="missing",
            )
            return
        duplicated = self.trades["trade_id"].astype(str).duplicated(keep=False)
        duplicate_ids = sorted(self.trades.loc[duplicated, "trade_id"].astype(str).unique())
        self._assert(
            not duplicate_ids,
            check_name="unique_trade_id",
            category="identity",
            description="Every trade has a unique trade_id.",
            expected="unique trade_id values",
            actual=", ".join(duplicate_ids) if duplicate_ids else "unique",
        )

    def _check_trade_identity(self, trade: pd.Series, condition: pd.Series | None) -> None:
        trade_id = trade.get("trade_id")
        self._assert(
            condition is not None,
            check_name="condition_snapshot_present",
            category="identity",
            description="Every trade has a matching condition snapshot.",
            trade_id=trade_id,
            expected="condition_snapshots.trade_id present",
            actual="present" if condition is not None else "missing",
        )
        required = [
            ("entry_time", "allow_missing_entry_time"),
            ("entry_price", "allow_missing_entry_price"),
            ("stop_price", "allow_missing_stop_price"),
            ("target_price", "allow_missing_target_price"),
        ]
        for field, allow_key in required:
            if _truthy(self.metadata.get(allow_key)) or _truthy(self.metadata.get("allow_missing_trade_prices")):
                continue
            self._assert(
                not _is_missing(trade.get(field)),
                check_name=f"{field}_present",
                category="identity",
                description=f"Trade has required {field}.",
                trade_id=trade_id,
                expected="non-missing",
                actual=trade.get(field),
            )

    def _check_time_ordering(self, trade: pd.Series, condition: pd.Series | None) -> None:
        trade_id = trade.get("trade_id")
        timestamps = {
            "sweep_time": _ts(_lookup(condition, ("sweep_time",))),
            "reclaim_time": _ts(_lookup(condition, ("reclaim_time",))),
            "signal_time": _ts(_first_present(_lookup(condition, ("signal_time",)), _lookup(condition, ("decision_bar_time",)))),
            "entry_time": _ts(trade.get("entry_time")),
            "exit_time": _ts(trade.get("exit_time")),
        }
        pairs = [
            ("sweep_time", "reclaim_time"),
            ("reclaim_time", "signal_time"),
            ("signal_time", "entry_time"),
            ("entry_time", "exit_time"),
        ]
        for earlier, later in pairs:
            if timestamps[earlier] is None or timestamps[later] is None:
                continue
            self._assert(
                timestamps[earlier] <= timestamps[later],
                check_name=f"{earlier}_before_{later}",
                category="time_ordering",
                description=f"{earlier} must be at or before {later}.",
                trade_id=trade_id,
                expected=f"{earlier} <= {later}",
                actual=f"{timestamps[earlier]} > {timestamps[later]}",
            )
        if timestamps["entry_time"] is not None and timestamps["exit_time"] is not None:
            self._assert(
                timestamps["entry_time"] <= timestamps["exit_time"],
                check_name="exit_not_before_entry",
                category="time_ordering",
                description="Exit time is not before entry time.",
                trade_id=trade_id,
                expected="entry_time <= exit_time",
                actual=f"{timestamps['entry_time']} <= {timestamps['exit_time']}",
            )
        if _bar_close_entry(condition, trade, self.metadata):
            decision = _ts(_lookup(condition, ("decision_bar_time",)))
            entry = timestamps["entry_time"]
            if decision is not None and entry is not None:
                self._assert(
                    entry >= decision,
                    check_name="bar_close_entry_not_before_signal_close",
                    category="time_ordering",
                    description="Bar-close signal does not enter before the decision bar close.",
                    trade_id=trade_id,
                    expected="entry_time >= decision_bar_time",
                    actual=f"{entry} >= {decision}",
                )
        if _is_forced_flatten(trade):
            entry = timestamps["entry_time"]
            exit_time = timestamps["exit_time"]
            if entry is not None and exit_time is not None:
                self._assert(
                    entry <= exit_time,
                    check_name="forced_flatten_after_entry",
                    category="time_ordering",
                    description="Forced flatten occurs after entry.",
                    trade_id=trade_id,
                    expected="entry_time <= forced flatten exit_time",
                    actual=f"{entry} <= {exit_time}",
                )
            cutoff = _cutoff_time(condition, self.metadata)
            if exit_time is not None and cutoff is not None:
                cutoff_dt = _session_cutoff(exit_time, cutoff)
                self._assert(
                    exit_time <= cutoff_dt + pd.Timedelta(minutes=1),
                    check_name="forced_flatten_before_cutoff",
                    category="time_ordering",
                    description="Forced flatten occurs before or at the configured cutoff.",
                    trade_id=trade_id,
                    expected=f"exit_time <= {cutoff_dt}",
                    actual=exit_time,
                )

    def _check_price_logic(self, trade: pd.Series) -> None:
        trade_id = trade.get("trade_id")
        direction = str(trade.get("direction") or "").lower()
        entry = _num(trade.get("entry_price"))
        stop = _num(trade.get("stop_price"))
        target = _num(trade.get("target_price"))
        if entry is None or stop is None or target is None:
            return
        if direction.startswith("long") or direction in {"buy", "1"}:
            self._assert(
                stop < entry,
                check_name="long_stop_below_entry",
                category="price_logic",
                description="Long trade stop is below entry.",
                trade_id=trade_id,
                expected="stop_price < entry_price",
                actual=f"{stop} < {entry}",
            )
            self._assert(
                target > entry,
                check_name="long_target_above_entry",
                category="price_logic",
                description="Long trade target is above entry.",
                trade_id=trade_id,
                expected="target_price > entry_price",
                actual=f"{target} > {entry}",
            )
        elif direction.startswith("short") or direction in {"sell", "-1"}:
            self._assert(
                stop > entry,
                check_name="short_stop_above_entry",
                category="price_logic",
                description="Short trade stop is above entry.",
                trade_id=trade_id,
                expected="stop_price > entry_price",
                actual=f"{stop} > {entry}",
            )
            self._assert(
                target < entry,
                check_name="short_target_below_entry",
                category="price_logic",
                description="Short trade target is below entry.",
                trade_id=trade_id,
                expected="target_price < entry_price",
                actual=f"{target} < {entry}",
            )

    def _check_filters(self, trade: pd.Series, condition: pd.Series | None, bars: pd.DataFrame) -> None:
        if condition is None:
            return
        trade_id = trade.get("trade_id")
        final_pass = _bool_or_none(_lookup(condition, ("final_entry_pass",)))
        if final_pass is True:
            failed = []
            for flag in (
                "rth_filter_pass",
                "volume_filter_pass",
                "delta_filter_pass",
                "stacked_imbalance_pass",
                "no_trade_window_filter_pass",
                "max_trades_filter_pass",
            ):
                value = _bool_or_none(_lookup(condition, (flag,)))
                if value is False:
                    failed.append(flag)
            self._assert(
                not failed,
                check_name="final_entry_required_filters",
                category="filter_logic",
                description="Final entry pass is not true when a required filter is false.",
                trade_id=trade_id,
                expected="no required filter false",
                actual=", ".join(failed) if failed else "all present filters pass",
            )

        self._check_numeric_filter(
            trade_id,
            condition,
            check_name="volume_filter_threshold",
            pass_aliases=("volume_filter_pass",),
            actual_threshold_pairs=(
                (("volume_ratio",), ("min_volume_ratio",)),
                (("total_volume", "volume", "sweep_bar_volume"), ("min_volume", "volume_threshold")),
            ),
            category="filter_logic",
            description="Volume filter pass flag matches exported actual and threshold.",
        )
        self._check_delta_filter(trade_id, condition)

        sweep = _ts(_lookup(condition, ("sweep_time",)))
        reclaim = _ts(_lookup(condition, ("reclaim_time",)))
        window = _num(_lookup(condition, ("reclaim_window_bars",)))
        if sweep is not None and reclaim is not None and window is not None and not bars.empty:
            sweep_idx = _bar_index_for_timestamp(bars, sweep)
            reclaim_idx = _bar_index_for_timestamp(bars, reclaim)
            if sweep_idx is not None and reclaim_idx is not None:
                distance = reclaim_idx - sweep_idx
                self._assert(
                    0 <= distance <= int(window),
                    check_name="reclaim_window_distance",
                    category="filter_logic",
                    description="Reclaim occurs inside the configured reclaim window.",
                    trade_id=trade_id,
                    expected=f"0 <= bars_between <= {int(window)}",
                    actual=distance,
                )

        rth_pass = _bool_or_none(_lookup(condition, ("rth_filter_pass",)))
        if rth_pass is not None:
            exported_rth = _bool_or_none(_lookup(condition, ("is_rth",)))
            if exported_rth is None and not bars.empty and "is_rth" in bars.columns:
                signal_idx = _bar_index_for_timestamp(bars, _first_present(_lookup(condition, ("signal_time",)), trade.get("entry_time")))
                if signal_idx is not None:
                    exported_rth = _bool_or_none(bars.iloc[signal_idx].get("is_rth"))
            if exported_rth is not None:
                self._assert(
                    rth_pass == exported_rth,
                    check_name="rth_filter_matches_session_flag",
                    category="filter_logic",
                    description="RTH filter pass flag matches exported RTH/session flag.",
                    trade_id=trade_id,
                    expected=f"rth_filter_pass == {exported_rth}",
                    actual=rth_pass,
                )

    def _check_numeric_filter(
        self,
        trade_id: Any,
        condition: pd.Series,
        *,
        check_name: str,
        pass_aliases: tuple[str, ...],
        actual_threshold_pairs: tuple[tuple[tuple[str, ...], tuple[str, ...]], ...],
        category: str,
        description: str,
    ) -> None:
        pass_flag = _bool_or_none(_lookup(condition, pass_aliases))
        if pass_flag is None:
            return
        for actual_aliases, threshold_aliases in actual_threshold_pairs:
            actual = _num(_lookup(condition, actual_aliases))
            threshold = _num(_lookup(condition, threshold_aliases))
            if actual is None or threshold is None:
                continue
            expected_pass = actual >= threshold
            self._assert(
                pass_flag == expected_pass,
                check_name=check_name,
                category=category,
                description=description,
                trade_id=trade_id,
                expected=f"{actual_aliases[0]} >= {threshold_aliases[0]} -> {expected_pass}",
                actual=pass_flag,
            )
            return

    def _check_delta_filter(self, trade_id: Any, condition: pd.Series) -> None:
        pass_flag = _bool_or_none(_lookup(condition, ("delta_filter_pass",)))
        if pass_flag is None:
            return
        checks = [
            (("delta_pct", "delta_imbalance"), ("min_delta_pct", "min_delta_imbalance"), "ge"),
            (("delta_pct", "delta_imbalance"), ("max_delta_pct", "max_delta_imbalance"), "le"),
            (("delta_value", "signed_volume", "absorption_bucket_delta"), ("delta_threshold", "absorption_delta_threshold"), "abs_ge"),
        ]
        for actual_aliases, threshold_aliases, mode in checks:
            actual = _num(_lookup(condition, actual_aliases))
            threshold = _num(_lookup(condition, threshold_aliases))
            if actual is None or threshold is None:
                continue
            if mode == "ge":
                expected_pass = actual >= threshold
                expression = f"{actual_aliases[0]} >= {threshold_aliases[0]}"
            elif mode == "le":
                expected_pass = actual <= threshold
                expression = f"{actual_aliases[0]} <= {threshold_aliases[0]}"
            else:
                expected_pass = abs(actual) >= abs(threshold)
                expression = f"abs({actual_aliases[0]}) >= abs({threshold_aliases[0]})"
            self._assert(
                pass_flag == expected_pass,
                check_name="delta_filter_threshold",
                category="filter_logic",
                description="Delta filter pass flag matches exported actual and threshold.",
                trade_id=trade_id,
                expected=f"{expression} -> {expected_pass}",
                actual=pass_flag,
            )
            return

    def _check_exits(self, trade: pd.Series, condition: pd.Series | None, exit_audit: pd.Series | None) -> None:
        trade_id = trade.get("trade_id")
        if exit_audit is None:
            self._add(
                check_name="exit_audit_present",
                category="exit_logic",
                status=WARNING,
                description="Trade has no matching exit audit row.",
                trade_id=trade_id,
                expected="exit audit present",
                actual="missing",
            )
            return
        trade_reason = _normalize_reason(trade.get("exit_reason"))
        audit_reason = _normalize_reason(_first_present(exit_audit.get("exit_reason"), exit_audit.get("first_touch_exit_decision")))
        if trade_reason and audit_reason:
            self._assert(
                trade_reason == audit_reason or _same_exit_family(trade_reason, audit_reason),
                check_name="exit_reason_matches_audit",
                category="exit_logic",
                description="Trade exit reason matches exit audit decision.",
                trade_id=trade_id,
                expected=trade_reason,
                actual=audit_reason,
            )
        if _is_target_reason(trade_reason):
            self._assert(
                not _is_missing(exit_audit.get("first_touch_tp_time")) or _bool_or_none(exit_audit.get("tp_hit_on_exit_bar")) is True,
                check_name="target_exit_has_target_touch",
                category="exit_logic",
                description="Target exit is explainable by a target touch.",
                trade_id=trade_id,
                expected="target touch present",
                actual=_format(exit_audit.get("first_touch_tp_time") or exit_audit.get("tp_hit_on_exit_bar")),
            )
        if _is_stop_reason(trade_reason):
            self._assert(
                not _is_missing(exit_audit.get("first_touch_sl_time")) or _bool_or_none(exit_audit.get("sl_hit_on_exit_bar")) is True,
                check_name="stop_exit_has_stop_touch",
                category="exit_logic",
                description="Stop exit is explainable by a stop touch.",
                trade_id=trade_id,
                expected="stop touch present",
                actual=_format(exit_audit.get("first_touch_sl_time") or exit_audit.get("sl_hit_on_exit_bar")),
            )
        if _is_forced_flatten(trade):
            cutoff = _cutoff_time(condition, self.metadata)
            self._add(
                check_name="forced_flatten_has_cutoff_context",
                category="exit_logic",
                status=PASS if cutoff else WARNING,
                description="Forced flatten has a visible cutoff/session rule.",
                trade_id=trade_id,
                expected="cutoff context present",
                actual=cutoff or "missing",
            )
        both_hit = _bool_or_none(exit_audit.get("tp_hit_on_exit_bar")) is True and _bool_or_none(exit_audit.get("sl_hit_on_exit_bar")) is True
        if both_hit:
            resolved_by_tick_path = (
                str(exit_audit.get("ambiguity_resolution") or "").lower() == "detail_data"
                and _bool_or_none(exit_audit.get("engine_exit_matches_path")) is True
                and _has_flag(exit_audit.get("warning_flags"), "same_bar_resolved_by_tick_path")
                and _normalize_reason(exit_audit.get("first_touch_decision")) in {"target", "stop"}
            )
            self._add(
                check_name="same_bar_ambiguity_flagged",
                category="exit_logic",
                status=(
                    PASS
                    if resolved_by_tick_path
                    else WARNING if _bool_or_none(exit_audit.get("same_bar_ambiguous")) is True else ERROR
                ),
                description=(
                    "Same-bar TP/SL touch is resolved by ordered tick path."
                    if resolved_by_tick_path
                    else "Same-bar TP/SL touch is flagged as ambiguous."
                ),
                trade_id=trade_id,
                expected="resolved by tick path" if resolved_by_tick_path else "same_bar_ambiguous true",
                actual=exit_audit.get("warning_flags") if resolved_by_tick_path else exit_audit.get("same_bar_ambiguous"),
            )

    def _check_data_quality(
        self,
        trade: pd.Series,
        condition: pd.Series | None,
        bars: pd.DataFrame,
        ticks: pd.DataFrame,
    ) -> None:
        trade_id = trade.get("trade_id")
        self._add(
            check_name="tick_window_present",
            category="data_quality",
            status=PASS if not ticks.empty else WARNING,
            description="Selected trade has tick/footprint window rows.",
            trade_id=trade_id,
            expected="tick rows present",
            actual=len(ticks),
        )
        missing_orderflow = []
        for column in ("bid_volume", "ask_volume", "delta"):
            if column not in bars.columns or pd.to_numeric(bars[column], errors="coerce").dropna().empty:
                missing_orderflow.append(column)
        self._add(
            check_name="orderflow_fields_present",
            category="data_quality",
            status=PASS if not missing_orderflow else WARNING,
            description="Bar window has exported orderflow fields.",
            trade_id=trade_id,
            expected="bid_volume, ask_volume, delta present",
            actual=", ".join(missing_orderflow) if missing_orderflow else "present",
        )
        for name, frame in (("bar", bars), ("tick", ticks)):
            if frame.empty or "timestamp" not in frame.columns:
                continue
            parsed = pd.to_datetime(frame["timestamp"], errors="coerce", utc=True)
            if name == "tick" and "price_level" in frame.columns and frame["price_level"].notna().any():
                duplicate_basis = pd.DataFrame({"timestamp": parsed, "price_level": frame["price_level"]})
                duplicated = duplicate_basis.duplicated().any()
                duplicate_expected = "no duplicate timestamp/price_level rows"
            else:
                duplicated = parsed.duplicated().any()
                duplicate_expected = "no duplicate timestamps"
            monotonic = parsed.dropna().is_monotonic_increasing
            self._add(
                check_name=f"{name}_timestamps_unique",
                category="data_quality",
                status=WARNING if duplicated else PASS,
                description=f"{name.title()} window timestamps are not duplicated.",
                trade_id=trade_id,
                expected=duplicate_expected,
                actual="duplicates found" if duplicated else "unique",
            )
            self._add(
                check_name=f"{name}_timestamps_monotonic",
                category="data_quality",
                status=WARNING if not monotonic else PASS,
                description=f"{name.title()} window timestamps are monotonic.",
                trade_id=trade_id,
                expected="monotonic increasing",
                actual="monotonic" if monotonic else "non-monotonic",
            )
        session_date = trade.get("session_date")
        entry = _ts(trade.get("entry_time"))
        if not _is_missing(session_date) and entry is not None:
            entry_date = str(entry.tz_convert("America/New_York").date())
            self._assert(
                str(session_date) == entry_date,
                check_name="session_date_matches_entry",
                category="data_quality",
                description="Trade session_date matches the New York entry date.",
                trade_id=trade_id,
                expected=entry_date,
                actual=session_date,
                fail_status=WARNING,
            )
        naive_fields = []
        for field in ("entry_time", "exit_time"):
            if _is_timezone_naive(trade.get(field)):
                naive_fields.append(f"trade.{field}")
        if condition is not None:
            for field in ("sweep_time", "reclaim_time", "signal_time", "decision_bar_time", "entry_execution_time"):
                if _is_timezone_naive(_lookup(condition, (field,))):
                    naive_fields.append(f"condition.{field}")
        for name, frame in (("bar", bars), ("tick", ticks)):
            if not frame.empty and "timestamp" in frame.columns and any(_is_timezone_naive(value) for value in frame["timestamp"].dropna().head(100)):
                naive_fields.append(f"{name}.timestamp")
        self._add(
            check_name="timestamps_timezone_aware",
            category="data_quality",
            status=WARNING if naive_fields else PASS,
            description="Validation timestamps are timezone-aware.",
            trade_id=trade_id,
            expected="timezone-aware timestamps",
            actual=", ".join(naive_fields) if naive_fields else "timezone-aware",
        )


def _row_for_trade(frame: pd.DataFrame, trade_id: Any) -> pd.Series | None:
    if frame.empty or "trade_id" not in frame.columns:
        return None
    rows = frame[frame["trade_id"] == trade_id]
    if rows.empty:
        rows = frame[frame["trade_id"].astype(str) == str(trade_id)]
    return None if rows.empty else rows.iloc[0]


def _rows_for_trade(frame: pd.DataFrame, trade_id: Any) -> pd.DataFrame:
    if frame.empty or "trade_id" not in frame.columns:
        return frame.iloc[0:0]
    rows = frame[frame["trade_id"] == trade_id]
    if rows.empty:
        rows = frame[frame["trade_id"].astype(str) == str(trade_id)]
    return rows.copy()


def _lookup(condition: pd.Series | None, aliases: tuple[str, ...]) -> Any:
    if condition is None:
        return None
    sources = [condition.to_dict()]
    for column in ("filter_pass_values", "raw_orderflow_values", "signal_metadata", "signal_report_fields", "decision_context", "entry_trigger_values"):
        parsed = _parse_json(condition.get(column))
        if parsed:
            sources.append(parsed)
    for alias in aliases:
        for source in sources:
            if alias in source and not _is_missing(source[alias]):
                return source[alias]
        for source in sources:
            for key, value in source.items():
                if str(key).split(".")[-1] == alias and not _is_missing(value):
                    return value
    return None


def _parse_json(value: Any) -> dict[str, Any]:
    if isinstance(value, dict):
        return value
    if _is_missing(value):
        return {}
    try:
        parsed = json.loads(str(value))
    except (TypeError, ValueError, json.JSONDecodeError):
        return {}
    return parsed if isinstance(parsed, dict) else {}


def _bar_index_for_timestamp(bars: pd.DataFrame, timestamp: Any) -> int | None:
    if bars.empty or "timestamp" not in bars.columns or timestamp is None:
        return None
    parsed = pd.to_datetime(bars["timestamp"], errors="coerce", utc=True)
    target = _ts(timestamp)
    if target is None or parsed.dropna().empty:
        return None
    sorted_positions = parsed.sort_values()
    position = int(sorted_positions.searchsorted(target, side="right")) - 1
    if position < 0:
        return None
    return position


def _ts(value: Any) -> pd.Timestamp | None:
    if _is_missing(value):
        return None
    try:
        timestamp = pd.to_datetime(value, errors="coerce", utc=True)
    except (TypeError, ValueError):
        return None
    return None if pd.isna(timestamp) else pd.Timestamp(timestamp)


def _num(value: Any) -> float | None:
    if _is_missing(value):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _bool_or_none(value: Any) -> bool | None:
    if _is_missing(value):
        return None
    if isinstance(value, str):
        lowered = value.strip().lower()
        if lowered in {"true", "1", "yes", "pass", "passed"}:
            return True
        if lowered in {"false", "0", "no", "fail", "failed"}:
            return False
    return bool(value)


def _truthy(value: Any) -> bool:
    result = _bool_or_none(value)
    return bool(result)


def _has_flag(value: Any, flag: str) -> bool:
    if _is_missing(value):
        return False
    return flag in {item.strip() for item in str(value).split(";") if item.strip()}


def _is_missing(value: Any) -> bool:
    if value is None:
        return True
    try:
        return bool(pd.isna(value))
    except (TypeError, ValueError):
        return False


def _first_present(*values: Any) -> Any:
    for value in values:
        if not _is_missing(value):
            return value
    return None


def _format(value: Any) -> str | None:
    if _is_missing(value):
        return None
    return str(value)


def _bar_close_entry(condition: pd.Series | None, trade: pd.Series, metadata: dict[str, Any]) -> bool:
    text = " ".join(
        str(value)
        for value in (
            _lookup(condition, ("entry_mode",)),
            trade.get("entry_order_type"),
            trade.get("debug_flags"),
            metadata.get("entry_timing"),
            metadata.get("signal_timing"),
        )
        if not _is_missing(value)
    ).lower()
    if "intrabar" in text:
        return False
    return any(token in text for token in ("bar_close", "bar close", "next_bar", "next bar", "close signal"))


def _is_forced_flatten(trade: pd.Series) -> bool:
    if _bool_or_none(trade.get("was_forced_flatten")) is True:
        return True
    reason = str(trade.get("exit_reason") or "").lower()
    return "flatten" in reason


def _cutoff_time(condition: pd.Series | None, metadata: dict[str, Any]) -> str | None:
    return _first_present(
        _lookup(condition, ("signal_flatten_time", "flatten_time", "forced_flatten_time")),
        metadata.get("signal_flatten_time"),
        metadata.get("flatten_time"),
        metadata.get("forced_flatten_time"),
    )


def _session_cutoff(reference: pd.Timestamp, cutoff: str) -> pd.Timestamp:
    parts = str(cutoff).split(":")
    hour = int(parts[0])
    minute = int(parts[1]) if len(parts) > 1 else 0
    second = int(parts[2]) if len(parts) > 2 else 0
    local = reference.tz_convert("America/New_York")
    return local.replace(hour=hour, minute=minute, second=second, microsecond=0).tz_convert("UTC")


def _normalize_reason(value: Any) -> str:
    if _is_missing(value):
        return ""
    return str(value).strip().lower()


def _same_exit_family(left: str, right: str) -> bool:
    if _is_target_reason(left) and _is_target_reason(right):
        return True
    if _is_stop_reason(left) and _is_stop_reason(right):
        return True
    if "flatten" in left and "flatten" in right:
        return True
    return False


def _is_target_reason(value: str) -> bool:
    return value in {"target", "tp", "take_profit", "take profit"} or "target" in value


def _is_stop_reason(value: str) -> bool:
    return value in {"stop", "sl", "stop_loss", "stop loss"} or "stop" in value


def _is_timezone_naive(value: Any) -> bool:
    if _is_missing(value):
        return False
    try:
        timestamp = pd.Timestamp(value)
    except (TypeError, ValueError):
        return False
    return timestamp.tzinfo is None
