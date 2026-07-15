from alphaquest.backtest.engine import BacktestEngine
from alphaquest.research.golden import backtest_result_signature
from tests.test_backtest_engine import BASE_CFG, _features


def test_backtest_engine_golden_fixture_signature():
    signature = backtest_result_signature(BacktestEngine(BASE_CFG).run(_features()))

    assert signature["hash"] == "a54783738a335c38e6e2b10710f0ea3b893d688a058a6e322073d38872c4e226"
    assert signature["payload"]["metrics"]["total_trades"] == 2
    assert signature["payload"]["metrics"]["net_profit"] == 182.5
