from pathlib import Path
import os

import pandas as pd

from alphaquest.data.clean import apply_continuous_contract, apply_roll_boundary_policy, load_roll_calendar
from alphaquest.data.load import _read_cached_dbn_file, list_databento_dbn_files, parse_dbn_file_dates


def test_databento_file_dates_parse_monthly_names():
    start, end = parse_dbn_file_dates("glbx-mdp3-20221201-20221231.ohlcv-1m.dbn.zst")

    assert start == pd.Timestamp("2022-12-01")
    assert end == pd.Timestamp("2022-12-31")


def test_databento_file_selection_uses_date_overlap(tmp_path):
    for name in [
        "glbx-mdp3-20221101-20221130.ohlcv-1m.dbn.zst",
        "glbx-mdp3-20221201-20221231.ohlcv-1m.dbn.zst",
        "glbx-mdp3-20230101-20230131.ohlcv-1m.dbn.zst",
    ]:
        Path(tmp_path / name).touch()

    files = list_databento_dbn_files(
        tmp_path,
        {
            "start_date": "2022-12-15",
            "end_date": "2023-01-05",
        },
    )

    assert [path.name for path in files] == [
        "glbx-mdp3-20221201-20221231.ohlcv-1m.dbn.zst",
        "glbx-mdp3-20230101-20230131.ohlcv-1m.dbn.zst",
    ]


def test_cached_databento_timestamps_convert_to_config_timezone(tmp_path):
    raw = tmp_path / "glbx-mdp3-20240101-20240131.ohlcv-1m.dbn.zst"
    raw.touch()
    cache_dir = tmp_path / "cache"
    cache_dir.mkdir()
    cache_path = cache_dir / "glbx-mdp3-20240101-20240131.ohlcv-1m.parquet"
    pd.DataFrame(
        {
            "timestamp": [pd.Timestamp("2024-01-02 22:30:00", tz="Asia/Singapore")],
            "open": [1.0],
            "high": [1.0],
            "low": [1.0],
            "close": [1.0],
            "volume": [1],
            "symbol": ["ES"],
            "contract_symbol": ["ESH4"],
        }
    ).to_parquet(cache_path, index=False)
    os.utime(cache_path, (raw.stat().st_mtime + 1, raw.stat().st_mtime + 1))

    out = _read_cached_dbn_file(raw, {"cache_dir": str(cache_dir), "timezone": "America/New_York"})

    assert str(out["timestamp"].dt.tz) == "America/New_York"
    assert out.loc[0, "timestamp"] == pd.Timestamp("2024-01-02 09:30:00", tz="America/New_York")


def test_continuous_contract_selects_dominant_session_contract():
    df = pd.DataFrame(
        {
            "timestamp": pd.to_datetime(
                [
                    "2024-01-02 09:30",
                    "2024-01-02 09:30",
                    "2024-01-02 09:31",
                    "2024-01-02 09:31",
                ],
                utc=True,
            ),
            "session_date": ["2024-01-02"] * 4,
            "symbol": ["ESH4", "ESM4", "ESH4", "ESM4"],
            "contract_symbol": ["ESH4", "ESM4", "ESH4", "ESM4"],
            "open": [1.0, 2.0, 1.1, 2.1],
            "high": [1.0, 2.0, 1.1, 2.1],
            "low": [1.0, 2.0, 1.1, 2.1],
            "close": [1.0, 2.0, 1.1, 2.1],
            "volume": [10, 100, 10, 100],
        }
    )

    filtered = apply_continuous_contract(
        df,
        {
            "source": "databento_dbn",
            "symbol": "ES",
            "continuous_contract": "dominant_session_volume",
        },
    )

    assert filtered["contract_symbol"].tolist() == ["ESM4", "ESM4"]
    assert filtered["symbol"].tolist() == ["ES", "ES"]


