from propstack.data.clean import clean_data

from tests.test_data_pipeline import DATA_CFG


def test_rth_and_eth_labels():
    df, _, _ = clean_data(DATA_CFG)
    assert set(df["session_label"]) == {"RTH", "ETH"}
    assert df["is_rth"].sum() == 16
    assert df["is_eth"].sum() == 4
