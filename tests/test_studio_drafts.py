from __future__ import annotations

import csv
import json
from pathlib import Path

import pandas as pd
import pytest
import yaml
from pydantic import ValidationError

from alphaquest.authoring import CampaignCompiler
from alphaquest.data.clean import clean_data
from alphaquest.data.pipeline import prepare_data
from alphaquest.studio.data_import import DataImportSpec, DatasetImporter
from alphaquest.studio.drafts import DraftStore
from alphaquest.studio.duplicates import duplicate_matches


def test_incomplete_draft_autosaves_outside_active_discovery(tmp_path: Path) -> None:
    store = DraftStore(tmp_path)
    path = store.save("es_new_edge", {"title": "A new edge"}, wizard_step=2)

    assert path == tmp_path / "research/drafts/es_new_edge/draft.json"
    assert not (tmp_path / "research/campaigns/active/es_new_edge").exists()
    assert store.list()[0]["wizard_step"] == 2
    report = store.validation_report("es_new_edge")
    assert report["valid"] is False
    assert report["errors"]


def test_frozen_draft_and_wizard_state_are_immutable(tmp_path: Path) -> None:
    store = DraftStore(tmp_path)
    frozen = {"campaign_id": "es_frozen", "title": "Frozen protocol", "frozen": True}
    path = store.save("es_frozen", frozen, wizard_step=7)
    document = json.loads(path.read_text(encoding="utf-8"))
    assert len(document["frozen_draft_sha256"]) == 64

    with pytest.raises(ValueError, match="immutable"):
        store.save("es_frozen", {**frozen, "title": "Changed after freeze"}, wizard_step=7)
    with pytest.raises(ValueError, match="immutable"):
        store.save_state("es_frozen", {"lane": "Certified recipe"})

    document["draft"]["title"] = "Hand-edited frozen protocol"
    path.write_text(json.dumps(document), encoding="utf-8")
    with pytest.raises(ValueError, match="integrity check failed"):
        store.validate("es_frozen")


def test_blocked_frozen_protocol_can_create_a_governed_editable_revision(tmp_path: Path) -> None:
    store = DraftStore(tmp_path)
    frozen = {
        "campaign_id": "es_frozen",
        "title": "Frozen protocol",
        "frozen": True,
        "confirmation_context_sha256": "a" * 64,
        "duplicate_review": {"conclusion": "distinct"},
        "variants": [{"variant_id": f"v{index:02d}", "confirmed": True} for index in range(1, 6)],
    }
    original_path = store.save("es_frozen", frozen, wizard_step=7)
    original_bytes = original_path.read_bytes()

    revised_path = store.create_revision(
        "es_frozen",
        "es_frozen_revision",
        reason="The governed dataset hash changed before publication and requires renewed review.",
    )

    revised = json.loads(revised_path.read_text(encoding="utf-8"))["draft"]
    assert revised["campaign_id"] == "es_frozen_revision"
    assert revised["frozen"] is False
    assert "duplicate_review" not in revised
    assert "confirmation_context_sha256" not in revised
    assert all(not variant["confirmed"] for variant in revised["variants"])
    assert original_path.read_bytes() == original_bytes
    state = store.load_state("es_frozen_revision")
    assert state["revision_of"] == "es_frozen"


def test_duplicate_review_scans_active_archive_and_ledger(tmp_path: Path) -> None:
    for lifecycle, campaign_id in (("active", "es_active_edge"), ("archive", "es_closed_edge")):
        folder = tmp_path / f"research/campaigns/{lifecycle}/{campaign_id}"
        folder.mkdir(parents=True)
        (folder / "campaign.yaml").write_text(
            yaml.safe_dump(
                {
                    "campaign_id": campaign_id,
                    "title": "Opening range continuation",
                    "hypothesis": "Opening range breakouts persist after high volume",
                    "expected_mechanism": "price discovery and delayed hedging",
                }
            ),
            encoding="utf-8",
        )
    ledger = tmp_path / "research_ledger.csv"
    with ledger.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=["campaign_id", "title", "verdict", "failure_reason"])
        writer.writeheader()
        writer.writerow(
            {
                "campaign_id": "es_ledger_only",
                "title": "Opening range continuation",
                "verdict": "FAIL",
                "failure_reason": "randomized entries were stronger",
            }
        )

    matches = duplicate_matches(
        project_root=tmp_path,
        campaign_id="es_new",
        title="Opening range continuation",
        hypothesis="Opening range breakouts persist",
        expected_mechanism="price discovery and delayed hedging",
    )

    assert {item["campaign_id"] for item in matches} >= {
        "es_active_edge",
        "es_closed_edge",
        "es_ledger_only",
    }


