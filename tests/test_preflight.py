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
    path.write_text(yaml.safe_dump(cfg, sort_keys=False), encoding="utf-8")


def test_preflight_accepts_valid_config_and_timezone_aware_data(tmp_path):
    data = tmp_path / "bars.csv"
    config = tmp_path / "config.yaml"
    _write_csv(data)
    _write_config(config, _config(data))

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
    generated = tmp_path / "backtest-campaigns/es_active/baseline/ES/run1/effective_config.yaml"
    archived = tmp_path / "_archived/campaigns/es_old/variants/baseline/config.yaml"
    for path in (variant, rescue, generated, archived):
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
    }
    assert Path("backtest-campaigns/es_active/baseline/ES/run1/effective_config.yaml") in generated_paths
    assert Path("_archived/campaigns/es_old/variants/baseline/config.yaml") not in generated_paths


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
