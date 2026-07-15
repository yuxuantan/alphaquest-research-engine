from __future__ import annotations

import pytest

from propstack.backtest.engine import _validate_large_record_source_contract


def test_rejects_legacy_component_row_large200_proxy() -> None:
    config = {
        "data": {"raw_parquet": "legacy_large200.parquet"},
        "strategy": {
            "entry": {
                "module": "large_record_aoi_reaction",
                "params": {"min_large200_record_volume": 200},
            }
        },
    }

    with pytest.raises(ValueError, match="component-row large200 proxies are prohibited"):
        _validate_large_record_source_contract(config)


def test_accepts_reconstructed_bar_large200_semantics() -> None:
    config = {
        "data": {"large_record_source_semantics": "reconstructed_trade_event"},
        "strategy": {
            "entry": {
                "module": "large_record_aoi_reaction",
                "params": {"min_large200_record_volume": 200},
            }
        },
    }

    _validate_large_record_source_contract(config)


def test_accepts_supported_intrabar_direct_event_module() -> None:
    config = {
        "data": {"execution_data": {"source": "databento_zip_trades"}},
        "strategy": {
            "entry": {
                "module": "yush_trend_47",
                "params": {"min_large200_record_volume": 200},
            }
        },
    }

    _validate_large_record_source_contract(config)


def test_defers_source_contract_for_caller_supplied_in_memory_data() -> None:
    config = {
        "strategy": {
            "entry": {
                "module": "yush_trend_47",
                "params": {"min_large200_record_volume": 200},
            }
        }
    }

    _validate_large_record_source_contract(config)
