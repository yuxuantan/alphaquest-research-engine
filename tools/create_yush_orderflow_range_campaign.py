from __future__ import annotations

import hashlib
import json
from pathlib import Path

from alphaquest.authoring import CampaignCompiler, CampaignDraftV1, TransactionalCampaignPublisher
from alphaquest.authoring.models import DatasetManifestV1, campaign_confirmation_context_sha256
from alphaquest.research.storage import display_path, load_storage_layout
from alphaquest.studio.drafts import DraftStore
from alphaquest.studio.ledger import append_planned_publication


CAMPAIGN_ID = "yush_orderflow_range"
BAR_PATH = Path("data/cache/orderflow/es_databento_trades_1m_20250714_20260610_0930_1100_ny.parquet")
EVENT_ARCHIVE = Path("data/raw/ES/GLBX-20260713-S6XF67C8UA.zip")
ROLL_CALENDAR = Path("data/reference/ES/roll_calendars/motivewave_rithmic_roll_calendar.csv")


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _mechanics() -> dict[str, object]:
    """One fixed parameter set; none of these values is an optimization grid."""

    return {
        "tick_size": 0.25,
        "point_value": 50.0,
        "contracts": 1,
        "commission_per_contract": 2.5,
        "max_trades_per_day": 3,
        "max_aoi_width_points": 3.0,
        "entry_offset_ticks": 2,
        "stop_offset_ticks": 2,
        "max_stop_points": 5.0,
        "value_area_fraction": 0.70,
        "range_expansion_fraction": 0.20,
        "delta_profile_min_abs": 300,
        "delta_bubble_threshold": 300,
        "big_trade_threshold": 200,
        "big_trade_window_ms": 100,
        "breakeven_offset_points": 1.25,
        "opening_range_seconds": 32,
        "bar_seconds": 180,
        "breakout_probe_ticks": 2,
        "initial_balance": 50_000.0,
        "minimum_stop_points": 2.0,
        "slippage_ticks": 1,
        "delta_neighbour_multiple": 2.0,
        "aoi_lineage_mode": "exact_fingerprint",
    }


def _dataset(project_root: Path) -> DatasetManifestV1:
    bar = project_root / BAR_PATH
    archive = project_root / EVENT_ARCHIVE
    roll = project_root / ROLL_CALENDAR
    bar_hash = _sha256(bar)
    return DatasetManifestV1.model_validate(
        {
            "schema": "alphaquest.dataset-manifest/v1",
            "dataset_id": "es_databento_trade_events_20250714_20260610_0930_1100_ny",
            "source": "parquet",
            "path": BAR_PATH.as_posix(),
            "symbol": "ES",
            "timeframe": "1m",
            "timezone": "America/New_York",
            "exchange_timezone": "America/New_York",
            "timestamp_semantics": "bar_open",
            "source_timestamp_semantics": "bar_open",
            "source_sha256": bar_hash,
            "canonical_sha256": bar_hash,
            "coverage_start": "2025-07-14T09:30:00-04:00",
            "coverage_end": "2026-06-10T10:59:59-04:00",
            "roll_policy": "MotiveWave/Rithmic predeclared active-contract calendar; no back adjustment",
            "continuous_contract": "explicit_roll_calendar",
            "contract_column": "contract_symbol",
            "contract_count": 4,
            "roll_calendar": ROLL_CALENDAR.as_posix(),
            "roll_calendar_sha256": _sha256(roll),
            "transformations": [
                "Canonical one-minute bars retained only for dataset provenance and reporting context",
                "Strategy decisions and fills use causally ordered Databento trade messages",
            ],
            "row_count": 20700,
            "dropped_row_count": 0,
            "gap_count": 0,
            "duplicate_count": 0,
            "out_of_order_count": 0,
            "invalid_ohlc_count": 0,
            "cadence_violation_count": 0,
            "certified_features": [],
            "quality_verdict": "PASS",
            "quality_notes": [
                "All 230 sessions contain exactly 90 one-minute reporting bars with no internal cadence defects.",
                "The event source is separately hash-bound and is the sole source of strategy decisions and fills.",
            ],
            "event_source": {
                "source": "databento_zip_trades",
                "archive": EVENT_ARCHIVE.as_posix(),
                "archive_sha256": _sha256(archive),
                "roll_calendar": ROLL_CALENDAR.as_posix(),
                "roll_calendar_sha256": _sha256(roll),
                "root_symbol": "ES",
                "aggregation_ms": 100,
                "overnight_start": "16:00:00",
                "rth_start": "09:30:00",
                "rth_end": "16:00:00",
                "reset_previous_levels_on_roll": True,
            },
        }
    )


