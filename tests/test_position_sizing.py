from alphaquest.backtest.sizing import size_position, tick_value_from_core


def test_tick_value_can_be_derived_from_point_value():
    assert tick_value_from_core({"tick_size": 0.5, "point_value": 20.0}) == 10.0


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


def test_fixed_dollar_sizing_can_require_exactly_two_contracts():
    size = size_position(
        {
            "position_sizing": {
                "mode": "fixed_dollar_risk",
                "risk_budget": 1600.0,
                "cost_allowance_per_contract": 28.1,
                "rounding": "floor",
                "min_contracts": 2,
                "max_contracts": 2,
            },
        },
        risk_points=15.25,
        tick_size=0.25,
        tick_value=12.50,
    )

    assert size.contracts == 2
    assert size.unrounded_contracts > 2
    assert size.planned_dollar_risk == 1581.2


def test_even_two_contract_sizing_rejects_a_gap_beyond_the_risk_cap():
    size = size_position(
        {
            "position_sizing": {
                "mode": "fixed_dollar_risk",
                "risk_budget": 1600.0,
                "cost_allowance_per_contract": 28.1,
                "rounding": "floor",
                "min_contracts": 2,
                "max_contracts": 2,
            },
        },
        risk_points=16.0,
        tick_size=0.25,
        tick_value=12.50,
    )

    assert size.contracts == 0


def test_prop_drawdown_survival_budget_sizes_one_es_or_rejects_the_setup():
    sizing = {
        "position_sizing": {
            "mode": "fixed_dollar_risk",
            "risk_budget": 200.0,
            "cost_allowance_per_contract": 28.1,
            "rounding": "floor",
            "min_contracts": 1,
            "max_contracts": 1,
        },
    }

    affordable = size_position(
        sizing,
        risk_points=3.25,  # 13 ES ticks.
        tick_size=0.25,
        tick_value=12.50,
    )
    unaffordable = size_position(
        sizing,
        risk_points=3.50,  # 14 ES ticks.
        tick_size=0.25,
        tick_value=12.50,
    )

    assert affordable.contracts == 1
    assert affordable.planned_dollar_risk == 190.6
    assert unaffordable.contracts == 0


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


def test_mes_net_liq_sizing_includes_costs_and_rejects_only_above_one_contract_risk_ceiling():
    core = {
        "initial_balance": 50_000,
        "position_sizing": {
            "mode": "risk_percent_net_liq",
            "risk_pct": 0.004,
            "cost_allowance_per_contract": 2.27,
            "rounding": "floor",
            "min_contracts": 1,
        },
    }

    affordable = size_position(
        core,
        risk_points=39.5,  # 158 MES ticks from filled entry to stop.
        tick_size=0.25,
        tick_value=1.25,
        net_liq=50_000,
    )
    too_wide = size_position(
        core,
        risk_points=39.75,  # 159 MES ticks from filled entry to stop.
        tick_size=0.25,
        tick_value=1.25,
        net_liq=50_000,
    )

    assert affordable.contracts == 1
    assert affordable.target_risk_amount == 200.0
    assert affordable.dollar_risk_per_contract == 199.77
    assert affordable.planned_dollar_risk == 199.77
    assert affordable.rejection_reason is None
    assert too_wide.contracts == 0
    assert too_wide.dollar_risk_per_contract == 201.02
    assert too_wide.rejection_reason == "stop_too_wide_for_minimum_contract"


def test_mes_net_liq_sizing_floors_quantity_without_rejecting_an_affordable_trade():
    size = size_position(
        {
            "initial_balance": 50_000,
            "position_sizing": {
                "mode": "risk_percent_net_liq",
                "risk_pct": 0.004,
                "cost_allowance_per_contract": 2.27,
                "rounding": "floor",
                "min_contracts": 1,
            },
        },
        risk_points=10.0,  # 40 ticks; $52.27 all-in planned risk per MES.
        tick_size=0.25,
        tick_value=1.25,
        net_liq=50_000,
    )

    assert size.contracts == 3
    assert size.target_risk_amount == 200.0
    assert size.planned_dollar_risk == 156.81
    assert size.rejection_reason is None
