from __future__ import annotations

from datetime import UTC, datetime, timedelta
import hashlib
import json
from pathlib import Path
from typing import Any

from fastapi import FastAPI
from fastapi.testclient import TestClient
import pytest
import yaml

from alphaquest.studio.api import register_api_routes
from alphaquest.studio.candidate_review import CandidateReviewV1
from alphaquest.studio.forward_incubation import ForwardIncubationService


class MutableClock:
    def __init__(self, value: datetime) -> None:
        self.value = value

    def __call__(self) -> datetime:
        return self.value


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _object_sha256(value: Any) -> str:
    encoded = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _evidence(root: Path, name: str = "paper_observations.csv") -> Path:
    path = root / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("session,trades,net_pnl\n2026-01-02,1,25.0\n", encoding="utf-8")
    return path


def _objectives(*, days: int = 30, trades: int = 1) -> dict[str, Any]:
    return {
        "schema": "alphaquest.research-objectives/v1",
        "development_goal": "Determine whether this candidate is robust enough for continued review.",
        "development_deadline": "2028-12-31",
        "evaluation_horizon_months": 24,
        "minimum_annualized_return_fraction": 0.1,
        "minimum_mar": 0.8,
        "maximum_drawdown_fraction": 0.1,
        "minimum_complete_wfa_windows": 3,
        "minimum_wfa_oos_trades": 50,
        "minimum_acceptance_oos_trades": 50,
        "monte_carlo_min_runs": 8000,
        "monte_carlo_horizon_months": 12,
        "minimum_net_profit_probability": 0.7,
        "maximum_account_breach_probability": 0.1,
        "forward_incubation_min_calendar_days": days,
        "forward_incubation_min_trades": trades,
        "maximum_variants": 5,
        "abandonment_rules": ["Any prop-rule breach", "Any forced-flatten violation"],
        "retirement_rules": ["Edge no longer survives current transaction costs"],
        "confirmed": True,
    }


def _candidate_fixture(
    root: Path,
    *,
    reviewed_at: datetime,
    days: int = 30,
    trades: int = 1,
) -> tuple[Path, Path, Path]:
    reporting = root / "research/evidence/runs/demo/v01/ES/run_1/reporting_v2"
    reporting.mkdir(parents=True)
    result_path = reporting / "result_bundle_v2.json"
    result_path.write_text('{"fixture":"terminal candidate PASS"}\n', encoding="utf-8")
    config_path = root / "research/campaigns/active/demo/variants/v01/config.yaml"
    config_path.parent.mkdir(parents=True)
    objectives = _objectives(days=days, trades=trades)
    config_path.write_text(
        yaml.safe_dump(
            {
                "campaign_id": "demo",
                "variant_id": "v01",
                "attempt_id": "original",
                "research_objectives": objectives,
                "research_objectives_sha256": _object_sha256(objectives),
            },
            sort_keys=True,
        ),
        encoding="utf-8",
    )
    review = CandidateReviewV1(
        campaign_id="demo",
        variant_id="v01",
        run_id="run_1",
        decision="approved_candidate",
        reviewer="candidate-reviewer",
        reviewed_at=reviewed_at,
        notes="Independent candidate review passed; true forward incubation remains mandatory.",
        result_bundle_sha256=_sha256(result_path),
        mechanics_approval_sha256="a" * 64,
        config_hash="b" * 64,
        input_data_hash="c" * 64,
        mechanics_reviewer="mechanics-reviewer",
        lifecycle_state="candidate",
    )
    review_path = reporting / "candidate_review.json"
    review_path.write_text(
        json.dumps(review.model_dump(mode="json", by_alias=True), sort_keys=True) + "\n",
        encoding="utf-8",
    )
    (reporting / "finalization_manifest.json").write_text(
        json.dumps({"source_config": str(config_path.resolve())}) + "\n",
        encoding="utf-8",
    )
    return review_path, result_path, config_path


@pytest.fixture
def valid_candidate_inspection(monkeypatch: pytest.MonkeyPatch):
    def inspect(_self, *, candidate_review_path, result_bundle_path, config_path):
        review = CandidateReviewV1.model_validate(
            json.loads(Path(candidate_review_path).read_text(encoding="utf-8"))
        )
        return {"valid": True, "lifecycle_state": review.lifecycle_state, "errors": [], "review": review}

    monkeypatch.setattr("alphaquest.studio.forward_incubation.CandidateReviewService.inspect", inspect)


