"""Legacy Streamlit compatibility shell for AlphaQuest Research Studio.

The novice launcher now serves the React/FastAPI workspace.  This module stays
available temporarily for parity checks and expert fallback; governed workflow
logic belongs in :mod:`alphaquest.studio.workflow`.
"""

from __future__ import annotations

from datetime import date
import json
import os
from pathlib import Path
import re
from typing import Any


PAGES = ("Home", "Campaigns", "Review Queue", "Libraries", "Tutorial", "Settings")
WIZARD_STEPS = (
    "1 · Research brief",
    "2 · Duplicate review",
    "3 · Dataset",
    "4 · Execution rules",
    "5 · Mechanics lane",
    "6 · First variant",
    "7 · Protocol and freeze",
)


def main() -> None:
    import streamlit as st

    st.set_page_config(page_title="AlphaQuest Research Studio", page_icon="🔬", layout="wide")
    root = _project_root()
    try:
        from alphaquest.studio.publishing import StudioPublicationService

        recovered_publications = StudioPublicationService(root).recover()
    except Exception as exc:
        recovered_publications = []
        st.error(f"Publication recovery requires manual review before new work: {exc}")
    if recovered_publications:
        st.warning(
            f"Recovered {len(recovered_publications)} abandoned publication transaction(s) fail-closed; "
            "review the publication journal before retrying."
        )
    with st.sidebar:
        st.title("AlphaQuest")
        st.caption("Research Studio · local workstation")
        page = st.radio("Workspace", PAGES, key="studio_page")
        st.divider()
        st.caption(f"Workspace: {root.name}")
        st.caption("Passing research remains candidate-only until separate review.")

    if page == "Home":
        _render_home(st, root)
    elif page == "Campaigns":
        _render_campaigns(st, root)
    elif page == "Review Queue":
        _render_review_queue(st, root)
    elif page == "Libraries":
        _render_libraries(st, root)
    elif page == "Tutorial":
        _render_tutorial(st, root)
    else:
        _render_settings(st, root)


def _render_home(st: Any, root: Path) -> None:
    from alphaquest.studio.drafts import DraftStore
    from alphaquest.studio.workspace import list_published_campaigns, list_review_queue, refresh_generated_indexes_if_stale

    st.title("AlphaQuest Research Studio")
    st.write("Turn a researched futures idea into a governed sequential backtest—without editing code or YAML.")
    try:
        refresh = refresh_generated_indexes_if_stale(root)
    except Exception as exc:  # pragma: no cover - defensive workstation guard
        st.warning("Generated indexes could not be refreshed. Drafts are still shown directly.")
        st.caption(str(exc))
        refresh = {"refreshed": False}
    if refresh.get("refreshed"):
        st.caption("Generated research indexes were refreshed from the authoritative source and evidence roots.")

    drafts = DraftStore(root).list()
    campaigns = list_published_campaigns(root)
    queue = list_review_queue(root)
    columns = st.columns(4)
    columns[0].metric("Live drafts", len(drafts))
    columns[1].metric("Active campaigns", sum(row["lifecycle"] == "active" for row in campaigns))
    columns[2].metric("Review items", len(queue))
    columns[3].metric("Certified modules", _certified_module_count())

    st.subheader("Start a research idea")
    with st.form("new_campaign_form", clear_on_submit=False):
        left, middle, right = st.columns([2, 3, 1])
        campaign_id = left.text_input("Campaign ID", placeholder="es_opening_auction_continuation")
        title = middle.text_input("Plain-language title", placeholder="Opening auction continuation after imbalance")
        instrument = right.selectbox("Market", ("ES", "NQ"))
        created = st.form_submit_button("Create draft", type="primary", use_container_width=True)
    if created:
        normalized = campaign_id.strip().lower()
        if re.fullmatch(r"[a-z0-9][a-z0-9_]*", normalized) is None:
            st.error("Use lowercase letters, numbers, and underscores for the campaign ID.")
        elif not title.strip():
            st.error("Add a title that a reviewer can understand.")
        else:
            store = DraftStore(root)
            if store.path_for(normalized).exists():
                st.error("That draft ID already exists; select it from Campaigns.")
            else:
                store.save(
                    normalized,
                    {
                        "schema": "alphaquest.campaign-draft/v1",
                        "campaign_id": normalized,
                        "title": title.strip(),
                        "created_at": date.today().isoformat(),
                        "instrument": instrument,
                        "timeframe": "1m",
                        "variant_protocol": "sequential_failure_informed",
                        "sequential_variant_history": [],
                        "frozen": False,
                    },
                    wizard_step=1,
                )
                st.session_state["selected_draft"] = normalized
                st.success("Draft created. Open Campaigns to complete the seven gated steps.")
                st.rerun()

    st.subheader("Work in progress")
    if drafts:
        st.dataframe(drafts, use_container_width=True, hide_index=True)
    else:
        st.info("No drafts yet. A draft appears here immediately after creation, before publication or indexing.")

    _render_job_status(st, root)

    st.subheader("How promotion works")
    st.markdown(
        "Research brief → duplicate review → governed data → execution rules → mechanics lane → "
        "one initial variant → mechanics approval → staged testing → optional next variant after FAIL → separate candidate review."
    )
    st.warning("A good-looking backtest is not a trading approval. Scientific failures stop each variant at its first failed gate.")


def _render_campaigns(st: Any, root: Path) -> None:
    from alphaquest.studio.drafts import DraftStore
    from alphaquest.studio.workspace import list_published_campaigns

    st.title("Campaigns")
    drafts_tab, published_tab = st.tabs(("Draft research", "Published research"))
    store = DraftStore(root)
    with drafts_tab:
        drafts = store.list()
        if not drafts:
            st.info("Create the first draft from Home.")
        else:
            ids = [row["campaign_id"] for row in drafts]
            preferred = st.session_state.get("selected_draft")
            index = ids.index(preferred) if preferred in ids else 0
            selected = st.selectbox("Draft", ids, index=index, format_func=lambda item: _draft_label(item, drafts))
            st.session_state["selected_draft"] = selected
            _render_wizard(st, root, store, selected)
    with published_tab:
        campaigns = list_published_campaigns(root)
        if campaigns:
            st.dataframe(campaigns, use_container_width=True, hide_index=True)
            active = [
                row
                for row in campaigns
                if row.get("authored_lifecycle", row["lifecycle"]) == "active"
                and row.get("studio_managed") is True
            ]
            developer_managed = [
                row
                for row in campaigns
                if row.get("authored_lifecycle", row["lifecycle"]) == "active"
                and row.get("studio_managed") is not True
            ]
            if developer_managed:
                st.warning(
                    "Existing unfinished or legacy source is blocked and developer-managed. "
                    "Studio will not queue mechanics or performance work until a complete reviewed "
                    "authoring manifest and frozen strategy specification exist."
                )
                st.dataframe(
                    [
                        {
                            "campaign": row["campaign_id"],
                            "status": row["workflow_status"],
                            "next action": row["workflow_blocker"],
                        }
                        for row in developer_managed
                    ],
                    use_container_width=True,
                    hide_index=True,
                )
            if active:
                selected = st.selectbox(
                    "Studio-managed active campaign",
                    [row["campaign_id"] for row in active],
                    key="active_campaign",
                )
                _render_published_actions(st, root, selected)
        else:
            st.info("No authored campaigns were discovered in configured source roots.")


def _render_wizard(st: Any, root: Path, store: Any, campaign_id: str) -> None:
    document = store.load(campaign_id)
    draft = dict(document.get("draft") or {})
    if draft.get("frozen"):
        _render_frozen_draft(st, root, store, campaign_id, draft)
        return
    saved_step = int(document.get("wizard_step") or 1)
    navigation_key = f"workflow_step_{campaign_id}"
    pending_key = f"workflow_next_{campaign_id}"
    desired_step = WIZARD_STEPS[max(0, min(6, saved_step - 1))]
    pending_step = st.session_state.pop(pending_key, None)
    if pending_step in WIZARD_STEPS:
        st.session_state[navigation_key] = pending_step
    if st.session_state.get(navigation_key) not in WIZARD_STEPS:
        st.session_state[navigation_key] = desired_step
    step = st.selectbox("Research workflow", WIZARD_STEPS, key=navigation_key)
    step_number = WIZARD_STEPS.index(step) + 1
    st.progress(step_number / 7, text=f"Step {step_number} of 7")
    prerequisite = _wizard_prerequisite_error(draft, store.load_state(campaign_id), step_number)
    if prerequisite:
        st.warning(prerequisite)
        return
    if step_number == 1:
        _wizard_research_brief(st, store, campaign_id, draft)
    elif step_number == 2:
        _wizard_duplicates(st, root, store, campaign_id, draft)
    elif step_number == 3:
        _wizard_dataset(st, root, store, campaign_id, draft)
    elif step_number == 4:
        _wizard_execution(st, store, campaign_id, draft)
    elif step_number == 5:
        _wizard_lane(st, root, store, campaign_id, draft)
    elif step_number == 6:
        _wizard_variants(st, store, campaign_id, draft)
    else:
        _wizard_protocol(st, root, store, campaign_id, draft)


def _wizard_prerequisite_error(
    draft: dict[str, Any],
    state: dict[str, Any],
    step_number: int,
) -> str | None:
    if step_number <= 1:
        return None
    fingerprint = draft.get("economic_edge_fingerprint")
    brief_ready = all(
        (
            draft.get("sources"),
            draft.get("hypothesis"),
            draft.get("expected_mechanism"),
            draft.get("holding_horizon"),
            draft.get("known_failure_modes"),
            isinstance(fingerprint, dict) and all(fingerprint.values()),
        )
    )
    if not brief_ready:
        return "Complete and save step 1's source, hypothesis, mechanism, horizon, failures, and edge fingerprint first."
    if step_number <= 2:
        return None
    if (draft.get("duplicate_review") or {}).get("conclusion") != "distinct":
        return "Complete step 2 and resolve every deterministic duplicate match before continuing."
    if step_number <= 3:
        return None
    if (draft.get("dataset") or {}).get("quality_verdict") != "PASS":
        return "Select or import a governed PASS dataset in step 3 before continuing."
    if step_number <= 4:
        return None
    if not draft.get("execution"):
        return "Confirm the full execution and prop protocol in step 4 before choosing mechanics."
    if step_number <= 5:
        return None
    lane = draft.get("authoring_lane")
    lane_ready = (
        lane == "certified_recipe" and bool(draft.get("certified_recipe"))
    ) or (
        lane == "visual_completed_bar_rule" and isinstance(state.get("safe_bar_rule"), dict)
    ) or (
        lane == "engineering_handoff" and bool(draft.get("engineering_handoff_path"))
    )
    if not lane_ready:
        return "Choose and confirm a certified recipe, visual rule, or engineering handoff in step 5 first."
    if step_number <= 6:
        return None
    variants = draft.get("variants") or []
    if len(variants) != 1 or not all(item.get("confirmed") for item in variants):
        return "Review and confirm the initial variant card in step 6 before protocol freeze."
    return None


def _advance_wizard(st: Any, campaign_id: str, step_number: int) -> None:
    st.session_state[f"workflow_next_{campaign_id}"] = WIZARD_STEPS[step_number - 1]


def _render_frozen_draft(
    st: Any,
    root: Path,
    store: Any,
    campaign_id: str,
    draft: dict[str, Any],
) -> None:
    """Render the immutable publication checkpoint without editable widgets."""

    from alphaquest.research.storage import load_storage_layout

    st.subheader("Frozen research protocol")
    st.success(
        "This protocol is immutable. A data, mechanics, parameter-space, or execution change requires an "
        "explicit governed follow-up attempt."
    )
    st.markdown(
        f"**{draft.get('title')}** · {draft.get('instrument')} {draft.get('timeframe')} · "
        f"{len(draft.get('variants') or [])} frozen variants"
    )
    report = store.validation_report(campaign_id)
    if not report.get("valid"):
        st.error("NEEDS MANUAL REVIEW — the frozen-draft integrity or schema check failed.")
        st.json(report, expanded=False)
        return
    destination = load_storage_layout(root).active_campaign_root / campaign_id
    if destination.exists():
        st.info("The immutable source tree is already published. Use the Published research tab for governed actions.")
        return
    if st.button("Publish governed campaign", type="primary", key=f"publish_frozen_{campaign_id}"):
        try:
            result = _publish_draft(root, store.validate(campaign_id))
        except Exception as exc:
            st.error(f"Publication failed closed: {exc}")
        else:
            st.success(f"Published {campaign_id} transactionally after full preflight.")
            st.json(_serializable(result), expanded=False)
    with st.expander("Publication blocked? Create an editable revision"):
        st.caption(
            "The frozen protocol remains immutable. A revision gets a new campaign ID, clears duplicate "
            "review and all mechanics confirmations, and returns to the governed wizard before any PnL."
        )
        revision_id = st.text_input(
            "Revision campaign ID",
            value=f"{campaign_id}_revision_{date.today():%Y%m%d}",
            key=f"revision_id_{campaign_id}",
        )
        revision_reason = st.text_area(
            "Publication blocker or reason for revision",
            key=f"revision_reason_{campaign_id}",
        )
        if st.button("Create revised draft", key=f"revise_frozen_{campaign_id}"):
            try:
                store.create_revision(campaign_id, revision_id.strip(), reason=revision_reason)
            except Exception as exc:
                st.error(f"Revision was not created: {exc}")
            else:
                st.session_state["selected_draft"] = revision_id.strip()
                st.success("Editable revision created. The frozen original was preserved unchanged.")
                st.rerun()


