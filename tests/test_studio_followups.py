from __future__ import annotations

from datetime import UTC, date, datetime
import hashlib
import json
from pathlib import Path
from types import SimpleNamespace

import pytest
import yaml

from alphaquest.research.campaign_stages import DEFAULT_STAGE_ORDER
from alphaquest.studio.followups import (
    FollowUpAttemptRequestV1,
    FollowUpAttemptService,
    MechanicParameterPatchV1,
    _config_mechanic_signature,
)
from alphaquest.studio.jobs import SQLiteJobQueue


VARIANTS = tuple(f"v{index:02d}" for index in range(1, 6))
FIXED_NOW = datetime(2026, 7, 15, 12, 30, tzinfo=UTC)


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _object_sha(value: object) -> str:
    encoded = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _dataset(root: Path, dataset_id: str, *, quality: str = "PASS", start: str = "2020-01-01") -> dict:
    dataset_root = root / "research/datasets" / dataset_id
    dataset_root.mkdir(parents=True)
    bars = dataset_root / "bars.csv"
    bars.write_text(
        "timestamp,open,high,low,close,volume\n" f"{start}T14:30:00+00:00,5000,5001,4999,5000.5,10\n",
        encoding="utf-8",
    )
    document = {
        "schema": "alphaquest.dataset-manifest/v1",
        "dataset_id": dataset_id,
        "source": "csv",
        "path": str(bars.relative_to(root)),
        "symbol": "ES",
        "timeframe": "1m",
        "timezone": "America/New_York",
        "exchange_timezone": "America/New_York",
        "timestamp_semantics": "bar_open",
        "source_timestamp_semantics": "bar_open",
        "source_sha256": _sha(bars),
        "canonical_sha256": _sha(bars),
        "coverage_start": f"{start}T09:30:00-04:00",
        "coverage_end": "2025-12-31T16:00:00-05:00",
        "roll_policy": "single_contract",
        "continuous_contract": "none",
        "contract_column": None,
        "source_contract_column": None,
        "contract_count": 1,
        "roll_calendar": None,
        "roll_calendar_sha256": None,
        "transformations": [],
        "row_count": 1,
        "dropped_row_count": 0,
        "gap_count": 0,
        "duplicate_count": 0,
        "out_of_order_count": 0,
        "invalid_ohlc_count": 0,
        "cadence_violation_count": 0,
        "certified_features": [],
        "quality_verdict": quality,
        "quality_notes": [],
    }
    (dataset_root / "dataset_manifest.json").write_text(
        json.dumps(document, indent=2) + "\n",
        encoding="utf-8",
    )
    return document


