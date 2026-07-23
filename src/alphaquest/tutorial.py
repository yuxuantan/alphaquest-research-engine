from __future__ import annotations

from contextlib import contextmanager
from datetime import date, timedelta
import hashlib
import json
import math
import os
from pathlib import Path
import shutil
from typing import Any

import pandas as pd
import yaml

from alphaquest.authoring import CampaignDraftV1, campaign_confirmation_context_sha256
from alphaquest.backtest.engine import BacktestEngine
from alphaquest.dashboard.validation_app import save_manual_review_annotation
from alphaquest.data.pipeline import prepare_data
from alphaquest.data.subset import subset_from_config
from alphaquest.research.monkey import run_monkey
from alphaquest.studio.approvals import MechanicsApprovalService
from alphaquest.studio.data_import import DataImportSpec, DatasetImporter
from alphaquest.studio.drafts import DraftStore
from alphaquest.studio.followups import FollowUpAttemptService
from alphaquest.studio.jobs import OperationalState, SQLiteJobQueue
from alphaquest.studio.publishing import StudioPublicationService
from alphaquest.studio.results import ResultBundleBuilder
from alphaquest.studio.variants import suggest_variant_card
from alphaquest.studio.worker import StudioWorker


TUTORIAL_SCHEMA = "alphaquest.tutorial/v2"
TUTORIAL_CAMPAIGN_ID = "tutorial_calendar_bias"
TUTORIAL_DATASET_ID = "synthetic_tutorial_es_1m"
TUTORIAL_RANDOM_SEED = 1729
TUTORIAL_RANDOM_RUNS = 32
CORE_MIN_TRADES = 5
RANDOM_ENTRY_BEAT_THRESHOLD = 0.80


def run_tutorial(
    *,
    output_root: str | Path = "examples/tutorial_campaign/generated",
    execute: bool = True,
) -> dict[str, Any]:
    """Build and optionally execute the isolated Studio teaching campaign.

    The tutorial deliberately uses synthetic, trending bars so a calendar-timed
    strategy can look profitable while having no timing edge.  All source,
    ledger, evidence, approval, and runtime writes stay below ``output_root``;
    configured production roots are never consulted or mutated.  Operational
    PASS only means the teaching exercise completed correctly; the research
    verdict is always FAIL and the output is never promotable.
    """

    root = Path(output_root).resolve()
    _reset_output(root)
    (root / ".generated_by_alphaquest").write_text(
        "Synthetic, non-promotable tutorial output. Safe to delete.\n",
        encoding="utf-8",
    )
    layout_path = _write_isolated_storage_layout(root)
    with _forced_storage_layout(layout_path):
        return _run_tutorial_workspace(root, execute=execute)


