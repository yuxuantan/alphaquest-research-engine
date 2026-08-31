from alphaquest.backtest.engine import BacktestEngine
from alphaquest.research.golden import backtest_result_signature
from tests.test_backtest_engine import BASE_CFG, _features


def test_backtest_engine_golden_fixture_signature():
    signature = backtest_result_signature(BacktestEngine(BASE_CFG).run(_features()))

    assert signature["hash"] == "b27c376cbbcc0dc1b56128eff841c01e3f477e88f2e6e1369db00bcdaa65150b"
    assert signature["payload"]["metrics"]["total_trades"] == 2
    assert signature["payload"]["metrics"]["net_profit"] == 182.5
    assert signature["payload"]["metrics"]["trades_per_year"] == 22.828125
