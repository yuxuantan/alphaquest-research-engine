from __future__ import annotations

from copy import deepcopy
import csv
from datetime import date
import hashlib
import json
from pathlib import Path
import subprocess
import sys

from jsonschema import Draft202012Validator
import pandas as pd
import pytest
import yaml
from pydantic import ValidationError

from alphaquest.authoring import (
    CERTIFIED_MODULE_CATALOG,
    BarRuleV1,
    BarRuleValidationError,
    CampaignCompilationError,
    CampaignCompiler,
    CampaignDraftV1,
    CampaignPublishError,
    PublishResult,
    SafeBarRuleEvaluator,
    TransactionalCampaignPublisher,
    authoring_schema_documents,
    campaign_confirmation_context_sha256,
    validate_bar_rule,
    write_authoring_schemas,
)
from alphaquest.authoring.catalog import ModuleCatalogError
from alphaquest.backtest.engine import BacktestEngine
from alphaquest.research.schemas import validate_campaign_config_contract
from alphaquest.strategy_modules.entry import ENTRY_MODULES, build_entry_module, entry_module_metadata
from alphaquest.studio.ledger import LEDGER_FIELDS, append_planned_publication
from alphaquest.studio.publishing import StudioPublicationService, _publication_file_lock
from alphaquest.studio.variants import suggest_variant_cards


LONG_TEXT = (
    "This predeclared explanation is deliberately longer than eighty characters and documents "
    "causal completed-bar mechanics without using any observed strategy profit results."
)


def _rule() -> dict:
    return {
        "schema": "alphaquest.bar-rule/v1",
        "long_rule": {
            "type": "comparison",
            "operator": "gt",
            "left": {"source": "feature", "name": "close"},
            "right": {"source": "rolling", "feature": "close", "function": "mean", "window": 5, "lag": 1},
        },
    }


def _variant(
    index: int,
    entry: dict,
    *,
    stop: str = "percent_from_entry",
    target: str = "fixed_r",
) -> dict:
    stop_params = (
        {"stop_pct": 0.002}
        if stop == "percent_from_entry"
        else {"dollars_per_contract": 250.0}
        if stop == "fixed_dollar_per_contract"
        else {"stop_points": 10.0}
    )
    return {
        "schema": "alphaquest.variant-draft/v1",
        "variant_id": f"v{index:02d}",
        "title": f"Variant {index}",
        "entry": entry,
        "stop": {"module": stop, "params": stop_params},
        "target": {"module": target, "params": {"target_r_multiple": 1.5}},
        "mechanic_rationale": f"{LONG_TEXT} Mechanic number {index} is frozen independently.",
        "entry_rationale": LONG_TEXT,
        "stop_rationale": LONG_TEXT,
        "target_rationale": LONG_TEXT,
        "timeframe_session_rationale": LONG_TEXT,
        "known_failure_modes": [LONG_TEXT],
        "material_difference": f"{LONG_TEXT} Material distinction number {index} is declared here.",
        "confirmed": True,
    }


def _draft_document() -> dict:
    variants = [
        _variant(
            1,
            {"module": "opening_range_breakout", "params": {}},
            stop="points_from_entry",
        ),
        _variant(2, {"module": "opening_range_breakout", "params": {}}),
        _variant(
            3,
            {"module": "opening_range_breakout", "params": {}},
            stop="fixed_dollar_per_contract",
            target="cost_adjusted_fixed_r",
        ),
        _variant(
            4,
            {"module": "opening_range_breakout", "params": {}},
            stop="points_from_entry",
            target="cost_adjusted_fixed_r",
        ),
        _variant(
            5,
            {"module": "opening_range_breakout", "params": {}},
            stop="fixed_dollar_per_contract",
        ),
    ]
    document = {
        "schema": "alphaquest.campaign-draft/v1",
        "campaign_id": "demo_completed_bar_edge",
        "title": "Demo completed bar edge",
        "created_at": "2026-07-15",
        "instrument": "ES",
        "timeframe": "1m",
        "edge_family": "completed_bar_reversal",
        "hypothesis": LONG_TEXT,
        "expected_mechanism": LONG_TEXT,
        "holding_horizon": "From the next bar open until the declared intraday flatten time.",
        "known_failure_modes": [LONG_TEXT],
        "sources": [
            {
                "title": "A testable market microstructure paper",
                "authors": ["A. Researcher"],
                "year": 2020,
                "link": "https://example.test/research",
                "relevance": LONG_TEXT,
            }
        ],
        "economic_edge_fingerprint": {
            "market_behavior": "Completed bars exhibit a repeatable response after a measurable liquidity shock.",
            "causal_mechanism": "Liquidity suppliers adjust quotes slowly after a completed and observable price shock.",
            "signal_inputs": ["Completed OHLCV bars and explicitly declared regular-session state"],
            "market_context": "Highly liquid ES regular trading hours under the configured continuous roll policy.",
            "holding_period": "Intraday from the next bar open until the fixed pre-close forced flatten.",
        },
        "duplicate_review": {
            "reviewed_campaign_ids": [],
            "ledger_queries": ["completed bar liquidity shock ES"],
            "conclusion": "distinct",
            "substantive_distinction": LONG_TEXT,
        },
        "dataset": {
            "schema": "alphaquest.dataset-manifest/v1",
            "dataset_id": "governed_es_1m",
            "source": "csv",
            "path": "data/raw/ES/governed_es_1m.csv",
            "symbol": "ES",
            "timeframe": "1m",
            "timezone": "America/New_York",
            "exchange_timezone": "America/New_York",
            "timestamp_semantics": "bar_open",
            "source_sha256": "a" * 64,
            "canonical_sha256": "b" * 64,
            "coverage_start": "2020-01-01",
            "coverage_end": "2025-12-31",
            "roll_policy": "Explicit non-back-adjusted roll calendar reviewed before testing.",
            "row_count": 1000,
            "quality_verdict": "PASS",
        },
        "execution": {
            "tick_size": 0.25,
            "point_value": 50.0,
            "tick_value": 12.5,
            "commission_per_contract": 2.5,
            "slippage_ticks": 1.0,
            "prop_profile": "reviewed_local_profile",
        },
        "variants": variants,
        "certified_recipe": "opening_range_breakout",
        "frozen": True,
    }
    document["confirmation_context_sha256"] = campaign_confirmation_context_sha256(document)
    return document


def _reconfirm(document: dict) -> dict:
    document["confirmation_context_sha256"] = campaign_confirmation_context_sha256(document)
    return document