def test_forward_incubation_is_immutable_hash_bound_and_never_auto_passes(
    tmp_path: Path,
    valid_candidate_inspection,
) -> None:
    start = datetime(2026, 1, 2, 14, 0, tzinfo=UTC)
    review_path, result_path, config_path = _candidate_fixture(
        tmp_path,
        reviewed_at=start - timedelta(days=1),
    )
    clock = MutableClock(start)
    service = ForwardIncubationService(tmp_path, clock=clock)

    created = service.start_from_paths(
        candidate_review_path=review_path,
        result_bundle_path=result_path,
        config_path=config_path,
        expected_campaign_id="demo",
        expected_variant_id="v01",
        expected_attempt_id="original",
        created_by="incubation-owner",
    )

    assert created["status"] == "ACTIVE"
    assert created["minimum_calendar_days"] == 90
    assert created["minimum_trades"] == 30
    assert created["automatic_pass_permitted"] is False
    record_dir = tmp_path / "research_artifacts/forward_incubation/demo/v01/original"
    frozen_plan = (record_dir / "plan.json").read_bytes()
    evidence = _evidence(tmp_path)

    clock.value = start + timedelta(days=90)
    eligible = service.append_observation(
        "demo",
        "v01",
        "original",
        recorded_by="paper-operator",
        notes="First frozen paper-account import.",
        evidence_source_path=evidence,
        trade_count_delta=30,
        net_pnl_delta=1250.0,
        prop_rule_breach=False,
        forced_flatten_violation=False,
    )

    assert eligible["status"] == "ELIGIBLE_FOR_REVIEW"
    assert eligible["status"] != "PASS"
    assert eligible["trade_count"] == 30
    assert eligible["calendar_days"] == 90
    assert (record_dir / "plan.json").read_bytes() == frozen_plan
    assert len((record_dir / "events.jsonl").read_text(encoding="utf-8").splitlines()) == 1
    attachment = record_dir / eligible["events"][0]["evidence_path"]
    assert attachment.is_file()
    evidence.unlink()
    assert service.detail("demo", "v01", "original")["status"] == "ELIGIBLE_FOR_REVIEW"
    with pytest.raises(FileExistsError, match="already exists"):
        service.start(
            campaign_id="demo",
            variant_id="v01",
            attempt_id="original",
            created_by="another-owner",
        )
    # The separate atomic head receipt makes otherwise-valid tail deletion visible.
    (record_dir / "events.jsonl").write_bytes(b"")
    truncated = service.detail("demo", "v01", "original")
    assert truncated["status"] == "NEEDS MANUAL REVIEW"
    assert any("event-head" in error for error in truncated["errors"])


def test_hash_drift_and_journal_tampering_fail_closed(
    tmp_path: Path,
    valid_candidate_inspection,
) -> None:
    start = datetime(2026, 1, 2, 14, 0, tzinfo=UTC)
    review_path, result_path, config_path = _candidate_fixture(
        tmp_path,
        reviewed_at=start - timedelta(days=1),
    )
    clock = MutableClock(start)
    service = ForwardIncubationService(tmp_path, clock=clock)
    service.start_from_paths(
        candidate_review_path=review_path,
        result_bundle_path=result_path,
        config_path=config_path,
        expected_campaign_id="demo",
        expected_variant_id="v01",
        expected_attempt_id="original",
        created_by="incubation-owner",
    )

    clock.value += timedelta(days=1)
    evidence = _evidence(tmp_path)
    service.append_observation(
        "demo",
        "v01",
        "original",
        recorded_by="paper-operator",
        notes="No-trade observation.",
        evidence_source_path=evidence,
        trade_count_delta=0,
        net_pnl_delta=0.0,
        prop_rule_breach=False,
        forced_flatten_violation=False,
    )

    config_path.write_text(config_path.read_text(encoding="utf-8") + "drift: true\n", encoding="utf-8")
    drifted = service.detail("demo", "v01", "original")
    assert drifted["status"] == "NEEDS MANUAL REVIEW"
    assert any("config hash" in error for error in drifted["errors"])
    with pytest.raises(RuntimeError, match="hash-drifted"):
        service.append_observation(
            "demo",
            "v01",
            "original",
            recorded_by="paper-operator",
            notes="This must not be appended.",
            evidence_source_path=evidence,
            trade_count_delta=1,
            net_pnl_delta=1.0,
            prop_rule_breach=False,
            forced_flatten_violation=False,
        )


