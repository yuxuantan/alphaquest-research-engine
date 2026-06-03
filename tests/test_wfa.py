import pandas as pd
import pytest

from propstack.data.clean import clean_data
from propstack.data.features import build_features
from propstack.research.wfa import create_windows, run_wfa
from tests.test_backtest_engine import BASE_CFG
from tests.test_data_pipeline import DATA_CFG


def test_wfa_train_test_split():
    df, _, _ = clean_data(DATA_CFG)
    data = build_features(df, DATA_CFG)
    windows = list(create_windows(data, 1, 1, 1))
    assert windows


def test_wfa_unanchored_windows_move_training_by_test_period():
    data = pd.DataFrame({"timestamp": pd.date_range("2007-01-01", "2013-12-01", freq="MS", tz="UTC")})

    windows = list(create_windows(data, train_months=48, test_months=12))

    assert windows[:3] == [
        (
            pd.Timestamp("2007-01-01"),
            pd.Timestamp("2011-01-01"),
            pd.Timestamp("2011-01-01"),
            pd.Timestamp("2012-01-01"),
        ),
        (
            pd.Timestamp("2008-01-01"),
            pd.Timestamp("2012-01-01"),
            pd.Timestamp("2012-01-01"),
            pd.Timestamp("2013-01-01"),
        ),
        (
            pd.Timestamp("2009-01-01"),
            pd.Timestamp("2013-01-01"),
            pd.Timestamp("2013-01-01"),
            pd.Timestamp("2014-01-01"),
        ),
    ]


def test_wfa_anchored_windows_expand_training_from_first_start():
    data = pd.DataFrame({"timestamp": pd.date_range("2007-01-01", "2013-12-01", freq="MS", tz="UTC")})

    windows = list(create_windows(data, train_months=48, test_months=12, mode="anchored"))

    assert windows[:3] == [
        (
            pd.Timestamp("2007-01-01"),
            pd.Timestamp("2011-01-01"),
            pd.Timestamp("2011-01-01"),
            pd.Timestamp("2012-01-01"),
        ),
        (
            pd.Timestamp("2007-01-01"),
            pd.Timestamp("2012-01-01"),
            pd.Timestamp("2012-01-01"),
            pd.Timestamp("2013-01-01"),
        ),
        (
            pd.Timestamp("2007-01-01"),
            pd.Timestamp("2013-01-01"),
            pd.Timestamp("2013-01-01"),
            pd.Timestamp("2014-01-01"),
        ),
    ]


def test_wfa_rejects_unknown_window_mode():
    data = pd.DataFrame({"timestamp": pd.date_range("2022-01-01", periods=3, freq="MS", tz="UTC")})

    with pytest.raises(ValueError, match="wfa.mode"):
        list(create_windows(data, train_months=1, test_months=1, mode="rolling"))


def test_wfa_runs():
    df, _, _ = clean_data(DATA_CFG)
    data = build_features(df, DATA_CFG)
    wfa_cfg = {
        "train_months": 1,
        "test_months": 1,
        "step_months": 1,
        "parameters": {
            "entry.params.reclaim_window_bars": [2, 3],
            "tp.params.target_r_multiple": [1.0],
        },
    }
    results, summary = run_wfa(
        data,
        BASE_CFG,
        wfa_cfg,
        {"min_trade_count": 0, "max_drawdown": 99999},
    )
    assert "windows" in summary


def test_wfa_uses_own_parameter_space(monkeypatch):
    calls = []
    engine_configs = []
    wfa_params = {
        "entry.params.reclaim_window_bars": [7],
        "tp.params.target_r_multiple": [2.0],
    }

    def fake_run_core_grid(data, base_config, grid_config, benchmarks, report_dir=None, parameter_label="core_grid.parameters"):
        calls.append((grid_config, parameter_label))
        return (
            pd.DataFrame(
                [
                    {
                        "entry.params.reclaim_window_bars": 7,
                        "tp.params.target_r_multiple": 2.0,
                        "net_profit": 100.0,
                        "profit_factor": 2.0,
                        "max_drawdown": 10.0,
                    }
                ]
            ),
            {},
        )

    class FakeBacktestEngine:
        def __init__(self, config):
            engine_configs.append(config)

        def run(self, data):
            return {
                "metrics": {
                    "net_profit": 25.0,
                    "profit_factor": 1.5,
                    "max_drawdown": 5.0,
                    "total_trades": 1,
                }
            }

    monkeypatch.setattr("propstack.research.wfa.run_core_grid", fake_run_core_grid)
    monkeypatch.setattr("propstack.research.wfa.BacktestEngine", FakeBacktestEngine)
    data = pd.DataFrame(
        {
            "timestamp": pd.to_datetime(
                ["2022-01-15", "2022-02-15", "2022-03-15"], utc=True
            )
        }
    )

    results, summary = run_wfa(
        data,
        BASE_CFG,
        {
            "train_months": 1,
            "test_months": 1,
            "step_months": 1,
            "parameters": wfa_params,
        },
        {"min_trade_count": 0, "max_drawdown": 99999},
    )

    assert summary["windows"] == 2
    assert len(results) == 2
    assert calls
    assert all(grid_config["parameters"] == wfa_params for grid_config, _ in calls)
    assert all(parameter_label == "wfa.parameters" for _, parameter_label in calls)
    assert all(
        config["strategy"]["entry"]["params"]["reclaim_window_bars"] == 7 for config in engine_configs
    )
    assert all(config["strategy"]["tp"]["params"]["target_r_multiple"] == 2.0 for config in engine_configs)