def _event_draft_document() -> dict:
    document = _draft_document()
    document["authoring_lane"] = "certified_event_replay"
    document["certified_recipe"] = None
    document["event_strategy"] = "yush_orderflow_range"
    document["dataset"].update(
        {
            "continuous_contract": "explicit_roll_calendar",
            "contract_column": "contract_symbol",
            "contract_count": 2,
            "roll_calendar": "data/reference/ES/roll.csv",
            "roll_calendar_sha256": "c" * 64,
            "event_source": {
                "source": "databento_zip_trades",
                "archive": "data/raw/ES/trades.zip",
                "archive_sha256": "d" * 64,
                "roll_calendar": "data/reference/ES/roll.csv",
                "roll_calendar_sha256": "c" * 64,
                "root_symbol": "ES",
                "aggregation_ms": 100,
                "overnight_start": "16:00:00",
                "rth_start": "09:30:00",
                "rth_end": "16:00:00",
                "reset_previous_levels_on_roll": True,
            },
        }
    )
    document["variants"] = [
        {
            "schema": "alphaquest.variant-draft/v1",
            "variant_id": "v01",
            "title": "Certified event variant",
            "entry": {"module": "yush_orderflow_range", "params": {"mechanics": {}}},
            "stop": {"module": "event_aoi_structural_stop", "params": {}},
            "target": {"module": "event_value_area_management", "params": {}},
            "mechanic_rationale": LONG_TEXT,
            "entry_rationale": LONG_TEXT,
            "stop_rationale": LONG_TEXT,
            "target_rationale": LONG_TEXT,
            "timeframe_session_rationale": LONG_TEXT,
            "known_failure_modes": [LONG_TEXT],
            "material_difference": LONG_TEXT,
            "confirmed": True,
        }
    ]
    return _reconfirm(document)


def test_event_campaign_compilation_embeds_current_strategy_certification():
    compiled = CampaignCompiler(project_root=Path(__file__).resolve().parents[1]).compile(
        CampaignDraftV1.model_validate(_event_draft_document())
    )
    config = compiled.variant_configs["v01"]
    identity = config["strategy_certification"]

    assert identity["strategy_id"] == "yush_orderflow_range"
    assert identity["implementation_version"] == 4
    assert len(identity["implementation_sha256"]) == 64
    assert compiled.strategy_spec["strategy_certification"]["implementation_sha256"] == identity[
        "implementation_sha256"
    ]
    assert compiled.authoring_manifest["strategy_certification"]["manifest_sha256"] == identity[
        "manifest_sha256"
    ]


def test_event_campaign_compiles_one_canonical_grid_for_core_and_wfa():
    document = _event_draft_document()
    document["variants"][0]["event_parameter_grid"] = {
        "max_aoi_width_points": [3, 4, 5, 6],
        "entry_offset_ticks": [0, 1, 2, 3, 4],
        "stop_offset_ticks": [0, 1, 2, 3, 4],
    }
    _reconfirm(document)

    compiled = CampaignCompiler(project_root=Path(__file__).resolve().parents[1]).compile(
        CampaignDraftV1.model_validate(document)
    )
    config = compiled.variant_configs["v01"]

    assert config["core_grid"]["parameters"] == config["wfa"]["parameters"]
    assert config["core_grid"]["parameters"] == {
        "event.params.max_aoi_width_points": [3, 4, 5, 6],
        "event.params.entry_offset_ticks": [0, 1, 2, 3, 4],
        "event.params.stop_offset_ticks": [0, 1, 2, 3, 4],
    }
    assert config["strategy"]["event"]["params"]["max_aoi_width_points"] == 3.0
    assert len(config["strategy"]["event"]["params"]) == 24


def _governed_publication_draft(root: Path) -> CampaignDraftV1:
    document = _draft_document()
    dataset = root / "research/datasets/governed_es_1m/bars.csv"
    dataset.parent.mkdir(parents=True)
    dataset.write_text("timestamp,open,high,low,close,volume\n", encoding="utf-8")
    digest = hashlib.sha256(dataset.read_bytes()).hexdigest()
    document["dataset"]["path"] = str(dataset.relative_to(root))
    document["dataset"]["source_sha256"] = digest
    document["dataset"]["canonical_sha256"] = digest
    _reconfirm(document)
    draft = CampaignDraftV1.model_validate(document)
    (dataset.parent / "dataset_manifest.json").write_text(
        json.dumps(draft.dataset.model_dump(mode="json", by_alias=True), indent=2) + "\n",
        encoding="utf-8",
    )
    return draft


def _ledger_record(
    campaign_id: str,
    *,
    stage: str,
    result: str,
    config_path: str,
) -> dict[str, str]:
    return {
        "timestamp": "2026-07-15T00:00:00+00:00",
        "campaign_id": campaign_id,
        "variant_id": "",
        "instrument": "ES",
        "timeframe": "1m",
        "edge": "Ledger transaction fixture",
        "variant_mechanic": "Fixture row",
        "parameter_space": "none",
        "data_scope": "fixture",
        "config_path": config_path,
        "report_path": "",
        "stage": stage,
        "result": result,
        "decision": "TEST",
        "failure_reason": "",
        "rescue_attempt": "none",
    }


