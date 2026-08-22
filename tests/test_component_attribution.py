from __future__ import annotations

import hashlib
import json

import pytest

from alphaquest.research.attribution import (
    AttributionBacktestResult,
    AttributionContractError,
    AttributionExecutionError,
    CertifiedNeutralReplacement,
    ClaimedComponent,
    execute_component_attribution,
    read_component_attribution_contract,
    seal_component_attribution_contract,
    write_component_attribution_contract,
)


def _hash(value) -> str:
    encoded = json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _full_config():
    return {
        "strategy": {
            "entry": {"module": "certified.momentum", "params": {"length": 20}},
            "sl": {"module": "certified.stop", "params": {"ticks": 8}},
            "tp": {"module": "certified.target", "params": {"ticks": 16}},
        },
        "core": {"commission_per_contract": 2.5, "slippage_ticks": 1},
        "data": {"dataset_id": "es_fixture"},
    }


def _component(config, *, component_id="momentum", status="eligible", edge_hash="a" * 64):
    neutral = CertifiedNeutralReplacement(
        binding={"module": "certified.always_false", "params": {}},
        strategy_id="neutral-entry-v1",
        implementation_version="1.0.0",
        implementation_sha256="b" * 64,
        certification_manifest_sha256="c" * 64,
        approved_edge_fingerprint_sha256=edge_hash,
        methodology_category="entry",
        neutrality_rationale="Disable only the claimed entry condition while retaining generic execution.",
    )
    return ClaimedComponent(
        component_id=component_id,
        claimed_mechanism="Twenty-bar continuation filter",
        methodology_category="entry",
        binding_path="strategy.entry",
        full_binding_sha256=_hash(config["strategy"]["entry"]),
        neutral_replacement=neutral,
        ablation_status=status,
    )


def _contract(config, components):
    return seal_component_attribution_contract(
        campaign_id="demo",
        variant_id="v01",
        attempt_id="attempt_001",
        declared_at="2026-08-14T08:00:00+00:00",
        pnl_observed=False,
        economic_edge_fingerprint_sha256="a" * 64,
        research_objectives_sha256="d" * 64,
        full_config_sha256=_hash(config),
        data_sha256="e" * 64,
        evaluation_window_sha256="f" * 64,
        execution_costs_sha256="1" * 64,
        parameter_grid_sha256="2" * 64,
        engine_contract_sha256="3" * 64,
        components=components,
    )


def test_component_attribution_is_predeclared_hash_bound_and_inspection_only(tmp_path):
    config = _full_config()
    contract = _contract(config, [_component(config)])
    path = tmp_path / "component_attribution_contract.json"

    write_component_attribution_contract(path, contract)
    write_component_attribution_contract(path, contract)
    assert read_component_attribution_contract(path) == contract

    seen = []

    def generic_backtest(spec):
        seen.append((spec.run_role, spec.component_id, spec.config["strategy"]["entry"]["module"]))
        metrics = (
            {"net_profit": 1200.0, "profit_factor": 1.5, "max_drawdown": 400.0}
            if spec.run_role == "full"
            else {"net_profit": 500.0, "profit_factor": 1.1, "max_drawdown": 550.0}
        )
        return AttributionBacktestResult(
            metrics=metrics,
            config_sha256=spec.config_sha256,
            data_sha256=spec.data_sha256,
            evaluation_window_sha256=spec.evaluation_window_sha256,
            execution_costs_sha256=spec.execution_costs_sha256,
            parameter_grid_sha256=spec.parameter_grid_sha256,
            engine_contract_sha256=spec.engine_contract_sha256,
        )

    result = execute_component_attribution(contract, config, generic_backtest)

    assert seen == [
        ("full", None, "certified.momentum"),
        ("leave_one_out", "momentum", "certified.always_false"),
    ]
    assert result["classification"] == "INSPECTION_ONLY"
    assert result["approval_effect"] == "NONE"
    assert result["promotion_authorized"] is False
    assert result["research_verdict"] == "NEEDS MANUAL REVIEW"
    assert result["component_deltas"][0]["delta_full_minus_leave_one_out"] == pytest.approx(
        {"max_drawdown": -150.0, "net_profit": 700.0, "profit_factor": 0.4}
    )
    assert len(result["result_sha256"]) == 64


