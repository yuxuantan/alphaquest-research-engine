"""Generated JSON Schema documents for public Studio operational contracts."""

from __future__ import annotations

import json
import os
from pathlib import Path
from tempfile import NamedTemporaryFile
from typing import Any

from alphaquest.studio.candidate_review import CandidateReviewV1
from alphaquest.studio.forward_incubation import (
    ForwardIncubationEventV1,
    ForwardIncubationPlanV1,
)
from alphaquest.studio.jobs import JobRecordV1
from alphaquest.studio.factory_reviews import (
    ReviewedEngineeringHandoffIntentArtifactV1,
    ReviewedHypothesisArtifactV1,
    ReviewedSourceEvidenceArtifactV1,
    ReviewedSourceEvidenceArtifactV2,
)
from alphaquest.studio.codex_runtime import (
    CodexRunProvenanceV1 as RuntimeCodexRunProvenanceV1,
    CodexTaskRecordV1,
    CodexTaskRequestV1,
)
from alphaquest.studio.portfolio import (
    DeploymentDecisionV1,
    DeploymentMonitoringEventV1,
    PortfolioReviewV1,
)
from alphaquest.studio.research_factory import (
    BudgetUsageV1,
    CandidateDueDiligenceSummaryV1,
    CodexProposalEnvelopeV1,
    CodexRunProvenanceV1 as ProposalCodexRunProvenanceV1,
    CodexTaskV1,
    ContextPacketV1,
    EngineeringHandoffProposalV1,
    FailureDiagnosisV1,
    HypothesisProposalV1,
    ImportedProposalV1,
    InformationAccessEventV1,
    InformationAccessLedgerV1,
    MechanicsIntentV1,
    NextActionEligibilityV1,
    NextActionRankingProposalV1,
    NextExperimentProposalV1,
    ResearchBudgetV1,
    SourceEvidenceBundleV1,
)
from alphaquest.studio.results import ResultBundleV2, ResultBundleV3
from alphaquest.accounts.models import AccountRuleProfileV1
from alphaquest.research.edge_backlog import (
    EdgeBacklogDecisionV1,
    EdgeBacklogEntryRevisionV1,
    EdgeBacklogLinkV1,
    ObservationRevisionV1,
)
from alphaquest.research.edge_backlog_taxonomy import (
    EconomicEdgeFingerprintV1,
    EconomicEdgeTaxonomyV1,
)


STUDIO_SCHEMA_MODELS = {
    "account-rule-profile-v1.schema.json": AccountRuleProfileV1,
    "candidate-review-v1.schema.json": CandidateReviewV1,
    "candidate-due-diligence-summary-v1.schema.json": CandidateDueDiligenceSummaryV1,
    "codex-context-packet-v1.schema.json": ContextPacketV1,
    "codex-proposal-envelope-v1.schema.json": CodexProposalEnvelopeV1,
    "codex-proposal-run-provenance-v1.schema.json": ProposalCodexRunProvenanceV1,
    "codex-runtime-run-provenance-v1.schema.json": RuntimeCodexRunProvenanceV1,
    "codex-task-record-v1.schema.json": CodexTaskRecordV1,
    "codex-task-request-v1.schema.json": CodexTaskRequestV1,
    "codex-task-v1.schema.json": CodexTaskV1,
    "deployment-decision-v1.schema.json": DeploymentDecisionV1,
    "deployment-monitoring-event-v1.schema.json": DeploymentMonitoringEventV1,
    "edge-backlog-decision-v1.schema.json": EdgeBacklogDecisionV1,
    "edge-backlog-economic-taxonomy-v1.schema.json": EconomicEdgeTaxonomyV1,
    "edge-backlog-entry-revision-v1.schema.json": EdgeBacklogEntryRevisionV1,
    "edge-backlog-fingerprint-v1.schema.json": EconomicEdgeFingerprintV1,
    "edge-backlog-link-v1.schema.json": EdgeBacklogLinkV1,
    "edge-backlog-observation-revision-v1.schema.json": ObservationRevisionV1,
    "engineering-handoff-proposal-v1.schema.json": EngineeringHandoffProposalV1,
    "failure-diagnosis-v1.schema.json": FailureDiagnosisV1,
    "forward-incubation-event-v1.schema.json": ForwardIncubationEventV1,
    "forward-incubation-plan-v1.schema.json": ForwardIncubationPlanV1,
    "hypothesis-proposal-v1.schema.json": HypothesisProposalV1,
    "imported-proposal-v1.schema.json": ImportedProposalV1,
    "information-access-event-v1.schema.json": InformationAccessEventV1,
    "information-access-ledger-v1.schema.json": InformationAccessLedgerV1,
    "job-record-v1.schema.json": JobRecordV1,
    "mechanics-intent-v1.schema.json": MechanicsIntentV1,
    "next-action-eligibility-v1.schema.json": NextActionEligibilityV1,
    "next-action-ranking-proposal-v1.schema.json": NextActionRankingProposalV1,
    "next-experiment-proposal-v1.schema.json": NextExperimentProposalV1,
    "portfolio-review-v1.schema.json": PortfolioReviewV1,
    "research-budget-usage-v1.schema.json": BudgetUsageV1,
    "research-budget-v1.schema.json": ResearchBudgetV1,
    "reviewed-engineering-handoff-intent-v1.schema.json": ReviewedEngineeringHandoffIntentArtifactV1,
    "reviewed-hypothesis-v1.schema.json": ReviewedHypothesisArtifactV1,
    "reviewed-source-evidence-v1.schema.json": ReviewedSourceEvidenceArtifactV1,
    "reviewed-source-evidence-v2.schema.json": ReviewedSourceEvidenceArtifactV2,
    "result-bundle-v2.schema.json": ResultBundleV2,
    "result-bundle-v3.schema.json": ResultBundleV3,
    "source-evidence-bundle-v1.schema.json": SourceEvidenceBundleV1,
}


def studio_schema_documents() -> dict[str, dict[str, Any]]:
    return {
        filename: model.model_json_schema(by_alias=True)
        for filename, model in STUDIO_SCHEMA_MODELS.items()
    }


def write_studio_schema_documents(output_dir: str | Path) -> list[Path]:
    """Atomically refresh committed schemas from their owning Pydantic models."""

    directory = Path(output_dir)
    directory.mkdir(parents=True, exist_ok=True)
    written = []
    for filename, document in studio_schema_documents().items():
        path = directory / filename
        data = (json.dumps(document, indent=2, sort_keys=True, allow_nan=False) + "\n").encode("utf-8")
        with NamedTemporaryFile(dir=directory, prefix=f".{filename}.", suffix=".tmp", delete=False) as handle:
            temporary = Path(handle.name)
            handle.write(data)
            handle.flush()
            os.fsync(handle.fileno())
        try:
            os.replace(temporary, path)
        finally:
            temporary.unlink(missing_ok=True)
        written.append(path)
    return written


def stale_studio_schema_documents(output_dir: str | Path) -> list[str]:
    """Return committed schema names that are missing or out of sync."""

    directory = Path(output_dir)
    stale = []
    for filename, expected in studio_schema_documents().items():
        path = directory / filename
        try:
            actual = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            stale.append(filename)
            continue
        if actual != expected:
            stale.append(filename)
    return stale
