from __future__ import annotations

from contextlib import contextmanager
from pathlib import Path
import json
import os
import shutil
from datetime import datetime
import math
import time

import pandas as pd
import yaml

from propstack.data.timeframe import canonical_timeframe, parse_timeframe_minutes
from propstack.research.policy import active_research_policy_metadata
from propstack.utils.hashing import file_sha256, object_sha256
from propstack.version import ENGINE_CONTRACT_VERSION


CAMPAIGN_REPORT_ROOT = Path("backtest-campaigns")
CAMPAIGN_METADATA_FILENAME = "campaign.yaml"
VARIANT_METADATA_FILENAME = "variant.yaml"
CAMPAIGN_VARIANTS_INDEX_FILENAME = "variants_index.yaml"
EFFECTIVE_CONFIG_FILENAME = "effective_config.yaml"
SOURCE_CONFIG_SNAPSHOT_FILENAME = "source_config.yaml"
LEGACY_CAMPAIGN_CONFIG_FILENAME = "config.yaml"
CAMPAIGN_CONFIG_FILENAME = EFFECTIVE_CONFIG_FILENAME
VARIANT_TEST_SUMMARY_FILENAME = "variant_test_summary.json"
LEGACY_VARIANT_SUMMARY_FILENAME = "variant_summary.json"
CONFIG_SNAPSHOT_FILENAMES = {
    EFFECTIVE_CONFIG_FILENAME,
    SOURCE_CONFIG_SNAPSHOT_FILENAME,
    LEGACY_CAMPAIGN_CONFIG_FILENAME,
    "variant_config.yaml",
    "config_snapshot.yaml",
}
DEFAULT_CAMPAIGN_TEST_RUN_ID = "run1"
RUN_ID_KEYS = ("test_run_id", "campaign_test_run_id", "run_name", "run_id")


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
    root = variant_root(config, config_path=config_path)
    validate_campaign_run_root(root, config, config_path=config_path)
    variant_metadata = ensure_variant_metadata(config, root_path=root)
    out = root / run_type
    out.mkdir(parents=True, exist_ok=True)
    (out / "warnings.txt").write_text("", encoding="utf-8")
    _write_campaign_config(root / CAMPAIGN_CONFIG_FILENAME, config, config_path)
    if config_path:
        src = Path(config_path)
        step_dst = out / "config_snapshot.yaml"
        if src.resolve() != step_dst.resolve():
            shutil.copy2(src, step_dst)
    manifest = {
        "campaign_id": _campaign_id(config),
        "variant_id": _variant_id(config),
        "test_run_id": campaign_test_run_id(config, config_path=config_path, root_path=root),
        "strategy_name": _strategy_name(config),
        "symbol": _symbol(config),
        "dataset_id": _dataset_id(config),
        "timeframe": config_timeframe(config),
        "data_source": _data_source(config),
        "raw_csv": _raw_csv(config),
        "raw_parquet": _raw_parquet(config),
        "raw_dir": _raw_dir(config),
        "config_source": str(config_path) if config_path else None,
        "config_hash": file_sha256(config_path) if config_path else object_sha256(config or {}),
        "campaign_metadata": campaign_metadata_info(config, root_path=root),
        "variant_metadata": variant_metadata,
        "research_policy": active_research_policy_metadata(),
        "engine_contract_version": ENGINE_CONTRACT_VERSION,
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "layout": "campaign_variant_symbol_run",
    }
    write_json(root / "run_manifest.json", manifest)
    return out


def variant_root(config: dict | None, config_path: str | Path | None = None) -> Path:
    _dataset_id(config)
    config_timeframe(config)
    return (
        CAMPAIGN_REPORT_ROOT
        / _campaign_id(config)
        / _variant_id(config)
        / _symbol(config)
        / campaign_test_run_id(config, config_path=config_path)
    )


def campaign_root(config: dict | None, root_path: str | Path | None = None) -> Path:
    root = _campaign_root_from_layout_path(root_path)
    return root if root is not None else CAMPAIGN_REPORT_ROOT / _campaign_id(config)


