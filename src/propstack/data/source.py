from __future__ import annotations

from pathlib import Path

from propstack.data.load import infer_data_source, list_databento_dbn_files
from propstack.data.subset import load_bounds_with_warmup, subset_from_data_config
from propstack.utils.hashing import file_sha256, object_sha256


def data_source_hash(data_config: dict, subset_config: dict | None = None) -> str:
    subset_config = subset_config or subset_from_data_config(data_config)
    source = infer_data_source(data_config)
    if source == "csv":
        raw_csv = data_config.get("raw_csv")
        return file_sha256(raw_csv) if raw_csv else object_sha256({"source": source})
    if source == "parquet":
        raw_parquet = data_config.get("raw_parquet") or data_config.get("raw_csv")
        return file_sha256(raw_parquet) if raw_parquet else object_sha256({"source": source})
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
        return object_sha256(payload)
    raise ValueError(f"Unsupported data source: {source}")