def _workspace(root: Path, *, rescue_allowed: bool = False) -> Path:
    _dataset(root, "bars_v1")
    campaign_root = root / "research/campaigns/active/demo"
    campaign_root.mkdir(parents=True)
    campaign = {
        "campaign_id": "demo",
        "title": "Governed demo",
        "governance_contract_version": 2,
        "variants": list(VARIANTS),
        "rescue_policy": {
            "allowed": rescue_allowed,
            "max_rescues_per_failed_variant": 1,
        },
    }
    (campaign_root / "campaign.yaml").write_text(yaml.safe_dump(campaign), encoding="utf-8")
    for variant in VARIANTS:
        stop_module, stop_params, target_module, target_params = {
            "v01": (
                "points_from_entry",
                {"stop_points": 2.0, "round_to_tick": True},
                "fixed_r",
                {"target_r_multiple": 1.5},
            ),
            "v02": (
                "percent_from_entry",
                {"stop_pct": 0.002, "round_to_tick": True},
                "fixed_r",
                {"target_r_multiple": 1.5},
            ),
            "v03": (
                "fixed_dollar_per_contract",
                {"dollars_per_contract": 250.0, "tick_value": 12.5, "round_to_tick": True},
                "cost_adjusted_fixed_r",
                {
                    "target_r_multiple": 1.5,
                    "tick_size": 0.25,
                    "tick_value": 12.5,
                    "commission_per_contract": 2.5,
                    "slippage_ticks": 1,
                    "round_to_tick": True,
                },
            ),
            "v04": (
                "points_from_entry",
                {"stop_points": 2.0, "round_to_tick": True},
                "cost_adjusted_fixed_r",
                {
                    "target_r_multiple": 1.5,
                    "tick_size": 0.25,
                    "tick_value": 12.5,
                    "commission_per_contract": 2.5,
                    "slippage_ticks": 1,
                    "round_to_tick": True,
                },
            ),
            "v05": (
                "fixed_dollar_per_contract",
                {"dollars_per_contract": 250.0, "tick_value": 12.5, "round_to_tick": True},
                "fixed_r",
                {"target_r_multiple": 1.5},
            ),
        }[variant]
        config = {
            "campaign_id": "demo",
            "variant_id": variant,
            "attempt_id": "original",
            "attempt_kind": "original",
            "attempt_provenance": "authored",
            "strategy_name": variant,
            "symbol": "ES",
            "dataset_id": "bars_v1",
            "timeframe": "1m",
            "research_metadata": {
                "validation_gate": {
                    "required": True,
                    "lane": "bar",
                    "data_subset": {"start_date": "2020-01-01", "end_date": "2020-01-08"},
                    "evidence_dir": str(root / f"old-validation/{variant}"),
                    "approval_path": str(root / f"old-approvals/{variant}.json"),
                }
            },
            "data": {
                "dataset_id": "bars_v1",
                "source": "csv",
                "raw_csv": "research/datasets/bars_v1/bars.csv",
                "symbol": "ES",
                "timezone": "America/New_York",
                "exchange_timezone": "America/New_York",
            },
            "strategy": {
                "entry": {
                    "module": "calendar_session_bias",
                    "params": {
                        "signal_time": "09:35:00",
                        "bar_interval_minutes": 1.0,
                        "max_trades_per_day": 1,
                        "weekday_directions": {"0": "long"},
                        "setup_mode": f"weekday_bias_{variant}",
                    },
                },
                "sl": {
                    "module": stop_module,
                    "params": stop_params,
                },
                "tp": {"module": target_module, "params": target_params},
                "flatten_time": "15:55:00",
            },
            "core": {
                "tick_size": 0.25,
                "point_value": 50.0,
                "tick_value": 12.5,
                "commission_per_contract": 2.5,
                "slippage_ticks": 1,
                "data_subset": {
                    "start_date": "2020-01-01",
                    "end_date": "2025-12-31",
                    "session_labels": ["RTH"],
                },
            },
            "core_grid": {"parameters": {}, "data_subset": {}},
            "monkey": {"data_subset": {}},
            "wfa": {"data_subset": {}},
            "campaign_tests": {
                "stage_order": list(DEFAULT_STAGE_ORDER),
                **{stage: {"enabled": True} for stage in DEFAULT_STAGE_ORDER},
            },
            "test_run_id": "run1",
        }
        path = campaign_root / "variants" / variant / "config.yaml"
        path.parent.mkdir(parents=True)
        path.write_text(yaml.safe_dump(config, sort_keys=False), encoding="utf-8")
    _rewrite_source_contract(campaign_root)
    return campaign_root


def _rewrite_source_contract(campaign_root: Path) -> None:
    campaign = yaml.safe_load((campaign_root / "campaign.yaml").read_text(encoding="utf-8"))
    variants = tuple(campaign["variants"])
    signatures: dict[str, str] = {}
    for variant in variants:
        path = campaign_root / "variants" / variant / "config.yaml"
        config = yaml.safe_load(path.read_text(encoding="utf-8"))
        signature = _config_mechanic_signature(config)
        config.setdefault("research_metadata", {})["mechanic_signature"] = signature
        path.write_text(yaml.safe_dump(config, sort_keys=False), encoding="utf-8")
        signatures[variant] = signature
    strategy_spec = {
        "schema": "alphaquest.strategy-spec/v1",
        "campaign_id": "demo",
        "frozen": True,
        "variants": [{"variant_id": variant, "mechanic_signature": signatures[variant]} for variant in variants],
    }
    (campaign_root / "strategy_spec.yaml").write_text(
        yaml.safe_dump(strategy_spec, sort_keys=False),
        encoding="utf-8",
    )
    compiled_paths = [
        "campaign.yaml",
        "strategy_spec.yaml",
        *(f"variants/{variant}/config.yaml" for variant in variants),
    ]
    manifest = {
        "schema": "alphaquest.authoring-manifest/v1",
        "campaign_id": "demo",
        "variant_count": 5,
        "variant_mechanic_signatures": signatures,
        "compiled_document_sha256": {
            relative: _object_sha(yaml.safe_load((campaign_root / relative).read_text(encoding="utf-8")))
            for relative in compiled_paths
        },
    }
    (campaign_root / "authoring_manifest.json").write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _service(root: Path, monkeypatch: pytest.MonkeyPatch) -> FollowUpAttemptService:
    def passed_preflight(*, config_paths, **_kwargs):
        paths = list(config_paths)
        assert len(paths) == 5
        assert all(".staging" in str(path) for path in paths)
        return {"passed": True, "failures": [], "warnings": []}

    monkeypatch.setattr("alphaquest.studio.followups.run_preflight", passed_preflight)
    monkeypatch.setattr("alphaquest.studio.followups.write_definition_manifests", lambda *_a, **_k: {})
    monkeypatch.setattr(
        "alphaquest.studio.followups.refresh_generated_indexes_if_stale",
        lambda *_a, **_k: {"refreshed": True},
    )
    tokens = iter(("aaa11111", "bbb22222", "ccc33333", "ddd44444"))
    return FollowUpAttemptService(root, now=lambda: FIXED_NOW, token=lambda: next(tokens))


