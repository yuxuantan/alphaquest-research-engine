"""Presentation-neutral workflow orchestration for Research Studio.

The browser UI and CLI use this service instead of embedding governance logic
in a rendering framework.  Drafts may be incomplete while they are being
authored, but every transition re-checks the relevant strict contract and the
publication path still terminates in :class:`CampaignDraftV1` validation.
"""

from __future__ import annotations

import csv
from copy import deepcopy
from datetime import date
import json
from pathlib import Path
import re
from typing import Any, Mapping

import yaml

from alphaquest.authoring import campaign_confirmation_context_sha256
from alphaquest.authoring.bar_rules import validate_bar_rule
from alphaquest.authoring.catalog import get_certified_module_catalog
from alphaquest.strategy_certification import get_strategy_certification
from alphaquest.authoring.models import (
    CERTIFIED_RECIPE_BINDINGS,
    CampaignDraftV1,
    DatasetManifestV1,
    EconomicEdgeFingerprintV1,
    ExecutionSettingsV1,
    ResearchSourceV1,
    VariantDraftV1,
)
from alphaquest.research.storage import campaign_definition_paths, display_path, load_storage_layout
from alphaquest.studio.drafts import DraftStore
from alphaquest.studio.duplicates import duplicate_matches
from alphaquest.studio.handoffs import new_handoff, write_engineering_handoff
from alphaquest.studio.ledger import append_duplicate_closure
from alphaquest.studio.publishing import StudioPublicationService
from alphaquest.prop.profiles import resolve_prop_profile
from alphaquest.studio.variants import suggest_variant_card
from alphaquest.studio.workspace import list_dataset_manifests


_IDENTIFIER = re.compile(r"^[a-z0-9][a-z0-9_]*$")


