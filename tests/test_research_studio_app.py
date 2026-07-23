import hashlib
import json
from pathlib import Path

import pytest
import pandas as pd
from streamlit.testing.v1 import AppTest
import yaml

from alphaquest.authoring import BarRuleV1
from alphaquest.dashboard.validation_app import save_manual_review_annotation
from alphaquest.dashboard.studio_app import (
    _build_visual_rule,
    _governed_review_config_paths,
    _parse_grid_values,
    _results_matrix_state,
    _resolve_result_config,
)
from alphaquest.studio.data_import import DataImportSpec, DatasetImporter
from alphaquest.studio.approvals import MechanicsApprovalService, require_all_variant_mechanics_approved
from alphaquest.studio.finalization import inspect_finalized_result
from alphaquest.studio.jobs import OperationalState, SQLiteJobQueue
from alphaquest.studio.results import ResultBundleBuilder
from alphaquest.studio.worker import CAMPAIGN_VARIANT_RUN, MECHANICS_VALIDATION_RUN, StudioWorker
from alphaquest.studio.workspace import list_published_campaigns


E2E_LONG_TEXT = (
    "This predeclared explanation is deliberately longer than eighty characters and documents a causal "
    "completed-bar market mechanism before any performance result is available to the researcher."
)


def test_studio_home_loads_in_fresh_workspace_without_terminal_or_yaml(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("ALPHAQUEST_PROJECT_ROOT", str(tmp_path))
    app_path = Path(__file__).resolve().parents[1] / "apps/research_studio.py"

    app = AppTest.from_file(str(app_path), default_timeout=20).run()

    assert not app.exception
    assert any(item.value == "AlphaQuest Research Studio" for item in app.title)
    assert any("without editing code or YAML" in item.value for item in app.markdown)


def test_studio_exposes_all_novice_pages(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("ALPHAQUEST_PROJECT_ROOT", str(tmp_path))
    app_path = Path(__file__).resolve().parents[1] / "apps/research_studio.py"
    app = AppTest.from_file(str(app_path), default_timeout=20).run()

    assert tuple(app.radio[0].options) == (
        "Home",
        "Campaigns",
        "Review Queue",
        "Libraries",
        "Tutorial",
        "Settings",
    )
    expected_titles = {
        "Campaigns": "Campaigns",
        "Review Queue": "Review Queue",
        "Libraries": "Libraries",
        "Tutorial": "15-minute Studio walkthrough",
        "Settings": "Settings",
    }
    for page, title in expected_titles.items():
        workspace = next(item for item in app.radio if item.label == "Workspace")
        workspace.set_value(page).run()
        assert not app.exception, page
        assert any(item.value == title for item in app.title)


def test_unfinished_legacy_campaign_is_visibly_blocked_and_developer_managed(
    tmp_path: Path,
    monkeypatch,
) -> None:
    campaign = tmp_path / "research/campaigns/active/unfinished_edge"
    campaign.mkdir(parents=True)
    (campaign / "campaign.yaml").write_text(
        yaml.safe_dump(
            {
                "campaign_id": "unfinished_edge",
                "title": "Unfinished legacy edge",
                "variants": ["v01", "v02", "v03", "v04", "v05"],
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setenv("ALPHAQUEST_PROJECT_ROOT", str(tmp_path))
    app_path = Path(__file__).resolve().parents[1] / "apps/research_studio.py"

    app = AppTest.from_file(str(app_path), default_timeout=20).run()
    app.radio[0].set_value("Campaigns").run()

    rows = list_published_campaigns(tmp_path)
    assert rows[0]["studio_managed"] is False
    assert rows[0]["workflow_status"] == "BLOCKED · DEVELOPER-MANAGED"
    assert any("blocked and developer-managed" in item.value for item in app.warning)
    assert not any(
        item.label == "Generate mechanics evidence · queue all five frozen variants"
        for item in app.button
    )


def test_researcher_can_create_and_reopen_a_draft_through_streamlit_only(
    tmp_path: Path,
    monkeypatch,
) -> None:
    monkeypatch.setenv("ALPHAQUEST_PROJECT_ROOT", str(tmp_path))
    app_path = Path(__file__).resolve().parents[1] / "apps/research_studio.py"
    app = AppTest.from_file(str(app_path), default_timeout=20).run()

    app.text_input[0].set_value("es_no_code_draft")
    app.text_input[1].set_value("Opening auction continuation")
    app.button[0].click().run()

    assert not app.exception
    draft_path = tmp_path / "research/drafts/es_no_code_draft/draft.json"
    assert draft_path.is_file()
    app.radio[0].set_value("Campaigns").run()
    assert not app.exception
    assert app.selectbox[0].value == "es_no_code_draft"
    assert app.selectbox[1].value == "1 · Research brief"


def test_out_of_order_variant_navigation_fails_soft_with_prerequisite_guidance(
    tmp_path: Path,
    monkeypatch,
) -> None:
    monkeypatch.setenv("ALPHAQUEST_PROJECT_ROOT", str(tmp_path))
    app_path = Path(__file__).resolve().parents[1] / "apps/research_studio.py"
    app = AppTest.from_file(str(app_path), default_timeout=20).run()
    app.text_input[0].set_value("early_navigation")
    app.text_input[1].set_value("Early navigation fixture")
    app.button[0].click().run()
    app.radio[0].set_value("Campaigns").run()
    app.selectbox[1].set_value("6 · First variant").run()

    assert not app.exception
    assert any("Complete and save step 1" in item.value for item in app.warning)


def test_fresh_workspace_completes_seven_checkpoint_tutorial_entirely_in_streamlit(
    tmp_path: Path,
    monkeypatch,
) -> None:
    monkeypatch.setenv("ALPHAQUEST_PROJECT_ROOT", str(tmp_path))
    app_path = Path(__file__).resolve().parents[1] / "apps/research_studio.py"

    app = AppTest.from_file(str(app_path), default_timeout=30).run()
    app.radio[0].set_value("Tutorial").run()

    for index in range(1, 7):
        button = next(item for item in app.button if item.label == f"Confirm step {index}")
        button.click().run(timeout=30)
        assert not app.exception
    next(item for item in app.button if item.label == "Run isolated staged tutorial").click().run(
        timeout=30
    )

    assert not app.exception
    assert any("Final research verdict: FAIL" in item.value for item in app.error)
    assert (tmp_path / "examples/tutorial_campaign/generated/stage_matrix.csv").is_file()
    assert not (tmp_path / "research_ledger.csv").exists()
    assert not (tmp_path / "research/campaigns/active").exists()


def test_no_code_wizard_reaches_atomic_initial_variant_publication_in_fresh_workspace(
    tmp_path: Path,
    monkeypatch,
) -> None:
    source = tmp_path / "administrator-provided-bars.csv"
    timestamps = pd.DatetimeIndex(
        [
            *pd.date_range("2026-01-05 09:30:00", periods=60, freq="min"),
            *pd.date_range("2026-01-06 09:30:00", periods=60, freq="min"),
            *pd.date_range("2026-01-07 09:30:00", periods=60, freq="min"),
        ]
    )
    session_prices = [5000.0] * 120 + [5000.0 + index * 0.25 for index in range(60)]
    pd.DataFrame(
        {
            "timestamp": timestamps.astype(str),
            # The deterministic shortlist chooses the first (flat) session,
            # so every variant fails its first scientific gate quickly. The
            # Wednesday's third session still creates mechanics-review trades.
            "open": session_prices,
            "high": [price + 1.0 for price in session_prices],
            "low": [price - 1.0 for price in session_prices],
            "close": [price + 0.5 for price in session_prices],
            "volume": [1000 + index for index in range(len(timestamps))],
        }
    ).to_csv(source, index=False)
    DatasetImporter(tmp_path).import_file(
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
    monkeypatch.setenv("ALPHAQUEST_PROJECT_ROOT", str(tmp_path))
    app_path = Path(__file__).resolve().parents[1] / "apps/research_studio.py"

    def reopen_campaigns() -> AppTest:
        reopened = AppTest.from_file(str(app_path), default_timeout=30).run()
        reopened.radio[0].set_value("Campaigns").run()
        return reopened

    app = AppTest.from_file(str(app_path), default_timeout=30).run()

    app.text_input[0].set_value("no_code_publication")
    app.text_input[1].set_value("No-code opening auction continuation")
    app.button[0].click().run()
    app = reopen_campaigns()

    next(item for item in app.text_input if item.label == "Economic edge family").set_value(
        "opening_auction_continuation"
    )
    next(item for item in app.text_area if item.label == "Falsifiable hypothesis").set_value(E2E_LONG_TEXT)
    next(item for item in app.text_area if item.label == "Expected causal mechanism").set_value(E2E_LONG_TEXT)
    next(item for item in app.text_input if item.label == "Expected holding horizon").set_value(
        "From the next completed-bar open until the configured intraday forced flatten."
    )
    next(item for item in app.text_area if item.label.startswith("Known failure modes")).set_value(E2E_LONG_TEXT)
    next(item for item in app.text_input if item.label == "Source title").set_value(
        "Opening auction price discovery study"
    )
    next(item for item in app.text_input if item.label.startswith("Authors")).set_value("A. Researcher")
    next(item for item in app.text_input if item.label == "Link").set_value(
        "https://example.test/opening-auction-study"
    )
    next(
        item
        for item in app.text_area
        if item.label == "Why this source may apply to this futures market"
    ).set_value(E2E_LONG_TEXT)
    next(item for item in app.text_input if item.label == "Market behavior").set_value(E2E_LONG_TEXT)
    next(item for item in app.text_input if item.label.startswith("Signal inputs")).set_value(
        "completed OHLCV bars, predeclared opening range"
    )
    next(item for item in app.text_input if item.label == "Market context").set_value(
        "Highly liquid ES regular trading hours after the opening auction completes."
    )
    next(item for item in app.button if item.label == "Save and continue").click().run()
    assert not app.exception
    app = reopen_campaigns()

    next(
        item
        for item in app.text_area
        if item.label == "Substantive economic distinction or duplicate rationale"
    ).set_value(E2E_LONG_TEXT)
    next(item for item in app.button if item.label == "Save duplicate review").click().run()
    assert not app.exception
    app = reopen_campaigns()

    next(item for item in app.button if item.label == "Use this dataset").click().run()
    assert not app.exception
    app = reopen_campaigns()

    next(
        item
        for item in app.checkbox
        if item.label == "I reviewed the selected dataset's contract roll policy."
    ).set_value(True)
    next(item for item in app.button if item.label == "Confirm execution rules").click().run()
    assert not app.exception
    app = reopen_campaigns()

    next(
        item
        for item in app.checkbox
        if item.label.startswith("I confirm this recipe represents")
    ).set_value(True)
    next(item for item in app.button if item.label == "Use reviewed certified recipe").click().run()
    assert not app.exception
    app = reopen_campaigns()

    confirmations = [
        item
        for item in app.checkbox
        if item.label == "I confirm this mechanic before performance testing"
    ]
    assert len(confirmations) == 1
    for checkbox in confirmations:
        checkbox.set_value(True)
    next(item for item in app.button if item.label == "Save the initial variant card").click().run()
    assert not app.exception
    app = reopen_campaigns()

    next(
        item
        for item in app.checkbox
        if item.label.startswith("Freeze this protocol")
    ).set_value(True)
    next(item for item in app.button if item.label == "Validate and freeze").click().run(timeout=30)
    assert not app.exception
    app = reopen_campaigns()
    next(item for item in app.button if item.label == "Publish governed campaign").click().run(timeout=30)

    assert not app.exception
    campaign = tmp_path / "research/campaigns/active/no_code_publication"
    assert (campaign / "campaign.yaml").is_file()
    assert (campaign / "authoring_manifest.json").is_file()
    assert len(list((campaign / "variants").glob("*/config.yaml"))) == 1
    assert any("Published no_code_publication" in item.value for item in app.success)
    published = next(
        row for row in list_published_campaigns(tmp_path) if row["campaign_id"] == "no_code_publication"
    )
    assert published["studio_managed"] is True

    app = reopen_campaigns()
    next(
        item
        for item in app.button
        if item.label == "Generate mechanics evidence · current variant"
    ).click().run(timeout=30)
    queue = SQLiteJobQueue(tmp_path / "run-store/studio-runtime/jobs.sqlite3")
    jobs = queue.list_jobs(limit=10)
    assert len(jobs) == 1
    assert [job.payload["variant_id"] for job in reversed(jobs)] == ["v01"]
    assert {job.state for job in jobs} == {OperationalState.QUEUED}

    handled = StudioWorker(
        queue,
        project_root=tmp_path,
        worker_id="e2e-mechanics-worker",
    ).run_forever(
        poll_interval=0,
        max_jobs=1,
        recover_stale_after=None,
    )
    assert handled == 1
    mechanics_jobs = [
        job for job in queue.list_jobs(limit=20) if job.job_type == MECHANICS_VALIDATION_RUN
    ]
    assert len(mechanics_jobs) == 1
    assert {job.state for job in mechanics_jobs} == {OperationalState.SUCCEEDED}
    assert {job.research_verdict for job in mechanics_jobs} == {"NEEDS MANUAL REVIEW"}
    assert {job.attempt_reserved for job in mechanics_jobs} == {False}
    assert {
        (job.result or {}).get("mechanics_validation_status") for job in mechanics_jobs
    } == {"READY_FOR_REVIEW"}

    config_paths = sorted(campaign.glob("variants/*/config.yaml"))
    approval_service = MechanicsApprovalService()
    first_plan = None
    for index, config_path in enumerate(config_paths):
        plan = approval_service.plan(config_path)
        assert plan.sampled_trade_ids
        assert not plan.blockers
        for trade_id in plan.sampled_trade_ids:
            save_manual_review_annotation(
                plan.evidence_dir,
                trade_id,
                "Correct",
                "The completed-bar implementation matches the frozen strategy specification.",
                reviewed_at="2026-07-15T12:00:00+00:00",
            )
        if index == 0:
            first_plan = approval_service.plan(config_path)
            continue
        approval_service.approve(
            config_path,
            reviewer="e2e-mechanics-reviewer",
            notes="Every required deterministic sample was reconciled to the frozen mechanics specification.",
            reviewed_at="2026-07-15T12:30:00+00:00",
        )

    assert first_plan is not None and first_plan.ready_for_approval
    review_app = AppTest.from_file(str(app_path), default_timeout=30).run()
    next(item for item in review_app.radio if item.label == "Workspace").set_value("Review Queue").run(
        timeout=30
    )
    next(
        item for item in review_app.selectbox if item.label == "Frozen variant"
    ).set_value(config_paths[0]).run(timeout=30)
    next(
        item for item in review_app.text_input if item.label == "Mechanics reviewer"
    ).set_value("e2e-mechanics-reviewer")
    next(
        item for item in review_app.text_area if item.label == "Mechanics review notes"
    ).set_value(
        "Every required deterministic sample was reconciled to the frozen mechanics specification."
    )
    next(
        item
        for item in review_app.button
        if item.label == "Approve implementation for testing"
    ).click().run(timeout=30)
    assert not review_app.exception
    assert any("Hash-, data-, lane-" in item.value for item in review_app.success)
    assert len(require_all_variant_mechanics_approved(config_paths)) == 1

    app = reopen_campaigns()
    next(
        item for item in app.button if item.label == "Run full test suite · current variant"
    ).click().run(timeout=30)
    assert not app.exception
    performance_jobs = [
        job for job in queue.list_jobs(limit=20) if job.job_type == CAMPAIGN_VARIANT_RUN
    ]
    assert len(performance_jobs) == 1
    assert [job.payload["variant_id"] for job in reversed(performance_jobs)] == ["v01"]

    handled = StudioWorker(
        queue,
        project_root=tmp_path,
        worker_id="e2e-performance-worker",
    ).run_forever(
        poll_interval=0,
        max_jobs=1,
        recover_stale_after=None,
    )
    assert handled == 1
    performance_jobs = [
        job for job in queue.list_jobs(limit=20) if job.job_type == CAMPAIGN_VARIANT_RUN
    ]
    assert {job.state for job in performance_jobs} == {OperationalState.SUCCEEDED}
    assert {job.research_verdict for job in performance_jobs} == {"FAIL"}
    assert {job.attempt_reserved for job in performance_jobs} == {True}
    for job in performance_jobs:
        bundle_path = tmp_path / str((job.result or {})["result_bundle_path"])
        assert inspect_finalized_result(bundle_path)["valid"] is True
        assert not (bundle_path.parents[1] / "candidate_strategy_report.md").exists()

    app = reopen_campaigns()
    rows, latest = _results_matrix_state(tmp_path, "no_code_publication")
    assert len(rows) == 1
    assert {row["research verdict"] for row in rows} == {"FAIL"}
    assert all(row["first failed or unresolved gate"] != "none" for row in rows)
    assert set(latest) == {"v01"}
    assert any("Sequential variant stage matrix" in item.value for item in app.markdown)
    assert any("Stage criteria · actual versus required" in item.value for item in app.markdown)
    assert any("Required metrics" in item.value for item in app.markdown)
    assert app.error


def test_results_matrix_always_leads_with_all_five_declared_variants(tmp_path: Path) -> None:
    campaign = tmp_path / "research/campaigns/active/demo"
    campaign.mkdir(parents=True)
    variants = [f"v{index:02d}" for index in range(1, 6)]
    (campaign / "campaign.yaml").write_text(
        yaml.safe_dump({"campaign_id": "demo", "variants": variants}),
        encoding="utf-8",
    )
    (campaign / "results_index.yaml").write_text(
        yaml.safe_dump(
            {
                "runs": [
                    {
                        "variant_id": "v02",
                        "research_verdict": "FAIL",
                        "failed_stage": "monkey_test",
                        "test_run_id": "run1",
                        "updated_at": "2026-07-15T00:00:00+00:00",
                    }
                ]
            }
        ),
        encoding="utf-8",
    )

    rows, latest = _results_matrix_state(tmp_path, "demo")

    assert [row["variant"] for row in rows] == variants
    assert rows[0]["research verdict"] == "PENDING"
    assert rows[1]["research verdict"] == "FAIL"
    assert rows[1]["first failed or unresolved gate"] == "monkey_test"
    assert set(latest) == {"v02"}


def test_visual_rule_builder_emits_bounded_boolean_ast_and_frozen_tunable_grid() -> None:
    values = {
        "condition_type": "Comparison with a threshold",
        "feature": "close",
        "lag": 0,
        "operator": "greater than",
        "threshold": 0.0,
        "tune_threshold": True,
        "threshold_values": "-3, -2, -1, 0, 1, 2, 3, 4",
        "signals": "Symmetric long and short",
        "second_filter": True,
        "filter_feature": "volume",
        "filter_operator": "greater than",
        "filter_threshold": 100.0,
        "boolean_group": "All conditions",
        "signal_start_time": "09:30:00",
        "signal_end_time": "15:45:00",
        "max_trades_per_day": 1,
        "rth_only": True,
    }

    parsed = BarRuleV1.model_validate(_build_visual_rule(values, "5m"))

    assert parsed.bar_interval_minutes == 5.0
    assert parsed.long_rule.type == "all"
    assert parsed.short_rule.type == "all"
    assert parsed.tunables[0].values == [-3.0, -2.0, -1.0, 0.0, 1.0, 2.0, 3.0, 4.0]
    assert _parse_grid_values("1, 2, 3", "integer") == [1, 2, 3]


def _attempt_sources(root: Path) -> tuple[Path, str]:
    campaign = root / "research/campaigns/active/demo"
    variants = [f"v{index:02d}" for index in range(1, 6)]
    campaign.mkdir(parents=True)
    (campaign / "campaign.yaml").write_text(
        yaml.safe_dump({"campaign_id": "demo", "variants": variants}),
        encoding="utf-8",
    )
    for variant in variants:
        path = campaign / "variants" / variant / "config.yaml"
        path.parent.mkdir(parents=True)
        path.write_text(
            yaml.safe_dump(
                {
                    "campaign_id": "demo",
                    "variant_id": variant,
                    "attempt_id": "original",
                    "attempt_kind": "original",
                    "test_run_id": "run1",
                }
            ),
            encoding="utf-8",
        )
    attempt_id = "replication_20260715"
    hashes = {}
    for variant in variants:
        path = campaign / "follow_up_attempts" / attempt_id / variant / "config.yaml"
        path.parent.mkdir(parents=True)
        path.write_text(
            yaml.safe_dump(
                {
                    "campaign_id": "demo",
                    "variant_id": variant,
                    "attempt_id": attempt_id,
                    "attempt_kind": "replication",
                    "parent_attempt_id": "original",
                    "test_run_id": f"attempt_{attempt_id}",
                }
            ),
            encoding="utf-8",
        )
        hashes[variant] = hashlib.sha256(path.read_bytes()).hexdigest()
    manifest = campaign / "follow_up_attempts" / attempt_id / "attempt_manifest.json"
    manifest.write_text(
        json.dumps(
            {
                "schema": "alphaquest.follow-up-attempt/v1",
                "campaign_id": "demo",
                "attempt_id": attempt_id,
                "attempt_kind": "replication",
                "parent_attempt_id": "original",
                "reason": "Explicit immutable replication used to test exact result-to-source resolution.",
                "config_sha256": hashes,
            }
        ),
        encoding="utf-8",
    )
    return campaign, attempt_id


def test_review_queue_lists_original_and_follow_up_mechanics_configs(tmp_path: Path) -> None:
    _campaign, attempt_id = _attempt_sources(tmp_path)

    paths = _governed_review_config_paths(tmp_path)

    assert len(paths) == 10
    assert sum(attempt_id in str(path) for path in paths) == 5


def test_candidate_review_resolves_exact_follow_up_source_from_finalization_manifest(tmp_path: Path) -> None:
    campaign, attempt_id = _attempt_sources(tmp_path)
    config = campaign / "follow_up_attempts" / attempt_id / "v03/config.yaml"
    reporting = tmp_path / "research/evidence/runs/demo/v03/ES" / f"attempt_{attempt_id}/reporting_v2"
    reporting.mkdir(parents=True)
    ResultBundleBuilder().build_and_write(
        pd.DataFrame(columns=["net_pnl"]),
        reporting,
        campaign_id="demo",
        variant_id="v03",
        run_id=f"attempt_{attempt_id}",
        verdict="NEEDS MANUAL REVIEW",
    )
    bundle = reporting / "result_bundle_v2.json"
    source_evidence = reporting.parent / "run_manifest.json"
    source_evidence.write_text('{"status":"complete"}\n', encoding="utf-8")
    journal = tmp_path / ".alphaquest-studio/recovery/follow-up-result-job.json"
    journal.parent.mkdir(parents=True)
    journal.write_text(
        json.dumps(
            {
                "schema": "alphaquest.studio-recovery-journal/v1",
                "job_id": "follow-up-result-job",
                "phase": "FINALIZED",
                "terminal": True,
                "automatic_replay_permitted": False,
                "events": [{"phase": "FINALIZED"}],
            }
        )
        + "\n",
        encoding="utf-8",
    )
    reporting_hashes = {
        path.name: hashlib.sha256(path.read_bytes()).hexdigest()
        for path in reporting.iterdir()
        if path.is_file() and path.name != "finalization_manifest.json"
    }
    (reporting / "finalization_manifest.json").write_text(
        json.dumps(
            {
                "schema": "alphaquest.studio-finalization/v1",
                "job_id": "follow-up-result-job",
                "campaign_id": "demo",
                "variant_id": "v03",
                "run_id": f"attempt_{attempt_id}",
                "research_verdict": "NEEDS MANUAL REVIEW",
                "automatic_replay_permitted": False,
                "source_config": str(config.relative_to(tmp_path)),
                "result_bundle": "result_bundle_v2.json",
                "evidence_issues": ["manual review fixture"],
                "evidence_artifact_sha256": {
                    source_evidence.name: hashlib.sha256(source_evidence.read_bytes()).hexdigest()
                },
                "reporting_artifact_sha256": reporting_hashes,
                "ledger_recorded": True,
                "registry_published": True,
                "registry_counts": {},
                "recovery_journal": str(journal.resolve()),
                "terminal_recovery_phase": "FINALIZED",
                "terminal_recovery_journal_sha256": hashlib.sha256(journal.read_bytes()).hexdigest(),
                "transaction_complete": True,
            }
        ),
        encoding="utf-8",
    )

    resolved = _resolve_result_config(
        tmp_path,
        bundle,
        campaign_id="demo",
        variant_id="v03",
        run_id=f"attempt_{attempt_id}",
    )

    assert resolved == config.resolve()
    config.write_text(config.read_text(encoding="utf-8") + "changed: true\n", encoding="utf-8")
    with pytest.raises(ValueError, match="immutable follow-up config hash drift"):
        _resolve_result_config(
            tmp_path,
            bundle,
            campaign_id="demo",
            variant_id="v03",
            run_id=f"attempt_{attempt_id}",
        )