def _request(kind: str, **updates) -> FollowUpAttemptRequestV1:
    values = {
        "campaign_id": "demo",
        "attempt_kind": kind,
        "parent_attempt_id": "original",
        "reason": (
            "The prior attempt is preserved unchanged; this explicit follow-up tests the stated governed "
            "reason without silently redefining the economic edge or using observed PnL to tune mechanics."
        ),
        "created_by": "researcher@example.com",
    }
    values.update(updates)
    return FollowUpAttemptRequestV1.model_validate(values)


def test_replication_is_a_new_complete_immutable_identity_and_never_edits_originals(tmp_path, monkeypatch):
    campaign_root = _workspace(tmp_path)
    originals = {path: path.read_bytes() for path in campaign_root.glob("variants/*/config.yaml")}
    service = _service(tmp_path, monkeypatch)

    first = service.create(_request("replication"))
    second = service.create(_request("replication"))

    assert first.attempt_id == "replication_20260715t123000_aaa11111"
    assert second.attempt_id == "replication_20260715t123000_bbb22222"
    assert first.attempt_id != second.attempt_id
    assert len(first.config_paths) == 5
    assert first.ledger_rows_appended == 5
    assert all(path.is_file() for path in first.config_paths)
    assert originals == {path: path.read_bytes() for path in originals}
    manifest = json.loads(first.manifest_path.read_text(encoding="utf-8"))
    assert manifest["immutable"] is True
    assert manifest["automatic_replay_permitted"] is False
    assert manifest["preflight"]["verdict"] == "PASS"
    for path in first.config_paths:
        cfg = yaml.safe_load(path.read_text(encoding="utf-8"))
        assert cfg["attempt_id"] == first.attempt_id
        assert cfg["parent_attempt_id"] == "original"
        assert cfg["test_run_id"] == f"attempt_{first.attempt_id}"
        gate = cfg["research_metadata"]["validation_gate"]
        assert first.attempt_id in gate["evidence_dir"]
        assert first.attempt_id in gate["approval_path"]
    ledger = (tmp_path / "research_ledger.csv").read_text(encoding="utf-8")
    assert f"follow_up_attempt/{first.attempt_id}" in ledger
    assert f"follow_up_attempt/{second.attempt_id}" in ledger


def test_failed_preflight_leaves_no_follow_up_definition(tmp_path, monkeypatch):
    campaign_root = _workspace(tmp_path)
    monkeypatch.setattr(
        "alphaquest.studio.followups.run_preflight",
        lambda **_kwargs: {"passed": False, "failures": ["ambiguous session"], "warnings": []},
    )
    service = FollowUpAttemptService(
        tmp_path,
        now=lambda: FIXED_NOW,
        token=lambda: "blocked1",
    )

    with pytest.raises(ValueError, match="ambiguous session"):
        service.create(_request("replication"))

    root = campaign_root / "follow_up_attempts"
    assert not any(path.name == "replication_20260715t123000_blocked1" for path in root.iterdir())
    assert not list(root.glob("*.staging"))


def test_ledger_failure_rolls_back_the_new_source_tree(tmp_path, monkeypatch):
    campaign_root = _workspace(tmp_path)
    service = _service(tmp_path, monkeypatch)
    monkeypatch.setattr(
        "alphaquest.studio.followups.append_planned_follow_up",
        lambda **_kwargs: (_ for _ in ()).throw(RuntimeError("ledger unavailable")),
    )

    with pytest.raises(RuntimeError, match="ledger unavailable"):
        service.create(_request("replication"))

    attempt = campaign_root / "follow_up_attempts/replication_20260715t123000_aaa11111"
    assert not attempt.exists()
    assert not (tmp_path / "research_ledger.csv").exists()