def _wizard_research_brief(st: Any, store: Any, campaign_id: str, draft: dict[str, Any]) -> None:
    st.subheader("1. Declare the economic edge before seeing PnL")
    _render_ai_drafting(st, store, campaign_id, draft)
    source = (draft.get("sources") or [{}])[0]
    fingerprint = draft.get("economic_edge_fingerprint") or {}
    with st.form(f"brief_{campaign_id}"):
        title = st.text_input(
            "Campaign title", value=str(draft.get("title") or ""), key=f"brief_title_{campaign_id}"
        )
        edge_family = st.text_input(
            "Economic edge family",
            value=str(draft.get("edge_family") or ""),
            key=f"brief_edge_family_{campaign_id}",
        )
        timeframe = st.selectbox(
            "Completed-bar timeframe · Studio V1",
            ("1m", "5m", "15m"),
            index=_index(("1m", "5m", "15m"), draft.get("timeframe")),
            key=f"brief_timeframe_{campaign_id}",
            help="Hourly, daily, intrabar, and event-driven ideas use the engineering-handoff lane until certified.",
        )
        hypothesis = st.text_area(
            "Falsifiable hypothesis",
            value=str(draft.get("hypothesis") or ""),
            key=f"brief_hypothesis_{campaign_id}",
        )
        mechanism = st.text_area(
            "Expected causal mechanism",
            value=str(draft.get("expected_mechanism") or ""),
            key=f"brief_mechanism_{campaign_id}",
        )
        horizon = st.text_input(
            "Expected holding horizon",
            value=str(draft.get("holding_horizon") or "intraday"),
            key=f"brief_horizon_{campaign_id}",
        )
        failures = st.text_area(
            "Known failure modes · one per line",
            value="\n".join(draft.get("known_failure_modes") or []),
            key=f"brief_failures_{campaign_id}",
        )
        st.markdown("**Research source**")
        a, b, c = st.columns([3, 2, 1])
        source_title = a.text_input(
            "Source title", value=str(source.get("title") or ""), key=f"brief_source_title_{campaign_id}"
        )
        authors = b.text_input(
            "Authors · comma separated",
            value=", ".join(source.get("authors") or []),
            key=f"brief_authors_{campaign_id}",
        )
        year = c.number_input(
            "Year",
            min_value=1900,
            max_value=2200,
            value=int(source.get("year") or date.today().year),
            key=f"brief_year_{campaign_id}",
        )
        link = st.text_input(
            "Link", value=str(source.get("link") or ""), key=f"brief_link_{campaign_id}"
        )
        doi = st.text_input(
            "DOI · optional when link is supplied",
            value=str(source.get("doi") or ""),
            key=f"brief_doi_{campaign_id}",
        )
        relevance = st.text_area(
            "Why this source may apply to this futures market",
            value=str(source.get("relevance") or ""),
            key=f"brief_relevance_{campaign_id}",
        )
        st.markdown("**Economic fingerprint used for duplicate checks**")
        behavior = st.text_input(
            "Market behavior",
            value=str(fingerprint.get("market_behavior") or ""),
            key=f"brief_behavior_{campaign_id}",
        )
        inputs = st.text_input(
            "Signal inputs · comma separated",
            value=", ".join(fingerprint.get("signal_inputs") or []),
            key=f"brief_inputs_{campaign_id}",
        )
        context = st.text_input(
            "Market context",
            value=str(fingerprint.get("market_context") or "RTH futures"),
            key=f"brief_context_{campaign_id}",
        )
        saved = st.form_submit_button("Save and continue", type="primary")
    if saved:
        updated = {
                "title": title.strip(),
                "edge_family": _identifier(edge_family),
                "timeframe": timeframe,
                "hypothesis": hypothesis.strip(),
                "expected_mechanism": mechanism.strip(),
                "holding_horizon": horizon.strip(),
                "known_failure_modes": _lines(failures),
                "sources": [
                    {
                        "title": source_title.strip(),
                        "authors": [item.strip() for item in authors.split(",") if item.strip()],
                        "year": int(year),
                        "link": link.strip() or None,
                        "doi": doi.strip() or None,
                        "relevance": relevance.strip(),
                    }
                ],
                "economic_edge_fingerprint": {
                    "market_behavior": behavior.strip(),
                    "causal_mechanism": mechanism.strip(),
                    "signal_inputs": [item.strip() for item in inputs.split(",") if item.strip()],
                    "market_context": context.strip(),
                    "holding_period": horizon.strip(),
                },
            }
        brief_changed = any(draft.get(key) != value for key, value in updated.items())
        timeframe_changed = draft.get("timeframe") != timeframe
        if brief_changed:
            draft.pop("duplicate_review", None)
            _clear_variant_design(draft)
        if timeframe_changed:
            draft.pop("dataset", None)
            _reset_mechanics_lane(store, campaign_id, draft)
        draft.update(updated)
        store.save(campaign_id, draft, wizard_step=2)
        _advance_wizard(st, campaign_id, 2)
        st.success("Research brief autosaved. Duplicate review is now available.")
        st.rerun()


def _wizard_duplicates(st: Any, root: Path, store: Any, campaign_id: str, draft: dict[str, Any]) -> None:
    from alphaquest.studio.duplicates import duplicate_matches
    from alphaquest.studio.ledger import append_duplicate_closure

    st.subheader("2. Review prior and active work")
    matches = duplicate_matches(
        project_root=root,
        campaign_id=campaign_id,
        title=str(draft.get("title") or ""),
        hypothesis=str(draft.get("hypothesis") or ""),
        expected_mechanism=str(draft.get("expected_mechanism") or ""),
        fingerprint=draft.get("economic_edge_fingerprint"),
    )
    if matches:
        st.dataframe(matches, use_container_width=True, hide_index=True)
    else:
        st.info("No definitions or ledger rows matched. Record that review explicitly below.")
    previous = draft.get("duplicate_review") or {}
    with st.form(f"duplicates_{campaign_id}"):
        reviewed = st.multiselect(
            "Reviewed matches",
            [item["campaign_id"] for item in matches],
            default=[item for item in previous.get("reviewed_campaign_ids", []) if item in {m["campaign_id"] for m in matches}],
            key=f"duplicate_reviewed_{campaign_id}",
        )
        conclusion = st.selectbox(
            "Conclusion",
            ("distinct", "duplicate", "needs_review"),
            index=_index(("distinct", "duplicate", "needs_review"), previous.get("conclusion")),
            key=f"duplicate_conclusion_{campaign_id}",
        )
        distinction = st.text_area(
            "Substantive economic distinction or duplicate rationale",
            value=str(previous.get("substantive_distinction") or ""),
            key=f"duplicate_distinction_{campaign_id}",
        )
        saved = st.form_submit_button("Save duplicate review", type="primary")
    if saved:
        review = {
            "reviewed_campaign_ids": reviewed,
            "ledger_queries": [str(draft.get("title") or campaign_id), str(draft.get("edge_family") or campaign_id)],
            "conclusion": conclusion,
            "substantive_distinction": distinction.strip(),
        }
        if draft.get("duplicate_review") != review:
            _invalidate_variant_confirmations(draft)
        draft["duplicate_review"] = review
        store.save(campaign_id, draft, wizard_step=3 if conclusion == "distinct" else 2)
        _advance_wizard(st, campaign_id, 3 if conclusion == "distinct" else 2)
        st.success("Duplicate decision autosaved.")
        st.rerun()
    if conclusion == "duplicate":
        closure_reason = distinction.strip()
        if len(closure_reason) < 80:
            st.warning("Closing an idea as a duplicate requires a substantive rationale of at least 80 characters.")
        if st.button(
            "Close duplicate before PnL as FAIL",
            type="primary",
            disabled=len(closure_reason) < 80,
        ):
            path = append_duplicate_closure(draft, project_root=root, failure_reason=closure_reason)
            st.error(f"Research closed as FAIL before PnL. Ledger event appended to {path.name}.")


def _wizard_dataset(st: Any, root: Path, store: Any, campaign_id: str, draft: dict[str, Any]) -> None:
    from alphaquest.studio.data_import import DataImportSpec, DatasetImporter
    from alphaquest.studio.workspace import list_dataset_manifests

    st.subheader("3. Select governed bars or import a local file")
    manifests = list_dataset_manifests(root)
    mode = st.radio("Data source", ("Governed dataset", "Import CSV or Parquet"), horizontal=True)
    if mode == "Governed dataset":
        if not manifests:
            st.info("No Studio dataset manifests exist yet. Use the import lane.")
            return
        by_id = {item["dataset_id"]: item for item in manifests}
        selected = st.selectbox("Dataset", list(by_id), format_func=lambda item: f"{item} · {by_id[item].get('quality_verdict')}")
        st.json(by_id[selected], expanded=False)
        if st.button("Use this dataset", type="primary"):
            selected_dataset = {key: value for key, value in by_id[selected].items() if key != "manifest_path"}
            if draft.get("dataset") != selected_dataset:
                _reset_mechanics_lane(store, campaign_id, draft)
            draft["dataset"] = selected_dataset
            store.save(campaign_id, draft, wizard_step=4)
            _advance_wizard(st, campaign_id, 4)
            st.success("Governed dataset selected.")
            st.rerun()
        return

    uploaded = st.file_uploader("Local bars", type=("csv", "parquet", "pq"))
    if uploaded is None:
        st.caption("The original file is copied into quarantine before parsing. Invalid rows are counted and never silently discarded.")
        return
    temporary = _uploaded_path(root, campaign_id, uploaded.name)
    temporary.parent.mkdir(parents=True, exist_ok=True)
    temporary.write_bytes(uploaded.getvalue())
    try:
        columns = DatasetImporter(root).inspect_columns(temporary)
    except Exception as exc:
        st.error(str(exc))
        return
    with st.form(f"data_map_{campaign_id}"):
        dataset_id = st.text_input("Dataset ID", value=f"{campaign_id}_bars")
        timezone_name = st.text_input("Timezone of source timestamps", value="America/New_York")
        semantics = st.selectbox("Timestamp means", ("bar_open", "bar_close"))
        roll_policy = st.selectbox(
            "Contract roll policy",
            ("single_contract", "explicit_roll_calendar"),
            help=(
                "Choose single_contract only for one outright contract. Multi-contract files must preserve "
                "a contract column and provide a causal, predeclared roll calendar."
            ),
        )
        roll_calendar_upload = st.file_uploader(
            "Roll calendar CSV",
            type=("csv",),
            disabled=roll_policy != "explicit_roll_calendar",
            help="Required columns: start_timestamp and contract_symbol.",
        )
        mappings: dict[str, str] = {}
        mapping_columns = st.columns(3)
        for index, canonical in enumerate(("timestamp", "open", "high", "low", "close", "volume")):
            mappings[canonical] = mapping_columns[index % 3].selectbox(
                f"{canonical.title()} column", columns, index=_guess_column(columns, canonical), key=f"map_{campaign_id}_{canonical}"
            )
        contract_choice = st.selectbox("Contract column · optional", ("<none>", *columns))
        single_contract = st.checkbox(
            "This file contains exactly one futures contract",
            disabled=roll_policy != "single_contract",
            help="Required for single_contract; continuous or stitched files need explicit contract lineage.",
        )
        imported = st.form_submit_button("Quarantine, validate, and import", type="primary")
    if imported:
        try:
            roll_calendar_path = None
            if roll_calendar_upload is not None:
                roll_calendar_path = _uploaded_path(
                    root,
                    campaign_id,
                    f"roll-calendar-{roll_calendar_upload.name}",
                )
                roll_calendar_path.write_bytes(roll_calendar_upload.getvalue())
            result = DatasetImporter(root).import_file(
                temporary,
                DataImportSpec(
                    dataset_id=_identifier(dataset_id),
                    symbol=draft.get("instrument", "ES"),
                    timeframe=draft.get("timeframe", "1m"),
                    timezone=timezone_name.strip(),
                    timestamp_semantics=semantics,
                    roll_policy=roll_policy.strip(),
                    roll_calendar_path=str(roll_calendar_path) if roll_calendar_path else None,
                    timestamp_column=mappings["timestamp"],
                    open_column=mappings["open"],
                    high_column=mappings["high"],
                    low_column=mappings["low"],
                    close_column=mappings["close"],
                    volume_column=mappings["volume"],
                    contract_column=None if contract_choice == "<none>" else contract_choice,
                    single_contract_confirmed=bool(single_contract),
                ),
            )
        except Exception as exc:
            st.error(f"Import stopped: {exc}")
        else:
            imported_dataset = result.manifest.model_dump(mode="json", by_alias=True)
            if draft.get("dataset") != imported_dataset:
                _reset_mechanics_lane(store, campaign_id, draft)
            draft["dataset"] = imported_dataset
            store.save(campaign_id, draft, wizard_step=4 if result.manifest.quality_verdict == "PASS" else 3)
            _advance_wizard(
                st,
                campaign_id,
                4 if result.manifest.quality_verdict == "PASS" else 3,
            )
            if result.manifest.quality_verdict == "PASS":
                st.success("Dataset passed intake and was selected.")
            else:
                st.error(f"Dataset verdict: {result.manifest.quality_verdict}. It cannot enter performance testing.")
            st.json(result.manifest.model_dump(mode="json", by_alias=True), expanded=False)


