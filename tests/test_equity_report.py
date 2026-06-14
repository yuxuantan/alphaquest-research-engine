from __future__ import annotations

import json
import re

import pandas as pd

from propstack.backtest.equity_report import equity_curve_frame, write_equity_report
from propstack.run_equity_curves import _config_for_trade_log, _initial_balance, _trade_log_spec
from propstack.run_equity_curves import discover_trade_logs


def test_equity_curve_frame_orders_by_exit_timestamp_and_tracks_drawdown():
    trades = pd.DataFrame(
        [
            {
                "trade_id": 2,
                "entry_timestamp": pd.Timestamp("2024-01-02 09:30", tz="America/New_York"),
                "exit_timestamp": pd.Timestamp("2024-01-02 10:00", tz="America/New_York"),
                "net_pnl": -50.0,
            },
            {
                "trade_id": 1,
                "entry_timestamp": pd.Timestamp("2024-01-01 09:30", tz="America/New_York"),
                "exit_timestamp": pd.Timestamp("2024-01-01 10:00", tz="America/New_York"),
                "net_pnl": 100.0,
            },
        ]
    )

    curve = equity_curve_frame(trades, initial_balance=1000.0)

    assert curve["point"].tolist() == [0, 1, 2]
    assert curve["trade_id"].tolist()[1:] == [1, 2]
    assert curve["equity"].tolist() == [1000.0, 1100.0, 1050.0]
    assert curve["drawdown"].tolist() == [0.0, 0.0, 50.0]
    assert round(curve.loc[2, "drawdown_pct"], 8) == round(50.0 / 1100.0, 8)


def test_write_equity_report_supports_run_id_selector(tmp_path):
    trades = pd.DataFrame(
        [
            {
                "run_id": 2,
                "trade_id": 1,
                "entry_timestamp": pd.Timestamp("2024-01-02 09:30", tz="America/New_York"),
                "exit_timestamp": pd.Timestamp("2024-01-02 10:00", tz="America/New_York"),
                "net_pnl": -20.0,
            },
            {
                "run_id": 1,
                "trade_id": 1,
                "entry_timestamp": pd.Timestamp("2024-01-01 09:30", tz="America/New_York"),
                "exit_timestamp": pd.Timestamp("2024-01-01 10:00", tz="America/New_York"),
                "net_pnl": 40.0,
            },
        ]
    )

    report = write_equity_report(
        trades,
        tmp_path,
        initial_balance=500.0,
        timezone="America/New_York",
        title="Test equity curves",
        run_column="run_id",
    )

    curve = pd.read_csv(tmp_path / "equity_curve.csv")
    html = (tmp_path / "equity_curve.html").read_text(encoding="utf-8")

    assert report["equity_curve_points"] == 4
    assert curve["run_id"].tolist() == [1, 1, 2, 2]
    assert curve["equity"].tolist() == [500.0, 540.0, 500.0, 480.0]
    assert "Run 1" in html
    assert "Run 2" in html
    assert "equity-data" in html
    assert "Net liq" in html
    assert "Curr DD" in html
    assert "Win Rate" in html
    assert "PF" in html
    assert "MAR" in html

    payload_match = re.search(
        r'<script id="equity-data" type="application/json">(.*?)</script>',
        html,
    )
    assert payload_match is not None
    payload = json.loads(payload_match.group(1))
    run_one = next(run for run in payload["runs"] if run["id"] == "1")
    run_two = next(run for run in payload["runs"] if run["id"] == "2")
    assert run_one["summary"]["winRate"] == 1.0
    assert run_one["summary"]["profitFactor"] == "Infinity"
    assert run_two["points"][1]["drawdownPct"] == 0.04
    assert run_two["summary"]["winRate"] == 0.0
    assert run_two["summary"]["profitFactor"] == 0.0
    assert "mar" in run_two["summary"]


def test_discover_trade_logs_finds_supported_report_files(tmp_path):
    core = tmp_path / "campaign" / "variant" / "core"
    grid = tmp_path / "campaign" / "variant" / "core_grid"
    core.mkdir(parents=True)
    grid.mkdir(parents=True)
    (core / "trade_log.csv").write_text("trade_id,net_pnl\n", encoding="utf-8")
    (grid / "core_grid_iteration_trades.csv").write_text("run_id,trade_id,net_pnl\n", encoding="utf-8")
    (grid / "ignored.csv").write_text("x\n", encoding="utf-8")

    names = [path.name for path in discover_trade_logs(tmp_path)]

    assert names == ["trade_log.csv", "core_grid_iteration_trades.csv"]


def test_trade_log_config_lookup_finds_parent_campaign_test_snapshot(tmp_path):
    campaign_tests = tmp_path / "campaign_tests"
    stage = campaign_tests / "simulated_incubation_core"
    stage.mkdir(parents=True)
    (campaign_tests / "config_snapshot.yaml").write_text(
        "\n".join(
            [
                "campaign_id: demo",
                "variant_id: staged",
                "core:",
                "  initial_balance: 150000",
            ]
        ),
        encoding="utf-8",
    )
    trade_log = stage / "trade_log.csv"
    trade_log.write_text("trade_id,net_pnl\n", encoding="utf-8")

    config = _config_for_trade_log(trade_log)
    spec = _trade_log_spec(trade_log)

    assert config["core"]["initial_balance"] == 150000
    assert _initial_balance(config, spec, None) == 150000.0
