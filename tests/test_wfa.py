import pandas as pd
import pytest

from propstack.data.clean import clean_data
from propstack.data.features import build_features
from propstack.research.wfa import create_windows, run_wfa
from propstack.research import wfa as wfa_module
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

    def fake_run_core_grid(
        data,
        base_config,
        grid_config,
        benchmarks,
        report_dir=None,
        parameter_label="core_grid.parameters",
        detail_data=None,
    ):
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

        def run(self, data, detail_data=None):
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
            "parallel": {"enabled": True, "workers": 3, "scope": "grid"},
            "parameters": wfa_params,
        },
        {"min_trade_count": 0, "max_drawdown": 99999},
    )

    assert summary["windows"] == 2
    assert len(results) == 2
    assert calls
    assert all(grid_config["parameters"] == wfa_params for grid_config, _ in calls)
    assert all(
        grid_config["parallel"] == {"enabled": True, "scope": "grid", "workers": 3}
        for grid_config, _ in calls
    )
    assert all(parameter_label == "wfa.parameters" for _, parameter_label in calls)
    assert all(
        config["strategy"]["entry"]["params"]["reclaim_window_bars"] == 7 for config in engine_configs
    )
    assert all(config["strategy"]["tp"]["params"]["target_r_multiple"] == 2.0 for config in engine_configs)


