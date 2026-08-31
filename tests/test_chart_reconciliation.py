from pathlib import Path

import pytest

from alphaquest.studio.chart_reconciliation import reconcile_chart_export


def test_chart_reconciliation_matches_hashes_but_never_approves(tmp_path: Path) -> None:
    source = tmp_path / "chart.csv"
    source.write_text(
        "trade_id,entry_time,exit_time,entry_price,exit_price,direction\n"
        "7,2026-01-01T14:30:00Z,2026-01-01T14:35:00Z,5000.25,5001.0,long\n",
        encoding="utf-8",
    )
    result = reconcile_chart_export(
        source,
        [
            {
                "trade_id": "7",
                "entry_time": "2026-01-01T09:30:00-05:00",
                "exit_time": "2026-01-01T09:35:00-05:00",
                "entry_price": 5000.25,
                "exit_price": 5001.0,
                "direction": "LONG",
            }
        ],
    )
    assert result["status"] == "MATCH"
    assert result["approval_effect"] == "NONE"
    assert len(result["source_sha256"]) == 64


def test_chart_reconciliation_requires_trade_identity(tmp_path: Path) -> None:
    source = tmp_path / "chart.csv"
    source.write_text("entry_price\n5000.25\n", encoding="utf-8")
    with pytest.raises(ValueError, match="trade_id"):
        reconcile_chart_export(source, [])
