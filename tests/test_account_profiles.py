from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from pathlib import Path

import pandas as pd

from alphaquest.accounts.assessment import run_account_monte_carlo, run_governed_account_assessment
from alphaquest.accounts.catalog import AccountProfileCatalog
from alphaquest.accounts.models import AccountAssessmentCostsV1
from alphaquest.accounts.simulator import evaluate_account_trade_path
from alphaquest.studio.api import _account_assessment_rows
from alphaquest.studio.results import ResultBundleBuilder, build_result_bundle_v3


FUNDED_ATTESTATION = "no_prohibited_trading_activity_or_cross_account_hedging"
EVALUATION_ATTESTATION = "no_cross_account_hedging_or_rule_circumvention"


def _costs(total: float = 100.0) -> AccountAssessmentCostsV1:
    return AccountAssessmentCostsV1(
        evaluation_purchase_price=total,
        activation_fee=0.0,
        observed_at=datetime(2026, 8, 14, tzinfo=timezone.utc),
        source="Apex checkout snapshot supplied by test",
    )


def _weekday_dates(count: int) -> list[date]:
    result = []
    current = date(2024, 1, 2)
    while len(result) < count:
        if current.weekday() < 5:
            result.append(current)
        current += timedelta(days=1)
    return result


def _funded_path(count: int = 126) -> pd.DataFrame:
    rows = []
    for index, session_date in enumerate(_weekday_dates(count)):
        pnl = 720.0 if index < 5 else 60.0 if index % 10 in {0, 5} else 0.0
        rows.append(
            {
                "trade_id": index + 1,
                "session_date": session_date,
                "net_pnl": pnl,
                "contracts": 1,
                "mae_currency": 100.0,
                "forced_flatten_compliant": True,
            }
        )
    return pd.DataFrame(rows)


def test_catalog_exposes_reviewed_apex_phases_and_nonpromotable_synthetic_profile() -> None:
    catalog = AccountProfileCatalog(".")

    evaluation = catalog.resolve("apex/eod_50k/evaluation", "2026-03-01")
    funded = catalog.resolve("apex/eod_50k/funded", "2026-03-01")
    synthetic = catalog.resolve("synthetic/vendor_neutral/funded", "v1")

    assert evaluation.profile.identity.account_kind == "prop_challenge"
    assert funded.profile.identity.account_kind == "prop_funded"
    assert funded.profile.rules.eod_drawdown.locked_threshold == 50_100.0
    assert funded.profile.rules.payouts.payout_caps == [1500.0, 1500.0, 2000.0, 2500.0, 2500.0, 3000.0]
    assert funded.profile.rules.scaling_tiers[0].maximum_contracts == 2
    assert len(funded.sha256) == 64
    assert synthetic.profile.promotable is False


def test_catalog_list_exposes_complete_browser_rule_contract_without_source_path() -> None:
    funded = next(
        item
        for item in AccountProfileCatalog(".").list()
        if item["profile_id"] == "apex/eod_50k/funded"
    )

    assert funded["identity"]["account_kind"] == "prop_funded"
    assert funded["rules"]["eod_drawdown"]["recalculation"] == "end_of_day"
    assert funded["rules"]["payouts"]["minimum_payout"] == 500.0
    assert funded["evaluation_policy"]["monte_carlo_runs"] == 8000
    assert funded["provenance"]["official_sources"]
    assert "profile_source_path" not in funded


def test_eod_profile_fails_closed_without_intraday_equity_evidence_and_costs() -> None:
    profile = AccountProfileCatalog(".").resolve("apex/eod_50k/funded").profile
    trades = pd.DataFrame(
        [{"session_date": "2024-01-02", "net_pnl": 100.0, "contracts": 1}]
    )

    result = evaluate_account_trade_path(trades, profile)

    assert result.summary["verdict"] == "NEEDS MANUAL REVIEW"
    assert any("intraday equity" in issue for issue in result.summary["unresolved"])
    assert any("checkout" in issue for issue in result.summary["unresolved"])


