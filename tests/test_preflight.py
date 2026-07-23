import subprocess
import sys
from pathlib import Path

import pandas as pd
import yaml

from research.preflight import _config_paths, _is_archived_path, run_preflight


def _write_csv(path, *, duplicate: bool = False) -> None:
    rows = [
        {
            "timestamp": "2024-01-03 09:30:00-05:00",
            "open": 100.0,
            "high": 101.0,
            "low": 99.0,
            "close": 100.5,
            "volume": 100,
        },
        {
            "timestamp": "2024-01-03 09:31:00-05:00",
            "open": 100.5,
            "high": 101.5,
            "low": 100.0,
            "close": 101.0,
            "volume": 120,
        },
    ]
    if duplicate:
        rows.append(dict(rows[-1]))
    pd.DataFrame(rows).to_csv(path, index=False)


def _config(raw_csv, **overrides):
    cfg = {
        "campaign_id": "preflight_test",
        "variant_id": "baseline",
        "strategy_name": "calendar_session_bias",
        "symbol": "ES",
        "dataset_id": "unit_fixture",
        "timeframe": "1m",
        "research_metadata": {
            "mechanics_review_required": True,
            "mechanics_review": {
                "mechanic_expresses_edge": "The entry maps the calendar edge into a same-session ES signal using only completed bars and the predeclared event state before any fill is attempted.",
                "entry_logic_rationale": "The entry waits for a completed bar at a fixed signal time so the decision is point-in-time and can be executed no earlier than the next bar open.",
                "stop_loss_rationale": "The stop is a fixed percentage from entry to cap loss size consistently across all parameter combinations without using future bar information.",
                "target_exit_rationale": "The target is a fixed-R exit so reward is linked directly to the predeclared stop distance rather than optimized price levels.",
                "profitability_rationale": "The variant is approved for testing because the hypothesized edge could create repeated intraday pressure after costs while preserving enough trade density.",
                "known_failure_modes": "The edge may be too weak after slippage, may concentrate in a few sessions, or may fail when same-bar stop and target ordering is pessimistic.",
                "pre_test_decision": "approve_for_testing",
            },
        },
        "data": {
            "source": "csv",
            "raw_csv": str(raw_csv),
            "symbol": "ES",
            "timezone": "America/New_York",
            "rth_start": "09:30:00",
            "rth_end": "16:00:00",
            "eth_start": "17:00:00",
            "eth_end": "09:29:00",
        },
        "strategy": {
            "entry": {
                "module": "calendar_session_bias",
                "params": {
                    "signal_time": "09:31:00",
                    "weekday_directions": {2: "long"},
                    "max_trades_per_day": 1,
                },
            },
            "tp": {"module": "fixed_r", "params": {"target_r_multiple": 1.0}},
            "sl": {"module": "percent_from_entry", "params": {"stop_pct": 0.01}},
            "flatten_time": "15:55:00",
        },
        "core": {
            "tick_size": 0.25,
            "point_value": 50.0,
            "tick_value": 12.5,
            "commission_per_contract": 2.5,
            "slippage_ticks": 1,
            "contracts": 1,
        },
        "apex_rules": {
            "enabled": True,
            "latest_flat_time": "16:59:59",
            "force_flatten_enabled": True,
            "force_flatten_time": "16:58:30",
            "latest_entry_time": "16:45:00",
        },
    }
    for key, value in overrides.items():
        if value is None:
            cfg.pop(key, None)
        else:
            cfg[key] = value
    return cfg


def _write_config(path, cfg) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(yaml.safe_dump(cfg, sort_keys=False), encoding="utf-8")


def _write_campaign_yaml(campaign_root: Path, *, variant_count: int, expansion_rationale: str | None = None) -> None:
    campaign = {
        "campaign_id": campaign_root.name,
        "title": "Preflight test campaign",
        "variants": [
            {
                "variant_id": f"v{index:02d}",
                "rationale": "Distinct predeclared mechanics for the same edge.",
            }
            for index in range(1, variant_count + 1)
        ],
    }
    if expansion_rationale is not None:
        campaign["variant_expansion_rationale"] = expansion_rationale
    _write_config(campaign_root / "campaign.yaml", campaign)


