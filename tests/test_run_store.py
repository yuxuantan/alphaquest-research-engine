import sqlite3

from propstack.research.run_store import backfill_run_uids, build_run_store_index, ensure_run_uid, read_run_uid


def test_run_uid_is_valid_and_stable(tmp_path):
    run = tmp_path / "run"
    first = ensure_run_uid(run)
    second = ensure_run_uid(run)
    assert first == second
    assert read_run_uid(run) == first


def test_run_store_builds_date_partitioned_compatibility_link(tmp_path):
    run = tmp_path / "backtest-campaigns" / "demo" / "base" / "ES" / "run1"
    run.mkdir(parents=True)
    database = tmp_path / "catalogs" / "registry.sqlite"
    database.parent.mkdir()
    with sqlite3.connect(database) as connection:
        connection.execute(
            """CREATE TABLE runs (
                run_uid TEXT, campaign_id TEXT, variant_id TEXT, test_run_id TEXT,
                verdict TEXT, updated_at TEXT, output_dir TEXT, summary_path TEXT,
                config_hash TEXT, input_data_hash TEXT
            )"""
        )
        connection.execute(
            "INSERT INTO runs VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                "00000000-0000-4000-8000-000000000001", "demo", "base", "run1", "FAIL",
                "2026-07-11T00:00:00Z", "backtest-campaigns/demo/base/ES/run1",
                "backtest-campaigns/demo/base/ES/run1/campaign_test_summary.json", "config", "data",
            ),
        )
    counts = build_run_store_index(database, project_root=tmp_path, apply=True)
    link = tmp_path / "run-store" / "generated" / "runs" / "2026" / "07" / "00000000-0000-4000-8000-000000000001"
    assert counts == {"runs": 1, "resolvable_sources": 1}
    assert link.is_symlink()
    assert link.resolve() == run


def test_uid_backfill_includes_variant_only_summaries(tmp_path):
    run = tmp_path / "backtest-campaigns" / "demo" / "base" / "ES" / "run1"
    run.mkdir(parents=True)
    (run / "variant_test_summary.json").write_text("{}", encoding="utf-8")

    counts = backfill_run_uids(project_root=tmp_path, apply=True)

    assert counts == {"runs": 1, "existing": 0, "created": 1, "invalid": 0}
    assert read_run_uid(run) is not None