def test_duplicate_review_uses_real_ledger_edge_and_mechanic_columns(tmp_path: Path) -> None:
    ledger = tmp_path / "research_ledger.csv"
    with ledger.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=["campaign_id", "edge", "variant_mechanic", "parameter_space", "result"],
        )
        writer.writeheader()
        writer.writerow(
            {
                "campaign_id": "es_prior_auction_edge",
                "edge": "Opening range breakout continuation after price discovery",
                "variant_mechanic": "completed close beyond the frozen opening range",
                "parameter_space": "opening range minutes and confirmation minutes",
                "result": "FAIL",
            }
        )

    matches = duplicate_matches(
        project_root=tmp_path,
        campaign_id="es_new_auction_edge",
        title="Opening range breakout continuation",
        hypothesis="Completed closes beyond the opening range continue after price discovery",
        expected_mechanism="Delayed hedging after the opening auction",
    )

    match = next(item for item in matches if item["campaign_id"] == "es_prior_auction_edge")
    assert match["source"] == "ledger"
    assert match["verdict"] == "FAIL"
    assert match["similarity"] > 0


def test_data_import_records_quality_and_preserves_raw_attachment(tmp_path: Path) -> None:
    source = tmp_path / "input.csv"
    pd.DataFrame(
        {
            "when": ["2026-01-02 09:30:00", "2026-01-02 09:31:00"],
            "o": [6000.0, 6001.0],
            "h": [6002.0, 6003.0],
            "l": [5999.0, 6000.0],
            "c": [6001.0, 6002.0],
            "v": [100, 120],
            "untrusted_signal": [1, 2],
        }
    ).to_csv(source, index=False)
    importer = DatasetImporter(tmp_path)
    result = importer.import_file(
        source,
        DataImportSpec(
            dataset_id="es_fixture",
            symbol="ES",
            timeframe="1m",
            timezone="America/New_York",
            timestamp_semantics="bar_open",
            roll_policy="single_contract",
            timestamp_column="when",
            open_column="o",
            high_column="h",
            low_column="l",
            close_column="c",
            volume_column="v",
            single_contract_confirmed=True,
        ),
    )

    assert result.manifest.quality_verdict == "PASS"
    assert result.manifest.source == "csv"
    assert result.canonical_path.suffix == ".csv"
    assert result.manifest.path.endswith("bars.csv")
    assert result.quarantined_path.read_bytes() == source.read_bytes()
    assert result.canonical_path.is_file()
    written = json.loads(result.manifest_path.read_text(encoding="utf-8"))
    assert written["source_sha256"] == result.manifest.source_sha256
    assert written["certified_features"] == []
    assert "untrusted_signal" in " ".join(written["quality_notes"])


def test_invalid_data_is_disclosed_and_fails_closed(tmp_path: Path) -> None:
    source = tmp_path / "bad.csv"
    pd.DataFrame(
        {
            "timestamp": ["2026-01-02 09:30:00", "not-a-time"],
            "open": [10, 10],
            "high": [9, 11],
            "low": [8, 9],
            "close": [10, 10],
            "volume": [1, 1],
        }
    ).to_csv(source, index=False)
    result = DatasetImporter(tmp_path).import_file(
        source,
        DataImportSpec(
            dataset_id="bad_fixture",
            symbol="ES",
            timeframe="1m",
            timezone="America/New_York",
            timestamp_semantics="bar_open",
            roll_policy="single_contract",
            timestamp_column="timestamp",
            open_column="open",
            high_column="high",
            low_column="low",
            close_column="close",
            volume_column="volume",
            single_contract_confirmed=True,
        ),
    )

    assert result.manifest.quality_verdict == "FAIL"
    assert result.manifest.dropped_row_count == 1
    assert result.manifest.invalid_ohlc_count == 1
    assert len(pd.read_csv(result.quarantined_path)) == 2


