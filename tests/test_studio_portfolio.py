from __future__ import annotations

from datetime import date, timedelta
import hashlib
import json
from pathlib import Path

import pandas as pd
import pytest
import yaml
from fastapi import FastAPI
from fastapi.testclient import TestClient

from alphaquest.studio.api import register_api_routes
from alphaquest.studio.candidate_review import CandidateReviewService, CandidateReviewV1
from alphaquest.studio.portfolio import (
    AccountContractLimitsV1,
    CandidateEvidencePaths,
    DeploymentCandidateRequest,
    DeploymentDecisionService,
    DeploymentMonitoringService,
    ForwardIncubationBindingV1,
    MonitoringThresholdsV1,
    PortfolioReviewService,
)
from alphaquest.studio.results import ResultBundleBuilder, load_result_bundle


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _dates(start: date, count: int) -> list[date]:
    return [start + timedelta(days=index) for index in range(count)]


def _candidate(
    tmp_path: Path,
    *,
    campaign_id: str,
    pnl: list[float],
    session_dates: list[date],
    instrument: str = "ES",
    evaluation_dates: list[date] | None = None,
) -> CandidateEvidencePaths:
    run_dir = tmp_path / campaign_id / "run"
    reporting = run_dir / "reporting_v2"
    acceptance = run_dir / "acceptance_oos_test" / "trade_log.csv"
    acceptance.parent.mkdir(parents=True, exist_ok=True)
    evaluation_dates = evaluation_dates or session_dates
    trades = pd.DataFrame(
        [
            {
                "trade_id": index + 1,
                "direction": "long" if value >= 0 else "short",
                "entry_timestamp": f"{session}T14:30:00Z",
                "exit_timestamp": f"{session}T14:35:00Z",
                "session_date": session.isoformat(),
                "net_pnl": value,
                "r_multiple": value / 100.0,
                "slippage_cost": 2.0,
                "contracts": 1,
            }
            for index, (session, value) in enumerate(zip(session_dates, pnl))
        ]
    )
    trades.to_csv(acceptance, index=False)
    ResultBundleBuilder().build_and_write(
        trades,
        reporting,
        campaign_id=campaign_id,
        variant_id="v01",
        run_id=f"{campaign_id}-run",
        verdict="PASS",
        initial_balance=50_000.0,
        prop_rule_outcome="PASS",
        forced_flatten_compliance=True,
        evaluation_start=evaluation_dates[0],
        evaluation_end=evaluation_dates[-1],
        trading_dates=evaluation_dates,
        generated_at="2026-08-14T00:00:00+00:00",
    )
    bundle_path = reporting / "result_bundle_v2.json"
    config_path = tmp_path / campaign_id / "config.yaml"
    config_path.write_text(
        yaml.safe_dump(
            {
                "campaign_id": campaign_id,
                "variant_id": "v01",
                "attempt_id": "original",
                "symbol": instrument,
                "core": {"initial_balance": 50_000.0},
                "research_objectives": {"confirmed": True},
                "research_objectives_sha256": "f" * 64,
            },
            sort_keys=False,
        ),
        encoding="utf-8",
    )
    review = CandidateReviewV1(
        campaign_id=campaign_id,
        variant_id="v01",
        run_id=f"{campaign_id}-run",
        decision="approved_candidate",
        reviewer=f"reviewer-{campaign_id}",
        reviewed_at="2026-08-14T01:00:00+00:00",
        notes="Independent candidate assessment; candidate only.",
        result_bundle_sha256=_sha256(bundle_path),
        mechanics_approval_sha256="a" * 64,
        config_hash=f"governed-{campaign_id}",
        input_data_hash="b" * 64,
        mechanics_reviewer=f"mechanics-{campaign_id}",
        lifecycle_state="candidate",
    )
    review_path = reporting / "candidate_review.json"
    review_path.write_text(
        json.dumps(review.model_dump(mode="json", by_alias=True), sort_keys=True) + "\n",
        encoding="utf-8",
    )
    manifest_path = reporting / "finalization_manifest.json"
    summary_path = run_dir / "acceptance_oos_test/acceptance_oos_summary.json"
    summary_path.write_text(
        json.dumps(
            {
                "test_start": evaluation_dates[0].isoformat(),
                "test_end": evaluation_dates[-1].isoformat(),
            },
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
    calendar_path = run_dir / "acceptance_oos_test/validation/tradingview_comparison.csv"
    calendar_path.parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(
        {"session_date": [item.isoformat() for item in evaluation_dates]}
    ).to_csv(calendar_path, index=False)
    manifest_path.write_text(
        json.dumps(
            {
                "evidence_artifact_sha256": {
                    "acceptance_oos_test/trade_log.csv": _sha256(acceptance),
                    "acceptance_oos_test/acceptance_oos_summary.json": _sha256(summary_path),
                    "acceptance_oos_test/validation/tradingview_comparison.csv": _sha256(calendar_path),
                }
            },
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
    return CandidateEvidencePaths(
        result_bundle_path=bundle_path,
        candidate_review_path=review_path,
        config_path=config_path,
    )


@pytest.fixture
def governed_inspection(monkeypatch):
    def inspect_finalized(result_bundle_path, *, config_path=None):
        result_path = Path(result_bundle_path).resolve()
        manifest_path = result_path.parent / "finalization_manifest.json"
        return {
            "valid": True,
            "errors": [],
            "bundle": load_result_bundle(result_path),
            "manifest": json.loads(manifest_path.read_text(encoding="utf-8")),
            "manifest_path": manifest_path,
        }

    def inspect_candidate(self, *, candidate_review_path, result_bundle_path, config_path):
        review = CandidateReviewV1.model_validate_json(
            Path(candidate_review_path).read_text(encoding="utf-8")
        )
        errors = []
        if review.result_bundle_sha256 != _sha256(Path(result_bundle_path)):
            errors.append("result bundle hash is stale or mismatched")
        return {
            "valid": not errors,
            "lifecycle_state": review.lifecycle_state if not errors else "review_required",
            "errors": errors,
            "review": review,
        }

    monkeypatch.setattr("alphaquest.studio.portfolio.inspect_finalized_result", inspect_finalized)
    monkeypatch.setattr(CandidateReviewService, "inspect", inspect_candidate)


def test_portfolio_review_uses_only_hash_bound_common_acceptance_sessions(
    tmp_path: Path,
    governed_inspection,
):
    sessions = _dates(date(2025, 1, 2), 6)
    first = _candidate(
        tmp_path,
        campaign_id="first",
        pnl=[100.0, -40.0, 80.0, -20.0, 60.0, -10.0],
        session_dates=sessions,
    )
    second = _candidate(
        tmp_path,
        campaign_id="second",
        pnl=[-30.0, -10.0, 70.0, -15.0, 50.0, 20.0],
        session_dates=sessions,
    )
    service = PortfolioReviewService()

    review, path = service.create(
        candidates=[first, second],
        output_dir=tmp_path / "portfolio",
        minimum_common_sessions=5,
        generated_at="2026-08-14T03:00:00+00:00",
    )

    assert review.status == "READY_FOR_HUMAN_REVIEW"
    assert review.scientific_disposition == "NEEDS MANUAL REVIEW"
    assert review.automatic_deployment_permitted is False
    assert review.analysis.common_session_count == 6
    assert len(review.analysis.pairwise) == 1
    assert review.analysis.pairwise[0].overlapping_loss_days == 2
    assert review.analysis.combined_max_drawdown == pytest.approx(50.0)
    assert len(review.analysis.contributions) == 2
    assert service.inspect(path)["valid"] is True

    with pytest.raises(ValueError, match="cannot be overwritten"):
        service.create(
            candidates=[first, second],
            output_dir=tmp_path / "portfolio",
            minimum_common_sessions=5,
            generated_at="2026-08-14T03:00:00+00:00",
        )

    acceptance = Path(first.result_bundle_path).parent.parent / "acceptance_oos_test/trade_log.csv"
    acceptance.write_text(acceptance.read_text(encoding="utf-8") + "\n", encoding="utf-8")
    stale = service.inspect(path)
    assert stale["valid"] is False
    assert "hash drifted" in "; ".join(stale["errors"])


def test_portfolio_review_fails_closed_for_nonoverlap_or_too_few_common_sessions(
    tmp_path: Path,
    governed_inspection,
):
    first = _candidate(
        tmp_path,
        campaign_id="first",
        pnl=[10.0, -5.0, 20.0, -7.0, 5.0, 9.0],
        session_dates=_dates(date(2025, 1, 1), 6),
    )
    nonoverlap = _candidate(
        tmp_path,
        campaign_id="nonoverlap",
        pnl=[5.0, -2.0, 7.0, -4.0, 9.0, 1.0],
        session_dates=_dates(date(2025, 2, 1), 6),
    )
    with pytest.raises(ValueError, match="do not overlap"):
        PortfolioReviewService().create(
            candidates=[first, nonoverlap],
            output_dir=tmp_path / "portfolio-a",
            minimum_common_sessions=3,
        )

    partial = _candidate(
        tmp_path,
        campaign_id="partial",
        pnl=[7.0, -3.0, 4.0, -1.0, 6.0, 2.0],
        session_dates=_dates(date(2025, 1, 5), 6),
    )
    with pytest.raises(ValueError, match="too few common"):
        PortfolioReviewService().create(
            candidates=[first, partial],
            output_dir=tmp_path / "portfolio-b",
            minimum_common_sessions=3,
        )


def test_portfolio_common_calendar_includes_days_when_only_one_candidate_trades(
    tmp_path: Path,
    governed_inspection,
):
    calendar = _dates(date(2025, 3, 3), 4)
    first = _candidate(
        tmp_path,
        campaign_id="alternating_first",
        pnl=[100.0, -200.0],
        session_dates=[calendar[0], calendar[2]],
        evaluation_dates=calendar,
    )
    second = _candidate(
        tmp_path,
        campaign_id="alternating_second",
        pnl=[-50.0, 300.0],
        session_dates=[calendar[1], calendar[3]],
        evaluation_dates=calendar,
    )

    service = PortfolioReviewService()
    review, review_path = service.create(
        candidates=[first, second],
        output_dir=tmp_path / "portfolio-alternating",
        minimum_common_sessions=4,
        generated_at="2026-08-14T03:30:00+00:00",
    )

    assert review.analysis.common_session_count == 4
    assert review.analysis.common_sessions_with_any_trade == 4
    assert review.analysis.common_sessions_with_no_trades == 0
    assert review.analysis.zero_filled_candidate_sessions == 4
    assert review.analysis.combined_common_period_net_pnl == pytest.approx(150.0)
    assert review.analysis.combined_max_drawdown == pytest.approx(250.0)
    assert [item.observed_trade_sessions for item in review.analysis.contributions] == [2, 2]
    assert [item.zero_filled_sessions for item in review.analysis.contributions] == [2, 2]

    calendar_path = (
        Path(first.result_bundle_path).parent.parent
        / "acceptance_oos_test/validation/tradingview_comparison.csv"
    )
    calendar_path.unlink()
    stale = service.inspect(review_path)
    assert stale["valid"] is False
    assert "tradingview_comparison.csv" in "; ".join(stale["errors"])


def _limits() -> AccountContractLimitsV1:
    return AccountContractLimitsV1(
        account_label="paper-evaluation-account",
        maximum_total_contracts=4,
        maximum_contracts_per_candidate=2,
        instrument_contract_limits={"ES": 4},
        maximum_daily_loss_currency=1_000.0,
        maximum_total_drawdown_currency=2_000.0,
    )


def _monitoring_thresholds() -> MonitoringThresholdsV1:
    return MonitoringThresholdsV1(
        daily_loss_alert_currency=150.0,
        drawdown_alert_currency=200.0,
        retirement_review_drawdown_currency=400.0,
        losing_streak_alert=2,
        retirement_review_losing_streak=4,
        rolling_window_trades=4,
        minimum_rolling_expectancy_currency=-1_000.0,
        maximum_average_slippage_per_contract=10.0,
    )


def test_deployment_requires_forward_and_portfolio_review_and_never_routes_orders(
    tmp_path: Path,
    governed_inspection,
    monkeypatch,
):
    sessions = _dates(date(2025, 1, 2), 6)
    first = _candidate(
        tmp_path,
        campaign_id="first",
        pnl=[100.0, -40.0, 80.0, -20.0, 60.0, -10.0],
        session_dates=sessions,
    )
    second = _candidate(
        tmp_path,
        campaign_id="second",
        pnl=[-30.0, -10.0, 70.0, -15.0, 50.0, 20.0],
        session_dates=sessions,
    )
    portfolio, portfolio_path = PortfolioReviewService().create(
        candidates=[first, second],
        output_dir=tmp_path / "portfolio",
        minimum_common_sessions=5,
        generated_at="2026-08-14T03:00:00+00:00",
    )
    assert portfolio.status == "READY_FOR_HUMAN_REVIEW"

    def eligible_forward(*, project_root, candidate, attempt_id):
        return ForwardIncubationBindingV1(
            status="ELIGIBLE_FOR_REVIEW",
            plan_path=f"forward/{candidate.campaign_id}/plan.json",
            plan_sha256="1" * 64,
            events_path=f"forward/{candidate.campaign_id}/events.jsonl",
            events_sha256="2" * 64,
            event_count=3,
            last_event_sha256="3" * 64,
            governed_config_hash=f"governed-{candidate.campaign_id}",
            research_objectives_sha256="f" * 64,
        )

    monkeypatch.setattr("alphaquest.studio.portfolio._current_forward_binding", eligible_forward)
    requests = [
        DeploymentCandidateRequest(**first.__dict__, attempt_id="original", requested_contracts=1),
        DeploymentCandidateRequest(**second.__dict__, attempt_id="original", requested_contracts=1),
    ]
    service = DeploymentDecisionService(tmp_path)
    common = {
        "candidates": requests,
        "account_limits": _limits(),
        "rollback_criteria": ["Rollback if data feed or config identity changes."],
        "kill_criteria": ["Stop manually on a prop-rule or flatten breach."],
        "monitoring_thresholds": _monitoring_thresholds(),
        "reviewer": "deployment-reviewer",
        "decision": "APPROVE",
        "decision_notes": "Manual deployment approved after independent review.",
        "output_dir": tmp_path / "deployment",
        "decided_at": "2026-08-14T04:00:00+00:00",
    }
    with pytest.raises(ValueError, match="portfolio review"):
        service.decide(**common)

    decision, decision_path = service.decide(
        **common,
        portfolio_review_path=portfolio_path,
    )
    assert decision.deployment_state == "APPROVED_FOR_MANUAL_DEPLOYMENT"
    assert decision.order_submission_permitted is False
    assert decision.execution_capability == "none"
    inspected = service.inspect(decision_path)
    assert inspected["valid"] is True
    assert inspected["order_submission_permitted"] is False

    def ineligible_forward(*, project_root, candidate, attempt_id):
        raise ValueError("status is not ELIGIBLE_FOR_REVIEW")

    monkeypatch.setattr("alphaquest.studio.portfolio._current_forward_binding", ineligible_forward)
    blocked = dict(common)
    blocked["decided_at"] = "2026-08-14T04:01:00+00:00"
    with pytest.raises(ValueError, match="ELIGIBLE_FOR_REVIEW"):
        service.decide(**blocked, portfolio_review_path=portfolio_path)


def test_post_decision_monitoring_is_hash_chained_and_only_emits_review_states(
    tmp_path: Path,
    governed_inspection,
    monkeypatch,
):
    sessions = _dates(date(2025, 1, 2), 6)
    candidate = _candidate(
        tmp_path,
        campaign_id="first",
        pnl=[100.0, -40.0, 80.0, -20.0, 60.0, -10.0],
        session_dates=sessions,
    )

    def eligible_forward(*, project_root, candidate, attempt_id):
        return ForwardIncubationBindingV1(
            status="ELIGIBLE_FOR_REVIEW",
            plan_path="forward/first/plan.json",
            plan_sha256="1" * 64,
            events_path="forward/first/events.jsonl",
            events_sha256="2" * 64,
            event_count=3,
            last_event_sha256="3" * 64,
            governed_config_hash="governed-first",
            research_objectives_sha256="f" * 64,
        )

    monkeypatch.setattr("alphaquest.studio.portfolio._current_forward_binding", eligible_forward)
    decision, decision_path = DeploymentDecisionService(tmp_path).decide(
        candidates=[
            DeploymentCandidateRequest(
                **candidate.__dict__, attempt_id="original", requested_contracts=1
            )
        ],
        account_limits=_limits(),
        rollback_criteria=["Rollback if source evidence drifts."],
        kill_criteria=["Stop manually on a prop-rule breach."],
        monitoring_thresholds=_monitoring_thresholds(),
        reviewer="deployment-reviewer",
        decision="APPROVE",
        decision_notes="Approved for separate manual deployment only.",
        output_dir=tmp_path / "deployment",
        decided_at="2026-08-14T04:00:00+00:00",
    )
    assert decision.order_submission_permitted is False

    first_log = tmp_path / "monitoring-week-1.csv"
    pd.DataFrame(
        [
            {"session_date": "2026-08-17", "net_pnl": 100.0, "slippage_cost": 2.0, "contracts": 1},
            {"session_date": "2026-08-18", "net_pnl": 50.0, "slippage_cost": 2.0, "contracts": 1},
        ]
    ).to_csv(first_log, index=False)
    monitoring = DeploymentMonitoringService(
        project_root=tmp_path,
        deployment_decision_path=decision_path,
    )
    healthy = monitoring.append(
        source_trade_log_path=first_log,
        recorded_by="operations-reviewer",
        notes="First weekly manual observation.",
        recorded_at="2026-08-19T00:00:00+00:00",
    )
    assert healthy["status"] == "HEALTHY"
    assert healthy["order_submission_permitted"] is False

    second_log = tmp_path / "monitoring-week-2.csv"
    pd.DataFrame(
        [
            {"session_date": f"2026-08-{day}", "net_pnl": -100.0, "slippage_cost": 2.0, "contracts": 1}
            for day in range(19, 23)
        ]
    ).to_csv(second_log, index=False)
    retirement = monitoring.append(
        source_trade_log_path=second_log,
        recorded_by="operations-reviewer",
        notes="Loss threshold review observation.",
        recorded_at="2026-08-23T00:00:00+00:00",
    )
    assert retirement["status"] == "RETIREMENT_REVIEW"
    assert retirement["automatic_retirement_permitted"] is False
    assert retirement["metrics"]["maximum_drawdown"] == pytest.approx(400.0)

    governed_source = Path(retirement["events"][0]["source_trade_log_path"])
    governed_source.write_text(
        governed_source.read_text(encoding="utf-8") + "\n", encoding="utf-8"
    )
    stale = monitoring.detail()
    assert stale["status"] == "NEEDS MANUAL REVIEW"
    assert any("source hash drifted" in error for error in stale["errors"])


def test_lifecycle_api_uses_opaque_ids_and_server_resolved_governed_paths(
    tmp_path: Path,
    governed_inspection,
    monkeypatch,
):
    sessions = _dates(date(2025, 1, 2), 6)
    first = _candidate(
        tmp_path,
        campaign_id="first",
        pnl=[100.0, -40.0, 80.0, -20.0, 60.0, -10.0],
        session_dates=sessions,
    )
    second = _candidate(
        tmp_path,
        campaign_id="second",
        pnl=[-30.0, -10.0, 70.0, -15.0, 50.0, 20.0],
        session_dates=sessions,
    )

    def record(candidate_id: str, candidate: CandidateEvidencePaths, campaign_id: str):
        return {
            "candidate_id": candidate_id,
            "campaign_id": campaign_id,
            "variant_id": "v01",
            "attempt_id": "original",
            "run_id": f"{campaign_id}-run",
            "instrument": "ES",
            "result_bundle_sha256": _sha256(Path(candidate.result_bundle_path)),
            "candidate_review_sha256": _sha256(Path(candidate.candidate_review_path)),
            "config_sha256": _sha256(Path(candidate.config_path)),
            "candidate_reviewed_at": "2026-08-14T01:00:00+00:00",
            "_result_bundle_path": str(candidate.result_bundle_path),
            "_candidate_review_path": str(candidate.candidate_review_path),
            "_config_path": str(candidate.config_path),
        }

    discovered = [record("1" * 64, first, "first"), record("2" * 64, second, "second")]
    monkeypatch.setattr(
        "alphaquest.studio.api._lifecycle_candidate_summaries",
        lambda root: discovered,
    )

    def eligible_forward(*, project_root, candidate, attempt_id):
        return ForwardIncubationBindingV1(
            status="ELIGIBLE_FOR_REVIEW",
            plan_path=f"forward/{candidate.campaign_id}/plan.json",
            plan_sha256="1" * 64,
            events_path=f"forward/{candidate.campaign_id}/events.jsonl",
            events_sha256="2" * 64,
            event_count=3,
            last_event_sha256="3" * 64,
            governed_config_hash=f"governed-{candidate.campaign_id}",
            research_objectives_sha256="f" * 64,
        )

    monkeypatch.setattr("alphaquest.studio.portfolio._current_forward_binding", eligible_forward)
    app = FastAPI()
    register_api_routes(app, tmp_path)
    client = TestClient(app)

    candidates = client.get("/api/lifecycle/candidates")
    assert candidates.status_code == 200
    assert [item["candidate_id"] for item in candidates.json()["items"]] == ["1" * 64, "2" * 64]
    assert "_result_bundle_path" not in candidates.text
    assert str(tmp_path) not in candidates.text

    arbitrary_path = client.post(
        "/api/portfolio-reviews",
        json={
            "candidate_ids": ["1" * 64, "2" * 64],
            "minimum_common_sessions": 5,
            "result_bundle_path": "/tmp/not-authorized.json",
        },
    )
    assert arbitrary_path.status_code == 422

    portfolio_response = client.post(
        "/api/portfolio-reviews",
        json={"candidate_ids": ["1" * 64, "2" * 64], "minimum_common_sessions": 5},
    )
    assert portfolio_response.status_code == 201, portfolio_response.text
    portfolio_payload = portfolio_response.json()
    assert portfolio_payload["valid"] is True
    assert portfolio_payload["automatic_deployment_permitted"] is False
    assert str(tmp_path) not in portfolio_response.text

    deployment_response = client.post(
        "/api/deployment-decisions",
        json={
            "candidates": [
                {"candidate_id": "1" * 64, "attempt_id": "original", "requested_contracts": 1},
                {"candidate_id": "2" * 64, "attempt_id": "original", "requested_contracts": 1},
            ],
            "portfolio_review_id": portfolio_payload["review_id"],
            "account_limits": _limits().model_dump(mode="json"),
            "rollback_criteria": ["Rollback if the governed data or config identity changes."],
            "kill_criteria": ["Stop manually on a prop-rule or flatten breach."],
            "monitoring_thresholds": _monitoring_thresholds().model_dump(mode="json"),
            "reviewer": "deployment-reviewer",
            "decision": "APPROVE",
            "decision_notes": "Explicit human approval for separate manual deployment only.",
        },
    )
    assert deployment_response.status_code == 201, deployment_response.text
    deployment_payload = deployment_response.json()
    assert deployment_payload["valid"] is True
    assert deployment_payload["order_submission_permitted"] is False
    assert deployment_payload["execution_capability"] == "none"
    assert str(tmp_path) not in deployment_response.text

    monitoring_csv = (
        "session_date,net_pnl,slippage_cost,contracts\n"
        "2026-01-02,100,2,1\n"
        "2026-01-05,50,2,1\n"
    )
    upload = client.post(
        "/api/deployment-monitoring/evidence/upload",
        params={"filename": "paper-observations.csv"},
        content=monitoring_csv.encode("utf-8"),
    )
    assert upload.status_code == 201, upload.text
    monitoring = client.post(
        f"/api/deployment-decisions/{deployment_payload['decision_id']}/monitoring",
        json={
            "upload_token": upload.json()["upload_token"],
            "recorded_by": "operations-reviewer",
            "notes": "First source-bound paper observation.",
        },
    )
    assert monitoring.status_code == 201, monitoring.text
    assert monitoring.json()["status"] == "HEALTHY"
    assert monitoring.json()["order_submission_permitted"] is False
    assert "source_trade_log_path" not in monitoring.text
    assert str(tmp_path) not in monitoring.text