def _wizard_execution(st: Any, store: Any, campaign_id: str, draft: dict[str, Any]) -> None:
    st.subheader("4. Confirm execution and prop constraints")
    current = draft.get("execution") or {}
    instrument = draft.get("instrument", "ES")
    defaults = {"ES": (0.25, 50.0, 12.5), "NQ": (0.25, 20.0, 5.0)}[instrument]
    with st.form(f"execution_{campaign_id}"):
        a, b, c = st.columns(3)
        session_start = a.text_input("Session start", value=str(current.get("session_start") or "09:30:00"))
        session_end = b.text_input("Session end", value=str(current.get("session_end") or "16:00:00"))
        latest_entry = c.text_input("Latest entry", value=str(current.get("latest_entry_time") or "15:45:00"))
        flatten = a.text_input("Force flatten", value=str(current.get("flatten_time") or "15:55:00"))
        latest_flat = b.text_input("Latest flat", value=str(current.get("latest_flat_time") or "15:56:00"))
        contracts = c.number_input("Contracts", min_value=1, value=int(current.get("contracts") or 1))
        tick_size = a.number_input("Tick size", min_value=0.000001, value=float(current.get("tick_size") or defaults[0]), format="%.6f")
        point_value = b.number_input("Point value", min_value=0.000001, value=float(current.get("point_value") or defaults[1]))
        tick_value = c.number_input("Tick value", min_value=0.000001, value=float(current.get("tick_value") or defaults[2]))
        commission = a.number_input("Commission per contract", min_value=0.0, value=float(current.get("commission_per_contract") or 2.5))
        slippage = b.number_input("Slippage ticks", min_value=0.0, value=float(current.get("slippage_ticks") or 1.0))
        balance = c.number_input("Initial balance", min_value=1.0, value=float(current.get("initial_balance") or 150000.0))
        prop_profile = st.text_input("Prop profile", value=str(current.get("prop_profile") or "configured_local_profile"))
        roll_confirm = st.checkbox("I reviewed the selected dataset's contract roll policy.")
        overnight = st.checkbox("Allow overnight positions", value=False, disabled=True)
        saved = st.form_submit_button("Confirm execution rules", type="primary")
    if saved:
        if not roll_confirm:
            st.error("Review and confirm the contract roll policy before continuing.")
            return
        execution = {
            "session_start": session_start,
            "session_end": session_end,
            "latest_entry_time": latest_entry,
            "flatten_time": flatten,
            "latest_flat_time": latest_flat,
            "overnight_allowed": bool(overnight),
            "initial_balance": float(balance),
            "tick_size": float(tick_size),
            "point_value": float(point_value),
            "tick_value": float(tick_value),
            "commission_per_contract": float(commission),
            "slippage_ticks": float(slippage),
            "contracts": int(contracts),
            "prop_profile": prop_profile.strip(),
        }
        if draft.get("execution") != execution:
            _reset_mechanics_lane(store, campaign_id, draft)
        draft["execution"] = execution
        store.save(campaign_id, draft, wizard_step=5)
        _advance_wizard(st, campaign_id, 5)
        st.success("Execution rules frozen for variant design.")
        st.rerun()


def _wizard_lane(st: Any, root: Path, store: Any, campaign_id: str, draft: dict[str, Any]) -> None:
    from alphaquest.studio.handoffs import new_handoff, write_engineering_handoff

    st.subheader("5. Choose a mechanics lane")
    state = store.load_state(campaign_id)
    stored_lane = state.get("lane") or {
        "certified_recipe": "Certified recipe",
        "visual_completed_bar_rule": "Visual completed-bar rule",
        "engineering_handoff": "Engineering handoff",
    }.get(draft.get("authoring_lane"))
    lane = st.radio(
        "Representation",
        ("Certified recipe", "Visual completed-bar rule", "Engineering handoff"),
        index=_index(("Certified recipe", "Visual completed-bar rule", "Engineering handoff"), stored_lane),
    )
    if lane == "Certified recipe":
        st.success("Only certified completed-bar modules will be available. Legal signals enter at the next bar open.")
        recipe_labels = {
            "Opening-range breakout": "opening_range_breakout",
            "Calendar session bias": "calendar_session_bias",
            "Daily trend · close to close": "daily_tsm_close_to_close",
            "Daily trend · volatility normalized": "daily_tsm_volatility_normalized",
            "Daily trend · short-term alignment": "daily_tsm_short_term_alignment",
        }
        current_recipe = draft.get("certified_recipe")
        selected_label = next(
            (label for label, recipe in recipe_labels.items() if recipe == current_recipe),
            "Opening-range breakout",
        )
        recipe_label = st.selectbox(
            "One economic edge recipe for the campaign's sequential variants",
            tuple(recipe_labels),
            index=_index(tuple(recipe_labels), selected_label),
            help="The entry edge stays fixed. The five cards vary certified risk and exit mechanics only.",
        )
        recipe_confirmed = st.checkbox(
            "I confirm this recipe represents the frozen hypothesis; variants may not substitute another entry edge."
        )
        if st.button("Use reviewed certified recipe", type="primary", disabled=not recipe_confirmed):
            _clear_variant_design(draft)
            draft["authoring_lane"] = "certified_recipe"
            draft["certified_recipe"] = recipe_labels[recipe_label]
            draft["engineering_handoff_path"] = None
            store.save_state(campaign_id, {**state, "lane": lane})
            store.save(campaign_id, draft, wizard_step=6)
            _advance_wizard(st, campaign_id, 6)
            st.rerun()
    elif lane == "Visual completed-bar rule":
        st.info("Build a bounded causal rule. Missing values evaluate false; simultaneous long and short signals emit no trade.")
        certified = list((draft.get("dataset") or {}).get("certified_features") or [])
        features = list(dict.fromkeys(["close", "open", "high", "low", "volume", *certified]))
        condition_type = st.selectbox(
            "Primary condition",
            ("Crossing a prior rolling value", "Comparison with a threshold", "Inside a range"),
            key=f"visual_type_{campaign_id}",
        )
        feature = st.selectbox("Completed-bar feature", features, key=f"visual_feature_{campaign_id}")
        lag = int(
            st.number_input(
                "Feature lag · zero is the just-completed bar",
                min_value=0,
                max_value=512,
                value=0,
                step=1,
                key=f"visual_lag_{campaign_id}",
            )
        )
        visual: dict[str, Any] = {"condition_type": condition_type, "feature": feature, "lag": lag}
        if condition_type == "Crossing a prior rolling value":
            a, b, c = st.columns(3)
            visual["rolling_function"] = a.selectbox(
                "Prior transform", ("mean", "sum", "min", "max", "std"), key=f"visual_fn_{campaign_id}"
            )
            visual["window"] = int(
                b.number_input("Window", min_value=2, max_value=256, value=20, step=1, key=f"visual_window_{campaign_id}")
            )
            visual["direction"] = c.selectbox(
                "Crossing direction", ("above", "below"), key=f"visual_direction_{campaign_id}"
            )
        elif condition_type == "Comparison with a threshold":
            a, b = st.columns(2)
            visual["operator"] = a.selectbox(
                "Comparison", ("greater than", "greater than or equal", "less than", "less than or equal"), key=f"visual_operator_{campaign_id}"
            )
            visual["threshold"] = float(
                b.number_input("Threshold", value=0.0, format="%.8f", key=f"visual_threshold_{campaign_id}")
            )
            visual["tune_threshold"] = st.checkbox(
                "Predeclare alternative threshold values",
                key=f"visual_tunable_{campaign_id}",
                help="The values are frozen now and cannot be chosen from observed PnL.",
            )
            if visual["tune_threshold"]:
                visual["threshold_values"] = st.text_input(
                    "Threshold values · 8–20 comma separated",
                    value=", ".join(map(str, _suggest_grid_values(visual["threshold"], "number"))),
                    key=f"visual_threshold_values_{campaign_id}",
                )
        else:
            a, b = st.columns(2)
            visual["lower"] = float(a.number_input("Lower bound", value=0.0, format="%.8f", key=f"visual_lower_{campaign_id}"))
            visual["upper"] = float(b.number_input("Upper bound", value=1.0, format="%.8f", key=f"visual_upper_{campaign_id}"))
            visual["inclusive"] = st.checkbox("Include boundary values", value=True, key=f"visual_inclusive_{campaign_id}")

        signal_choices = ("Long only", "Short only") if condition_type == "Inside a range" else (
            "Symmetric long and short",
            "Long only",
            "Short only",
        )
        visual["signals"] = st.selectbox("Signals", signal_choices, key=f"visual_signals_{campaign_id}")
        visual["second_filter"] = st.checkbox(
            "Add a second completed-bar filter",
            key=f"visual_second_{campaign_id}",
        )
        if visual["second_filter"]:
            a, b, c = st.columns(3)
            visual["filter_feature"] = a.selectbox("Filter feature", features, key=f"visual_filter_feature_{campaign_id}")
            visual["filter_operator"] = b.selectbox(
                "Filter comparison", ("greater than", "less than"), key=f"visual_filter_operator_{campaign_id}"
            )
            visual["filter_threshold"] = float(
                c.number_input("Filter threshold", value=0.0, format="%.8f", key=f"visual_filter_threshold_{campaign_id}")
            )
            visual["boolean_group"] = st.radio(
                "Combine primary and filter",
                ("All conditions", "Any condition"),
                horizontal=True,
                key=f"visual_group_{campaign_id}",
            )
        a, b, c = st.columns(3)
        visual["signal_start_time"] = a.text_input("Signal start · HH:MM:SS", value="09:30:00", key=f"visual_start_{campaign_id}")
        visual["signal_end_time"] = b.text_input(
            "Signal end · HH:MM:SS",
            value=str((draft.get("execution") or {}).get("latest_entry_time") or "15:45:00"),
            key=f"visual_end_{campaign_id}",
        )
        visual["max_trades_per_day"] = int(
            c.number_input("Maximum trades per day", min_value=1, max_value=20, value=1, step=1, key=f"visual_max_trades_{campaign_id}")
        )
        visual["rth_only"] = st.checkbox("RTH completed bars only", value=True, key=f"visual_rth_{campaign_id}")
        saved = st.button("Validate and save visual rule", type="primary", key=f"visual_save_{campaign_id}")
        if saved:
            try:
                from alphaquest.authoring.bar_rules import validate_bar_rule

                rule = _build_visual_rule(visual, str(draft.get("timeframe") or "1m"))
                rule = validate_bar_rule(rule, certified_features=set(certified)).model_dump(mode="json", by_alias=True)
            except Exception as exc:
                st.error(f"Visual rule is invalid: {exc}")
            else:
                _clear_variant_design(draft)
                draft["authoring_lane"] = "visual_completed_bar_rule"
                draft["certified_recipe"] = None
                draft["engineering_handoff_path"] = None
                store.save_state(campaign_id, {**state, "lane": lane, "safe_bar_rule": rule})
                store.save(campaign_id, draft, wizard_step=6)
                _advance_wizard(st, campaign_id, 6)
                st.success("Causal rule saved. It will be deterministically validated before publication.")
                st.rerun()
    else:
        st.warning("Intrabar, order-flow, event-replay, or custom features are never approximated with OHLC bars.")
        with st.form(f"handoff_{campaign_id}"):
            reason = st.text_area("Why certified completed bars are insufficient")
            timeline = st.text_area("Causal timeline · one event per line")
            granularity = st.text_input("Required data granularity", value="tick-by-tick event replay")
            ambiguity = st.text_area("Fill and ambiguity rules · one per line")
            contract = st.text_area("Required module contract · one requirement per line")
            tests = st.text_area("Required tests · one per line")
            mechanics = st.text_area("Five proposed variant mechanics · exactly one per line")
            generated = st.form_submit_button("Generate engineering handoff", type="primary")
        if generated:
            try:
                handoff = new_handoff(
                    campaign_id=campaign_id,
                    reason_unsupported=reason.strip(),
                    causal_timeline=_lines(timeline),
                    required_data_granularity=granularity.strip(),
                    fill_and_ambiguity_rules=_lines(ambiguity),
                    required_module_contract=_lines(contract),
                    required_tests=_lines(tests),
                    proposed_mechanics=_lines(mechanics),
                )
                path = write_engineering_handoff(handoff, project_root=root)
            except Exception as exc:
                st.error(str(exc))
            else:
                _clear_variant_design(draft)
                draft["authoring_lane"] = "engineering_handoff"
                draft["certified_recipe"] = None
                draft["engineering_handoff_path"] = str(path.relative_to(root))
                store.save_state(campaign_id, {**state, "lane": lane, "handoff_path": str(path)})
                store.save(campaign_id, draft, wizard_step=5)
                st.error("NEEDS MANUAL REVIEW — submission is blocked until an engineer certifies the required implementation.")
                st.code(str(path.relative_to(root)))


