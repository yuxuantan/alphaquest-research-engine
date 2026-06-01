from __future__ import annotations

from pathlib import Path
import json
import shutil
from datetime import datetime
import math

import pandas as pd
import yaml

from propstack.utils.hashing import file_sha256, object_sha256


def load_yaml(path: str | Path) -> dict:
    with open(path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def write_json(path: str | Path, data: dict) -> None:
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(_json_safe(data), f, indent=2, default=str, allow_nan=False)


def _json_safe(value):
    if isinstance(value, float) and not math.isfinite(value):
        return None
    if isinstance(value, dict):
        return {k: _json_safe(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_json_safe(v) for v in value]
    return value


def create_run_dir(
    run_type: str,
    config_path: str | Path | None = None,
    config: dict | None = None,
) -> Path:
    root = campaign_root(config)
    out = root / run_type
    out.mkdir(parents=True, exist_ok=True)
    (out / "warnings.txt").write_text("", encoding="utf-8")
    if config_path:
        src = Path(config_path)
        dst = root / "campaign_config.yaml"
        if src.resolve() != dst.resolve():
            shutil.copy2(src, dst)
        step_dst = out / "config_snapshot.yaml"
        if src.resolve() != step_dst.resolve():
            shutil.copy2(src, step_dst)
    manifest = {
        "campaign_id": _campaign_id(config),
        "strategy_name": _strategy_name(config),
        "symbol": _symbol(config),
        "dataset_id": _dataset_id(config),
        "raw_csv": _raw_csv(config),
        "config_source": str(config_path) if config_path else None,
        "config_hash": file_sha256(config_path) if config_path else object_sha256(config or {}),
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "layout": "strategy_symbol_dataset_campaign",
    }
    write_json(root / "run_manifest.json", manifest)
    return out


def campaign_root(config: dict | None) -> Path:
    return (
        Path("data")
        / "reports"
        / "strategies"
        / _strategy_name(config)
        / _symbol(config)
        / _dataset_id(config)
        / _campaign_id(config)
    )


def validation_dir(run_dir: str | Path) -> Path:
    out = Path(run_dir).parent / "validation"
    out.mkdir(parents=True, exist_ok=True)
    return out


def record_campaign_result(
    run_dir: str | Path,
    config: dict,
    config_path: str | Path,
    input_hash: str,
    section: str,
    summary: dict,
) -> None:
    root = Path(run_dir).parent
    (root / "input_data_hash.txt").write_text(input_hash, encoding="utf-8")
    (root / "config_hash.txt").write_text(file_sha256(config_path), encoding="utf-8")
    _update_manifest(root, config, config_path, input_hash)
    _update_campaign_summary(root, config, config_path, input_hash, section, summary)
    _update_runs_index(root)


def _update_manifest(root: Path, config: dict, config_path: str | Path, input_hash: str) -> None:
    manifest = {
        "campaign_id": _campaign_id(config),
        "strategy_name": _strategy_name(config),
        "symbol": _symbol(config),
        "dataset_id": _dataset_id(config),
        "raw_csv": _raw_csv(config),
        "config_source": str(config_path),
        "config_hash": file_sha256(config_path),
        "input_data_hash": input_hash,
        "updated_at": datetime.now().isoformat(timespec="seconds"),
        "layout": "strategy_symbol_dataset_campaign",
    }
    write_json(root / "run_manifest.json", manifest)


def _update_campaign_summary(
    root: Path,
    config: dict,
    config_path: str | Path,
    input_hash: str,
    section: str,
    summary: dict,
) -> None:
    path = root / "campaign_summary.json"
    if path.exists():
        existing = json.loads(path.read_text(encoding="utf-8"))
    else:
        existing = {}
    existing.update(
        {
            "campaign_id": _campaign_id(config),
            "strategy_name": _strategy_name(config),
            "symbol": _symbol(config),
            "dataset_id": _dataset_id(config),
            "raw_csv": _raw_csv(config),
            "config_source": str(config_path),
            "config_hash": file_sha256(config_path),
            "input_data_hash": input_hash,
            "updated_at": datetime.now().isoformat(timespec="seconds"),
        }
    )
    sections = existing.setdefault("sections", {})
    sections[section] = summary
    write_json(path, existing)


def _update_runs_index(root: Path) -> None:
    summary_path = root / "campaign_summary.json"
    if not summary_path.exists():
        return
    summary = json.loads(summary_path.read_text(encoding="utf-8"))
    sections = summary.get("sections", {})
    backtest = sections.get("backtest", {})
    grid = sections.get("grid", {})
    monkey = sections.get("monkey", {})
    wfa = sections.get("wfa", {})
    monte_carlo = sections.get("monte_carlo", {})
    row = {
        "campaign_id": summary.get("campaign_id"),
        "strategy_name": summary.get("strategy_name"),
        "symbol": summary.get("symbol"),
        "dataset_id": summary.get("dataset_id"),
        "raw_csv": summary.get("raw_csv"),
        "config_hash": summary.get("config_hash"),
        "input_data_hash": summary.get("input_data_hash"),
        "updated_at": summary.get("updated_at"),
        "total_trades": backtest.get("total_trades"),
        "trades_per_year": backtest.get("trades_per_year"),
        "net_profit": backtest.get("net_profit"),
        "profit_factor": backtest.get("profit_factor"),
        "max_drawdown_pct": backtest.get("max_drawdown_pct"),
        "cagr": backtest.get("cagr"),
        "mar": backtest.get("mar"),
        "win_rate": backtest.get("win_rate"),
        "grid_pass_rate": grid.get("percentage_passing_benchmark"),
        "monkey_pass_rate": monkey.get("percentage_passing_benchmark"),
        "wfa_profitable_window_rate": wfa.get("profitable_window_rate"),
        "monte_carlo_prop_pass_chance": monte_carlo.get("probability_profit_before_drawdown"),
    }
    index_path = root.parent / "runs_index.csv"
    if index_path.exists():
        index = pd.read_csv(index_path)
        index = index[index["campaign_id"] != row["campaign_id"]]
        index = pd.concat([index, pd.DataFrame([row])], ignore_index=True)
    else:
        index = pd.DataFrame([row])
    index = index.sort_values(["updated_at", "campaign_id"], na_position="last")
    index.to_csv(index_path, index=False)


def _campaign_id(config: dict | None) -> str:
    if config and config.get("campaign_id"):
        return str(config["campaign_id"])
    raise ValueError("Campaign config must define a non-empty campaign_id.")


def _strategy_name(config: dict | None) -> str:
    if not config:
        return "unknown_strategy"
    if config.get("strategy_name"):
        return str(config["strategy_name"])
    strategy = config.get("strategy") or {}
    if strategy.get("strategy_name"):
        return str(strategy["strategy_name"])
    return "unknown_strategy"


def _symbol(config: dict | None) -> str:
    if not config:
        return "UNKNOWN"
    data = config.get("data") or {}
    return str(data.get("symbol") or config.get("symbol") or "UNKNOWN")


def _dataset_id(config: dict | None) -> str:
    if not config:
        return "unknown_dataset"
    data = config.get("data") or {}
    dataset_id = config.get("dataset_id") or data.get("dataset_id")
    if dataset_id:
        return str(dataset_id)
    raise ValueError("Campaign config must define a non-empty dataset_id.")


def _raw_csv(config: dict | None) -> str | None:
    if not config:
        return None
    data = config.get("data") or {}
    raw_csv = data.get("raw_csv")
    return str(raw_csv) if raw_csv else None