def test_apex_funded_path_models_threshold_lock_payout_and_inactivity() -> None:
    profile = AccountProfileCatalog(".").resolve("apex/eod_50k/funded").profile

    result = evaluate_account_trade_path(
        _funded_path(),
        profile,
        costs=_costs(),
        manual_attestations=[FUNDED_ATTESTATION],
    )

    assert result.summary["verdict"] == "PASS"
    assert result.summary["account_closed"] is False
    assert result.summary["daily_loss_lock_count"] == 0
    assert result.summary["payout_count"] >= 1
    assert result.summary["gross_payouts"] >= 1500.0
    assert result.summary["net_payout_after_costs"] > 0
    assert result.daily["eod_threshold"].max() == 50_100.0
    assert result.summary["inactivity_breach"] is False


def test_apex_funded_profile_rejects_initial_three_contract_trade() -> None:
    profile = AccountProfileCatalog(".").resolve("apex/eod_50k/funded").profile
    trades = _funded_path()
    trades.loc[0, "contracts"] = 3

    result = evaluate_account_trade_path(
        trades,
        profile,
        costs=_costs(),
        manual_attestations=[FUNDED_ATTESTATION],
    )

    assert result.summary["verdict"] == "FAIL"
    assert result.summary["position_rejection_count"] == 1
    assert "position_size_rejected" in set(result.events["event"])


def test_apex_eod_threshold_touch_closes_account_intraday() -> None:
    profile = AccountProfileCatalog(".").resolve("apex/eod_50k/funded").profile
    trades = _funded_path()
    trades.loc[0, "mae_currency"] = 2000.0

    result = evaluate_account_trade_path(
        trades,
        profile,
        costs=_costs(),
        manual_attestations=[FUNDED_ATTESTATION],
    )

    assert result.summary["verdict"] == "FAIL"
    assert result.summary["account_closed"] is True
    assert result.summary["closure_reason"] == "eod_drawdown_threshold"


def test_account_monte_carlo_reports_risk_and_cost_adjusted_payout_metrics() -> None:
    resolved = AccountProfileCatalog(".").resolve("apex/eod_50k/funded")

    results, summary = run_account_monte_carlo(
        _funded_path(),
        resolved,
        costs=_costs(),
        manual_attestations=[FUNDED_ATTESTATION],
        runs=20,
        seed=19,
    )

    assert len(results) == 20
    assert summary["number_of_runs"] == 20
    assert 0 <= summary["probability_account_closed"] <= 1
    assert 0 <= summary["probability_first_payout"] <= 1
    assert summary["expected_net_payout_after_costs"] is not None
    assert summary["expected_payout_to_cost_ratio"] is not None
    assert summary["expected_replacement_cost"] is not None
    assert summary["expected_net_payout_after_expected_replacement_cost"] is not None
    assert {item["metric"] for item in summary["criteria"]} >= {
        "probability_account_closed",
        "probability_first_payout",
        "expected_payout_to_cost_ratio",
    }


def test_challenge_expires_after_30_calendar_days_and_reports_retry_adjusted_fee() -> None:
    resolved = AccountProfileCatalog(".").resolve("apex/eod_50k/evaluation")
    trades = pd.DataFrame(
        [
            {
                "session_date": session_date,
                "net_pnl": 100.0,
                "contracts": 1,
                "mae_currency": 25.0,
                "forced_flatten_compliant": True,
            }
            for session_date in _weekday_dates(60)
        ]
    )

    deterministic = evaluate_account_trade_path(
        trades,
        resolved.profile,
        costs=_costs(80.0),
        manual_attestations=[EVALUATION_ATTESTATION],
    )
    assert deterministic.summary["verdict"] == "FAIL"
    assert deterministic.summary["closure_reason"] == "evaluation_access_period_expired"

    faster = trades.copy()
    faster["net_pnl"] = 250.0
    _, summary = run_account_monte_carlo(
        faster,
        resolved,
        costs=_costs(80.0),
        manual_attestations=[EVALUATION_ATTESTATION],
        runs=20,
        seed=5,
    )
    assert summary["probability_target_reached"] > 0
    assert summary["expected_evaluation_fees_per_pass"] >= 80.0
    assert summary["verdict"] == "NEEDS MANUAL REVIEW"
    assert any("8000" in issue for issue in summary["unresolved"])