def _draft(project_root: Path) -> CampaignDraftV1:
    mechanics = _mechanics()
    payload = {
        "schema": "alphaquest.campaign-draft/v1",
        "campaign_id": CAMPAIGN_ID,
        "title": "Yush Orderflow Range Reversal",
        "created_at": "2026-07-20",
        "instrument": "ES",
        "timeframe": "1m",
        "edge_family": "orderflow_range_reversal",
        "hypothesis": (
            "During balanced ES morning auctions, a retest of a developing value-area edge that overlaps a prior "
            "liquidity reference and then attracts fresh one-sided trade activity may reverse toward fair value."
        ),
        "expected_mechanism": (
            "Repeated rejection at a developing value boundary suggests passive liquidity is absorbing aggressive "
            "flow; a fresh delta or large-trade event after the tap supplies causal confirmation for reversion."
        ),
        "holding_horizon": "Intraday only, from a post-tap stop entry between 09:30 and 10:59:59 New York until 11:00.",
        "known_failure_modes": [
            "A developing profile can move while an order is pending, apparent one-sided delta can be continuation "
            "rather than absorption, and sparse trade prints can make a narrow AOI or local prominence unstable.",
            "Trade-message aggressor classification, contract rolls, gap-through fills, and platform aggregation "
            "differences may cause mechanical entries to disagree with a MotiveWave/Rithmic chart.",
        ],
        "sources": [
            {
                "title": "Yush order-flow range-reversal rules and clarifications",
                "authors": ["User-supplied trading specification"],
                "year": 2026,
                "link": "research://user-supplied/yush-orderflow-range-specification",
                "relevance": "Primary source for the exact mechanics being forward tested and submitted for manual replay validation.",
            },
            {
                "title": "Support for Resistance: Technical Analysis and Intraday Exchange Rates",
                "authors": ["Carol L. Osler"],
                "year": 2000,
                "link": "https://www.newyorkfed.org/medialibrary/media/research/epr/00v06n2/0007osle.pdf",
                "relevance": "Documents clustering and predictive behavior around widely observed support and resistance levels.",
            },
            {
                "title": "Technical Analysis and Liquidity Provision",
                "authors": ["Kenneth A. Kavajecz", "Elizabeth R. Odders-White"],
                "year": 2004,
                "doi": "10.1016/S1386-4181(03)00041-9",
                "relevance": "Connects technical price levels with liquidity provision and limit-order-book behavior.",
            },
            {
                "title": "The Price Impact of Order Book Events",
                "authors": ["Rama Cont", "Arseniy Kukanov", "Sasha Stoikov"],
                "year": 2014,
                "doi": "10.1017/jfm.2014.86",
                "relevance": "Supports the general microstructure premise that signed order-flow imbalance has short-horizon price impact.",
            },
        ],
        "economic_edge_fingerprint": {
            "market_behavior": "Morning ES price repeatedly rejects a developing value-area boundary inside a balanced auction.",
            "causal_mechanism": "Passive liquidity absorbs one-sided aggressive trading near a known reference and price reverts toward fair value.",
            "signal_inputs": [
                "causal developing volume profile",
                "prior-session and overnight price references",
                "local four-tick signed-delta prominence",
                "same-price same-side 100 millisecond large-trade aggregation",
            ],
            "market_context": "ES regular trading hours from 09:30 to 11:00 New York after a 16:00-to-09:30 overnight session.",
            "holding_period": "Minutes to at most the 11:00 New York forced flatten; no overnight exposure.",
        },
        "duplicate_review": {
            "reviewed_campaign_ids": [],
            "ledger_queries": [
                "Clean-slate registry query on 2026-07-20 returned zero campaigns, variants, attempts, and runs.",
                "Pre-reset campaigns and evidence were excluded because none had hash-bound manual mechanics approval.",
            ],
            "conclusion": "distinct",
            "substantive_distinction": (
                "This is the first governed campaign after the user-authorized clean-slate reset; no archived, "
                "unverified result is treated as prior evidence or as an economic duplicate decision."
            ),
        },
        "dataset": _dataset(project_root).model_dump(mode="json", by_alias=True),
        "execution": {
            "session_start": "09:30:00",
            "session_end": "16:00:00",
            "latest_entry_time": "10:59:59",
            "flatten_time": "11:00:00",
            "latest_flat_time": "11:00:00",
            "overnight_allowed": False,
            "initial_balance": 50_000.0,
            "tick_size": 0.25,
            "point_value": 50.0,
            "tick_value": 12.5,
            "commission_per_contract": 2.5,
            "slippage_ticks": 1.0,
            "contracts": 1,
            "prop_profile": "configured_local_profile",
        },
        "variants": [
            {
                "schema": "alphaquest.variant-draft/v1",
                "variant_id": "v01",
                "title": "Exact forward-tested AOI and post-tap order-flow confirmation",
                "entry": {"module": "yush_orderflow_range", "params": {"mechanics": mechanics}},
                "stop": {"module": "event_aoi_structural_stop", "params": {}},
                "target": {"module": "event_value_area_management", "params": {}},
                "mechanic_rationale": (
                    "Build a causal AOI around developing VAL or VAH plus the strongest available market, local-delta, "
                    "and large-trade categories; reset eligibility whenever the exact AOI price envelope or selected "
                    "confluence identity changes, then require a prior reversal, a fresh directed tap, and a new "
                    "post-tap trigger."
                ),
                "entry_rationale": (
                    "A two-tick stop entry beyond the AOI demands observable movement away from the tested boundary, "
                    "while neither the tap nor its post-tap trigger can be the event that created or materially changed "
                    "the exact AOI; a tapped AOI is frozen until its developing-value anchor leaves the box."
                ),
                "stop_rationale": (
                    "The stop sits two ticks beyond the opposite AOI edge but is widened to at least two points so "
                    "tiny confluence envelopes do not create suffocating risk; entries above five points are rejected."
                ),
                "target_rationale": (
                    "The developing value midpoint is the first objective; after it trades, the stop protects 1.25 "
                    "points and the opposite developing value edge becomes the final target, with an 11:00 hard flatten."
                ),
                "timeframe_session_rationale": (
                    "Trade messages are replayed in causal order from 09:30 to 11:00 New York; the three-minute delta "
                    "bubble clock and 100 millisecond large-trade aggregation match the frozen chart interpretation."
                ),
                "known_failure_modes": [
                    "Moving developing-value anchors can invalidate pending AOIs, and local delta prominence can be "
                    "sensitive to neighboring buckets when activity is sparse or distributed across nearby prices.",
                    "Gap-through stop orders receive adverse event-price fills plus one tick, so actual risk may exceed "
                    "the planned structural distance and cause otherwise attractive signals to be rejected."
                ],
                "material_difference": (
                    "As v01 this is the single frozen baseline mechanic; any later variant is prohibited until this "
                    "implementation passes manual mechanics review and then receives a terminal FAIL in the test suite."
                ),
                "confirmed": True,
            }
        ],
        "variant_protocol": "sequential_failure_informed",
        "sequential_variant_history": [],
        "authoring_lane": "certified_event_replay",
        "certified_recipe": None,
        "event_strategy": "yush_orderflow_range",
        "engineering_handoff_path": None,
        "confirmation_context_sha256": None,
        "frozen": False,
    }
    payload["confirmation_context_sha256"] = campaign_confirmation_context_sha256(payload)
    payload["frozen"] = True
    return CampaignDraftV1.model_validate(payload)


def main() -> int:
    root = Path(".").resolve()
    layout = load_storage_layout(root)
    draft = _draft(root)
    dataset_dir = layout.dataset_root / draft.dataset.dataset_id
    dataset_dir.mkdir(parents=True, exist_ok=False)
    (dataset_dir / "dataset_manifest.json").write_text(
        json.dumps(draft.dataset.model_dump(mode="json", by_alias=True), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    DraftStore(root).save(CAMPAIGN_ID, draft.model_dump(mode="json", by_alias=True), wizard_step=7)
    compiled = CampaignCompiler(
        evidence_root=display_path(layout.evidence_roots[0], root),
        research_artifact_root=display_path(layout.research_artifact_root, root),
    ).compile(draft)
    result = TransactionalCampaignPublisher(project_root=root).publish(compiled)
    append_planned_publication(
        draft,
        project_root=root,
        active_campaign_root=layout.active_campaign_root,
    )
    print(result.destination)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
