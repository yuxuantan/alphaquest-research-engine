from pathlib import Path

import pytest
import yaml

from propstack.utils.config import (
    ensure_variant_metadata,
    campaign_metadata_path,
    validate_campaign_run_root,
    variant_metadata_path,
    variant_root,
)


def test_variant_root_includes_campaign_dataset_timeframe_and_variant():
    config = {
        "campaign_id": "pdh_pdl_sweep",
        "variant_id": "baseline",
        "strategy_name": "pdh_pdl_sweep",
        "symbol": "ES",
        "dataset_id": "1m_20221201_20260529",
        "timeframe": "5m",
    }

    assert str(variant_root(config)) == (
        "backtest-campaigns/pdh_pdl_sweep/baseline/ES/run1"
    )


def test_variant_root_uses_campaign_test_run_id():
    config = {
        "campaign_id": "pdh_pdl_sweep",
        "variant_id": "baseline",
        "strategy_name": "pdh_pdl_sweep",
        "symbol": "ES",
        "dataset_id": "1m_20221201_20260529",
        "timeframe": "5m",
        "test_run_id": "run2",
    }

    assert str(variant_root(config)) == (
        "backtest-campaigns/pdh_pdl_sweep/baseline/ES/run2"
    )


def test_variant_root_can_derive_campaign_test_run_id_from_local_config_path():
    config = {
        "campaign_id": "pdh_pdl_sweep",
        "variant_id": "baseline",
        "strategy_name": "pdh_pdl_sweep",
        "symbol": "ES",
        "dataset_id": "1m_20221201_20260529",
        "timeframe": "5m",
    }

    assert str(
        variant_root(
            config,
            config_path="backtest-campaigns/pdh_pdl_sweep/baseline/ES/run2/config.yaml",
        )
    ) == "backtest-campaigns/pdh_pdl_sweep/baseline/ES/run2"


def test_campaign_metadata_path_lives_at_campaign_root():
    config = {
        "campaign_id": "pdh_pdl_sweep",
        "variant_id": "baseline",
        "strategy_name": "pdh_pdl_sweep",
        "symbol": "ES",
        "dataset_id": "1m_20221201_20260529",
        "timeframe": "5m",
    }

    assert str(campaign_metadata_path(config)) == "backtest-campaigns/pdh_pdl_sweep/campaign.yaml"


def test_variant_metadata_path_lives_at_variant_root():
    config = {
        "campaign_id": "pdh_pdl_sweep",
        "variant_id": "baseline",
        "strategy_name": "pdh_pdl_sweep",
        "symbol": "ES",
        "dataset_id": "1m_20221201_20260529",
        "timeframe": "5m",
    }

    assert str(variant_metadata_path(config)) == "backtest-campaigns/pdh_pdl_sweep/baseline/variant.yaml"