def _write_ledger(path: Path, rows: list[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=LEDGER_FIELDS)
        writer.writeheader()
        writer.writerows(rows)


def test_campaign_draft_is_strict_allows_one_to_five_distinct_variants():
    document = _draft_document()
    assert len(CampaignDraftV1.model_validate(document).variants) == 5

    extra = deepcopy(document)
    extra["unexpected"] = True
    with pytest.raises(ValidationError, match="extra_forbidden"):
        CampaignDraftV1.model_validate(extra)

    sequential = deepcopy(document)
    sequential["variant_protocol"] = "sequential_failure_informed"
    sequential["variants"] = sequential["variants"][:1]
    sequential["sequential_variant_history"] = []
    _reconfirm(sequential)
    assert len(CampaignDraftV1.model_validate(sequential).variants) == 1

    too_many = deepcopy(document)
    extra_variant = deepcopy(too_many["variants"][-1])
    extra_variant["variant_id"] = "v06"
    too_many["variants"].append(extra_variant)
    with pytest.raises(ValidationError, match="at most 5 items"):
        CampaignDraftV1.model_validate(too_many)

    duplicate = deepcopy(document)
    duplicate["variants"][1]["entry"] = deepcopy(duplicate["variants"][0]["entry"])
    duplicate["variants"][1]["stop"] = deepcopy(duplicate["variants"][0]["stop"])
    duplicate["variants"][1]["target"] = deepcopy(duplicate["variants"][0]["target"])
    with pytest.raises(ValidationError, match="materially distinct"):
        CampaignDraftV1.model_validate(duplicate)

    stale = deepcopy(document)
    stale["hypothesis"] = stale["hypothesis"] + " Materially revised after confirmation."
    with pytest.raises(ValidationError, match="confirmations are stale"):
        CampaignDraftV1.model_validate(stale)


def test_certified_suggestions_hold_one_edge_fixed_across_five_risk_expressions():
    document = _draft_document()
    cards = suggest_variant_cards(document)

    assert len(cards) == 5
    assert {card["entry"]["module"] for card in cards} == {"opening_range_breakout"}
    assert len(
        {
            (card["stop"]["module"], card["target"]["module"])
            for card in cards
        }
    ) == 5

    crossed_edge = deepcopy(document)
    crossed_edge["variants"][0]["entry"] = {
        "module": "calendar_session_bias",
        "params": {"weekday_directions": {0: "long"}},
    }
    _reconfirm(crossed_edge)
    with pytest.raises(ValidationError, match="one edge"):
        CampaignDraftV1.model_validate(crossed_edge)


def test_publication_requires_review_of_similarity_matches_not_only_exact_fingerprints(tmp_path):
    prior = tmp_path / "research/campaigns/archive/prior_completed_bar_edge"
    prior.mkdir(parents=True)
    (prior / "campaign.yaml").write_text(
        yaml.safe_dump(
            {
                "campaign_id": "prior_completed_bar_edge",
                "title": "Demo completed bar edge",
                "hypothesis": LONG_TEXT,
                "expected_mechanism": LONG_TEXT,
            }
        ),
        encoding="utf-8",
    )
    document = _draft_document()
    service = StudioPublicationService(tmp_path)

    with pytest.raises(ValueError, match="unreviewed deterministic duplicate matches"):
        service._duplicate_guard(CampaignDraftV1.model_validate(document))

    document["duplicate_review"]["reviewed_campaign_ids"] = ["prior_completed_bar_edge"]
    _reconfirm(document)
    service._duplicate_guard(CampaignDraftV1.model_validate(document))


def test_publication_duplicate_review_has_no_hidden_ten_match_ceiling(tmp_path):
    prior_ids = []
    for index in range(12):
        campaign_id = f"prior_completed_bar_edge_{index:02d}"
        prior_ids.append(campaign_id)
        prior = tmp_path / "research/campaigns/archive" / campaign_id
        prior.mkdir(parents=True)
        (prior / "campaign.yaml").write_text(
            yaml.safe_dump(
                {
                    "campaign_id": campaign_id,
                    "title": "Demo completed bar edge",
                    "hypothesis": LONG_TEXT,
                    "expected_mechanism": LONG_TEXT,
                }
            ),
            encoding="utf-8",
        )
    document = _draft_document()
    document["duplicate_review"]["reviewed_campaign_ids"] = prior_ids[:10]
    _reconfirm(document)
    service = StudioPublicationService(tmp_path)

    with pytest.raises(ValueError, match=prior_ids[10]):
        service._duplicate_guard(CampaignDraftV1.model_validate(document))

    document["duplicate_review"]["reviewed_campaign_ids"] = prior_ids
    _reconfirm(document)
    service._duplicate_guard(CampaignDraftV1.model_validate(document))


def test_studio_publication_appends_planned_ledger_and_recovery_journal(tmp_path, monkeypatch):
    document = _draft_document()
    dataset = tmp_path / "research/datasets/governed_es_1m/bars.csv"
    dataset.parent.mkdir(parents=True)
    dataset.write_text("timestamp,open,high,low,close,volume\n", encoding="utf-8")
    digest = hashlib.sha256(dataset.read_bytes()).hexdigest()
    document["dataset"]["path"] = str(dataset.relative_to(tmp_path))
    document["dataset"]["source_sha256"] = digest
    document["dataset"]["canonical_sha256"] = digest
    _reconfirm(document)
    draft = CampaignDraftV1.model_validate(document)
    (dataset.parent / "dataset_manifest.json").write_text(
        json.dumps(draft.dataset.model_dump(mode="json", by_alias=True), indent=2) + "\n",
        encoding="utf-8",
    )
    (dataset.parent / "dataset_manifest.json").write_text(
        json.dumps(draft.dataset.model_dump(mode="json", by_alias=True), indent=2) + "\n",
        encoding="utf-8",
    )

    class FakePublisher:
        def __init__(self, **kwargs):
            self.root = Path(kwargs["active_campaign_root"])
            self.guard = kwargs["duplicate_guard"]

        def publish(self, compiled):
            self.guard(compiled.draft)
            destination = self.root / compiled.campaign_id
            destination.mkdir(parents=True)
            path = destination / "campaign.yaml"
            path.write_text("campaign_id: demo_completed_bar_edge\n", encoding="utf-8")
            from alphaquest.authoring import PublishResult

            return PublishResult(
                campaign_id=compiled.campaign_id,
                destination=destination,
                files=(path,),
                file_sha256={"campaign.yaml": hashlib.sha256(path.read_bytes()).hexdigest()},
                draft_sha256=compiled.draft_sha256,
            )

    monkeypatch.setattr("alphaquest.studio.publishing.TransactionalCampaignPublisher", FakePublisher)
    monkeypatch.setattr(
        "alphaquest.studio.publishing.refresh_generated_indexes_if_stale",
        lambda _root, *, force=False: {"refreshed": force},
    )

    result = StudioPublicationService(tmp_path).publish(draft)

    assert result.ledger_rows_appended == 6
    with (tmp_path / "research_ledger.csv").open(newline="", encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))
    assert len(rows) == 6
    assert {row["variant_id"] for row in rows} == {"", "v01", "v02", "v03", "v04", "v05"}
    journal = json.loads(result.journal_path.read_text(encoding="utf-8"))
    assert journal["state"] == "COMPLETED"
    assert journal["destination"] == "research/campaigns/active/demo_completed_bar_edge"
    assert journal["draft_sha256"] == result.draft_sha256
    backup = tmp_path / journal["ledger_backup_path"]
    assert backup.is_file()
    assert hashlib.sha256(backup.read_bytes()).hexdigest() == journal["ledger_backup_sha256"]


def test_publication_file_lock_is_visible_to_another_process(tmp_path):
    lock_path = tmp_path / "run-store/studio-runtime/publication.lock"
    probe = (
        "import fcntl, pathlib, sys; "
        "handle = pathlib.Path(sys.argv[1]).open('a+b'); "
        "\ntry:\n fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)"
        "\nexcept BlockingIOError:\n sys.exit(23)"
        "\nelse:\n sys.exit(0)"
    )

    with _publication_file_lock(lock_path):
        completed = subprocess.run(
            [sys.executable, "-c", probe, str(lock_path)],
            check=False,
            capture_output=True,
            text=True,
        )

    assert completed.returncode == 23, completed.stderr


