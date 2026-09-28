"""Research Studio application services.

The Studio is a novice-facing client over AlphaQuest's existing research and
execution contracts.  Importing this package must not require optional UI or
AI dependencies.
"""

from alphaquest.studio.ai import (
    AIDraftProvenance,
    OpenAIResearchDraftAdapter,
    ResearchBriefSuggestion,
)
from alphaquest.studio.approvals import (
    MechanicsApprovalService,
    MechanicsReviewPlan,
    require_all_variant_mechanics_approved,
)
from alphaquest.studio.candidate_review import CandidateReviewService, CandidateReviewV1
from alphaquest.studio.codex_runtime import (
    CodexAvailabilityV1,
    CodexRunProvenanceV1,
    CodexRunner,
    CodexTaskRecordV1,
    CodexTaskRequestV1,
    SQLiteCodexTaskQueue,
)
from alphaquest.studio.finalization import FinalizationResult, RunFinalizer
from alphaquest.studio.factory_reviews import (
    EngineeringHandoffIntentHumanAcceptanceV1,
    HypothesisHumanAcceptanceV1,
    ReviewedEngineeringHandoffIntentArtifactV1,
    ReviewedHypothesisArtifactV1,
    ReviewedSourceEvidenceArtifactV1,
    ReviewedSourceEvidenceArtifactV2,
    SourceClaimHumanReviewV1,
    SourceEvidenceHumanVerificationV1,
    SourceEvidenceHumanVerificationV2,
    SourceFullTextCaptureBindingV1,
    build_reviewed_source_evidence_v2,
)
from alphaquest.studio.followups import (
    FollowUpAttemptRequestV1,
    FollowUpAttemptResult,
    FollowUpAttemptService,
    MechanicParameterPatchV1,
)
from alphaquest.studio.forward_incubation import (
    ForwardIncubationEventV1,
    ForwardIncubationPlanV1,
    ForwardIncubationService,
)
from alphaquest.studio.jobs import JobExecutionContext, JobRecordV1, OperationalState, SQLiteJobQueue
from alphaquest.studio.portfolio import (
    AccountContractLimitsV1,
    CandidateEvidencePaths,
    DeploymentDecisionService,
    DeploymentDecisionV1,
    DeploymentMonitoringService,
    MonitoringThresholdsV1,
    PortfolioReviewService,
    PortfolioReviewV1,
)
from alphaquest.studio.results import ResultBundleBuilder, ResultBundleV2
from alphaquest.studio.research_factory import (
    BudgetUsageV1,
    CodexProposalEnvelopeV1,
    CodexTaskV1,
    ContextPacketV1,
    FailureDiagnosisV1,
    HypothesisProposalV1,
    InformationAccessEventV1,
    MechanicsIntentV1,
    NextActionEligibilityV1,
    NextActionRankingProposalV1,
    NextExperimentProposalV1,
    ResearchBudgetV1,
    SourceEvidenceBundleV1,
    build_codex_task,
    build_context_packet,
    classify_result_failure,
    determine_next_action_eligibility,
    validate_and_import_proposal,
)
from alphaquest.studio.schemas import stale_studio_schema_documents, studio_schema_documents
from alphaquest.studio.worker import MECHANICS_VALIDATION_RUN, StudioWorker, run_forever, run_once

__all__ = [
    "AIDraftProvenance",
    "AccountContractLimitsV1",
    "CandidateEvidencePaths",
    "CandidateReviewService",
    "CandidateReviewV1",
    "CodexAvailabilityV1",
    "CodexProposalEnvelopeV1",
    "CodexRunProvenanceV1",
    "CodexRunner",
    "CodexTaskRecordV1",
    "CodexTaskRequestV1",
    "CodexTaskV1",
    "ContextPacketV1",
    "FinalizationResult",
    "DeploymentDecisionService",
    "DeploymentDecisionV1",
    "DeploymentMonitoringService",
    "EngineeringHandoffIntentHumanAcceptanceV1",
    "FollowUpAttemptRequestV1",
    "FollowUpAttemptResult",
    "FollowUpAttemptService",
    "FailureDiagnosisV1",
    "ForwardIncubationEventV1",
    "ForwardIncubationPlanV1",
    "ForwardIncubationService",
    "JobExecutionContext",
    "JobRecordV1",
    "HypothesisProposalV1",
    "HypothesisHumanAcceptanceV1",
    "InformationAccessEventV1",
    "MechanicsApprovalService",
    "MechanicParameterPatchV1",
    "MechanicsReviewPlan",
    "MECHANICS_VALIDATION_RUN",
    "OpenAIResearchDraftAdapter",
    "OperationalState",
    "MonitoringThresholdsV1",
    "MechanicsIntentV1",
    "NextActionEligibilityV1",
    "NextActionRankingProposalV1",
    "NextExperimentProposalV1",
    "PortfolioReviewService",
    "PortfolioReviewV1",
    "ResearchBriefSuggestion",
    "ReviewedEngineeringHandoffIntentArtifactV1",
    "ReviewedHypothesisArtifactV1",
    "ReviewedSourceEvidenceArtifactV1",
    "ReviewedSourceEvidenceArtifactV2",
    "ResearchBudgetV1",
    "BudgetUsageV1",
    "ResultBundleBuilder",
    "ResultBundleV2",
    "RunFinalizer",
    "SQLiteJobQueue",
    "SQLiteCodexTaskQueue",
    "SourceEvidenceBundleV1",
    "SourceClaimHumanReviewV1",
    "SourceEvidenceHumanVerificationV1",
    "SourceEvidenceHumanVerificationV2",
    "SourceFullTextCaptureBindingV1",
    "StudioWorker",
    "require_all_variant_mechanics_approved",
    "build_codex_task",
    "build_context_packet",
    "build_reviewed_source_evidence_v2",
    "classify_result_failure",
    "determine_next_action_eligibility",
    "run_forever",
    "run_once",
    "stale_studio_schema_documents",
    "studio_schema_documents",
    "validate_and_import_proposal",
]
