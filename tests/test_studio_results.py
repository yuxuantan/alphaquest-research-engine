from __future__ import annotations

import json
import math

import pandas as pd
import pytest
from pydantic import ValidationError

from alphaquest.studio.results import (
    MetricValueV2,
    RESULT_BUNDLE_FILENAME,
    ResultBundleV2,
    ResultBundleBuilder,
    load_result_bundle,
)
from alphaquest.studio.schemas import stale_studio_schema_documents, write_studio_schema_documents


def _trades() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "trade_id": 1,
                "direction": "long",
                "entry_timestamp": "2025-01-02T14:30:00Z",
                "exit_timestamp": "2025-01-02T14:45:00Z",
                "net_pnl": 100.0,
                "r_multiple": 2.0,
                "commission": 5.0,
                "slippage_cost": 12.5,
                "apex_rule_violation": False,
                "position_flat_before_deadline": True,
            },
            {
                "trade_id": 2,
                "direction": "short",
                "entry_timestamp": "2025-01-03T15:30:00Z",
                "exit_timestamp": "2025-01-03T16:00:00Z",
                "net_pnl": -50.0,
                "r_multiple": -1.0,
                "commission": 5.0,
                "slippage_cost": 12.5,
                "apex_rule_violation": False,
                "position_flat_before_deadline": True,
            },
            {
                "trade_id": 3,
                "direction": "long",
                "entry_timestamp": "2025-02-03T14:30:00Z",
                "exit_timestamp": "2025-02-03T14:35:00Z",
                "net_pnl": 30.0,
                "r_multiple": 0.5,
                "commission": 5.0,
                "slippage_cost": 12.5,
                "apex_rule_violation": False,
                "position_flat_before_deadline": True,
            },
            {
                "trade_id": 4,
                "direction": "short",
                "entry_timestamp": "2025-02-04T17:30:00Z",
                "exit_timestamp": "2025-02-04T17:40:00Z",
                "net_pnl": -20.0,
                "r_multiple": -0.5,
                "commission": 5.0,
                "slippage_cost": 12.5,
                "apex_rule_violation": False,
                "position_flat_before_deadline": True,
            },
        ]
    )


def test_result_bundle_writes_strict_metrics_and_stable_breakdowns(tmp_path):
    bundle = ResultBundleBuilder().build_and_write(
        _trades(),
        tmp_path,
        campaign_id="demo",
        variant_id="v01",
        run_id="run-1",
        verdict="PASS",
        initial_balance=10_000.0,
        evaluation_start="2025-01-01",
        evaluation_end="2025-12-31",
        trading_dates=pd.date_range("2025-01-01", "2025-12-31", freq="B").date.tolist(),
        stage_criteria=[
            {
                "stage": "acceptance",
                "metric": "profit_factor",
                "operator": ">=",
                "threshold": {"value": 1.2},
                "actual": {"value": 130.0 / 70.0},
                "result": "PASS",
                "reason": "actual 1.857 exceeded required 1.2",
                "evidence_path": "acceptance/metrics.json",
            }
        ],
    )

    assert bundle.metrics.net_profit_after_costs.value == 60.0
    assert bundle.metrics.total_transaction_costs.value == 70.0
    assert bundle.metrics.profit_factor.value == pytest.approx(130.0 / 70.0)
    assert bundle.metrics.expectancy_currency.value == 15.0
    assert bundle.metrics.expectancy_r.value == 0.25
    assert bundle.metrics.average_trade_duration_minutes.value == 15.0
    assert bundle.metrics.payoff_ratio.value == pytest.approx(65.0 / 35.0)
    assert bundle.metrics.max_losing_streak.value == 1
    assert bundle.metrics.prop_rule_outcome.value == "PASS"
    assert bundle.metrics.forced_flatten_compliance.value is True
    assert "candidate strategy only" in bundle.verdict_message

    for filename in (
        "yearly_breakdown.csv",
        "monthly_breakdown.csv",
        "entry_session_breakdown.csv",
        "side_breakdown.csv",
        "equity_curve.csv",
        "drawdown_curve.csv",
        RESULT_BUNDLE_FILENAME,
    ):
        assert (tmp_path / filename).is_file()
    assert len(pd.read_csv(tmp_path / "monthly_breakdown.csv")) == 2
    assert set(pd.read_csv(tmp_path / "side_breakdown.csv")["side"]) == {"long", "short"}

    raw = (tmp_path / RESULT_BUNDLE_FILENAME).read_text(encoding="utf-8")
    assert "Infinity" not in raw
    assert "NaN" not in raw
    assert json.loads(raw)["schema"] == "alphaquest.result-bundle/v2"
    assert load_result_bundle(tmp_path / RESULT_BUNDLE_FILENAME) == bundle


