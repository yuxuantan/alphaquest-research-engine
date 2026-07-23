from __future__ import annotations

import json
from pathlib import Path
from io import BytesIO

from fastapi import FastAPI
from fastapi.testclient import TestClient
import pandas as pd
import pytest
import yaml

from alphaquest.studio.api import (
    _job_payload,
    _mechanics_event_timeline,
    _mechanics_strategy_context,
    register_api_routes,
)
from alphaquest.studio.jobs import SQLiteJobQueue
from alphaquest.studio.data_import import DataImportSpec, DatasetImporter
from alphaquest.studio.ai import AIDraftProvenance, ResearchBriefSuggestion
from alphaquest.studio.settings import StudioSettings, save_settings
from alphaquest.studio.results import ResultBundleBuilder


LONG_RATIONALE = (
    "This predeclared explanation is intentionally substantive and distinguishes the completed-bar economic "
    "mechanism from every deterministic active, archived, and failed historical match."
)


def test_job_api_exposes_durable_progress_elapsed_time_and_eta(tmp_path: Path) -> None:
    queue = SQLiteJobQueue(tmp_path / "jobs.sqlite")
    job = queue.submit(
        job_type="mechanics_validation_run",
        campaign_id="demo",
        payload={"variant_id": "v01"},
        idempotency_key="demo-progress",
        hash_locks={},
    )
    queue.claim_next(worker_id="worker-1", observed_hashes={})
    current = queue.update_progress(
        job.job_id,
        worker_id="worker-1",
        phase="event_replay",
        message="Replaying market sessions",
        percent=50.0,
        completed=5,
        total=10,
        unit="sessions",
    )

    payload = _job_payload(current)

    assert payload["progress"] == 50.0
    assert payload["progress_detail"]["phase"] == "event_replay"
    assert payload["progress_detail"]["completed"] == 5
    assert payload["progress_detail"]["total"] == 10
    assert payload["progress_detail"]["elapsed_seconds"] >= 0
    assert payload["progress_detail"]["eta_seconds"] >= 0
    assert payload["heartbeat_at"] == current.heartbeat_at.isoformat()


def test_event_replay_eta_uses_intra_session_percent_instead_of_completed_sessions(tmp_path: Path) -> None:
    queue = SQLiteJobQueue(tmp_path / "jobs.sqlite")
    job = queue.submit(
        job_type="mechanics_validation_run",
        campaign_id="demo",
        payload={"variant_id": "v01"},
        idempotency_key="demo-event-progress",
        hash_locks={},
    )
    queue.claim_next(worker_id="worker-1", observed_hashes={})
    current = queue.update_progress(
        job.job_id,
        worker_id="worker-1",
        phase="event_replay",
        message="Replaying session 2/4 · 50,000/100,000 events",
        percent=41.25,
        completed=1,
        total=4,
        unit="sessions",
    )

    payload = _job_payload(current)

    assert payload["progress_detail"]["eta_seconds"] is not None
    elapsed = payload["progress_detail"]["elapsed_seconds"]
    # 41.25% is 37.5% through the 15%-85% replay phase.
    assert payload["progress_detail"]["eta_seconds"] == pytest.approx(
        elapsed * (1.0 - 0.375) / 0.375,
        abs=0.1,
    )


def _client(root: Path) -> TestClient:
    app = FastAPI()
    register_api_routes(app, root)
    return TestClient(app)


def test_event_mechanics_detail_includes_prior_submission_and_strategy_trace(tmp_path: Path) -> None:
    events = pd.DataFrame(
        [
            {
                "trade_id": None,
                "session_date": "2025-07-14",
                "contract": "ESU5",
                "order_id": "VAL",
                "event_index": 10,
                "source_ordinal": 100,
                "timestamp": "2025-07-14T14:30:00Z",
                "transition": "order_submitted",
            },
            {
                "trade_id": 1,
                "session_date": "2025-07-14",
                "contract": "ESU5",
                "order_id": "VAL",
                "event_index": 12,
                "source_ordinal": 102,
                "timestamp": "2025-07-14T14:30:01Z",
                "transition": "entry_filled",
            },
            {
                "trade_id": 1,
                "session_date": "2025-07-14",
                "contract": "ESU5",
                "order_id": "VAL",
                "event_index": 20,
                "source_ordinal": 110,
                "timestamp": "2025-07-14T14:31:00Z",
                "transition": "position_closed",
            },
        ]
    )
    source = tmp_path / "run" / "trade_log.csv"
    source.parent.mkdir()
    pd.DataFrame([{"trade_id": 1, "aoi_side": "VAL", "trigger_kind": "delta_4tick_3m"}]).to_csv(
        source,
        index=False,
    )
    config = tmp_path / "research/campaigns/active/demo/variants/v01/config.yaml"
    config.parent.mkdir(parents=True)
    config.write_text("campaign_id: demo\n", encoding="utf-8")

    timeline = _mechanics_event_timeline(events, "1")
    context = _mechanics_strategy_context(
        {"source_trade_log": str(source)},
        "1",
        config,
    )

    assert timeline["transition"].tolist() == ["order_submitted", "entry_filled", "position_closed"]
    assert context["aoi_side"] == "VAL"
    assert context["trigger_kind"] == "delta_4tick_3m"


