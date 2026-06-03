from propstack.backtest.sizing import size_position


def test_risk_percent_sizing_floors_to_risk_ceiling():
    size = size_position(
        {
            "initial_balance": 100000,
            "position_sizing": {
                "mode": "risk_percent_initial_balance",
                "risk_pct": 0.01,
            },
        },
        risk_points=12.0,
        tick_size=0.25,
        tick_value=12.50,
    )

    assert size.contracts == 1
    assert size.target_risk_amount == 1000.0
    assert size.dollar_risk_per_contract == 600.0
    assert round(size.unrounded_contracts, 6) == round(1000.0 / 600.0, 6)
    assert size.planned_dollar_risk == 600.0


def test_risk_percent_sizing_uses_current_net_liq_when_provided():
    size = size_position(
        {
            "initial_balance": 100000,
            "position_sizing": {
                "mode": "risk_percent_net_liq",
                "risk_pct": 0.01,
            },
        },
        risk_points=12.0,
        tick_size=0.25,
        tick_value=12.50,
        net_liq=125000,
    )

    assert size.contracts == 2
    assert size.net_liq == 125000.0
    assert size.target_risk_amount == 1250.0
    assert size.planned_dollar_risk == 1200.0


def test_risk_percent_sizing_can_round_to_nearest_contract():
    size = size_position(
        {
            "initial_balance": 100000,
            "position_sizing": {
                "mode": "risk_percent_initial_balance",
                "risk_pct": 0.01,
                "rounding": "nearest",
            },
        },
        risk_points=12.0,
        tick_size=0.25,
        tick_value=12.50,
    )

    assert size.contracts == 2
    assert size.planned_dollar_risk == 1200.0


def test_risk_percent_field_uses_percent_points():
    size = size_position(
        {
            "initial_balance": 100000,
            "position_sizing": {
                "mode": "risk_percent_initial_balance",
                "risk_percent": 1.0,
            },
        },
        risk_points=12.0,
        tick_size=0.25,
        tick_value=12.50,
    )

    assert size.target_risk_amount == 1000.0
    assert size.contracts == 1


def test_risk_percent_sizing_skips_when_capital_cannot_size_one_contract():
    size = size_position(
        {
            "initial_balance": 50000,
            "position_sizing": {
                "mode": "risk_percent_initial_balance",
                "risk_pct": 0.01,
            },
        },
        risk_points=12.0,
        tick_size=0.25,
        tick_value=12.50,
    )

    assert size.contracts == 0
    assert size.planned_dollar_risk == 0.0
