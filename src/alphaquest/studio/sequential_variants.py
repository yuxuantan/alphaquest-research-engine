"""Failure-informed, one-at-a-time variant expansion for Studio campaigns."""

from __future__ import annotations

from datetime import UTC, datetime
from copy import deepcopy
import hashlib
import json
import os
from pathlib import Path
import shutil
import tempfile
from typing import Any, Mapping

from pydantic import ValidationError
import yaml

from alphaquest.authoring import CampaignCompiler, CampaignDraftV1, TransactionalCampaignPublisher
from alphaquest.authoring.compiler import CompiledCampaign, _object_sha256
from alphaquest.authoring.models import VariantDraftV1, campaign_confirmation_context_sha256
from alphaquest.research.storage import display_path, load_storage_layout
from alphaquest.studio.drafts import DraftStore, _verify_frozen_document
from alphaquest.studio.ledger import append_planned_publication
from alphaquest.studio.variants import suggest_variant_card
from alphaquest.studio.workspace import refresh_generated_indexes_if_stale
from alphaquest.validation.promotion_gate import inspect_historical_validation_approval


MAX_VARIANTS = 5


class SequentialVariantService:
    """Append one new mechanic only after the immediately prior mechanic failed."""

    def __init__(self, project_root: str | Path = ".") -> None:
        self.project_root = Path(project_root).resolve()
        self.layout = load_storage_layout(self.project_root)
        self.drafts = DraftStore(self.project_root)

    def eligibility(self, campaign_id: str) -> dict[str, Any]:
        draft = self._draft(campaign_id)
        current = draft.variants[-1]
        result_path, result = self._latest_result(campaign_id, current.variant_id)
        config_path = (
            result_path.parent.parent / "source_config.yaml"
            if result_path is not None
            else self._campaign_root(campaign_id) / "variants" / current.variant_id / "config.yaml"
        )
        config = yaml.safe_load(config_path.read_text(encoding="utf-8")) or {}
        approval = inspect_historical_validation_approval(config, config_path)
        verdict = str(result.get("verdict") or result.get("research_verdict") or "")
        blockers: list[str] = []
        if len(draft.variants) >= MAX_VARIANTS:
            blockers.append("the campaign has reached the five-variant maximum")
        if approval.get("status") != "APPROVED_FOR_TESTING":
            blockers.append("the current variant has not passed manual mechanics review")
        if result_path is None:
            blockers.append("the current variant has no complete ResultBundleV2")
        elif verdict != "FAIL":
            blockers.append(
                f"the current variant verdict is {verdict or 'unresolved'}; only FAIL permits another variant"
            )
        return {
            "eligible": not blockers,
            "campaign_id": campaign_id,
            "current_variant_id": current.variant_id,
            "next_variant_id": f"v{len(draft.variants) + 1:02d}" if len(draft.variants) < MAX_VARIANTS else None,
            "variant_count": len(draft.variants),
            "max_variants": MAX_VARIANTS,
            "mechanics_approval_status": approval.get("status"),
            "predecessor_verdict": verdict or None,
            "predecessor_result_path": display_path(result_path, self.project_root) if result_path else None,
            "blockers": blockers,
        }

    def suggestion(self, campaign_id: str) -> dict[str, Any]:
        state = self.eligibility(campaign_id)
        if not state["eligible"]:
            raise ValueError("next variant is blocked: " + "; ".join(state["blockers"]))
        draft = self._draft(campaign_id)
        index = len(draft.variants)
        _, result = self._latest_result(campaign_id, draft.variants[-1].variant_id)
        failure_context = _failure_context(result)
        card = suggest_variant_card(
            draft.model_dump(mode="json", by_alias=True),
            index=index,
            failure_context=failure_context,
        )
        card["variant_id"] = state["next_variant_id"]
        card["confirmed"] = False
        return {**state, "failure_context": failure_context, "variant": card}

    def append(
        self,
        campaign_id: str,
        *,
        variant: Mapping[str, Any],
        failure_analysis: str,
        created_by: str,
    ) -> dict[str, Any]:
        state = self.eligibility(campaign_id)
        if not state["eligible"]:
            raise ValueError("next variant is blocked: " + "; ".join(state["blockers"]))
        analysis = failure_analysis.strip()
        author = created_by.strip()
        if len(analysis) < 80:
            raise ValueError("failure analysis must contain at least 80 characters")
        if not author:
            raise ValueError("researcher identity is required")

        draft = self._draft(campaign_id)
        candidate = dict(variant)
        candidate["variant_id"] = str(state["next_variant_id"])
        candidate["confirmed"] = True
        parsed_variant = VariantDraftV1.model_validate(candidate)
        if parsed_variant.mechanic_signature in {item.mechanic_signature for item in draft.variants}:
            raise ValueError("the new variant duplicates an existing mechanic signature")

        result_path, result = self._latest_result(campaign_id, draft.variants[-1].variant_id)
        assert result_path is not None and str(result.get("verdict") or result.get("research_verdict")) == "FAIL"
        payload = draft.model_dump(mode="json", by_alias=True)
        predecessor_config = self._predecessor_source_config(result_path)
        predecessor_dataset = self._predecessor_dataset_manifest(predecessor_config)
        if predecessor_dataset is not None:
            payload["dataset"] = predecessor_dataset
        payload["timeframe"] = str(predecessor_config.get("timeframe") or payload.get("timeframe"))
        payload["execution"] = self._predecessor_execution_settings(predecessor_config)
        payload["variants"].append(parsed_variant.model_dump(mode="json", by_alias=True))
        payload.setdefault("sequential_variant_history", []).append(
            {
                "schema": "alphaquest.sequential-variant-lineage/v1",
                "variant_id": parsed_variant.variant_id,
                "predecessor_variant_id": draft.variants[-1].variant_id,
                "predecessor_verdict": "FAIL",
                "predecessor_result_path": display_path(result_path, self.project_root),
                "predecessor_result_sha256": _sha256(result_path),
                "failure_analysis": analysis,
                "created_by": author,
                "created_at": datetime.now(UTC).isoformat(),
            }
        )
        payload["confirmation_context_sha256"] = campaign_confirmation_context_sha256(payload)
        payload["frozen"] = True
        updated = CampaignDraftV1.model_validate(payload)
        compilation_payload = updated.model_dump(mode="json", by_alias=True)
        compilation_payload["variants"] = [updated.variants[-1].model_dump(mode="json", by_alias=True)]
        compilation_payload["variant_protocol"] = "legacy_predeclared"
        compilation_payload["sequential_variant_history"] = []
        compilation_payload["event_strategy"] = updated.variants[-1].entry.module
        compilation_payload["confirmation_context_sha256"] = campaign_confirmation_context_sha256(compilation_payload)
        compilation_draft = CampaignDraftV1.model_validate(compilation_payload)
        compiled = CampaignCompiler(
            project_root=self.project_root,
            evidence_root=display_path(self.layout.evidence_roots[0], self.project_root),
            research_artifact_root=display_path(self.layout.research_artifact_root, self.project_root),
        ).compile(compilation_draft)
        compiled = self._preserve_prior_variants(
            draft,
            updated,
            compiled,
            predecessor_config=predecessor_config,
        )
        return self._install(draft, updated, compiled, result_path)

    def _install(
        self, previous: CampaignDraftV1, updated: CampaignDraftV1, compiled: Any, result_path: Path
    ) -> dict[str, Any]:
        campaign_root = self._campaign_root(updated.campaign_id)
        staging_base = Path(
            tempfile.mkdtemp(prefix=f".{updated.campaign_id}.sequence-", dir=self.layout.active_campaign_root)
        )
        revision_root = (
            self.layout.research_artifact_root
            / "variant_sequence"
            / updated.campaign_id
            / updated.variants[-1].variant_id
        )
        backup_source = revision_root / "previous_source"
        displaced = revision_root / "displaced_source"
        draft_path = self.drafts.path_for(updated.campaign_id)
        draft_before = draft_path.read_bytes()
        ledger_path = self.project_root / "research_ledger.csv"
        ledger_before = ledger_path.read_bytes() if ledger_path.is_file() else None
        try:
            published = TransactionalCampaignPublisher(
                project_root=self.project_root,
                active_campaign_root=staging_base,
                repository_preflight=False,
            ).publish(compiled)
            staged = published.destination
            # The compiler owns only the authored campaign documents. Preserve
            # immutable follow-up attempts, generated indexes, and any other
            # campaign-local evidence that is outside that authored surface.
            authored_top_level = {
                "campaign.yaml",
                "authoring_manifest.json",
                "strategy_spec.yaml",
                "variants",
            }
            for existing in campaign_root.iterdir():
                if existing.name in authored_top_level:
                    continue
                _copy_preserved_path(existing, staged / existing.name)
            for prior in previous.variants:
                old_variant = campaign_root / "variants" / prior.variant_id
                new_variant = staged / "variants" / prior.variant_id
                for existing in old_variant.iterdir():
                    if existing.name == "config.yaml":
                        continue
                    _copy_preserved_path(existing, new_variant / existing.name)
                old = old_variant / "config.yaml"
                new = new_variant / "config.yaml"
                # Prior variant bytes are immutable even when shared
                # certifications or compiler metadata have advanced.
                shutil.copy2(old, new)
                if old.read_bytes() != new.read_bytes():
                    raise ValueError(f"sequential expansion attempted to change frozen {prior.variant_id} config")
            if revision_root.exists():
                raise FileExistsError(f"variant revision already exists: {revision_root}")
            revision_root.mkdir(parents=True)
            shutil.copytree(campaign_root, backup_source)
            (revision_root / "lineage.json").write_text(
                json.dumps(
                    {
                        "schema": "alphaquest.sequential-variant-install/v1",
                        "campaign_id": updated.campaign_id,
                        "variant_id": updated.variants[-1].variant_id,
                        "predecessor_result_path": display_path(result_path, self.project_root),
                        "installed_at": datetime.now(UTC).isoformat(),
                    },
                    indent=2,
                    sort_keys=True,
                )
                + "\n",
                encoding="utf-8",
            )
            os.replace(campaign_root, displaced)
            try:
                os.replace(staged, campaign_root)
                from alphaquest.research.preflight import run_preflight

                preflight = run_preflight(
                    config_paths=[campaign_root / "variants" / updated.variants[-1].variant_id / "config.yaml"],
                    run_tests=False,
                    project_root=self.project_root,
                )
                if preflight.get("passed") is not True:
                    raise ValueError(
                        "sequential variant preflight failed: "
                        + "; ".join(str(item) for item in preflight.get("failures") or [])
                    )
                self.drafts.replace_frozen_sequence(updated.campaign_id, updated)
                append_planned_publication(
                    updated, project_root=self.project_root, active_campaign_root=self.layout.active_campaign_root
                )
                refresh_generated_indexes_if_stale(self.project_root, force=True)
            except Exception:
                if campaign_root.exists():
                    shutil.rmtree(campaign_root)
                os.replace(displaced, campaign_root)
                _atomic_bytes(draft_path, draft_before)
                if ledger_before is None:
                    ledger_path.unlink(missing_ok=True)
                else:
                    _atomic_bytes(ledger_path, ledger_before)
                shutil.rmtree(revision_root, ignore_errors=True)
                raise
            shutil.rmtree(displaced)
        finally:
            shutil.rmtree(staging_base, ignore_errors=True)
        return {
            "research_verdict": "NEEDS MANUAL REVIEW",
            "campaign_id": updated.campaign_id,
            "variant_id": updated.variants[-1].variant_id,
            "variant_count": len(updated.variants),
            "next_action": "Generate mechanics evidence and complete the fixed manual chart review before performance testing.",
            "revision_path": display_path(revision_root, self.project_root),
        }

    def _draft(self, campaign_id: str) -> CampaignDraftV1:
        try:
            draft = self.drafts.validate(campaign_id)
        except ValidationError as exc:
            if "variant confirmations are stale" not in str(exc):
                raise
            document = self.drafts.load(campaign_id)
            _verify_frozen_document(document, campaign_id)
            payload = deepcopy(document["draft"])
            payload["confirmation_context_sha256"] = campaign_confirmation_context_sha256(payload)
            draft = CampaignDraftV1.model_validate(payload)
        if not draft.frozen:
            raise ValueError("only a published frozen campaign can add a sequential variant")
        if draft.variant_protocol != "sequential_failure_informed":
            raise ValueError("legacy predeclared campaigns cannot add sequential variants")
        return draft

    def _predecessor_source_config(self, result_path: Path) -> dict[str, Any]:
        source = result_path.parent.parent / "source_config.yaml"
        if not source.is_file():
            raise FileNotFoundError("terminal predecessor result is missing its immutable source_config.yaml")
        value = yaml.safe_load(source.read_text(encoding="utf-8")) or {}
        if not isinstance(value, dict):
            raise ValueError("terminal predecessor source config must be a mapping")
        return value

    def _predecessor_dataset_manifest(
        self,
        predecessor_config: Mapping[str, Any],
    ) -> dict[str, Any] | None:
        dataset_id = str(
            predecessor_config.get("dataset_id") or (predecessor_config.get("data") or {}).get("dataset_id") or ""
        )
        if not dataset_id:
            return None
        path = self.layout.dataset_root / dataset_id / "dataset_manifest.json"
        if not path.is_file():
            raise FileNotFoundError(f"predecessor governed dataset manifest is missing: {path}")
        value = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(value, dict) or value.get("dataset_id") != dataset_id:
            raise ValueError("predecessor governed dataset manifest identity is invalid")
        return value

    def _predecessor_execution_settings(
        self,
        predecessor_config: Mapping[str, Any],
    ) -> dict[str, Any]:
        data = predecessor_config.get("data") or {}
        core = predecessor_config.get("core") or {}
        apex = predecessor_config.get("apex_rules") or {}
        prop = predecessor_config.get("prop_rules") or {}
        account_bindings = predecessor_config.get("account_profile_bindings") or []
        tick_size = float(core.get("tick_size", 0.0))
        point_value = float(core.get("point_value", 0.0))
        tick_value = float(core.get("tick_value", tick_size * point_value))
        execution = {
            "session_start": str(data.get("rth_start") or "09:30:00"),
            "session_end": str(data.get("rth_end") or "16:00:00"),
            "latest_entry_time": str(apex.get("latest_entry_time") or core.get("latest_entry_time") or "15:30:00"),
            "flatten_time": str(apex.get("force_flatten_time") or core.get("flatten_time") or "15:55:00"),
            "latest_flat_time": str(
                apex.get("latest_flat_time") or apex.get("force_flatten_time") or core.get("flatten_time") or "15:55:00"
            ),
            "overnight_allowed": False,
            "initial_balance": float(core.get("initial_balance", 0.0)),
            "tick_size": tick_size,
            "point_value": point_value,
            "tick_value": tick_value,
            "commission_per_contract": float(core.get("commission_per_contract", 0.0)),
            "slippage_ticks": float(core.get("entry_slippage_ticks", core.get("slippage_ticks", 0.0))),
            "contracts": int(core.get("contracts", 1)),
            "prop_profile": str(prop.get("profile") or "configured_local_profile"),
        }
        target_account_profiles = [
            {
                "profile_id": str(item.get("profile_id") or ""),
                "version": str(item.get("version") or "") or None,
                "role": str(item.get("role") or "comparison"),
            }
            for item in account_bindings
            if isinstance(item, Mapping) and str(item.get("profile_id") or "")
        ]
        if target_account_profiles:
            execution["target_account_profiles"] = target_account_profiles
        return execution

    def _preserve_prior_variants(
        self,
        previous: CampaignDraftV1,
        updated: CampaignDraftV1,
        compiled: CompiledCampaign,
        *,
        predecessor_config: Mapping[str, Any],
    ) -> CompiledCampaign:
        campaign_root = self._campaign_root(previous.campaign_id)
        new_variant_id = updated.variants[-1].variant_id
        if list(compiled.variant_configs) != [new_variant_id]:
            raise ValueError("sequential expansion must compile only the newly declared variant")

        configs: dict[str, Any] = {}
        for prior in previous.variants:
            path = campaign_root / "variants" / prior.variant_id / "config.yaml"
            configs[prior.variant_id] = yaml.safe_load(path.read_text(encoding="utf-8"))
        configs[new_variant_id] = _plain_mutable(compiled.variant_configs[new_variant_id])

        validation = (predecessor_config.get("research_metadata") or {}).get("validation_gate", {}).get("data_subset")
        if isinstance(validation, Mapping):
            configs[new_variant_id]["research_metadata"]["validation_gate"]["data_subset"] = deepcopy(dict(validation))

        old_campaign_path = campaign_root / "campaign.yaml"
        campaign = yaml.safe_load(old_campaign_path.read_text(encoding="utf-8")) or {}
        new_campaign = _plain_mutable(compiled.campaign)
        campaign["timeframe"] = updated.timeframe
        campaign["variants"] = [variant.variant_id for variant in updated.variants]
        campaign["sequential_variant_history"] = [
            item.model_dump(mode="json", by_alias=True) for item in updated.sequential_variant_history
        ]
        new_event_strategies = new_campaign.get("event_strategies") or {}
        if new_variant_id in new_event_strategies:
            campaign.setdefault("event_strategies", {})[new_variant_id] = new_event_strategies[
                new_variant_id
            ]
        campaign.setdefault("variant_distinctions", {})[new_variant_id] = new_campaign["variant_distinctions"][
            new_variant_id
        ]

        old_spec_path = campaign_root / "strategy_spec.yaml"
        old_spec = yaml.safe_load(old_spec_path.read_text(encoding="utf-8")) or {}
        strategy_spec = deepcopy(old_spec)
        new_spec = _plain_mutable(compiled.strategy_spec)
        strategy_spec["draft_sha256"] = _object_sha256(updated.model_dump(mode="json", by_alias=True))
        strategy_spec["dataset"] = updated.dataset.model_dump(mode="json", by_alias=True)
        strategy_spec["execution"] = updated.execution.model_dump(mode="json")
        strategy_spec.setdefault("variants", []).append(deepcopy(new_spec["variants"][0]))
        new_spec_certifications = new_spec.get("variant_strategy_certifications") or {}
        if new_variant_id in new_spec_certifications:
            strategy_spec.setdefault("variant_strategy_certifications", {})[
                new_variant_id
            ] = deepcopy(new_spec_certifications[new_variant_id])

        old_manifest_path = campaign_root / "authoring_manifest.json"
        old_manifest = json.loads(old_manifest_path.read_text(encoding="utf-8"))
        manifest = deepcopy(old_manifest)
        new_manifest = _plain_mutable(compiled.authoring_manifest)
        full_draft_sha256 = _object_sha256(updated.model_dump(mode="json", by_alias=True))
        manifest["draft_sha256"] = full_draft_sha256
        manifest["dataset_id"] = updated.dataset.dataset_id
        manifest["dataset_canonical_sha256"] = updated.dataset.canonical_sha256
        manifest["variant_count"] = len(updated.variants)
        manifest["variant_protocol"] = updated.variant_protocol
        manifest["variant_mechanic_signatures"] = {
            variant.variant_id: variant.mechanic_signature for variant in updated.variants
        }
        new_manifest_certifications = (
            new_manifest.get("variant_strategy_certifications") or {}
        )
        if new_variant_id in new_manifest_certifications:
            manifest.setdefault("variant_strategy_certifications", {})[
                new_variant_id
            ] = deepcopy(new_manifest_certifications[new_variant_id])
        manifest["planned_files"] = [
            "campaign.yaml",
            "strategy_spec.yaml",
            "authoring_manifest.json",
            *[f"variants/{variant.variant_id}/config.yaml" for variant in updated.variants],
        ]
        manifest["compiled_document_sha256"] = {
            "campaign.yaml": _object_sha256(campaign),
            "strategy_spec.yaml": _object_sha256(strategy_spec),
            **{f"variants/{variant_id}/config.yaml": _object_sha256(config) for variant_id, config in configs.items()},
        }
        return CompiledCampaign(
            draft=updated,
            campaign=campaign,
            variant_configs=configs,
            authoring_manifest=manifest,
            strategy_spec=strategy_spec,
            draft_sha256=full_draft_sha256,
        )

    def _campaign_root(self, campaign_id: str) -> Path:
        path = self.layout.active_campaign_root / campaign_id
        if not (path / "campaign.yaml").is_file():
            raise FileNotFoundError(f"active Studio campaign is missing: {path}")
        return path

    def _latest_result(self, campaign_id: str, variant_id: str) -> tuple[Path | None, dict[str, Any]]:
        root = self.layout.evidence_roots[0] / campaign_id / variant_id
        candidates = sorted(
            root.glob("**/reporting_v2/result_bundle_v2.json"), key=lambda item: item.stat().st_mtime, reverse=True
        )
        for path in candidates:
            try:
                value = json.loads(path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                continue
            if (
                isinstance(value, dict)
                and value.get("campaign_id") == campaign_id
                and value.get("variant_id") == variant_id
            ):
                return path, value
        return None, {}


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _failure_context(result: Mapping[str, Any]) -> dict[str, Any]:
    criteria = result.get("stage_criteria")
    if isinstance(criteria, list):
        for item in criteria:
            if not isinstance(item, Mapping) or str(item.get("result") or "") != "FAIL":
                continue
            actual = item.get("actual")
            threshold = item.get("threshold")
            return {
                "stage": str(item.get("stage") or "terminal assessment"),
                "metric": str(item.get("metric") or "campaign verdict"),
                "actual": actual.get("value") if isinstance(actual, Mapping) else actual,
                "threshold": threshold.get("value") if isinstance(threshold, Mapping) else threshold,
                "operator": item.get("operator"),
                "reason": str(item.get("reason") or ""),
                "verdict_message": str(result.get("verdict_message") or ""),
            }
    return {
        "stage": "terminal assessment",
        "metric": "campaign verdict",
        "actual": "FAIL",
        "threshold": "PASS",
        "operator": "==",
        "reason": str(result.get("verdict_message") or "The predecessor received a terminal FAIL."),
        "verdict_message": str(result.get("verdict_message") or ""),
    }


def _atomic_bytes(path: Path, value: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    handle, name = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=path.parent)
    temporary = Path(name)
    try:
        with os.fdopen(handle, "wb") as stream:
            stream.write(value)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def _plain_mutable(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {str(key): _plain_mutable(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_plain_mutable(item) for item in value]
    return deepcopy(value)


def _copy_preserved_path(source: Path, destination: Path) -> None:
    if source.is_dir():
        shutil.copytree(source, destination)
    else:
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, destination)


__all__ = ["MAX_VARIANTS", "SequentialVariantService"]