def test_annualized_metrics_use_governed_period_not_first_and_last_trade(tmp_path):
    trades = _trades().iloc[[0, 1]].copy()
    bundle = ResultBundleBuilder().build_and_write(
        trades,
        tmp_path,
        campaign_id="demo",
        variant_id="v01",
        run_id="governed-window",
        verdict="FAIL",
        initial_balance=10_000.0,
        evaluation_start="2025-01-01",
        evaluation_end="2025-12-31",
        trading_dates=pd.date_range("2025-01-01", "2025-12-31", freq="B").date.tolist(),
    )

    years = 365 / 365.25
    expected_cagr = (10_050.0 / 10_000.0) ** (1 / years) - 1
    expected_drawdown_pct = 50.0 / 10_100.0
    assert bundle.metrics.trades_per_year.value == pytest.approx(2 / years)
    assert bundle.metrics.mar.value == pytest.approx(expected_cagr / expected_drawdown_pct)


def test_annualized_metrics_are_undefined_without_governed_period(tmp_path):
    bundle = ResultBundleBuilder().build_and_write(
        _trades(),
        tmp_path,
        campaign_id="demo",
        variant_id="v01",
        run_id="missing-window",
        verdict="NEEDS MANUAL REVIEW",
        initial_balance=10_000.0,
    )

    assert bundle.metrics.trades_per_year.value is None
    assert "governed evaluation-period" in bundle.metrics.trades_per_year.reason
    assert bundle.metrics.mar.value is None
    assert "governed evaluation-period" in bundle.metrics.mar.reason
    assert bundle.metrics.daily_sharpe.value is None
    assert "governed evaluation-period" in bundle.metrics.daily_sharpe.reason


def test_daily_risk_metrics_include_zero_trade_days_from_governed_coverage(tmp_path):
    trades = _trades().iloc[[0, 1]].copy()
    coverage = ["2025-01-02", "2025-01-03", "2025-01-06", "2025-01-07"]
    bundle = ResultBundleBuilder().build_and_write(
        trades,
        tmp_path,
        campaign_id="demo",
        variant_id="v01",
        run_id="daily-coverage",
        verdict="FAIL",
        initial_balance=10_000.0,
        evaluation_start="2025-01-02",
        evaluation_end="2025-01-07",
        trading_dates=coverage,
    )

    expected_returns = pd.Series([0.01, -50.0 / 10_100.0, 0.0, 0.0])
    expected_sharpe = (252.0**0.5) * expected_returns.mean() / expected_returns.std(ddof=1)
    downside = expected_returns[expected_returns < 0]
    expected_sortino = (252.0**0.5) * expected_returns.mean() / ((downside**2).mean() ** 0.5)
    assert bundle.metrics.daily_sharpe.value == pytest.approx(expected_sharpe)
    assert bundle.metrics.daily_sortino.value == pytest.approx(expected_sortino)

    coerced = bundle.model_dump(mode="python", by_alias=True)
    coerced["campaign_id"] = 123
    with pytest.raises(ValidationError, match="string_type"):
        ResultBundleV2.model_validate(coerced)