def test_explicit_publication_recovery_preserves_later_committed_ledger_rows(tmp_path, monkeypatch):
    draft = _governed_publication_draft(tmp_path)
    service = StudioPublicationService(tmp_path)
    compiled = service._compiler().compile(draft)
    ledger = tmp_path / "research_ledger.csv"
    baseline = _ledger_record(
        "existing_campaign",
        stage="full_staged_methodology",
        result="FAIL",
        config_path="research/campaigns/archive/existing/campaign.yaml",
    )
    _write_ledger(ledger, [baseline])
    before = ledger.read_bytes()
    service.journal_root.mkdir(parents=True)
    backup = service.journal_root / "crashed.ledger.bak"
    backup.write_bytes(before)
    destination = service.layout.active_campaign_root / draft.campaign_id
    destination.mkdir(parents=True)
    (destination / "authoring_manifest.json").write_text(
        json.dumps({"draft_sha256": compiled.draft_sha256}) + "\n",
        encoding="utf-8",
    )
    append_planned_publication(
        draft,
        project_root=tmp_path,
        active_campaign_root=service.layout.active_campaign_root,
    )
    concurrent = _ledger_record(
        "concurrent_committed_campaign",
        stage="full_staged_methodology",
        result="PASS",
        config_path="research/campaigns/active/concurrent/campaign.yaml",
    )
    with ledger.open("a", newline="", encoding="utf-8") as handle:
        csv.DictWriter(handle, fieldnames=LEDGER_FIELDS).writerow(concurrent)
    journal_path = service.journal_root / "crashed.json"
    journal_path.write_text(
        json.dumps(
            {
                "schema": "alphaquest.studio-publication-journal/v1",
                "transaction_id": "crashed",
                "campaign_id": draft.campaign_id,
                "draft_sha256": compiled.draft_sha256,
                "destination": str(destination.relative_to(tmp_path)),
                "ledger_path": "research_ledger.csv",
                "ledger_backup_path": str(backup.relative_to(tmp_path)),
                "ledger_existed_before": True,
                "ledger_before_sha256": hashlib.sha256(before).hexdigest(),
                "ledger_backup_sha256": hashlib.sha256(before).hexdigest(),
                "state": "PREPARING",
                "research_verdict": None,
                "steps": [],
            }
        ),
        encoding="utf-8",
    )
    refresh_calls = []
    monkeypatch.setattr(
        "alphaquest.studio.publishing.refresh_generated_indexes_if_stale",
        lambda root, *, force=False: refresh_calls.append((Path(root), force)) or {"refreshed": True},
    )

    recovered = service.recover()

    assert recovered[0]["state"] == "ROLLED_BACK"
    assert not destination.exists()
    with ledger.open(newline="", encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))
    assert {row["campaign_id"] for row in rows} == {
        "existing_campaign",
        "concurrent_committed_campaign",
    }
    journal = json.loads(journal_path.read_text(encoding="utf-8"))
    assert journal["state"] == "ROLLED_BACK"
    assert any(step.get("mode") == "transaction_rows_removed_preserving_concurrent_rows" for step in journal["steps"])
    assert refresh_calls == [(tmp_path.resolve(), True)]


def test_incomplete_publication_recovery_is_needs_manual_review(tmp_path, monkeypatch):
    draft = _governed_publication_draft(tmp_path)
    service = StudioPublicationService(tmp_path)
    compiled = service._compiler().compile(draft)
    service.journal_root.mkdir(parents=True)
    backup = service.journal_root / "unsafe.ledger.bak"
    backup.write_bytes(b"")
    destination = service.layout.active_campaign_root / draft.campaign_id
    destination.mkdir(parents=True)
    (destination / "authoring_manifest.json").write_text(
        json.dumps({"draft_sha256": "f" * 64}) + "\n",
        encoding="utf-8",
    )
    journal_path = service.journal_root / "unsafe.json"
    journal_path.write_text(
        json.dumps(
            {
                "schema": "alphaquest.studio-publication-journal/v1",
                "transaction_id": "unsafe",
                "campaign_id": draft.campaign_id,
                "draft_sha256": compiled.draft_sha256,
                "destination": str(destination.relative_to(tmp_path)),
                "ledger_path": "research_ledger.csv",
                "ledger_backup_path": str(backup.relative_to(tmp_path)),
                "ledger_existed_before": False,
                "ledger_before_sha256": hashlib.sha256(b"").hexdigest(),
                "ledger_backup_sha256": hashlib.sha256(b"").hexdigest(),
                "state": "PREPARING",
                "research_verdict": None,
                "steps": [],
            }
        ),
        encoding="utf-8",
    )
    refresh_calls = []
    monkeypatch.setattr(
        "alphaquest.studio.publishing.refresh_generated_indexes_if_stale",
        lambda root, *, force=False: refresh_calls.append((Path(root), force)) or {"refreshed": True},
    )

    with pytest.raises(RuntimeError, match="NEEDS MANUAL REVIEW"):
        service.recover()

    assert destination.is_dir()
    journal = json.loads(journal_path.read_text(encoding="utf-8"))
    assert journal["state"] == "NEEDS MANUAL REVIEW"
    assert journal["research_verdict"] == "NEEDS MANUAL REVIEW"
    assert "refusing destructive rollback" in journal["rollback_errors"][0]
    assert refresh_calls == [(tmp_path.resolve(), True)]


def test_publish_recovers_abandoned_preparing_transaction_before_new_mutation(tmp_path, monkeypatch):
    draft = _governed_publication_draft(tmp_path)
    service = StudioPublicationService(tmp_path)
    compiled = service._compiler().compile(draft)
    service.journal_root.mkdir(parents=True)
    backup = service.journal_root / "abandoned.ledger.bak"
    backup.write_bytes(b"")
    destination = service.layout.active_campaign_root / draft.campaign_id
    destination.mkdir(parents=True)
    (destination / "authoring_manifest.json").write_text(
        json.dumps({"draft_sha256": compiled.draft_sha256}) + "\n",
        encoding="utf-8",
    )
    abandoned = service.journal_root / "abandoned.json"
    abandoned.write_text(
        json.dumps(
            {
                "schema": "alphaquest.studio-publication-journal/v1",
                "transaction_id": "abandoned",
                "campaign_id": draft.campaign_id,
                "draft_sha256": compiled.draft_sha256,
                "destination": str(destination.relative_to(tmp_path)),
                "ledger_path": "research_ledger.csv",
                "ledger_backup_path": str(backup.relative_to(tmp_path)),
                "ledger_existed_before": False,
                "ledger_before_sha256": hashlib.sha256(b"").hexdigest(),
                "ledger_backup_sha256": hashlib.sha256(b"").hexdigest(),
                "state": "PREPARING",
                "research_verdict": None,
                "steps": [],
            }
        ),
        encoding="utf-8",
    )
    refresh_calls = []
    monkeypatch.setattr(
        "alphaquest.studio.publishing.refresh_generated_indexes_if_stale",
        lambda root, *, force=False: refresh_calls.append((Path(root), force)) or {"refreshed": True},
    )

    class FakePublisher:
        def __init__(self, **kwargs):
            self.root = Path(kwargs["active_campaign_root"])

        def publish(self, candidate):
            target = self.root / candidate.campaign_id
            target.mkdir(parents=True)
            manifest = target / "authoring_manifest.json"
            manifest.write_text(
                json.dumps({"draft_sha256": candidate.draft_sha256}) + "\n",
                encoding="utf-8",
            )
            return PublishResult(
                campaign_id=candidate.campaign_id,
                destination=target,
                files=(manifest,),
                file_sha256={"authoring_manifest.json": hashlib.sha256(manifest.read_bytes()).hexdigest()},
                draft_sha256=candidate.draft_sha256,
            )

    monkeypatch.setattr("alphaquest.studio.publishing.TransactionalCampaignPublisher", FakePublisher)

    result = service.publish(draft)

    assert result.destination.is_dir()
    assert json.loads(abandoned.read_text(encoding="utf-8"))["state"] == "ROLLED_BACK"
    completed = [
        json.loads(path.read_text(encoding="utf-8"))
        for path in service.journal_root.glob("*.json")
        if path != abandoned
    ]
    assert len(completed) == 1 and completed[0]["state"] == "COMPLETED"
    assert refresh_calls == [(tmp_path.resolve(), True), (tmp_path.resolve(), True)]


