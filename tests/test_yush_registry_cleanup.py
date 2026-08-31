from pathlib import Path

import pytest

from alphaquest.authoring.catalog import CERTIFIED_MODULE_CATALOG
from alphaquest.strategy_modules.entry import ENTRY_MODULES, build_entry_module


RETIRED_COMPANION_MODULES = {
    "event_aoi_structural_stop",
    "event_value_area_management",
    "event_adaptive_sweep_structural_stop",
    "event_excursion_structural_stop",
    "event_frozen_poc_time_exit",
    "event_frozen_poc_value_area_scale_out",
}


def test_authoring_catalog_retains_only_the_yush_v04_range_reversal_package() -> None:
    manifests = CERTIFIED_MODULE_CATALOG.all()

    assert {item.name for item in manifests if item.name.startswith("yush_")} == {
        "yush_adaptive_orderflow_range_v4"
    }
    assert RETIRED_COMPANION_MODULES.isdisjoint(item.name for item in manifests)
    assert CERTIFIED_MODULE_CATALOG.get("sl", "event_fill_time_sweep_to_entry_extreme_stop")
    assert CERTIFIED_MODULE_CATALOG.get(
        "tp",
        "event_frozen_midpoint_two_ticks_outside_opposite_value_area_scale_out",
    )


def test_legacy_yush_sources_are_preserved_but_not_registered() -> None:
    source_root = (
        Path(__file__).resolve().parents[1]
        / "src"
        / "alphaquest"
        / "strategy_modules"
        / "entry"
    )
    source_names = {
        path.stem
        for pattern in ("yush_range_*.py", "yush_trend_*.py")
        for path in source_root.glob(pattern)
    }

    assert len(source_names) == 112
    assert {"yush_range_1", "yush_range_31", "yush_trend_1", "yush_trend_82"} <= source_names
    assert source_names.isdisjoint(ENTRY_MODULES)


@pytest.mark.parametrize(
    "module_name",
    ["yush_range_1", "yush_range_31", "yush_trend_1", "yush_trend_82"],
)
def test_legacy_yush_entry_modules_fail_closed_at_runtime(module_name: str) -> None:
    with pytest.raises(ValueError, match=f"Unknown entry module: {module_name}"):
        build_entry_module({"module": module_name, "params": {}})