def test_bar_close_source_is_normalized_to_canonical_bar_open(tmp_path: Path) -> None:
    source = tmp_path / "close_stamped.csv"
    pd.DataFrame(
        {
            "timestamp": ["2026-01-02 09:31:00", "2026-01-02 09:32:00"],
            "open": [10, 11],
            "high": [11, 12],
            "low": [9, 10],
            "close": [10.5, 11.5],
            "volume": [1, 1],
        }
    ).to_csv(source, index=False)
    result = DatasetImporter(tmp_path).import_file(
        source,
        DataImportSpec(
            dataset_id="close_stamped",
            symbol="ES",
            timeframe="1m",
            timezone="America/New_York",
            timestamp_semantics="bar_close",
            roll_policy="single_contract",
            timestamp_column="timestamp",
            open_column="open",
            high_column="high",
            low_column="low",
            close_column="close",
            volume_column="volume",
            single_contract_confirmed=True,
        ),
    )

    canonical = pd.read_csv(result.canonical_path)
    canonical["timestamp"] = pd.to_datetime(canonical["timestamp"])
    assert str(canonical.iloc[0]["timestamp"]) == "2026-01-02 14:30:00+00:00"
    assert result.manifest.source_timestamp_semantics == "bar_close"
    assert result.manifest.timestamp_semantics == "bar_open"
    assert "canonical bar-open" in " ".join(result.manifest.transformations)


def test_parquet_import_keeps_loader_format_in_sync(tmp_path: Path) -> None:
    source = tmp_path / "bars.parquet"
    pd.DataFrame(
        {
            "timestamp": ["2026-01-02 09:30:00", "2026-01-02 09:31:00"],
            "open": [10, 11],
            "high": [11, 12],
            "low": [9, 10],
            "close": [10.5, 11.5],
            "volume": [1, 1],
        }
    ).to_parquet(source, index=False)
    result = DatasetImporter(tmp_path).import_file(
        source,
        DataImportSpec(
            dataset_id="parquet_bars",
            symbol="ES",
            timeframe="1m",
            timezone="America/New_York",
            timestamp_semantics="bar_open",
            roll_policy="single_contract",
            timestamp_column="timestamp",
            open_column="open",
            high_column="high",
            low_column="low",
            close_column="close",
            volume_column="volume",
            single_contract_confirmed=True,
        ),
    )

    assert result.manifest.source == "parquet"
    assert result.canonical_path.suffix == ".parquet"
    assert result.manifest.path.endswith("bars.parquet")


def test_import_without_contract_lineage_needs_manual_review(tmp_path: Path) -> None:
    source = tmp_path / "ambiguous_roll.csv"
    pd.DataFrame(
        {
            "timestamp": ["2026-01-02 09:30:00"],
            "open": [10],
            "high": [11],
            "low": [9],
            "close": [10.5],
            "volume": [1],
        }
    ).to_csv(source, index=False)
    result = DatasetImporter(tmp_path).import_file(
        source,
        DataImportSpec(
            dataset_id="ambiguous_roll",
            symbol="ES",
            timeframe="1m",
            timezone="America/New_York",
            timestamp_semantics="bar_open",
            roll_policy="single_contract",
            timestamp_column="timestamp",
            open_column="open",
            high_column="high",
            low_column="low",
            close_column="close",
            volume_column="volume",
        ),
    )

    assert result.manifest.quality_verdict == "NEEDS MANUAL REVIEW"
    assert "lineage is unresolved" in " ".join(result.manifest.quality_notes)