def _wizard_variants(st: Any, store: Any, campaign_id: str, draft: dict[str, Any]) -> None:
    from alphaquest.authoring.catalog import get_certified_module_catalog
    from alphaquest.studio.variants import binding_defaults, suggest_variant_cards

    st.subheader("6. Confirm five materially distinct variants before PnL")
    state = store.load_state(campaign_id)
    if draft.get("authoring_lane") == "engineering_handoff" or state.get("lane") == "Engineering handoff":
        st.error("NEEDS MANUAL REVIEW — unsupported mechanics cannot be submitted or approximated.")
        return
    if not draft.get("dataset") or not draft.get("execution"):
        st.warning("Complete governed data intake and execution confirmation in steps 3 and 4 first.")
        return
    if draft.get("authoring_lane") == "certified_recipe" and not draft.get("certified_recipe"):
        st.warning("Return to step 5 and explicitly review one certified edge recipe first.")
        return
    if draft.get("authoring_lane") == "visual_completed_bar_rule" and not isinstance(
        state.get("safe_bar_rule"), dict
    ):
        st.warning("Return to step 5 and validate the visual completed-bar rule first.")
        return
    if draft.get("authoring_lane") not in {"certified_recipe", "visual_completed_bar_rule"}:
        st.warning("Choose and confirm a mechanics lane in step 5 first.")
        return
    variants = list(draft.get("variants") or _suggest_variants_for_lane(draft, state, suggest_variant_cards))
    catalog = get_certified_module_catalog()
    if draft.get("authoring_lane") == "certified_recipe":
        from alphaquest.authoring.models import CERTIFIED_RECIPE_BINDINGS

        recipe = draft.get("certified_recipe")
        if recipe not in CERTIFIED_RECIPE_BINDINGS:
            st.error("Return to step 5 and explicitly review one certified edge recipe.")
            return
        entry_names = [CERTIFIED_RECIPE_BINDINGS[recipe][0]]
    elif draft.get("authoring_lane") == "visual_completed_bar_rule":
        entry_names = ["safe_bar_rule"]
    else:
        entry_names = [item.name for item in catalog.all("entry")]
    stop_names = [item.name for item in catalog.all("sl")]
    target_names = [item.name for item in catalog.all("tp")]
    st.caption("Suggestions use only the frozen brief and certified catalog. No PnL or backtest artifacts are read.")
    edited: list[dict[str, Any]] = []
    parameter_errors: list[str] = []
    with st.form(f"variants_{campaign_id}"):
        for index, variant in enumerate(variants):
            with st.expander(f"Variant {index + 1}: {variant.get('title')}", expanded=index == 0):
                title = st.text_input("Variant title", value=str(variant.get("title") or ""), key=f"variant_title_{campaign_id}_{index}")
                cols = st.columns(3)
                entry = cols[0].selectbox(
                    "Frozen entry edge",
                    entry_names,
                    index=_index(entry_names, (variant.get("entry") or {}).get("module")),
                    key=f"entry_{campaign_id}_{index}",
                    disabled=True,
                )
                stop = cols[1].selectbox("Stop", stop_names, index=_index(stop_names, (variant.get("stop") or {}).get("module")), key=f"stop_{campaign_id}_{index}")
                target = cols[2].selectbox("Target", target_names, index=_index(target_names, (variant.get("target") or {}).get("module")), key=f"target_{campaign_id}_{index}")
                st.markdown("**Mechanic settings and predeclared parameter space**")
                st.caption(
                    "Edit the certified inputs directly. Optional test values are frozen before PnL; the total "
                    "must be either one fixed combination or 8–120 combinations."
                )
                entry_tab, stop_tab, target_tab = st.tabs(("Entry", "Stop", "Target"))
                execution = draft.get("execution") or {}
                with entry_tab:
                    entry_binding, errors = _edit_module_binding(
                        st,
                        catalog,
                        "entry",
                        entry,
                        variant.get("entry"),
                        binding_defaults,
                        execution,
                        state,
                        draft,
                        key=f"{campaign_id}_{index}_entry",
                    )
                    parameter_errors.extend(f"v{index + 1:02d} entry: {item}" for item in errors)
                with stop_tab:
                    stop_binding, errors = _edit_module_binding(
                        st,
                        catalog,
                        "sl",
                        stop,
                        variant.get("stop"),
                        binding_defaults,
                        execution,
                        state,
                        draft,
                        key=f"{campaign_id}_{index}_stop",
                    )
                    parameter_errors.extend(f"v{index + 1:02d} stop: {item}" for item in errors)
                with target_tab:
                    target_binding, errors = _edit_module_binding(
                        st,
                        catalog,
                        "tp",
                        target,
                        variant.get("target"),
                        binding_defaults,
                        execution,
                        state,
                        draft,
                        key=f"{campaign_id}_{index}_target",
                    )
                    parameter_errors.extend(f"v{index + 1:02d} target: {item}" for item in errors)
                combinations = _binding_combinations(entry_binding, stop_binding, target_binding)
                st.caption(f"Predeclared combinations for this variant: {combinations}")
                if combinations != 1 and not 8 <= combinations <= 120:
                    parameter_errors.append(
                        f"v{index + 1:02d}: {combinations} combinations; use exactly 1 or between 8 and 120"
                    )
                rationale = st.text_area("Why this mechanic expresses the edge", value=str(variant.get("mechanic_rationale") or ""), key=f"rationale_{campaign_id}_{index}")
                difference = st.text_input("Material difference from the other four", value=str(variant.get("material_difference") or ""), key=f"difference_{campaign_id}_{index}")
                entry_rationale = st.text_area(
                    "Entry timing rationale",
                    value=str(variant.get("entry_rationale") or ""),
                    key=f"entry_rationale_{campaign_id}_{index}",
                )
                stop_rationale = st.text_area(
                    "Stop-loss rationale",
                    value=str(variant.get("stop_rationale") or ""),
                    key=f"stop_rationale_{campaign_id}_{index}",
                )
                target_rationale = st.text_area(
                    "Target/exit rationale",
                    value=str(variant.get("target_rationale") or ""),
                    key=f"target_rationale_{campaign_id}_{index}",
                )
                timeframe_rationale = st.text_area(
                    "Timeframe and session rationale",
                    value=str(variant.get("timeframe_session_rationale") or ""),
                    key=f"timeframe_rationale_{campaign_id}_{index}",
                )
                confirmed = st.checkbox("I confirm this mechanic before performance testing", value=bool(variant.get("confirmed")), key=f"confirm_{campaign_id}_{index}")
                edited.append(
                    {
                        "schema": "alphaquest.variant-draft/v1",
                        "variant_id": f"v{index + 1:02d}",
                        "title": title.strip(),
                        "entry": entry_binding,
                        "stop": stop_binding,
                        "target": target_binding,
                        "mechanic_rationale": rationale.strip(),
                        "entry_rationale": entry_rationale.strip(),
                        "stop_rationale": stop_rationale.strip(),
                        "target_rationale": target_rationale.strip(),
                        "timeframe_session_rationale": timeframe_rationale.strip(),
                        "known_failure_modes": draft.get("known_failure_modes") or ["Hypothesized behavior may be absent."],
                        "material_difference": difference.strip(),
                        "confirmed": confirmed,
                    }
                )
        saved = st.form_submit_button("Save the initial variant card", type="primary")
    if saved:
        if parameter_errors:
            st.error("Variant settings are not ready:\n- " + "\n- ".join(parameter_errors))
            return
        draft["variants"] = edited
        if all(item["confirmed"] for item in edited):
            from alphaquest.authoring import campaign_confirmation_context_sha256

            draft["confirmation_context_sha256"] = campaign_confirmation_context_sha256(draft)
        else:
            draft.pop("confirmation_context_sha256", None)
        store.save(campaign_id, draft, wizard_step=7 if all(item["confirmed"] for item in edited) else 6)
        _advance_wizard(
            st,
            campaign_id,
            7 if all(item["confirmed"] for item in edited) else 6,
        )
        if all(item["confirmed"] for item in edited):
            st.success("The initial mechanic was confirmed before PnL.")
        else:
            st.warning("Every card must be confirmed before protocol freeze.")
        st.rerun()


def _wizard_protocol(st: Any, root: Path, store: Any, campaign_id: str, draft: dict[str, Any]) -> None:
    st.subheader("7. Review the protocol, preflight, and freeze")
    state = store.load_state(campaign_id)
    if draft.get("authoring_lane") == "engineering_handoff" or state.get("lane") == "Engineering handoff":
        st.error("NEEDS MANUAL REVIEW — engineering handoff is durable, but this idea cannot be submitted yet.")
        return
    variants = draft.get("variants") or []
    st.markdown(
        f"This campaign tests **{draft.get('hypothesis', 'an undeclared hypothesis')}** on "
        f"**{draft.get('instrument')} {draft.get('timeframe')}** using one initial frozen mechanic. "
        "Signals are decided after completed bars and legal entries occur no earlier than the next bar open. "
        "Each variant stops at its first failed scientific gate; later variants continue."
    )
    checklist = {
        "source_and_hypothesis": bool(draft.get("sources") and draft.get("hypothesis") and draft.get("expected_mechanism")),
        "duplicate_distinct": (draft.get("duplicate_review") or {}).get("conclusion") == "distinct",
        "dataset_pass": (draft.get("dataset") or {}).get("quality_verdict") == "PASS",
        "execution_confirmed": bool(draft.get("execution")),
        "one_edge_recipe_reviewed": (
            draft.get("authoring_lane") == "visual_completed_bar_rule"
            or bool(draft.get("certified_recipe"))
        ),
        "initial_variant": len(variants) == 1,
        "initial_variant_confirmed": len(variants) == 1 and all(item.get("confirmed") for item in variants),
    }
    st.dataframe([{"gate": key.replace("_", " "), "ready": value} for key, value in checklist.items()], hide_index=True, use_container_width=True)
    confirmation = st.checkbox("Freeze this protocol. Any later mechanics or data change requires a new governed attempt.")
    if st.button("Validate and freeze", type="primary", disabled=not confirmation):
        from pydantic import ValidationError

        from alphaquest.authoring.models import CampaignDraftV1
        from alphaquest.studio.publishing import StudioPublicationService

        candidate = {**draft, "frozen": True}
        if not all(checklist.values()):
            st.error("Freeze blocked by unresolved workflow gates.")
            return
        try:
            parsed = CampaignDraftV1.model_validate(candidate)
            preflight = StudioPublicationService(root).preflight_draft(parsed)
        except (ValidationError, ValueError, OSError, RuntimeError) as exc:
            st.error("Freeze blocked. Resolve every strict contract error below.")
            errors = exc.errors() if isinstance(exc, ValidationError) else [{"loc": ("publication_preflight",), "msg": str(exc)}]
            st.dataframe(
                [
                    {
                        "field": ".".join(str(part) for part in item.get("loc", ())),
                        "message": item.get("msg"),
                    }
                    for item in errors
                ],
                use_container_width=True,
                hide_index=True,
            )
        else:
            store.save(campaign_id, candidate, wizard_step=7)
            st.success(
                f"Protocol is immutable after publication preflight: "
                f"{preflight['preflight_verdict']}."
            )
            st.rerun()


def _render_published_actions(st: Any, root: Path, campaign_id: str) -> None:
    st.subheader("Governed actions")
    _render_results_matrix(st, root, campaign_id)
    st.info(
        "First generate mechanics evidence, inspect every required sample, and approve the current frozen "
        "variants. Performance testing remains locked until those approvals are current."
    )
    from alphaquest.studio.followups import FollowUpAttemptService
    from alphaquest.validation.promotion_gate import inspect_validation_gate

    import yaml

    follow_ups = FollowUpAttemptService(root)
    attempts = follow_ups.list_attempts(campaign_id)
    _render_follow_up_creator(st, root, campaign_id, follow_ups, attempts)
    attempt_ids = [str(item["attempt_id"]) for item in attempts]
    preferred = st.session_state.get(f"selected_attempt_{campaign_id}")
    selected_attempt = st.selectbox(
        "Attempt identity",
        attempt_ids,
        index=attempt_ids.index(preferred) if preferred in attempt_ids else len(attempt_ids) - 1,
        format_func=lambda item: next(
            f"{item} · {row.get('attempt_kind')}" for row in attempts if row.get("attempt_id") == item
        ),
        key=f"attempt_select_{campaign_id}",
    )
    st.session_state[f"selected_attempt_{campaign_id}"] = selected_attempt
    selected_row = next(row for row in attempts if row.get("attempt_id") == selected_attempt)
    if selected_attempt != "original":
        st.caption(
            f"Parent: {selected_row.get('parent_attempt_id')} · reason: {selected_row.get('reason')}"
        )
    config_paths = list(follow_ups.config_paths(campaign_id, selected_attempt))
    gate_rows: list[dict[str, Any]] = []
    unresolved_configs: list[Path] = []
    for config_path in config_paths:
        try:
            config = yaml.safe_load(config_path.read_text(encoding="utf-8")) or {}
            gate = inspect_validation_gate(config, config_path)
        except Exception as exc:
            gate = {
                "status": "BLOCKED",
                "errors": [str(exc)],
                "config_hash": None,
                "input_data_hash": None,
            }
        if gate.get("status") != "APPROVED_FOR_TESTING":
            unresolved_configs.append(config_path)
        evidence_value = gate.get("evidence_dir")
        evidence_ready = bool(evidence_value and Path(str(evidence_value)).is_dir())
        gate_rows.append(
            {
                "variant": config_path.parent.name,
                "mechanics status": gate.get("status"),
                "evidence": "ready" if evidence_ready else "not generated",
                "approval": gate.get("approval_status") or "not approved",
                "blocker": "; ".join(str(item) for item in gate.get("errors") or []),
            }
        )
    if gate_rows:
        st.dataframe(gate_rows, use_container_width=True, hide_index=True)
    if unresolved_configs:
        if st.button(
            "Generate mechanics evidence · current variant",
            type="primary",
            key=f"mechanics_{campaign_id}_{selected_attempt}",
        ):
            try:
                jobs = follow_ups.queue_mechanics_validation(campaign_id, selected_attempt)
            except Exception as exc:
                st.error(f"Mechanics evidence submission blocked: {exc}")
            else:
                st.success(
                    "Mechanics evidence jobs are queued. The local worker continues after the browser closes; "
                    "review the completed evidence in Review Queue."
                )
                st.json([_serializable(job) for job in jobs], expanded=False)
    try:
        from alphaquest.studio.approvals import require_all_variant_mechanics_approved

        approvals = require_all_variant_mechanics_approved(config_paths)
    except Exception as exc:
        st.warning(f"Mechanics approval gate: {exc}")
        approvals = None
    if approvals:
        st.success("The current mechanics approval is valid. Queue submission is available.")
        if st.button(
            "Run full test suite · current variant",
            type="primary",
            key=f"run_{campaign_id}_{selected_attempt}",
        ):
            try:
                jobs = follow_ups.queue_performance(campaign_id, selected_attempt)
            except Exception as exc:
                st.error(f"Submission blocked: {exc}")
            else:
                st.success("Campaign queued in declared variant order. Closing this browser will not stop the worker.")
                st.json([_serializable(job) for job in jobs], expanded=False)