def test_undefined_profit_factor_is_null_with_reason_never_infinity(tmp_path):
    trades = _trades().iloc[[0, 2]].copy()

    bundle = ResultBundleBuilder().build_and_write(
        trades,
        tmp_path,
        campaign_id="demo",
        variant_id="v01",
        run_id="run-2",
        verdict="NEEDS MANUAL REVIEW",
        initial_balance=10_000.0,
    )

    assert bundle.metrics.profit_factor.value is None
    assert "infinite" in bundle.metrics.profit_factor.reason
    raw = (tmp_path / RESULT_BUNDLE_FILENAME).read_text(encoding="utf-8")
    assert '"value": null' in raw
    assert "Infinity" not in raw


def test_nonfinite_metric_values_are_rejected():
    with pytest.raises(ValidationError, match="finite"):
        MetricValueV2(value=math.inf)


def test_invalid_trade_pnl_fails_closed(tmp_path):
    trades = _trades()
    trades.loc[0, "net_pnl"] = float("nan")

    with pytest.raises(ValueError, match="missing or non-finite"):
        ResultBundleBuilder().build_and_write(
            trades,
            tmp_path,
            campaign_id="demo",
            variant_id="v01",
            run_id="run-3",
            verdict="FAIL",
        )


def test_breakdowns_use_exchange_timezone_not_utc(tmp_path):
    trades = _trades().iloc[[0]].copy()
    trades.loc[:, "entry_timestamp"] = "2025-01-01T00:30:00Z"
    trades.loc[:, "exit_timestamp"] = "2025-01-01T00:45:00Z"

    ResultBundleBuilder().build_and_write(
        trades,
        tmp_path,
        campaign_id="demo",
        variant_id="v01",
        run_id="timezone-run",
        verdict="FAIL",
        exchange_timezone="America/New_York",
    )

    assert pd.read_csv(tmp_path / "yearly_breakdown.csv")["year"].astype(str).tolist() == ["2024"]
    assert pd.read_csv(tmp_path / "monthly_breakdown.csv")["month"].tolist() == ["2024-12"]
    assert pd.read_csv(tmp_path / "entry_session_breakdown.csv")["entry_session"].tolist() == [
        "19:00-19:59"
    ]


def test_forced_flatten_compliance_uses_position_deadline_field_only(tmp_path):
    trades = _trades().iloc[[0, 1]].copy()
    trades.loc[:, "apex_rule_violation"] = [True, False]
    trades.loc[:, "position_flat_before_deadline"] = [True, True]

    compliant = ResultBundleBuilder().build_and_write(
        trades,
        tmp_path / "compliant",
        campaign_id="demo",
        variant_id="v01",
        run_id="flatten-compliant",
        verdict="FAIL",
    )

    assert compliant.metrics.prop_rule_outcome.value == "FAIL"
    assert compliant.metrics.forced_flatten_compliance.value is True

    trades.loc[1, "position_flat_before_deadline"] = False
    breached = ResultBundleBuilder().build_and_write(
        trades,
        tmp_path / "breached",
        campaign_id="demo",
        variant_id="v01",
        run_id="flatten-breached",
        verdict="FAIL",
    )
    assert breached.metrics.forced_flatten_compliance.value is False

    missing = ResultBundleBuilder().build_and_write(
        trades.drop(columns=["position_flat_before_deadline"]),
        tmp_path / "missing",
        campaign_id="demo",
        variant_id="v01",
        run_id="flatten-missing",
        verdict="FAIL",
    )
    assert missing.metrics.forced_flatten_compliance.value is None
    assert "position_flat_before_deadline" in missing.metrics.forced_flatten_compliance.reason


def test_committed_studio_schemas_match_owning_models(tmp_path):
    assert stale_studio_schema_documents("schemas") == []

    written = write_studio_schema_documents(tmp_path)

    assert {path.name for path in written} == {
        "candidate-review-v1.schema.json",
        "job-record-v1.schema.json",
        "result-bundle-v2.schema.json",
    }
    assert stale_studio_schema_documents(tmp_path) == []