def test_position_close_deadline_violation_is_a_deterministic_failure() -> None:
    profile = AccountProfileCatalog(".").resolve("apex/eod_50k/funded").profile
    trades = _funded_path()
    trades.loc[0, "forced_flatten_compliant"] = False

    result = evaluate_account_trade_path(
        trades,
        profile,
        costs=_costs(),
        manual_attestations=[FUNDED_ATTESTATION],
    )

    assert result.summary["verdict"] == "FAIL"
    assert result.summary["position_close_violation_count"] == 1


def test_governed_assessment_writes_new_hash_bound_transaction(tmp_path: Path) -> None:
    resolved = AccountProfileCatalog(".").resolve("apex/eod_50k/evaluation")
    trades = pd.DataFrame(
        [
            {
                "trade_id": index + 1,
                "session_date": session_date,
                "net_pnl": 200.0,
                "contracts": 1,
                "mae_currency": 50.0,
                "forced_flatten_compliant": True,
            }
            for index, session_date in enumerate(_weekday_dates(60))
        ]
    )

    output_root = tmp_path / "research_artifacts"
    manifest = run_governed_account_assessment(
        trades,
        resolved,
        output_root,
        campaign_id="example",
        variant_id="v01",
        attempt_id="original",
        config_sha256="a" * 64,
        data_sha256="b" * 64,
        strategy_implementation_sha256="c" * 64,
        costs=_costs(),
        manual_attestations=[EVALUATION_ATTESTATION],
        runs=5,
    )

    directory = Path(manifest["assessment_path"])
    assert (directory / "evaluation_manifest.json").is_file()
    assert (directory / "account_profile_snapshot.json").is_file()
    assert (directory / "deterministic_summary.json").is_file()
    assert (directory / "monte_carlo_summary.json").is_file()
    assert manifest["profile_sha256"] == resolved.sha256
    assert len(manifest["manifest_sha256"]) == 64

    rows = _account_assessment_rows(tmp_path, "example")
    assert len(rows) == 1
    assert rows[0]["profile_id"] == "apex/eod_50k/evaluation"

    reporting_trades = trades.assign(
        entry_timestamp=lambda frame: pd.to_datetime(frame["session_date"]).astype(str) + "T14:30:00Z",
        exit_timestamp=lambda frame: pd.to_datetime(frame["session_date"]).astype(str) + "T15:00:00Z",
        direction="long",
        r_multiple=1.0,
        gross_pnl=lambda frame: frame["net_pnl"],
        commission=0.0,
        slippage_cost=0.0,
        position_flat_before_deadline=True,
    )
    result_dir = tmp_path / "result"
    ResultBundleBuilder().build_and_write(
        reporting_trades,
        result_dir,
        campaign_id="example",
        variant_id="v01",
        run_id="original",
        verdict="PASS",
        scientific_validity_verdict="PASS",
        stage_criteria=[
            {
                "stage": "acceptance_oos_test",
                "metric": "metrics.annualization_available",
                "operator": "==",
                "threshold": {"value": True},
                "actual": {"value": True},
                "result": "PASS",
                "reason": "governed evaluation coverage is complete",
                "decision_role": "scientific_validity",
            }
        ],
        evaluation_start=_weekday_dates(60)[0],
        evaluation_end=_weekday_dates(60)[-1],
    )
    bundle = build_result_bundle_v3(
        result_dir / "result_bundle_v2.json",
        [directory / "evaluation_manifest.json"],
        result_dir / "result_bundle_v3.json",
    )
    assert bundle.scientific_verdict == "PASS"
    assert bundle.scientific_validity_verdict == "PASS"
    assert bundle.account_evaluations[0].destination_candidate_eligible is (
        bundle.account_evaluations[0].verdict == "PASS"
    )
    assert bundle.account_evaluations[0].profile_id == "apex/eod_50k/evaluation"
    assert bundle.deployment_authorized is False
