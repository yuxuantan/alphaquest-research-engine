from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path
import subprocess
import sys

import pandas as pd
import pytest
import yaml

import alphaquest.run_mvp_diagnostic as mvp
from alphaquest.research.campaign_stages import (
    PRE_ACCEPTANCE_STAGE_ORDER,
    STAGE_LABELS,
    _annotate_stage_decisions,
    _criteria_for_stage,
    _error_stage,
    _skipped_stage,
    canonicalize_campaign_config,
    evaluate_criteria,
)
from alphaquest.research.factory_policy import research_factory_binding, research_objectives_sha256
from alphaquest.prop.profiles import resolve_prop_profile
from alphaquest.dashboard.validation_app import save_manual_review_annotation
from alphaquest.studio.approvals import MechanicsApprovalService
from alphaquest.utils.hashing import file_sha256
from alphaquest.validation.promotion_gate import (
    REQUIRED_AUTOMATED_CATEGORIES,
    REQUIRED_AUTOMATED_CHECK_NAMES,
    SAMPLING_POLICY_SHA256,
    SAMPLING_POLICY_VERSION,
)
from alphaquest.version import ENGINE_CONTRACT_VERSION


def _write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2), encoding="utf-8")


def _write_yaml(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(yaml.safe_dump(value, sort_keys=False), encoding="utf-8")


def _project(tmp_path: Path, *, disabled_stage: str | None = None) -> tuple[Path, Path, dict[str, object]]:
    root = tmp_path / "project"
    _write_yaml(
        root / "config/storage_layout.yaml",
        {
            "schema": "alphaquest.storage-layout/v1",
            "active_campaign_root": "research/campaigns/active",
            "evidence_roots": ["research/evidence/runs"],
            "dataset_root": "research/datasets",
        },
    )
    dataset_id = "demo_es"
    canonical = root / f"research/datasets/{dataset_id}/bars.csv"
    canonical.parent.mkdir(parents=True)
    canonical.write_text(
        "timestamp,open,high,low,close,volume\n" "2026-01-05T14:30:00Z,100,101,99,100.5,10\n",
        encoding="utf-8",
    )
    canonical_hash = file_sha256(canonical)
    dataset_manifest = {
        "schema": "alphaquest.dataset-manifest/v1",
        "dataset_id": dataset_id,
        "source": "csv",
        "path": str(canonical.relative_to(root)),
        "symbol": "ES",
        "timeframe": "1m",
        "timezone": "America/New_York",
        "exchange_timezone": "America/New_York",
        "timestamp_semantics": "bar_open",
        "source_timestamp_semantics": "bar_open",
        "source_sha256": canonical_hash,
        "canonical_sha256": canonical_hash,
        "coverage_start": "2023-06-30T13:30:00+00:00",
        "coverage_end": "2026-01-16T15:30:00+00:00",
        "roll_policy": "single_contract",
        "continuous_contract": "none",
        "contract_column": None,
        "source_contract_column": None,
        "contract_count": 1,
        "roll_calendar": None,
        "roll_calendar_sha256": None,
        "transformations": ["test fixture canonicalization"],
        "row_count": 1,
        "dropped_row_count": 0,
        "gap_count": 0,
        "duplicate_count": 0,
        "out_of_order_count": 0,
        "invalid_ohlc_count": 0,
        "cadence_violation_count": 0,
        "certified_features": [],
        "quality_verdict": "PASS",
        "quality_notes": [],
        "event_source": None,
    }
    _write_json(canonical.parent / "dataset_manifest.json", dataset_manifest)

    campaign_root = root / "research/campaigns/active/recipe_demo"
    source_path = campaign_root / "variants/v01/config.yaml"
    evidence_dir = root / "research/evidence/mechanics/validation_runs/core"
    evidence_dir.mkdir(parents=True)
    approval_path = root / "research_artifacts/validation_approvals/recipe_demo/v01/approval.json"
    objectives = {
        "schema": "alphaquest.research-objectives/v1",
        "development_goal": "Exercise the isolated diagnostic path.",
        "development_deadline": "2099-12-31",
        "evaluation_horizon_months": 24,
        "minimum_annualized_return_fraction": 0.2,
        "minimum_mar": 0.4,
        "maximum_drawdown_fraction": 0.1,
        "minimum_complete_wfa_windows": 3,
        "minimum_wfa_oos_trades": 50,
        "minimum_acceptance_oos_trades": 30,
        "monte_carlo_min_runs": 8000,
        "monte_carlo_horizon_months": 6,
        "minimum_net_profit_probability": 0.7,
        "maximum_account_breach_probability": 0.1,
        "forward_incubation_min_calendar_days": 90,
        "forward_incubation_min_trades": 30,
        "maximum_variants": 1,
        "abandonment_rules": ["Stop after this demonstration."],
        "retirement_rules": ["Never promote this demonstration."],
        "confirmed": True,
    }
    research_factory = research_factory_binding(
        objectives,
        dataset={
            "dataset_id": dataset_id,
            "canonical_sha256": canonical_hash,
            "source_sha256": canonical_hash,
            "coverage_start": dataset_manifest["coverage_start"],
            "coverage_end": dataset_manifest["coverage_end"],
        },
    )
    objectives_sha256 = research_objectives_sha256(objectives)
    signature = "85bf616b7744fbef864ffddca3775d556941f5a10c91ca4f5c06202419bd7270"
    hypothesis = "A fixed weekday direction entered after the open may capture a calendar effect."
    expected_mechanism = "A predeclared calendar effect may persist during the first hour."
    mechanic_rationale = "Express the calendar effect with a fixed post-open entry."
    entry_rationale = "Enter only after the signal time is known."
    stop_rationale = "Use a fixed points stop declared before testing."
    target_rationale = "Use a fixed reward multiple declared before testing."
    timeframe_rationale = "One-minute bars resolve the declared session timing."
    known_failure_modes = ["The calendar effect may not survive costs."]
    source = {
        "campaign_id": "recipe_demo",
        "variant_id": "v01",
        "test_run_id": "run1",
        "attempt_id": "original",
        "attempt_kind": "original",
        "attempt_provenance": "authored",
        "parent_attempt_id": None,
        "strategy_name": "v01",
        "symbol": "ES",
        "dataset_id": dataset_id,
        "timeframe": "1m",
        "research_objectives": objectives,
        "research_objectives_sha256": objectives_sha256,
        "research_factory": research_factory,
        "research_metadata": {
            "mechanics_review_required": True,
            "mechanics_review_version": 1,
            "authoring_contract": "alphaquest.campaign-draft/v1",
            "mechanic_signature": signature,
            "timeframe_rationale": timeframe_rationale,
            "mechanics_review": {
                "mechanic_expresses_edge": mechanic_rationale,
                "entry_logic_rationale": entry_rationale,
                "stop_loss_rationale": stop_rationale,
                "target_exit_rationale": target_rationale,
                "profitability_rationale": f"{expected_mechanism} {mechanic_rationale}",
                "known_failure_modes": " ".join(known_failure_modes),
                "pre_test_decision": "approve_for_testing",
            },
            "validation_gate": {
                "required": True,
                "lane": "bar",
                "parameter_mode": "declared_defaults",
                "manual_review_random_sample_size": 5,
                "manual_review_seed": 7,
                "selection_mode": "latest_eligible_sessions",
                "session_count": 10,
                "minimum_trade_samples": 5,
                "evidence_dir": str(evidence_dir.relative_to(root)),
                "approval_path": str(approval_path.relative_to(root)),
            },
        },
        "data": {
            "dataset_id": dataset_id,
            "source": "csv",
            "raw_csv": str(canonical.relative_to(root)),
            "symbol": "ES",
            "source_timeframe": "1m",
            "timezone": "America/New_York",
            "source_timezone": "America/New_York",
            "exchange_timezone": "America/New_York",
            "timestamp_semantics": "bar_open",
            "source_timestamp_semantics": "bar_open",
            "source_sha256": canonical_hash,
            "canonical_sha256": canonical_hash,
            "coverage_start": dataset_manifest["coverage_start"],
            "coverage_end": dataset_manifest["coverage_end"],
            "roll_policy": "single_contract",
            "continuous_contract": "none",
            "contract_column": None,
            "contract_count": 1,
            "certified_features": [],
            "rth_start": "09:30:00",
            "rth_end": "10:30:00",
        },
        "strategy": {
            "entry": {
                "module": "calendar_session_bias",
                "params": {"signal_time": "09:35:00", "weekday_directions": {"0": "long"}},
            },
            "sl": {"module": "points_from_entry", "params": {"stop_points": 10.0}},
            "tp": {"module": "fixed_r", "params": {"target_r_multiple": 1.5}},
            "flatten_time": "10:25:00",
        },
        "core": {
            "initial_balance": 50000.0,
            "tick_size": 0.25,
            "point_value": 50.0,
            "tick_value": 12.5,
            "commission_per_contract": 2.5,
            "slippage_ticks": 1.0,
            "position_sizing": {"mode": "fixed_contracts", "contracts": 1},
            "flatten_time": "10:25:00",
            "max_trades_per_day": 1,
        },
        "apex_rules": {
            "enabled": True,
            "timezone": "America/New_York",
            "force_flatten_enabled": True,
            "force_flatten_time": "10:25:00",
            "latest_flat_time": "10:26:00",
            "latest_entry_time": "10:15:00",
            "cancel_pending_orders_before_flatten": True,
            "no_overnight_positions": True,
            "reject_if_position_after_flatten_deadline": True,
            "reject_if_pending_order_after_flatten_deadline": True,
            "reject_if_entry_after_latest_entry_time": True,
        },
        "account_profile_bindings": [],
        "prop_rules": resolve_prop_profile(
            "synthetic_tutorial_non_promotable",
            starting_balance=50000.0,
            max_contracts=1,
            force_flatten_time="10:25:00",
        ),
        "core_grid": {"parameters": {}},
        "wfa": {"parameters": {}},
    }
    if disabled_stage is not None:
        source["campaign_tests"] = {disabled_stage: {"enabled": False}}
    _write_yaml(source_path, source)
    source_hash = file_sha256(source_path)
    artifact_files = {
        "trades": "trades.parquet",
        "condition_snapshots": "condition_snapshots.parquet",
        "bar_windows": "bar_windows.parquet",
        "tick_windows": "tick_windows.parquet",
        "event_transitions": "event_transitions.parquet",
        "exit_audits": "exit_audits.parquet",
        "validation_checks": "validation_checks.parquet",
    }
    _write_json(
        evidence_dir / "metadata.json",
        {
            "run_id": "mechanics-validation-test",
            "campaign_id": "recipe_demo",
            "strategy_id": "v01",
            "variant_id": "v01",
            "symbol": "ES",
            "stage": "core",
            "timezone": "America/New_York",
            "tick_size": 0.25,
            "tick_value": 12.5,
            "timeframe": "1m",
            "timeframe_minutes": 1,
            "config_hash": source_hash,
            "input_data_hash": canonical_hash,
            "validation_lane": "bar",
            "source_trade_count": 5,
            "minimum_trade_samples": 5,
            "source_data_type": "csv",
            "source_data_path": str(canonical.relative_to(root)),
            "commission_per_contract": 2.5,
            "slippage_ticks": 1.0,
            "point_value": 50.0,
            "forced_flatten_time": "10:25:00",
            "notes": "Generated by the synthetic mechanics fixture.",
            "schema_version": "1.6",
            "created_at_utc": "2026-09-27T00:00:00+00:00",
            "artifact_files": artifact_files,
            "record_counts": {
                "trades": 5,
                "condition_snapshots": 0,
                "bar_windows": 5,
                "tick_windows": 0,
                "event_transitions": 0,
                "exit_audits": 0,
                "validation_checks": (
                    len(REQUIRED_AUTOMATED_CHECK_NAMES) + len(REQUIRED_AUTOMATED_CATEGORIES - {"reconciliation"})
                ),
            },
        },
    )
    trades = pd.DataFrame(
        [
            {
                "trade_id": trade_id,
                "entry_time": f"2026-01-{trade_id:02d}T14:30:00Z",
                "exit_time": f"2026-01-{trade_id:02d}T14:35:00Z",
                "direction": "long" if trade_id % 2 else "short",
                "entry_order_type": "market",
                "exit_reason": "target" if trade_id % 2 else "stop",
                "r_multiple": 1.0 if trade_id % 2 else -1.0,
                "pnl_ticks": 4 if trade_id % 2 else -4,
                "was_forced_flatten": False,
            }
            for trade_id in range(1, 6)
        ]
    )
    trades.to_parquet(evidence_dir / "trades.parquet", index=False)
    pd.DataFrame(
        [{"trade_id": trade_id, "timestamp": f"2026-01-{trade_id:02d}T14:30:00Z"} for trade_id in range(1, 6)]
    ).to_parquet(evidence_dir / "bar_windows.parquet", index=False)
    for filename in (
        "condition_snapshots.parquet",
        "tick_windows.parquet",
        "event_transitions.parquet",
        "exit_audits.parquet",
    ):
        pd.DataFrame().to_parquet(evidence_dir / filename, index=False)
    checks = [
        {
            "check_id": f"required.{name}",
            "check_name": name,
            "category": "reconciliation",
            "status": "PASS",
            "severity": "error",
        }
        for name in sorted(REQUIRED_AUTOMATED_CHECK_NAMES)
    ]
    checks.extend(
        {
            "check_id": f"category.{category}",
            "check_name": f"{category}_coverage",
            "category": category,
            "status": "PASS",
            "severity": "error",
        }
        for category in sorted(REQUIRED_AUTOMATED_CATEGORIES - {"reconciliation"})
    )
    pd.DataFrame(checks).to_parquet(evidence_dir / "validation_checks.parquet", index=False)
    service = MechanicsApprovalService()
    initial_plan = service.plan(source_path)
    for trade_id in initial_plan.sampled_trade_ids:
        save_manual_review_annotation(
            evidence_dir,
            trade_id,
            "Correct",
            "SIMULATED complete annotation for a synthetic fixture; no owner authority.",
            reviewed_at="2026-09-27T00:00:00+00:00",
        )
    approval = service.approve(
        source_path,
        reviewer="SIMULATED_MVP_FIXTURE_ONLY",
        notes="SIMULATED mechanics decision on a synthetic fixture. No owner authority.",
        reviewed_at="2026-09-27T00:00:00+00:00",
    )
    draft_sha256 = "2" * 64
    campaign = {
        "campaign_id": source["campaign_id"],
        "title": "Calendar bias diagnostic edge",
        "status": "authored_for_testing",
        "edge_family": "calendar_bias",
        "created_at": "2026-09-27",
        "instrument": "ES",
        "timeframe": "1m",
        "variant_protocol": "sequential_failure_informed",
        "governance_contract_version": 3,
        "max_variants": 1,
        "research_objectives": objectives,
        "research_objectives_sha256": objectives_sha256,
        "authoring_lane": "certified_recipe",
        "certified_recipe": "calendar_session_bias",
        "event_strategy": None,
        "event_strategies": {},
        "research_factory": research_factory,
        "hypothesis": hypothesis,
        "economic_edge_fingerprint": {
            "market_behavior": "Calendar direction",
            "causal_mechanism": "Session behavior",
            "signal_inputs": "weekday",
            "market_context": "regular session",
            "holding_period": "intraday",
        },
        "duplicate_edge_review": {
            "reviewed_campaign_ids": [],
            "ledger_queries": ["calendar bias"],
            "conclusion": "distinct",
            "substantive_distinction": "Separate diagnostic campaign.",
        },
        "sources": [
            {
                "title": "Diagnostic research source",
                "authors": "Research team",
                "year": 2026,
                "link": "https://example.invalid/research",
                "doi": None,
                "relevance": "Documents the predeclared calendar hypothesis.",
            }
        ],
        "variants": ["v01"],
        "sequential_variant_history": [],
        "variant_distinctions": {
            "v01": {
                "mechanic_signature": signature,
                "mechanic": mechanic_rationale,
                "material_difference": "One predeclared fixed-risk implementation.",
            }
        },
        "rescue_policy": {"allowed": False, "max_rescues_per_failed_variant": 1},
    }
    strategy_spec = {
        "schema": "alphaquest.strategy-spec/v1",
        "campaign_id": source["campaign_id"],
        "draft_sha256": draft_sha256,
        "research_objectives": objectives,
        "research_objectives_sha256": objectives_sha256,
        "frozen": True,
        "authoring_lane": "certified_recipe",
        "certified_recipe": "calendar_session_bias",
        "event_strategy": None,
        "strategy_certification": None,
        "variant_strategy_certifications": {},
        "research_factory": research_factory,
        "dataset": dataset_manifest,
        "hypothesis": hypothesis,
        "expected_mechanism": expected_mechanism,
        "holding_horizon": "Same-session first hour.",
        "known_failure_modes": known_failure_modes,
        "execution": {
            "session_start": "09:30:00",
            "session_end": "10:30:00",
            "latest_entry_time": "10:15:00",
            "flatten_time": "10:25:00",
            "latest_flat_time": "10:26:00",
            "overnight_allowed": False,
            "initial_balance": 50000.0,
            "tick_size": 0.25,
            "point_value": 50.0,
            "tick_value": 12.5,
            "commission_per_contract": 2.5,
            "slippage_ticks": 1.0,
            "contracts": 1,
            "prop_profile": "synthetic_tutorial_non_promotable",
            "target_account_profiles": [],
        },
        "variants": [
            {
                "variant_id": "v01",
                "title": "Calendar bias fixed-risk implementation",
                "mechanic_signature": signature,
                "entry": {**source["strategy"]["entry"], "parameter_grid": {}},
                "stop": {**source["strategy"]["sl"], "parameter_grid": {}},
                "target": {**source["strategy"]["tp"], "parameter_grid": {}},
                "event_parameter_grid": {},
                "rationales": {
                    "mechanic": mechanic_rationale,
                    "entry": entry_rationale,
                    "stop": stop_rationale,
                    "target": target_rationale,
                    "timeframe_session": timeframe_rationale,
                },
            }
        ],
    }
    _write_yaml(campaign_root / "campaign.yaml", campaign)
    _write_yaml(campaign_root / "strategy_spec.yaml", strategy_spec)
    compiled = {
        "campaign.yaml": mvp._compiled_object_sha256(campaign),
        "strategy_spec.yaml": mvp._compiled_object_sha256(strategy_spec),
        "variants/v01/config.yaml": mvp._compiled_object_sha256(source),
    }
    _write_json(
        campaign_root / "authoring_manifest.json",
        {
            "schema": "alphaquest.authoring-manifest/v1",
            "campaign_id": source["campaign_id"],
            "draft_schema": "alphaquest.campaign-draft/v1",
            "draft_sha256": draft_sha256,
            "research_objectives_sha256": objectives_sha256,
            "authoring_lane": "certified_recipe",
            "certified_recipe": "calendar_session_bias",
            "event_strategy": None,
            "strategy_certification": None,
            "variant_strategy_certifications": {},
            "compiler": "alphaquest.authoring.CampaignCompiler/v1",
            "created_at": "2026-09-27",
            "dataset_id": dataset_id,
            "dataset_canonical_sha256": canonical_hash,
            "research_factory": research_factory,
            "variant_count": 1,
            "variant_protocol": "sequential_failure_informed",
            "max_variants": 1,
            "planned_files": [
                "campaign.yaml",
                "strategy_spec.yaml",
                "authoring_manifest.json",
                "variants/v01/config.yaml",
            ],
            "variant_mechanic_signatures": {"v01": signature},
            "compiled_document_sha256": compiled,
            "generated_python_stubs": False,
        },
    )

    run = root / "research/evidence/runs/recipe_demo/v01/ES/run1"
    run.mkdir(parents=True)
    (run / "source_config.yaml").write_bytes(source_path.read_bytes())
    effective = canonicalize_campaign_config(source, include_acceptance=False)
    _write_yaml(run / "effective_config.yaml", effective)
    run_uid = "920c43cb-7c65-413e-9491-f8a0e375d8e5"
    (run / "run_uid.txt").write_text(run_uid, encoding="utf-8")
    gate = {
        "required": True,
        "status": "APPROVED_FOR_TESTING",
        "verdict": "PASS",
        "errors": [],
        "warnings": [],
        "config_path": str(source_path),
        "lane": "bar",
        "evidence_dir": str(evidence_dir),
        "approval_path": str(approval_path),
        "config_hash": source_hash,
        "input_data_hash": canonical_hash,
        "strategy_implementation_version": None,
        "strategy_implementation_sha256": None,
        "strategy_certification_manifest_sha256": None,
        "validation_schema_version": "1.6",
        "approval_status": "approved_for_testing",
        "reviewer": "SIMULATED_MVP_FIXTURE_ONLY",
        "reviewed_at": "2026-09-27T00:00:00+00:00",
    }
    stages: list[dict[str, object]] = []
    for index, stage in enumerate(PRE_ACCEPTANCE_STAGE_ORDER):
        stage_dir = run / stage
        if stage == disabled_stage:
            result = _annotate_stage_decisions(_skipped_stage(stage, "disabled"))
        elif index == 0:
            execution_assumptions = mvp.ExecutionAssumptions.from_core_config(effective["core"]).as_dict()
            fixed_core = {
                "purpose": "fixed_config_mechanics_cross_check",
                "parameter_source": "strategy section in effective config",
                "uses_grid_selected_params": False,
                "reproducibility": {"execution_assumptions": execution_assumptions},
                "strategy": deepcopy(effective["strategy"]),
                "core": deepcopy(effective["core"]),
            }
            stage_summary = {
                "parameter_mode": "fixed_config",
                "parameter_value_counts": {},
                "expected_combinations": 1,
                "total_combinations_tested": 1,
                "percentage_profitable_iterations": 0.0,
                "fixed_config_core": fixed_core,
            }
            output = stage_dir / mvp._CANONICAL_STAGE_SUMMARIES[stage]
            _write_json(output, stage_summary)
            _write_json(stage_dir / "fixed_config_core_metrics.json", fixed_core)
            retained_quality = {
                "rows": 1,
                "duplicate_count": 0,
                "invalid_ohlc_count": 0,
                "missing_session_segments": 0,
                "first_timestamp": "2026-01-05 09:30:00-05:00",
                "last_timestamp": "2026-01-05 09:30:00-05:00",
                "roll_boundary_sessions_skipped": 0,
                "loaded_rows": 1,
                "strategy_rows": 1,
                "timeframe": "1m",
                "timeframe_minutes": 1,
                "source_timeframe": "1m",
            }
            quality_path = stage_dir / "validation/data_quality_report.csv"
            quality_path.parent.mkdir(parents=True)
            pd.DataFrame([retained_quality]).to_csv(quality_path, index=False)
            data_quality = {
                **retained_quality,
                "prepare_data_duration_seconds": 0.01,
                "prepared_data_cache": {"enabled": True, "hit": False, "key": "test"},
            }
            artifacts = [str(path.relative_to(root)) for path in sorted(stage_dir.rglob("*")) if path.is_file()]
            result: dict[str, object] = {
                "stage": stage,
                "label": STAGE_LABELS[stage],
                "status": "failed",
                "passed": False,
                "started_at": "2026-09-27T00:00:00",
                "completed_at": "2026-09-27T00:00:01",
                "duration_seconds": 1.0,
                "summary": stage_summary,
                "data_quality": data_quality,
                "input_hash": canonical_hash,
                "core_grid_parameters": {},
                "artifacts": artifacts,
            }
            result["criteria"] = evaluate_criteria(
                result,
                _criteria_for_stage(stage, ((effective.get("campaign_tests") or {}).get(stage) or {})),
            )
            result = _annotate_stage_decisions(result)
        else:
            result = _annotate_stage_decisions(
                _error_stage(stage, RuntimeError("upstream fixture evidence unavailable"))
            )
        stages.append(result)
        if result["status"] != "skipped":
            _write_json(stage_dir / "stage_result.json", result)
    preflight: dict[str, object] = {
        "passed": True,
        "configs_checked": [str(source_path.relative_to(root))],
        "failures": [],
        "warnings": [],
        "tests_ran": False,
        "include_generated_results": False,
        "data_sources_checked": 1,
        "data_cache_hits": 0,
        "terminal_configs_not_executed": 0,
    }
    receipt = root / "pre-run-preflight.json"
    _write_json(receipt, preflight)
    identity = {
        "run_uid": run_uid,
        "campaign_id": source["campaign_id"],
        "variant_id": "v01",
        "test_run_id": "run1",
        "attempt_id": "original",
        "attempt_kind": "original",
        "attempt_provenance": "authored",
        "parent_attempt_id": None,
        "symbol": "ES",
        "dataset_id": dataset_id,
        "timeframe": "1m",
    }
    mechanic = {
        "entry_module": "calendar_session_bias",
        "take_profit_module": "fixed_r",
        "stop_loss_module": "points_from_entry",
        "flatten_time": "10:25:00",
    }
    variant_path = run / "variant.yaml"
    _write_yaml(
        variant_path,
        {
            "campaign_id": source["campaign_id"],
            "variant_id": "v01",
            "strategy_name": "v01",
            "mechanic": mechanic,
            "rescue_policy": {},
        },
    )
    variant_metadata = {
        "path": str(variant_path.relative_to(root)),
        "hash": file_sha256(variant_path),
        "mechanic": mechanic,
        "rescue_policy": {},
    }
    results_index = campaign_root / "results_index.yaml"
    summary = {
        **identity,
        "data_source": "csv",
        "raw_csv": str(canonical.relative_to(root)),
        "raw_parquet": None,
        "raw_dir": None,
        "campaign_metadata": None,
        "variant_metadata": variant_metadata,
        "config_hash": file_sha256(run / "effective_config.yaml"),
        "source_config_hash": source_hash,
        "config_path": str((run / "effective_config.yaml").relative_to(root)),
        "effective_config_path": str((run / "effective_config.yaml").relative_to(root)),
        "source_config_path": str(source_path),
        "source_config_snapshot_path": str((run / "source_config.yaml").relative_to(root)),
        "output_dir": str(run.relative_to(root)),
        "created_at": "2026-09-27T00:00:00",
        "updated_at": "2026-09-27T00:00:00",
        "passed": False,
        "halted": False,
        "stages": stages,
        "research_policy": effective["research_policy"],
        "engine_contract_version": ENGINE_CONTRACT_VERSION,
        "diagnostic_only": True,
        "diagnostic_reasons": ["mandatory acceptance_oos_test was omitted"],
        "skip_validation": False,
        "fast_runtime_defaults": False,
        "authoritative_parallel_workers": None,
        "authoritative_core_grid_workers": None,
        "research_verdict": "NEEDS MANUAL REVIEW",
        "generic_objective_verdict": "NEEDS MANUAL REVIEW",
        "scientific_validity_verdict": "NEEDS MANUAL REVIEW",
        "submission_preflight": preflight,
        "mechanics_validation_gate": gate,
        "source_results_index_path": str(results_index.relative_to(root)),
    }
    results_entry = {
        "campaign_id": summary["campaign_id"],
        "variant_id": summary["variant_id"],
        "symbol": summary["symbol"],
        "test_run_id": summary["test_run_id"],
        "attempt_id": summary["attempt_id"],
        "attempt_kind": summary["attempt_kind"],
        "attempt_provenance": summary["attempt_provenance"],
        "parent_attempt_id": summary["parent_attempt_id"],
        "source_config_path": str(source_path),
        "source_config_snapshot_path": summary["source_config_snapshot_path"],
        "source_config_hash": summary["source_config_hash"],
        "effective_config_path": summary["effective_config_path"],
        "effective_config_hash": summary["config_hash"],
        "run_dir": summary["output_dir"],
        "campaign_test_summary": str(Path(str(summary["output_dir"])) / "campaign_test_summary.json"),
        "variant_test_summary": str(Path(str(summary["output_dir"])) / "variant_test_summary.json"),
        "passed": summary["passed"],
        "research_verdict": summary["research_verdict"],
        "finalization_state": None,
        "result_bundle_path": None,
        "incomplete_attempt_marker_path": None,
        "diagnostic_only": summary["diagnostic_only"],
        "halted": summary["halted"],
        "failed_stage": PRE_ACCEPTANCE_STAGE_ORDER[0],
        "updated_at": summary["updated_at"],
    }
    _write_yaml(
        results_index,
        {
            "campaign_id": source["campaign_id"],
            "generated_by": "alphaquest.run_campaign_stages",
            "description": "Navigation pointers from authored source configs to generated backtest evidence.",
            "runs": [results_entry],
        },
    )
    manifest = {
        **identity,
        "data_source": summary["data_source"],
        "raw_csv": summary["raw_csv"],
        "raw_parquet": summary["raw_parquet"],
        "raw_dir": summary["raw_dir"],
        "campaign_metadata": summary["campaign_metadata"],
        "variant_metadata": summary["variant_metadata"],
        "research_policy": summary["research_policy"],
        "engine_contract_version": summary["engine_contract_version"],
        "config_source": str(source_path),
        "effective_config": str((run / "effective_config.yaml").relative_to(root)),
        "source_config_snapshot": str((run / "source_config.yaml").relative_to(root)),
        "config_hash": summary["config_hash"],
        "source_config_hash": source_hash,
        "source_results_index": str(results_index.relative_to(root)),
        "created_at": summary["created_at"],
        "updated_at": summary["updated_at"],
        "stage_order": PRE_ACCEPTANCE_STAGE_ORDER,
        "mechanics_validation_gate": gate,
        "submission_preflight": preflight,
        "diagnostic_only": True,
        "diagnostic_reasons": ["mandatory acceptance_oos_test was omitted"],
        "authoritative_parallel_workers": None,
        "authoritative_core_grid_workers": None,
        "research_verdict": "NEEDS MANUAL REVIEW",
        "generic_objective_verdict": "NEEDS MANUAL REVIEW",
        "scientific_validity_verdict": "NEEDS MANUAL REVIEW",
        "layout": "campaign_variant_symbol_run",
    }
    _write_json(run / "campaign_test_summary.json", summary)
    _write_json(run / "variant_test_summary.json", summary)
    _write_json(run / "run_manifest.json", manifest)
    return root, run, preflight


def _build(
    root: Path,
    run: Path,
    preflight: dict[str, object],
    monkeypatch: pytest.MonkeyPatch,
    *,
    mode: str = "synthetic",
) -> dict[str, object]:
    monkeypatch.setattr(mvp, "run_preflight", lambda **_kwargs: preflight)
    return mvp.build_diagnostic_index(
        project_root=root,
        run_dir=run,
        preflight_receipt=root / "pre-run-preflight.json",
        mode=mode,
    )


def _update_summary_and_manifest(run: Path, update) -> None:
    summary_path = run / "campaign_test_summary.json"
    summary = json.loads(summary_path.read_text(encoding="utf-8"))
    update(summary)
    _write_json(summary_path, summary)
    _write_json(run / "variant_test_summary.json", summary)
    manifest_path = run / "run_manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    update(manifest)
    _write_json(manifest_path, manifest)


def _replace_stage_in_run(run: Path, index: int, stage: dict[str, object]) -> None:
    _write_json(run / str(stage["stage"]) / "stage_result.json", stage)

    def update(document):
        if "stages" in document:
            document["stages"][index] = stage

    _update_summary_and_manifest(run, update)


def test_builds_bound_synthetic_report(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    root, run, preflight = _project(tmp_path)
    report = _build(root, run, preflight, monkeypatch)

    assert report["overall_verdict"] == "NEEDS MANUAL REVIEW"
    assert report["passed"] is False
    assert set(report["assurance"].values()) == {False}
    assert report["assurance"]["data_origin_verified"] is False
    assert report["assurance"]["source_review_verified"] is False
    assert report["authoring"]["certified_recipe"] == "calendar_session_bias"
    published_config = next(
        document
        for document in report["authoring"]["documents"]
        if document["path"].endswith("variants/v01/config.yaml")
    )
    assert published_config["file_sha256"] == file_sha256(
        root / "research/campaigns/active/recipe_demo/variants/v01/config.yaml"
    )
    assert published_config["compiled_object_sha256"]
    assert "sha256" not in published_config
    assert report["execution_contract"]["mechanic"]["entry_module"] == "calendar_session_bias"
    assert report["preflight"]["repository_engineering_tests_verified"] is False
    assert report["stages"][0]["referenced_artifacts"][0]["sha256"]
    assert report["dataset"]["manifest_historical_run_hash_recorded"] is False
    assert report["producer_bindings"]["source_results_index"]["sha256"]
    assert report["mechanics"]["planner_contract_validated"] is True
    assert report["mechanics"]["technical_gate_inspector_validated"] is True
    assert report["mechanics"]["retained_evidence_contract"]["observed_record_counts"]["trades"] == 5
    assert report["mechanics"]["evidence_inventory_only"] is False
    assert report["execution_contract"]["engine_execution_assumptions"]["market_exit_slippage_ticks"] == 1.0
    assert report["stages"][0]["omitted_unverified_fields"] == [
        "data_quality.prepare_data_duration_seconds",
        "data_quality.prepared_data_cache",
    ]
    assert "prepared_data_cache" not in report["stages"][0]["summary"]["data_quality"]
    assert report["stages"][0]["validated_execution_config_snapshots"]["grid"] == {
        "parameter_mode": "fixed_config",
        "parameter_value_counts": {},
        "expected_combinations": 1,
    }


@pytest.mark.parametrize(
    ("mutation", "message"),
    [
        ("extra", "completed payload fields"),
        ("input", "input hash"),
        ("grid", "limited core grid parameters"),
        ("quality", "retained data quality rows"),
    ],
)
def test_rejects_coordinated_forged_completed_stage_payload(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    mutation: str,
    message: str,
) -> None:
    root, run, preflight = _project(tmp_path)
    stage_path = run / PRE_ACCEPTANCE_STAGE_ORDER[0] / "stage_result.json"
    stage = json.loads(stage_path.read_text(encoding="utf-8"))
    if mutation == "extra":
        stage["producer_impossible"] = True
    elif mutation == "input":
        stage["input_hash"] = "0" * 64
    elif mutation == "grid":
        stage["core_grid_parameters"] = {"entry.params.forged": [1, 2]}
    else:
        stage["data_quality"]["rows"] = 99
    _replace_stage_in_run(run, 0, stage)

    with pytest.raises(ValueError, match=message):
        _build(root, run, preflight, monkeypatch)


def test_rejects_coordinated_execution_assumption_forgery(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    root, run, preflight = _project(tmp_path)
    stage_name = PRE_ACCEPTANCE_STAGE_ORDER[0]
    canonical_path = run / stage_name / mvp._CANONICAL_STAGE_SUMMARIES[stage_name]
    canonical = json.loads(canonical_path.read_text(encoding="utf-8"))
    forged = deepcopy(canonical["fixed_config_core"]["reproducibility"]["execution_assumptions"])
    forged["commission_per_contract"] = 0.0
    forged["commission_source"] = "forged"
    canonical["fixed_config_core"]["reproducibility"]["execution_assumptions"] = forged
    _write_json(canonical_path, canonical)
    stage_path = run / stage_name / "stage_result.json"
    stage = json.loads(stage_path.read_text(encoding="utf-8"))
    stage["summary"] = canonical
    _replace_stage_in_run(run, 0, stage)

    with pytest.raises(ValueError, match="canonical_summary.*execution_assumptions"):
        _build(root, run, preflight, monkeypatch)


@pytest.mark.parametrize(
    ("mutation", "message"),
    [
        ("mode", "canonical parameter mode"),
        ("counts", "canonical parameter value counts"),
        ("combinations", "canonical expected combinations"),
        ("tested", "canonical tested combinations"),
    ],
)
def test_rejects_coordinated_canonical_grid_forgery(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    mutation: str,
    message: str,
) -> None:
    root, run, preflight = _project(tmp_path)
    stage_name = PRE_ACCEPTANCE_STAGE_ORDER[0]
    canonical_path = run / stage_name / mvp._CANONICAL_STAGE_SUMMARIES[stage_name]
    canonical = json.loads(canonical_path.read_text(encoding="utf-8"))
    if mutation == "mode":
        canonical["parameter_mode"] = "predeclared_optimization"
    elif mutation == "counts":
        canonical["parameter_value_counts"] = {"entry.params.forged": 2}
    elif mutation == "combinations":
        canonical["expected_combinations"] = 2
    else:
        canonical["total_combinations_tested"] = 2
    _write_json(canonical_path, canonical)
    stage = json.loads((run / stage_name / "stage_result.json").read_text(encoding="utf-8"))
    stage["summary"] = canonical
    if mutation == "tested":
        stage["criteria"] = evaluate_criteria(stage, _criteria_for_stage(stage_name, {}))
        stage = mvp._annotate_stage_decisions(stage)
    _replace_stage_in_run(run, 0, stage)

    with pytest.raises(ValueError, match=message):
        _build(root, run, preflight, monkeypatch)


@pytest.mark.parametrize(
    ("section", "message"),
    [
        ("core", "fixed core snapshot"),
        ("strategy", "fixed strategy snapshot"),
    ],
)
def test_rejects_coordinated_fixed_execution_snapshot_forgery(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    section: str,
    message: str,
) -> None:
    root, run, preflight = _project(tmp_path)
    stage_name = PRE_ACCEPTANCE_STAGE_ORDER[0]
    canonical_path = run / stage_name / mvp._CANONICAL_STAGE_SUMMARIES[stage_name]
    canonical = json.loads(canonical_path.read_text(encoding="utf-8"))
    fixed = canonical["fixed_config_core"]
    if section == "core":
        fixed["core"]["commission_per_contract"] = 0.0
    else:
        fixed["strategy"]["entry"]["params"]["signal_time"] = "23:59:00"
    _write_json(canonical_path, canonical)
    _write_json(run / stage_name / "fixed_config_core_metrics.json", fixed)
    stage = json.loads((run / stage_name / "stage_result.json").read_text(encoding="utf-8"))
    stage["summary"] = canonical
    _replace_stage_in_run(run, 0, stage)

    with pytest.raises(ValueError, match=message):
        _build(root, run, preflight, monkeypatch)


def test_rejects_incomplete_subordinate_fixed_metrics_projection(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root, run, preflight = _project(tmp_path)
    stage_name = PRE_ACCEPTANCE_STAGE_ORDER[0]
    metrics_path = run / stage_name / "fixed_config_core_metrics.json"
    metrics = json.loads(metrics_path.read_text(encoding="utf-8"))
    metrics["diagnostics"] = {"forged": True}
    _write_json(metrics_path, metrics)

    with pytest.raises(ValueError, match="complete fixed metrics projection"):
        _build(root, run, preflight, monkeypatch)


def test_validates_wfa_selections_against_frozen_grid(tmp_path: Path) -> None:
    stage_dir = tmp_path / "walk_forward_analysis"
    stage_dir.mkdir()
    results = stage_dir / "wfa_results.csv"
    trades = stage_dir / "wfa_oos_trade_log.csv"
    results.write_text("selected_params\n\"{'entry.params.lookback': 10}\"\n", encoding="utf-8")
    trades.write_text("wfa_selected_params\n\"{'entry.params.lookback': 10}\"\n", encoding="utf-8")
    canonical = {
        "parameter_mode": "predeclared_optimization",
        "incubation_selected_params": {"entry.params.lookback": 10},
    }
    effective = {"wfa": {"parameters": {"entry.params.lookback": [10, 20]}}}

    validated = mvp._validate_stage_execution_config(
        stage="walk_forward_analysis",
        stage_cfg={},
        canonical_summary=canonical,
        artifact_paths=[results, trades],
        effective_config=effective,
    )

    assert validated["window_selected_params"] == [{"entry.params.lookback": 10}]
    canonical["incubation_selected_params"] = {"entry.params.lookback": 99}
    with pytest.raises(ValueError, match="outside the frozen grid"):
        mvp._validate_stage_execution_config(
            stage="walk_forward_analysis",
            stage_cfg={},
            canonical_summary=canonical,
            artifact_paths=[results, trades],
            effective_config=effective,
        )


def test_binds_explicit_per_exit_execution_assumptions(tmp_path: Path) -> None:
    core = {
        "tick_size": 0.25,
        "tick_value": 12.5,
        "point_value": 50.0,
        "commission_per_contract": 2.5,
        "slippage_ticks": 1.0,
        "entry_slippage_ticks": 2.0,
        "protective_stop_slippage_ticks": 3.0,
        "target_limit_slippage_ticks": 0.0,
        "market_exit_slippage_ticks": 4.0,
    }
    expected = mvp.ExecutionAssumptions.from_core_config(core).as_dict()
    canonical = {"fixed_config_core": {"reproducibility": {"execution_assumptions": expected}}}
    metrics_path = tmp_path / "fixed_config_core_metrics.json"
    _write_json(metrics_path, {"reproducibility": {"execution_assumptions": expected}})

    mvp._validate_execution_assumptions("limited_core_grid_test", canonical, [metrics_path], expected)

    assert expected["entry_slippage_ticks"] == 2.0
    assert expected["protective_stop_slippage_ticks"] == 3.0
    assert expected["target_limit_slippage_ticks"] == 0.0
    assert expected["market_exit_slippage_ticks"] == 4.0


def test_unverified_mode_never_claims_real_origin(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    root, run, preflight = _project(tmp_path)
    with pytest.raises(ValueError, match="explicit simulated fixture classification"):
        _build(root, run, preflight, monkeypatch, mode="unverified")

    approval_path = root / "research_artifacts/validation_approvals/recipe_demo/v01/approval.json"
    approval = json.loads(approval_path.read_text(encoding="utf-8"))
    approval["reviewer"] = "UNVERIFIED_USER_SUPPLIED"
    _write_json(approval_path, approval)
    _update_summary_and_manifest(
        run,
        lambda document: document.get("mechanics_validation_gate", {}).__setitem__(
            "reviewer", "UNVERIFIED_USER_SUPPLIED"
        ),
    )
    retained = _build(root, run, preflight, monkeypatch, mode="synthetic")
    assert retained["input_classification"]["classification"] == "SYNTHETIC_OR_SIMULATED_CONTEXT"
    assert "Mechanics approval is simulated and has no owner authority." in retained["labels"]
    with pytest.raises(ValueError, match="explicit simulated fixture classification"):
        _build(root, run, preflight, monkeypatch, mode="unverified")

    approval["notes"] = "Recorded approval of unknown provenance."
    _write_json(approval_path, approval)
    report = _build(root, run, preflight, monkeypatch, mode="unverified")

    assert report["assurance"]["data_origin_verified"] is False
    assert report["input_classification"]["classification"] == "UNVERIFIED_ORIGIN"
    assert all("real-data diagnostic evidence" not in label.lower() for label in report["labels"])
    with pytest.raises(ValueError, match="synthetic mode requires"):
        _build(root, run, preflight, monkeypatch, mode="synthetic")
    with pytest.raises(ValueError, match="positive real-origin classification is unsupported"):
        _build(root, run, preflight, monkeypatch, mode="real")


def test_synthetic_source_does_not_imply_simulated_mechanics(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    root, run, preflight = _project(tmp_path)
    campaign_root = root / "research/campaigns/active/recipe_demo"
    campaign_path = campaign_root / "campaign.yaml"
    campaign = yaml.safe_load(campaign_path.read_text(encoding="utf-8"))
    campaign["title"] = "Synthetic teaching context"
    _write_yaml(campaign_path, campaign)
    manifest_path = campaign_root / "authoring_manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["compiled_document_sha256"]["campaign.yaml"] = mvp._compiled_object_sha256(campaign)
    _write_json(manifest_path, manifest)
    approval_path = root / "research_artifacts/validation_approvals/recipe_demo/v01/approval.json"
    approval = json.loads(approval_path.read_text(encoding="utf-8"))
    approval["reviewer"] = "UNVERIFIED_USER_SUPPLIED"
    approval["notes"] = "Recorded approval of unknown provenance."
    _write_json(approval_path, approval)
    _update_summary_and_manifest(
        run,
        lambda document: document.get("mechanics_validation_gate", {}).__setitem__(
            "reviewer", "UNVERIFIED_USER_SUPPLIED"
        ),
    )

    report = _build(root, run, preflight, monkeypatch, mode="synthetic")
    classification = report["input_classification"]
    assert classification["source_synthetic_disclosed"] is True
    assert classification["mechanics_simulated_disclosed"] is False
    assert "Synthetic fixture source; not independently verified." in report["labels"]
    assert "Mechanics approval is simulated and has no owner authority." not in report["labels"]


@pytest.mark.parametrize("field", ["run_uid", "test_run_id", "attempt_id", "attempt_kind", "attempt_provenance"])
def test_rejects_empty_required_identity(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, field: str) -> None:
    root, run, preflight = _project(tmp_path)
    _update_summary_and_manifest(run, lambda document: document.__setitem__(field, ""))
    with pytest.raises(ValueError, match=field):
        _build(root, run, preflight, monkeypatch)


def test_rejects_effective_strategy_drift_even_when_hashes_are_relabelled(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root, run, preflight = _project(tmp_path)
    effective_path = run / "effective_config.yaml"
    effective = yaml.safe_load(effective_path.read_text(encoding="utf-8"))
    effective["strategy"]["entry"]["module"] = "opening_range_breakout"
    _write_yaml(effective_path, effective)
    changed_hash = file_sha256(effective_path)
    _update_summary_and_manifest(run, lambda document: document.__setitem__("config_hash", changed_hash))

    with pytest.raises(ValueError, match="effective config canonicalization"):
        _build(root, run, preflight, monkeypatch)


def test_rejects_invented_stage_status(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    root, run, preflight = _project(tmp_path)
    first = PRE_ACCEPTANCE_STAGE_ORDER[0]
    stage_path = run / first / "stage_result.json"
    stage = json.loads(stage_path.read_text(encoding="utf-8"))
    stage["status"] = "invented"
    _write_json(stage_path, stage)

    def update(document):
        if "stages" in document:
            document["stages"][0] = stage

    _update_summary_and_manifest(run, update)
    with pytest.raises(ValueError, match="status must be one of"):
        _build(root, run, preflight, monkeypatch)


def test_rejects_stage_status_passed_disagreement(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    root, run, preflight = _project(tmp_path)
    first = PRE_ACCEPTANCE_STAGE_ORDER[0]
    stage_path = run / first / "stage_result.json"
    stage = json.loads(stage_path.read_text(encoding="utf-8"))
    stage["passed"] = True
    _write_json(stage_path, stage)

    def update(document):
        if "stages" in document:
            document["stages"][0] = stage

    _update_summary_and_manifest(run, update)
    with pytest.raises(ValueError, match="status and passed flag are inconsistent"):
        _build(root, run, preflight, monkeypatch)


def test_rejects_integer_for_boolean_control(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    root, run, preflight = _project(tmp_path)
    _update_summary_and_manifest(
        run,
        lambda document: document.__setitem__("skip_validation", 0) if "stages" in document else None,
    )
    with pytest.raises(ValueError, match="skip_validation must be boolean"):
        _build(root, run, preflight, monkeypatch)


def test_rejects_missing_referenced_stage_artifact(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    root, run, preflight = _project(tmp_path)
    first = PRE_ACCEPTANCE_STAGE_ORDER[0]
    (run / first / mvp._CANONICAL_STAGE_SUMMARIES[first]).unlink()
    with pytest.raises(ValueError, match="required artifact is not a file"):
        _build(root, run, preflight, monkeypatch)


def test_rejects_approval_identity_drift(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    root, run, preflight = _project(tmp_path)
    approval_path = root / "research_artifacts/validation_approvals/recipe_demo/v01/approval.json"
    approval = json.loads(approval_path.read_text(encoding="utf-8"))
    approval["reviewer"] = "different-reviewer"
    _write_json(approval_path, approval)
    with pytest.raises(ValueError, match="recorded/current mechanics reviewer"):
        _build(root, run, preflight, monkeypatch)


def test_rejects_dataset_without_pass_quality(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    root, run, preflight = _project(tmp_path)
    manifest_path = root / "research/datasets/demo_es/dataset_manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["quality_verdict"] = "NEEDS MANUAL REVIEW"
    _write_json(manifest_path, manifest)
    with pytest.raises(ValueError, match="dataset quality verdict"):
        _build(root, run, preflight, monkeypatch)


def test_rejects_published_source_hash_drift(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    root, run, preflight = _project(tmp_path)
    manifest_path = root / "research/campaigns/active/recipe_demo/authoring_manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["compiled_document_sha256"]["variants/v01/config.yaml"] = "0" * 64
    _write_json(manifest_path, manifest)
    with pytest.raises(ValueError, match="published source config hash"):
        _build(root, run, preflight, monkeypatch)


def test_formatting_preserves_compiled_object_hash_but_breaks_raw_run_binding(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root, run, preflight = _project(tmp_path)
    source_path = root / "research/campaigns/active/recipe_demo/variants/v01/config.yaml"
    manifest_path = source_path.parents[2] / "authoring_manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    source = yaml.safe_load(source_path.read_text(encoding="utf-8"))
    prior_file_hash = file_sha256(source_path)

    source_path.write_text(yaml.safe_dump(source, sort_keys=True), encoding="utf-8")

    assert file_sha256(source_path) != prior_file_hash
    assert mvp._compiled_object_sha256(source) == manifest["compiled_document_sha256"]["variants/v01/config.yaml"]
    with pytest.raises(ValueError, match="authored source config hash"):
        _build(root, run, preflight, monkeypatch)


def test_rejects_preflight_receipt_that_claims_tests_ran(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    root, run, preflight = _project(tmp_path)
    preflight["tests_ran"] = True
    _write_json(root / "pre-run-preflight.json", preflight)
    _update_summary_and_manifest(
        run,
        lambda document: document.__setitem__("submission_preflight", preflight),
    )
    with pytest.raises(ValueError, match="pre-run preflight tests_ran"):
        _build(root, run, preflight, monkeypatch)


def test_rejects_output_dir_and_run_uid_drift(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    root, run, preflight = _project(tmp_path)

    def change_output(document):
        if "stages" in document:
            document["output_dir"] = "research/evidence/runs/other"

    _update_summary_and_manifest(run, change_output)
    with pytest.raises(ValueError, match="summary output_dir"):
        _build(root, run, preflight, monkeypatch)

    root, run, preflight = _project(tmp_path / "second")
    (run / "run_uid.txt").write_text("different", encoding="utf-8")
    with pytest.raises(ValueError, match="run UID marker"):
        _build(root, run, preflight, monkeypatch)


@pytest.mark.parametrize(
    ("field", "value", "message"),
    [
        ("halted", True, "run halted flag"),
        ("engine_contract_version", "contradictory", "summary engine contract"),
    ],
)
def test_rejects_producer_impossible_run_fields(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    field: str,
    value: object,
    message: str,
) -> None:
    root, run, preflight = _project(tmp_path)
    _update_summary_and_manifest(run, lambda document: document.__setitem__(field, value))
    with pytest.raises(ValueError, match=message):
        _build(root, run, preflight, monkeypatch)


def test_rejects_manifest_data_contract_drift(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    root, run, preflight = _project(tmp_path)
    manifest_path = run / "run_manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["data_source"] = "parquet"
    manifest["raw_csv"] = None
    manifest["raw_parquet"] = "different.parquet"
    _write_json(manifest_path, manifest)
    with pytest.raises(ValueError, match="manifest data_source"):
        _build(root, run, preflight, monkeypatch)


@pytest.mark.parametrize(
    ("mutation", "message"),
    [
        ("criteria_pass", "criteria aggregate"),
        ("verdict", "generic_objective_verdict"),
        ("metric", "authoritative criteria"),
    ],
)
def test_rejects_producer_impossible_stage_semantics(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, mutation: str, message: str
) -> None:
    root, run, preflight = _project(tmp_path)
    stage_name = PRE_ACCEPTANCE_STAGE_ORDER[0]
    result_path = run / stage_name / "stage_result.json"
    result = json.loads(result_path.read_text(encoding="utf-8"))
    if mutation == "criteria_pass":
        result["status"] = "passed"
        result["passed"] = True
    elif mutation == "verdict":
        result["generic_objective_verdict"] = "FAIL"
        result["generic_objective_passed"] = False
    else:
        result["criteria"][0]["metric"] = "invented.metric"
    _write_json(result_path, result)

    def update(document):
        if "stages" in document:
            document["stages"][0] = result

    _update_summary_and_manifest(run, update)
    if mutation == "criteria_pass":
        results_path = root / "research/campaigns/active/recipe_demo/results_index.yaml"
        results = yaml.safe_load(results_path.read_text(encoding="utf-8"))
        results["runs"][0]["failed_stage"] = PRE_ACCEPTANCE_STAGE_ORDER[1]
        _write_yaml(results_path, results)
    with pytest.raises(ValueError, match=message):
        _build(root, run, preflight, monkeypatch)


def test_rejects_coordinated_stage_relabel_when_canonical_summary_still_fails(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root, run, preflight = _project(tmp_path)
    stage_name = PRE_ACCEPTANCE_STAGE_ORDER[0]
    result_path = run / stage_name / "stage_result.json"
    result = json.loads(result_path.read_text(encoding="utf-8"))
    result["summary"]["percentage_profitable_iterations"] = 1.0
    result["criteria"] = evaluate_criteria(result, _criteria_for_stage(stage_name, {}))
    result["status"] = "passed"
    result["passed"] = True
    result = _annotate_stage_decisions(result)
    _write_json(result_path, result)
    _update_summary_and_manifest(
        run,
        lambda document: document["stages"].__setitem__(0, result) if "stages" in document else None,
    )
    results_path = root / "research/campaigns/active/recipe_demo/results_index.yaml"
    results = yaml.safe_load(results_path.read_text(encoding="utf-8"))
    results["runs"][0]["failed_stage"] = PRE_ACCEPTANCE_STAGE_ORDER[1]
    _write_yaml(results_path, results)

    with pytest.raises(ValueError, match="canonical summary projection"):
        _build(root, run, preflight, monkeypatch)


def test_accepts_exact_disabled_stage_without_stage_result(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    disabled = PRE_ACCEPTANCE_STAGE_ORDER[1]
    root, run, preflight = _project(tmp_path, disabled_stage=disabled)
    effective = yaml.safe_load((run / "effective_config.yaml").read_text(encoding="utf-8"))
    effective["campaign_tests"][disabled]["enabled"] = False
    summary = json.loads((run / "campaign_test_summary.json").read_text(encoding="utf-8"))
    manifest = json.loads((run / "run_manifest.json").read_text(encoding="utf-8"))
    canonical = root / "research/datasets/demo_es/bars.csv"
    stages = mvp._stage_bindings(
        run,
        effective,
        summary,
        manifest,
        root,
        file_sha256(canonical),
        mvp.ExecutionAssumptions.from_core_config(effective["core"]).as_dict(),
    )

    bound = stages[1]
    assert bound["summary"]["status"] == "skipped"
    assert bound["summary"]["skip_reason"] == "disabled"
    assert bound["stage_result"] is None
    assert bound["missing_stage_result_reason"] == "disabled"


def test_rejects_hash_valid_strategy_spec_execution_drift(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    root, run, preflight = _project(tmp_path)
    campaign_root = root / "research/campaigns/active/recipe_demo"
    spec_path = campaign_root / "strategy_spec.yaml"
    spec = yaml.safe_load(spec_path.read_text(encoding="utf-8"))
    spec["execution"]["tick_size"] = 0.5
    spec["execution"]["tick_value"] = 25.0
    _write_yaml(spec_path, spec)
    manifest_path = campaign_root / "authoring_manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["compiled_document_sha256"]["strategy_spec.yaml"] = mvp._compiled_object_sha256(spec)
    _write_json(manifest_path, manifest)

    with pytest.raises(ValueError, match="strategy spec execution tick_size"):
        _build(root, run, preflight, monkeypatch)


@pytest.mark.parametrize(
    ("mutation", "message"),
    [
        ("draft_sha", "authoring draft_sha256 must be a lowercase SHA-256"),
        ("date", "authoring created_at must be a valid YYYY-MM-DD date"),
        ("certification", "certified recipe strategy certification mismatch"),
    ],
)
def test_rejects_hash_valid_authoring_identity_or_certification_forgery(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    mutation: str,
    message: str,
) -> None:
    root, run, preflight = _project(tmp_path)
    campaign_root = root / "research/campaigns/active/recipe_demo"
    campaign_path = campaign_root / "campaign.yaml"
    spec_path = campaign_root / "strategy_spec.yaml"
    manifest_path = campaign_root / "authoring_manifest.json"
    campaign = yaml.safe_load(campaign_path.read_text(encoding="utf-8"))
    spec = yaml.safe_load(spec_path.read_text(encoding="utf-8"))
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if mutation == "draft_sha":
        spec["draft_sha256"] = "not-a-sha256"
        manifest["draft_sha256"] = "not-a-sha256"
    elif mutation == "date":
        campaign["created_at"] = "2026-02-30"
        manifest["created_at"] = "2026-02-30"
    else:
        forged = {"strategy_id": "forged", "implementation_sha256": "0" * 64}
        spec["strategy_certification"] = forged
        spec["variant_strategy_certifications"] = {"v01": forged}
        manifest["strategy_certification"] = forged
        manifest["variant_strategy_certifications"] = {"v01": forged}
    _write_yaml(campaign_path, campaign)
    _write_yaml(spec_path, spec)
    manifest["compiled_document_sha256"]["campaign.yaml"] = mvp._compiled_object_sha256(campaign)
    manifest["compiled_document_sha256"]["strategy_spec.yaml"] = mvp._compiled_object_sha256(spec)
    _write_json(manifest_path, manifest)

    with pytest.raises(ValueError, match=message):
        _build(root, run, preflight, monkeypatch)


@pytest.mark.parametrize(
    "field",
    [
        "cancel_pending_orders_before_flatten",
        "reject_if_position_after_flatten_deadline",
        "reject_if_pending_order_after_flatten_deadline",
        "reject_if_entry_after_latest_entry_time",
    ],
)
def test_rejects_compiler_fixed_execution_safety_drift(tmp_path: Path, field: str) -> None:
    root, _run, _preflight = _project(tmp_path)
    campaign_root = root / "research/campaigns/active/recipe_demo"
    source = yaml.safe_load((campaign_root / "variants/v01/config.yaml").read_text(encoding="utf-8"))
    execution = yaml.safe_load((campaign_root / "strategy_spec.yaml").read_text(encoding="utf-8"))["execution"]
    source["apex_rules"][field] = False

    with pytest.raises(ValueError, match=f"compiled execution safety {field}"):
        mvp._validate_authoring_execution(execution, source)


@pytest.mark.parametrize(
    ("mutation", "message"),
    [
        ("source", "campaign source 0 fields"),
        ("fingerprint", "campaign economic edge fingerprint fields"),
        ("duplicate", "campaign duplicate review ledger queries"),
        ("distinction", "campaign variant distinction v01 fields"),
    ],
)
def test_rejects_hash_valid_malformed_research_publication(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    mutation: str,
    message: str,
) -> None:
    root, run, preflight = _project(tmp_path)
    campaign_root = root / "research/campaigns/active/recipe_demo"
    campaign_path = campaign_root / "campaign.yaml"
    campaign = yaml.safe_load(campaign_path.read_text(encoding="utf-8"))
    if mutation == "source":
        campaign["sources"][0].pop("authors")
    elif mutation == "fingerprint":
        campaign["economic_edge_fingerprint"].pop("causal_mechanism")
    elif mutation == "duplicate":
        campaign["duplicate_edge_review"]["ledger_queries"] = []
    else:
        campaign["variant_distinctions"]["v01"]["unexpected"] = "forged"
    _write_yaml(campaign_path, campaign)
    manifest_path = campaign_root / "authoring_manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["compiled_document_sha256"]["campaign.yaml"] = mvp._compiled_object_sha256(campaign)
    _write_json(manifest_path, manifest)

    with pytest.raises(ValueError, match=message):
        _build(root, run, preflight, monkeypatch)


def test_accepts_producer_relative_source_path_identity(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    root, run, preflight = _project(tmp_path)
    relative = "research/campaigns/active/recipe_demo/variants/v01/config.yaml"
    _update_summary_and_manifest(
        run,
        lambda document: document.__setitem__(
            "source_config_path" if "stages" in document else "config_source", relative
        ),
    )
    results_path = root / "research/campaigns/active/recipe_demo/results_index.yaml"
    results = yaml.safe_load(results_path.read_text(encoding="utf-8"))
    results["runs"][0]["source_config_path"] = relative
    _write_yaml(results_path, results)

    report = _build(root, run, preflight, monkeypatch)

    assert report["producer_bindings"]["source_results_index_entry"]["source_config_path"] == relative


def test_accepts_distinct_source_and_exchange_timezones_and_rejects_swap(tmp_path: Path) -> None:
    root, run, _preflight = _project(tmp_path)
    source_path = root / "research/campaigns/active/recipe_demo/variants/v01/config.yaml"
    source = yaml.safe_load(source_path.read_text(encoding="utf-8"))
    source["data"]["source_timezone"] = "UTC"
    manifest_path = root / "research/datasets/demo_es/dataset_manifest.json"
    dataset_manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    dataset_manifest["timezone"] = "UTC"
    _write_json(manifest_path, dataset_manifest)
    summary = json.loads((run / "campaign_test_summary.json").read_text(encoding="utf-8"))

    binding = mvp._dataset_binding(source, summary, root)

    assert binding["manifest_document"]["timezone"] == "UTC"
    assert binding["manifest_document"]["exchange_timezone"] == "America/New_York"
    swapped = deepcopy(source)
    swapped["data"]["source_timezone"] = "America/New_York"
    swapped["data"]["exchange_timezone"] = "UTC"
    swapped["data"]["timezone"] = "UTC"
    with pytest.raises(ValueError, match="dataset manifest timezone"):
        mvp._dataset_binding(swapped, summary, root)


def test_rejects_undersized_mechanics_random_sample(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    root, run, preflight = _project(tmp_path)
    approval_path = root / "research_artifacts/validation_approvals/recipe_demo/v01/approval.json"
    approval = json.loads(approval_path.read_text(encoding="utf-8"))
    approval["sampled_trade_ids"] = [1]
    approval["sampling_categories"] = {
        "random_trades": [1],
        "warning_representatives": [],
        "resolved_ambiguities": [],
        "universal_coverage": [],
    }
    approval["sampling_reasons"] = {"1": ["deterministic random baseline"]}
    _write_json(approval_path, approval)

    with pytest.raises(ValueError, match="random sample count"):
        _build(root, run, preflight, monkeypatch)


@pytest.mark.parametrize(
    ("mutation", "message"),
    [
        ("union", "sampled/category ordered union"),
        ("reasons", "sampling reason IDs"),
        ("boolean_id", "string or integer trade ID"),
    ],
)
def test_rejects_malformed_mechanics_sampling_structure(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    mutation: str,
    message: str,
) -> None:
    root, run, preflight = _project(tmp_path)
    approval_path = root / "research_artifacts/validation_approvals/recipe_demo/v01/approval.json"
    approval = json.loads(approval_path.read_text(encoding="utf-8"))
    if mutation == "union":
        approval["sampled_trade_ids"] = [5, 4, 3, 2, 1]
    elif mutation == "reasons":
        approval["sampling_reasons"].pop("5")
    else:
        approval["sampled_trade_ids"][0] = True
        approval["sampling_categories"]["random_trades"][0] = True
        approval["sampling_reasons"]["True"] = approval["sampling_reasons"].pop("1")
    _write_json(approval_path, approval)

    with pytest.raises(ValueError, match=message):
        _build(root, run, preflight, monkeypatch)


def test_rejects_same_size_noncanonical_mechanics_sample(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    root, run, preflight = _project(tmp_path)
    approval_path = root / "research_artifacts/validation_approvals/recipe_demo/v01/approval.json"
    approval = json.loads(approval_path.read_text(encoding="utf-8"))
    replacement = list(reversed(approval["sampled_trade_ids"]))
    approval["sampled_trade_ids"] = replacement
    approval["sampling_categories"]["random_trades"] = replacement
    approval["sampling_reasons"] = {str(trade_id): ["deterministic random baseline"] for trade_id in replacement}
    _write_json(approval_path, approval)

    with pytest.raises(ValueError, match="approval/planner sampled_trade_ids"):
        _build(root, run, preflight, monkeypatch)


def test_rejects_mixed_alias_and_nonexistent_mechanics_ids(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    root, run, preflight = _project(tmp_path)
    approval_path = root / "research_artifacts/validation_approvals/recipe_demo/v01/approval.json"
    approval = json.loads(approval_path.read_text(encoding="utf-8"))
    approval["sampled_trade_ids"] = [1, "1", 2, 3, 4]
    approval["sampling_categories"]["random_trades"] = [1, "1", 2, 3, 4]
    approval["sampling_reasons"] = {
        "1": ["deterministic random baseline"],
        "2": ["deterministic random baseline"],
        "3": ["deterministic random baseline"],
        "4": ["deterministic random baseline"],
    }
    _write_json(approval_path, approval)
    with pytest.raises(ValueError, match="sampled_trade_ids must be unique"):
        _build(root, run, preflight, monkeypatch)

    root, run, preflight = _project(tmp_path / "nonexistent")
    approval_path = root / "research_artifacts/validation_approvals/recipe_demo/v01/approval.json"
    approval = json.loads(approval_path.read_text(encoding="utf-8"))
    replacement = [101, 102, 103, 104, 105]
    approval["sampled_trade_ids"] = replacement
    approval["sampling_categories"]["random_trades"] = replacement
    approval["sampling_reasons"] = {str(trade_id): ["deterministic random baseline"] for trade_id in replacement}
    _write_json(approval_path, approval)
    with pytest.raises(ValueError, match="approval/planner sampled_trade_ids"):
        _build(root, run, preflight, monkeypatch)


@pytest.mark.parametrize(
    ("mutation", "message"),
    [
        ("missing", "unreviewed sampled trades"),
        ("incorrect", "non-Correct sampled trades"),
        ("empty_notes", "notes must be a non-empty string"),
    ],
)
def test_rejects_incomplete_retained_mechanics_review(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    mutation: str,
    message: str,
) -> None:
    root, run, preflight = _project(tmp_path)
    review_path = root / "research/evidence/mechanics/validation_runs/core/manual_review.parquet"
    reviews = pd.read_parquet(review_path)
    if mutation == "missing":
        reviews = reviews.iloc[1:].copy()
    elif mutation == "incorrect":
        reviews.loc[0, "reviewer_status"] = "Incorrect"
    else:
        reviews.loc[0, "reviewer_notes"] = ""
    reviews.to_parquet(review_path, index=False)

    with pytest.raises(ValueError, match=message):
        _build(root, run, preflight, monkeypatch)


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("config_hash", "0" * 64),
        ("input_data_hash", "1" * 64),
        ("validation_lane", "event_replay"),
        ("schema_version", "forged-schema"),
        ("strategy_implementation_sha256", "2" * 64),
    ],
)
def test_rejects_retained_mechanics_metadata_identity_drift(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    field: str,
    value: object,
) -> None:
    root, run, preflight = _project(tmp_path)
    metadata_path = root / "research/evidence/mechanics/validation_runs/core/metadata.json"
    metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
    metadata[field] = value
    _write_json(metadata_path, metadata)

    message = (
        "mechanics metadata strategy_implementation_sha256"
        if field == "strategy_implementation_sha256"
        else "technical inspection failed"
    )
    with pytest.raises(ValueError, match=message):
        _build(root, run, preflight, monkeypatch)


def test_rejects_missing_declared_bar_lane_artifact(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    root, run, preflight = _project(tmp_path)
    (root / "research/evidence/mechanics/validation_runs/core/bar_windows.parquet").unlink()

    with pytest.raises(ValueError, match="technical inspection failed.*bar_windows"):
        _build(root, run, preflight, monkeypatch)


@pytest.mark.parametrize(
    ("mutation", "message"),
    [
        ("map", "mechanics artifact map"),
        ("count", "mechanics record count trades"),
    ],
)
def test_rejects_incoherent_declared_mechanics_inventory(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    mutation: str,
    message: str,
) -> None:
    root, run, preflight = _project(tmp_path)
    metadata_path = root / "research/evidence/mechanics/validation_runs/core/metadata.json"
    metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
    if mutation == "map":
        metadata["artifact_files"].pop("bar_windows")
    else:
        metadata["record_counts"]["trades"] = 999
    _write_json(metadata_path, metadata)

    with pytest.raises(ValueError, match=message):
        _build(root, run, preflight, monkeypatch)


def test_accepts_fewer_random_samples_when_evidence_has_fewer_trades(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root, run, preflight = _project(tmp_path)
    evidence_dir = root / "research/evidence/mechanics/validation_runs/core"
    evidence_metadata = evidence_dir / "metadata.json"
    metadata = json.loads(evidence_metadata.read_text(encoding="utf-8"))
    metadata["source_trade_count"] = 2
    metadata["record_counts"]["trades"] = 2
    metadata["record_counts"]["bar_windows"] = 2
    _write_json(evidence_metadata, metadata)
    for filename in ("trades.parquet", "bar_windows.parquet"):
        path = evidence_dir / filename
        pd.read_parquet(path).iloc[:2].to_parquet(path, index=False)
    source_path = root / "research/campaigns/active/recipe_demo/variants/v01/config.yaml"
    approval = MechanicsApprovalService().approve(
        source_path,
        reviewer="SIMULATED_MVP_FIXTURE_ONLY",
        notes="SIMULATED mechanics decision on a synthetic fixture. No owner authority.",
        reviewed_at="2026-09-27T00:00:00+00:00",
    )

    report = _build(root, run, preflight, monkeypatch)
    assert report["mechanics"]["approval_record"]["sampled_trade_ids"] == approval["sampled_trade_ids"]
    assert len(approval["sampled_trade_ids"]) == 2


def test_results_index_allows_other_entries_but_requires_exact_current_entry(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root, run, preflight = _project(tmp_path)
    results_path = root / "research/campaigns/active/recipe_demo/results_index.yaml"
    results = yaml.safe_load(results_path.read_text(encoding="utf-8"))
    results["runs"].insert(0, {"campaign_id": "recipe_demo", "test_run_id": "older"})
    _write_yaml(results_path, results)
    report = _build(root, run, preflight, monkeypatch)
    assert report["producer_bindings"]["source_results_index_entry"]["test_run_id"] == "run1"

    _update_summary_and_manifest(
        run,
        lambda document: document.__setitem__(
            "source_results_index_path", "research/campaigns/active/recipe_demo/campaign.yaml"
        )
        if "source_results_index_path" in document
        else document.__setitem__("source_results_index", "research/campaigns/active/recipe_demo/campaign.yaml"),
    )
    with pytest.raises(ValueError, match="canonical source results index path"):
        _build(root, run, preflight, monkeypatch)


def test_rejects_incomplete_authoring_document_topology(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    root, run, preflight = _project(tmp_path)
    manifest_path = root / "research/campaigns/active/recipe_demo/authoring_manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["compiled_document_sha256"].pop("campaign.yaml")
    _write_json(manifest_path, manifest)
    with pytest.raises(ValueError, match="compiled document topology"):
        _build(root, run, preflight, monkeypatch)


def test_rejects_hash_valid_semantically_contradictory_authoring_documents(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root, run, preflight = _project(tmp_path)
    campaign_root = root / "research/campaigns/active/recipe_demo"
    manifest_path = campaign_root / "authoring_manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    for name in ("campaign.yaml", "strategy_spec.yaml"):
        path = campaign_root / name
        document = yaml.safe_load(path.read_text(encoding="utf-8"))
        document["certified_recipe"] = "opening_range_breakout"
        _write_yaml(path, document)
        manifest["compiled_document_sha256"][name] = mvp._compiled_object_sha256(document)
    _write_json(manifest_path, manifest)
    with pytest.raises(ValueError, match="campaign certified recipe"):
        _build(root, run, preflight, monkeypatch)


def test_rejects_hash_valid_forged_mechanic_signature(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    root, run, preflight = _project(tmp_path)
    campaign_root = root / "research/campaigns/active/recipe_demo"
    manifest_path = campaign_root / "authoring_manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    forged = "0" * 64
    campaign_path = campaign_root / "campaign.yaml"
    campaign = yaml.safe_load(campaign_path.read_text(encoding="utf-8"))
    campaign["variant_distinctions"]["v01"]["mechanic_signature"] = forged
    _write_yaml(campaign_path, campaign)
    spec_path = campaign_root / "strategy_spec.yaml"
    spec = yaml.safe_load(spec_path.read_text(encoding="utf-8"))
    spec["variants"][0]["mechanic_signature"] = forged
    _write_yaml(spec_path, spec)
    manifest["variant_mechanic_signatures"]["v01"] = forged
    manifest["compiled_document_sha256"]["campaign.yaml"] = mvp._compiled_object_sha256(campaign)
    manifest["compiled_document_sha256"]["strategy_spec.yaml"] = mvp._compiled_object_sha256(spec)
    _write_json(manifest_path, manifest)
    with pytest.raises(ValueError, match="strategy spec mechanic signature"):
        _build(root, run, preflight, monkeypatch)


@pytest.mark.parametrize(
    ("field", "value", "message"),
    [
        ("symbol", "NQ", "dataset manifest symbol"),
        ("timeframe", "5m", "dataset manifest timeframe"),
        ("timezone", "UTC", "dataset manifest timezone"),
        ("timestamp_semantics", "bar_close", "dataset manifest timestamp_semantics"),
        ("row_count", 999, "strategy spec dataset"),
    ],
)
def test_rejects_dataset_execution_metadata_drift(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    field: str,
    value: object,
    message: str,
) -> None:
    root, run, preflight = _project(tmp_path)
    manifest_path = root / "research/datasets/demo_es/dataset_manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest[field] = value
    _write_json(manifest_path, manifest)
    with pytest.raises(ValueError, match=message):
        _build(root, run, preflight, monkeypatch)


@pytest.mark.parametrize(
    ("field", "value", "message"),
    [
        ("config_hash", "0" * 64, "mechanics gate config hash"),
        ("config_path", "research/campaigns/active/different/config.yaml", "mechanics gate config path"),
        ("verdict", "FAIL", "mechanics gate verdict"),
        ("lane", "event_replay", "mechanics gate lane"),
    ],
)
def test_rejects_recorded_mechanics_gate_drift(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    field: str,
    value: object,
    message: str,
) -> None:
    root, run, preflight = _project(tmp_path)

    def update(document):
        document["mechanics_validation_gate"][field] = value

    _update_summary_and_manifest(run, update)
    with pytest.raises(ValueError, match=message):
        _build(root, run, preflight, monkeypatch)


@pytest.mark.parametrize(
    ("field", "value", "message"),
    [
        ("schema", "unsupported/v9", "technical inspection failed"),
        ("review_scope", "profitability", "review scope"),
        ("profitability_approval", True, "profitability approval"),
        ("sampling_categories", {}, "technical inspection failed"),
    ],
)
def test_rejects_malformed_mechanics_approval(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    field: str,
    value: object,
    message: str,
) -> None:
    root, run, preflight = _project(tmp_path)
    approval_path = root / "research_artifacts/validation_approvals/recipe_demo/v01/approval.json"
    approval = json.loads(approval_path.read_text(encoding="utf-8"))
    approval[field] = value
    _write_json(approval_path, approval)
    with pytest.raises(ValueError, match=message):
        _build(root, run, preflight, monkeypatch)


@pytest.mark.parametrize(
    ("configs", "data_sources", "message"),
    [
        (["research/campaigns/active/different/variants/v99/config.yaml"], 1, "config identity"),
        ([], 1, "config identity"),
        (
            [
                "research/campaigns/active/recipe_demo/variants/v01/config.yaml",
                "research/campaigns/active/different/variants/v99/config.yaml",
            ],
            1,
            "config identity",
        ),
        (["research/campaigns/active/recipe_demo/variants/v01/config.yaml"], 0, "data source count"),
    ],
)
def test_rejects_preflight_input_identity_drift(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    configs: list[str],
    data_sources: int,
    message: str,
) -> None:
    root, run, preflight = _project(tmp_path)
    preflight["configs_checked"] = configs
    preflight["data_sources_checked"] = data_sources
    _write_json(root / "pre-run-preflight.json", preflight)
    _update_summary_and_manifest(
        run,
        lambda document: document.__setitem__("submission_preflight", preflight),
    )
    with pytest.raises(ValueError, match=message):
        _build(root, run, preflight, monkeypatch)


def test_preflight_accepts_equivalent_absolute_config_identity(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    root, run, preflight = _project(tmp_path)
    source_path = root / "research/campaigns/active/recipe_demo/variants/v01/config.yaml"
    preflight["configs_checked"] = [str(source_path)]
    _write_json(root / "pre-run-preflight.json", preflight)
    _update_summary_and_manifest(
        run,
        lambda document: document.__setitem__("submission_preflight", preflight),
    )
    report = _build(root, run, preflight, monkeypatch)
    assert report["preflight"]["recorded"]["configs_checked"] == [str(source_path)]


def test_cli_uses_exclusive_create_and_refuses_inside_run(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    root, run, _preflight = _project(tmp_path)
    document = {"overall_verdict": "NEEDS MANUAL REVIEW"}
    monkeypatch.setattr(mvp, "build_diagnostic_index", lambda **_kwargs: document)
    output = root / "diagnostics/index.json"
    arguments = [
        "run_mvp_diagnostic",
        "--project-root",
        str(root),
        "--run-dir",
        str(run),
        "--preflight-receipt",
        str(root / "pre-run-preflight.json"),
        "--output",
        str(output),
        "--mode",
        "synthetic",
    ]
    monkeypatch.setattr(sys, "argv", arguments)
    mvp.main()
    with pytest.raises(FileExistsError):
        mvp.main()

    arguments[arguments.index(str(output))] = str(run / "inside.json")
    monkeypatch.setattr(sys, "argv", arguments)
    with pytest.raises(ValueError, match="outside the run directory"):
        mvp.main()


def test_runbook_existing_stage_summary_blocks_runner_stub(tmp_path: Path) -> None:
    runbook = (Path(__file__).parents[1] / "docs/operations/codex-mvp.md").read_text(encoding="utf-8")
    guard_line = "test ! -e research_artifacts/mvp_diagnostics/ATTEMPT-stage-summary.json && \\"
    assert f"{guard_line}\n   PYTHONPATH=/ABSOLUTE/PATH/TO/ALPHAQUEST/src" in runbook
    existing = tmp_path / "stage-summary.json"
    existing.write_text("preserved", encoding="utf-8")
    marker = tmp_path / "runner-called"
    runner = tmp_path / "runner-stub"
    runner.write_text('#!/bin/sh\ntouch "$1"\n', encoding="utf-8")
    runner.chmod(0o755)

    completed = subprocess.run(
        [
            "/bin/sh",
            "-c",
            'test ! -e "$1" && "$2" "$3"',
            "guard-test",
            str(existing),
            str(runner),
            str(marker),
        ],
        check=False,
    )

    assert completed.returncode != 0
    assert not marker.exists()
    assert existing.read_text(encoding="utf-8") == "preserved"