def test_multi_contract_import_preserves_lineage_and_governed_roll_selection(
    tmp_path: Path,
) -> None:
    source = tmp_path / "multi_contract.csv"
    pd.DataFrame(
        {
            "when": [
                "2026-01-02 09:30:00",
                "2026-01-02 09:30:00",
                "2026-01-02 09:31:00",
                "2026-01-02 09:31:00",
            ],
            "o": [6000.0, 6001.0, 6000.5, 6001.5],
            "h": [6001.0, 6002.0, 6001.5, 6002.5],
            "l": [5999.0, 6000.0, 5999.5, 6000.5],
            "c": [6000.5, 6001.5, 6001.0, 6002.0],
            "v": [10, 100, 10, 100],
            "outright": ["ESH26", "ESM26", "ESH26", "ESM26"],
        }
    ).to_csv(source, index=False)
    roll_calendar = tmp_path / "roll_calendar.csv"
    pd.DataFrame(
        {
            "start_timestamp": ["2026-01-02 09:00:00"],
            "contract_symbol": ["ESM26"],
        }
    ).to_csv(roll_calendar, index=False)

    result = DatasetImporter(tmp_path).import_file(
        source,
        DataImportSpec(
            dataset_id="governed_multi_contract",
            symbol="ES",
            timeframe="1m",
            timezone="America/New_York",
            timestamp_semantics="bar_open",
            roll_policy="explicit_roll_calendar",
            roll_calendar_path=str(roll_calendar),
            timestamp_column="when",
            open_column="o",
            high_column="h",
            low_column="l",
            close_column="c",
            volume_column="v",
            contract_column="outright",
        ),
    )

    canonical = pd.read_csv(result.canonical_path)
    assert result.manifest.quality_verdict == "PASS"
    assert result.manifest.contract_column == "contract_symbol"
    assert result.manifest.source_contract_column == "outright"
    assert result.manifest.contract_count == 2
    assert result.manifest.continuous_contract == "explicit_roll_calendar"
    assert result.manifest.roll_calendar_sha256
    assert result.roll_calendar_path is not None and result.roll_calendar_path.is_file()
    assert canonical["contract_symbol"].tolist() == ["ESH26", "ESM26", "ESH26", "ESM26"]

    from tests.test_authoring_core import _draft_document, _reconfirm

    draft = _draft_document()
    draft["dataset"] = result.manifest.model_dump(mode="json", by_alias=True)
    _reconfirm(draft)
    compiled = CampaignCompiler().compile(draft)
    data_config = dict(compiled.variant_configs["v01"]["data"])
    assert data_config["continuous_contract"] == "explicit_roll_calendar"
    assert data_config["contract_column"] == "contract_symbol"
    data_config["roll_calendar"] = str(result.roll_calendar_path)
    data_config["raw_csv"] = str(result.canonical_path)
    cleaned, report, _missing = clean_data(data_config)
    assert report["duplicate_count"] == 0
    assert cleaned["contract_symbol"].unique().tolist() == ["ESM26"]
    assert len(cleaned) == 2


def test_import_and_compiler_reject_unsupported_or_ambiguous_multi_contract_rolls(
    tmp_path: Path,
) -> None:
    with pytest.raises(ValidationError, match="roll_policy"):
        DataImportSpec.model_validate(
            {
                "dataset_id": "unsafe_roll",
                "symbol": "ES",
                "timeframe": "1m",
                "timezone": "America/New_York",
                "timestamp_semantics": "bar_open",
                "roll_policy": "vendor_magic_stitch",
                "timestamp_column": "timestamp",
                "open_column": "open",
                "high_column": "high",
                "low_column": "low",
                "close_column": "close",
                "volume_column": "volume",
            }
        )

    from tests.test_authoring_core import _draft_document, _reconfirm

    unsafe = _draft_document()
    unsafe["dataset"].update(
        {
            "contract_column": "contract_symbol",
            "contract_count": 2,
            "continuous_contract": "none",
        }
    )
    with pytest.raises(ValueError, match="continuous-contract selection rule"):
        CampaignCompiler().compile(unsafe)

    future_volume = _draft_document()
    future_volume["dataset"].update(
        {
            "contract_column": "contract_symbol",
            "contract_count": 2,
            "continuous_contract": "dominant_session_volume",
        }
    )
    _reconfirm(future_volume)
    with pytest.raises(ValueError, match="session-final volume"):
        CampaignCompiler().compile(future_volume)


@pytest.mark.parametrize("bad_value", [0.0, -1.0, float("inf")])
def test_import_rejects_non_positive_or_non_finite_ohlcv(tmp_path: Path, bad_value: float) -> None:
    source = tmp_path / "invalid_numeric.csv"
    pd.DataFrame(
        {
            "timestamp": ["2026-01-02 09:30:00"],
            "open": [bad_value],
            "high": [10.0],
            "low": [9.0],
            "close": [9.5],
            "volume": [1.0],
        }
    ).to_csv(source, index=False)
    result = DatasetImporter(tmp_path).import_file(
        source,
        DataImportSpec(
            dataset_id="invalid_numeric",
            symbol="ES",
            timeframe="1m",
            timezone="America/New_York",
            timestamp_semantics="bar_open",
            roll_policy="single_contract",
            timestamp_column="timestamp",
            open_column="open",
            high_column="high",
            low_column="low",
            close_column="close",
            volume_column="volume",
            single_contract_confirmed=True,
        ),
    )
    assert result.manifest.quality_verdict == "FAIL"
    assert result.manifest.invalid_ohlc_count == 1