def campaign_metadata_path(config: dict | None, root_path: str | Path | None = None) -> Path:
    return campaign_root(config, root_path=root_path) / CAMPAIGN_METADATA_FILENAME


def campaign_metadata_info(config: dict | None, root_path: str | Path | None = None) -> dict | None:
    path = campaign_metadata_path(config, root_path=root_path)
    if not path.is_file():
        return None
    return {"path": str(path), "hash": file_sha256(path)}


def campaign_variant_root(config: dict | None, root_path: str | Path | None = None) -> Path:
    root = _campaign_variant_root_from_layout_path(root_path)
    return root if root is not None else campaign_root(config) / _variant_id(config)


def variant_metadata_path(config: dict | None, root_path: str | Path | None = None) -> Path:
    return campaign_variant_root(config, root_path=root_path) / VARIANT_METADATA_FILENAME


def variant_metadata_info(
    config: dict | None,
    root_path: str | Path | None = None,
    *,
    ensure: bool = False,
) -> dict | None:
    if ensure:
        return ensure_variant_metadata(config, root_path=root_path)
    path = variant_metadata_path(config, root_path=root_path)
    if not path.is_file():
        return None
    metadata = load_yaml(path)
    return {
        "path": str(path),
        "hash": file_sha256(path),
        "mechanic": metadata.get("mechanic") or {},
        "rescue_policy": metadata.get("rescue_policy") or {},
    }