def test_refresh_failure_rolls_back_and_force_rebuilds_indexes(tmp_path, monkeypatch):
    draft = _governed_publication_draft(tmp_path)
    calls = []

    class FakePublisher:
        def __init__(self, **kwargs):
            self.root = Path(kwargs["active_campaign_root"])

        def publish(self, candidate):
            destination = self.root / candidate.campaign_id
            destination.mkdir(parents=True)
            manifest = destination / "authoring_manifest.json"
            manifest.write_text(
                json.dumps({"draft_sha256": candidate.draft_sha256}) + "\n",
                encoding="utf-8",
            )
            return PublishResult(
                campaign_id=candidate.campaign_id,
                destination=destination,
                files=(manifest,),
                file_sha256={"authoring_manifest.json": hashlib.sha256(manifest.read_bytes()).hexdigest()},
                draft_sha256=candidate.draft_sha256,
            )

    def refresh(root, *, force=False):
        calls.append((Path(root), force))
        if len(calls) == 1:
            raise RuntimeError("injected publication refresh failure")
        return {"refreshed": True}

    monkeypatch.setattr(
        "alphaquest.studio.publishing.refresh_generated_indexes_if_stale",
        refresh,
    )
    monkeypatch.setattr("alphaquest.studio.publishing.TransactionalCampaignPublisher", FakePublisher)
    service = StudioPublicationService(tmp_path)

    with pytest.raises(RuntimeError, match="injected publication refresh failure"):
        service.publish(draft)

    assert not (service.layout.active_campaign_root / draft.campaign_id).exists()
    assert not (tmp_path / "research_ledger.csv").exists()
    journal_paths = list(service.journal_root.glob("*.json"))
    assert len(journal_paths) == 1
    journal = json.loads(journal_paths[0].read_text(encoding="utf-8"))
    assert journal["state"] == "ROLLED_BACK"
    assert any(step["name"] == "registry_and_views_rebuilt_after_rollback" for step in journal["steps"])
    assert calls == [(tmp_path.resolve(), True), (tmp_path.resolve(), True)]


def test_fresh_workspace_draft_passes_same_preflight_before_freeze_and_publication(tmp_path):
    from alphaquest.studio.data_import import DataImportSpec, DatasetImporter

    source = tmp_path / "research-notes-bars.csv"
    timestamps = pd.date_range("2026-01-05 09:30:00", periods=60, freq="min")
    pd.DataFrame(
        {
            "timestamp": timestamps.astype(str),
            "open": [6000.0 + index * 0.25 for index in range(60)],
            "high": [6001.0 + index * 0.25 for index in range(60)],
            "low": [5999.0 + index * 0.25 for index in range(60)],
            "close": [6000.5 + index * 0.25 for index in range(60)],
            "volume": [100 + index for index in range(60)],
        }
    ).to_csv(source, index=False)
    imported = DatasetImporter(tmp_path).import_file(
        source,
        DataImportSpec(
            dataset_id="governed_es_1m",
            symbol="ES",
            timeframe="1m",
            timezone="America/New_York",
            timestamp_semantics="bar_open",
            roll_policy="single_contract",
            timestamp_column="timestamp",
            open_column="open",
            high_column="high",
            low_column="low",
            close_column="close",
            volume_column="volume",
            single_contract_confirmed=True,
        ),
    )
    document = _draft_document()
    document["dataset"] = imported.manifest.model_dump(mode="json", by_alias=True)
    _reconfirm(document)
    draft = CampaignDraftV1.model_validate(document)
    service = StudioPublicationService(tmp_path)

    preflight = service.preflight_draft(draft)
    published = service.publish(draft)

    assert preflight["preflight_verdict"] == "PASS"
    assert preflight["variant_count"] == 5
    assert published.destination == tmp_path / "research/campaigns/active/demo_completed_bar_edge"
    assert len(list(published.destination.glob("variants/*/config.yaml"))) == 5
    assert published.ledger_rows_appended == 6


def test_publication_rejects_draft_dataset_metadata_that_differs_from_governed_manifest(tmp_path):
    dataset = tmp_path / "research/datasets/governed_es_1m/bars.csv"
    dataset.parent.mkdir(parents=True)
    dataset.write_text(
        "timestamp,open,high,low,close,volume\n2026-01-05T14:30:00Z,100,101,99,100.5,10\n",
        encoding="utf-8",
    )
    digest = hashlib.sha256(dataset.read_bytes()).hexdigest()
    document = _draft_document()
    document["dataset"].update(
        {
            "path": str(dataset.relative_to(tmp_path)),
            "source_sha256": digest,
            "canonical_sha256": digest,
            "quality_notes": ["Draft-only claim that was not in the governed intake manifest."],
        }
    )
    _reconfirm(document)
    draft = CampaignDraftV1.model_validate(document)
    governed = draft.dataset.model_copy(update={"quality_notes": []})
    (dataset.parent / "dataset_manifest.json").write_text(
        json.dumps(governed.model_dump(mode="json", by_alias=True), indent=2) + "\n",
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="differs from the governed dataset manifest"):
        StudioPublicationService(tmp_path).preflight_draft(draft)


def test_publication_rechecks_governed_roll_calendar_hash(tmp_path):
    from alphaquest.studio.data_import import DataImportSpec, DatasetImporter

    source = tmp_path / "multi-contract.csv"
    pd.DataFrame(
        {
            "timestamp": [
                "2026-01-05 09:30:00",
                "2026-01-05 09:30:00",
                "2026-01-05 09:31:00",
                "2026-01-05 09:31:00",
            ],
            "open": [6000.0, 6001.0, 6000.5, 6001.5],
            "high": [6001.0, 6002.0, 6001.5, 6002.5],
            "low": [5999.0, 6000.0, 5999.5, 6000.5],
            "close": [6000.5, 6001.5, 6001.0, 6002.0],
            "volume": [10, 100, 10, 100],
            "contract": ["ESH26", "ESM26", "ESH26", "ESM26"],
        }
    ).to_csv(source, index=False)
    roll_calendar = tmp_path / "roll-calendar.csv"
    pd.DataFrame(
        {
            "start_timestamp": ["2026-01-05 09:00:00"],
            "contract_symbol": ["ESM26"],
        }
    ).to_csv(roll_calendar, index=False)
    imported = DatasetImporter(tmp_path).import_file(
        source,
        DataImportSpec(
            dataset_id="governed_es_1m",
            symbol="ES",
            timeframe="1m",
            timezone="America/New_York",
            timestamp_semantics="bar_open",
            roll_policy="explicit_roll_calendar",
            roll_calendar_path=str(roll_calendar),
            timestamp_column="timestamp",
            open_column="open",
            high_column="high",
            low_column="low",
            close_column="close",
            volume_column="volume",
            contract_column="contract",
        ),
    )
    document = _draft_document()
    document["dataset"] = imported.manifest.model_dump(mode="json", by_alias=True)
    _reconfirm(document)
    draft = CampaignDraftV1.model_validate(document)
    assert imported.roll_calendar_path is not None

    imported.roll_calendar_path.write_text(
        "start_timestamp,contract_symbol\n2026-01-05T14:00:00+00:00,ESH26\n",
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="roll calendar hash changed after review"):
        StudioPublicationService(tmp_path).preflight_draft(draft)


