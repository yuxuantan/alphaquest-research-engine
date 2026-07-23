"""Strict ResultBundleV2 metrics and report-artifact builder."""

from __future__ import annotations

from datetime import UTC, date, datetime
import hashlib
import json
import math
import os
from pathlib import Path
from tempfile import NamedTemporaryFile
from typing import Any, Literal, Sequence
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

import numpy as np
import pandas as pd
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


RESULT_BUNDLE_SCHEMA = "alphaquest.result-bundle/v2"
STRICT_VERDICTS = {"PASS", "FAIL", "NEEDS MANUAL REVIEW"}
RESULT_BUNDLE_FILENAME = "result_bundle_v2.json"


class MetricValueV2(BaseModel):
    """A JSON-safe scalar and an explicit explanation when it is undefined."""

    model_config = ConfigDict(extra="forbid", strict=True)

    # Keep bool first so Pydantic's JSON-mode union serializer does not turn
    # compliance booleans into 1.0/0.0 in the strict public artifact.
    value: bool | int | float | str | None
    reason: str | None = None

    @field_validator("value", mode="before")
    @classmethod
    def _native_finite_value(cls, value: Any) -> Any:
        if hasattr(value, "item"):
            value = value.item()
        if isinstance(value, float) and not math.isfinite(value):
            raise ValueError("metric values must be finite; use null plus a reason")
        return value

    @model_validator(mode="after")
    def _undefined_requires_reason(self) -> "MetricValueV2":
        if self.value is None and not str(self.reason or "").strip():
            raise ValueError("undefined metrics require a reason")
        if self.value is not None and self.reason is not None and not self.reason.strip():
            self.reason = None
        return self


