from __future__ import annotations

from datetime import date, timedelta
import json
from pathlib import Path
import shutil
from typing import Any

import pandas as pd
import yaml

from alphaquest.backtest.engine import BacktestEngine


TUTORIAL_SCHEMA = "alphaquest.tutorial/v1"


def run_tutorial(
    *,
    output_root: str | Path = "examples/tutorial_campaign/generated",
    execute: bool = True,
) -> dict[str, Any]:
    root = Path(output_root)
    _reset_output(root)
    (root / ".generated_by_alphaquest").write_text("Synthetic tutorial output. Safe to delete.\n", encoding="utf-8")
    data = _tutorial_bars()
    data_path = root / "data" / "tutorial_es_1m.csv"
    data_path.parent.mkdir(parents=True)
    data.to_csv(data_path, index=False)

    configs = []
    for index in range(1, 6):
        config = _tutorial_config(index, data_path)
        config_path = root / "campaigns" / "tutorial_calendar_bias" / "variants" / f"v{index:02d}" / "config.yaml"
        config_path.parent.mkdir(parents=True)
        config_path.write_text(yaml.safe_dump(config, sort_keys=False, width=120), encoding="utf-8")
        configs.append(config_path)

    payload: dict[str, Any] = {
        "schema": TUTORIAL_SCHEMA,
        "status": "PASS",
        "purpose": "Synthetic onboarding only; not research evidence.",
        "research_verdict": "NEEDS MANUAL REVIEW",
        "data_path": str(data_path),
        "configs": [str(path) for path in configs],
        "executed": bool(execute),
    }
    if execute:
        config = yaml.safe_load(configs[0].read_text(encoding="utf-8"))
        engine_data = _engine_frame(data)
        result = BacktestEngine(config).run(engine_data)
        run_dir = root / "runs" / "v01"
        run_dir.mkdir(parents=True)
        result["trades"].to_csv(run_dir / "trade_log.csv", index=False)
        result["daily"].to_csv(run_dir / "daily_results.csv", index=False)
        (run_dir / "metrics.json").write_text(json.dumps(result["metrics"], indent=2, default=str), encoding="utf-8")
        payload.update(
            {
                "run_dir": str(run_dir),
                "total_trades": int(result["metrics"].get("total_trades") or 0),
                "net_profit": float(result["metrics"].get("net_profit") or 0.0),
                "apex_rule_violations": int(result["metrics"].get("apex_rule_violations") or 0),
            }
        )
        if payload["total_trades"] <= 0 or payload["apex_rule_violations"]:
            payload["status"] = "FAIL"
    (root / "tutorial_manifest.json").write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return payload


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


def _engine_frame(data: pd.DataFrame) -> pd.DataFrame:
    frame = data.copy()
    frame["timestamp"] = pd.to_datetime(frame["timestamp"])
    frame["session_date"] = frame["timestamp"].dt.date
    frame["session_label"] = "RTH"
    frame["is_rth"] = True
    return frame


def _tutorial_config(index: int, data_path: Path) -> dict[str, Any]:
    variant_id = f"v{index:02d}"
    return {
        "campaign_id": "tutorial_calendar_bias",
        "variant_id": variant_id,
        "strategy_name": f"tutorial_calendar_bias_{variant_id}",
        "symbol": "ES",
        "dataset_id": "synthetic_tutorial_es_1m",
        "timeframe": "1m",
        "data": {
            "dataset_id": "synthetic_tutorial_es_1m",
            "source": "csv",
            "raw_csv": str(data_path.resolve()),
            "symbol": "ES",
            "timezone": "America/New_York",
            "exchange_timezone": "America/New_York",
        },
        "core": {
            "initial_balance": 50000,
            "tick_size": 0.25,
            "point_value": 50.0,
            "tick_value": 12.5,
            "commission_per_contract": 2.5,
            "slippage_ticks": 1,
            "flatten_time": "10:25:00",
            "position_sizing": {"mode": "fixed_contracts", "contracts": 1},
            "daily_loss_limit": 2000,
            "daily_profit_stop": 1000000,
        },
        "apex_rules": {
            "enabled": True,
            "force_flatten_enabled": True,
            "force_flatten_time": "10:25:00",
            "latest_flat_time": "10:26:00",
            "latest_entry_time": "10:15:00",
            "no_overnight_positions": True,
            "reject_if_position_after_flatten_deadline": True,
            "reject_if_entry_after_latest_entry_time": True,
        },
        "strategy": {
            "entry": {
                "module": "calendar_session_bias",
                "params": {
                    "signal_time": f"09:{35 + index:02d}:00",
                    "bar_interval_minutes": 1,
                    "weekday_directions": {weekday: "long" for weekday in range(5)},
                    "max_trades_per_day": 1,
                },
            },
            "sl": {"module": "percent_from_entry", "params": {"stop_pct": 0.002}},
            "tp": {"module": "fixed_r", "params": {"target_r_multiple": 1.5}},
            "flatten_time": "10:25:00",
        },
    }


def _reset_output(path: Path) -> None:
    if path.exists():
        marker = path / ".generated_by_alphaquest"
        if any(path.iterdir()) and not marker.is_file():
            raise RuntimeError(f"refusing to replace non-tutorial directory: {path}")
        shutil.rmtree(path)
    path.mkdir(parents=True)