def _governed_dataset(root: Path) -> None:
    source = root / "administrator-bars.csv"
    timestamps = pd.date_range("2026-01-05 09:30:00", periods=180, freq="min")
    prices = [5000.0 + index * 0.25 for index in range(len(timestamps))]
    pd.DataFrame(
        {
            "timestamp": timestamps.astype(str),
            "open": prices,
            "high": [item + 1 for item in prices],
            "low": [item - 1 for item in prices],
            "close": [item + 0.25 for item in prices],
            "volume": [1000 + index for index in range(len(timestamps))],
        }
    ).to_csv(source, index=False)
    DatasetImporter(root).import_file(
        source,
        DataImportSpec(
            dataset_id="governed_es_1m",
            symbol="ES",
            timeframe="1m",
            timezone="America/New_York",
            timestamp_semantics="bar_open",
            roll_policy="single_contract",
            timestamp_column="timestamp",
            open_column="open",
            high_column="high",
            low_column="low",
            close_column="close",
            volume_column="volume",
            single_contract_confirmed=True,
        ),
    )


def _brief() -> dict:
    return {
        "title": "Opening auction continuation after completed imbalance",
        "edge_family": "opening_auction_continuation",
        "timeframe": "1m",
        "hypothesis": LONG_RATIONALE,
        "expected_mechanism": LONG_RATIONALE,
        "holding_horizon": "Next bar open through the configured same-session forced flatten.",
        "known_failure_modes": [LONG_RATIONALE],
        "source": {
            "title": "Opening auction price discovery study",
            "authors": ["A. Researcher"],
            "year": 2025,
            "link": "https://example.test/opening-auction",
            "doi": None,
            "relevance": LONG_RATIONALE,
        },
        "economic_edge_fingerprint": {
            "market_behavior": "Completed opening-range expansion persists into the following intraday bars.",
            "causal_mechanism": LONG_RATIONALE,
            "signal_inputs": ["completed opening range", "completed close"],
            "market_context": "ES regular trading hours",
            "holding_period": "Intraday through forced flatten",
        },
    }


def test_bootstrap_is_task_oriented_and_keeps_operational_state_separate(tmp_path: Path) -> None:
    client = _client(tmp_path)

    response = client.get("/api/bootstrap")

    assert response.status_code == 200
    payload = response.json()
    assert payload["workspace"]["ui_runtime"] == "react-fastapi"
    assert payload["workspace"]["candidate_only"] is True
    assert payload["workspace"]["metrics"] == {
        "live_drafts": 0,
        "active_campaigns": 0,
        "review_items": 0,
        "certified_modules": 12,
    }
    assert payload["jobs"] == []