def test_data_refresh_requires_pass_governed_manifest_and_changes_only_declared_data(tmp_path, monkeypatch):
    _workspace(tmp_path)
    _dataset(tmp_path, "bars_v2", start="2021-01-01")
    service = _service(tmp_path, monkeypatch)

    result = service.create(_request("data_refresh", dataset_id="bars_v2"))

    manifest = json.loads(result.manifest_path.read_text(encoding="utf-8"))
    assert manifest["dataset_id"] == "bars_v2"
    assert len(manifest["changes"]) == 5
    for path in result.config_paths:
        cfg = yaml.safe_load(path.read_text(encoding="utf-8"))
        assert cfg["dataset_id"] == "bars_v2"
        assert cfg["data"]["raw_csv"] == "research/datasets/bars_v2/bars.csv"
        assert cfg["strategy"]["entry"]["params"]["signal_time"] == "09:35:00"

    _dataset(tmp_path, "bars_bad", quality="NEEDS MANUAL REVIEW", start="2022-01-01")
    with pytest.raises(ValueError, match="quality verdict PASS"):
        service.create(_request("data_refresh", dataset_id="bars_bad"))


def test_follow_up_paths_honor_configured_evidence_and_artifact_roots(tmp_path, monkeypatch):
    _workspace(tmp_path)
    config_root = tmp_path / "config"
    config_root.mkdir()
    (config_root / "storage_layout.yaml").write_text(
        yaml.safe_dump(
            {
                "schema": "alphaquest.storage-layout/v1",
                "active_campaign_root": "research/campaigns/active",
                "archive_campaign_roots": ["research/campaigns/archive"],
                "evidence_roots": ["custom/evidence"],
                "research_artifact_root": "custom/artifacts",
                "catalog_root": "catalogs",
                "views_root": "views",
                "run_store_root": "run-store",
                "draft_root": "research/drafts",
                "dataset_root": "research/datasets",
                "handoff_root": "research/handoffs",
                "studio_runtime_root": "run-store/studio-runtime",
            }
        ),
        encoding="utf-8",
    )
    service = _service(tmp_path, monkeypatch)

    result = service.create(_request("replication"))
    cfg = yaml.safe_load(result.config_paths[0].read_text(encoding="utf-8"))
    gate = cfg["research_metadata"]["validation_gate"]

    assert gate["evidence_dir"].startswith(str(tmp_path / "custom/evidence"))
    assert gate["approval_path"].startswith(str(tmp_path / "custom/artifacts/validation_approvals"))


def test_data_refresh_daily_tsm_validation_subset_includes_twenty_session_warmup(tmp_path, monkeypatch):
    campaign_root = _workspace(tmp_path)
    for variant in VARIANTS:
        path = campaign_root / "variants" / variant / "config.yaml"
        config = yaml.safe_load(path.read_text(encoding="utf-8"))
        config["strategy"]["entry"] = {
            "module": "daily_time_series_momentum",
            "params": {
                "setup_mode": "close_to_close_trend",
                "rth_end": "16:00:00",
                "signal_time": "10:00:00",
                "bar_interval_minutes": 1.0,
                "lookback_sessions": 20,
                "confirmation_sessions": 1,
                "min_abs_trend_return_pct": 0.0,
                "min_trend_zscore": 0.0,
                "max_trades_per_day": 1,
                "allow_long": True,
                "allow_short": True,
            },
        }
        path.write_text(yaml.safe_dump(config, sort_keys=False), encoding="utf-8")
    _rewrite_source_contract(campaign_root)
    _dataset(tmp_path, "bars_tsm_refresh", start="2021-01-01")
    service = _service(tmp_path, monkeypatch)

    result = service.create(_request("data_refresh", dataset_id="bars_tsm_refresh"))

    for path in result.config_paths:
        config = yaml.safe_load(path.read_text(encoding="utf-8"))
        subset = config["research_metadata"]["validation_gate"]["data_subset"]
        window_days = (date.fromisoformat(subset["end_date"]) - date.fromisoformat(subset["start_date"])).days
        assert window_days >= 50


