from __future__ import annotations

from pathlib import Path

from propstack.data.load import infer_data_source, list_databento_dbn_files
from propstack.data.subset import load_bounds_with_warmup, subset_from_data_config
from propstack.utils.hashing import file_sha256, object_sha256


def data_source_hash(data_config: dict, subset_config: dict | None = None) -> str:
    subset_config = subset_config or subset_from_data_config(data_config)
    source = infer_data_source(data_config)
    execution_config = data_config.get("execution_data")
    execution_payload = _execution_source_payload(execution_config, subset_config) if execution_config else None
    if source == "csv":
        raw_csv = data_config.get("raw_csv")
        if not execution_payload:
            return file_sha256(raw_csv) if raw_csv else object_sha256({"source": source})
        return object_sha256(
            {
                "source": source,
                "raw_csv_sha256": file_sha256(raw_csv) if raw_csv else "",
                "execution_data": execution_payload,
            }
        )
    if source == "parquet":
        raw_parquet = data_config.get("raw_parquet") or data_config.get("raw_csv")
        if not execution_payload:
            return file_sha256(raw_parquet) if raw_parquet else object_sha256({"source": source})
        return object_sha256(
            {
                "source": source,
                "raw_parquet_sha256": file_sha256(raw_parquet) if raw_parquet else "",
                "execution_data": execution_payload,
            }
        )
    if source == "databento_dbn":
        load_bounds = load_bounds_with_warmup(subset_config, data_config)
        files = list_databento_dbn_files(data_config["raw_dir"], date_bounds=load_bounds)
        payload = {
            "source": source,
            "raw_dir": str(Path(data_config["raw_dir"])),
            "subset": subset_config or {},
            "load_bounds": load_bounds or {},
            "timezone": data_config.get("timezone"),
            "include_spreads": bool(data_config.get("include_spreads", False)),
            "continuous_contract": data_config.get("continuous_contract", "dominant_session_volume"),
            "roll_calendar": str(data_config.get("roll_calendar", "")),
            "roll_calendar_sha256": file_sha256(data_config["roll_calendar"])
            if data_config.get("roll_calendar")
            else "",
            "roll_boundary_policy": data_config.get("roll_boundary_policy", {}),
            "files": [
                {
                    "path": str(path),
                    "sha256": file_sha256(path),
                }
                for path in files
            ],
        }
        if execution_payload:
            payload["execution_data"] = execution_payload
        return object_sha256(payload)
    raise ValueError(f"Unsupported data source: {source}")


def _execution_source_payload(execution_config: dict | None, subset_config: dict | None) -> dict:
    if not execution_config:
        return {}
    source = str(execution_config.get("source", "")).lower()
    if source not in {"sierra_scid_records", "scid_records", "sierra_scid"}:
        return {"source": source}
    raw_dir = Path(execution_config.get("raw_dir", ""))
    roll_calendar = execution_config.get("roll_calendar")
    files = sorted(raw_dir.glob("*.parquet")) if raw_dir.exists() else []
    return {
        "source": source,
        "raw_dir": str(raw_dir),
        "subset": subset_config or {},
        "root_symbol": execution_config.get("root_symbol", execution_config.get("symbol", "")),
        "roll_calendar": str(roll_calendar or ""),
        "roll_calendar_sha256": file_sha256(roll_calendar) if roll_calendar else "",
        "files": [
            {
                "path": str(path),
                "size": path.stat().st_size,
                "mtime_ns": path.stat().st_mtime_ns,
            }
            for path in files
        ],
    }