def test_continuous_contract_selects_explicit_roll_calendar(tmp_path):
    calendar = tmp_path / "roll_calendar.csv"
    calendar.write_text(
        "\n".join(
            [
                "start_timestamp,contract_symbol",
                "2024-01-02 09:30:00-05:00,ESH4",
                "2024-01-02 09:31:00-05:00,ESM4",
            ]
        ),
        encoding="utf-8",
    )
    df = pd.DataFrame(
        {
            "timestamp": pd.to_datetime(
                [
                    "2024-01-02 09:30",
                    "2024-01-02 09:30",
                    "2024-01-02 09:31",
                    "2024-01-02 09:31",
                ]
            ).tz_localize("America/New_York"),
            "session_date": ["2024-01-02"] * 4,
            "symbol": ["ESH4", "ESM4", "ESH4", "ESM4"],
            "contract_symbol": ["ESH4", "ESM4", "ESH4", "ESM4"],
            "open": [1.0, 2.0, 1.1, 2.1],
            "high": [1.0, 2.0, 1.1, 2.1],
            "low": [1.0, 2.0, 1.1, 2.1],
            "close": [1.0, 2.0, 1.1, 2.1],
            "volume": [100, 100, 100, 100],
        }
    )

    filtered = apply_continuous_contract(
        df,
        {
            "source": "databento_dbn",
            "symbol": "ES",
            "timezone": "America/New_York",
            "continuous_contract": "explicit_roll_calendar",
            "roll_calendar": str(calendar),
        },
    )

    assert filtered["contract_symbol"].tolist() == ["ESH4", "ESM4"]


def test_explicit_roll_calendar_matches_two_digit_cache_symbols_to_one_digit_calendar(tmp_path):
    calendar = tmp_path / "roll_calendar.csv"
    calendar.write_text(
        "start_timestamp,contract_symbol\n2025-06-17 00:00:00-04:00,ESU5\n",
        encoding="utf-8",
    )
    timestamp = pd.Timestamp("2025-07-14 09:30:00", tz="America/New_York")
    frame = pd.DataFrame(
        {
            "timestamp": [timestamp],
            "session_date": ["2025-07-14"],
            "symbol": ["ES"],
            "contract_symbol": ["ESU25"],
            "open": [6300.0],
            "high": [6300.0],
            "low": [6300.0],
            "close": [6300.0],
            "volume": [1],
        }
    )

    filtered = apply_continuous_contract(
        frame,
        {
            "source": "parquet",
            "symbol": "ES",
            "timezone": "America/New_York",
            "continuous_contract": "explicit_roll_calendar",
            "roll_calendar": str(calendar),
        },
    )

    assert filtered["contract_symbol"].tolist() == ["ESU25"]


def test_roll_calendar_handles_mixed_dst_offsets(tmp_path):
    calendar = tmp_path / "roll_calendar.csv"
    calendar.write_text(
        "\n".join(
            [
                "start_timestamp,contract_symbol",
                "2024-03-12 00:00:00-04:00,ESM4",
                "2024-12-17 00:00:00-05:00,ESH5",
            ]
        ),
        encoding="utf-8",
    )

    parsed = load_roll_calendar(calendar, "America/New_York")

    assert str(parsed["start_timestamp"].dt.tz) == "America/New_York"
    assert parsed["contract_symbol"].tolist() == ["ESM4", "ESH5"]


def test_roll_boundary_policy_can_skip_roll_sessions():
    df = pd.DataFrame(
        {
            "timestamp": pd.to_datetime(
                [
                    "2024-01-01 09:30",
                    "2024-01-02 09:30",
                    "2024-01-03 09:30",
                    "2024-01-04 09:30",
                ]
            ).tz_localize("America/New_York"),
            "session_date": [
                pd.Timestamp("2024-01-01").date(),
                pd.Timestamp("2024-01-02").date(),
                pd.Timestamp("2024-01-03").date(),
                pd.Timestamp("2024-01-04").date(),
            ],
            "contract_symbol": ["ESH4", "ESH4", "ESM4", "ESM4"],
        }
    )

    filtered, report = apply_roll_boundary_policy(
        df,
        {"roll_boundary_policy": {"skip_sessions_around_roll": 1}},
    )

    assert filtered["session_date"].astype(str).tolist() == ["2024-01-01"]
    assert report["roll_boundary_sessions_skipped"] == 3
