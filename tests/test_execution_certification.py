from pathlib import Path
import shutil

from alphaquest.execution_certification import list_execution_profiles


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def test_generic_quote_order_profile_is_current_and_fail_closed() -> None:
    profiles = list_execution_profiles(PROJECT_ROOT)
    profile = next(item for item in profiles if item["profile_id"] == "generic_quote_orders_v1")

    assert profile["status"] == "certified"
    assert profile["errors"] == []
    assert profile["observed_implementation_sha256"] == profile["implementation_sha256"]
    assert "MBO queue priority" in profile["excluded_capabilities"]


def test_execution_profile_becomes_unavailable_after_source_drift(tmp_path: Path) -> None:
    source = PROJECT_ROOT / "src/alphaquest/backtest/order_simulation.py"
    manifest = PROJECT_ROOT / "src/alphaquest/execution_certifications/generic_quote_orders_v1.yaml"
    target_source = tmp_path / "src/alphaquest/backtest/order_simulation.py"
    target_manifest = tmp_path / "src/alphaquest/execution_certifications/generic_quote_orders_v1.yaml"
    target_source.parent.mkdir(parents=True)
    target_manifest.parent.mkdir(parents=True)
    shutil.copy2(source, target_source)
    shutil.copy2(manifest, target_manifest)
    target_source.write_text(
        target_source.read_text(encoding="utf-8") + "\n# simulated drift\n",
        encoding="utf-8",
    )

    profile = list_execution_profiles(tmp_path)[0]

    assert profile["status"] == "unavailable"
    assert profile["errors"] == ["execution implementation hash is stale"]