def test_import_rejects_ambiguous_numeric_timestamps(tmp_path: Path) -> None:
    source = tmp_path / "epoch.csv"
    pd.DataFrame(
        {
            "timestamp": [1_767_355_800, 1_767_355_860],
            "open": [10, 10],
            "high": [11, 11],
            "low": [9, 9],
            "close": [10, 10],
            "volume": [1, 1],
        }
    ).to_csv(source, index=False)
    with pytest.raises(ValueError, match="numeric timestamps are ambiguous"):
        DatasetImporter(tmp_path).import_file(
            source,
            DataImportSpec(
                dataset_id="epoch",
                symbol="ES",
                timeframe="1m",
                timezone="America/New_York",
                timestamp_semantics="bar_open",
                roll_policy="single_contract",
                timestamp_column="timestamp",
                open_column="open",
                high_column="high",
                low_column="low",
                close_column="close",
                volume_column="volume",
                single_contract_confirmed=True,
            ),
        )


def test_import_fails_overlapping_cadence_and_flags_long_missing_period(tmp_path: Path) -> None:
    overlap = tmp_path / "overlap.csv"
    pd.DataFrame(
        {
            "timestamp": ["2026-01-02 09:30:00", "2026-01-02 09:30:30"],
            "open": [10, 10],
            "high": [11, 11],
            "low": [9, 9],
            "close": [10, 10],
            "volume": [1, 1],
        }
    ).to_csv(overlap, index=False)
    common = {
        "symbol": "ES",
        "timeframe": "1m",
        "timezone": "America/New_York",
        "timestamp_semantics": "bar_open",
        "roll_policy": "single_contract",
        "timestamp_column": "timestamp",
        "open_column": "open",
        "high_column": "high",
        "low_column": "low",
        "close_column": "close",
        "volume_column": "volume",
        "single_contract_confirmed": True,
    }
    overlap_result = DatasetImporter(tmp_path).import_file(
        overlap,
        DataImportSpec(dataset_id="overlap", **common),
    )
    assert overlap_result.manifest.quality_verdict == "FAIL"
    assert overlap_result.manifest.cadence_violation_count >= 1

    outage = tmp_path / "outage.csv"
    pd.DataFrame(
        {
            "timestamp": ["2026-01-02 09:30:00", "2026-01-06 09:30:00"],
            "open": [10, 10],
            "high": [11, 11],
            "low": [9, 9],
            "close": [10, 10],
            "volume": [1, 1],
        }
    ).to_csv(outage, index=False)
    outage_result = DatasetImporter(tmp_path).import_file(
        outage,
        DataImportSpec(dataset_id="outage", **common),
    )
    assert outage_result.manifest.quality_verdict == "NEEDS MANUAL REVIEW"
    assert outage_result.manifest.gap_count >= 1


def test_native_five_minute_import_is_not_reaggregated(tmp_path: Path) -> None:
    source = tmp_path / "five_minute.csv"
    pd.DataFrame(
        {
            "timestamp": ["2026-01-02 09:30:00", "2026-01-02 09:35:00"],
            "open": [10, 11],
            "high": [11, 12],
            "low": [9, 10],
            "close": [10.5, 11.5],
            "volume": [100, 110],
        }
    ).to_csv(source, index=False)
    result = DatasetImporter(tmp_path).import_file(
        source,
        DataImportSpec(
            dataset_id="native_five",
            symbol="ES",
            timeframe="5m",
            timezone="America/New_York",
            timestamp_semantics="bar_open",
            roll_policy="single_contract",
            timestamp_column="timestamp",
            open_column="open",
            high_column="high",
            low_column="low",
            close_column="close",
            volume_column="volume",
            single_contract_confirmed=True,
        ),
    )
    canonical = pd.read_csv(result.canonical_path)
    assert canonical["timeframe_minutes"].unique().tolist() == [5.0]
    prepared, quality = prepare_data(
        {
            "source": "csv",
            "raw_csv": str(result.canonical_path),
            "source_timeframe": "5m",
            "symbol": "ES",
            "timezone": "America/New_York",
            "continuous_contract": "none",
            "rth_start": "09:30:00",
            "rth_end": "16:00:00",
        },
        timeframe="5m",
    )
    assert len(prepared) == 2
    assert quality["timeframe_minutes"] == 5