def test_wfa_progress_updates_at_start_and_after_each_window(monkeypatch):
    updates = []
    progress_kwargs = []

    class FakeProgress:
        def update(self, current, force=False):
            updates.append((current, force))

    def fake_run_core_grid(data, base_config, grid_config, benchmarks, report_dir=None, parameter_label="core_grid.parameters"):
        return pd.DataFrame(), {}

    def fake_progress_bar(total, label, **kwargs):
        progress_kwargs.append(kwargs)
        return FakeProgress()

    monkeypatch.setattr("propstack.research.wfa.progress_bar", fake_progress_bar)
    monkeypatch.setattr("propstack.research.wfa.run_core_grid", fake_run_core_grid)
    data = pd.DataFrame(
        {
            "timestamp": pd.to_datetime(
                ["2022-01-15", "2022-02-15", "2022-03-15"], utc=True
            )
        }
    )

    run_wfa(
        data,
        BASE_CFG,
        {
            "train_months": 1,
            "test_months": 1,
            "step_months": 1,
            "parameters": {"entry.params.reclaim_window_bars": [2]},
        },
        {"min_trade_count": 0, "max_drawdown": 99999},
    )

    assert updates == [(0, True), (1, True), (2, True)]
    assert progress_kwargs == [{"show_timing": True}]


def test_wfa_logs_current_window_details(monkeypatch, capsys):
    class FakeProgress:
        def update(self, current, force=False):
            return None

    def fake_run_core_grid(data, base_config, grid_config, benchmarks, report_dir=None, parameter_label="core_grid.parameters"):
        return (
            pd.DataFrame(
                [
                    {
                        "entry.params.reclaim_window_bars": 7,
                        "net_profit": 100.0,
                        "profit_factor": 2.0,
                        "max_drawdown": 10.0,
                    }
                ]
            ),
            {},
        )

    class FakeBacktestEngine:
        def __init__(self, config):
            self.config = config

        def run(self, data):
            return {
                "metrics": {
                    "net_profit": 25.0,
                    "profit_factor": 1.5,
                    "max_drawdown": 5.0,
                    "total_trades": 1,
                }
            }

    monkeypatch.setattr("propstack.research.wfa.progress_bar", lambda total, label, **kwargs: FakeProgress())
    monkeypatch.setattr("propstack.research.wfa.run_core_grid", fake_run_core_grid)
    monkeypatch.setattr("propstack.research.wfa.BacktestEngine", FakeBacktestEngine)
    data = pd.DataFrame(
        {
            "timestamp": pd.to_datetime(
                ["2022-01-15", "2022-02-15"], utc=True
            )
        }
    )

    run_wfa(
        data,
        BASE_CFG,
        {
            "train_months": 1,
            "test_months": 1,
            "step_months": 1,
            "parameters": {"entry.params.reclaim_window_bars": [7]},
        },
        {"min_trade_count": 0, "max_drawdown": 99999},
    )

    out = capsys.readouterr().out
    assert "walk-forward 1/1 start" in out
    assert "in-sample 2022-01-15 -> 2022-02-15" in out
    assert "out-of-sample 2022-02-15 -> 2022-03-15" in out
    assert "objective=net_profit train_objective=100.00" in out
    assert "selected_params=entry.params.reclaim_window_bars=7" in out
    assert "oos_net_profit=25.00" in out
    assert "oos_max_drawdown=5.00" in out


def test_wfa_requires_own_parameter_space():
    df, _, _ = clean_data(DATA_CFG)
    data = build_features(df, DATA_CFG)

    with pytest.raises(ValueError, match="wfa.parameters"):
        run_wfa(
            data,
            BASE_CFG,
            {"train_months": 1, "test_months": 1, "step_months": 1},
            {"min_trade_count": 0, "max_drawdown": 99999},
        )