def _render_follow_up_creator(
    st: Any,
    root: Path,
    campaign_id: str,
    service: Any,
    attempts: list[dict[str, Any]],
) -> None:
    """Novice-safe controls for explicit post-publication scientific lineage."""

    from alphaquest.studio.followups import FollowUpAttemptRequestV1
    from alphaquest.studio.settings import load_settings
    from alphaquest.studio.workspace import list_dataset_manifests

    labels = {
        "replication": "Replication · same frozen protocol, new evidence identity",
        "data_refresh": "Data refresh · same mechanics, new governed dataset",
        "methodology_rerun": "Methodology rerun · same mechanics/data under current full stages",
        "pre_pnl_mechanics_correction": "Pre-PnL mechanics correction · explicit scalar correction",
        "pre_pnl_parameter_declaration": "Pre-PnL parameter declaration · freeze tunable names and grids",
        "rescue": "Authorized rescue · one permitted change after a FAIL",
    }
    with st.expander("Create an explicit governed follow-up", expanded=False):
        st.warning(
            "Original definitions and evidence remain immutable. A blocked or interrupted job is never replayed; "
            "this action creates a new attempt identity with fresh mechanics approval and run paths."
        )
        parent_ids = [str(item["attempt_id"]) for item in attempts]
        parent = st.selectbox("Parent attempt", parent_ids, key=f"follow_parent_{campaign_id}")
        kind = st.selectbox(
            "Follow-up type",
            tuple(labels),
            format_func=labels.get,
            key=f"follow_kind_{campaign_id}",
        )
        settings = load_settings(project_root=root)
        parent_paths = service.config_paths(campaign_id, parent)
        parent_config = __import__("yaml").safe_load(parent_paths[0].read_text(encoding="utf-8")) or {}
        created_by = st.text_input(
            "Researcher identity",
            value=settings.reviewer_identity,
            key=f"follow_creator_{campaign_id}",
        )
        reason = st.text_area(
            "Substantive reason · at least 80 characters",
            help="Explain why this new attempt is scientifically warranted and what remains unchanged.",
            key=f"follow_reason_{campaign_id}",
        )
        dataset_id = None
        target_variant = None
        authorized_by = None
        patches: list[dict[str, Any]] = []
        parameter_grid: dict[str, list[Any]] = {}
        if kind == "data_refresh":
            datasets = [
                row
                for row in list_dataset_manifests(root)
                if row.get("quality_verdict") == "PASS"
                and row.get("symbol") == parent_config.get("symbol")
                and row.get("timeframe") == parent_config.get("timeframe")
            ]
            if not datasets:
                st.error("Import a governed dataset with quality verdict PASS before creating a data refresh.")
            else:
                dataset_id = st.selectbox(
                    "Governed replacement dataset",
                    [str(row["dataset_id"]) for row in datasets],
                    key=f"follow_dataset_{campaign_id}",
                )
        if kind in {"pre_pnl_mechanics_correction", "rescue"}:
            target_variant = st.selectbox(
                "Variant whose mechanic changes",
                [path.parent.name for path in parent_paths],
                key=f"follow_variant_{campaign_id}",
            )
            config_path = next(path for path in parent_paths if path.parent.name == target_variant)
            config = __import__("yaml").safe_load(config_path.read_text(encoding="utf-8")) or {}
            component = st.selectbox(
                "Mechanics component",
                ("entry", "sl", "tp"),
                format_func=lambda item: {"entry": "Entry", "sl": "Stop", "tp": "Target"}[item],
                key=f"follow_component_{campaign_id}",
            )
            params = (((config.get("strategy") or {}).get(component) or {}).get("params") or {})
            scalar_options = _scalar_parameter_options(params)
            if not scalar_options:
                st.error("This component has no scalar parameter that Studio can correct safely.")
            else:
                parameter = st.selectbox(
                    "Reviewed parameter",
                    tuple(scalar_options),
                    key=f"follow_parameter_{campaign_id}_{component}",
                )
                old_value = scalar_options[parameter]
                widget_key = f"follow_value_{campaign_id}_{component}_{parameter}"
                if isinstance(old_value, bool):
                    new_value = st.selectbox("Corrected value", (True, False), index=int(not old_value), key=widget_key)
                elif isinstance(old_value, int):
                    new_value = int(st.number_input("Corrected value", value=old_value, step=1, key=widget_key))
                elif isinstance(old_value, float):
                    new_value = float(st.number_input("Corrected value", value=old_value, key=widget_key))
                else:
                    new_value = st.text_input("Corrected value", value=str(old_value), key=widget_key)
                patches = [
                    {
                        "variant_id": target_variant,
                        "component": component,
                        "parameter_path": parameter,
                        "value": new_value,
                    }
                ]
            if kind == "rescue":
                authorized_by = st.text_input(
                    "Rescue authorizer identity",
                    help="The campaign must permit rescue and the parent target must have an immutable FAIL.",
                    key=f"follow_authorizer_{campaign_id}",
                )
        if kind == "pre_pnl_parameter_declaration":
            target_variant = st.selectbox(
                "Variant whose pre-PnL parameter space is declared",
                [path.parent.name for path in parent_paths],
                key=f"follow_grid_variant_{campaign_id}",
            )
            raw_grid = st.text_area(
                "Certified event parameter grid · JSON object",
                value='{"max_aoi_width_points": [3, 4, 5, 6], "entry_offset_ticks": [0, 1, 2, 3, 4], "stop_offset_ticks": [0, 1, 2, 3, 4]}',
                help="Use certified parameter names only. Every grid must include its reviewed default.",
                key=f"follow_grid_{campaign_id}",
            )
            try:
                decoded = __import__("json").loads(raw_grid)
                if isinstance(decoded, dict):
                    parameter_grid = decoded
                else:
                    st.error("The parameter grid must be a JSON object.")
            except ValueError as exc:
                st.error(f"Parameter grid JSON is invalid: {exc}")
        confirmed = st.checkbox(
            "Create a new immutable attempt; do not alter or replay the parent.",
            key=f"follow_confirm_{campaign_id}",
        )
        disabled = (
            not confirmed
            or not created_by.strip()
            or len(reason.strip()) < 80
            or (kind == "data_refresh" and not dataset_id)
            or (kind in {"pre_pnl_mechanics_correction", "rescue"} and not patches)
            or (kind == "pre_pnl_parameter_declaration" and not parameter_grid)
            or (kind == "rescue" and not str(authorized_by or "").strip())
        )
        if st.button(
            "Create governed follow-up",
            type="primary",
            disabled=disabled,
            key=f"follow_create_{campaign_id}",
        ):
            try:
                request = FollowUpAttemptRequestV1.model_validate(
                    {
                        "campaign_id": campaign_id,
                        "attempt_kind": kind,
                        "parent_attempt_id": parent,
                        "reason": reason,
                        "created_by": created_by,
                        "dataset_id": dataset_id,
                        "target_variant_id": target_variant,
                        "authorized_by": authorized_by,
                        "mechanic_patches": patches,
                        "parameter_grid": parameter_grid,
                    }
                )
                result = service.create(request)
            except Exception as exc:
                st.error(f"Follow-up creation stopped before installation: {exc}")
            else:
                st.session_state[f"selected_attempt_{campaign_id}"] = result.attempt_id
                st.session_state[f"attempt_select_{campaign_id}"] = result.attempt_id
                st.success(f"Created {result.attempt_id}. {result.next_action}")
                st.rerun()


def _scalar_parameter_options(value: dict[str, Any], prefix: str = "") -> dict[str, Any]:
    context_bound = {
        "bar_interval_minutes",
        "tick_size",
        "tick_value",
        "commission_per_contract",
        "slippage_ticks",
        "rth_start",
        "rth_end",
        "last_entry_time",
        "signal_start_time",
        "signal_end_time",
    }
    options: dict[str, Any] = {}
    for key, item in value.items():
        path = f"{prefix}.{key}" if prefix else str(key)
        if isinstance(item, dict):
            options.update(_scalar_parameter_options(item, path))
        elif key not in context_bound and (isinstance(item, (str, int, float, bool)) or item is None):
            options[path] = item
    return options


def _render_job_status(st: Any, root: Path) -> None:
    from alphaquest.studio.jobs import OperationalState, SQLiteJobQueue
    from alphaquest.research.storage import load_storage_layout

    database = load_storage_layout(root).studio_runtime_root / "jobs.sqlite3"
    if not database.is_file():
        return
    queue = SQLiteJobQueue(database)
    jobs = queue.list_jobs(limit=25)
    if not jobs:
        return
    st.subheader("Local worker queue")
    st.caption("Operational state is separate from the scientific research verdict.")
    st.dataframe(
        [
            {
                "job ID": job.job_id,
                "job": job.job_type,
                "campaign": job.campaign_id,
                "variant": job.payload.get("variant_id"),
                "operational state": job.state.value,
                "research verdict": job.research_verdict,
                "attempt reserved": job.attempt_reserved,
                "blocker/error": job.blocked_reason or job.error,
                "next action": _job_next_action(job),
            }
            for job in jobs
        ],
        use_container_width=True,
        hide_index=True,
    )
    cancellable = [
        job
        for job in jobs
        if job.state in {OperationalState.QUEUED, OperationalState.RUNNING, OperationalState.CANCEL_REQUESTED}
    ]
    if cancellable:
        selected = st.selectbox(
            "Cancel queued or running work",
            [job.job_id for job in cancellable],
            format_func=lambda job_id: next(
                f"{job.payload.get('variant_id')} · {job.state.value} · {job_id[:8]}"
                for job in cancellable
                if job.job_id == job_id
            ),
        )
        if st.button("Request cancellation"):
            job = queue.request_cancel(selected)
            st.warning(
                f"Cancellation state: {job.state.value}. If evidence was already reserved, the research verdict becomes NEEDS MANUAL REVIEW."
            )
            st.rerun()


def _job_next_action(job: Any) -> str | None:
    result = job.result if isinstance(job.result, dict) else {}
    if result.get("next_action"):
        return str(result["next_action"])
    if not job.attempt_reserved and (
        str(job.state.value) == "BLOCKED" or job.research_verdict == "NEEDS MANUAL REVIEW"
    ):
        return (
            "Open Campaigns and create an explicit replication, data refresh, methodology rerun, "
            "pre-PnL mechanics correction, or authorized rescue. The blocked job will not replay."
        )
    if job.attempt_reserved and job.research_verdict == "NEEDS MANUAL REVIEW":
        return "Inspect preserved partial evidence, then create an explicit governed follow-up; never replay this attempt."
    return None


def _render_review_queue(st: Any, root: Path) -> None:
    from alphaquest.studio.workspace import list_review_queue

    st.title("Review Queue")
    st.write("Mechanics review verifies implementation against the frozen specification—not profitability.")
    queue = list_review_queue(root)
    if queue:
        st.dataframe(queue, use_container_width=True, hide_index=True)
    else:
        st.info("No unresolved run or candidate items are indexed.")
    mechanics, candidate = st.tabs(("Mechanics inspector", "Candidate sign-off"))
    with mechanics:
        from alphaquest.dashboard.validation_app import main as validation_main

        validation_main(embedded=True, project_root=root)
        st.divider()
        st.subheader("Finalize mechanics decision")
        st.caption("Self-review is allowed here and means only: implementation matches the frozen specification.")
        from alphaquest.studio.approvals import MechanicsApprovalService
        from alphaquest.studio.settings import load_settings

        try:
            config_paths = _governed_review_config_paths(root)
        except Exception as exc:
            config_paths = []
            st.error(f"Governed mechanics definitions could not be resolved: {exc}")
        if not config_paths:
            st.info("No active frozen variant configs are available.")
        else:
            selected_config = st.selectbox(
                "Frozen variant",
                config_paths,
                format_func=lambda path: str(path.relative_to(root)),
                key="mechanics_approval_config",
            )
            plan = MechanicsApprovalService().plan(selected_config)
            st.dataframe(
                [
                    {"sample category": category, "trade IDs": ", ".join(map(str, trade_ids)) or "none"}
                    for category, trade_ids in plan.sampling_categories.items()
                ],
                use_container_width=True,
                hide_index=True,
            )
            if plan.blockers or plan.unreviewed_trade_ids or plan.non_correct_trade_ids:
                st.warning(
                    "Approval is not ready. Resolve automated blockers and mark every sampled trade Correct in the inspector."
                )
                if plan.blockers:
                    st.write(plan.blockers)
                if plan.unreviewed_trade_ids:
                    st.write("Unreviewed:", plan.unreviewed_trade_ids)
                if plan.non_correct_trade_ids:
                    st.write("Not marked Correct:", plan.non_correct_trade_ids)
            settings = load_settings(project_root=root)
            reviewer = st.text_input("Mechanics reviewer", value=settings.reviewer_identity, key="mechanics_reviewer")
            notes = st.text_area("Mechanics review notes", key="mechanics_notes")
            approve, reject = st.columns(2)
            if approve.button("Approve implementation for testing", type="primary", disabled=not plan.ready_for_approval):
                try:
                    payload = MechanicsApprovalService().approve(selected_config, reviewer=reviewer, notes=notes)
                except Exception as exc:
                    st.error(str(exc))
                else:
                    st.success("Hash-, data-, lane-, schema-, and sample-bound approval written. Profitability approval remains false.")
                    st.json(payload, expanded=False)
            if reject.button("Reject mechanics"):
                try:
                    payload = MechanicsApprovalService().reject(selected_config, reviewer=reviewer, notes=notes)
                except Exception as exc:
                    st.error(str(exc))
                else:
                    st.error("Mechanics rejected before performance testing.")
                    st.json(payload, expanded=False)
    with candidate:
        st.warning("A terminal PASS remains review_queue until a separately identified reviewer signs candidate_review.json.")
        from alphaquest.research.storage import load_storage_layout
        from alphaquest.studio.finalization import inspect_finalized_result
        from alphaquest.studio.results import load_result_bundle

        layout = load_storage_layout(root)
        discovered_bundle_paths = sorted(
            path
            for evidence_root in layout.evidence_roots
            for path in evidence_root.glob("**/reporting_v2/result_bundle_v2.json")
        )
        bundle_paths: list[Path] = []
        incomplete_count = 0
        for path in discovered_bundle_paths:
            inspection = inspect_finalized_result(path)
            if inspection["valid"]:
                bundle_paths.append(path)
            else:
                incomplete_count += 1
        if incomplete_count:
            st.warning(
                f"{incomplete_count} result transaction(s) are incomplete or hash-invalid and remain "
                "NEEDS MANUAL REVIEW; candidate sign-off is blocked."
            )
        if not bundle_paths:
            st.info("No finalized ResultBundleV2 is awaiting review.")
        else:
            selected_bundle = st.selectbox(
                "Finalized result",
                bundle_paths,
                format_func=lambda path: str(path.relative_to(root)),
            )
            bundle = load_result_bundle(selected_bundle)
            try:
                config_path = _resolve_result_config(
                    root,
                    selected_bundle,
                    campaign_id=bundle.campaign_id,
                    variant_id=bundle.variant_id,
                    run_id=bundle.run_id,
                )
            except Exception as exc:
                config_path = None
                st.error(f"Finalized result source config is unresolved: {exc}")
            if config_path is not None:
                st.caption(f"Frozen config resolved automatically: {config_path.relative_to(root)}")
            reviewer = st.text_input("Independent reviewer identity")
            decision = st.selectbox("Decision", ("needs_manual_review", "approved_candidate", "rejected"))
            notes = st.text_area("Review notes")
            if st.button(
                "Write candidate review",
                disabled=not reviewer or config_path is None or not config_path.is_file(),
            ):
                try:
                    from alphaquest.studio.candidate_review import CandidateReviewService

                    service = CandidateReviewService()
                    result = service.review(
                        result_bundle_path=selected_bundle,
                        config_path=config_path,
                        reviewer=reviewer,
                        decision=decision,
                        notes=notes,
                    )
                except Exception as exc:
                    st.error(str(exc))
                else:
                    st.success("Candidate review recorded. Generated registry/views will promote only a valid independent sign-off.")
                    st.json(_serializable(result), expanded=False)