def test_abandonment_and_retirement_are_terminal_and_chronology_is_server_owned(
    tmp_path: Path,
    valid_candidate_inspection,
) -> None:
    start = datetime(2026, 1, 2, 14, 0, tzinfo=UTC)
    review_path, result_path, config_path = _candidate_fixture(
        tmp_path,
        reviewed_at=start - timedelta(days=1),
        days=120,
        trades=40,
    )
    clock = MutableClock(start)
    service = ForwardIncubationService(tmp_path, clock=clock)
    service.start_from_paths(
        candidate_review_path=review_path,
        result_bundle_path=result_path,
        config_path=config_path,
        expected_campaign_id="demo",
        expected_variant_id="v01",
        expected_attempt_id="original",
        created_by="incubation-owner",
    )
    clock.value += timedelta(hours=1)
    retired = service.retire(
        "demo",
        "v01",
        "original",
        retired_by="risk-owner",
        reason="The market structure supporting the edge has changed.",
    )
    assert retired["status"] == "RETIRED"
    assert retired["minimum_calendar_days"] == 120
    assert retired["minimum_trades"] == 40
    with pytest.raises(RuntimeError, match="terminal"):
        service.append_review(
            "demo",
            "v01",
            "original",
            reviewer="risk-owner",
            notes="Cannot reopen a retired record.",
            evidence_source_path=_evidence(tmp_path, "review.json"),
            decision="continue",
        )

    # A separate record demonstrates a hard fail and the no-backdating guard.
    other_root = tmp_path / "other"
    review_path, result_path, config_path = _candidate_fixture(
        other_root,
        reviewed_at=start - timedelta(days=1),
    )
    clock.value = start
    other = ForwardIncubationService(other_root, clock=clock)
    other.start_from_paths(
        candidate_review_path=review_path,
        result_bundle_path=result_path,
        config_path=config_path,
        expected_campaign_id="demo",
        expected_variant_id="v01",
        expected_attempt_id="original",
        created_by="incubation-owner",
    )
    with pytest.raises(ValueError, match="backdated"):
        other.append_observation(
            "demo",
            "v01",
            "original",
            recorded_by="paper-operator",
            notes="Same server timestamp is not chronological.",
            evidence_source_path=_evidence(other_root),
            trade_count_delta=1,
            net_pnl_delta=-100.0,
            prop_rule_breach=False,
            forced_flatten_violation=False,
        )
    clock.value += timedelta(seconds=1)
    failed = other.append_observation(
        "demo",
        "v01",
        "original",
        recorded_by="paper-operator",
        notes="A declared prop-rule breach is terminal.",
        evidence_source_path=_evidence(other_root),
        trade_count_delta=1,
        net_pnl_delta=-100.0,
        prop_rule_breach=True,
        forced_flatten_violation=False,
    )
    assert failed["status"] == "FAILED"


def test_forward_incubation_api_lists_starts_appends_and_retires(
    tmp_path: Path,
    valid_candidate_inspection,
) -> None:
    _candidate_fixture(tmp_path, reviewed_at=datetime.now(UTC) - timedelta(days=1))
    app = FastAPI()
    register_api_routes(app, tmp_path)
    client = TestClient(app)

    started = client.post(
        "/api/forward-incubations",
        json={
            "campaign_id": "demo",
            "variant_id": "v01",
            "attempt_id": "original",
            "created_by": "incubation-owner",
        },
    )
    assert started.status_code == 201, started.text
    assert started.json()["status"] == "ACTIVE"
    uploaded = client.post(
        "/api/forward-incubations/evidence/upload",
        params={"filename": "paper_observations.csv"},
        content=b"session,trades,net_pnl\n2026-08-14,1,25.0\n",
    )
    assert uploaded.status_code == 201, uploaded.text
    upload_token = uploaded.json()["upload_token"]

    rejected_backdate = client.post(
        "/api/forward-incubations/demo/v01/original/observations",
        json={
            "recorded_by": "paper-operator",
            "notes": "Append through the governed endpoint.",
            "upload_token": upload_token,
            "trade_count_delta": 1,
            "net_pnl_delta": 25.0,
            "prop_rule_breach": False,
            "forced_flatten_violation": False,
            "occurred_at": "2020-01-01T00:00:00Z",
        },
    )
    assert rejected_backdate.status_code == 422

    observed = client.post(
        "/api/forward-incubations/demo/v01/original/observations",
        json={
            "recorded_by": "paper-operator",
            "notes": "Append through the governed endpoint.",
            "upload_token": upload_token,
            "trade_count_delta": 1,
            "net_pnl_delta": 25.0,
            "prop_rule_breach": False,
            "forced_flatten_violation": False,
        },
    )
    assert observed.status_code == 200, observed.text
    assert observed.json()["trade_count"] == 1
    manual_review = client.post(
        "/api/forward-incubations/demo/v01/original/reviews",
        json={
            "reviewer": "incubation-reviewer",
            "notes": "The latest paper observation needs independent reconciliation.",
            "upload_token": upload_token,
            "decision": "needs_manual_review",
        },
    )
    assert manual_review.status_code == 200, manual_review.text
    assert manual_review.json()["status"] == "NEEDS MANUAL REVIEW"
    continued = client.post(
        "/api/forward-incubations/demo/v01/original/reviews",
        json={
            "reviewer": "incubation-reviewer",
            "notes": "Reconciliation completed against the durable source attachment.",
            "upload_token": upload_token,
            "decision": "continue",
        },
    )
    assert continued.status_code == 200, continued.text
    assert continued.json()["status"] == "ACTIVE"
    listing = client.get("/api/forward-incubations", params={"campaign_id": "demo"})
    assert listing.status_code == 200
    assert len(listing.json()["items"]) == 1
    detail = client.get("/api/forward-incubations/demo/v01/original")
    assert detail.json()["plan"]["candidate_review_sha256"]

    retired = client.post(
        "/api/forward-incubations/demo/v01/original/retire",
        json={
            "retired_by": "risk-owner",
            "reason": "The frozen retirement rule was met after review.",
        },
    )
    assert retired.status_code == 200, retired.text
    assert retired.json()["status"] == "RETIRED"
