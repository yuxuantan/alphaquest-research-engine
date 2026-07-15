from __future__ import annotations

from alphaquest.validation.loaders import load_validation_run
from alphaquest.validation.sample_run import write_sample_validation_run


def test_sample_validation_run_writes_dashboard_artifacts(tmp_path):
    run_dir = write_sample_validation_run(tmp_path / "sample_core")
    loaded = load_validation_run(run_dir)

    assert (run_dir / "metadata.json").exists()
    assert (run_dir / "trades.parquet").exists()
    assert (run_dir / "validation_checks.parquet").exists()
    assert len(loaded.trades) == 3
    assert not loaded.bar_windows.empty
    assert not loaded.exit_audits.empty
    assert not loaded.validation_checks.empty
