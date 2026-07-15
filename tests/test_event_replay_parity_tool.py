from __future__ import annotations

import json

import pandas as pd

from tools.compare_event_replay_parity import METRIC_FIELDS, compare_runs


def _write_run(path, *, net_pnl: float = 10.0, extra_trade_column: bool = False) -> None:
    core = path / "core"
    core.mkdir(parents=True)
    trades = pd.DataFrame(
        [
            {
                "trade_id": 1,
                "entry_timestamp": "2026-05-04T09:30:00-04:00",
                "net_pnl": net_pnl,
            }
        ]
    )
    if extra_trade_column:
        trades["engine_audit_field"] = "allowed"
    trades.to_csv(core / "trade_log.csv", index=False)
    pd.DataFrame([{"session_date": "2026-05-04", "trades": 1}]).to_csv(
        core / "session_audits.csv",
        index=False,
    )
    metrics = {field: 1.0 for field in METRIC_FIELDS}
    metrics["net_profit"] = net_pnl
    (core / "metrics.json").write_text(json.dumps(metrics))


def test_parity_tool_accepts_additive_candidate_audit_columns(tmp_path):
    baseline = tmp_path / "baseline"
    candidate = tmp_path / "candidate"
    _write_run(baseline)
    _write_run(candidate, extra_trade_column=True)

    report = compare_runs(baseline, candidate)

    assert report["status"] == "PASS"


def test_parity_tool_fails_on_result_change(tmp_path):
    baseline = tmp_path / "baseline"
    candidate = tmp_path / "candidate"
    _write_run(baseline)
    _write_run(candidate, net_pnl=9.0)

    report = compare_runs(baseline, candidate)

    assert report["status"] == "FAIL"
    assert "net_pnl" in report["artifacts"]["core/trade_log.csv"]["column_mismatches"]
    assert "net_profit" in report["metrics"]["mismatches"]