def ensure_variant_metadata(config: dict | None, root_path: str | Path | None = None) -> dict | None:
    path = variant_metadata_path(config, root_path=root_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        validate_variant_metadata(config, root_path=root_path)
        metadata = load_yaml(path)
        if metadata.get("rescue_policy") != rescue_policy_scaffold():
            metadata["rescue_policy"] = rescue_policy_scaffold()
            path.write_text(
                yaml.safe_dump(metadata, sort_keys=False, default_flow_style=False),
                encoding="utf-8",
            )
    else:
        path.write_text(
            yaml.safe_dump(_variant_metadata_scaffold(config), sort_keys=False, default_flow_style=False),
            encoding="utf-8",
        )
    info = variant_metadata_info(config, root_path=root_path)
    if info:
        _update_variants_index(campaign_root(config, root_path=root_path), config, info)
    return info


def validate_variant_metadata(config: dict | None, root_path: str | Path | None = None) -> None:
    path = variant_metadata_path(config, root_path=root_path)
    if not path.is_file():
        return
    metadata = load_yaml(path)
    expected_ids = {
        "campaign_id": _campaign_id(config),
        "variant_id": _variant_id(config),
    }
    for key, expected in expected_ids.items():
        actual = metadata.get(key)
        if actual and str(actual) != expected:
            raise ValueError(f"{path} {key} {actual!r} does not match run config {expected!r}.")

    expected_mechanic = metadata.get("mechanic") or {}
    actual_mechanic = strategy_mechanic(config)
    for key in ("entry_module", "take_profit_module", "stop_loss_module"):
        expected = expected_mechanic.get(key)
        actual = actual_mechanic.get(key)
        if expected and str(expected) != str(actual or ""):
            raise ValueError(
                f"{path} mechanic.{key} {expected!r} does not match run config {actual!r}."
            )


def strategy_mechanic(config: dict | None) -> dict:
    strategy = (config or {}).get("strategy") or {}
    mechanic = {
        "entry_module": _module_name(strategy.get("entry")),
        "take_profit_module": _module_name(strategy.get("tp")),
        "stop_loss_module": _module_name(strategy.get("sl")),
    }
    if strategy.get("flatten_time") is not None:
        mechanic["flatten_time"] = str(strategy.get("flatten_time"))
    return mechanic


def validate_campaign_run_root(
    root: str | Path,
    config: dict | None,
    config_path: str | Path | None = None,
) -> Path:
    path = Path(root)
    rel = _campaign_report_relative_parts(path)
    if len(rel) != 4:
        raise ValueError(
            "Campaign run output must be "
            "backtest-campaigns/{campaign_id}/{variant_id}/{symbol}/{run_id}; "
            f"got {path}"
        )
    expected = {
        "campaign_id": _campaign_id(config),
        "variant_id": _variant_id(config),
        "symbol": _symbol(config),
    }
    actual = {"campaign_id": rel[0], "variant_id": rel[1], "symbol": rel[2]}
    mismatches = [key for key, value in expected.items() if actual[key] != value]
    if mismatches:
        details = ", ".join(f"{key}: expected {expected[key]}, got {actual[key]}" for key in mismatches)
        raise ValueError(f"Campaign run output path does not match config ({details}): {path}")

    run_id = rel[3]
    explicit_run_id = _explicit_campaign_test_run_id(config)
    if explicit_run_id and explicit_run_id != run_id:
        raise ValueError(
            f"Campaign run output path run id {run_id} does not match config test_run_id {explicit_run_id}: {path}"
        )
    source_run_id = _campaign_test_run_id_from_path(config_path)
    if source_run_id and source_run_id != run_id:
        raise ValueError(
            f"Campaign run output path run id {run_id} does not match source config folder {source_run_id}: {path}"
        )
    return path


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
    _update_variant_summary(root, config, config_path, input_hash, section, summary)
    _update_runs_index(root)


def _update_manifest(root: Path, config: dict, config_path: str | Path, input_hash: str) -> None:
    variant_metadata = ensure_variant_metadata(config, root_path=root)
    manifest = {
        "campaign_id": _campaign_id(config),
        "variant_id": _variant_id(config),
        "test_run_id": campaign_test_run_id(config, config_path=config_path, root_path=root),
        "strategy_name": _strategy_name(config),
        "symbol": _symbol(config),
        "dataset_id": _dataset_id(config),
        "timeframe": config_timeframe(config),
        "data_source": _data_source(config),
        "raw_csv": _raw_csv(config),
        "raw_parquet": _raw_parquet(config),
        "raw_dir": _raw_dir(config),
        "config_source": str(config_path),
        "config_hash": file_sha256(config_path),
        "input_data_hash": input_hash,
        "campaign_metadata": campaign_metadata_info(config, root_path=root),
        "variant_metadata": variant_metadata,
        "research_policy": active_research_policy_metadata(),
        "engine_contract_version": ENGINE_CONTRACT_VERSION,
        "updated_at": datetime.now().isoformat(timespec="seconds"),
        "layout": "campaign_variant_symbol_run",
    }
    write_json(root / "run_manifest.json", manifest)


def _update_variant_summary(
    root: Path,
    config: dict,
    config_path: str | Path,
    input_hash: str,
    section: str,
    summary: dict,
) -> None:
    path = root / VARIANT_TEST_SUMMARY_FILENAME
    legacy_path = root / LEGACY_VARIANT_SUMMARY_FILENAME
    if path.exists():
        existing = json.loads(path.read_text(encoding="utf-8"))
    elif legacy_path.exists():
        existing = json.loads(legacy_path.read_text(encoding="utf-8"))
    else:
        existing = {}
    existing.update(
        {
            "campaign_id": _campaign_id(config),
            "variant_id": _variant_id(config),
            "test_run_id": campaign_test_run_id(config, config_path=config_path, root_path=root),
            "strategy_name": _strategy_name(config),
            "symbol": _symbol(config),
            "dataset_id": _dataset_id(config),
            "timeframe": config_timeframe(config),
            "data_source": _data_source(config),
            "raw_csv": _raw_csv(config),
            "raw_parquet": _raw_parquet(config),
            "raw_dir": _raw_dir(config),
            "config_source": str(config_path),
            "config_hash": file_sha256(config_path),
            "input_data_hash": input_hash,
            "campaign_metadata": campaign_metadata_info(config, root_path=root),
            "variant_metadata": ensure_variant_metadata(config, root_path=root),
            "research_policy": active_research_policy_metadata(),
            "engine_contract_version": ENGINE_CONTRACT_VERSION,
            "updated_at": datetime.now().isoformat(timespec="seconds"),
        }
    )
    sections = existing.setdefault("sections", {})
    for legacy_section in ["backtest", "grid"]:
        sections.pop(legacy_section, None)
    sections[section] = summary
    write_json(path, existing)


def update_runs_index(root: str | Path) -> None:
    _update_runs_index(Path(root))


def _update_runs_index(root: Path) -> None:
    summary_path = root / VARIANT_TEST_SUMMARY_FILENAME
    if not summary_path.exists():
        summary_path = root / LEGACY_VARIANT_SUMMARY_FILENAME
    if not summary_path.exists():
        return
    summary = json.loads(summary_path.read_text(encoding="utf-8"))
    sections = summary.get("sections", {})
    core = sections.get("core", {})
    core_grid = sections.get("core_grid", {})
    monkey = sections.get("monkey", {})
    wfa = sections.get("wfa", {})
    monte_carlo = sections.get("monte_carlo", {})
    stages = summary.get("stages", [])
    row = {
        "campaign_id": summary.get("campaign_id"),
        "variant_id": summary.get("variant_id"),
        "test_run_id": summary.get("test_run_id") or root.name,
        "strategy_name": summary.get("strategy_name"),
        "symbol": summary.get("symbol"),
        "dataset_id": summary.get("dataset_id"),
        "timeframe": summary.get("timeframe"),
        "data_source": summary.get("data_source"),
        "raw_csv": summary.get("raw_csv"),
        "raw_parquet": summary.get("raw_parquet"),
        "raw_dir": summary.get("raw_dir"),
        "config_hash": summary.get("config_hash"),
        "input_data_hash": summary.get("input_data_hash"),
        "variant_metadata_path": (summary.get("variant_metadata") or {}).get("path"),
        "variant_metadata_hash": (summary.get("variant_metadata") or {}).get("hash"),
        "updated_at": summary.get("updated_at"),
        "passed": summary.get("passed"),
        "halted": summary.get("halted"),
        "failed_stage": _first_failed_stage(stages),
        "stage_count": len(stages),
        "total_trades": core.get("total_trades"),
        "trades_per_year": core.get("trades_per_year"),
        "net_profit": core.get("net_profit"),
        "profit_factor": core.get("profit_factor"),
        "max_drawdown_pct": core.get("max_drawdown_pct"),
        "cagr": core.get("cagr"),
        "mar": core.get("mar"),
        "win_rate": core.get("win_rate"),
        "core_grid_pass_rate": core_grid.get("percentage_passing_benchmark"),
        "core_grid_profitable_iteration_rate": core_grid.get("percentage_profitable_iterations"),
        "core_grid_meets_profitable_iteration_threshold": core_grid.get("meets_profitable_iteration_threshold"),
        "monkey_pass_rate": monkey.get("percentage_passing_benchmark"),
        "wfa_profitable_window_rate": wfa.get("profitable_window_rate"),
        "monte_carlo_prop_pass_chance": monte_carlo.get("probability_profit_before_drawdown"),
    }
    index_path = root.parent / "runs_index.csv"
    if index_path.exists():
        index = pd.read_csv(index_path)
        for legacy_column in ["grid_pass_rate"]:
            if legacy_column in index.columns:
                index = index.drop(columns=[legacy_column])
        if "timeframe" not in index.columns:
            index["timeframe"] = None
        if "test_run_id" not in index.columns:
            index["test_run_id"] = None
        index = index[
            ~(
                (index["variant_id"] == row["variant_id"])
                & (index["symbol"] == row["symbol"])
                & (index["test_run_id"] == row["test_run_id"])
            )
        ]
        index = pd.concat([index, pd.DataFrame([row])], ignore_index=True)
    else:
        index = pd.DataFrame([row])
    index = index.sort_values(["updated_at", "variant_id", "test_run_id"], na_position="last")
    index.to_csv(index_path, index=False)


def _write_campaign_config(path: Path, config: dict | None, config_path: str | Path | None = None) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if config_path:
        src = Path(config_path)
        try:
            same_file = src.resolve() == path.resolve()
        except FileNotFoundError:
            same_file = False
        if src.exists() and not same_file:
            shutil.copy2(src, path)
            return
    if config is not None:
        path.write_text(
            yaml.safe_dump(config, sort_keys=False, default_flow_style=False),
            encoding="utf-8",
        )


def campaign_test_run_id(
    config: dict | None,
    config_path: str | Path | None = None,
    root_path: str | Path | None = None,
) -> str:
    explicit = _explicit_campaign_test_run_id(config)
    if explicit:
        return explicit
    derived = _campaign_test_run_id_from_path(config_path)
    if derived:
        return derived
    root_derived = _campaign_test_run_id_from_root(root_path)
    return root_derived or DEFAULT_CAMPAIGN_TEST_RUN_ID


def _explicit_campaign_test_run_id(config: dict | None) -> str | None:
    if not config:
        return None
    for key in RUN_ID_KEYS:
        value = config.get(key)
        if value:
            return str(value)
    return None


def _campaign_test_run_id_from_path(config_path: str | Path | None) -> str | None:
    if config_path is None:
        return None
    path = Path(config_path)
    if path.name not in CONFIG_SNAPSHOT_FILENAMES:
        return None
    if CAMPAIGN_REPORT_ROOT.name not in path.parts:
        return None
    return path.parent.name or None


def _campaign_test_run_id_from_root(root_path: str | Path | None) -> str | None:
    if root_path is None:
        return None
    rel = _campaign_report_relative_parts(Path(root_path))
    return rel[3] if len(rel) == 4 else None


def _campaign_report_relative_parts(path: Path) -> tuple[str, ...]:
    parts = path.parts
    root_name = CAMPAIGN_REPORT_ROOT.name
    if root_name not in parts:
        return ()
    index = len(parts) - 1 - list(reversed(parts)).index(root_name)
    return tuple(parts[index + 1 :])


def _campaign_root_from_layout_path(root_path: str | Path | None) -> Path | None:
    if root_path is None:
        return None
    path = Path(root_path)
    parts = path.parts
    root_name = CAMPAIGN_REPORT_ROOT.name
    if root_name not in parts:
        return None
    index = len(parts) - 1 - list(reversed(parts)).index(root_name)
    if len(parts) <= index + 1:
        return None
    return Path(*parts[: index + 2])


def _campaign_variant_root_from_layout_path(root_path: str | Path | None) -> Path | None:
    if root_path is None:
        return None
    path = Path(root_path)
    parts = path.parts
    root_name = CAMPAIGN_REPORT_ROOT.name
    if root_name not in parts:
        return None
    index = len(parts) - 1 - list(reversed(parts)).index(root_name)
    if len(parts) <= index + 2:
        return None
    return Path(*parts[: index + 3])


def _variant_metadata_scaffold(config: dict | None) -> dict:
    return {
        "campaign_id": _campaign_id(config),
        "variant_id": _variant_id(config),
        "strategy_name": _strategy_name(config),
        "mechanic": strategy_mechanic(config),
        "rescue_policy": rescue_policy_scaffold(),
        "review_status": "scaffold",
    }


def rescue_policy_scaffold() -> dict:
    return {
        "rescue_scope": "failed_variant",
        "max_rescue_attempts_per_failed_variant": 1,
        "allowed": [
            "change fixed parameters inside existing strategy modules",
            "change tunable parameter space inside existing strategy modules",
        ],
        "forbidden": [
            "rescue the same failed variant more than once",
            "change entry module",
            "change take-profit module",
            "change stop-loss module",
            "change the economic edge thesis",
            "change stage criteria",
            "change data window",
            "change timeframe",
            "add or remove filters outside the existing strategy modules",
        ],
    }


def _update_variants_index(campaign_dir: Path, config: dict | None, variant_info: dict) -> None:
    index_path = campaign_dir / CAMPAIGN_VARIANTS_INDEX_FILENAME
    with _file_lock(index_path.with_suffix(index_path.suffix + ".lock")):
        if index_path.exists():
            index = load_yaml(index_path)
        else:
            index = {}
        variants = index.get("variants") if isinstance(index, dict) else None
        if not isinstance(variants, list):
            variants = []
        row = {
            "variant_id": _variant_id(config),
            "strategy_name": _strategy_name(config),
            "path": variant_info.get("path"),
            "hash": variant_info.get("hash"),
            "mechanic": variant_info.get("mechanic") or {},
        }
        normalized_variants = []
        for item in variants:
            if isinstance(item, dict):
                normalized_variants.append(item)
            elif item:
                normalized_variants.append({"variant_id": str(item)})
        variants = [
            item for item in normalized_variants if item.get("variant_id") != row["variant_id"]
        ]
        variants.append(row)
        variants = sorted(variants, key=lambda item: str(item.get("variant_id") or ""))
        payload = {"campaign_id": _campaign_id(config), "variants": variants}
        _atomic_write_text(index_path, yaml.safe_dump(payload, sort_keys=False, default_flow_style=False))


@contextmanager
def _file_lock(lock_path: Path, timeout_seconds: float = 30.0, poll_seconds: float = 0.05):
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    started = time.monotonic()
    fd = None
    while fd is None:
        try:
            fd = os.open(str(lock_path), os.O_CREAT | os.O_EXCL | os.O_RDWR)
        except FileExistsError:
            if time.monotonic() - started >= timeout_seconds:
                raise TimeoutError(f"Timed out waiting for lock: {lock_path}")
            time.sleep(poll_seconds)
    try:
        yield
    finally:
        os.close(fd)
        lock_path.unlink(missing_ok=True)


def _atomic_write_text(path: Path, text: str) -> None:
    tmp = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    tmp.write_text(text, encoding="utf-8")
    tmp.replace(path)


def _module_name(value: object) -> str | None:
    if isinstance(value, dict):
        module = value.get("module")
        return str(module) if module is not None else None
    return None


def _first_failed_stage(stages: list) -> str | None:
    for stage in stages:
        if isinstance(stage, dict) and stage.get("status") in {"failed", "error"}:
            return str(stage.get("stage") or "")
    return None


def _campaign_id(config: dict | None) -> str:
    if config and config.get("campaign_id"):
        return str(config["campaign_id"])
    raise ValueError("Campaign config must define a non-empty campaign_id.")


def _variant_id(config: dict | None) -> str:
    if config and config.get("variant_id"):
        return str(config["variant_id"])
    raise ValueError("Variant config must define a non-empty variant_id.")


def _strategy_name(config: dict | None) -> str:
    if not config:
        return "unknown_strategy"
    if config.get("strategy_name"):
        return str(config["strategy_name"])
    strategy = config.get("strategy") or {}
    if strategy.get("strategy_name"):
        return str(strategy["strategy_name"])
    if config.get("campaign_id"):
        return str(config["campaign_id"])
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


def config_timeframe(config: dict | None, required: bool = True) -> str | None:
    if not config:
        if required:
            raise ValueError("Campaign run config must define a non-empty timeframe.")
        return None
    data = config.get("data") or {}
    value = config.get("timeframe") or data.get("timeframe")
    if value:
        return canonical_timeframe(value)
    if required:
        raise ValueError("Campaign run config must define a non-empty timeframe.")
    return None


def config_timeframe_minutes(config: dict | None, required: bool = True) -> int | None:
    value = config_timeframe(config, required=required)
    return parse_timeframe_minutes(value) if value else None


def _raw_csv(config: dict | None) -> str | None:
    if not config:
        return None
    data = config.get("data") or {}
    raw_csv = data.get("raw_csv")
    return str(raw_csv) if raw_csv else None


def _raw_parquet(config: dict | None) -> str | None:
    if not config:
        return None
    data = config.get("data") or {}
    raw_parquet = data.get("raw_parquet")
    return str(raw_parquet) if raw_parquet else None


def _raw_dir(config: dict | None) -> str | None:
    if not config:
        return None
    data = config.get("data") or {}
    raw_dir = data.get("raw_dir")
    return str(raw_dir) if raw_dir else None


def _data_source(config: dict | None) -> str | None:
    if not config:
        return None
    data = config.get("data") or {}
    if data.get("source"):
        return str(data["source"])
    if data.get("raw_dir"):
        return "databento_dbn"
    if data.get("raw_parquet"):
        return "parquet"
    if data.get("raw_csv"):
        return "csv"
    return None