def _governed_review_config_paths(root: Path) -> list[Path]:
    """Resolve originals and follow-ups through their immutable source contracts."""

    from alphaquest.research.storage import load_storage_layout
    from alphaquest.studio.followups import FollowUpAttemptService

    service = FollowUpAttemptService(root)
    active_root = load_storage_layout(root).active_campaign_root
    paths: list[Path] = []
    for campaign_path in sorted(active_root.glob("*/campaign.yaml")):
        campaign_id = campaign_path.parent.name
        for attempt in service.list_attempts(campaign_id):
            paths.extend(service.config_paths(campaign_id, str(attempt["attempt_id"])))
    return sorted(set(paths))


def _resolve_result_config(
    root: Path,
    result_bundle_path: Path,
    *,
    campaign_id: str,
    variant_id: str,
    run_id: str,
) -> Path:
    """Resolve ResultBundleV2 to its exact original or follow-up source config."""

    from alphaquest.studio.finalization import inspect_finalized_result
    from alphaquest.studio.followups import FollowUpAttemptService

    inspection = inspect_finalized_result(result_bundle_path)
    if not inspection["valid"]:
        raise ValueError("finalization is incomplete or hash-invalid: " + "; ".join(inspection["errors"]))
    manifest = inspection["manifest"] or {}
    source = manifest.get("source_config")
    if not source:
        raise ValueError("finalization manifest does not record source_config")
    config_path = Path(str(source))
    config_path = config_path.resolve() if config_path.is_absolute() else (root / config_path).resolve()
    if not config_path.is_file():
        raise FileNotFoundError(f"finalized source config is missing: {config_path}")
    try:
        cfg = __import__("yaml").safe_load(config_path.read_text(encoding="utf-8")) or {}
    except Exception as exc:
        raise ValueError(f"finalized source config is unreadable: {exc}") from exc
    expected = {
        "campaign_id": campaign_id,
        "variant_id": variant_id,
        "test_run_id": run_id,
    }
    mismatches = [key for key, value in expected.items() if str(cfg.get(key) or "") != str(value)]
    if mismatches:
        raise ValueError("finalized source config identity mismatch: " + ", ".join(mismatches))
    attempt_id = str(cfg.get("attempt_id") or "")
    governed = FollowUpAttemptService(root).config_paths(campaign_id, attempt_id)
    if config_path not in governed:
        raise ValueError("finalized source config is not part of its governed sequential attempt")
    bound = inspect_finalized_result(result_bundle_path, config_path=config_path)
    if not bound["valid"]:
        raise ValueError("finalized source binding is invalid: " + "; ".join(bound["errors"]))
    return config_path


def _render_libraries(st: Any, root: Path) -> None:
    from alphaquest.authoring.catalog import get_certified_module_catalog
    from alphaquest.studio.workspace import list_dataset_manifests

    st.title("Libraries")
    modules, datasets = st.tabs(("Certified mechanics", "Governed datasets"))
    with modules:
        catalog = get_certified_module_catalog()
        for manifest in catalog.all():
            with st.expander(f"{manifest.module_type.upper()} · {manifest.name}"):
                st.write(manifest.summary)
                st.caption(f"Decision timing: {manifest.decision_timing} · next-bar entry: {manifest.next_bar_entry}")
                st.dataframe(
                    [
                        {"parameter": name, "type": spec.value_type, "required": spec.required, "tunable": spec.tunable, "description": spec.description}
                        for name, spec in manifest.parameters.items()
                    ],
                    hide_index=True,
                    use_container_width=True,
                )
        st.info("All other legacy modules remain executable for existing campaigns but are developer-only in Studio.")
    with datasets:
        rows = list_dataset_manifests(root)
        if rows:
            st.dataframe(rows, use_container_width=True, hide_index=True)
        else:
            st.info("Import a local CSV or Parquet file from Campaigns → Dataset.")


def _render_tutorial(st: Any, root: Path) -> None:
    st.title("15-minute Studio walkthrough")
    st.write(
        "Practice the same intake → preflight → mechanics review → approval → staged-result flow on "
        "isolated synthetic bars. The run uses the governed Studio services inside a disposable workspace; "
        "each checkpoint unlocks the next, and no terminal, code, or YAML is required."
    )
    steps = (
        (
            "Research declaration",
            "Review a falsifiable claim: a completed weekday bar predicts continuation at the next bar open. "
            "Known failure: a market-wide drift can make arbitrary entry times look profitable.",
        ),
        (
            "Duplicate review",
            "Confirm this is a permanently isolated teaching edge. It is never compared with, written to, "
            "or promoted into the production research ledger.",
        ),
        (
            "Governed data preflight",
            "Inspect synthetic ES-like bars with America/New_York timezone, bar-open timestamps, fixed seed, "
            "explicit OHLCV checks, and a warning that the trend was constructed.",
        ),
        (
            "Execution protocol",
            "Confirm tick value, costs, next-bar entry, intraday cutoff, forced flatten, pessimistic ambiguity, "
            "and no overnight exposure before any result is visible.",
        ),
        (
            "Five frozen mechanics",
            "Review five value-independent mechanic signatures. They share one teaching edge and vary risk or "
            "exit structure; none was suggested from observed PnL.",
        ),
        (
            "Mechanics approval",
            "Self-review means only that implementation matches the frozen specification. It does not approve "
            "profitability or candidate status.",
        ),
        (
            "Staged result review",
            "Run the isolated durable queue and strict result-bundle flow, lead with the five-row gate matrix, "
            "and reject positive core PnL if the seeded randomized-entry benchmark performs better. Full WFA, "
            "incubation, and acceptance remain NOT_RUN because ten synthetic sessions cannot satisfy them.",
        ),
    )
    current = int(st.session_state.get("tutorial_checkpoint", 0))
    for index, (title, explanation) in enumerate(steps, start=1):
        if index <= current:
            st.success(f"{index}. {title} — reviewed")
        elif index == current + 1:
            st.subheader(f"{index}. {title}")
            st.write(explanation)
            if index < len(steps):
                if st.button(f"Confirm step {index}", type="primary", key=f"tutorial_confirm_{index}"):
                    st.session_state["tutorial_checkpoint"] = index
                    st.rerun()
            break
        else:
            st.caption(f"{index}. {title} — locked until the prior checkpoint is reviewed")

    result = st.session_state.get("tutorial_result")
    if current == len(steps) - 1 and st.button(
        "Run isolated staged tutorial",
        type="primary",
        key="tutorial_execute",
    ):
        from alphaquest.tutorial import run_tutorial

        with st.spinner("Generating synthetic bars and running the tutorial..."):
            result = run_tutorial(output_root=root / "examples/tutorial_campaign/generated", execute=True)
        st.session_state["tutorial_result"] = result
        st.session_state["tutorial_checkpoint"] = len(steps)
    if isinstance(result, dict):
        st.success("Tutorial execution completed. This output is prohibited from research promotion.")
        services = result.get("governed_services")
        if isinstance(services, dict):
            st.markdown("**Governed services exercised in the isolated workspace**")
            st.dataframe(
                [
                    {
                        "workflow boundary": name.replace("_", " "),
                        "service": details.get("service"),
                    }
                    for name, details in services.items()
                    if isinstance(details, dict)
                ],
                use_container_width=True,
                hide_index=True,
            )
        matrix = result.get("stage_matrix")
        if isinstance(matrix, list):
            st.markdown("**Sequential variant stage matrix · first failed gate leads**")
            st.dataframe(matrix, use_container_width=True, hide_index=True)
        if result.get("research_verdict") == "FAIL":
            st.error("Final research verdict: FAIL — promising core PnL did not beat randomized entries.")
        else:
            st.warning(f"Final research verdict: {result.get('research_verdict')}")
        st.json(result, expanded=False)
    if current or isinstance(result, dict):
        if st.button("Reset tutorial", key="tutorial_reset"):
            st.session_state.pop("tutorial_checkpoint", None)
            st.session_state.pop("tutorial_result", None)
            st.rerun()


def _render_settings(st: Any, root: Path) -> None:
    from alphaquest.studio.ai import save_api_key
    from alphaquest.studio.settings import load_settings, save_settings

    st.title("Settings")
    settings = load_settings(project_root=root)
    with st.form("studio_settings"):
        reviewer = st.text_input("Default researcher/reviewer identity", value=settings.reviewer_identity)
        model = st.text_input("Administrator-configured OpenAI model ID · optional", value=settings.openai_model or "")
        retention_notice = st.text_area(
            "Administrator-recorded OpenAI organization retention policy",
            value=settings.openai_retention_notice,
            help="Describe the organization's actual endpoint controls. Do not claim zero retention unless enabled for this API organization.",
        )
        zero_retention = st.checkbox(
            "Administrator confirms Zero Data Retention is enabled for this OpenAI API organization",
            value=settings.openai_zero_data_retention_enabled,
        )
        privacy = st.checkbox(
            "I understand AI drafting sends only selected notes/PDF text; organization retention controls still apply.",
            value=settings.privacy_notice_acknowledged,
        )
        saved = st.form_submit_button("Save local settings", type="primary")
    if saved:
        try:
            settings.reviewer_identity = reviewer.strip()
            settings.openai_model = model.strip()
            settings.openai_retention_notice = retention_notice.strip()
            settings.openai_zero_data_retention_enabled = zero_retention
            settings.privacy_notice_acknowledged = privacy
            save_settings(settings, project_root=root)
        except ValueError as exc:
            st.error(f"Settings were not saved: {exc}")
        else:
            st.success("Settings saved in the ignored local Studio runtime root.")
    st.subheader("Optional AI drafting")
    st.write("Studio works fully without an API key. Model output is an untrusted suggestion and requires deterministic validation plus explicit confirmation.")
    api_key = st.text_input("OpenAI API key", type="password")
    if st.button("Store key in macOS keychain", disabled=not api_key):
        try:
            save_api_key(api_key)
        except Exception as exc:
            st.error(str(exc))
        else:
            st.success("Key stored in the operating-system keychain; it was not written to the workspace.")
    st.info(settings.openai_retention_notice)
    if settings.openai_zero_data_retention_enabled:
        st.caption("Administrator record: Zero Data Retention is enabled for this API organization.")
    else:
        st.caption("AI requests use store=false and no tools. Studio does not promise zero retention.")


def _render_ai_drafting(st: Any, store: Any, campaign_id: str, draft: dict[str, Any]) -> None:
    from alphaquest.studio.ai import OpenAIResearchDraftAdapter, extract_pdf_text
    from alphaquest.studio.settings import load_settings

    state = store.load_state(campaign_id)
    settings = load_settings(project_root=store.project_root)
    with st.expander("Optional AI-assisted first draft · no API key required for manual forms"):
        st.caption(
            "Only the text you paste or the PDF pages you select are sent. Market data, backtest results, files, "
            "web tools, and execution access are excluded. The response is untrusted until you apply and confirm it."
        )
        st.info(settings.openai_retention_notice)
        notes = st.text_area("Selected research notes", key=f"ai_notes_{campaign_id}")
        pdf = st.file_uploader("Optional local PDF", type=("pdf",), key=f"ai_pdf_{campaign_id}")
        pages_text = st.text_input(
            "PDF pages to extract · one-based, comma separated",
            placeholder="1,2,5",
            key=f"ai_pages_{campaign_id}",
        )
        source_title = st.text_input(
            "Source title sent with the selected text",
            value=str(((draft.get("sources") or [{}])[0]).get("title") or ""),
            key=f"ai_source_{campaign_id}",
        )
        prose_confirmed = st.checkbox(
            "I confirm the selected text is research prose only and contains no market-data rows, raw file "
            "contents, trade logs, or observed backtest metrics.",
            key=f"ai_prose_only_{campaign_id}",
        )
        if st.button("Generate schema-bound suggestion", key=f"ai_generate_{campaign_id}"):
            if not settings.openai_model:
                st.error("An administrator-configured model ID is required in Settings. No moving alias is assumed.")
            elif not settings.privacy_notice_acknowledged:
                st.error("Acknowledge the organization-retention notice in Settings first.")
            elif not prose_confirmed:
                st.error("Confirm the prose-only privacy boundary before any text can be sent.")
            else:
                selected_text = notes.strip()
                if pdf is not None:
                    path = _uploaded_path(store.project_root, campaign_id, pdf.name)
                    path.parent.mkdir(parents=True, exist_ok=True)
                    path.write_bytes(pdf.getvalue())
                    try:
                        page_indexes = [int(item.strip()) - 1 for item in pages_text.split(",") if item.strip()]
                        if not page_indexes:
                            raise ValueError("select at least one PDF page explicitly")
                        selected_text = (selected_text + "\n\n" + extract_pdf_text(path, page_indexes)).strip()
                    except Exception as exc:
                        st.error(f"Local PDF extraction stopped: {exc}")
                        return
                try:
                    suggestion, provenance = OpenAIResearchDraftAdapter(model=settings.openai_model).suggest(
                        selected_text,
                        source_title=source_title,
                        instrument=str(draft.get("instrument") or "ES"),
                    )
                except Exception as exc:
                    st.error(f"AI drafting is unavailable: {exc}. Continue with the manual form below.")
                else:
                    state["ai_suggestion"] = suggestion.model_dump(mode="json")
                    state["ai_provenance"] = provenance.model_dump(mode="json", by_alias=True)
                    store.save_state(campaign_id, state)
                    st.success("Suggestion validated against the strict schema. Review it before applying.")
                    st.rerun()
        suggestion = state.get("ai_suggestion")
        if isinstance(suggestion, dict):
            st.json(suggestion, expanded=False)
            st.caption("Provider/model/prompt/source/response hashes are retained in the local draft state.")
            if st.button("Apply suggestion to editable fields", key=f"ai_apply_{campaign_id}"):
                edge = suggestion.get("economic_edge_fingerprint") or {}
                draft.pop("duplicate_review", None)
                _clear_variant_design(draft)
                draft.update(
                    {
                        "hypothesis": suggestion.get("hypothesis") or draft.get("hypothesis"),
                        "expected_mechanism": suggestion.get("expected_mechanism") or draft.get("expected_mechanism"),
                        "holding_horizon": suggestion.get("expected_holding_horizon") or draft.get("holding_horizon"),
                        "known_failure_modes": suggestion.get("known_failure_modes") or draft.get("known_failure_modes"),
                        "economic_edge_fingerprint": {
                            "market_behavior": edge.get("market_behavior", ""),
                            "causal_mechanism": edge.get("causal_mechanism", ""),
                            "signal_inputs": [edge.get("signal_inputs", "")],
                            "market_context": edge.get("market_context", ""),
                            "holding_period": edge.get("holding_period", ""),
                        },
                    }
                )
                store.save(campaign_id, draft, wizard_step=1)
                state["ai_human_applied"] = True
                store.save_state(campaign_id, state)
                st.success("Applied as editable text. Saving the form below is still required confirmation.")
                st.rerun()


