import importlib.util
from pathlib import Path
import sys

import pytest

from propstack.utils.target_rr import require_minimum_target_rr


def _load_tool_module():
    path = Path(__file__).resolve().parents[1] / "tools" / "tp_widen_best_core_rescues.py"
    spec = importlib.util.spec_from_file_location("tp_widen_best_core_rescues", path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_tp_min_rr_floor_rewrites_all_target_r_multiple_sections():
    tool = _load_tool_module()
    config = {
        "strategy": {
            "tp": {"params": {"target_r_multiple": 0.75}},
            "entry": {"params": {"target_r_multiple": 1.25}},
        },
        "core_grid": {
            "parameters": {
                "tp.params.target_r_multiple": [0.5, 0.75, 1.0, 1.5],
            },
        },
        "wfa": {
            "parameters": {
                "tp.params.target_r_multiple": [0.75, 1.25],
            },
        },
    }

    updated, changes = tool._floor_target_rr_tree(config)

    assert updated["strategy"]["tp"]["params"]["target_r_multiple"] == 1.0
    assert updated["strategy"]["entry"]["params"]["target_r_multiple"] == 1.25
    assert updated["core_grid"]["parameters"]["tp.params.target_r_multiple"] == [1.0, 1.5]
    assert updated["wfa"]["parameters"]["tp.params.target_r_multiple"] == [1.0, 1.25]
    assert {change["path"] for change in changes} == {
        "config.strategy.tp.params.target_r_multiple",
        "config.core_grid.parameters.tp.params.target_r_multiple",
        "config.wfa.parameters.tp.params.target_r_multiple",
    }


def test_tp_min_rr_floor_leaves_one_r_and_higher_targets_unchanged():
    tool = _load_tool_module()
    config = {
        "strategy": {"tp": {"params": {"target_r_multiple": 1.25}}},
        "core_grid": {
            "parameters": {
                "tp.params.target_r_multiple": [1.0, 1.5, 2.0],
            },
        },
        "wfa": {
            "parameters": {
                "tp.params.target_r_multiple": [1.25, 2.0],
            },
        },
    }

    updated, changes = tool._floor_target_rr_tree(config)

    assert updated == config
    assert changes == []


def test_tp_min_rr_prepare_rescue_rejects_already_valid_targets(tmp_path):
    tool = _load_tool_module()
    source_config = tmp_path / "config.yaml"
    source_config.write_text(
        """
strategy:
  tp:
    params:
      target_r_multiple: 1.25
core_grid:
  parameters:
    tp.params.target_r_multiple: [1.0, 1.5, 2.0]
wfa:
  parameters:
    tp.params.target_r_multiple: [1.0, 1.5]
""",
        encoding="utf-8",
    )
    selected = tool.SelectedRun(
        campaign_id="es_test_campaign",
        variant_id="already_valid_rr",
        run_id="run1",
        run_dir=tmp_path,
        summary_path=tmp_path / "core_grid_summary.json",
        source_config_path=source_config,
        score=(),
        metrics={},
    )

    with pytest.raises(ValueError, match="No target_r_multiple below 1.0 found"):
        tool.prepare_rescue(selected, overwrite=True)


def test_target_rr_guard_checks_nested_value_mappings():
    config = {
        "core_grid": {
            "parameters": {
                "tp.params.target_r_multiple": {
                    "values": [0.75, 1.0],
                },
            },
        },
    }

    with pytest.raises(ValueError, match="target_r_multiple must be >= 1.0"):
        require_minimum_target_rr(config)