def test_preflight_accepts_valid_config_and_timezone_aware_data(tmp_path):
    data = tmp_path / "bars.csv"
    config = tmp_path / "config.yaml"
    _write_csv(data)
    _write_config(config, _config(data))

    result = run_preflight(config_paths=[config], run_tests=False)

    assert result["passed"]
    assert result["failures"] == []


def test_preflight_rejects_nonfinite_or_nonpositive_ohlcv_before_runtime_cleaning(tmp_path):
    data = tmp_path / "bars.csv"
    config = tmp_path / "config.yaml"
    _write_csv(data)
    frame = pd.read_csv(data)
    frame.loc[0, "open"] = float("inf")
    frame.loc[1, "low"] = -1.0
    frame.to_csv(data, index=False)
    _write_config(config, _config(data))

    result = run_preflight(config_paths=[config], run_tests=False)

    assert result["passed"] is False
    assert any("non-finite, non-positive" in failure for failure in result["failures"])


def test_preflight_loads_shared_dataset_once(tmp_path, monkeypatch):
    import research.preflight as preflight

    data = tmp_path / "bars.csv"
    config_one = tmp_path / "one.yaml"
    config_two = tmp_path / "two.yaml"
    _write_csv(data)
    _write_config(config_one, _config(data, variant_id="one"))
    second = _config(data, variant_id="two")
    second["data"]["feature_set"] = "different_downstream_features"
    _write_config(config_two, second)
    original = preflight.load_raw_data
    calls = 0

    def counted_load(config):
        nonlocal calls
        calls += 1
        return original(config)

    monkeypatch.setattr(preflight, "load_raw_data", counted_load)

    result = run_preflight(config_paths=[config_one, config_two], run_tests=False)

    assert result["passed"]
    assert calls == 1
    assert result["data_sources_checked"] == 1
    assert result["data_cache_hits"] == 1


def test_explicit_terminal_rejection_remains_fail_closed(tmp_path):
    data = tmp_path / "bars.csv"
    config = tmp_path / "config.yaml"
    _write_csv(data)
    cfg = _config(data)
    cfg["research_metadata"]["mechanics_review"]["pre_test_decision"] = "reject_pre_pnl_density"
    _write_config(config, cfg)

    result = run_preflight(config_paths=[config], run_tests=False)

    assert not result["passed"]
    assert any("not an accepted pre-test lifecycle state" in failure for failure in result["failures"])


def test_preflight_rejects_campaign_with_more_than_five_variants(tmp_path):
    data = tmp_path / "bars.csv"
    campaign_root = tmp_path / "campaigns" / "es_active"
    config = campaign_root / "variants" / "v01" / "config.yaml"
    _write_csv(data)
    _write_campaign_yaml(
        campaign_root,
        variant_count=9,
        expansion_rationale=(
            "The extra mechanics are predeclared for density screening, but this text should not matter "
            "because the hard campaign cap is five variants."
        ),
    )
    _write_config(config, _config(data, campaign_id="es_active", variant_id="v01"))

    result = run_preflight(config_paths=[config], run_tests=False)

    assert not result["passed"]
    assert any("campaign variant cap is 5" in failure for failure in result["failures"])


def test_preflight_finds_campaign_yaml_below_configured_active_root(tmp_path, monkeypatch):
    import research.preflight as preflight

    data = tmp_path / "bars.csv"
    campaign_root = tmp_path / "research/campaigns/active/es_active"
    config = campaign_root / "variants/v01/config.yaml"
    _write_csv(data)
    _write_campaign_yaml(campaign_root, variant_count=9)
    _write_config(config, _config(data, campaign_id="es_active", variant_id="v01"))
    monkeypatch.setattr(preflight, "PROJECT_ROOT", tmp_path)

    result = run_preflight(config_paths=[config], run_tests=False)

    assert not result["passed"]
    assert any("campaign variant cap is 5" in failure for failure in result["failures"])
    assert not any("campaign.yaml is absent" in warning for warning in result["warnings"])


def test_preflight_rejects_six_variants_even_with_a_rationale(tmp_path):
    data = tmp_path / "bars.csv"
    campaign_root = tmp_path / "campaigns" / "es_active"
    config = campaign_root / "variants" / "v01" / "config.yaml"
    _write_csv(data)
    _write_campaign_yaml(campaign_root, variant_count=6)
    _write_config(config, _config(data, campaign_id="es_active", variant_id="v01"))

    result = run_preflight(config_paths=[config], run_tests=False)

    assert not result["passed"]
    assert any("campaign variant cap is 5" in failure for failure in result["failures"])