def _clear_variant_design(draft: dict[str, Any]) -> None:
    draft.pop("variants", None)
    draft.pop("confirmation_context_sha256", None)


def _invalidate_variant_confirmations(draft: dict[str, Any]) -> None:
    for variant in draft.get("variants") or []:
        if isinstance(variant, dict):
            variant["confirmed"] = False
    draft.pop("confirmation_context_sha256", None)


def _reset_mechanics_lane(store: Any, campaign_id: str, draft: dict[str, Any]) -> None:
    _clear_variant_design(draft)
    draft.pop("authoring_lane", None)
    draft.pop("certified_recipe", None)
    draft.pop("engineering_handoff_path", None)
    state = dict(store.load_state(campaign_id))
    for key in ("lane", "safe_bar_rule", "handoff_path"):
        state.pop(key, None)
    store.save_state(campaign_id, state)


def _publish_draft(root: Path, draft: Any) -> Any:
    from alphaquest.studio.publishing import StudioPublicationService

    return StudioPublicationService(root).publish(draft)


def _render_results_matrix(st: Any, root: Path, campaign_id: str) -> None:
    rows, latest = _results_matrix_state(root, campaign_id)
    st.markdown("**Sequential variant stage matrix**")
    st.dataframe(rows, use_container_width=True, hide_index=True)
    if latest:
        selected = st.selectbox("Inspect one variant's governed result", sorted(latest), key=f"result_variant_{campaign_id}")
        run_dir_value = latest[selected].get("run_dir")
        run_dir = Path(str(run_dir_value)) if run_dir_value else None
        if run_dir is not None and not run_dir.is_absolute():
            run_dir = root / run_dir
        bundle_path = run_dir / "reporting_v2/result_bundle_v2.json" if run_dir is not None else None
        if bundle_path is not None and not bundle_path.is_file() and run_dir is not None:
            legacy_bundle = run_dir / "result_bundle_v2.json"
            bundle_path = legacy_bundle if legacy_bundle.is_file() else bundle_path
        if bundle_path is not None and bundle_path.is_file():
            from alphaquest.studio.finalization import inspect_finalized_result
            from alphaquest.studio.results import load_result_bundle

            try:
                bundle = load_result_bundle(bundle_path)
            except Exception as exc:
                st.error(f"ResultBundleV2 failed strict validation: {exc}")
                return
            finalization = inspect_finalized_result(bundle_path)
            displayed_verdict = bundle.verdict if finalization["valid"] else "NEEDS MANUAL REVIEW"
            if not finalization["valid"]:
                st.warning(
                    "NEEDS MANUAL REVIEW — the reporting transaction is incomplete or its immutable hashes "
                    "do not verify. Responsible next action: inspect preserved evidence and create an explicit "
                    "governed follow-up; do not sign or replay this attempt."
                )
                st.write(finalization["errors"])
            if displayed_verdict == "PASS":
                st.success(bundle.verdict_message)
            elif displayed_verdict == "FAIL":
                st.error(bundle.verdict_message)
            elif finalization["valid"]:
                st.warning(bundle.verdict_message)
                unresolved = [
                    item.reason or f"{item.stage}: {item.metric} is unresolved"
                    for item in bundle.stage_criteria
                    if item.result == "NEEDS MANUAL REVIEW"
                ]
                if unresolved:
                    st.write("Missing or unresolved evidence: " + "; ".join(unresolved))
                st.info(
                    "Responsible next action: the named researcher/reviewer must inspect the cited evidence, "
                    "supply or correct the missing governed artifact, and create an explicit follow-up if the "
                    "frozen attempt must change. Do not replay or reuse this attempt."
                )
            if bundle.stage_criteria:
                st.markdown("**Stage criteria · actual versus required**")
                st.dataframe(
                    [
                        {
                            "stage": item.stage,
                            "metric": item.metric,
                            "operator": item.operator,
                            "threshold": item.threshold.value,
                            "actual": item.actual.value,
                            "result": item.result,
                            "reason": item.reason,
                            "evidence": item.evidence_path,
                        }
                        for item in bundle.stage_criteria
                    ],
                    use_container_width=True,
                    hide_index=True,
                )
            st.markdown("**Required metrics**")
            metrics = bundle.metrics.model_dump(mode="json")
            st.dataframe(
                [
                    {"metric": name.replace("_", " "), "value": item.get("value"), "undefined reason": item.get("reason")}
                    for name, item in metrics.items()
                ],
                use_container_width=True,
                hide_index=True,
            )
        else:
            st.caption("This historical run has no ResultBundleV2. It remains visible, but Studio will not invent missing metrics.")


def _results_matrix_state(
    root: Path,
    campaign_id: str,
) -> tuple[list[dict[str, Any]], dict[str, dict[str, Any]]]:
    """Join the currently declared sequential variants to evidence and jobs."""

    import yaml

    from alphaquest.research.storage import load_storage_layout

    layout = load_storage_layout(root)
    campaign_root = layout.active_campaign_root / campaign_id
    definition: dict[str, Any] = {}
    definition_path = campaign_root / "campaign.yaml"
    if definition_path.is_file():
        loaded = yaml.safe_load(definition_path.read_text(encoding="utf-8")) or {}
        definition = loaded if isinstance(loaded, dict) else {}
    declared = definition.get("variants")
    variants = [str(item) for item in declared] if isinstance(declared, list) else []
    if not 1 <= len(variants) <= 5 or len(set(variants)) != len(variants):
        discovered = sorted(
            path.parent.name for path in (campaign_root / "variants").glob("*/config.yaml")
        )
        variants = discovered if 1 <= len(discovered) <= 5 else []

    value: dict[str, Any] = {}
    results_path = campaign_root / "results_index.yaml"
    if results_path.is_file():
        loaded = yaml.safe_load(results_path.read_text(encoding="utf-8")) or {}
        value = loaded if isinstance(loaded, dict) else {}
    runs = value.get("runs") if isinstance(value.get("runs"), list) else []
    latest: dict[str, dict[str, Any]] = {}
    for item in runs:
        if not isinstance(item, dict):
            continue
        variant = str(item.get("variant_id") or "")
        if variant in variants and str(item.get("updated_at") or "") >= str(
            latest.get(variant, {}).get("updated_at") or ""
        ):
            latest[variant] = item

    latest_jobs: dict[str, Any] = {}
    database = layout.studio_runtime_root / "jobs.sqlite3"
    if database.is_file():
        from alphaquest.studio.jobs import SQLiteJobQueue

        for job in SQLiteJobQueue(database).list_jobs(limit=500):
            variant = str(job.payload.get("variant_id") or "")
            if job.campaign_id != campaign_id or variant not in variants:
                continue
            previous = latest_jobs.get(variant)
            if previous is None or job.updated_at >= previous.updated_at:
                latest_jobs[variant] = job

    rows: list[dict[str, Any]] = []
    for variant in variants:
        result = latest.get(variant)
        job = latest_jobs.get(variant)
        if result is not None:
            verdict = result.get("research_verdict") or (
                "PASS" if result.get("passed") else "FAIL"
            )
            unresolved = result.get("failed_stage") or "none"
            operational = job.state.value if job is not None else "SUCCEEDED"
            run_id = result.get("test_run_id")
            diagnostic = bool(result.get("diagnostic_only"))
        else:
            verdict = job.research_verdict if job is not None and job.research_verdict else "PENDING"
            operational = job.state.value if job is not None else "NOT_QUEUED"
            unresolved = (
                (job.blocked_reason or job.error)
                if job is not None and (job.blocked_reason or job.error)
                else "awaiting mechanics approval or staged submission"
            )
            run_id = None
            diagnostic = False
        rows.append(
            {
                "variant": variant,
                "research verdict": verdict,
                "operational state": operational,
                "first failed or unresolved gate": unresolved,
                "diagnostic only": diagnostic,
                "run": run_id,
            }
        )
    return rows, latest


def _suggest_variants_for_lane(
    draft: dict[str, Any],
    state: dict[str, Any],
    suggester: Any,
) -> list[dict[str, Any]]:
    cards = list(suggester(draft))[:1]
    if draft.get("authoring_lane") != "visual_completed_bar_rule" and state.get("lane") != "Visual completed-bar rule":
        return cards
    rule = state.get("safe_bar_rule")
    if not isinstance(rule, dict):
        return cards
    for index, card in enumerate(cards, start=1):
        card["entry"] = {
            "module": "safe_bar_rule",
            "params": {"rule": rule, "tunable_values": {}, "certified_features": []},
            "parameter_grid": {},
        }
        card["entry_rationale"] = (
            "The reviewed visual rule uses only current or lagged completed-bar features and bounded causal "
            "rolling transforms; a legal decision enters no earlier than the next bar open."
        )
        card["material_difference"] = (
            f"Variant v{index:02d} combines the frozen completed-bar rule with a distinct certified stop and "
            "target structure, changing risk invalidation or payoff mechanics rather than only a parameter value."
        )
    return cards