def test_api_completes_the_seven_gate_draft_without_yaml_or_hash_input(
    tmp_path: Path,
    monkeypatch,
) -> None:
    _governed_dataset(tmp_path)
    client = _client(tmp_path)

    created = client.post(
        "/api/drafts",
        json={"campaign_id": "es_web_publication", "title": "Opening auction continuation", "instrument": "ES"},
    )
    assert created.status_code == 201
    assert len(created.json()["steps"]) == 7

    brief = client.put("/api/drafts/es_web_publication/brief", json=_brief())
    assert brief.status_code == 200, brief.text
    assert brief.json()["steps"][0]["complete"] is True

    context = client.get("/api/drafts/es_web_publication/duplicates")
    assert context.status_code == 200
    duplicate = client.put(
        "/api/drafts/es_web_publication/duplicates",
        json={
            "reviewed_campaign_ids": [item["campaign_id"] for item in context.json()["matches"]],
            "conclusion": "distinct",
            "substantive_distinction": LONG_RATIONALE,
        },
    )
    assert duplicate.status_code == 200, duplicate.text

    dataset = client.post(
        "/api/drafts/es_web_publication/dataset/select",
        json={"dataset_id": "governed_es_1m"},
    )
    assert dataset.status_code == 200, dataset.text

    execution = client.put(
        "/api/drafts/es_web_publication/execution",
        json={
            "roll_policy_confirmed": True,
            "execution": {
                "session_start": "09:30:00",
                "session_end": "16:00:00",
                "latest_entry_time": "15:45:00",
                "flatten_time": "15:55:00",
                "latest_flat_time": "15:56:00",
                "overnight_allowed": False,
                "initial_balance": 150000.0,
                "tick_size": 0.25,
                "point_value": 50.0,
                "tick_value": 12.5,
                "commission_per_contract": 2.5,
                "slippage_ticks": 1.0,
                "contracts": 1,
                "prop_profile": "configured_local_profile",
            },
        },
    )
    assert execution.status_code == 200, execution.text

    recipe = client.put(
        "/api/drafts/es_web_publication/mechanics/recipe",
        json={"recipe": "opening_range_breakout", "confirmed": True},
    )
    assert recipe.status_code == 200, recipe.text

    suggested = client.get("/api/drafts/es_web_publication/variants")
    assert suggested.status_code == 200, suggested.text
    variants = suggested.json()["variants"]
    assert len(variants) == 1
    for item in variants:
        item["confirmed"] = True
    saved = client.put(
        "/api/drafts/es_web_publication/variants",
        json={"variants": variants},
    )
    assert saved.status_code == 200, saved.text
    assert saved.json()["steps"][5]["complete"] is True

    frozen = client.post(
        "/api/drafts/es_web_publication/freeze",
        json={"confirmed": True},
    )
    assert frozen.status_code == 200, frozen.text
    assert frozen.json()["steps"][6]["complete"] is True
    assert frozen.json()["preflight"]["preflight_verdict"] == "PASS"

    published = client.post("/api/drafts/es_web_publication/publish")
    assert published.status_code == 200, published.text
    campaign = client.get("/api/campaigns/es_web_publication")
    assert campaign.status_code == 200, campaign.text
    assert campaign.json()["campaign"]["studio_managed"] is True
    assert len(campaign.json()["stage_matrix"]) == 1
    assert campaign.json()["next_variant"]["eligible"] is False

    failed_result = (
        tmp_path
        / "research/evidence/runs/es_web_publication/v01/ES/run1/reporting_v2/result_bundle_v2.json"
    )
    failed_result.parent.mkdir(parents=True)
    failed_result.write_text(
        json.dumps({"campaign_id": "es_web_publication", "variant_id": "v01", "verdict": "FAIL"}),
        encoding="utf-8",
    )
    monkeypatch.setattr(
        "alphaquest.studio.sequential_variants.MechanicsApprovalService.inspect",
        lambda _self, _path: {"status": "APPROVED_FOR_TESTING"},
    )
    proposal = client.get("/api/campaigns/es_web_publication/next-variant")
    assert proposal.status_code == 200, proposal.text
    assert proposal.json()["next_variant_id"] == "v02"
    appended = client.post(
        "/api/campaigns/es_web_publication/next-variant",
        json={
            "variant": proposal.json()["variant"],
            "failure_analysis": LONG_RATIONALE,
            "created_by": "mechanics-reviewer",
        },
    )
    assert appended.status_code == 201, appended.text
    assert appended.json()["research_verdict"] == "NEEDS MANUAL REVIEW"
    campaign_root = tmp_path / "research/campaigns/active/es_web_publication"
    assert (campaign_root / "variants/v02/config.yaml").is_file()
    campaign_definition = yaml.safe_load((campaign_root / "campaign.yaml").read_text(encoding="utf-8"))
    assert campaign_definition["variants"] == ["v01", "v02"]
    assert campaign_definition["sequential_variant_history"][0]["predecessor_verdict"] == "FAIL"


