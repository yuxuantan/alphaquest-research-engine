from propstack.data.clean import clean_data
from propstack.data.quality import tradingview_comparison_report
from propstack.data.features import build_features

from tests.test_data_pipeline import DATA_CFG


def test_tradingview_comparison_columns():
    df, _, _ = clean_data(DATA_CFG)
    report = tradingview_comparison_report(build_features(df, DATA_CFG))
    assert "rth_open" in report.columns
    assert "overnight_high" in report.columns
    assert "previous_rth_low" in report.columns
