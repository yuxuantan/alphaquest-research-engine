from alphaquest.data.source import data_source_hash
from alphaquest.utils.hashing import file_sha256


def test_plain_parquet_source_hash_remains_file_hash(tmp_path):
    raw_parquet = tmp_path / "bars.parquet"
    raw_parquet.write_bytes(b"plain-bars")

    assert data_source_hash({"source": "parquet", "raw_parquet": str(raw_parquet)}, {}) == file_sha256(raw_parquet)


def test_execution_data_changes_parquet_source_hash(tmp_path):
    raw_parquet = tmp_path / "bars.parquet"
    raw_parquet.write_bytes(b"plain-bars")
    scid_dir = tmp_path / "scid"
    scid_dir.mkdir()
    scid_file = scid_dir / "ESM26.parquet"
    scid_file.write_bytes(b"scid-records")
    roll_calendar = tmp_path / "roll.csv"
    roll_calendar.write_text("contract_symbol,start_timestamp\nESM6,2026-03-12T22:00:00Z\n")

    plain_hash = data_source_hash({"source": "parquet", "raw_parquet": str(raw_parquet)}, {})
    execution_hash = data_source_hash(
        {
            "source": "parquet",
            "raw_parquet": str(raw_parquet),
            "execution_data": {
                "source": "sierra_scid_records",
                "raw_dir": str(scid_dir),
                "roll_calendar": str(roll_calendar),
                "root_symbol": "ES",
            },
        },
        {"start_date": "2026-05-01", "end_date": "2026-05-29"},
    )

    assert execution_hash != plain_hash


def test_explicit_roll_calendar_is_bound_into_bar_source_hash(tmp_path):
    bars = tmp_path / "bars.csv"
    bars.write_bytes(b"timestamp,open,high,low,close,volume\n")
    calendar = tmp_path / "roll.csv"
    calendar.write_text("start_timestamp,contract_symbol\n2026-01-01T00:00:00Z,ESH26\n")
    config = {
        "source": "csv",
        "raw_csv": str(bars),
        "continuous_contract": "explicit_roll_calendar",
        "roll_calendar": str(calendar),
    }

    before = data_source_hash(config, {})
    calendar.write_text("start_timestamp,contract_symbol\n2026-01-01T00:00:00Z,ESM26\n")

    assert data_source_hash(config, {}) != before


def test_databento_execution_hash_is_independent_of_relative_path_spelling(tmp_path, monkeypatch):
    bars = tmp_path / "bars.parquet"
    archive = tmp_path / "events.zip"
    calendar = tmp_path / "roll.csv"
    manifest = tmp_path / "contracts.csv"
    bars.write_bytes(b"bars")
    archive.write_bytes(b"events")
    calendar.write_bytes(b"roll")
    manifest.write_bytes(b"manifest")
    monkeypatch.chdir(tmp_path)
    relative = {
        "source": "parquet",
        "raw_parquet": "bars.parquet",
        "execution_data": {
            "source": "databento_zip_trades",
            "archive": "events.zip",
            "roll_calendar": "roll.csv",
            "contract_manifest": "contracts.csv",
            "root_symbol": "ES",
        },
    }
    absolute = {
        "source": "parquet",
        "raw_parquet": str(bars),
        "execution_data": {
            "source": "databento_zip_trades",
            "archive": str(archive),
            "roll_calendar": str(calendar),
            "contract_manifest": str(manifest),
            "root_symbol": "ES",
        },
    }

    assert data_source_hash(relative, {}) == data_source_hash(absolute, {})