def test_preflight_accepts_five_legacy_variants(tmp_path):
    data = tmp_path / "bars.csv"
    campaign_root = tmp_path / "campaigns" / "es_active"
    config = campaign_root / "variants" / "v01" / "config.yaml"
    _write_csv(data)
    _write_campaign_yaml(
        campaign_root,
        variant_count=5,
        expansion_rationale=(
            "This legacy campaign records five predeclared mechanics and remains readable while all new "
            "governance-v3 campaigns use the sequential one-at-a-time workflow."
        ),
    )
    _write_config(config, _config(data, campaign_id="es_active", variant_id="v01"))

    result = run_preflight(config_paths=[config], run_tests=False)

    assert result["passed"]
    assert result["failures"] == []


def test_preflight_default_discovery_treats_archive_paths_as_inactive():
    assert _is_archived_path(Path("_archived/campaigns/foo/config.yaml"))
    assert _is_archived_path(Path("configs/campaigns/archive_not_benchmark_20260615/foo.yaml"))
    assert _is_archived_path(Path("data/reports/campaigns/archive_not_likely_20260614/foo/config.yaml"))
    assert not _is_archived_path(Path("campaigns/es_active/variants/baseline/config.yaml"))


def test_preflight_default_discovery_uses_authored_configs_only(tmp_path, monkeypatch):
    import research.preflight as preflight

    variant = tmp_path / "campaigns/es_active/variants/baseline/config.yaml"
    rescue = tmp_path / "campaigns/es_active/rescue_attempts/rescue1/baseline/config.yaml"
    follow_up = tmp_path / "campaigns/es_active/follow_up_attempts/replication1/baseline/config.yaml"
    generated = tmp_path / "backtest-campaigns/es_active/baseline/ES/run1/effective_config.yaml"
    archived = tmp_path / "_archived/campaigns/es_old/variants/baseline/config.yaml"
    for path in (variant, rescue, follow_up, generated, archived):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("campaign_id: test\n", encoding="utf-8")

    monkeypatch.setattr(preflight, "PROJECT_ROOT", tmp_path)

    default_paths = {path.relative_to(tmp_path) for path in _config_paths(None)}
    generated_paths = {
        path.relative_to(tmp_path) for path in _config_paths(None, include_generated_results=True)
    }

    assert default_paths == {
        Path("campaigns/es_active/variants/baseline/config.yaml"),
        Path("campaigns/es_active/rescue_attempts/rescue1/baseline/config.yaml"),
        Path("campaigns/es_active/follow_up_attempts/replication1/baseline/config.yaml"),
    }
    assert Path("backtest-campaigns/es_active/baseline/ES/run1/effective_config.yaml") in generated_paths
    assert Path("_archived/campaigns/es_old/variants/baseline/config.yaml") not in generated_paths


def test_preflight_default_discovery_uses_configured_active_root(tmp_path, monkeypatch):
    import research.preflight as preflight

    (tmp_path / "config").mkdir()
    (tmp_path / "config/storage_layout.yaml").write_text(
        yaml.safe_dump(
            {
                "schema": "alphaquest.storage-layout/v1",
                "active_campaign_root": "workspace/open",
                "archive_campaign_roots": ["workspace/closed"],
                "evidence_roots": ["workspace/evidence"],
                "research_artifact_root": "artifacts",
                "catalog_root": "catalogs",
                "views_root": "views",
                "run_store_root": "run-store",
            }
        ),
        encoding="utf-8",
    )
    configured = tmp_path / "workspace/open/live_edge/variants/v01/config.yaml"
    configured.parent.mkdir(parents=True)
    configured.write_text("campaign_id: live_edge\n", encoding="utf-8")
    monkeypatch.setattr(preflight, "PROJECT_ROOT", tmp_path)

    assert _config_paths(None) == [configured]