def _edit_module_binding(
    st: Any,
    catalog: Any,
    module_type: str,
    selected: str,
    previous: Any,
    defaults: Any,
    execution: dict[str, Any],
    state: dict[str, Any],
    draft: dict[str, Any],
    *,
    key: str,
) -> tuple[dict[str, Any], list[str]]:
    """Render a typed no-code editor from a certified module manifest."""

    from alphaquest.authoring.models import DatasetManifestV1

    base = _binding_for(
        selected,
        previous,
        defaults,
        execution,
        state,
        module_type=module_type,
    )
    manifest = catalog.get(module_type, selected)
    old_params = dict(base.get("params") or {})
    old_grid = dict(base.get("parameter_grid") or {})
    params: dict[str, Any] = {}
    grid: dict[str, list[Any]] = {}
    errors: list[str] = []
    context_values = _binding_context_values(selected, execution, draft)

    if selected == "safe_bar_rule":
        rule = state.get("safe_bar_rule") or old_params.get("rule")
        if not isinstance(rule, dict):
            errors.append("return to step 5 and build a visual completed-bar rule")
            rule = {}
        params["rule"] = rule
        params["certified_features"] = list((draft.get("dataset") or {}).get("certified_features") or [])
        selected_values: dict[str, Any] = {}
        for definition in rule.get("tunables") or []:
            name = str(definition.get("name") or "")
            values = list(definition.get("values") or [])
            if not name or len(values) < 2:
                errors.append("visual rule contains an invalid tunable definition")
                continue
            default = (old_params.get("tunable_values") or {}).get(name, definition.get("default"))
            selected_values[name] = st.selectbox(
                f"Default value · {name}",
                values,
                index=_index(values, default),
                key=f"{key}_safe_default_{name}",
                help="The complete value set is frozen as the pre-PnL grid.",
            )
            grid[f"tunable_values.{name}"] = values
        params["tunable_values"] = selected_values
        st.caption("The visual rule itself is frozen in step 5; edit that step to change its causal structure.")

    for name, spec in manifest.parameters.items():
        if selected == "safe_bar_rule" and name in {"rule", "certified_features", "tunable_values"}:
            continue
        value = old_params.get(name, context_values.get(name, spec.default))
        if value is None and spec.required:
            value = _required_parameter_fallback(selected, name, execution)
        if name in context_values:
            value = context_values[name]
            st.text_input(
                name.replace("_", " ").title(),
                value=str(value),
                disabled=True,
                key=f"{key}_{name}_locked",
                help="Bound to the confirmed dataset or execution settings.",
            )
        elif name == "weekday_directions":
            prior = value if isinstance(value, dict) else {}
            directions: dict[str, str] = {}
            for day, label in enumerate(("Monday", "Tuesday", "Wednesday", "Thursday", "Friday")):
                choice = st.selectbox(
                    label,
                    ("long", "short", "no trade"),
                    index=_index(("long", "short", "no trade"), prior.get(str(day), "no trade")),
                    key=f"{key}_{name}_{day}",
                )
                if choice != "no trade":
                    directions[str(day)] = choice
            value = directions
            if not value:
                errors.append("choose at least one weekday direction")
        elif spec.value_type == "boolean":
            value = st.checkbox(
                name.replace("_", " ").title(),
                value=bool(value),
                key=f"{key}_{name}",
                help=spec.description,
            )
        elif spec.value_type == "integer":
            current = int(value if value is not None else 0)
            minimum = int(spec.minimum) if spec.minimum is not None else None
            value = int(
                st.number_input(
                    name.replace("_", " ").title(),
                    value=max(current, minimum) if minimum is not None else current,
                    min_value=minimum,
                    step=1,
                    key=f"{key}_{name}",
                    help=spec.description,
                )
            )
        elif spec.value_type == "number":
            current = float(value if value is not None else 0.0)
            minimum = float(spec.minimum) if spec.minimum is not None else None
            value = float(
                st.number_input(
                    name.replace("_", " ").title(),
                    value=max(current, minimum) if minimum is not None else current,
                    min_value=minimum,
                    step=_numeric_step(current, minimum),
                    format="%.8f",
                    key=f"{key}_{name}",
                    help=spec.description,
                )
            )
        elif spec.value_type == "string" and spec.choices:
            value = st.selectbox(
                name.replace("_", " ").title(),
                list(spec.choices),
                index=_index(spec.choices, value),
                key=f"{key}_{name}",
                help=spec.description,
            )
        elif spec.value_type == "string":
            value = st.text_input(
                name.replace("_", " ").title(),
                value=str(value or ""),
                key=f"{key}_{name}",
                help=spec.description,
            )
        elif spec.value_type == "array":
            value = list(value or [])
            st.caption(f"{name.replace('_', ' ').title()}: {', '.join(map(str, value)) or 'none'}")
        elif spec.value_type == "object":
            if not isinstance(value, dict):
                errors.append(f"{name} must be a structured mapping supplied by the certified editor")
                value = {}
            st.caption(f"{name.replace('_', ' ').title()} is managed by its certified visual control.")
        params[name] = value

        if spec.tunable:
            enabled = st.checkbox(
                f"Test alternatives for {name.replace('_', ' ')}",
                value=name in old_grid,
                key=f"{key}_{name}_tune",
                help="This parameter space is frozen before any PnL is calculated.",
            )
            if enabled:
                existing = old_grid.get(name) or _suggest_grid_values(value, spec.value_type)
                raw = st.text_input(
                    f"Predeclared values · {name.replace('_', ' ')}",
                    value=", ".join(map(str, existing)),
                    key=f"{key}_{name}_grid",
                    help="Enter 2–20 values separated by commas. Total combinations must be 8–120.",
                )
                try:
                    parsed = _parse_grid_values(raw, spec.value_type)
                except ValueError as exc:
                    errors.append(f"{name}: {exc}")
                else:
                    grid[name] = parsed

    binding = {"module": selected, "params": params, "parameter_grid": grid}
    try:
        dataset = DatasetManifestV1.model_validate(draft.get("dataset") or {})
        validated = catalog.validate_binding(module_type, binding, dataset=dataset)
    except Exception as exc:
        errors.append(str(exc))
    else:
        binding = validated.model_dump(mode="json")
    return binding, list(dict.fromkeys(errors))


def _binding_context_values(
    module_name: str,
    execution: dict[str, Any],
    draft: dict[str, Any],
) -> dict[str, Any]:
    timeframe = str(draft.get("timeframe") or "1m")
    interval = float(timeframe[:-1]) if timeframe.endswith("m") else 1.0
    values: dict[str, Any] = {}
    if module_name in {
        "calendar_session_bias",
        "opening_range_breakout",
        "daily_time_series_momentum",
    }:
        values["bar_interval_minutes"] = interval
    if module_name == "opening_range_breakout":
        values.update(
            {
                "rth_start": execution.get("session_start", "09:30:00"),
                "last_entry_time": execution.get("latest_entry_time", "15:45:00"),
            }
        )
    if module_name == "daily_time_series_momentum":
        values["rth_end"] = execution.get("session_end", "16:00:00")
    if module_name == "fixed_dollar_per_contract":
        values["tick_value"] = float(execution.get("tick_value") or 12.5)
    if module_name == "cost_adjusted_fixed_r":
        values.update(
            {
                "tick_size": float(execution.get("tick_size") or 0.25),
                "tick_value": float(execution.get("tick_value") or 12.5),
                "commission_per_contract": float(execution.get("commission_per_contract") or 0.0),
                "slippage_ticks": float(execution.get("slippage_ticks") or 0.0),
            }
        )
    return values


def _required_parameter_fallback(selected: str, name: str, execution: dict[str, Any]) -> Any:
    if selected == "fixed_dollar_per_contract" and name == "dollars_per_contract":
        return 250.0
    if name == "tick_value":
        return float(execution.get("tick_value") or 12.5)
    return 0.0


def _numeric_step(value: float, minimum: float | None) -> float:
    scale = abs(value) or abs(minimum or 0.0)
    if scale < 0.01:
        return 0.0001
    if scale < 1:
        return 0.01
    return 1.0


def _suggest_grid_values(value: Any, value_type: str) -> list[Any]:
    if value_type == "boolean":
        return [False, True]
    if value_type == "integer":
        center = int(value)
        return list(dict.fromkeys(max(1, center + offset) for offset in (-3, -2, -1, 0, 1, 2, 3, 4)))
    if value_type == "number":
        center = float(value)
        if center == 0.0:
            return [-3.0, -2.0, -1.0, 0.0, 1.0, 2.0, 3.0, 4.0]
        base = center
        return [round(base * factor, 8) for factor in (0.65, 0.75, 0.85, 0.95, 1.0, 1.05, 1.15, 1.25)]
    return [str(value), f"{value}_alternative"]


def _parse_grid_values(raw: str, value_type: str) -> list[Any]:
    parts = [item.strip() for item in raw.split(",") if item.strip()]
    if not 2 <= len(parts) <= 20:
        raise ValueError("provide between 2 and 20 comma-separated values")
    try:
        if value_type == "boolean":
            lookup = {"true": True, "false": False}
            values = [lookup[item.casefold()] for item in parts]
        elif value_type == "integer":
            values = [int(item) for item in parts]
        elif value_type == "number":
            values = [float(item) for item in parts]
        else:
            values = parts
    except (KeyError, ValueError) as exc:
        raise ValueError(f"values do not match type {value_type}") from exc
    canonical = [json.dumps(item, sort_keys=True) for item in values]
    if len(set(canonical)) != len(canonical):
        raise ValueError("values must be unique")
    return values


def _binding_combinations(*bindings: dict[str, Any]) -> int:
    product = 1
    for binding in bindings:
        for values in (binding.get("parameter_grid") or {}).values():
            product *= len(values)
    return product


def _binding_for(
    selected: str,
    previous: Any,
    defaults: Any,
    execution: dict[str, Any],
    state: dict[str, Any],
    *,
    module_type: str = "entry",
) -> dict[str, Any]:
    previous = previous if isinstance(previous, dict) else {}
    if previous.get("module") == selected:
        return previous
    params = defaults(module_type, selected, execution)
    if selected == "safe_bar_rule":
        rule = state.get("safe_bar_rule")
        if rule:
            params["rule"] = rule
    return {"module": selected, "params": params, "parameter_grid": {}}


def _build_visual_rule(values: dict[str, Any], timeframe: str) -> dict[str, Any]:
    """Compile the visual controls to the bounded causal BarRuleV1 AST."""

    feature = {"source": "feature", "name": str(values["feature"]), "lag": int(values["lag"])}
    condition_type = str(values["condition_type"])
    tunables: list[dict[str, Any]] = []
    if condition_type == "Crossing a prior rolling value":
        direction = str(values["direction"])
        main: dict[str, Any] = {
            "type": "cross",
            "direction": direction,
            "left": feature,
            "right": {
                "source": "rolling",
                "feature": str(values["feature"]),
                "function": str(values["rolling_function"]),
                "window": int(values["window"]),
                # Lag one prevents the current completed bar from changing the
                # reference it is being compared with.
                "lag": 1,
                "min_periods": int(values["window"]),
            },
        }
    elif condition_type == "Comparison with a threshold":
        operator = {
            "greater than": "gt",
            "greater than or equal": "gte",
            "less than": "lt",
            "less than or equal": "lte",
        }[str(values["operator"])]
        right: dict[str, Any]
        if values.get("tune_threshold"):
            grid_values = _parse_grid_values(str(values.get("threshold_values") or ""), "number")
            if not 8 <= len(grid_values) <= 20:
                raise ValueError("a threshold grid must contain 8–20 values so the variant has a valid test space")
            default = float(values["threshold"])
            if default not in grid_values:
                raise ValueError("the displayed threshold must be included in its predeclared value set")
            right = {"source": "tunable", "name": "primary_threshold"}
            tunables.append(
                {
                    "name": "primary_threshold",
                    "value_type": "number",
                    "values": grid_values,
                    "default": default,
                }
            )
        else:
            right = {"source": "constant", "value": float(values["threshold"])}
        main = {"type": "comparison", "operator": operator, "left": feature, "right": right}
    else:
        lower = float(values["lower"])
        upper = float(values["upper"])
        if lower >= upper:
            raise ValueError("range lower bound must be below its upper bound")
        main = {
            "type": "range",
            "value": feature,
            "lower": {"source": "constant", "value": lower},
            "upper": {"source": "constant", "value": upper},
            "inclusive": bool(values["inclusive"]),
        }

    primary = _combine_visual_filter(main, values, mirror=False)
    mirrored = _combine_visual_filter(_mirror_condition(main), values, mirror=True)
    signals = str(values["signals"])
    long_rule = primary if signals in {"Long only", "Symmetric long and short"} else None
    short_rule = (
        mirrored
        if signals == "Symmetric long and short"
        else primary
        if signals == "Short only"
        else None
    )
    if timeframe.endswith("m") is False:
        raise ValueError("Studio V1 visual rules require a minute completed-bar timeframe")
    return {
        "schema": "alphaquest.bar-rule/v1",
        "long_rule": long_rule,
        "short_rule": short_rule,
        "tunables": tunables,
        "rth_only": bool(values["rth_only"]),
        "signal_start_time": str(values["signal_start_time"]),
        "signal_end_time": str(values["signal_end_time"]),
        "bar_interval_minutes": float(int(timeframe[:-1])),
        "max_trades_per_day": int(values["max_trades_per_day"]),
    }


def _combine_visual_filter(
    primary: dict[str, Any],
    values: dict[str, Any],
    *,
    mirror: bool,
) -> dict[str, Any]:
    if not values.get("second_filter"):
        return primary
    operator = "gt" if values.get("filter_operator") == "greater than" else "lt"
    if mirror:
        operator = "lt" if operator == "gt" else "gt"
    secondary = {
        "type": "comparison",
        "operator": operator,
        "left": {"source": "feature", "name": str(values["filter_feature"]), "lag": 0},
        "right": {"source": "constant", "value": float(values["filter_threshold"])},
    }
    group_type = "all" if values.get("boolean_group") == "All conditions" else "any"
    return {"type": group_type, "conditions": [primary, secondary]}


def _mirror_condition(condition: dict[str, Any]) -> dict[str, Any]:
    mirrored = json.loads(json.dumps(condition))
    if mirrored.get("type") == "cross":
        mirrored["direction"] = "below" if mirrored.get("direction") == "above" else "above"
    elif mirrored.get("type") == "comparison":
        mirrored["operator"] = {"gt": "lt", "gte": "lte", "lt": "gt", "lte": "gte"}.get(
            mirrored.get("operator"), mirrored.get("operator")
        )
    elif mirrored.get("type") == "range":
        mirrored = {"type": "not", "condition": mirrored}
    return mirrored


def _uploaded_path(root: Path, campaign_id: str, name: str) -> Path:
    from alphaquest.research.storage import load_storage_layout

    safe_name = Path(name).name
    return load_storage_layout(root).studio_runtime_root / "temporary-imports" / campaign_id / safe_name


def _project_root() -> Path:
    return Path(os.environ.get("ALPHAQUEST_PROJECT_ROOT") or Path.cwd()).resolve()


def _draft_label(campaign_id: str, drafts: list[dict[str, Any]]) -> str:
    row = next(item for item in drafts if item["campaign_id"] == campaign_id)
    return f"{row['title']} · step {row['wizard_step']}/7"


def _certified_module_count() -> int:
    try:
        from alphaquest.authoring.catalog import get_certified_module_catalog

        return len(get_certified_module_catalog().all())
    except Exception:
        return 0


def _identifier(value: str) -> str:
    normalized = re.sub(r"[^a-z0-9]+", "_", value.strip().lower()).strip("_")
    return normalized or "unspecified_edge"


def _lines(value: str) -> list[str]:
    return [line.strip() for line in value.splitlines() if line.strip()]


def _index(values: Any, current: Any) -> int:
    try:
        return list(values).index(current)
    except ValueError:
        return 0


def _guess_column(columns: list[str], canonical: str) -> int:
    aliases = {
        "timestamp": ("timestamp", "time", "datetime", "date"),
        "open": ("open", "o"),
        "high": ("high", "h"),
        "low": ("low", "l"),
        "close": ("close", "c"),
        "volume": ("volume", "vol", "v"),
    }[canonical]
    lowered = [item.lower() for item in columns]
    for alias in aliases:
        if alias in lowered:
            return lowered.index(alias)
    return 0


def _serializable(value: Any) -> Any:
    if hasattr(value, "model_dump"):
        return value.model_dump(mode="json", by_alias=True)
    if hasattr(value, "__dict__"):
        return {key: _serializable(item) for key, item in vars(value).items()}
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, dict):
        return {key: _serializable(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_serializable(item) for item in value]
    return value


__all__ = ["main"]