def test_ensure_variant_metadata_writes_variant_file_and_campaign_index(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    config = {
        "campaign_id": "pdh_pdl_sweep",
        "variant_id": "baseline",
        "strategy_name": "pdh_pdl_sweep",
        "symbol": "ES",
        "dataset_id": "1m_20221201_20260529",
        "timeframe": "5m",
        "strategy": {
            "entry": {"module": "pdh_pdl_sweep_reclaim"},
            "tp": {"module": "fixed_r"},
            "sl": {"module": "sweep_extreme"},
        },
    }

    info = ensure_variant_metadata(config)

    assert info["path"] == "backtest-campaigns/pdh_pdl_sweep/baseline/variant.yaml"
    variant_metadata = yaml.safe_load(Path(info["path"]).read_text(encoding="utf-8"))
    assert variant_metadata["mechanic"] == {
        "entry_module": "pdh_pdl_sweep_reclaim",
        "take_profit_module": "fixed_r",
        "stop_loss_module": "sweep_extreme",
    }
    assert variant_metadata["rescue_policy"] == {
        "rescue_scope": "failed_variant",
        "max_rescue_attempts_per_failed_variant": 1,
        "allowed": [
            "change fixed parameters inside existing strategy modules",
            "change tunable parameter space inside existing strategy modules",
        ],
        "forbidden": [
            "rescue the same failed variant more than once",
            "change entry module",
            "change take-profit module",
            "change stop-loss module",
            "change the economic edge thesis",
            "change stage criteria",
            "change data window",
            "change timeframe",
            "add or remove filters outside the existing strategy modules",
        ],
    }
    index = yaml.safe_load(
        Path("backtest-campaigns/pdh_pdl_sweep/variants_index.yaml").read_text(encoding="utf-8")
    )
    assert index["variants"][0]["variant_id"] == "baseline"
    assert index["variants"][0]["mechanic"]["entry_module"] == "pdh_pdl_sweep_reclaim"


def test_ensure_variant_metadata_rejects_changed_mechanic(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    metadata = tmp_path / "backtest-campaigns/pdh_pdl_sweep/baseline/variant.yaml"
    metadata.parent.mkdir(parents=True)
    metadata.write_text(
        "\n".join(
            [
                "campaign_id: pdh_pdl_sweep",
                "variant_id: baseline",
                "mechanic:",
                "  entry_module: pdh_pdl_sweep_reclaim",
                "  take_profit_module: fixed_r",
                "  stop_loss_module: sweep_extreme",
            ]
        ),
        encoding="utf-8",
    )
    config = {
        "campaign_id": "pdh_pdl_sweep",
        "variant_id": "baseline",
        "strategy_name": "pdh_pdl_sweep",
        "symbol": "ES",
        "dataset_id": "1m_20221201_20260529",
        "timeframe": "5m",
        "strategy": {
            "entry": {"module": "different_entry"},
            "tp": {"module": "fixed_r"},
            "sl": {"module": "sweep_extreme"},
        },
    }

    with pytest.raises(ValueError, match="mechanic.entry_module"):
        ensure_variant_metadata(config)


def test_ensure_variant_metadata_tightens_existing_rescue_policy(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    metadata = tmp_path / "backtest-campaigns/pdh_pdl_sweep/baseline/variant.yaml"
    metadata.parent.mkdir(parents=True)
    metadata.write_text(
        "\n".join(
            [
                "campaign_id: pdh_pdl_sweep",
                "variant_id: baseline",
                "mechanic:",
                "  entry_module: pdh_pdl_sweep_reclaim",
                "  take_profit_module: fixed_r",
                "  stop_loss_module: sweep_extreme",
                "rescue_policy:",
                "  allowed:",
                "    - change fixed parameters",
                "    - change tunable parameter space",
                "    - change stage settings",
                "    - change data window",
            ]
        ),
        encoding="utf-8",
    )
    config = {
        "campaign_id": "pdh_pdl_sweep",
        "variant_id": "baseline",
        "strategy_name": "pdh_pdl_sweep",
        "symbol": "ES",
        "dataset_id": "1m_20221201_20260529",
        "timeframe": "5m",
        "strategy": {
            "entry": {"module": "pdh_pdl_sweep_reclaim"},
            "tp": {"module": "fixed_r"},
            "sl": {"module": "sweep_extreme"},
        },
    }

    ensure_variant_metadata(config)

    variant_metadata = yaml.safe_load(metadata.read_text(encoding="utf-8"))
    assert variant_metadata["rescue_policy"]["rescue_scope"] == "failed_variant"
    assert variant_metadata["rescue_policy"]["max_rescue_attempts_per_failed_variant"] == 1
    assert "change stage settings" not in variant_metadata["rescue_policy"]["allowed"]
    assert "change data window" not in variant_metadata["rescue_policy"]["allowed"]
    assert "rescue the same failed variant more than once" in variant_metadata["rescue_policy"]["forbidden"]
    assert "change stage criteria" in variant_metadata["rescue_policy"]["forbidden"]
    assert "change data window" in variant_metadata["rescue_policy"]["forbidden"]


def test_validate_campaign_run_root_rejects_symbol_level_summary_folder():
    config = {
        "campaign_id": "pdh_pdl_sweep",
        "variant_id": "baseline",
        "strategy_name": "pdh_pdl_sweep",
        "symbol": "ES",
        "dataset_id": "1m_20221201_20260529",
        "timeframe": "5m",
    }

    with pytest.raises(ValueError, match="backtest-campaigns/\\{campaign_id\\}"):
        validate_campaign_run_root("backtest-campaigns/pdh_pdl_sweep/baseline/ES", config)


def test_validate_campaign_run_root_rejects_timeframe_symbol_folder():
    config = {
        "campaign_id": "pdh_pdl_sweep",
        "variant_id": "baseline",
        "strategy_name": "pdh_pdl_sweep",
        "symbol": "ES",
        "dataset_id": "1m_20221201_20260529",
        "timeframe": "5m",
    }

    with pytest.raises(ValueError, match="symbol: expected ES, got ES_1m"):
        validate_campaign_run_root("backtest-campaigns/pdh_pdl_sweep/baseline/ES_1m/run1", config)


def test_validate_campaign_run_root_rejects_config_folder_run_mismatch():
    config = {
        "campaign_id": "pdh_pdl_sweep",
        "variant_id": "baseline",
        "strategy_name": "pdh_pdl_sweep",
        "symbol": "ES",
        "dataset_id": "1m_20221201_20260529",
        "timeframe": "5m",
    }

    with pytest.raises(ValueError, match="source config folder run1"):
        validate_campaign_run_root(
            "backtest-campaigns/pdh_pdl_sweep/baseline/ES/run2",
            config,
            config_path="backtest-campaigns/pdh_pdl_sweep/baseline/ES/run1/config.yaml",
        )


def test_variant_root_requires_dataset_id():
    with pytest.raises(ValueError, match="dataset_id"):
        variant_root(
            {
                "campaign_id": "pdh_pdl_sweep",
                "variant_id": "baseline",
                "strategy_name": "pdh_pdl_sweep",
                "symbol": "ES",
                "timeframe": "1m",
            }
        )


def test_variant_root_requires_timeframe():
    with pytest.raises(ValueError, match="timeframe"):
        variant_root(
            {
                "campaign_id": "pdh_pdl_sweep",
                "variant_id": "baseline",
                "strategy_name": "pdh_pdl_sweep",
                "symbol": "ES",
                "dataset_id": "1m_20221201_20260529",
            }
        )


def test_variant_root_requires_variant_id():
    with pytest.raises(ValueError, match="variant_id"):
        variant_root(
            {
                "campaign_id": "pdh_pdl_sweep",
                "strategy_name": "pdh_pdl_sweep",
                "symbol": "ES",
                "dataset_id": "1m_20221201_20260529",
                "timeframe": "1m",
            }
        )


def test_active_configs_do_not_reference_invalid_prefixed_sierra_cache():
    invalid_tokens = [
        "configs/data/ES",
        "sierra_trade_orderflow_1m_20110105_20260610_full_rth",
        "es_sierra_trade_orderflow_1m_20101214_20260610_full_rth.parquet",
        "es_sierra_recent_pocket_combo_signal_1m_20110105_20260610",
        "es_sierra_cross_pocket_meta_signal_1m_20110105_20260610",
        "es_sierra_footprint_extreme_1m_20110105_20260610",
    ]
    offenders = []
    for path in Path("backtest-campaigns").rglob("*.yaml"):
        text = path.read_text(encoding="utf-8")
        if any(token in text for token in invalid_tokens):
            offenders.append(str(path))

    assert offenders == []