def test_api_returns_field_addressable_validation_and_protects_frozen_drafts(tmp_path: Path) -> None:
    client = _client(tmp_path)
    client.post(
        "/api/drafts",
        json={"campaign_id": "es_invalid", "title": "Invalid fixture", "instrument": "ES"},
    )

    response = client.put("/api/drafts/es_invalid/brief", json={})

    assert response.status_code == 422
    detail = response.json()["detail"]
    assert {item["loc"][-1] for item in detail} >= {"title", "hypothesis", "source"}


def test_raw_upload_inspection_never_accepts_a_server_side_path(tmp_path: Path) -> None:
    client = _client(tmp_path)
    body = b"timestamp,open,high,low,close,volume\n2026-01-05 09:30,1,2,0,1.5,10\n"

    response = client.post(
        "/api/uploads/inspect?filename=../../bars.csv",
        content=body,
        headers={"content-type": "application/octet-stream"},
    )

    assert response.status_code == 201, response.text
    payload = response.json()
    assert payload["filename"] == "bars.csv"
    assert payload["columns"] == ["timestamp", "open", "high", "low", "close", "volume"]
    assert Path(payload["upload_token"]).name == payload["upload_token"]


def test_ai_suggestion_persists_hash_only_provenance_on_the_selected_draft(
    tmp_path: Path,
    monkeypatch,
) -> None:
    client = _client(tmp_path)
    client.post(
        "/api/drafts",
        json={"campaign_id": "es_ai_notes", "title": "AI notes", "instrument": "ES"},
    )
    save_settings(StudioSettings(openai_model="pinned-model"), project_root=tmp_path)

    def suggest(_self, notes: str, *, source_title: str, instrument: str):
        assert notes == "Selected prose only"
        assert source_title == "Research paper"
        assert instrument == "ES"
        return (
            ResearchBriefSuggestion(
                hypothesis="A sufficiently falsifiable hypothesis generated from selected research prose.",
                expected_mechanism="A sufficiently detailed causal mechanism generated from selected research prose.",
                expected_holding_horizon="Intraday",
                known_failure_modes=["The effect may fail outside the declared session."],
                lookahead_risks=["Confirm every rolling input is lagged."],
                missing_questions=[],
                economic_edge_fingerprint={
                    "market_behavior": "Completed bars retain a predeclared directional response.",
                    "causal_mechanism": "Participants adjust inventory after a completed observable imbalance.",
                    "signal_inputs": "completed close and prior rolling mean",
                    "market_context": "ES regular trading session",
                    "holding_period": "intraday",
                },
            ),
            AIDraftProvenance(
                model="pinned-model",
                prompt_sha256="a" * 64,
                source_sha256="b" * 64,
                response_sha256="c" * 64,
                generated_at="2026-07-16T12:00:00+00:00",
            ),
        )

    monkeypatch.setattr("alphaquest.studio.ai.OpenAIResearchDraftAdapter.suggest", suggest)
    response = client.post(
        "/api/ai/suggest",
        json={
            "campaign_id": "es_ai_notes",
            "selected_text": "Selected prose only",
            "source_title": "Research paper",
            "instrument": "ES",
        },
    )

    assert response.status_code == 200, response.text
    state = client.get("/api/drafts/es_ai_notes").json()["state"]
    assert state["ai_provenance_events"][0]["source_sha256"] == "b" * 64
    serialized = str(state)
    assert "Selected prose only" not in serialized
    assert "sufficiently falsifiable" not in serialized


def test_pdf_pages_are_selected_and_extracted_locally_without_provider_access(
    tmp_path: Path,
    monkeypatch,
) -> None:
    PdfWriter = pytest.importorskip("pypdf").PdfWriter
    writer = PdfWriter()
    writer.add_blank_page(width=612, height=792)
    raw = BytesIO()
    writer.write(raw)
    client = _client(tmp_path)

    inspected = client.post(
        "/api/ai/pdf/inspect?filename=paper.pdf",
        content=raw.getvalue(),
        headers={"content-type": "application/pdf"},
    )

    assert inspected.status_code == 201, inspected.text
    payload = inspected.json()
    assert payload["local_only"] is True
    assert payload["pages"][0]["page_number"] == 1
    monkeypatch.setattr(
        "alphaquest.studio.ai.extract_pdf_text",
        lambda _path, page_indexes: "Only locally selected page text" if page_indexes == [0] else "",
    )
    extracted = client.post(
        "/api/ai/pdf/extract",
        json={"upload_token": payload["upload_token"], "page_indexes": [0]},
    )
    assert extracted.status_code == 200, extracted.text
    assert extracted.json() == {
        "selected_text": "Only locally selected page text",
        "characters": 31,
        "page_indexes": [0],
        "local_only": True,
    }