class StudioWorkflowService:
    """Governed mutations used by every novice presentation surface."""

    def __init__(self, project_root: str | Path = ".") -> None:
        self.project_root = Path(project_root).resolve()
        self.store = DraftStore(self.project_root)

    def create_draft(self, *, campaign_id: str, title: str, instrument: str) -> dict[str, Any]:
        identifier = campaign_id.strip().lower()
        if _IDENTIFIER.fullmatch(identifier) is None:
            raise ValueError("campaign ID must use lowercase letters, numbers, and underscores")
        if not title.strip():
            raise ValueError("campaign title is required")
        if instrument not in {"ES", "NQ"}:
            raise ValueError("instrument must be ES or NQ")
        if self.store.path_for(identifier).exists():
            raise FileExistsError(f"Studio draft already exists: {identifier}")
        _require_unreserved_campaign_id(self.project_root, identifier)
        self.store.save(
            identifier,
            {
                "schema": "alphaquest.campaign-draft/v1",
                "campaign_id": identifier,
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
        return self.draft_view(identifier)

    def draft_view(self, campaign_id: str) -> dict[str, Any]:
        document = self.store.load(campaign_id)
        draft = dict(document.get("draft") or {})
        state = self.store.load_state(campaign_id)
        gates = _step_gates(draft, state)
        return {
            "campaign_id": campaign_id,
            "wizard_step": int(document.get("wizard_step") or 1),
            "updated_at": document.get("updated_at"),
            "frozen_draft_sha256": document.get("frozen_draft_sha256"),
            "closed_before_pnl": document.get("closed_before_pnl"),
            "draft": draft,
            "state": state,
            "steps": [
                {
                    "number": number,
                    "label": label,
                    "complete": gates[number - 1],
                    "available": number == 1 or all(gates[: number - 1]),
                }
                for number, label in enumerate(
                    (
                        "Research brief",
                        "Duplicate review",
                        "Dataset",
                        "Execution rules",
                        "Mechanics lane",
                        "First variant",
                        "Protocol and freeze",
                    ),
                    start=1,
                )
            ],
            "validation": self.store.validation_report(campaign_id) if draft.get("frozen") else None,
        }

    def save_brief(self, campaign_id: str, value: Mapping[str, Any]) -> dict[str, Any]:
        document, draft = self._mutable(campaign_id)
        timeframe = str(value.get("timeframe") or "")
        if timeframe not in {"1m", "5m", "15m"}:
            raise ValueError("Studio supports completed 1m, 5m, and 15m bars")
        source = ResearchSourceV1.model_validate(value.get("source") or {})
        fingerprint = EconomicEdgeFingerprintV1.model_validate(value.get("economic_edge_fingerprint") or {})
        failures = _nonblank_strings(value.get("known_failure_modes"), "known failure modes")
        updated = {
            "title": _required_text(value.get("title"), "campaign title"),
            "edge_family": _identifier(value.get("edge_family"), "economic edge family"),
            "timeframe": timeframe,
            "hypothesis": _required_text(value.get("hypothesis"), "falsifiable hypothesis"),
            "expected_mechanism": _required_text(value.get("expected_mechanism"), "expected mechanism"),
            "holding_horizon": _required_text(value.get("holding_horizon"), "holding horizon"),
            "known_failure_modes": failures,
            "sources": [source.model_dump(mode="json")],
            "economic_edge_fingerprint": fingerprint.model_dump(mode="json"),
        }
        changed = any(draft.get(key) != item for key, item in updated.items())
        timeframe_changed = draft.get("timeframe") != timeframe
        if changed:
            draft.pop("duplicate_review", None)
            _clear_variant_design(draft)
        if timeframe_changed:
            draft.pop("dataset", None)
            self._reset_mechanics(campaign_id, draft)
        draft.update(updated)
        self.store.save(campaign_id, draft, wizard_step=2)
        return self.draft_view(campaign_id)

    def duplicate_review_context(self, campaign_id: str) -> dict[str, Any]:
        _, draft = self._load(campaign_id)
        _require_gate(_step_gates(draft, self.store.load_state(campaign_id)), 1)
        matches = duplicate_matches(
            project_root=self.project_root,
            campaign_id=campaign_id,
            title=str(draft.get("title") or ""),
            hypothesis=str(draft.get("hypothesis") or ""),
            expected_mechanism=str(draft.get("expected_mechanism") or ""),
            fingerprint=draft.get("economic_edge_fingerprint"),
            limit=None,
        )
        return {"matches": matches, "review": draft.get("duplicate_review")}

    def save_duplicate_review(self, campaign_id: str, value: Mapping[str, Any]) -> dict[str, Any]:
        _, draft = self._mutable(campaign_id)
        matches = self.duplicate_review_context(campaign_id)["matches"]
        known = {str(item.get("campaign_id")) for item in matches}
        reviewed = [str(item) for item in value.get("reviewed_campaign_ids") or []]
        unknown = set(reviewed) - known
        if unknown:
            raise ValueError("duplicate review references unknown matches: " + ", ".join(sorted(unknown)))
        conclusion = str(value.get("conclusion") or "needs_review")
        if conclusion not in {"distinct", "duplicate", "needs_review"}:
            raise ValueError("duplicate conclusion is invalid")
        rationale = _required_text(value.get("substantive_distinction"), "duplicate-review rationale")
        if conclusion in {"distinct", "duplicate"} and len(rationale) < 80:
            raise ValueError("a distinct or duplicate decision requires at least 80 characters of economic rationale")
        review = {
            "reviewed_campaign_ids": reviewed,
            "ledger_queries": [str(draft.get("title") or campaign_id), str(draft.get("edge_family") or campaign_id)],
            "conclusion": conclusion,
            "substantive_distinction": rationale,
        }
        if draft.get("duplicate_review") != review:
            _invalidate_variant_confirmations(draft)
        draft["duplicate_review"] = review
        self.store.save(campaign_id, draft, wizard_step=3 if conclusion == "distinct" else 2)
        return self.draft_view(campaign_id)

    def close_duplicate(self, campaign_id: str) -> dict[str, Any]:
        document, draft = self._load(campaign_id)
        existing = document.get("closed_before_pnl")
        if isinstance(existing, dict) and existing.get("status") == "CLOSED":
            return {
                "verdict": "FAIL",
                "closed_before_pnl": True,
                "ledger_path": str(existing.get("ledger_path") or ""),
                "closure": existing,
            }
        if draft.get("frozen"):
            raise ValueError("the research protocol is frozen; duplicate closure is no longer available")
        review = draft.get("duplicate_review") or {}
        if review.get("conclusion") != "duplicate":
            raise ValueError("only a reviewed duplicate may be closed before PnL")
        reason = str(review.get("substantive_distinction") or "")
        path = append_duplicate_closure(draft, project_root=self.project_root, failure_reason=reason)
        closure = self.store.close_before_pnl(
            campaign_id,
            ledger_path=path,
            reason=reason,
        )
        return {
            "verdict": "FAIL",
            "closed_before_pnl": True,
            "ledger_path": str(path),
            "closure": closure,
        }

    def select_dataset(self, campaign_id: str, dataset_id: str) -> dict[str, Any]:
        _, draft = self._mutable(campaign_id)
        manifests = {str(item.get("dataset_id")): item for item in list_dataset_manifests(self.project_root)}
        try:
            raw = manifests[dataset_id]
        except KeyError as exc:
            raise FileNotFoundError(f"governed dataset not found: {dataset_id}") from exc
        payload = {key: item for key, item in raw.items() if key != "manifest_path"}
        manifest = DatasetManifestV1.model_validate(payload)
        if manifest.quality_verdict != "PASS":
            raise ValueError(f"dataset {dataset_id} is not eligible: {manifest.quality_verdict}")
        if manifest.symbol != draft.get("instrument") or manifest.timeframe != draft.get("timeframe"):
            raise ValueError("dataset symbol and timeframe must match the research brief")
        if draft.get("dataset") != payload:
            self._reset_mechanics(campaign_id, draft)
        draft["dataset"] = payload
        self.store.save(campaign_id, draft, wizard_step=4)
        return self.draft_view(campaign_id)

    def save_execution(
        self,
        campaign_id: str,
        value: Mapping[str, Any],
        *,
        roll_policy_confirmed: bool,
    ) -> dict[str, Any]:
        _, draft = self._mutable(campaign_id)
        if not roll_policy_confirmed:
            raise ValueError("confirm the governed dataset roll policy before continuing")
        parsed_execution = ExecutionSettingsV1.model_validate(value)
        resolve_prop_profile(
            parsed_execution.prop_profile,
            starting_balance=parsed_execution.initial_balance,
            max_contracts=parsed_execution.contracts,
            force_flatten_time=parsed_execution.flatten_time,
        )
        execution = parsed_execution.model_dump(mode="json")
        if draft.get("execution") != execution:
            self._reset_mechanics(campaign_id, draft)
        draft["execution"] = execution
        self.store.save(campaign_id, draft, wizard_step=5)
        return self.draft_view(campaign_id)

    def save_recipe(self, campaign_id: str, recipe: str, *, confirmed: bool) -> dict[str, Any]:
        _, draft = self._mutable(campaign_id)
        if not confirmed:
            raise ValueError("explicitly confirm that the recipe represents the frozen hypothesis")
        if recipe not in CERTIFIED_RECIPE_BINDINGS:
            raise ValueError("unknown or uncertified recipe")
        _clear_variant_design(draft)
        draft["authoring_lane"] = "certified_recipe"
        draft["certified_recipe"] = recipe
        draft["engineering_handoff_path"] = None
        self.store.save_state(campaign_id, {"lane": "Certified recipe"})
        self.store.save(campaign_id, draft, wizard_step=6)
        return self.draft_view(campaign_id)

    def save_visual_rule(self, campaign_id: str, rule: Mapping[str, Any]) -> dict[str, Any]:
        _, draft = self._mutable(campaign_id)
        certified = set((draft.get("dataset") or {}).get("certified_features") or [])
        parsed = validate_bar_rule(dict(rule), certified_features=certified)
        _clear_variant_design(draft)
        draft["authoring_lane"] = "visual_completed_bar_rule"
        draft["certified_recipe"] = None
        draft["engineering_handoff_path"] = None
        self.store.save_state(
            campaign_id,
            {"lane": "Visual completed-bar rule", "safe_bar_rule": parsed.model_dump(mode="json", by_alias=True)},
        )
        self.store.save(campaign_id, draft, wizard_step=6)
        return self.draft_view(campaign_id)

    def save_event_strategy(self, campaign_id: str, strategy_id: str, *, confirmed: bool) -> dict[str, Any]:
        _, draft = self._mutable(campaign_id)
        if not confirmed:
            raise ValueError("explicitly confirm that the certified event strategy represents the frozen hypothesis")
        certification = get_strategy_certification(strategy_id, self.project_root, require_current=True)
        if certification.studio.get("visible") is not True:
            raise ValueError("the certified event strategy is not exposed for Studio authoring")
        if not isinstance((draft.get("dataset") or {}).get("event_source"), dict):
            raise ValueError("certified event replay requires a governed dataset with event_source metadata")
        _clear_variant_design(draft)
        draft["authoring_lane"] = "certified_event_replay"
        draft["event_strategy"] = certification.strategy_id
        draft["certified_recipe"] = None
        draft["engineering_handoff_path"] = None
        self.store.save_state(
            campaign_id,
            {
                "lane": "Certified event replay",
                "strategy_id": certification.strategy_id,
                "implementation_version": certification.implementation_version,
                "implementation_sha256": certification.implementation_sha256,
            },
        )
        self.store.save(campaign_id, draft, wizard_step=6)
        return self.draft_view(campaign_id)

    def save_engineering_handoff(self, campaign_id: str, value: Mapping[str, Any]) -> dict[str, Any]:
        _, draft = self._mutable(campaign_id)
        handoff = new_handoff(
            campaign_id=campaign_id,
            reason_unsupported=_required_text(value.get("reason_unsupported"), "unsupported-mechanics reason"),
            causal_timeline=_nonblank_strings(value.get("causal_timeline"), "causal timeline"),
            required_data_granularity=_required_text(
                value.get("required_data_granularity"), "required data granularity"
            ),
            fill_and_ambiguity_rules=_nonblank_strings(
                value.get("fill_and_ambiguity_rules"), "fill and ambiguity rules"
            ),
            required_module_contract=_nonblank_strings(
                value.get("required_module_contract"), "required module contract"
            ),
            required_tests=_nonblank_strings(value.get("required_tests"), "required tests"),
            proposed_mechanics=_nonblank_strings(value.get("proposed_mechanics"), "initial proposed mechanic"),
        )
        path = write_engineering_handoff(handoff, project_root=self.project_root)
        _clear_variant_design(draft)
        draft["authoring_lane"] = "engineering_handoff"
        draft["certified_recipe"] = None
        draft["engineering_handoff_path"] = str(path.relative_to(self.project_root))
        self.store.save_state(campaign_id, {"lane": "Engineering handoff", "handoff_path": str(path)})
        self.store.save(campaign_id, draft, wizard_step=5)
        return {**self.draft_view(campaign_id), "research_verdict": "NEEDS MANUAL REVIEW"}

    def suggested_variants(self, campaign_id: str) -> list[dict[str, Any]]:
        _, draft = self._load(campaign_id)
        state = self.store.load_state(campaign_id)
        if draft.get("authoring_lane") == "engineering_handoff":
            raise ValueError("engineering-handoff mechanics cannot be submitted or approximated")
        if draft.get("authoring_lane") == "certified_event_replay":
            certification = get_strategy_certification(
                str(draft.get("event_strategy") or ""), self.project_root, require_current=True
            )
            cards = [
                {
                    "schema": "alphaquest.variant-draft/v1",
                    "variant_id": "v01",
                    "title": f"{draft.get('title') or certification.strategy_id} — certified event implementation",
                    "entry": {
                        "module": certification.entry_module,
                        "params": {
                            "mechanics": {
                                name: parameter.default
                                for name, parameter in certification.parameters.items()
                            }
                        },
                        "parameter_grid": {},
                    },
                    "stop": {"module": certification.stop_module, "params": {}, "parameter_grid": {}},
                    "target": {"module": certification.target_module, "params": {}, "parameter_grid": {}},
                    "event_parameter_grid": {},
                    "mechanic_rationale": (
                        "This first variant uses the versioned certified event implementation and its frozen "
                        "default mechanics, without selecting values from performance results or approximating events."
                    ),
                    "entry_rationale": (
                        "The certified event state machine consumes causally ordered trade events and only submits "
                        "orders after its declared AOI, tap, and trigger transitions are observable."
                    ),
                    "stop_rationale": (
                        "The certified structural stop is derived from the active AOI and applies the declared "
                        "minimum breathing room and maximum risk before an entry can be submitted."
                    ),
                    "target_rationale": (
                        "The certified value-area management activates protected profit at the midpoint and uses "
                        "the opposite value edge without consulting future events."
                    ),
                    "timeframe_session_rationale": (
                        "The governed event source, exchange timezone, session boundaries, entry cutoff, and forced "
                        "flatten are fixed before mechanics validation and performance testing."
                    ),
                    "material_difference": (
                        "This is the campaign's first and only currently unlocked event mechanic; later variants "
                        "remain blocked until this implementation is manually reviewed and fails testing."
                    ),
                    "known_failure_modes": list(draft.get("known_failure_modes") or []),
                    "confirmed": False,
                }
            ]
            return cards
        cards = [suggest_variant_card(draft, index=0)]
        if draft.get("authoring_lane") != "visual_completed_bar_rule":
            return cards
        rule = state.get("safe_bar_rule")
        if not isinstance(rule, dict):
            raise ValueError("the visual completed-bar rule has not been validated")
        certified = list((draft.get("dataset") or {}).get("certified_features") or [])
        for index, card in enumerate(cards, start=1):
            card["entry"] = {
                "module": "safe_bar_rule",
                "params": {"rule": rule, "tunable_values": {}, "certified_features": certified},
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

    def save_variants(self, campaign_id: str, values: list[Mapping[str, Any]]) -> dict[str, Any]:
        _, draft = self._mutable(campaign_id)
        if len(values) != 1:
            raise ValueError("campaign creation requires exactly one initial variant card")
        dataset = DatasetManifestV1.model_validate(draft.get("dataset") or {})
        catalog = get_certified_module_catalog()
        parsed: list[VariantDraftV1] = []
        for index, raw in enumerate(values, start=1):
            candidate = dict(raw)
            candidate["variant_id"] = f"v{index:02d}"
            for key, kind in (("entry", "entry"), ("stop", "sl"), ("target", "tp")):
                candidate[key] = catalog.validate_binding(kind, candidate.get(key) or {}, dataset=dataset).model_dump(
                    mode="json"
                )
            parsed.append(VariantDraftV1.model_validate(candidate))
        signatures = {item.mechanic_signature for item in parsed}
        if len(signatures) != len(parsed):
            raise ValueError("variants must have materially distinct, value-independent mechanics")
        entry_modules = {item.entry.module for item in parsed}
        if draft.get("authoring_lane") == "certified_recipe":
            recipe = str(draft.get("certified_recipe") or "")
            expected = CERTIFIED_RECIPE_BINDINGS.get(recipe, (None, None))[0]
            if entry_modules != {expected}:
                raise ValueError("all variants must preserve the selected certified entry edge")
        elif draft.get("authoring_lane") == "visual_completed_bar_rule" and entry_modules != {"safe_bar_rule"}:
            raise ValueError("all visual-rule variants must preserve the reviewed safe_bar_rule edge")
        elif draft.get("authoring_lane") == "certified_event_replay":
            certification = get_strategy_certification(
                str(draft.get("event_strategy") or ""), self.project_root, require_current=True
            )
            if entry_modules != {certification.entry_module}:
                raise ValueError("all event variants must preserve the selected certified strategy implementation")
        payload = [item.model_dump(mode="json", by_alias=True) for item in parsed]
        draft["variants"] = payload
        if all(item.confirmed for item in parsed):
            draft["confirmation_context_sha256"] = campaign_confirmation_context_sha256(draft)
            next_step = 7
        else:
            draft.pop("confirmation_context_sha256", None)
            next_step = 6
        self.store.save(campaign_id, draft, wizard_step=next_step)
        return self.draft_view(campaign_id)

    def freeze(self, campaign_id: str, *, confirmed: bool) -> dict[str, Any]:
        _, draft = self._mutable(campaign_id)
        if not confirmed:
            raise ValueError("explicitly confirm the immutable protocol before freezing")
        candidate = {**draft, "frozen": True}
        parsed = CampaignDraftV1.model_validate(candidate)
        preflight = StudioPublicationService(self.project_root).preflight_draft(parsed)
        self.store.save(campaign_id, candidate, wizard_step=7)
        return {**self.draft_view(campaign_id), "preflight": preflight}

    def publish(self, campaign_id: str) -> dict[str, Any]:
        draft = self.store.validate(campaign_id)
        result = StudioPublicationService(self.project_root).publish(draft)
        return _jsonable(result)

    def create_revision(self, campaign_id: str, *, revision_id: str, reason: str) -> dict[str, Any]:
        _require_unreserved_campaign_id(self.project_root, revision_id)
        self.store.create_revision(campaign_id, revision_id, reason=reason)
        return self.draft_view(revision_id)

    def _load(self, campaign_id: str) -> tuple[dict[str, Any], dict[str, Any]]:
        document = self.store.load(campaign_id)
        return document, dict(document.get("draft") or {})

    def _mutable(self, campaign_id: str) -> tuple[dict[str, Any], dict[str, Any]]:
        document, draft = self._load(campaign_id)
        if self.store.is_closed_before_pnl(campaign_id, document=document):
            raise ValueError(
                "the research draft was closed before PnL as a duplicate FAIL and cannot be reopened"
            )
        if draft.get("frozen"):
            raise ValueError("the research protocol is frozen; create a governed revision or follow-up")
        return document, draft

    def _reset_mechanics(self, campaign_id: str, draft: dict[str, Any]) -> None:
        _clear_variant_design(draft)
        draft.pop("authoring_lane", None)
        draft.pop("certified_recipe", None)
        draft.pop("engineering_handoff_path", None)
        state = dict(self.store.load_state(campaign_id))
        for key in ("lane", "safe_bar_rule", "handoff_path"):
            state.pop(key, None)
        self.store.save_state(campaign_id, state)


def _step_gates(draft: Mapping[str, Any], state: Mapping[str, Any]) -> list[bool]:
    fingerprint = draft.get("economic_edge_fingerprint")
    brief = bool(
        draft.get("sources")
        and draft.get("hypothesis")
        and draft.get("expected_mechanism")
        and draft.get("holding_horizon")
        and draft.get("known_failure_modes")
        and isinstance(fingerprint, Mapping)
        and all(fingerprint.values())
    )
    duplicate = (draft.get("duplicate_review") or {}).get("conclusion") == "distinct"
    dataset = (draft.get("dataset") or {}).get("quality_verdict") == "PASS"
    execution = bool(draft.get("execution"))
    lane_name = draft.get("authoring_lane")
    lane = bool(
        (lane_name == "certified_recipe" and draft.get("certified_recipe"))
        or (lane_name == "visual_completed_bar_rule" and isinstance(state.get("safe_bar_rule"), Mapping))
        or (lane_name == "engineering_handoff" and draft.get("engineering_handoff_path"))
    )
    variants = draft.get("variants") or []
    variant_gate = len(variants) == 1 and all(item.get("confirmed") for item in variants if isinstance(item, Mapping))
    frozen = bool(draft.get("frozen"))
    return [brief, duplicate, dataset, execution, lane, variant_gate, frozen]


def _require_gate(gates: list[bool], number: int) -> None:
    if not gates[number - 1]:
        raise ValueError(f"complete Studio step {number} before continuing")


def _clear_variant_design(draft: dict[str, Any]) -> None:
    draft.pop("variants", None)
    draft.pop("confirmation_context_sha256", None)


def _invalidate_variant_confirmations(draft: dict[str, Any]) -> None:
    for variant in draft.get("variants") or []:
        if isinstance(variant, dict):
            variant["confirmed"] = False
    draft.pop("confirmation_context_sha256", None)


def _required_text(value: Any, label: str) -> str:
    text = str(value or "").strip()
    if not text:
        raise ValueError(f"{label} is required")
    return text


def _nonblank_strings(value: Any, label: str) -> list[str]:
    if not isinstance(value, list):
        raise ValueError(f"{label} must be a list")
    items = [str(item).strip() for item in value if str(item).strip()]
    if not items:
        raise ValueError(f"{label} requires at least one item")
    return items


def _identifier(value: Any, label: str) -> str:
    text = re.sub(r"[^a-z0-9]+", "_", str(value or "").strip().lower()).strip("_")
    if _IDENTIFIER.fullmatch(text) is None:
        raise ValueError(f"{label} must use lowercase letters, numbers, and underscores")
    return text


def _jsonable(value: Any) -> Any:
    if hasattr(value, "model_dump"):
        return value.model_dump(mode="json", by_alias=True)
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, Mapping):
        return {str(key): _jsonable(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_jsonable(item) for item in value]
    if hasattr(value, "__dict__"):
        return _jsonable(vars(value))
    json.dumps(value, allow_nan=False)
    return value


def _require_unreserved_campaign_id(project_root: Path, campaign_id: str) -> None:
    """Reserve campaign identity across authored roots and append-only history."""

    layout = load_storage_layout(project_root)
    for source_root in layout.campaign_roots:
        candidate = source_root / campaign_id
        if candidate.exists() or candidate.is_symlink():
            raise FileExistsError(
                f"campaign ID is already reserved by authored research: {display_path(candidate, project_root)}"
            )

    for definition in campaign_definition_paths(
        project_root=project_root,
        layout=layout,
        include_ledger=True,
    ):
        recorded_id = definition.parent.name
        try:
            value = yaml.safe_load(definition.read_text(encoding="utf-8")) or {}
        except (OSError, yaml.YAMLError):
            value = {}
        if isinstance(value, Mapping) and value.get("campaign_id"):
            recorded_id = str(value["campaign_id"])
        if recorded_id == campaign_id:
            raise FileExistsError(
                f"campaign ID is already reserved by authored research: {display_path(definition, project_root)}"
            )

    ledger = project_root / "research_ledger.csv"
    if not ledger.is_file():
        return
    try:
        with ledger.open(newline="", encoding="utf-8") as handle:
            reader = csv.DictReader(handle)
            if "campaign_id" not in (reader.fieldnames or []):
                raise ValueError("research_ledger.csv has no campaign_id column")
            if any(str(row.get("campaign_id") or "").strip() == campaign_id for row in reader):
                raise FileExistsError(
                    f"campaign ID is already reserved by research ledger history: {campaign_id}"
                )
    except UnicodeError as exc:
        raise ValueError("research_ledger.csv could not be decoded while reserving campaign identity") from exc


__all__ = ["StudioWorkflowService"]
