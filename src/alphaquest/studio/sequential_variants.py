"""Failure-informed, one-at-a-time variant expansion for Studio campaigns."""

from __future__ import annotations

from datetime import UTC, datetime
import hashlib
import json
import os
from pathlib import Path
import shutil
import tempfile
from typing import Any, Mapping

from alphaquest.authoring import CampaignCompiler, CampaignDraftV1, TransactionalCampaignPublisher
from alphaquest.authoring.models import VariantDraftV1, campaign_confirmation_context_sha256
from alphaquest.research.storage import display_path, load_storage_layout
from alphaquest.studio.approvals import MechanicsApprovalService
from alphaquest.studio.drafts import DraftStore
from alphaquest.studio.ledger import append_planned_publication
from alphaquest.studio.variants import suggest_variant_card
from alphaquest.studio.workspace import refresh_generated_indexes_if_stale


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
        config_path = self._campaign_root(campaign_id) / "variants" / current.variant_id / "config.yaml"
        approval = MechanicsApprovalService().inspect(config_path)
        result_path, result = self._latest_result(campaign_id, current.variant_id)
        verdict = str(result.get("verdict") or result.get("research_verdict") or "")
        blockers: list[str] = []
        if len(draft.variants) >= MAX_VARIANTS:
            blockers.append("the campaign has reached the five-variant maximum")
        if approval.get("status") != "APPROVED_FOR_TESTING":
            blockers.append("the current variant has not passed manual mechanics review")
        if result_path is None:
            blockers.append("the current variant has no complete ResultBundleV2")
        elif verdict != "FAIL":
            blockers.append(f"the current variant verdict is {verdict or 'unresolved'}; only FAIL permits another variant")
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
        compiled = CampaignCompiler(
            evidence_root=display_path(self.layout.evidence_roots[0], self.project_root),
            research_artifact_root=display_path(self.layout.research_artifact_root, self.project_root),
        ).compile(updated)
        return self._install(draft, updated, compiled, result_path)

    def _install(self, previous: CampaignDraftV1, updated: CampaignDraftV1, compiled: Any, result_path: Path) -> dict[str, Any]:
        campaign_root = self._campaign_root(updated.campaign_id)
        staging_base = Path(tempfile.mkdtemp(prefix=f".{updated.campaign_id}.sequence-", dir=self.layout.active_campaign_root))
        revision_root = self.layout.research_artifact_root / "variant_sequence" / updated.campaign_id / updated.variants[-1].variant_id
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
            for prior in previous.variants:
                old = campaign_root / "variants" / prior.variant_id / "config.yaml"
                new = staged / "variants" / prior.variant_id / "config.yaml"
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
                ) + "\n",
                encoding="utf-8",
            )
            os.replace(campaign_root, displaced)
            try:
                os.replace(staged, campaign_root)
                from alphaquest.research.preflight import run_preflight

                preflight = run_preflight(
                    config_paths=sorted(campaign_root.glob("variants/*/config.yaml")),
                    run_tests=False,
                    project_root=self.project_root,
                )
                if preflight.get("passed") is not True:
                    raise ValueError(
                        "sequential variant preflight failed: "
                        + "; ".join(str(item) for item in preflight.get("failures") or [])
                    )
                self.drafts.replace_frozen_sequence(updated.campaign_id, updated)
                append_planned_publication(updated, project_root=self.project_root, active_campaign_root=self.layout.active_campaign_root)
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
        draft = self.drafts.validate(campaign_id)
        if not draft.frozen:
            raise ValueError("only a published frozen campaign can add a sequential variant")
        if draft.variant_protocol != "sequential_failure_informed":
            raise ValueError("legacy predeclared campaigns cannot add sequential variants")
        return draft

    def _campaign_root(self, campaign_id: str) -> Path:
        path = self.layout.active_campaign_root / campaign_id
        if not (path / "campaign.yaml").is_file():
            raise FileNotFoundError(f"active Studio campaign is missing: {path}")
        return path

    def _latest_result(self, campaign_id: str, variant_id: str) -> tuple[Path | None, dict[str, Any]]:
        root = self.layout.evidence_roots[0] / campaign_id / variant_id
        candidates = sorted(root.glob("**/reporting_v2/result_bundle_v2.json"), key=lambda item: item.stat().st_mtime, reverse=True)
        for path in candidates:
            try:
                value = json.loads(path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                continue
            if isinstance(value, dict) and value.get("campaign_id") == campaign_id and value.get("variant_id") == variant_id:
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


__all__ = ["MAX_VARIANTS", "SequentialVariantService"]