def _indexed_bundle_fixture(
    tmp_path: Path,
    *,
    index_verdict: str = "PASS",
    bundle_verdict: str = "FAIL",
):
    campaign_root = tmp_path / "research/campaigns/active/demo"
    config_path = campaign_root / "variants/v01/config.yaml"
    config_path.parent.mkdir(parents=True)
    config_path.write_text(
        yaml.safe_dump({"campaign_id": "demo", "variant_id": "v01", "test_run_id": "run1"}),
        encoding="utf-8",
    )
    (campaign_root / "campaign.yaml").write_text(
        yaml.safe_dump(
            {
                "campaign_id": "demo",
                "title": "Authoritative result presentation",
                "variants": ["v01", "v02", "v03", "v04", "v05"],
            }
        ),
        encoding="utf-8",
    )
    reporting = tmp_path / "research/evidence/runs/demo/v01/ES/run1/reporting_v2"
    trades = pd.DataFrame(
        [
            {
                "trade_id": 1,
                "direction": "long",
                "entry_timestamp": "2025-01-02T14:30:00Z",
                "exit_timestamp": "2025-01-02T14:35:00Z",
                "net_pnl": 100.0 if bundle_verdict == "PASS" else -50.0,
                "r_multiple": 2.0 if bundle_verdict == "PASS" else -1.0,
                "commission": 5.0,
                "slippage_cost": 12.5,
                "apex_rule_violation": False,
                "position_flat_before_deadline": True,
            }
        ]
    )
    bundle = ResultBundleBuilder().build_and_write(
        trades,
        reporting,
        campaign_id="demo",
        variant_id="v01",
        run_id="run1",
        verdict=bundle_verdict,
        stage_criteria=[
            {
                "stage": "limited_core_grid_test",
                "metric": "profit_factor",
                "operator": ">=",
                "threshold": {"value": 1.2, "reason": None},
                "actual": {"value": 1.3 if bundle_verdict == "PASS" else 0.8, "reason": None},
                "result": bundle_verdict,
                "reason": (
                    "actual 1.3 met required 1.2"
                    if bundle_verdict == "PASS"
                    else "actual 0.8 was below required 1.2"
                ),
                "evidence_path": "limited_core_grid_test/stage_result.json",
            }
        ],
        initial_balance=50_000,
        prop_rule_outcome="PASS",
        forced_flatten_compliance=True,
    )
    bundle_path = reporting / "result_bundle_v2.json"
    (campaign_root / "results_index.yaml").write_text(
        yaml.safe_dump(
            {
                "runs": [
                    {
                        "variant_id": "v01",
                        "test_run_id": "run1",
                        "research_verdict": index_verdict,
                        "passed": index_verdict == "PASS",
                        "failed_stage": None,
                        "updated_at": "2026-07-16T00:00:00+00:00",
                        "result_bundle_path": str(bundle_path),
                        "output_dir": str(reporting.parent),
                    }
                ]
            }
        ),
        encoding="utf-8",
    )
    return config_path, bundle_path, bundle


def test_campaign_result_rejects_schema_valid_bundle_without_complete_finalization(tmp_path: Path) -> None:
    _indexed_bundle_fixture(tmp_path)

    payload = _client(tmp_path).get("/api/campaigns/demo").json()

    row = next(item for item in payload["stage_matrix"] if item["variant"] == "v01")
    result = payload["latest_results"]["v01"]
    assert row["research verdict"] == "NEEDS MANUAL REVIEW"
    assert row["first failed or unresolved gate"] == "result_bundle_v2_finalization"
    assert result["research_verdict"] == "NEEDS MANUAL REVIEW"
    assert result["metrics"] == {}
    assert result["stage_criteria"] == []
    assert result["finalization"]["valid"] is False
    assert any("finalization manifest" in item for item in result["finalization"]["errors"])