def test_dataset_manifest_fails_closed_on_objective_row_defects():
    document = _draft_document()
    document["dataset"]["duplicate_count"] = 1
    with pytest.raises(ValidationError, match="cannot have PASS quality"):
        CampaignDraftV1.model_validate(document)


def test_certified_catalog_contains_only_initial_studio_allowlist_and_rejects_unknown_params():
    names = {(item.module_type, item.name) for item in CERTIFIED_MODULE_CATALOG.all()}
    assert names == {
        ("entry", "safe_bar_rule"),
        ("entry", "calendar_session_bias"),
        ("entry", "opening_range_breakout"),
        ("entry", "daily_time_series_momentum"),
        ("entry", "yush_orderflow_range"),
        ("sl", "points_from_entry"),
        ("sl", "percent_from_entry"),
        ("sl", "fixed_dollar_per_contract"),
        ("sl", "event_aoi_structural_stop"),
        ("tp", "fixed_r"),
        ("tp", "cost_adjusted_fixed_r"),
        ("tp", "event_value_area_management"),
    }
    safe_manifest = CERTIFIED_MODULE_CATALOG.get("entry", "safe_bar_rule")
    assert safe_manifest.parameters["certified_features"].value_type == "array"
    with pytest.raises(ModuleCatalogError, match="unknown parameters"):
        CERTIFIED_MODULE_CATALOG.validate_binding(
            "entry",
            {"module": "calendar_session_bias", "params": {"weekday_directions": {}, "eval": "bad"}},
        )
    assert CERTIFIED_MODULE_CATALOG.certification_status("entry", "pdh_pdl_sweep_reclaim") == "developer_only"
    assert CERTIFIED_MODULE_CATALOG.describe("entry", "pdh_pdl_sweep_reclaim").certification_status == "developer_only"
    with pytest.raises(ModuleCatalogError, match="developer-only"):
        CERTIFIED_MODULE_CATALOG.get("entry", "pdh_pdl_sweep_reclaim")

    tunable_rule = {
        "schema": "alphaquest.bar-rule/v1",
        "long_rule": {
            "type": "comparison",
            "operator": "gt",
            "left": {"source": "feature", "name": "close"},
            "right": {"source": "tunable", "name": "threshold"},
        },
        "tunables": [
            {"name": "threshold", "value_type": "number", "values": [10.0, 20.0], "default": 10.0}
        ],
    }
    with pytest.raises(ModuleCatalogError, match="must match exactly"):
        CERTIFIED_MODULE_CATALOG.validate_binding(
            "entry",
            {"module": "safe_bar_rule", "params": {"rule": tunable_rule}},
        )


def test_bar_rule_uses_only_current_or_lagged_certified_features():
    validate_bar_rule(_rule())
    custom = deepcopy(_rule())
    custom["long_rule"]["left"]["name"] = "reviewed_feature"
    with pytest.raises(BarRuleValidationError, match="not causally certified"):
        validate_bar_rule(custom)
    validate_bar_rule(custom, certified_features={"reviewed_feature"})

    future = deepcopy(custom)
    future["long_rule"]["left"]["name"] = "session_final_high"
    with pytest.raises(BarRuleValidationError, match="prohibited"):
        validate_bar_rule(future, certified_features={"session_final_high"})

    negative_lag = deepcopy(_rule())
    negative_lag["long_rule"]["left"]["lag"] = -1
    with pytest.raises(BarRuleValidationError, match="greater than or equal to 0"):
        validate_bar_rule(negative_lag)


def test_bar_rule_is_incremental_missing_safe_and_resolves_simultaneous_signals_to_none():
    rule = {
        "schema": "alphaquest.bar-rule/v1",
        "long_rule": {
            "type": "comparison",
            "operator": "gt",
            "left": {"source": "feature", "name": "close"},
            "right": {"source": "rolling", "feature": "close", "function": "mean", "window": 2, "lag": 1},
        },
        "short_rule": {
            "type": "comparison",
            "operator": "lt",
            "left": {"source": "feature", "name": "close"},
            "right": {"source": "rolling", "feature": "close", "function": "mean", "window": 2, "lag": 1},
        },
    }
    evaluator = SafeBarRuleEvaluator(rule)
    assert evaluator.evaluate({"close": 10.0}) is None
    assert evaluator.evaluate({"close": 10.0}) is None
    assert evaluator.evaluate({"close": 12.0}) == "long"
    assert evaluator.evaluate({"close": 8.0}) == "short"
    assert SafeBarRuleEvaluator(rule).evaluate({}) is None

    negated_missing = {
        "schema": "alphaquest.bar-rule/v1",
        "long_rule": {
            "type": "not",
            "condition": {
                "type": "comparison",
                "operator": "gt",
                "left": {"source": "feature", "name": "close"},
                "right": {"source": "constant", "value": 10.0},
            },
        },
    }
    assert SafeBarRuleEvaluator(negated_missing).evaluate({}) is None

    both = deepcopy(rule)
    both["short_rule"] = deepcopy(both["long_rule"])
    simultaneous = SafeBarRuleEvaluator(both)
    simultaneous.evaluate({"close": 10.0})
    simultaneous.evaluate({"close": 10.0})
    assert simultaneous.evaluate({"close": 12.0}) is None


def test_bar_rule_crossing_and_tunable_values_are_predeclared_and_typed():
    rule = {
        "schema": "alphaquest.bar-rule/v1",
        "long_rule": {
            "type": "cross",
            "direction": "above",
            "left": {"source": "feature", "name": "close"},
            "right": {"source": "tunable", "name": "threshold"},
        },
        "tunables": [{"name": "threshold", "value_type": "number", "values": [10.0, 20.0], "default": 10.0}],
    }
    evaluator = SafeBarRuleEvaluator(rule)
    assert evaluator.evaluate({"close": 9.0}) is None
    assert evaluator.evaluate({"close": 11.0}) == "long"
    with pytest.raises(BarRuleValidationError, match="predeclared typed values"):
        SafeBarRuleEvaluator(rule, tunable_values={"threshold": 15.0})