def test_pre_pnl_correction_records_explicit_scalar_diff_and_is_forbidden_after_pnl(tmp_path, monkeypatch):
    _workspace(tmp_path)
    service = _service(tmp_path, monkeypatch)
    patch = MechanicParameterPatchV1(
        variant_id="v01",
        component="entry",
        parameter_path="signal_time",
        value="09:40:00",
    )

    result = service.create(
        _request(
            "pre_pnl_mechanics_correction",
            target_variant_id="v01",
            mechanic_patches=[patch],
        )
    )
    cfg = yaml.safe_load(result.config_paths[0].read_text(encoding="utf-8"))
    assert cfg["strategy"]["entry"]["params"]["signal_time"] == "09:40:00"
    manifest = json.loads(result.manifest_path.read_text(encoding="utf-8"))
    assert manifest["changes"] == [
        {
            "field": "signal_time",
            "new": "09:40:00",
            "old": "09:35:00",
            "reviewed": True,
            "scope": "strategy.entry.params",
            "variant_id": "v01",
        }
    ]

    evidence = tmp_path / "research/evidence/runs/demo/v01/ES/run1"
    evidence.mkdir(parents=True)
    (evidence / "campaign_test_summary.json").write_text(
        json.dumps({"attempt_id": "original", "research_verdict": "FAIL"}),
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="forbidden after performance evidence"):
        service.create(
            _request(
                "pre_pnl_mechanics_correction",
                target_variant_id="v01",
                mechanic_patches=[patch],
            )
        )


def test_pre_pnl_correction_rejects_reserved_job_without_run_files(tmp_path, monkeypatch):
    _workspace(tmp_path)
    service = _service(tmp_path, monkeypatch)
    queue = SQLiteJobQueue(service.layout.studio_runtime_root / "jobs.sqlite3")
    queue.submit(
        job_type="campaign_variant_run",
        campaign_id="demo",
        payload={
            "campaign_id": "demo",
            "variant_id": "v01",
            "attempt_id": "original",
            "config_path": str(tmp_path / "research/campaigns/active/demo/variants/v01/config.yaml"),
        },
        idempotency_key="reserved-original-v01",
        hash_locks={},
    )

    def reserve_then_crash(context, _job):
        context.reserve_attempt()
        raise RuntimeError("simulated post-reservation crash")

    failed = queue.run_once(worker_id="worker", executor=reserve_then_crash, observed_hashes={})
    assert failed is not None and failed.attempt_reserved is True
    patch = MechanicParameterPatchV1(
        variant_id="v01",
        component="sl",
        parameter_path="stop_points",
        value=2.25,
    )

    with pytest.raises(ValueError, match="forbidden after performance evidence"):
        service.create(
            _request(
                "pre_pnl_mechanics_correction",
                target_variant_id="v01",
                mechanic_patches=[patch],
            )
        )


def test_rescue_requires_campaign_authorization_parent_fail_and_maximum_one(tmp_path, monkeypatch):
    _workspace(tmp_path, rescue_allowed=True)
    evidence = tmp_path / "research/evidence/runs/demo/v01/ES/run1"
    evidence.mkdir(parents=True)
    (evidence / "campaign_test_summary.json").write_text(
        json.dumps({"attempt_id": "original", "research_verdict": "FAIL"}),
        encoding="utf-8",
    )
    service = _service(tmp_path, monkeypatch)
    patch = MechanicParameterPatchV1(
        variant_id="v01",
        component="sl",
        parameter_path="stop_points",
        value=2.25,
    )
    request = _request(
        "rescue",
        target_variant_id="v01",
        mechanic_patches=[patch],
        authorized_by="research-lead@example.com",
    )

    with pytest.raises(ValueError, match="complete, hash-valid finalized FAIL"):
        service.create(request)

    bundle_path = evidence / "reporting_v2/result_bundle_v2.json"
    bundle_path.parent.mkdir()
    bundle_path.write_text("{}\n", encoding="utf-8")
    calls = []

    def finalized_fail(path, *, config_path):
        calls.append((Path(path), Path(config_path)))
        return {
            "valid": True,
            "errors": [],
            "bundle": SimpleNamespace(
                campaign_id="demo",
                variant_id="v01",
                run_id="run1",
                verdict="FAIL",
            ),
        }

    monkeypatch.setattr("alphaquest.studio.followups.inspect_finalized_result", finalized_fail)
    result = service.create(request)
    assert result.attempt_kind == "rescue"
    assert json.loads(result.manifest_path.read_text(encoding="utf-8"))["authorized_by"]
    assert calls == [
        (
            bundle_path,
            tmp_path / "research/campaigns/active/demo/variants/v01/config.yaml",
        )
    ]
    with pytest.raises(ValueError, match="one authorized rescue"):
        service.create(request)

    blocked_root = tmp_path / "blocked"
    _workspace(blocked_root, rescue_allowed=False)
    blocked_service = _service(blocked_root, monkeypatch)
    with pytest.raises(ValueError, match="does not authorize"):
        blocked_service.create(request)