def test_campaign_and_candidate_views_use_validated_bundle_not_index_verdict(
    tmp_path: Path,
    monkeypatch,
) -> None:
    config_path, bundle_path, bundle = _indexed_bundle_fixture(tmp_path, index_verdict="PASS")

    def valid_inspection(path, *, config_path=None):
        assert Path(path).resolve() == bundle_path.resolve()
        return {
            "valid": True,
            "errors": [],
            "bundle": bundle,
            "manifest": {"source_config": str(config_path or config_path_fixture)},
        }

    config_path_fixture = config_path
    monkeypatch.setattr("alphaquest.studio.api.inspect_finalized_result", valid_inspection)
    client = _client(tmp_path)

    campaign = client.get("/api/campaigns/demo").json()
    row = next(item for item in campaign["stage_matrix"] if item["variant"] == "v01")
    result = campaign["latest_results"]["v01"]
    assert row["research verdict"] == "FAIL"
    assert row["first failed or unresolved gate"] == "limited_core_grid_test"
    assert result["research_verdict"] == "FAIL"
    assert result["source_index_verdict"] == "PASS"
    assert result["metrics"]["total_trades"]["value"] == 1
    assert result["stage_criteria"][0]["actual"]["value"] == 0.8
    assert result["finalization"] == {"valid": True, "errors": []}

    assert not any(
        item["campaign_id"] == "demo" for item in client.get("/api/reviews").json()["candidate"]
    )


def test_campaign_result_suppresses_bundle_values_when_finalization_hashes_drift(
    tmp_path: Path,
    monkeypatch,
) -> None:
    config_path, bundle_path, bundle = _indexed_bundle_fixture(tmp_path)

    def drifted_inspection(path, *, config_path=None):
        assert Path(path).resolve() == bundle_path.resolve()
        return {
            "valid": False,
            "errors": ["hashed reporting artifact drifted: result_bundle_v2.json"],
            "bundle": bundle,
            "manifest": {"source_config": str(config_path or config_path_fixture)},
        }

    config_path_fixture = config_path
    monkeypatch.setattr("alphaquest.studio.api.inspect_finalized_result", drifted_inspection)

    payload = _client(tmp_path).get("/api/campaigns/demo").json()
    result = payload["latest_results"]["v01"]

    assert result["research_verdict"] == "NEEDS MANUAL REVIEW"
    assert result["metrics"] == {}
    assert result["stage_criteria"] == []
    assert result["finalization"]["valid"] is False
    assert result["finalization"]["errors"] == [
        "hashed reporting artifact drifted: result_bundle_v2.json"
    ]


def test_candidate_queue_contains_only_unreviewed_valid_terminal_passes(
    tmp_path: Path,
    monkeypatch,
) -> None:
    config_path, bundle_path, bundle = _indexed_bundle_fixture(
        tmp_path,
        index_verdict="FAIL",
        bundle_verdict="PASS",
    )

    def valid_finalization(path, *, config_path=None):
        assert Path(path).resolve() == bundle_path.resolve()
        return {
            "valid": True,
            "errors": [],
            "bundle": bundle,
            "manifest": {"source_config": str(config_path or config_path_fixture)},
        }

    config_path_fixture = config_path
    monkeypatch.setattr("alphaquest.studio.api.inspect_finalized_result", valid_finalization)
    client = _client(tmp_path)

    candidates = client.get("/api/reviews").json()["candidate"]
    candidate = next(item for item in candidates if item["campaign_id"] == "demo")
    assert candidate["verdict"] == "PASS"
    assert candidate["review_status"] == "required"
    assert candidate["review_blockers"] == []
    assert candidate["metrics"]["total_trades"]["value"] == 1

    review_path = bundle_path.parent / "candidate_review.json"
    review_path.write_text("{}\n", encoding="utf-8")

    def stale_review(self, **kwargs):
        return {
            "valid": False,
            "lifecycle_state": "review_required",
            "errors": ["result bundle hash is stale or mismatched"],
        }

    monkeypatch.setattr(
        "alphaquest.studio.candidate_review.CandidateReviewService.inspect",
        stale_review,
    )
    candidates = client.get("/api/reviews").json()["candidate"]
    candidate = next(item for item in candidates if item["campaign_id"] == "demo")
    assert candidate["review_status"] == "invalid_or_stale"
    assert candidate["review_blockers"] == [
        "Existing candidate review is invalid or stale: result bundle hash is stale or mismatched"
    ]

    def valid_terminal_review(self, **kwargs):
        return {"valid": True, "lifecycle_state": "candidate", "errors": []}

    monkeypatch.setattr(
        "alphaquest.studio.candidate_review.CandidateReviewService.inspect",
        valid_terminal_review,
    )
    assert not any(
        item["campaign_id"] == "demo" for item in client.get("/api/reviews").json()["candidate"]
    )