def test_safe_bar_rule_is_registered_and_emits_only_after_completed_bar():
    assert "safe_bar_rule" in ENTRY_MODULES
    metadata = entry_module_metadata("safe_bar_rule")
    assert metadata.decision_timing == "bar_close"
    assert metadata.required_detail_granularity is None
    module = build_entry_module(
        {
            "module": "safe_bar_rule",
            "params": {
                "rule": {
                    "schema": "alphaquest.bar-rule/v1",
                    "long_rule": {
                        "type": "comparison",
                        "operator": "gt",
                        "left": {"source": "feature", "name": "close"},
                        "right": {"source": "feature", "name": "open"},
                    },
                    "bar_interval_minutes": 1.0,
                }
            },
        }
    )
    signal = module.on_bar_close(
        pd.Series(
            {
                "timestamp": pd.Timestamp("2026-01-05 09:30:00", tz="America/New_York"),
                "session_date": "2026-01-05",
                "is_rth": True,
                "open": 100.0,
                "high": 102.0,
                "low": 99.0,
                "close": 101.0,
                "volume": 1000.0,
            }
        )
    )
    assert signal is not None
    assert signal.direction == "long"
    assert signal.reclaim_timestamp == pd.Timestamp("2026-01-05 09:31:00", tz="America/New_York")


def test_safe_bar_rule_backtest_enters_at_next_bar_open():
    rule = {
        "schema": "alphaquest.bar-rule/v1",
        "long_rule": {
            "type": "comparison",
            "operator": "gt",
            "left": {"source": "feature", "name": "close"},
            "right": {"source": "feature", "name": "open"},
        },
        "signal_start_time": "09:30:00",
        "signal_end_time": "09:33:00",
        "bar_interval_minutes": 1.0,
    }
    config = {
        "strategy_name": "safe_rule_fixture",
        "timeframe": "1m",
        "symbol": "ES",
        "dataset_id": "fixture",
        "data": {"source": "csv", "raw_csv": "unused.csv", "timezone": "America/New_York"},
        "strategy": {
            "entry": {"module": "safe_bar_rule", "params": {"rule": rule}},
            "sl": {"module": "points_from_entry", "params": {"stop_points": 5.0}},
            "tp": {"module": "fixed_r", "params": {"target_r_multiple": 1.5}},
            "flatten_time": "09:32:00",
        },
        "core": {
            "initial_balance": 10000.0,
            "tick_size": 0.25,
            "point_value": 50.0,
            "tick_value": 12.5,
            "commission_per_contract": 0.0,
            "slippage_ticks": 0.0,
            "flatten_time": "09:32:00",
            "position_sizing": {"mode": "fixed_contracts", "contracts": 1},
        },
        "apex_rules": {
            "enabled": True,
            "timezone": "America/New_York",
            "force_flatten_enabled": True,
            "force_flatten_time": "09:32:00",
            "latest_flat_time": "09:33:00",
            "latest_entry_time": "09:31:30",
            "no_overnight_positions": True,
        },
    }
    timestamps = pd.date_range("2026-01-05 09:30", periods=4, freq="min", tz="America/New_York")
    bars = pd.DataFrame(
        {
            "timestamp": timestamps,
            "open": [100.0, 101.0, 102.0, 103.0],
            "high": [101.0, 102.0, 103.0, 104.0],
            "low": [99.0, 100.0, 101.0, 102.0],
            "close": [100.5, 101.5, 102.5, 103.5],
            "volume": [10.0] * 4,
            "session_date": [timestamp.date() for timestamp in timestamps],
            "session_label": ["RTH"] * 4,
            "is_rth": [True] * 4,
        }
    )
    trades = BacktestEngine(config).run(bars)["trades"]
    assert len(trades) == 1
    assert trades.iloc[0]["entry_timestamp"] == timestamps[1]
    assert trades.iloc[0]["entry_price"] == bars.iloc[1]["open"]


def test_compiler_is_deterministic_and_emits_current_contracts_without_stubs():
    draft = CampaignDraftV1.model_validate(_draft_document())
    first = CampaignCompiler().compile(draft)
    second = CampaignCompiler().compile(draft)
    assert first.draft_sha256 == second.draft_sha256
    assert dict(first.campaign) == dict(second.campaign)
    assert tuple(first.variant_configs) == ("v01", "v02", "v03", "v04", "v05")
    assert first.authoring_manifest["generated_python_stubs"] is False
    assert not any(path.endswith(".py") for path in first.relative_paths)
    for config in first.variant_configs.values():
        validate_campaign_config_contract(dict(config))
        assert config["attempt_provenance"] == "authored"
        assert config["research_metadata"]["validation_gate"]["required"] is True
        from alphaquest.research.campaign_stages import DEFAULT_STAGE_ORDER

        assert config["campaign_tests"]["stage_order"] == DEFAULT_STAGE_ORDER
        assert all(config["campaign_tests"][stage]["enabled"] for stage in DEFAULT_STAGE_ORDER)
    fixed_dollar = first.variant_configs["v03"]["strategy"]["sl"]["params"]
    assert fixed_dollar["dollars_per_contract"] == 250.0
    assert fixed_dollar["tick_value"] == 12.5
    assert "risk_dollars" not in fixed_dollar
    assert "point_value" not in fixed_dollar


def test_compiler_records_configured_evidence_and_approval_roots():
    compiled = CampaignCompiler(
        evidence_root="custom-evidence/runs",
        research_artifact_root="custom-artifacts",
    ).compile(_draft_document())
    gate = compiled.variant_configs["v01"]["research_metadata"]["validation_gate"]

    assert gate["evidence_dir"].startswith("custom-evidence/runs/")
    assert gate["approval_path"].startswith("custom-artifacts/validation_approvals/")


def test_daily_trend_mechanics_subset_includes_contract_warmup_and_review_sessions():
    document = _draft_document()
    document["certified_recipe"] = "daily_tsm_close_to_close"
    for variant in document["variants"]:
        variant["entry"] = {
            "module": "daily_time_series_momentum",
            "params": {"setup_mode": "close_to_close_trend", "lookback_sessions": 20},
        }
    _reconfirm(document)

    compiled = CampaignCompiler().compile(document)
    subset = compiled.variant_configs["v01"]["research_metadata"]["validation_gate"]["data_subset"]

    assert (date.fromisoformat(subset["end_date"]) - date.fromisoformat(subset["start_date"])).days >= 50


def test_compiler_rejects_unfrozen_or_unreviewed_drafts():
    unfrozen = _draft_document()
    unfrozen["frozen"] = False
    with pytest.raises(CampaignCompilationError, match="frozen"):
        CampaignCompiler().compile(unfrozen)
    unresolved = _draft_document()
    unresolved["duplicate_review"]["conclusion"] = "needs_review"
    _reconfirm(unresolved)
    with pytest.raises(CampaignCompilationError, match="distinct"):
        CampaignCompiler().compile(unresolved)

    close_stamped = _draft_document()
    close_stamped["dataset"]["timestamp_semantics"] = "bar_close"
    _reconfirm(close_stamped)
    with pytest.raises(CampaignCompilationError, match="bar-open"):
        CampaignCompiler().compile(close_stamped)


