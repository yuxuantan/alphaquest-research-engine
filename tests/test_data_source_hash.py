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
