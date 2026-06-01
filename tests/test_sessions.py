import pandas as pd

from propstack.data.clean import clean_data
from propstack.data.sessions import assign_sessions

from tests.test_data_pipeline import DATA_CFG


def test_rth_and_eth_labels():
    df, _, _ = clean_data(DATA_CFG)
    assert set(df["session_label"]) == {"RTH", "ETH"}
    assert df["is_rth"].sum() == 16
    assert df["is_eth"].sum() == 4


def test_shared_rth_eth_boundary_is_eth_only():
    df = pd.DataFrame(
        {
            "timestamp": pd.to_datetime(
                [
                    "2022-12-16 15:59:00",
                    "2022-12-16 16:00:00",
                    "2022-12-16 16:01:00",
                ]
            ).tz_localize("America/New_York"),
        }
    )
    out = assign_sessions(
        df,
        {
            "rth_start": "09:30:00",
            "rth_end": "16:00:00",
            "eth_start": "16:00:00",
            "eth_end": "09:29:00",
        },
    )

    boundary = out.iloc[1]

    assert not boundary["is_rth"]
    assert boundary["is_eth"]
    assert boundary["session_label"] == "ETH"
    assert str(boundary["session_date"]) == "2022-12-17"
