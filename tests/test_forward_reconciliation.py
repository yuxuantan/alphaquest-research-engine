from __future__ import annotations

from pathlib import Path

from alphaquest.studio.forward_reconciliation import reconcile_forward_trade_csv


def test_reconcile_forward_trade_csv_derives_explicit_totals(tmp_path: Path) -> None:
    source = tmp_path / "forward.csv"
    source.write_text(
        "trade_id,net_pnl,prop_rule_breach,forced_flatten_violation\n"
        "t1,125.50,false,false\n"
        "t2,-25.25,false,true\n",
        encoding="utf-8",
    )

    result = reconcile_forward_trade_csv(source)

    assert result["usable"] is True
    assert result["trade_count_delta"] == 2
    assert result["net_pnl_delta"] == 100.25
    assert result["prop_rule_breach"] is False
    assert result["forced_flatten_violation"] is True
    assert result["blockers"] == []


def test_reconcile_forward_trade_csv_leaves_absent_risk_flags_for_human_confirmation(
    tmp_path: Path,
) -> None:
    source = tmp_path / "forward.csv"
    source.write_text("trade_id,pnl\nt1,10\nt2,20\n", encoding="utf-8")

    result = reconcile_forward_trade_csv(source)

    assert result["usable"] is True
    assert result["net_pnl_delta"] == 30
    assert result["prop_rule_breach"] is None
    assert result["forced_flatten_violation"] is None
    assert len(result["warnings"]) == 2


def test_reconcile_forward_trade_csv_fails_closed_on_duplicates_or_bad_pnl(
    tmp_path: Path,
) -> None:
    source = tmp_path / "forward.csv"
    source.write_text("trade_id,pnl\nt1,10\nt1,not-a-number\n", encoding="utf-8")

    result = reconcile_forward_trade_csv(source)

    assert result["usable"] is False
    assert result["net_pnl_delta"] is None
    assert any("duplicate" in blocker for blocker in result["blockers"])
    assert any("invalid pnl" in blocker for blocker in result["blockers"])
