from __future__ import annotations

import json

import pytest

from alphaquest.studio.ai import OpenAIResearchDraftAdapter


def _suggestion() -> dict:
    return {
        "hypothesis": "Completed-session liquidity stress predicts a measurable next-session futures response.",
        "expected_mechanism": "Risk-constrained liquidity suppliers demand compensation after unusually costly trading conditions.",
        "expected_holding_horizon": "One intraday session",
        "known_failure_modes": ["The premium can disappear when liquidity provision capacity improves."],
        "lookahead_risks": ["The liquidity state must use only values finalized before the signal decision."],
        "missing_questions": ["Which timestamp marks final feature availability?"],
        "economic_edge_fingerprint": {
            "market_behavior": "A completed liquidity stress state precedes a directional intraday futures response.",
            "causal_mechanism": "Inventory-constrained intermediaries require compensation for absorbing one-sided demand.",
            "signal_inputs": "Prior completed-session liquidity and price-impact measures",
            "market_context": "ES regular trading hours after a completed prior session",
            "holding_period": "Open to same-session forced flatten",
        },
    }


def _assert_every_object_property_is_required(schema: object) -> None:
    if isinstance(schema, dict):
        properties = schema.get("properties")
        if isinstance(properties, dict):
            assert set(schema.get("required", [])) == set(properties)
        for value in schema.values():
            _assert_every_object_property_is_required(value)
    elif isinstance(schema, list):
        for value in schema:
            _assert_every_object_property_is_required(value)


def test_openai_adapter_sends_strict_non_stored_text_only_payload():
    captured = {}

    def transport(payload, api_key):
        captured.update(payload)
        assert api_key == "secret"
        return {"output_text": json.dumps(_suggestion())}

    adapter = OpenAIResearchDraftAdapter(model="pinned-model", api_key="secret", transport=transport)
    suggestion, provenance = adapter.suggest(
        "A completed liquidity observation may predict the next session.",
        source_title="Liquidity research",
        instrument="ES",
    )

    assert captured["store"] is False
    assert "tools" not in captured
    assert captured["text"]["format"]["strict"] is True
    assert captured["text"]["format"]["type"] == "json_schema"
    _assert_every_object_property_is_required(captured["text"]["format"]["schema"])
    assert "variant_suggestions" not in suggestion.model_dump(mode="json")
    assert "variant_suggestions" not in captured["text"]["format"]["schema"]["properties"]
    assert provenance.model == "pinned-model"
    assert provenance.store_requested is False
    assert provenance.external_tools_enabled is False
    serialized = json.dumps(captured)
    assert "market data" not in serialized.lower()


def test_openai_adapter_rejects_malformed_or_refused_output():
    malformed = OpenAIResearchDraftAdapter(
        model="pinned-model",
        api_key="secret",
        transport=lambda payload, key: {"output_text": "{}"},
    )
    with pytest.raises(ValueError, match="research-brief schema"):
        malformed.suggest("Long enough notes", source_title="Paper", instrument="ES")

    refused = OpenAIResearchDraftAdapter(
        model="pinned-model",
        api_key="secret",
        transport=lambda payload, key: {
            "output": [{"content": [{"type": "refusal", "refusal": "not available"}]}]
        },
    )
    with pytest.raises(RuntimeError, match="declined"):
        refused.suggest("Long enough notes", source_title="Paper", instrument="NQ")


def test_openai_adapter_is_optional_without_key(monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.setattr("alphaquest.studio.ai.load_api_key", lambda: None)
    adapter = OpenAIResearchDraftAdapter(model="pinned-model")
    with pytest.raises(RuntimeError, match="guided forms remain available"):
        adapter.suggest("Long enough notes", source_title="Paper", instrument="ES")


def test_openai_adapter_rejects_market_data_or_result_tables_before_transport():
    called = False

    def transport(payload, key):
        nonlocal called
        called = True
        return {"output_text": json.dumps(_suggestion())}

    adapter = OpenAIResearchDraftAdapter(model="pinned-model", api_key="secret", transport=transport)
    market_data = (
        "timestamp,open,high,low,close,volume\n"
        "2026-01-02T14:30:00Z,6000,6001,5999,6000.5,10\n"
        "2026-01-02T14:31:00Z,6000.5,6002,6000,6001,12"
    )
    with pytest.raises(ValueError, match="selected prose only"):
        adapter.suggest(market_data, source_title="Local bars", instrument="ES")
    whitespace_market_data = (
        "timestamp open high low close volume\n"
        "2026-01-02T14:30:00Z 6000 6001 5999 6000.5 10\n"
        "2026-01-02T14:31:00Z 6000.5 6002 6000 6001 12"
    )
    with pytest.raises(ValueError, match="selected prose only"):
        adapter.suggest(whitespace_market_data, source_title="Local bars", instrument="ES")
    with pytest.raises(ValueError, match="structured raw/result data"):
        adapter.suggest(
            json.dumps({"net_profit": 1200.0, "profit_factor": 1.4}),
            source_title="Local results",
            instrument="ES",
        )
    with pytest.raises(ValueError, match="observed backtest metrics"):
        adapter.suggest(
            "The observed backtest net profit was $1200 and should be used to improve the setup.",
            source_title="Local results",
            instrument="ES",
        )
    assert called is False
