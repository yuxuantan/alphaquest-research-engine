from __future__ import annotations

import pandas as pd

from tools.prepare_historical_remediation_review import (
    _latest_ledger_row,
    _latest_variant_row,
    _ledger_verdict,
    _trade_id,
)


def test_latest_ledger_row_prefers_exact_run_path_and_latest_entry():
    ledger = pd.DataFrame(
        [
            {"campaign_id": "c", "variant_id": "v", "report_path": "other/run/metrics.json", "decision": "FAIL"},
            {"campaign_id": "c", "variant_id": "v", "report_path": "target/run/old.json", "decision": "NEEDS MANUAL REVIEW"},
            {"campaign_id": "c", "variant_id": "v", "report_path": "target/run/new.json", "decision": "FAIL"},
        ]
    ).fillna("")

    result = _latest_ledger_row(
        ledger,
        {"campaign_id": "c", "variant_id": "v", "run_dir": "target/run"},
    )

    assert result["decision"] == "FAIL"
    assert result["report_path"] == "target/run/new.json"


def test_trade_id_normalizes_integer_floats():
    assert _trade_id(7.0) == "7"
    assert _trade_id("trade-a") == "trade-a"


def test_ledger_verdict_uses_result_and_rejection_decision():
    assert _ledger_verdict({"result": "FAIL", "decision": "reject"}) == "FAIL"
    assert _ledger_verdict({"result": "needs_manual_review", "decision": ""}) == "NEEDS MANUAL REVIEW"
    assert _ledger_verdict({"result": "metrics", "decision": "not_a_candidate"}) is None


def test_latest_variant_row_does_not_limit_to_historical_run_path():
    ledger = pd.DataFrame(
        [
            {"campaign_id": "c", "variant_id": "v", "report_path": "old/run", "result": "NEEDS MANUAL REVIEW"},
            {"campaign_id": "c", "variant_id": "v", "report_path": "later/run", "result": "FAIL"},
        ]
    ).fillna("")

    result = _latest_variant_row(ledger, {"campaign_id": "c", "variant_id": "v"})

    assert result["report_path"] == "later/run"
    assert _ledger_verdict(result) == "FAIL"