def test_preflight_explicit_project_root_controls_layout_and_relative_data_paths(tmp_path):
    (tmp_path / "config").mkdir()
    (tmp_path / "config/storage_layout.yaml").write_text(
        yaml.safe_dump(
            {
                "schema": "alphaquest.storage-layout/v1",
                "active_campaign_root": "workspace/open",
                "archive_campaign_roots": ["workspace/closed"],
                "evidence_roots": ["workspace/evidence"],
                "research_artifact_root": "artifacts",
                "catalog_root": "catalogs",
                "views_root": "views",
                "run_store_root": "run-store",
            }
        ),
        encoding="utf-8",
    )
    data = tmp_path / "research/datasets/bars.csv"
    data.parent.mkdir(parents=True)
    _write_csv(data)
    campaign = tmp_path / "workspace/open/fresh_root_edge"
    config = campaign / "variants/v01/config.yaml"
    _write_campaign_yaml(campaign, variant_count=1)
    cfg = _config("research/datasets/bars.csv", campaign_id="fresh_root_edge", variant_id="v01")
    _write_config(config, cfg)

    result = run_preflight(
        config_paths=["workspace/open/fresh_root_edge/variants/v01/config.yaml"],
        project_root=tmp_path,
        run_tests=False,
    )

    assert result["passed"]
    assert result["configs_checked"] == ["workspace/open/fresh_root_edge/variants/v01/config.yaml"]
    assert _config_paths(None, project_root=tmp_path) == [config]


def test_preflight_explicit_project_root_finds_campaign_governance_in_custom_active_root(tmp_path):
    (tmp_path / "config").mkdir()
    (tmp_path / "config/storage_layout.yaml").write_text(
        yaml.safe_dump(
            {
                "schema": "alphaquest.storage-layout/v1",
                "active_campaign_root": "custom/active",
                "archive_campaign_roots": ["custom/archive"],
                "evidence_roots": ["custom/evidence"],
                "research_artifact_root": "artifacts",
                "catalog_root": "catalogs",
                "views_root": "views",
                "run_store_root": "run-store",
            }
        ),
        encoding="utf-8",
    )
    data = tmp_path / "bars.csv"
    _write_csv(data)
    campaign = tmp_path / "custom/active/too_many"
    config = campaign / "variants/v01/config.yaml"
    _write_campaign_yaml(campaign, variant_count=9)
    _write_config(config, _config(data, campaign_id="too_many", variant_id="v01"))

    result = run_preflight(config_paths=[config], project_root=tmp_path, run_tests=False)

    assert not result["passed"]
    assert any("campaign variant cap is 5" in failure for failure in result["failures"])
    assert not any("campaign.yaml is absent" in warning for warning in result["warnings"])


def test_preflight_rejects_missing_timezone(tmp_path):
    data = tmp_path / "bars.csv"
    config = tmp_path / "config.yaml"
    _write_csv(data)
    cfg = _config(data)
    cfg["data"].pop("timezone")
    _write_config(config, cfg)

    result = run_preflight(config_paths=[config], run_tests=False)

    assert not result["passed"]
    assert any("timezone" in failure for failure in result["failures"])


def test_preflight_rejects_duplicate_bars(tmp_path):
    data = tmp_path / "bars.csv"
    config = tmp_path / "config.yaml"
    _write_csv(data, duplicate=True)
    _write_config(config, _config(data))

    result = run_preflight(config_paths=[config], run_tests=False)

    assert not result["passed"]
    assert any("duplicate bar" in failure for failure in result["failures"])


def test_preflight_rejects_missing_forced_flatten_config(tmp_path):
    data = tmp_path / "bars.csv"
    config = tmp_path / "config.yaml"
    _write_csv(data)
    cfg = _config(data)
    cfg["apex_rules"].pop("force_flatten_time")
    _write_config(config, cfg)

    result = run_preflight(config_paths=[config], run_tests=False)

    assert not result["passed"]
    assert any("force_flatten_time" in failure for failure in result["failures"])


def test_preflight_rejects_unknown_strategy_module(tmp_path):
    data = tmp_path / "bars.csv"
    config = tmp_path / "config.yaml"
    _write_csv(data)
    cfg = _config(data)
    cfg["strategy"]["entry"]["module"] = "not_registered"
    _write_config(config, cfg)

    result = run_preflight(config_paths=[config], run_tests=False)

    assert not result["passed"]
    assert any("unknown strategy.entry.module" in failure for failure in result["failures"])