class ScalarMetricsV2(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    net_profit_after_costs: MetricValueV2
    total_transaction_costs: MetricValueV2
    profit_factor: MetricValueV2
    expectancy_currency: MetricValueV2
    expectancy_r: MetricValueV2
    total_trades: MetricValueV2
    trades_per_year: MetricValueV2
    max_drawdown: MetricValueV2
    max_drawdown_pct: MetricValueV2
    mar: MetricValueV2
    daily_sharpe: MetricValueV2
    daily_sortino: MetricValueV2
    average_trade_duration_minutes: MetricValueV2
    win_rate: MetricValueV2
    average_win: MetricValueV2
    average_loss: MetricValueV2
    payoff_ratio: MetricValueV2
    max_losing_streak: MetricValueV2
    largest_winning_trade_contribution: MetricValueV2
    prop_rule_outcome: MetricValueV2
    forced_flatten_compliance: MetricValueV2


class ArtifactStatusV2(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    path: str | None
    available: bool
    rows: int | None = None
    sha256: str | None = None
    reason: str | None = None

    @model_validator(mode="after")
    def _status_consistent(self) -> "ArtifactStatusV2":
        if self.available and (not self.path or not self.sha256 or self.rows is None):
            raise ValueError("available artifacts require path, row count, and sha256")
        if not self.available and not str(self.reason or "").strip():
            raise ValueError("unavailable artifacts require a reason")
        return self


class BreakdownArtifactsV2(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    yearly: ArtifactStatusV2
    monthly: ArtifactStatusV2
    entry_session: ArtifactStatusV2
    side: ArtifactStatusV2
    equity_curve: ArtifactStatusV2
    drawdown_curve: ArtifactStatusV2


class SupplementalArtifactsV2(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    parameter_neighbors: ArtifactStatusV2
    wfa_stitched_oos: ArtifactStatusV2
    monte_carlo_summary: ArtifactStatusV2


class StageCriterionV2(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    stage: str
    metric: str
    operator: Literal[">=", ">", "<=", "<", "==", "!=", "present"]
    threshold: MetricValueV2
    actual: MetricValueV2
    result: Literal["PASS", "FAIL", "NEEDS MANUAL REVIEW"]
    reason: str
    evidence_path: str | None = None

    @field_validator("stage", "metric", "reason")
    @classmethod
    def _nonblank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("value must be non-empty")
        return value.strip()


class ResultBundleV2(BaseModel):
    """Sole strict-JSON source for Studio result presentation."""

    model_config = ConfigDict(extra="forbid", populate_by_name=True, strict=True)

    schema_name: Literal["alphaquest.result-bundle/v2"] = Field(
        default=RESULT_BUNDLE_SCHEMA,
        alias="schema",
        serialization_alias="schema",
    )
    campaign_id: str
    variant_id: str
    run_id: str
    generated_at: datetime
    verdict: Literal["PASS", "FAIL", "NEEDS MANUAL REVIEW"]
    verdict_message: str
    metrics: ScalarMetricsV2
    stage_criteria: list[StageCriterionV2] = Field(default_factory=list)
    breakdowns: BreakdownArtifactsV2
    supplemental_artifacts: SupplementalArtifactsV2

    @field_validator("campaign_id", "variant_id", "run_id", "verdict_message")
    @classmethod
    def _required_text(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("value must be non-empty")
        return value.strip()

    @field_validator("generated_at")
    @classmethod
    def _timezone_aware(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("generated_at must be timezone-aware")
        return value

    @model_validator(mode="after")
    def _candidate_only_pass_language(self) -> "ResultBundleV2":
        if self.verdict == "PASS" and "candidate strategy only" not in self.verdict_message.casefold():
            raise ValueError("PASS language must say 'candidate strategy only'")
        return self


class ResultBundleBuilder:
    """Compute required metrics and atomically publish stable report files."""

    def build_and_write(
        self,
        trades: pd.DataFrame,
        output_dir: str | Path,
        *,
        campaign_id: str,
        variant_id: str,
        run_id: str,
        verdict: Literal["PASS", "FAIL", "NEEDS MANUAL REVIEW"],
        stage_criteria: list[StageCriterionV2 | dict[str, Any]] | None = None,
        initial_balance: float = 0.0,
        prop_rule_outcome: Literal["PASS", "FAIL", "NEEDS MANUAL REVIEW"] | None = None,
        forced_flatten_compliance: bool | None = None,
        parameter_neighbors: pd.DataFrame | None = None,
        wfa_stitched_oos: pd.DataFrame | None = None,
        monte_carlo_summary: pd.DataFrame | None = None,
        generated_at: datetime | str | None = None,
        exchange_timezone: str = "America/New_York",
        evaluation_start: date | datetime | str | None = None,
        evaluation_end: date | datetime | str | None = None,
        trading_dates: Sequence[date | datetime | str] | None = None,
    ) -> ResultBundleV2:
        output = Path(output_dir)
        output.mkdir(parents=True, exist_ok=True)
        timezone = _exchange_timezone(exchange_timezone)
        normalized = _normalize_trades(trades)
        timestamp_column = _timestamp_column(normalized, "exit_timestamp", "exit_time")
        entry_column = _timestamp_column(normalized, "entry_timestamp", "entry_time")
        metrics = _scalar_metrics(
            normalized,
            initial_balance=float(initial_balance),
            entry_column=entry_column,
            exit_column=timestamp_column,
            prop_rule_outcome=prop_rule_outcome,
            forced_flatten_compliance=forced_flatten_compliance,
            exchange_timezone=timezone,
            evaluation_start=evaluation_start,
            evaluation_end=evaluation_end,
            trading_dates=trading_dates,
        )

        yearly = _time_breakdown(
            normalized,
            timestamp_column,
            period="year",
            exchange_timezone=timezone,
        )
        monthly = _time_breakdown(
            normalized,
            timestamp_column,
            period="month",
            exchange_timezone=timezone,
        )
        sessions = _session_breakdown(
            normalized,
            entry_column,
            exchange_timezone=timezone,
        )
        sides = _group_breakdown(normalized, "direction", "side")
        equity, drawdown = _equity_and_drawdown(normalized, timestamp_column, initial_balance=float(initial_balance))

        breakdowns = BreakdownArtifactsV2(
            yearly=_write_required_csv(output, "yearly_breakdown.csv", yearly, "no dated trades for yearly breakdown"),
            monthly=_write_required_csv(output, "monthly_breakdown.csv", monthly, "no dated trades for monthly breakdown"),
            entry_session=_write_required_csv(
                output,
                "entry_session_breakdown.csv",
                sessions,
                "no entry timestamps or session labels for entry-session breakdown",
            ),
            side=_write_required_csv(output, "side_breakdown.csv", sides, "no trade directions for side breakdown"),
            equity_curve=_write_required_csv(output, "equity_curve.csv", equity, "no trades for equity curve"),
            drawdown_curve=_write_required_csv(output, "drawdown_curve.csv", drawdown, "no trades for drawdown curve"),
        )
        supplemental = SupplementalArtifactsV2(
            parameter_neighbors=_write_optional_csv(
                output,
                "parameter_neighbors.csv",
                parameter_neighbors,
                "parameter-neighbor evidence was not supplied",
            ),
            wfa_stitched_oos=_write_optional_csv(
                output,
                "wfa_stitched_oos.csv",
                wfa_stitched_oos,
                "stitched walk-forward OOS evidence was not supplied",
            ),
            monte_carlo_summary=_write_optional_csv(
                output,
                "monte_carlo_summary.csv",
                monte_carlo_summary,
                "Monte Carlo summary was not supplied",
            ),
        )
        criterion_models = [
            item if isinstance(item, StageCriterionV2) else StageCriterionV2.model_validate(item)
            for item in (stage_criteria or [])
        ]
        bundle = ResultBundleV2(
            campaign_id=campaign_id,
            variant_id=variant_id,
            run_id=run_id,
            generated_at=_aware_datetime(generated_at),
            verdict=verdict,
            verdict_message=_verdict_message(verdict, criterion_models),
            metrics=metrics,
            stage_criteria=criterion_models,
            breakdowns=breakdowns,
            supplemental_artifacts=supplemental,
        )
        write_result_bundle(output / RESULT_BUNDLE_FILENAME, bundle)
        return bundle


def write_result_bundle(path: str | Path, bundle: ResultBundleV2) -> Path:
    target = Path(path)
    payload = bundle.model_dump(mode="json", by_alias=True)
    _atomic_write_bytes(
        target,
        (json.dumps(payload, indent=2, sort_keys=True, allow_nan=False) + "\n").encode("utf-8"),
    )
    return target


def load_result_bundle(path: str | Path) -> ResultBundleV2:
    try:
        raw = Path(path).read_text(encoding="utf-8")
        return ResultBundleV2.model_validate_json(raw)
    except (OSError, ValueError) as exc:
        raise ValueError(f"could not read ResultBundleV2: {exc}") from exc


def _scalar_metrics(
    trades: pd.DataFrame,
    *,
    initial_balance: float,
    entry_column: str | None,
    exit_column: str | None,
    prop_rule_outcome: str | None,
    forced_flatten_compliance: bool | None,
    exchange_timezone: str,
    evaluation_start: date | datetime | str | None,
    evaluation_end: date | datetime | str | None,
    trading_dates: Sequence[date | datetime | str] | None,
) -> ScalarMetricsV2:
    count = int(len(trades))
    period_start, period_end, years, period_reason = _governed_evaluation_period(
        evaluation_start,
        evaluation_end,
    )
    daily_returns, daily_returns_reason = _governed_daily_returns(
        trades,
        initial_balance=initial_balance,
        exit_column=exit_column,
        exchange_timezone=exchange_timezone,
        evaluation_start=period_start,
        evaluation_end=period_end,
        trading_dates=trading_dates,
        period_reason=period_reason,
    )
    sharpe, sharpe_reason = _daily_sharpe(daily_returns, unavailable_reason=daily_returns_reason)
    sortino, sortino_reason = _daily_sortino(daily_returns, unavailable_reason=daily_returns_reason)
    if count == 0:
        undefined = lambda reason: MetricValueV2(value=None, reason=reason)
        return ScalarMetricsV2(
            net_profit_after_costs=MetricValueV2(value=0.0),
            total_transaction_costs=MetricValueV2(value=0.0),
            profit_factor=undefined("no trades"),
            expectancy_currency=undefined("no trades"),
            expectancy_r=undefined("no trades"),
            total_trades=MetricValueV2(value=0),
            trades_per_year=(
                MetricValueV2(value=0.0)
                if years is not None
                else undefined(period_reason or "governed evaluation-period start/end are required")
            ),
            max_drawdown=MetricValueV2(value=0.0),
            max_drawdown_pct=undefined("positive initial balance is required"),
            mar=undefined(
                period_reason
                or "positive initial balance and nonzero drawdown are required over the governed evaluation period"
            ),
            daily_sharpe=undefined(sharpe_reason),
            daily_sortino=undefined(sortino_reason),
            average_trade_duration_minutes=undefined("no trades"),
            win_rate=undefined("no trades"),
            average_win=undefined("no winning trades"),
            average_loss=undefined("no losing trades"),
            payoff_ratio=undefined("both winning and losing trades are required"),
            max_losing_streak=MetricValueV2(value=0),
            largest_winning_trade_contribution=undefined("no winning trades"),
            prop_rule_outcome=_prop_outcome(trades, prop_rule_outcome),
            forced_flatten_compliance=_flatten_compliance(trades, forced_flatten_compliance),
        )

    pnl = trades["net_pnl"].astype(float)
    wins = pnl[pnl > 0]
    losses = pnl[pnl < 0]
    net = float(pnl.sum())
    gross_wins = float(wins.sum())
    gross_losses = float(abs(losses.sum()))
    average_win = float(wins.mean()) if len(wins) else None
    average_loss = float(losses.mean()) if len(losses) else None
    drawdown, drawdown_pct, ending_balance = _drawdown_inputs(
        trades,
        pnl,
        initial_balance=initial_balance,
        exit_column=exit_column,
    )
    expectancy_r = _mean_column(trades, "r_multiple")
    costs = _cost_total(trades)
    duration = _average_duration(trades, entry_column, exit_column)
    cagr = None
    if initial_balance > 0 and years is not None and ending_balance > 0:
        cagr = (ending_balance / initial_balance) ** (1.0 / years) - 1.0
    mar = cagr / drawdown_pct if cagr is not None and drawdown_pct is not None and drawdown_pct > 0 else None
    return ScalarMetricsV2(
        net_profit_after_costs=MetricValueV2(value=net),
        total_transaction_costs=MetricValueV2(value=costs) if costs is not None else MetricValueV2(
            value=None,
            reason="trade log has no transaction-cost columns",
        ),
        profit_factor=MetricValueV2(value=gross_wins / gross_losses)
        if gross_losses > 0
        else MetricValueV2(value=None, reason="no losing trades; infinite values are not serialized"),
        expectancy_currency=MetricValueV2(value=float(pnl.mean())),
        expectancy_r=MetricValueV2(value=expectancy_r)
        if expectancy_r is not None
        else MetricValueV2(value=None, reason="r_multiple is unavailable"),
        total_trades=MetricValueV2(value=count),
        trades_per_year=MetricValueV2(value=count / years)
        if years is not None
        else MetricValueV2(
            value=None,
            reason=period_reason or "governed evaluation-period start/end are required",
        ),
        max_drawdown=MetricValueV2(value=drawdown),
        max_drawdown_pct=MetricValueV2(value=drawdown_pct)
        if drawdown_pct is not None
        else MetricValueV2(value=None, reason="positive initial balance is required"),
        mar=MetricValueV2(value=mar)
        if mar is not None and math.isfinite(mar)
        else MetricValueV2(
            value=None,
            reason=(
                period_reason
                or "positive initial balance, positive ending balance, and nonzero drawdown are required "
                "over the governed evaluation period"
            ),
        ),
        daily_sharpe=MetricValueV2(value=sharpe)
        if sharpe is not None
        else MetricValueV2(value=None, reason=sharpe_reason),
        daily_sortino=MetricValueV2(value=sortino)
        if sortino is not None
        else MetricValueV2(value=None, reason=sortino_reason),
        average_trade_duration_minutes=MetricValueV2(value=duration)
        if duration is not None
        else MetricValueV2(value=None, reason="valid entry and exit timestamps are required"),
        win_rate=MetricValueV2(value=float((pnl > 0).mean())),
        average_win=MetricValueV2(value=average_win)
        if average_win is not None
        else MetricValueV2(value=None, reason="no winning trades"),
        average_loss=MetricValueV2(value=average_loss)
        if average_loss is not None
        else MetricValueV2(value=None, reason="no losing trades"),
        payoff_ratio=MetricValueV2(value=average_win / abs(average_loss))
        if average_win is not None and average_loss is not None and average_loss != 0
        else MetricValueV2(value=None, reason="both winning and losing trades are required"),
        max_losing_streak=MetricValueV2(value=_max_losing_streak(pnl)),
        largest_winning_trade_contribution=MetricValueV2(value=float(wins.max() / gross_wins))
        if gross_wins > 0
        else MetricValueV2(value=None, reason="no winning trades"),
        prop_rule_outcome=_prop_outcome(trades, prop_rule_outcome),
        forced_flatten_compliance=_flatten_compliance(trades, forced_flatten_compliance),
    )


def _normalize_trades(trades: pd.DataFrame) -> pd.DataFrame:
    if not isinstance(trades, pd.DataFrame):
        raise TypeError("trades must be a pandas DataFrame")
    frame = trades.copy()
    if frame.empty:
        if "net_pnl" not in frame.columns:
            frame["net_pnl"] = pd.Series(dtype=float)
        return frame
    if "net_pnl" not in frame.columns:
        raise ValueError("trade log is missing required net_pnl")
    numeric = pd.to_numeric(frame["net_pnl"], errors="coerce")
    if bool(numeric.isna().any()) or not bool(np.isfinite(numeric.to_numpy(dtype=float)).all()):
        raise ValueError("trade log net_pnl contains missing or non-finite values")
    frame["net_pnl"] = numeric.astype(float)
    for column in ("r_multiple", "total_transaction_cost", "commission", "slippage_cost"):
        if column in frame.columns:
            values = pd.to_numeric(frame[column], errors="coerce")
            present = values.dropna().to_numpy(dtype=float)
            if len(present) and not bool(np.isfinite(present).all()):
                raise ValueError(f"trade log {column} contains non-finite values")
            frame[column] = values
    return frame


def _time_breakdown(
    trades: pd.DataFrame,
    timestamp_column: str | None,
    *,
    period: str,
    exchange_timezone: str,
) -> pd.DataFrame:
    key = period
    columns = [key, *_BREAKDOWN_METRIC_COLUMNS]
    if trades.empty or timestamp_column is None:
        return pd.DataFrame(columns=columns)
    timestamps = pd.to_datetime(trades[timestamp_column], utc=True, errors="coerce").dt.tz_convert(
        exchange_timezone
    )
    if period == "year":
        labels = timestamps.dt.year.astype("Int64").astype(str).replace("<NA>", pd.NA)
    else:
        labels = timestamps.dt.tz_localize(None).dt.to_period("M").astype(str).replace("NaT", pd.NA)
    return _summarize_groups(trades, labels, key)


def _session_breakdown(
    trades: pd.DataFrame,
    entry_column: str | None,
    *,
    exchange_timezone: str,
) -> pd.DataFrame:
    columns = ["entry_session", *_BREAKDOWN_METRIC_COLUMNS]
    if trades.empty:
        return pd.DataFrame(columns=columns)
    for candidate in ("entry_session", "session", "time_of_day"):
        if candidate in trades.columns and bool(trades[candidate].notna().any()):
            return _summarize_groups(trades, trades[candidate].astype("string"), "entry_session")
    if entry_column is None:
        return pd.DataFrame(columns=columns)
    timestamps = pd.to_datetime(trades[entry_column], utc=True, errors="coerce").dt.tz_convert(
        exchange_timezone
    )
    labels = timestamps.dt.strftime("%H:00-%H:59").replace("NaN:00-NaN:59", pd.NA)
    return _summarize_groups(trades, labels, "entry_session")


def _group_breakdown(trades: pd.DataFrame, source: str, label: str) -> pd.DataFrame:
    columns = [label, *_BREAKDOWN_METRIC_COLUMNS]
    if trades.empty or source not in trades.columns:
        return pd.DataFrame(columns=columns)
    return _summarize_groups(trades, trades[source].astype("string").str.lower(), label)


_BREAKDOWN_METRIC_COLUMNS = [
    "net_profit_after_costs",
    "trades",
    "wins",
    "losses",
    "win_rate",
    "expectancy_currency",
    "expectancy_r",
]


def _summarize_groups(trades: pd.DataFrame, labels: pd.Series, label: str) -> pd.DataFrame:
    scoped = trades.assign(_group=labels).dropna(subset=["_group"])
    rows = []
    for group_value, group in scoped.groupby("_group", sort=True, dropna=False):
        pnl = group["net_pnl"].astype(float)
        r_value = _mean_column(group, "r_multiple")
        rows.append(
            {
                label: str(group_value),
                "net_profit_after_costs": float(pnl.sum()),
                "trades": int(len(group)),
                "wins": int((pnl > 0).sum()),
                "losses": int((pnl < 0).sum()),
                "win_rate": float((pnl > 0).mean()),
                "expectancy_currency": float(pnl.mean()),
                "expectancy_r": r_value,
            }
        )
    return pd.DataFrame(rows, columns=[label, *_BREAKDOWN_METRIC_COLUMNS])


def _equity_and_drawdown(
    trades: pd.DataFrame,
    timestamp_column: str | None,
    *,
    initial_balance: float,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    eq_columns = ["sequence", "trade_id", "exit_timestamp", "net_pnl", "equity"]
    dd_columns = ["sequence", "exit_timestamp", "equity", "equity_peak", "drawdown", "drawdown_pct"]
    if trades.empty:
        return pd.DataFrame(columns=eq_columns), pd.DataFrame(columns=dd_columns)
    ordered = trades.copy()
    if timestamp_column:
        ordered["_exit"] = pd.to_datetime(ordered[timestamp_column], utc=True, errors="coerce")
        sort_columns = ["_exit"] + (["trade_id"] if "trade_id" in ordered.columns else [])
        ordered = ordered.sort_values(sort_columns, kind="mergesort")
    else:
        ordered["_exit"] = pd.NaT
    equity_values = initial_balance + ordered["net_pnl"].astype(float).cumsum()
    peaks = pd.concat([pd.Series([initial_balance]), equity_values.reset_index(drop=True)]).cummax().iloc[1:].reset_index(drop=True)
    equity_values = equity_values.reset_index(drop=True)
    drawdowns = peaks - equity_values
    drawdown_pct = drawdowns / peaks.where(peaks > 0)
    sequence = pd.Series(range(1, len(ordered) + 1), dtype=int)
    trade_ids = ordered["trade_id"].reset_index(drop=True) if "trade_id" in ordered.columns else sequence
    exits = ordered["_exit"].reset_index(drop=True)
    pnl = ordered["net_pnl"].reset_index(drop=True)
    equity = pd.DataFrame(
        {
            "sequence": sequence,
            "trade_id": trade_ids,
            "exit_timestamp": exits,
            "net_pnl": pnl,
            "equity": equity_values,
        },
        columns=eq_columns,
    )
    drawdown = pd.DataFrame(
        {
            "sequence": sequence,
            "exit_timestamp": exits,
            "equity": equity_values,
            "equity_peak": peaks,
            "drawdown": drawdowns,
            "drawdown_pct": drawdown_pct,
        },
        columns=dd_columns,
    )
    return equity, drawdown


def _drawdown_inputs(
    trades: pd.DataFrame,
    pnl: pd.Series,
    *,
    initial_balance: float,
    exit_column: str | None,
) -> tuple[float, float | None, float]:
    ordered = trades.assign(_pnl=pnl)
    if exit_column:
        ordered = ordered.assign(_exit=pd.to_datetime(ordered[exit_column], utc=True, errors="coerce"))
        ordered = ordered.sort_values("_exit", kind="mergesort")
    equity = initial_balance + ordered["_pnl"].cumsum()
    full = pd.concat([pd.Series([initial_balance]), equity.reset_index(drop=True)], ignore_index=True)
    peaks = full.cummax()
    drawdown = float((peaks - full).max())
    valid = peaks > 0
    drawdown_pct = float(((peaks[valid] - full[valid]) / peaks[valid]).max()) if bool(valid.any()) else None
    ending = float(initial_balance + pnl.sum())
    return drawdown, drawdown_pct, ending


def _governed_evaluation_period(
    start: date | datetime | str | None,
    end: date | datetime | str | None,
) -> tuple[date | None, date | None, float | None, str | None]:
    if start is None or end is None:
        return None, None, None, "governed evaluation-period start/end are required"
    try:
        start_value = pd.Timestamp(start).date()
        end_value = pd.Timestamp(end).date()
    except (TypeError, ValueError, OverflowError) as exc:
        return None, None, None, f"governed evaluation-period dates are invalid: {exc}"
    if end_value < start_value:
        return None, None, None, "governed evaluation-period end precedes its start"
    days = (end_value - start_value).days + 1
    return start_value, end_value, float(days / 365.25), None


def _governed_daily_returns(
    trades: pd.DataFrame,
    *,
    initial_balance: float,
    exit_column: str | None,
    exchange_timezone: str,
    evaluation_start: date | None,
    evaluation_end: date | None,
    trading_dates: Sequence[date | datetime | str] | None,
    period_reason: str | None,
) -> tuple[pd.Series | None, str | None]:
    if period_reason or evaluation_start is None or evaluation_end is None:
        return None, period_reason or "governed evaluation-period start/end are required"
    if trading_dates is None:
        return None, "governed trading-day coverage is required for daily returns"
    parsed_dates: list[date] = []
    for value in trading_dates:
        try:
            parsed_dates.append(pd.Timestamp(value).date())
        except (TypeError, ValueError, OverflowError):
            return None, "governed trading-day coverage contains an invalid date"
    calendar = pd.Index(sorted(set(parsed_dates)), dtype="object")
    if calendar.empty:
        return None, "governed trading-day coverage is empty"
    if any(value < evaluation_start or value > evaluation_end for value in calendar):
        return None, "governed trading-day coverage extends outside the evaluation period"
    if initial_balance <= 0:
        return None, "positive initial balance is required for daily returns"

    daily_pnl = pd.Series(0.0, index=calendar, dtype=float)
    if not trades.empty:
        if exit_column is None:
            return None, "valid exit timestamps are required for daily returns"
        exits = pd.to_datetime(trades[exit_column], utc=True, errors="coerce").dt.tz_convert(
            exchange_timezone
        )
        if bool(exits.isna().any()):
            return None, "trade log contains invalid exit timestamps"
        trade_dates = exits.dt.date
        outside = sorted(set(trade_dates) - set(calendar))
        if outside:
            return None, "trade exits fall outside governed trading-day coverage"
        grouped = trades.assign(_date=trade_dates).groupby("_date")["net_pnl"].sum().astype(float)
        daily_pnl.loc[grouped.index] = grouped
    starts = initial_balance + daily_pnl.cumsum().shift(1, fill_value=0.0)
    if not bool((starts > 0).all()):
        return None, "daily return denominator became non-positive"
    return daily_pnl / starts, None


def _daily_sharpe(
    returns: pd.Series | None,
    *,
    unavailable_reason: str | None = None,
) -> tuple[float | None, str]:
    if returns is None or len(returns) < 2:
        return None, unavailable_reason or "at least two governed trading-day returns are required"
    deviation = float(returns.std(ddof=1))
    if not math.isfinite(deviation) or deviation <= 0:
        return None, "daily return standard deviation is zero or undefined"
    return float(math.sqrt(252.0) * returns.mean() / deviation), ""


def _daily_sortino(
    returns: pd.Series | None,
    *,
    unavailable_reason: str | None = None,
) -> tuple[float | None, str]:
    if returns is None or len(returns) < 2:
        return None, unavailable_reason or "at least two governed trading-day returns are required"
    downside = returns[returns < 0]
    if downside.empty:
        return None, "no negative daily returns; infinite values are not serialized"
    deviation = float(math.sqrt(float((downside**2).mean())))
    if not math.isfinite(deviation) or deviation <= 0:
        return None, "downside deviation is zero or undefined"
    return float(math.sqrt(252.0) * returns.mean() / deviation), ""


def _average_duration(trades: pd.DataFrame, entry_column: str | None, exit_column: str | None) -> float | None:
    if not entry_column or not exit_column:
        return None
    entry = pd.to_datetime(trades[entry_column], utc=True, errors="coerce")
    exit_ = pd.to_datetime(trades[exit_column], utc=True, errors="coerce")
    durations = (exit_ - entry).dt.total_seconds().div(60.0).dropna()
    if durations.empty or bool((durations < 0).any()):
        return None
    return float(durations.mean())


def _mean_column(trades: pd.DataFrame, column: str) -> float | None:
    if column not in trades.columns:
        return None
    values = pd.to_numeric(trades[column], errors="coerce").dropna()
    return float(values.mean()) if len(values) else None


def _cost_total(trades: pd.DataFrame) -> float | None:
    if "total_transaction_cost" in trades.columns:
        return float(pd.to_numeric(trades["total_transaction_cost"], errors="coerce").fillna(0).sum())
    available = [column for column in ("commission", "slippage_cost") if column in trades.columns]
    if not available:
        return None
    return float(sum(pd.to_numeric(trades[column], errors="coerce").fillna(0).sum() for column in available))


def _max_losing_streak(pnl: pd.Series) -> int:
    current = maximum = 0
    for value in pnl:
        if value < 0:
            current += 1
            maximum = max(maximum, current)
        else:
            current = 0
    return int(maximum)


def _prop_outcome(trades: pd.DataFrame, explicit: str | None) -> MetricValueV2:
    if explicit is not None:
        verdict = str(explicit).strip().upper()
        if verdict not in STRICT_VERDICTS:
            raise ValueError(f"prop_rule_outcome must be one of {sorted(STRICT_VERDICTS)}")
        return MetricValueV2(value=verdict)
    if trades.empty:
        return MetricValueV2(value=None, reason="no trades are available for prop-rule simulation")
    if "apex_rule_violation" in trades.columns:
        violations = trades["apex_rule_violation"].map(_strict_bool_or_none)
        if bool(violations.isna().any()):
            return MetricValueV2(
                value=None,
                reason="apex_rule_violation contains missing or ambiguous values",
            )
        return MetricValueV2(value="FAIL" if bool(violations.astype(bool).any()) else "PASS")
    return MetricValueV2(value=None, reason="prop-rule simulation outcome was not supplied")


def _flatten_compliance(trades: pd.DataFrame, explicit: bool | None) -> MetricValueV2:
    if explicit is not None:
        return MetricValueV2(value=bool(explicit))
    if trades.empty:
        return MetricValueV2(value=None, reason="no trades are available for forced-flatten review")
    if "position_flat_before_deadline" not in trades.columns:
        return MetricValueV2(
            value=None,
            reason="position_flat_before_deadline evidence was not supplied",
        )
    values = trades["position_flat_before_deadline"].map(_strict_bool_or_none)
    if bool(values.isna().any()):
        return MetricValueV2(
            value=None,
            reason="position_flat_before_deadline contains missing or ambiguous values",
        )
    return MetricValueV2(value=bool(values.astype(bool).all()))


def _strict_bool_or_none(value: Any) -> bool | None:
    if value is None or (not isinstance(value, (str, bool)) and pd.isna(value)):
        return None
    if isinstance(value, (bool, np.bool_)):
        return bool(value)
    if isinstance(value, (int, np.integer)) and value in {0, 1}:
        return bool(value)
    if isinstance(value, (float, np.floating)) and value in {0.0, 1.0}:
        return bool(value)
    if isinstance(value, str):
        normalized = value.strip().casefold()
        if normalized in {"true", "1", "yes"}:
            return True
        if normalized in {"false", "0", "no"}:
            return False
    return None


def _exchange_timezone(value: str) -> str:
    timezone = str(value or "").strip()
    if not timezone:
        raise ValueError("exchange_timezone is required for result breakdowns")
    try:
        ZoneInfo(timezone)
    except ZoneInfoNotFoundError as exc:
        raise ValueError(f"unknown exchange_timezone: {timezone}") from exc
    return timezone


def _timestamp_column(trades: pd.DataFrame, primary: str, fallback: str) -> str | None:
    if primary in trades.columns:
        return primary
    if fallback in trades.columns:
        return fallback
    return None


def _write_required_csv(output: Path, filename: str, frame: pd.DataFrame, empty_reason: str) -> ArtifactStatusV2:
    path = output / filename
    _atomic_write_frame(path, frame)
    digest = _file_sha256(path)
    if frame.empty:
        return ArtifactStatusV2(path=filename, available=False, rows=0, sha256=digest, reason=empty_reason)
    return ArtifactStatusV2(path=filename, available=True, rows=len(frame), sha256=digest)


def _write_optional_csv(
    output: Path,
    filename: str,
    frame: pd.DataFrame | None,
    missing_reason: str,
) -> ArtifactStatusV2:
    if frame is None:
        return ArtifactStatusV2(path=None, available=False, reason=missing_reason)
    path = output / filename
    _atomic_write_frame(path, frame)
    digest = _file_sha256(path)
    if frame.empty:
        return ArtifactStatusV2(path=filename, available=False, rows=0, sha256=digest, reason=f"{filename} is empty")
    return ArtifactStatusV2(path=filename, available=True, rows=len(frame), sha256=digest)


def _verdict_message(verdict: str, criteria: list[StageCriterionV2]) -> str:
    if verdict == "PASS":
        return "PASS — candidate strategy only; independent review and incubation are still required."
    unresolved = next((item for item in criteria if item.result != "PASS"), None)
    if verdict == "FAIL":
        return (
            f"FAIL — first failed criterion: {unresolved.metric}; {unresolved.reason}"
            if unresolved
            else "FAIL — the strategy did not satisfy the frozen research protocol."
        )
    return (
        f"NEEDS MANUAL REVIEW — first unresolved criterion: {unresolved.metric}; {unresolved.reason}"
        if unresolved
        else "NEEDS MANUAL REVIEW — required evidence is missing or ambiguous."
    )


def _aware_datetime(value: datetime | str | None) -> datetime:
    if value is None:
        result = datetime.now(UTC)
    elif isinstance(value, datetime):
        result = value
    else:
        try:
            result = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        except ValueError as exc:
            raise ValueError("generated_at must be ISO-8601") from exc
    if result.tzinfo is None or result.utcoffset() is None:
        raise ValueError("generated_at must be timezone-aware")
    return result


def _atomic_write_frame(path: Path, frame: pd.DataFrame) -> None:
    with NamedTemporaryFile(dir=path.parent, prefix=f".{path.name}.", suffix=".tmp", delete=False) as handle:
        temporary = Path(handle.name)
    try:
        frame.to_csv(temporary, index=False)
        with temporary.open("rb") as handle:
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def _atomic_write_bytes(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with NamedTemporaryFile(dir=path.parent, prefix=f".{path.name}.", suffix=".tmp", delete=False) as handle:
        temporary = Path(handle.name)
        handle.write(data)
        handle.flush()
        os.fsync(handle.fileno())
    try:
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def _file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()
