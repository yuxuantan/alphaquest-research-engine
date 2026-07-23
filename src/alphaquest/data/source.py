from __future__ import annotations

from pathlib import Path

from alphaquest.data.load import infer_data_source, list_databento_dbn_files
from alphaquest.data.subset import load_bounds_with_warmup, subset_from_data_config
from alphaquest.utils.hashing import file_sha256, object_sha256


def data_source_hash(data_config: dict, subset_config: dict | None = None) -> str:
    subset_config = subset_config or subset_from_data_config(data_config)
    source = infer_data_source(data_config)
    execution_config = data_config.get("execution_data")
    execution_payload = _execution_source_payload(execution_config, subset_config) if execution_config else None
    if source == "csv":
        raw_csv = data_config.get("raw_csv")
        roll_payload = _roll_source_payload(data_config)
        if not execution_payload and not roll_payload:
            return file_sha256(raw_csv) if raw_csv else object_sha256({"source": source})
        return object_sha256(
            {
                "source": source,
                "raw_csv_sha256": file_sha256(raw_csv) if raw_csv else "",
                "execution_data": execution_payload,
                "roll_selection": roll_payload,
            }
        )
    if source == "parquet":
        raw_parquet = data_config.get("raw_parquet") or data_config.get("raw_csv")
        roll_payload = _roll_source_payload(data_config)
        if not execution_payload and not roll_payload:
            return file_sha256(raw_parquet) if raw_parquet else object_sha256({"source": source})
        return object_sha256(
            {
                "source": source,
                "raw_parquet_sha256": file_sha256(raw_parquet) if raw_parquet else "",
                "execution_data": execution_payload,
                "roll_selection": roll_payload,
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


def _roll_source_payload(data_config: dict) -> dict:
    rule = str(data_config.get("continuous_contract") or "none").lower()
    if rule in {"", "none", "false"}:
        return {}
    calendar = data_config.get("roll_calendar")
    return {
        "continuous_contract": rule,
        "roll_calendar": _canonical_local_path(calendar),
        "roll_calendar_sha256": file_sha256(calendar) if calendar else "",
        "roll_boundary_policy": data_config.get("roll_boundary_policy", {}),
    }


def _execution_source_payload(execution_config: dict | None, subset_config: dict | None) -> dict:
    if not execution_config:
        return {}
    source = str(execution_config.get("source", "")).lower()
    if source in {"databento_zip_trades", "databento_trades_zip"}:
        archive = execution_config.get("archive")
        roll_calendar = execution_config.get("roll_calendar")
        manifest = execution_config.get(
            "contract_manifest",
            "data/reference/ES/event_quality/sierra_event_capabilities_0930_1100.csv",
        )
        return {
            "source": source,
            "price_path_semantics": "databento_trade_message_v1",
            "archive": _canonical_local_path(archive),
            "archive_sha256": file_sha256(archive) if archive else "",
            "roll_calendar": _canonical_local_path(roll_calendar),
            "roll_calendar_sha256": file_sha256(roll_calendar) if roll_calendar else "",
            "contract_manifest": _canonical_local_path(manifest),
            "contract_manifest_sha256": file_sha256(manifest) if manifest else "",
            "subset": subset_config or {},
            "rth_start": execution_config.get("rth_start"),
            "rth_end": execution_config.get("rth_end"),
            "overnight_start": execution_config.get("overnight_start"),
            "root_symbol": execution_config.get("root_symbol"),
            "reset_previous_levels_on_roll": bool(
                execution_config.get("reset_previous_levels_on_roll", True)
            ),
        }
    if source not in {"sierra_scid_records", "scid_records", "sierra_scid"}:
        return {"source": source}
    raw_dir = Path(execution_config.get("raw_dir", ""))
    roll_calendar = execution_config.get("roll_calendar")
    raw_manifest = execution_config.get("raw_manifest")
    session_levels = execution_config.get("session_levels")
    quality_manifest = execution_config.get(
        "quality_manifest",
        "data/reference/ES/event_quality/sierra_event_capabilities_0930_1100.csv",
    )
    concordance_report = execution_config.get("concordance_report")
    return {
        "source": source,
        "price_path_semantics": "sierra_unbundled_trade_event_v1",
        "raw_dir": _canonical_local_path(raw_dir),
        "raw_manifest": _canonical_local_path(raw_manifest),
        "raw_manifest_sha256": file_sha256(raw_manifest) if raw_manifest else "",
        "session_levels": _canonical_local_path(session_levels),
        "session_levels_sha256": file_sha256(session_levels) if session_levels else "",
        "subset": subset_config or {},
        "root_symbol": execution_config.get("root_symbol", execution_config.get("symbol", "")),
        "roll_calendar": _canonical_local_path(roll_calendar),
        "roll_calendar_sha256": file_sha256(roll_calendar) if roll_calendar else "",
        "quality_manifest": _canonical_local_path(quality_manifest),
        "quality_manifest_sha256": file_sha256(quality_manifest),
        "concordance_report": _canonical_local_path(concordance_report),
        "concordance_report_sha256": file_sha256(concordance_report) if concordance_report else "",
        "required_capability": execution_config.get("required_capability", "full_strategy_events"),
        "ineligible_session_policy": execution_config.get("ineligible_session_policy", "error"),
        "rth_start": execution_config.get("rth_start"),
        "rth_end": execution_config.get("rth_end"),
        "aggregation_ms": execution_config.get("aggregation_ms"),
    }


def _canonical_local_path(value: object) -> str:
    """Return one stable spelling for a local source path.

    Validation generation commonly sees authored project-relative paths while
    the promotion gate resolves those same paths before hashing.  Binding the
    hash to the canonical absolute spelling keeps both callers identical while
    the file digest still binds the source bytes.
    """

    if value is None or str(value) == "":
        return ""
    return str(Path(str(value)).expanduser().resolve(strict=False))