def test_preflight_rejects_methodology_parameter_cap_violations(tmp_path):
    data = tmp_path / "bars.csv"
    config = tmp_path / "config.yaml"
    _write_csv(data)
    cfg = _config(data)
    cfg["core_grid"] = {
        "parameters": {
            "entry.params.a": [1, 2],
            "entry.params.b": [1, 2],
            "entry.params.c": [1, 2],
            "sl.params.stop_pct": [0.002, 0.003],
            "tp.params.target_r_multiple": [1.0, 2.0],
        }
    }
    _write_config(config, cfg)

    result = run_preflight(config_paths=[config], run_tests=False)

    assert not result["passed"]
    assert any("exceeds methodology tunable count" in failure for failure in result["failures"])


def test_preflight_rejects_parameter_combination_cap(tmp_path):
    data = tmp_path / "bars.csv"
    config = tmp_path / "config.yaml"
    _write_csv(data)
    cfg = _config(data)
    cfg["core_grid"] = {
        "parameters": {
            "entry.params.a": list(range(11)),
            "entry.params.b": list(range(11)),
            "sl.params.stop_pct": [0.002, 0.003],
        }
    }
    _write_config(config, cfg)

    result = run_preflight(config_paths=[config], run_tests=False)

    assert not result["passed"]
    assert any("methodology cap is 120" in failure for failure in result["failures"])


def test_preflight_rejects_target_r_multiple_below_one(tmp_path):
    data = tmp_path / "bars.csv"
    config = tmp_path / "config.yaml"
    _write_csv(data)
    cfg = _config(data)
    cfg["strategy"]["tp"]["params"]["target_r_multiple"] = 0.75
    cfg["core_grid"] = {
        "parameters": {
            "sl.params.stop_pct": [0.01],
            "tp.params.target_r_multiple": [0.75, 1.0],
        }
    }
    _write_config(config, cfg)

    result = run_preflight(config_paths=[config], run_tests=False)

    assert not result["passed"]
    assert any("minimum allowed reward:risk" in failure for failure in result["failures"])


def test_preflight_rejects_unsupported_continuous_contract_rule(tmp_path):
    data = tmp_path / "bars.csv"
    config = tmp_path / "config.yaml"
    _write_csv(data)
    cfg = _config(data)
    cfg["data"]["continuous_contract"] = "explicit_roll"
    _write_config(config, cfg)

    result = run_preflight(config_paths=[config], run_tests=False)

    assert not result["passed"]
    assert any("data.continuous_contract=explicit_roll is unsupported" in failure for failure in result["failures"])


def test_preflight_rejects_required_mechanics_review_without_approval(tmp_path):
    data = tmp_path / "bars.csv"
    config = tmp_path / "config.yaml"
    _write_csv(data)
    cfg = _config(data)
    cfg["research_metadata"]["mechanics_review"] = {
        "mechanic_expresses_edge": "too short",
        "pre_test_decision": "needs_work",
    }
    _write_config(config, cfg)

    result = run_preflight(config_paths=[config], run_tests=False)

    assert not result["passed"]
    assert any("mechanics_review.entry_logic_rationale" in failure for failure in result["failures"])
    assert any("pre_test_decision" in failure for failure in result["failures"])


def test_preflight_cli_runs_from_repo_root_with_explicit_config(tmp_path):
    data = tmp_path / "bars.csv"
    config = tmp_path / "config.yaml"
    _write_csv(data)
    _write_config(config, _config(data))

    proc = subprocess.run(
        [sys.executable, "-m", "research.preflight", "--config", str(config), "--skip-tests"],
        text=True,
        capture_output=True,
    )

    assert proc.returncode == 0
    assert "Preflight PASS" in proc.stdout


def test_preflight_cli_groups_repeated_warnings_by_default(tmp_path):
    data = tmp_path / "bars.csv"
    one = tmp_path / "one.yaml"
    two = tmp_path / "two.yaml"
    _write_csv(data)
    for path in (one, two):
        cfg = _config(data)
        cfg["research_metadata"]["mechanics_review_required"] = False
        cfg["research_metadata"].pop("mechanics_review_version", None)
        _write_config(path, cfg)

    proc = subprocess.run(
        [
            sys.executable,
            "-m",
            "research.preflight",
            "--config",
            str(one),
            "--config",
            str(two),
            "--skip-tests",
        ],
        text=True,
        capture_output=True,
    )

    assert proc.returncode == 0
    assert "WARNING x2:" in proc.stdout