def test_mechanics_patch_recomputes_signature_and_rejects_duplicate_variant(tmp_path, monkeypatch):
    campaign_root = _workspace(tmp_path)
    entries = {
        "v01": "close_to_close_trend",
        "v02": "volatility_normalized_trend",
    }
    for variant, setup_mode in entries.items():
        path = campaign_root / "variants" / variant / "config.yaml"
        config = yaml.safe_load(path.read_text(encoding="utf-8"))
        config["strategy"]["entry"] = {
            "module": "daily_time_series_momentum",
            "params": {
                "setup_mode": setup_mode,
                "rth_end": "16:00:00",
                "signal_time": "10:00:00",
                "bar_interval_minutes": 1.0,
                "lookback_sessions": 20,
                "confirmation_sessions": 1,
                "min_abs_trend_return_pct": 0.0,
                "min_trend_zscore": 0.0,
                "max_trades_per_day": 1,
                "allow_long": True,
                "allow_short": True,
            },
        }
        if variant == "v02":
            config["strategy"]["sl"] = {
                "module": "points_from_entry",
                "params": {"stop_points": 2.0, "round_to_tick": True},
            }
        path.write_text(yaml.safe_dump(config, sort_keys=False), encoding="utf-8")
    _rewrite_source_contract(campaign_root)
    service = _service(tmp_path, monkeypatch)
    patch = MechanicParameterPatchV1(
        variant_id="v02",
        component="entry",
        parameter_path="setup_mode",
        value="close_to_close_trend",
    )

    with pytest.raises(ValueError, match="materially distinct.*duplicate signatures"):
        service.create(
            _request(
                "pre_pnl_mechanics_correction",
                target_variant_id="v02",
                mechanic_patches=[patch],
            )
        )
    assert not (campaign_root / "follow_up_attempts").exists()


def test_queueing_one_attempt_is_idempotent_but_different_attempts_are_distinct(tmp_path, monkeypatch):
    _workspace(tmp_path)
    service = _service(tmp_path, monkeypatch)
    attempt = service.create(_request("replication"))

    def gate(_cfg, path):
        return {
            "required": True,
            "config_hash": _sha(Path(path)),
            "input_data_hash": "d" * 64,
            "errors": ["fresh approval not written"],
        }

    monkeypatch.setattr("alphaquest.studio.followups.inspect_validation_gate", gate)
    first = service.queue_mechanics_validation("demo", attempt.attempt_id)
    repeated = service.queue_mechanics_validation("demo", attempt.attempt_id)

    assert [job.job_id for job in first] == [job.job_id for job in repeated]
    assert all(job.payload["attempt_id"] == attempt.attempt_id for job in first)
    assert len({job.idempotency_key for job in first}) == 5


def test_original_compiled_hash_drift_blocks_follow_up_before_source_writes(tmp_path, monkeypatch):
    campaign_root = _workspace(tmp_path)
    path = campaign_root / "variants/v01/config.yaml"
    config = yaml.safe_load(path.read_text(encoding="utf-8"))
    config["strategy"]["sl"]["params"]["stop_points"] = 99.0
    path.write_text(yaml.safe_dump(config, sort_keys=False), encoding="utf-8")
    service = _service(tmp_path, monkeypatch)

    with pytest.raises(ValueError, match="immutable original compiled source hash drift"):
        service.create(_request("replication"))
    assert not (campaign_root / "follow_up_attempts").exists()
    assert not (tmp_path / "research_ledger.csv").exists()


def test_follow_up_config_hash_drift_requires_another_explicit_attempt(tmp_path, monkeypatch):
    _workspace(tmp_path)
    service = _service(tmp_path, monkeypatch)
    attempt = service.create(_request("replication"))
    path = attempt.config_paths[0]
    cfg = yaml.safe_load(path.read_text(encoding="utf-8"))
    cfg["strategy"]["sl"]["params"]["stop_points"] = 99.0
    path.write_text(yaml.safe_dump(cfg, sort_keys=False), encoding="utf-8")

    with pytest.raises(ValueError, match="immutable follow-up config hash drift"):
        service.config_paths("demo", attempt.attempt_id)