def test_engineering_handoff_lane_cannot_be_frozen_or_published():
    document = _draft_document()
    document["authoring_lane"] = "engineering_handoff"
    document["engineering_handoff_path"] = "research/handoffs/demo/handoff.json"
    with pytest.raises(ValidationError, match="cannot be frozen or published"):
        CampaignDraftV1.model_validate(document)


def test_compiler_preserves_predeclared_parameter_grid_and_enforces_interval_parity():
    document = _draft_document()
    variant = document["variants"][1]
    variant["entry"]["parameter_grid"] = {
        "opening_range_minutes": [5.0, 15.0],
        "confirmation_minutes": [1.0, 5.0],
    }
    variant["stop"]["parameter_grid"] = {"stop_pct": [0.001, 0.002]}
    _reconfirm(document)
    compiled = CampaignCompiler().compile(document)
    grid = compiled.variant_configs["v02"]["core_grid"]["parameters"]
    assert list(grid) == [
        "entry.params.opening_range_minutes",
        "entry.params.confirmation_minutes",
        "sl.params.stop_pct",
    ]
    assert len(grid["entry.params.opening_range_minutes"]) * len(
        grid["entry.params.confirmation_minutes"]
    ) * len(grid["sl.params.stop_pct"]) == 8

    mismatch = _draft_document()
    mismatch["variants"][1]["entry"]["params"]["bar_interval_minutes"] = 5.0
    _reconfirm(mismatch)
    with pytest.raises(CampaignCompilationError, match="does not match"):
        CampaignCompiler().compile(mismatch)


def test_compiler_uses_exchange_timezone_at_runtime_and_retains_source_timezone():
    document = _draft_document()
    document["dataset"]["timezone"] = "UTC"
    document["dataset"]["exchange_timezone"] = "America/New_York"
    _reconfirm(document)

    data = CampaignCompiler().compile(document).variant_configs["v01"]["data"]

    assert data["timezone"] == "America/New_York"
    assert data["source_timezone"] == "UTC"


def test_publisher_installs_one_complete_tree_atomically_and_never_writes_python(tmp_path):
    compiled = CampaignCompiler().compile(_draft_document())
    publisher = TransactionalCampaignPublisher(project_root=tmp_path, repository_preflight=False)
    result = publisher.publish(compiled)
    assert result.destination == tmp_path / "research" / "campaigns" / "active" / compiled.campaign_id
    assert len(result.files) == 8
    assert not list(result.destination.rglob("*.py"))
    assert yaml.safe_load((result.destination / "campaign.yaml").read_text())["variants"] == [
        "v01",
        "v02",
        "v03",
        "v04",
        "v05",
    ]
    manifest = json.loads((result.destination / "authoring_manifest.json").read_text())
    assert manifest["draft_sha256"] == compiled.draft_sha256
    with pytest.raises(CampaignPublishError, match="already exists"):
        publisher.publish(compiled)


def test_publisher_removes_staging_tree_when_validation_fails(tmp_path):
    compiled = CampaignCompiler().compile(_draft_document())

    def fail_validation(_path: Path) -> None:
        raise ValueError("injected preflight failure")

    publisher = TransactionalCampaignPublisher(
        project_root=tmp_path,
        staged_validator=fail_validation,
        repository_preflight=False,
    )
    with pytest.raises(CampaignPublishError, match="injected preflight failure"):
        publisher.publish(compiled)
    active = tmp_path / "research" / "campaigns" / "active"
    assert not (active / compiled.campaign_id).exists()
    assert list(active.iterdir()) == []


def test_publisher_detects_compiled_document_drift_before_writing(tmp_path):
    compiled = CampaignCompiler().compile(_draft_document())
    compiled.variant_configs["v01"]["strategy"]["entry"]["params"]["signal_time"] = "10:00:00"
    with pytest.raises(CampaignPublishError, match="documents changed"):
        TransactionalCampaignPublisher(project_root=tmp_path, repository_preflight=False).publish(compiled)
    assert not (tmp_path / "research").exists()


def test_publisher_runs_repository_preflight_by_default_and_fails_before_install(tmp_path, monkeypatch):
    calls = []

    def reject(*, config_paths, run_tests, project_root):
        calls.append((list(config_paths), run_tests, project_root))
        return {"passed": False, "failures": ["injected repository preflight rejection"]}

    monkeypatch.setattr("alphaquest.research.preflight.run_preflight", reject)
    compiled = CampaignCompiler().compile(_draft_document())
    with pytest.raises(CampaignPublishError, match="repository preflight rejection"):
        TransactionalCampaignPublisher(project_root=tmp_path).publish(compiled)
    assert len(calls) == 1
    assert len(calls[0][0]) == 5
    assert calls[0][1] is False
    assert calls[0][2] == tmp_path.resolve()
    active = tmp_path / "research" / "campaigns" / "active"
    assert list(active.iterdir()) == []


def test_publisher_preflight_uses_fresh_workspace_root_for_relative_dataset(tmp_path):
    dataset = tmp_path / "research/datasets/governed_es_1m/bars.csv"
    dataset.parent.mkdir(parents=True)
    pd.DataFrame(
        {
            "timestamp": ["2024-01-03 09:30:00-05:00", "2024-01-03 09:31:00-05:00"],
            "open": [100.0, 100.5],
            "high": [101.0, 101.5],
            "low": [99.0, 100.0],
            "close": [100.5, 101.0],
            "volume": [100, 120],
            "timeframe_minutes": [1, 1],
        }
    ).to_csv(dataset, index=False)
    digest = hashlib.sha256(dataset.read_bytes()).hexdigest()
    document = _draft_document()
    document["dataset"]["path"] = str(dataset.relative_to(tmp_path))
    document["dataset"]["source_sha256"] = digest
    document["dataset"]["canonical_sha256"] = digest
    _reconfirm(document)

    result = TransactionalCampaignPublisher(project_root=tmp_path).publish(
        CampaignCompiler().compile(document)
    )

    assert result.destination == tmp_path / "research/campaigns/active/demo_completed_bar_edge"
    assert (result.destination / "campaign.yaml").is_file()


def test_generated_authoring_schemas_are_committed_and_valid():
    documents = authoring_schema_documents()
    assert set(documents) == {
        "campaign-draft-v1.schema.json",
        "variant-draft-v1.schema.json",
        "module-manifest-v1.schema.json",
        "dataset-manifest-v1.schema.json",
        "bar-rule-v1.schema.json",
    }
    for document in documents.values():
        Draft202012Validator.check_schema(document)
    Draft202012Validator(documents["campaign-draft-v1.schema.json"]).validate(
        CampaignDraftV1.model_validate(_draft_document()).model_dump(mode="json", by_alias=True)
    )
    Draft202012Validator(documents["bar-rule-v1.schema.json"]).validate(
        BarRuleV1.model_validate(_rule()).model_dump(mode="json", by_alias=True)
    )
    assert write_authoring_schemas(check=True) == ()
