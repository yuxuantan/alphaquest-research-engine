from pathlib import Path

import pandas as pd

from propstack.data.clean import apply_continuous_contract
from propstack.data.load import list_databento_dbn_files, parse_dbn_file_dates


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