def _run_tutorial_workspace(root: Path, *, execute: bool) -> dict[str, Any]:
    data = _tutorial_bars()
    source_path = root / "intake" / "tutorial_es_1m_source.csv"
    source_path.parent.mkdir(parents=True)
    data.to_csv(source_path, index=False)
    imported = DatasetImporter(root).import_file(
        source_path,
        DataImportSpec(
            dataset_id=TUTORIAL_DATASET_ID,
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
    draft = _tutorial_draft(imported.manifest)
    DraftStore(root).save(TUTORIAL_CAMPAIGN_ID, draft.model_dump(mode="json", by_alias=True), wizard_step=7)
    publisher = StudioPublicationService(root)
    publication_preflight = publisher.preflight_draft(draft)
    publication = publisher.publish(draft)
    configs = [publication.destination / "variants" / "v01" / "config.yaml"]
    data_path = imported.canonical_path

    payload: dict[str, Any] = {
        "schema": TUTORIAL_SCHEMA,
        "status": "PASS",
        "operational_status": "PASS",
        "purpose": "Synthetic 15-minute Studio onboarding only; not research evidence.",
        "synthetic": True,
        "promotion_eligible": False,
        "production_ledger_update": False,
        "research_verdict": "FAIL",
        "verdict_reason": "Synthetic teaching data cannot support a candidate strategy.",
        "random_seed": TUTORIAL_RANDOM_SEED,
        "data_path": str(data_path),
        "configs": [str(path) for path in configs],
        "isolated_workspace": str(root),
        "isolated_ledger_path": str(root / "research_ledger.csv"),
        "governed_services": {
            "dataset_import": {
                "service": "DatasetImporter",
                "manifest_path": str(imported.manifest_path),
                "quality_verdict": imported.manifest.quality_verdict,
                "canonical_sha256": imported.manifest.canonical_sha256,
            },
            "draft_validation": {
                "service": "CampaignDraftV1 + DraftStore",
                "draft_path": str(DraftStore(root).path_for(TUTORIAL_CAMPAIGN_ID)),
                "frozen": draft.frozen,
                "variant_count": len(draft.variants),
            },
            "publication": {
                "service": "StudioPublicationService",
                "preflight_verdict": publication_preflight["preflight_verdict"],
                "publication_verdict": publication.verdict,
                "journal_path": str(publication.journal_path),
                "ledger_rows_appended": publication.ledger_rows_appended,
            },
        },
        "executed": bool(execute),
        "walkthrough": _walkthrough_steps(),
    }

    if execute:
        execution = _execute_governed_tutorial(
            root=root,
            configs=configs,
            draft=draft,
            data_quality_verdict=imported.manifest.quality_verdict,
            intake_verdict=publication_preflight["preflight_verdict"],
        )
        governed_execution_services = execution.pop("_governed_services")
        payload.update(execution)
        payload["governed_services"].update(governed_execution_services)
    else:
        matrix = _planned_stage_matrix(
            intake_verdict=publication_preflight["preflight_verdict"],
            data_quality_verdict=imported.manifest.quality_verdict,
        )
        _write_stage_matrix(root / "stage_matrix.csv", matrix)
        _write_json(root / "stage_results.json", {"variants": matrix})
        payload.update(
            {
                "stage_matrix_path": str(root / "stage_matrix.csv"),
                "stage_matrix": matrix,
                "lesson_demonstrated": False,
                "lesson": "Run the tutorial to see why positive core PnL is not enough.",
            }
        )

    _write_tutorial_report(root / "tutorial_report.md", payload)
    payload["tutorial_report_path"] = str(root / "tutorial_report.md")
    _write_json(root / "tutorial_manifest.json", payload)
    return payload


def _tutorial_draft(dataset: Any) -> CampaignDraftV1:
    long_failure = (
        "A broad intraday drift can make arbitrary long entry times profitable, so the seeded randomized-entry "
        "benchmark may reject apparent calendar timing skill even when the limited core PnL is positive."
    )
    document: dict[str, Any] = {
        "schema": "alphaquest.campaign-draft/v1",
        "campaign_id": TUTORIAL_CAMPAIGN_ID,
        "title": "Synthetic calendar-bias teaching edge",
        "created_at": "2026-01-05",
        "instrument": "ES",
        "timeframe": "1m",
        "edge_family": "synthetic_calendar_bias",
        "hypothesis": (
            "On the constructed ES-like teaching series, the completed 09:35 regular-session bar predicts "
            "positive continuation from the next legal bar open until a fixed intraday exit."
        ),
        "expected_mechanism": (
            "The teaching claim attributes continuation to a weekday session bias, while the deliberately broad "
            "upward drift provides the declared confound that randomized entries should expose."
        ),
        "holding_horizon": "From the next legal one-minute bar open until the fixed stop, target, or 10:25 flatten.",
        "known_failure_modes": [long_failure],
        "sources": [
            {
                "title": "AlphaQuest isolated synthetic tutorial protocol",
                "authors": ["AlphaQuest Research Engineering"],
                "year": 2026,
                "link": "https://alphaquest.local/tutorial/synthetic-calendar-bias",
                "relevance": (
                    "This is an explicitly synthetic teaching declaration, not external evidence for a market edge; "
                    "it exists only to demonstrate governed rejection when randomized timing performs better."
                ),
            }
        ],
        "economic_edge_fingerprint": {
            "market_behavior": "Completed early-session bars are followed by same-direction intraday continuation.",
            "causal_mechanism": "A purported weekday positioning imbalance persists after the observed decision bar.",
            "signal_inputs": ["Completed one-minute OHLCV bars and the known weekday/session clock"],
            "market_context": "Synthetic ES-like regular-session bars with an intentionally disclosed upward drift.",
            "holding_period": "Next-bar-open entry through a fixed same-session stop, target, or forced flatten.",
        },
        "duplicate_review": {
            "reviewed_campaign_ids": [],
            "ledger_queries": ["isolated synthetic calendar bias tutorial"],
            "conclusion": "distinct",
            "substantive_distinction": (
                "The campaign ID, dataset, ledger, evidence, and runtime all exist inside a disposable tutorial "
                "workspace and are prohibited from promotion or comparison with real authored research."
            ),
        },
        "dataset": dataset.model_dump(mode="json", by_alias=True),
        "execution": {
            "session_start": "09:30:00",
            "session_end": "10:30:00",
            "latest_entry_time": "10:15:00",
            "flatten_time": "10:25:00",
            "latest_flat_time": "10:26:00",
            "overnight_allowed": False,
            "initial_balance": 50_000.0,
            "tick_size": 0.25,
            "point_value": 50.0,
            "tick_value": 12.5,
            "commission_per_contract": 2.5,
            "slippage_ticks": 1.0,
            "contracts": 1,
            "prop_profile": "synthetic_tutorial_non_promotable",
        },
        "authoring_lane": "certified_recipe",
        "certified_recipe": "calendar_session_bias",
        "variant_protocol": "sequential_failure_informed",
        "sequential_variant_history": [],
        "frozen": False,
    }
    variants = [suggest_variant_card(document, index=0)]
    variants[0]["stop"]["params"]["stop_points"] = 10.0
    for variant in variants:
        variant["confirmed"] = True
    document["variants"] = variants
    document["confirmation_context_sha256"] = campaign_confirmation_context_sha256(document)
    document["frozen"] = True
    return CampaignDraftV1.model_validate(document)


def _execute_governed_tutorial(
    *,
    root: Path,
    configs: list[Path],
    draft: CampaignDraftV1,
    data_quality_verdict: str,
    intake_verdict: str,
) -> dict[str, Any]:
    follow_ups = FollowUpAttemptService(root)
    mechanics_jobs = follow_ups.queue_mechanics_validation(TUTORIAL_CAMPAIGN_ID, "original")
    queue_path = root / "run-store" / "studio-runtime" / "jobs.sqlite3"
    queue = SQLiteJobQueue(queue_path)
    worker = StudioWorker(queue, project_root=root, worker_id="synthetic-tutorial-mechanics-worker")
    completed_mechanics = [worker.run_once() for _ in mechanics_jobs]
    if any(job is None or job.state != OperationalState.SUCCEEDED for job in completed_mechanics):
        states = [None if job is None else job.state.value for job in completed_mechanics]
        raise RuntimeError(f"isolated mechanics worker did not complete the current job: {states}")

    approval_service = MechanicsApprovalService()
    approval_reports: list[dict[str, Any]] = []
    for config_path in configs:
        plan = approval_service.plan(config_path)
        if plan.blockers:
            raise RuntimeError(
                f"isolated mechanics review is blocked for {config_path.parent.name}: " + "; ".join(plan.blockers)
            )
        if not plan.evidence_dir:
            raise RuntimeError(f"isolated mechanics evidence path is unresolved for {config_path.parent.name}")
        for trade_id in plan.sampled_trade_ids:
            save_manual_review_annotation(
                plan.evidence_dir,
                trade_id,
                "Correct",
                "Synthetic tutorial self-review confirms implementation matches the frozen specification only.",
                reviewed_at="2026-01-20T12:00:00+00:00",
            )
        approval_service.approve(
            config_path,
            reviewer="synthetic-tutorial-researcher",
            notes=(
                "Reviewed every service-selected mechanics category against synthetic evidence; this decision "
                "confirms implementation fidelity only and is not profitability or candidate approval."
            ),
            reviewed_at="2026-01-20T12:30:00+00:00",
        )
        approval_reports.append(approval_service.inspect(config_path))

    protocol_hash = hashlib.sha256(
        json.dumps(draft.model_dump(mode="json", by_alias=True), sort_keys=True).encode("utf-8")
    ).hexdigest()
    evaluation_job = queue.submit(
        job_type="synthetic_tutorial_scientific_evaluation",
        campaign_id=TUTORIAL_CAMPAIGN_ID,
        payload={
            "campaign_id": TUTORIAL_CAMPAIGN_ID,
            "config_paths": [str(path) for path in configs],
            "synthetic": True,
            "promotion_eligible": False,
        },
        idempotency_key=f"{TUTORIAL_CAMPAIGN_ID}:synthetic-evaluation:{protocol_hash}",
        hash_locks={"frozen_protocol_sha256": protocol_hash},
    )
    terminal = queue.run_once(
        worker_id="synthetic-tutorial-result-worker",
        observed_hashes={"frozen_protocol_sha256": protocol_hash},
        executor=lambda context, job: _execute_variants(
            root=root,
            configs=configs,
            approval_reports=approval_reports,
            data_quality_verdict=data_quality_verdict,
            intake_verdict=intake_verdict,
        ),
    )
    if terminal is None or terminal.job_id != evaluation_job.job_id or terminal.state != OperationalState.SUCCEEDED:
        state = None if terminal is None else terminal.state.value
        error = None if terminal is None else terminal.error
        raise RuntimeError(f"isolated result job did not complete: state={state}, error={error}")
    execution = dict(terminal.result or {})
    execution["_governed_services"] = {
        "job_queue": {
            "service": "SQLiteJobQueue + StudioWorker",
            "database_path": str(queue_path),
            "mechanics_job_states": [str(job.state.value) for job in completed_mechanics if job is not None],
            "result_job_state": terminal.state.value,
            "attempt_reserved": terminal.attempt_reserved,
        },
        "mechanics_approval": {
            "service": "MechanicsApprovalService",
            "approved_variants": sum(
                report.get("status") == "APPROVED_FOR_TESTING" for report in approval_reports
            ),
            "review_scope": "implementation_matches_frozen_specification",
            "profitability_approval": False,
        },
        "results": {
            "service": "ResultBundleBuilder / alphaquest.result-bundle/v2",
            "bundle_count": len(execution.get("variant_runs") or []),
        },
    }
    return execution


def _execute_variants(
    *,
    root: Path,
    configs: list[Path],
    approval_reports: list[dict[str, Any]],
    data_quality_verdict: str,
    intake_verdict: str,
) -> dict[str, Any]:
    core_results: dict[str, dict[str, Any]] = {}

    for config_path in configs:
        config = yaml.safe_load(config_path.read_text(encoding="utf-8"))
        variant_id = str(config["variant_id"])
        engine_data, _, execution_data = prepare_data(
            _workspace_data_config(config["data"], root),
            None,
            subset_from_config(config, "core"),
            timeframe=str(config["timeframe"]),
            include_execution_data=True,
        )
        detail_data = execution_data if str(config["timeframe"]) != "1m" else None
        result = BacktestEngine(config).run(engine_data, detail_data=detail_data)
        run_dir = root / "runs" / variant_id
        run_dir.mkdir(parents=True)
        _finite_frame(result["trades"]).to_csv(run_dir / "trade_log.csv", index=False)
        _finite_frame(result["daily"]).to_csv(run_dir / "daily_results.csv", index=False)
        core_stage = _core_stage(variant_id, result["metrics"])
        core_results[variant_id] = {
            "config": config,
            "result": result,
            "stage": core_stage,
            "run_dir": run_dir,
            "engine_data": engine_data,
        }

    benchmark_payloads: dict[str, dict[str, Any]] = {}
    benchmark_stages: dict[str, dict[str, Any]] = {}
    for variant_id, core in core_results.items():
        if core["stage"]["result"] != "PASS":
            benchmark_stages[variant_id] = _not_run_random_stage(core["stage"])
            continue
        benchmark_dir = root / "randomized_entry_benchmark" / variant_id
        benchmark_dir.mkdir(parents=True)
        random_rows, random_summary = run_monkey(
            core["engine_data"],
            core["config"],
            _tutorial_monkey_config(),
            {"min_trades": 1},
            core_trades=core["result"]["trades"],
        )
        _finite_frame(random_rows).to_csv(benchmark_dir / "randomized_entry_results.csv", index=False)
        benchmark_payload = {
            "schema": "alphaquest.tutorial.randomized-entry/v1",
            "synthetic": True,
            "promotion_eligible": False,
            "seed": TUTORIAL_RANDOM_SEED,
            "summary": _json_safe(random_summary),
        }
        _write_json(benchmark_dir / "summary.json", benchmark_payload)
        benchmark_payloads[variant_id] = benchmark_payload
        benchmark_stages[variant_id] = _randomized_entry_stage(
            random_summary,
            evidence_path=f"randomized_entry_benchmark/{variant_id}/summary.json",
        )

    approval_by_variant = {
        Path(str(report.get("config_path") or "")).parent.name: report
        for report in approval_reports
    }
    stage_details: list[dict[str, Any]] = []
    matrix: list[dict[str, Any]] = []
    variant_results: list[dict[str, Any]] = []
    for variant_id in sorted(core_results):
        core = core_results[variant_id]
        core_stage = core["stage"]
        random_stage = benchmark_stages[variant_id]
        approval_report = approval_by_variant.get(variant_id) or {}
        mechanics_result = (
            "PASS" if approval_report.get("status") == "APPROVED_FOR_TESTING" else "NEEDS MANUAL REVIEW"
        )
        data_result = data_quality_verdict if data_quality_verdict in {"PASS", "FAIL", "NEEDS MANUAL REVIEW"} else "NEEDS MANUAL REVIEW"
        intake_result = intake_verdict if intake_verdict in {"PASS", "FAIL", "NEEDS MANUAL REVIEW"} else "NEEDS MANUAL REVIEW"
        first_failed = (
            "intake"
            if intake_result != "PASS"
            else "data_preflight"
            if data_result != "PASS"
            else "mechanics_approval"
            if mechanics_result != "PASS"
            else "limited_core_test"
            if core_stage["result"] == "FAIL"
            else "randomized_entry_benchmark"
        )
        matrix.append(
            {
                "variant_id": variant_id,
                "intake": intake_result,
                "data_preflight": data_result,
                "mechanics_approval": mechanics_result,
                "limited_core_test": core_stage["result"],
                "randomized_entry_benchmark": random_stage["result"],
                "acceptance_oos": "NOT_RUN",
                "first_failed_or_unresolved_gate": first_failed,
                "research_verdict": "FAIL",
            }
        )
        stage_details.append(
            {
                "variant_id": variant_id,
                "stages": [
                    _simple_stage(
                        "intake",
                        intake_result,
                        "StudioPublicationService compiled, preflighted, and atomically published the frozen brief.",
                    ),
                    _simple_stage(
                        "data_preflight",
                        data_result,
                        "DatasetImporter produced the governed canonical manifest and disclosed every quality check.",
                    ),
                    _simple_stage(
                        "mechanics_approval",
                        mechanics_result,
                        "MechanicsApprovalService verified automated checks, required samples, hashes, lane, and schema.",
                    ),
                    core_stage,
                    random_stage,
                    _simple_stage(
                        "acceptance_oos",
                        "NOT_RUN",
                        f"Stopped after first failed gate: {first_failed}.",
                    ),
                ],
                "first_failed_or_unresolved_gate": first_failed,
                "research_verdict": "FAIL",
            }
        )

        criteria = _result_bundle_criteria(core_stage, random_stage)
        result = core["result"]
        evaluation_data = core["engine_data"]
        bundle = ResultBundleBuilder().build_and_write(
            result["trades"],
            core["run_dir"],
            campaign_id=TUTORIAL_CAMPAIGN_ID,
            variant_id=variant_id,
            run_id=f"synthetic_tutorial_{variant_id}",
            verdict="FAIL",
            stage_criteria=criteria,
            initial_balance=50_000.0,
            prop_rule_outcome=(
                "PASS" if int(result["metrics"].get("apex_rule_violations") or 0) == 0 else "FAIL"
            ),
            forced_flatten_compliance=int(result["metrics"].get("apex_rule_violations") or 0) == 0,
            generated_at="2026-01-20T13:00:00+00:00",
            exchange_timezone="America/New_York",
            evaluation_start=evaluation_data["timestamp"].min(),
            evaluation_end=evaluation_data["timestamp"].max(),
            trading_dates=pd.to_datetime(evaluation_data["timestamp"]).dt.date.unique().tolist(),
        )
        variant_results.append(
            {
                "variant_id": variant_id,
                "run_dir": str(core["run_dir"]),
                "result_bundle_path": str(core["run_dir"] / "result_bundle_v2.json"),
                "result_bundle_schema": bundle.schema_name,
                "total_trades": int(result["metrics"].get("total_trades") or 0),
                "net_profit": float(result["metrics"].get("net_profit") or 0.0),
                "apex_rule_violations": int(result["metrics"].get("apex_rule_violations") or 0),
                "core_result": core_stage["result"],
                "core_reason": core_stage["reason"],
                "first_failed_or_unresolved_gate": first_failed,
            }
        )

    _write_stage_matrix(root / "stage_matrix.csv", matrix)
    _write_json(root / "stage_results.json", {"variants": stage_details})

    lead_benchmark = benchmark_payloads.get("v01")
    if lead_benchmark is None:
        raise RuntimeError("lead tutorial variant did not reach its declared randomized-entry gate")
    lead_summary = lead_benchmark["summary"]
    core_net_profit = float(lead_summary["core_metrics"]["net_profit"])
    random_median = float(lead_summary["median_net_profit"])
    lesson_demonstrated = (
        core_net_profit > 0
        and random_median > core_net_profit
        and not bool(lead_summary["meets_monkey_goal"])
    )
    operational_status = "PASS" if lesson_demonstrated else "FAIL"
    return {
        "status": operational_status,
        "operational_status": operational_status,
        "variant_runs": variant_results,
        "run_dir": str(root / "runs" / "v01"),
        "total_trades": sum(row["total_trades"] for row in variant_results),
        "net_profit": core_net_profit,
        "apex_rule_violations": sum(row["apex_rule_violations"] for row in variant_results),
        "randomized_entry_benchmark_path": str(
            root / "randomized_entry_benchmark" / "v01" / "summary.json"
        ),
        "randomized_entry_benchmark": lead_benchmark,
        "stage_matrix_path": str(root / "stage_matrix.csv"),
        "stage_matrix": matrix,
        "lesson_demonstrated": lesson_demonstrated,
        "lesson": (
            "The lead variant made positive core PnL but failed because matched, seeded randomized entries "
            "performed better. Positive backtest PnL alone is not evidence of timing skill."
        ),
        "research_verdict": "FAIL",
        "verdict_reason": (
            "Lead variant v01 failed the randomized-entry benchmark; other variants either failed the earlier "
            "core gate or independently failed their randomized-entry gate."
        ),
    }


def _workspace_data_config(data_config: dict[str, Any], root: Path) -> dict[str, Any]:
    resolved = dict(data_config)
    for name in ("raw_csv", "raw_parquet", "roll_calendar"):
        value = resolved.get(name)
        if value and not Path(str(value)).is_absolute():
            resolved[name] = str((root / str(value)).resolve())
    return resolved


def _tutorial_bars() -> pd.DataFrame:
    rows = []
    session = date(2026, 1, 5)
    sessions = 0
    while sessions < 10:
        if session.weekday() < 5:
            start = pd.Timestamp(f"{session.isoformat()} 09:30:00", tz="America/New_York")
            for minute in range(61):
                timestamp = start + pd.Timedelta(minutes=minute)
                open_price = 5000.0 + sessions * 4.0 + minute * 2.0
                rows.append(
                    {
                        "timestamp": timestamp,
                        "open": open_price,
                        "high": open_price + 2.5,
                        "low": open_price - 0.5,
                        "close": open_price + 2.0,
                        "volume": 1000 + minute * 10,
                        "symbol": "ES",
                    }
                )
            sessions += 1
        session += timedelta(days=1)
    return pd.DataFrame(rows)


def _core_stage(variant_id: str, metrics: dict[str, Any]) -> dict[str, Any]:
    trades = int(metrics.get("total_trades") or 0)
    net_profit = float(metrics.get("net_profit") or 0.0)
    violations = int(metrics.get("apex_rule_violations") or 0)
    criteria = [
        _criterion("trade_count", ">=", CORE_MIN_TRADES, trades, trades >= CORE_MIN_TRADES),
        _criterion("net_profit_after_costs", ">", 0.0, net_profit, net_profit > 0.0),
        _criterion("forced_flatten_violations", "==", 0, violations, violations == 0),
    ]
    passed = all(bool(row["result"]) for row in criteria)
    if passed:
        reason = f"{variant_id} made ${net_profit:,.2f} after costs across {trades} trades."
    elif trades < CORE_MIN_TRADES:
        reason = f"Only {trades} trades; at least {CORE_MIN_TRADES} are required for this teaching gate."
    elif net_profit <= 0:
        reason = f"Net profit after costs was ${net_profit:,.2f}; required greater than $0."
    else:
        reason = f"Forced-flatten violations were {violations}; required 0."
    return {
        "stage_id": "limited_core_test",
        "result": "PASS" if passed else "FAIL",
        "reason": reason,
        "criteria": criteria,
        "evidence_path": f"runs/{variant_id}/result_bundle_v2.json",
    }


def _randomized_entry_stage(
    summary: dict[str, Any],
    *,
    evidence_path: str = "randomized_entry_benchmark/v01/summary.json",
) -> dict[str, Any]:
    net_rate = float(summary["core_beats_monkey_net_profit_rate"])
    drawdown_rate = float(summary["core_beats_monkey_max_drawdown_rate"])
    passed = bool(summary["meets_monkey_goal"])
    criteria = [
        _criterion(
            "core_beats_random_net_profit_rate",
            ">=",
            RANDOM_ENTRY_BEAT_THRESHOLD,
            net_rate,
            net_rate >= RANDOM_ENTRY_BEAT_THRESHOLD,
        ),
        _criterion(
            "core_beats_random_drawdown_rate",
            ">=",
            RANDOM_ENTRY_BEAT_THRESHOLD,
            drawdown_rate,
            drawdown_rate >= RANDOM_ENTRY_BEAT_THRESHOLD,
        ),
    ]
    core_profit = float(summary["core_metrics"]["net_profit"])
    median_profit = float(summary["median_net_profit"])
    return {
        "stage_id": "randomized_entry_benchmark",
        "result": "PASS" if passed else "FAIL",
        "reason": (
            f"Core made ${core_profit:,.2f}, but seeded matched random entries had median net profit "
            f"${median_profit:,.2f}; core beat random net profit in {net_rate:.1%} of runs versus the "
            f"required {RANDOM_ENTRY_BEAT_THRESHOLD:.0%}."
        ),
        "criteria": criteria,
        "evidence_path": evidence_path,
    }


def _not_run_random_stage(core_stage: dict[str, Any]) -> dict[str, Any]:
    return _simple_stage(
        "randomized_entry_benchmark",
        "NOT_RUN",
        f"Stopped after limited core result {core_stage['result']}: {core_stage['reason']}",
    )


def _criterion(metric: str, operator: str, threshold: Any, actual: Any, result: bool) -> dict[str, Any]:
    return {
        "metric": metric,
        "operator": operator,
        "threshold": threshold,
        "actual": actual,
        "result": result,
        "reason": None if result else f"actual {actual} did not satisfy {operator} {threshold}",
    }


def _simple_stage(stage_id: str, result: str, reason: str) -> dict[str, Any]:
    return {"stage_id": stage_id, "result": result, "reason": reason, "criteria": []}


def _result_bundle_criteria(
    core_stage: dict[str, Any],
    random_stage: dict[str, Any],
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for stage in (core_stage, random_stage):
        if stage.get("result") == "NOT_RUN":
            continue
        for criterion in stage.get("criteria") or []:
            passed = bool(criterion["result"])
            rows.append(
                {
                    "stage": str(stage["stage_id"]),
                    "metric": str(criterion["metric"]),
                    "operator": str(criterion["operator"]),
                    "threshold": {"value": criterion["threshold"], "reason": None},
                    "actual": {"value": criterion["actual"], "reason": None},
                    "result": "PASS" if passed else "FAIL",
                    "reason": (
                        f"Actual {criterion['actual']} satisfied {criterion['operator']} "
                        f"{criterion['threshold']}."
                        if passed
                        else str(criterion.get("reason") or stage.get("reason") or "criterion failed")
                    ),
                    "evidence_path": str(stage.get("evidence_path") or "") or None,
                }
            )
    return rows


def _tutorial_monkey_config() -> dict[str, Any]:
    return {
        "seed": TUTORIAL_RANDOM_SEED,
        "runs": TUTORIAL_RANDOM_RUNS,
        "beat_threshold": RANDOM_ENTRY_BEAT_THRESHOLD,
        "parallel": False,
        "constraints": {
            "rth_only": True,
            "trade_count_tolerance": 0,
            "trade_count_tolerance_pct": 0.0,
            "long_short_ratio_tolerance": 0.0,
            "average_bars_tolerance_pct": 0.0,
            "duration_sampling": "core_distribution",
            "enforce_non_overlapping": True,
            "enforce_max_trades_per_day": True,
        },
    }


def _walkthrough_steps() -> list[dict[str, Any]]:
    return [
        {"step": 1, "minutes": 2, "title": "Research declaration", "action": "Review the falsifiable synthetic claim and failure modes."},
        {"step": 2, "minutes": 1, "title": "Duplicate review", "action": "Observe the isolated tutorial-only duplicate decision."},
        {"step": 3, "minutes": 2, "title": "Data intake", "action": "Inspect timezone, bar semantics, quality checks, and synthetic warning."},
        {"step": 4, "minutes": 2, "title": "Execution assumptions", "action": "Confirm costs, session, cutoff, flattening, and no overnight exposure."},
        {"step": 5, "minutes": 2, "title": "Mechanics review", "action": "Confirm completed-bar signals enter on the next bar."},
        {"step": 6, "minutes": 2, "title": "First variant", "action": "Confirm one mechanic before PnL and add no later mechanic unless this one fails."},
        {"step": 7, "minutes": 4, "title": "Staged results", "action": "Read the first failed gate and reject profitable but non-distinct timing."},
    ]


def _planned_stage_matrix(
    *,
    intake_verdict: str,
    data_quality_verdict: str,
) -> list[dict[str, Any]]:
    return [
        {
            "variant_id": f"v{index:02d}",
            "intake": intake_verdict,
            "data_preflight": data_quality_verdict,
            "mechanics_approval": "NOT_RUN",
            "limited_core_test": "NOT_RUN",
            "randomized_entry_benchmark": "NOT_RUN",
            "acceptance_oos": "NOT_RUN",
            "first_failed_or_unresolved_gate": "mechanics_approval",
            "research_verdict": "FAIL",
        }
        for index in range(1, 2)
    ]


def _write_stage_matrix(path: Path, matrix: list[dict[str, Any]]) -> None:
    pd.DataFrame(matrix).to_csv(path, index=False)


def _json_safe(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(key): _json_safe(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_safe(item) for item in value]
    if isinstance(value, float) and not math.isfinite(value):
        return None
    if isinstance(value, (pd.Timestamp, date)):
        return value.isoformat()
    if hasattr(value, "item"):
        return _json_safe(value.item())
    return value


def _finite_frame(frame: pd.DataFrame) -> pd.DataFrame:
    out = frame.copy()
    for column in out.select_dtypes(include="number").columns:
        finite = pd.to_numeric(out[column], errors="coerce").map(math.isfinite)
        if not bool(finite.all()):
            out[column] = out[column].astype(object)
            out.loc[~finite, column] = None
    return out


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(_json_safe(payload), indent=2, allow_nan=False), encoding="utf-8")


def _write_tutorial_report(path: Path, payload: dict[str, Any]) -> None:
    lines = [
        "# Synthetic Studio Tutorial Result",
        "",
        "> Teaching artifact only. It is synthetic, non-promotable, and never written to the research ledger.",
        "",
        f"- Operational execution: `{payload.get('operational_status', 'PASS')}`",
        f"- Research verdict: `{payload['research_verdict']}`",
        f"- Reason: {payload['verdict_reason']}",
        "",
        "## What the matrix teaches",
        "",
        payload.get("lesson", "Execute the tutorial to produce staged results."),
        "",
        "Open `stage_matrix.csv` and start with each variant's first failed or unresolved gate. Do not rank by PnL.",
        "",
        "FAIL",
        "",
    ]
    path.write_text("\n".join(lines), encoding="utf-8")


def _write_isolated_storage_layout(root: Path) -> Path:
    path = root / "config" / "storage_layout.yaml"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        yaml.safe_dump(
            {
                "schema": "alphaquest.storage-layout/v1",
                "active_campaign_root": "research/campaigns/active",
                "archive_campaign_roots": ["research/campaigns/archive"],
                "evidence_roots": ["research/evidence/runs"],
                "research_artifact_root": "research_artifacts",
                "catalog_root": "catalogs",
                "views_root": "views",
                "run_store_root": "run-store",
                "draft_root": "research/drafts",
                "dataset_root": "research/datasets",
                "handoff_root": "research/handoffs",
                "studio_runtime_root": "run-store/studio-runtime",
            },
            sort_keys=False,
        ),
        encoding="utf-8",
    )
    return path.resolve()


@contextmanager
def _forced_storage_layout(path: Path):
    """Prevent a caller's production layout override from escaping isolation."""

    name = "ALPHAQUEST_STORAGE_LAYOUT"
    previous = os.environ.get(name)
    os.environ[name] = str(path)
    try:
        yield
    finally:
        if previous is None:
            os.environ.pop(name, None)
        else:
            os.environ[name] = previous


def _reset_output(path: Path) -> None:
    if path.exists():
        marker = path / ".generated_by_alphaquest"
        if any(path.iterdir()) and not marker.is_file():
            raise RuntimeError(f"refusing to replace non-tutorial directory: {path}")
        shutil.rmtree(path)
    path.mkdir(parents=True)