def test_wfa_can_return_stitched_oos_trade_log(monkeypatch):
    def fake_run_core_grid(
        data,
        base_config,
        grid_config,
        benchmarks,
        report_dir=None,
        parameter_label="core_grid.parameters",
        detail_data=None,
    ):
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

        def run(self, data, detail_data=None):
            ts = data["timestamp"].iloc[0]
            return {
                "metrics": {
                    "net_profit": 25.0,
                    "profit_factor": 1.5,
                    "max_drawdown": 5.0,
                    "total_trades": 1,
                },
                "trades": pd.DataFrame(
                    [
                        {
                            "trade_id": 1,
                            "session_date": pd.Timestamp(ts).date(),
                            "entry_timestamp": ts,
                            "exit_timestamp": ts + pd.Timedelta(minutes=5),
                            "contracts": 1,
                            "net_pnl": 25.0,
                        }
                    ]
                ),
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

    results, summary, trades = run_wfa(
        data,
        BASE_CFG,
        {
            "train_months": 1,
            "test_months": 1,
            "step_months": 1,
            "parameters": {"entry.params.reclaim_window_bars": [7]},
        },
        {"min_trade_count": 0, "max_drawdown": 99999},
        include_trade_log=True,
    )

    assert len(results) == 2
    assert summary["stitched_oos_trades"] == 2
    assert list(trades["trade_id"]) == [1, 2]
    assert list(trades["source_trade_id"]) == [1, 1]
    assert list(trades["wfa_window_id"]) == [1, 2]
    assert "wfa_selected_params" in trades.columns
    assert list(trades["net_pnl"]) == [25.0, 25.0]


def test_wfa_can_persist_window_train_grids(monkeypatch, tmp_path):
    def fake_run_core_grid(
        data,
        base_config,
        grid_config,
        benchmarks,
        report_dir=None,
        parameter_label="core_grid.parameters",
        detail_data=None,
    ):
        return (
            pd.DataFrame(
                [
                    {
                        "run_id": 1,
                        "entry.params.reclaim_window_bars": 2,
                        "net_profit": 200.0,
                        "profit_factor": 2.0,
                        "max_drawdown": 20.0,
                        "max_drawdown_pct": 0.08,
                        "cagr": 0.12,
                        "mar": 1.5,
                    },
                    {
                        "run_id": 2,
                        "entry.params.reclaim_window_bars": 7,
                        "net_profit": 100.0,
                        "profit_factor": 1.8,
                        "max_drawdown": 5.0,
                        "max_drawdown_pct": 0.02,
                        "cagr": 0.10,
                        "mar": 5.0,
                    },
                ]
            ),
            {},
        )

    class FakeBacktestEngine:
        def __init__(self, config):
            self.config = config

        def run(self, data, detail_data=None):
            return {
                "metrics": {
                    "net_profit": 25.0,
                    "profit_factor": 1.5,
                    "max_drawdown": 5.0,
                    "max_drawdown_pct": 0.01,
                    "cagr": 0.05,
                    "mar": 5.0,
                    "total_trades": 1,
                }
            }

    monkeypatch.setattr("propstack.research.wfa.run_core_grid", fake_run_core_grid)
    monkeypatch.setattr("propstack.research.wfa.BacktestEngine", FakeBacktestEngine)
    data = pd.DataFrame(
        {
            "timestamp": pd.to_datetime(
                ["2022-01-15", "2022-02-15"], utc=True
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
            "objective": "MAR",
            "parameters": {"entry.params.reclaim_window_bars": [2, 7]},
        },
        {"min_trade_count": 0, "max_drawdown": 99999},
        train_grid_dir=tmp_path,
    )

    grid_path = tmp_path / "window_001_train_grid.csv"
    saved = pd.read_csv(grid_path)

    assert len(results) == 1
    assert summary["train_grid_reports_retained"] is True
    assert summary["train_grid_report_files"] == [str(grid_path)]
    assert list(saved["wfa_selection_rank"]) == [1, 2]
    assert list(saved["wfa_selected"]) == [True, False]
    assert list(saved["entry.params.reclaim_window_bars"]) == [7, 2]
    assert saved.loc[0, "mar"] == 5.0


def test_wfa_progress_updates_at_start_and_after_each_window(monkeypatch):
    updates = []
    progress_kwargs = []

    class FakeProgress:
        def update(self, current, force=False, detail=None):
            updates.append((current, force))

    def fake_run_core_grid(
        data,
        base_config,
        grid_config,
        benchmarks,
        report_dir=None,
        parameter_label="core_grid.parameters",
        detail_data=None,
    ):
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
        def update(self, current, force=False, detail=None):
            return None

    def fake_run_core_grid(
        data,
        base_config,
        grid_config,
        benchmarks,
        report_dir=None,
        parameter_label="core_grid.parameters",
        detail_data=None,
    ):
        return (
            pd.DataFrame(
                [
                    {
                        "entry.params.reclaim_window_bars": 7,
                        "net_profit": 100.0,
                        "profit_factor": 2.0,
                        "max_drawdown": 10.0,
                        "max_drawdown_pct": 0.02,
                        "cagr": 0.12,
                        "mar": 6.0,
                    }
                ]
            ),
            {},
        )

    class FakeBacktestEngine:
        def __init__(self, config):
            self.config = config

        def run(self, data, detail_data=None):
            return {
                "metrics": {
                    "net_profit": 25.0,
                    "profit_factor": 1.5,
                    "max_drawdown": 5.0,
                    "max_drawdown_pct": 0.01,
                    "cagr": 0.05,
                    "mar": 5.0,
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
    assert "train_mar=6.00" in out
    assert "train_cagr=12.00%" in out
    assert "train_max_dd_pct=2.00%" in out
    assert "train_net_profit=100.00" in out
    assert "oos_mar=5.00" in out
    assert "oos_cagr=5.00%" in out
    assert "oos_max_dd_pct=1.00%" in out
    assert "oos_net_profit=25.00" in out


def test_wfa_mar_objective_selects_highest_in_sample_mar(monkeypatch):
    engine_configs = []

    def fake_run_core_grid(
        data,
        base_config,
        grid_config,
        benchmarks,
        report_dir=None,
        parameter_label="core_grid.parameters",
        detail_data=None,
    ):
        assert grid_config["objective"] == "mar"
        return (
            pd.DataFrame(
                [
                    {
                        "entry.params.reclaim_window_bars": 2,
                        "net_profit": 200.0,
                        "profit_factor": 2.0,
                        "max_drawdown": 20.0,
                        "max_drawdown_pct": 0.08,
                        "cagr": 0.12,
                        "mar": 1.5,
                    },
                    {
                        "entry.params.reclaim_window_bars": 7,
                        "net_profit": 100.0,
                        "profit_factor": 1.8,
                        "max_drawdown": 5.0,
                        "max_drawdown_pct": 0.02,
                        "cagr": 0.10,
                        "mar": 5.0,
                    },
                ]
            ),
            {},
        )

    class FakeBacktestEngine:
        def __init__(self, config):
            engine_configs.append(config)

        def run(self, data, detail_data=None):
            return {
                "metrics": {
                    "net_profit": 25.0,
                    "profit_factor": 1.5,
                    "max_drawdown": 5.0,
                    "max_drawdown_pct": 0.01,
                    "cagr": 0.05,
                    "mar": 5.0,
                    "total_trades": 1,
                }
            }

    monkeypatch.setattr("propstack.research.wfa.run_core_grid", fake_run_core_grid)
    monkeypatch.setattr("propstack.research.wfa.BacktestEngine", FakeBacktestEngine)
    data = pd.DataFrame(
        {
            "timestamp": pd.to_datetime(
                ["2022-01-15", "2022-02-15"], utc=True
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
            "objective": "MAR",
            "parameters": {"entry.params.reclaim_window_bars": [2, 7]},
        },
        {"min_trade_count": 0, "max_drawdown": 99999},
    )

    assert engine_configs[0]["strategy"]["entry"]["params"]["reclaim_window_bars"] == 7
    assert summary["objective"] == "MAR"
    assert results.loc[0, "objective"] == "MAR"
    assert results.loc[0, "train_objective"] == 5.0
    assert results.loc[0, "train_mar"] == 5.0
    assert results.loc[0, "train_cagr"] == 0.10
    assert results.loc[0, "train_max_drawdown_pct"] == 0.02
    assert results.loc[0, "train_net_profit"] == 100.0
    assert results.loc[0, "test_mar"] == 5.0
    assert results.loc[0, "test_cagr"] == 0.05
    assert results.loc[0, "test_max_drawdown_pct"] == 0.01


def test_wfa_profit_factor_objective_can_filter_by_trade_frequency():
    grid = pd.DataFrame(
        [
            {"run_id": 1, "profit_factor": 3.0, "trades_per_year": 10, "net_profit": 100.0},
            {"run_id": 2, "profit_factor": 2.0, "trades_per_year": 60, "net_profit": 80.0},
            {"run_id": 3, "profit_factor": 1.5, "trades_per_year": 70, "net_profit": 120.0},
        ]
    )

    best = wfa_module._select_best_in_sample(
        grid,
        "profit_factor",
        {"min_trades_per_year": 52},
    )

    assert best["run_id"] == 2


def test_wfa_can_early_exit_on_low_selected_train_profit_factor(monkeypatch):
    def fake_run_core_grid(
        data,
        base_config,
        grid_config,
        benchmarks,
        report_dir=None,
        parameter_label="core_grid.parameters",
        detail_data=None,
    ):
        return (
            pd.DataFrame(
                [
                    {
                        "entry.params.reclaim_window_bars": 7,
                        "net_profit": 100.0,
                        "profit_factor": 0.9,
                        "max_drawdown": 10.0,
                        "total_trades": 10,
                        "trades_per_year": 100.0,
                    }
                ]
            ),
            {},
        )

    monkeypatch.setattr("propstack.research.wfa.run_core_grid", fake_run_core_grid)
    data = pd.DataFrame(
        {
            "timestamp": pd.to_datetime(
                ["2022-01-15", "2022-02-15"], utc=True
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
            "objective": "profit_factor",
            "early_exit_min_train_profit_factor": 1.0,
            "parameters": {"entry.params.reclaim_window_bars": [7]},
        },
        {"min_trade_count": 0, "max_drawdown": 99999},
    )

    assert summary["early_exit"] is True
    assert bool(results.loc[0, "early_exit"]) is True


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


def test_wfa_rejects_unknown_objective():
    df, _, _ = clean_data(DATA_CFG)
    data = build_features(df, DATA_CFG)

    with pytest.raises(ValueError, match="wfa.objective"):
        run_wfa(
            data,
            BASE_CFG,
            {
                "train_months": 1,
                "test_months": 1,
                "step_months": 1,
                "objective": "sharpe",
                "parameters": {"entry.params.reclaim_window_bars": [2]},
            },
            {"min_trade_count": 0, "max_drawdown": 99999},
        )
