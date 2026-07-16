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
from alphaquest.studio.finalization import FinalizationResult, RunFinalizer
from alphaquest.studio.followups import (
    FollowUpAttemptRequestV1,
    FollowUpAttemptResult,
    FollowUpAttemptService,
    MechanicParameterPatchV1,
)
from alphaquest.studio.jobs import JobExecutionContext, JobRecordV1, OperationalState, SQLiteJobQueue
from alphaquest.studio.results import ResultBundleBuilder, ResultBundleV2
from alphaquest.studio.schemas import stale_studio_schema_documents, studio_schema_documents
from alphaquest.studio.worker import MECHANICS_VALIDATION_RUN, StudioWorker, run_forever, run_once

__all__ = [
    "AIDraftProvenance",
    "CandidateReviewService",
    "CandidateReviewV1",
    "FinalizationResult",
    "FollowUpAttemptRequestV1",
    "FollowUpAttemptResult",
    "FollowUpAttemptService",
    "JobExecutionContext",
    "JobRecordV1",
    "MechanicsApprovalService",
    "MechanicParameterPatchV1",
    "MechanicsReviewPlan",
    "MECHANICS_VALIDATION_RUN",
    "OpenAIResearchDraftAdapter",
    "OperationalState",
    "ResearchBriefSuggestion",
    "ResultBundleBuilder",
    "ResultBundleV2",
    "RunFinalizer",
    "SQLiteJobQueue",
    "StudioWorker",
    "require_all_variant_mechanics_approved",
    "run_forever",
    "run_once",
    "stale_studio_schema_documents",
    "studio_schema_documents",
]