def test_component_attribution_rejects_post_pnl_cross_edge_fixed_and_undeclared_ablations():
    config = _full_config()
    component = _component(config)

    with pytest.raises(AttributionContractError, match="before any PnL"):
        seal_component_attribution_contract(
            campaign_id="demo",
            variant_id="v01",
            attempt_id="attempt_001",
            declared_at="2026-08-14T08:00:00+00:00",
            pnl_observed=True,
            economic_edge_fingerprint_sha256="a" * 64,
            research_objectives_sha256="d" * 64,
            full_config_sha256=_hash(config),
            data_sha256="e" * 64,
            evaluation_window_sha256="f" * 64,
            execution_costs_sha256="1" * 64,
            parameter_grid_sha256="2" * 64,
            engine_contract_sha256="3" * 64,
            components=[component],
        )

    with pytest.raises(AttributionContractError, match="different economic edge"):
        _contract(config, [_component(config, edge_hash="9" * 64)])

    fixed = _contract(config, [_component(config, status="fixed")])
    with pytest.raises(AttributionExecutionError, match="fixed"):
        execute_component_attribution(fixed, config, lambda spec: {}, component_ids=["momentum"])

    contract = _contract(config, [component])
    with pytest.raises(AttributionExecutionError, match="not predeclared"):
        execute_component_attribution(contract, config, lambda spec: {}, component_ids=["secret_filter"])


def test_component_attribution_fails_closed_when_generic_run_inputs_or_metrics_differ():
    config = _full_config()
    contract = _contract(config, [_component(config)])

    def wrong_data(spec):
        return AttributionBacktestResult(
            metrics={"net_profit": 1.0},
            config_sha256=spec.config_sha256,
            data_sha256="0" * 64,
            evaluation_window_sha256=spec.evaluation_window_sha256,
            execution_costs_sha256=spec.execution_costs_sha256,
            parameter_grid_sha256=spec.parameter_grid_sha256,
            engine_contract_sha256=spec.engine_contract_sha256,
        )

    with pytest.raises(AttributionExecutionError, match="data_sha256 mismatch"):
        execute_component_attribution(contract, config, wrong_data)

    def changing_metrics(spec):
        return AttributionBacktestResult(
            metrics={"net_profit": 1.0} if spec.run_role == "full" else {"profit_factor": 1.0},
            config_sha256=spec.config_sha256,
            data_sha256=spec.data_sha256,
            evaluation_window_sha256=spec.evaluation_window_sha256,
            execution_costs_sha256=spec.execution_costs_sha256,
            parameter_grid_sha256=spec.parameter_grid_sha256,
            engine_contract_sha256=spec.engine_contract_sha256,
        )

    with pytest.raises(AttributionExecutionError, match="different metric schema"):
        execute_component_attribution(contract, config, changing_metrics)

    drifted = _full_config()
    drifted["strategy"]["entry"]["params"]["length"] = 21
    with pytest.raises(AttributionExecutionError, match="Full config hash drift"):
        execute_component_attribution(contract, drifted, wrong_data)


def test_attribution_contract_file_cannot_be_reused_for_different_declaration(tmp_path):
    config = _full_config()
    original = _contract(config, [_component(config)])
    changed = seal_component_attribution_contract(
        **{
            **{
                "campaign_id": "demo",
                "variant_id": "v01",
                "attempt_id": "attempt_002",
                "declared_at": "2026-08-14T08:01:00+00:00",
                "pnl_observed": False,
                "economic_edge_fingerprint_sha256": "a" * 64,
                "research_objectives_sha256": "d" * 64,
                "full_config_sha256": _hash(config),
                "data_sha256": "e" * 64,
                "evaluation_window_sha256": "f" * 64,
                "execution_costs_sha256": "1" * 64,
                "parameter_grid_sha256": "2" * 64,
                "engine_contract_sha256": "3" * 64,
                "components": [_component(config)],
            }
        }
    )
    path = tmp_path / "contract.json"
    write_component_attribution_contract(path, original)

    with pytest.raises(AttributionContractError, match="already exists"):
        write_component_attribution_contract(path, changed)
