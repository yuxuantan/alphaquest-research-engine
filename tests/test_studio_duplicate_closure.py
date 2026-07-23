from __future__ import annotations

import json

import pytest

from alphaquest.studio.drafts import CLOSED_BEFORE_PNL_SCHEMA
from alphaquest.studio.workflow import StudioWorkflowService


RATIONALE = (
    "This exact economic mechanism already exists in governed prior research, so another renamed or "
    "parameterized copy would add no independent evidence and must be rejected before any PnL is observed."
)


def _duplicate_draft(service: StudioWorkflowService) -> None:
    service.create_draft(
        campaign_id="es_closed_duplicate",
        title="Duplicate completed-bar idea",
        instrument="ES",
    )
    service.save_brief(
        "es_closed_duplicate",
        {
            "title": "Duplicate completed-bar idea",
            "edge_family": "duplicate_completed_bar_edge",
            "timeframe": "1m",
            "hypothesis": "A completed-bar imbalance predicts continuation from the next legal bar open.",
            "expected_mechanism": "Delayed hedging preserves the same previously tested intraday imbalance.",
            "holding_horizon": "Intraday until the configured forced flatten.",
            "known_failure_modes": ["Broad market drift can explain the apparent continuation."],
            "source": {
                "title": "Governed duplicate fixture",
                "authors": ["AlphaQuest"],
                "year": 2026,
                "link": "https://example.com/duplicate-fixture",
                "doi": None,
                "relevance": "Exercises terminal duplicate closure without loading market data.",
            },
            "economic_edge_fingerprint": {
                "market_behavior": "Completed-bar continuation after an intraday imbalance.",
                "causal_mechanism": "Delayed hedging after the observed completed bar.",
                "signal_inputs": ["Completed OHLCV bars"],
                "market_context": "ES regular trading hours",
                "holding_period": "Next bar open through same-session flatten",
            },
        },
    )
    service.save_duplicate_review(
        "es_closed_duplicate",
        {
            "reviewed_campaign_ids": [],
            "conclusion": "duplicate",
            "substantive_distinction": RATIONALE,
        },
    )


def test_duplicate_fail_closure_is_terminal_immutable_and_hidden_from_live_drafts(tmp_path) -> None:
    service = StudioWorkflowService(tmp_path)
    _duplicate_draft(service)

    result = service.close_duplicate("es_closed_duplicate")

    assert result["verdict"] == "FAIL"
    document = service.store.load("es_closed_duplicate")
    marker = document["closed_before_pnl"]
    assert marker["schema"] == CLOSED_BEFORE_PNL_SCHEMA
    assert marker["status"] == "CLOSED"
    assert marker["research_verdict"] == "FAIL"
    assert len(marker["draft_sha256"]) == 64
    assert service.store.list() == []

    with pytest.raises(ValueError, match="closed before PnL"):
        service.save_duplicate_review(
            "es_closed_duplicate",
            {
                "reviewed_campaign_ids": [],
                "conclusion": "distinct",
                "substantive_distinction": RATIONALE,
            },
        )
    with pytest.raises(ValueError, match="cannot be frozen or published"):
        service.publish("es_closed_duplicate")
    with pytest.raises(ValueError, match="closed before PnL"):
        service.store.save(
            "es_closed_duplicate",
            {**document["draft"], "title": "Silently reopened"},
            wizard_step=3,
        )

    repeated = service.close_duplicate("es_closed_duplicate")
    assert repeated["verdict"] == "FAIL"
    assert repeated["closure"] == marker


def test_duplicate_ledger_fail_closes_mutations_if_marker_write_was_interrupted(tmp_path) -> None:
    service = StudioWorkflowService(tmp_path)
    _duplicate_draft(service)
    service.close_duplicate("es_closed_duplicate")
    path = service.store.path_for("es_closed_duplicate")
    document = json.loads(path.read_text(encoding="utf-8"))
    document.pop("closed_before_pnl")
    path.write_text(json.dumps(document), encoding="utf-8")

    assert service.store.list() == []
    with pytest.raises(ValueError, match="closed before PnL"):
        service.save_brief("es_closed_duplicate", {})
    with pytest.raises(ValueError, match="cannot be frozen or published"):
        service.publish("es_closed_duplicate")
