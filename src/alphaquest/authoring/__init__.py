"""Strict no-code authoring contracts and deterministic compilation services."""

from alphaquest.authoring.bar_rules import (
    BarRuleValidationError,
    SafeBarRuleEvaluator,
    referenced_features,
    required_history_bars,
    validate_bar_rule,
)
from alphaquest.authoring.catalog import (
    CERTIFIED_MODULE_CATALOG,
    CertifiedModuleCatalog,
    ModuleCatalogError,
    get_certified_module_catalog,
)
from alphaquest.authoring.compiler import (
    CampaignCompilationError,
    CampaignCompiler,
    CompiledCampaign,
    mechanics_validation_subset,
)
from alphaquest.authoring.models import (
    BarRuleV1,
    CampaignDraftV1,
    DatasetManifestV1,
    DuplicateReviewV1,
    ExecutionSettingsV1,
    ModuleBindingV1,
    ModuleManifestV1,
    VariantDraftV1,
    campaign_confirmation_context_sha256,
)
from alphaquest.authoring.publisher import (
    CampaignPublishError,
    PublishResult,
    TransactionalCampaignPublisher,
)
from alphaquest.authoring.schemas import authoring_schema_documents, write_authoring_schemas


__all__ = [
    "BarRuleV1",
    "BarRuleValidationError",
    "CERTIFIED_MODULE_CATALOG",
    "CampaignCompilationError",
    "CampaignCompiler",
    "CampaignDraftV1",
    "CampaignPublishError",
    "CertifiedModuleCatalog",
    "CompiledCampaign",
    "DatasetManifestV1",
    "DuplicateReviewV1",
    "ExecutionSettingsV1",
    "ModuleBindingV1",
    "ModuleCatalogError",
    "ModuleManifestV1",
    "PublishResult",
    "SafeBarRuleEvaluator",
    "TransactionalCampaignPublisher",
    "VariantDraftV1",
    "authoring_schema_documents",
    "get_certified_module_catalog",
    "mechanics_validation_subset",
    "referenced_features",
    "required_history_bars",
    "validate_bar_rule",
    "write_authoring_schemas",
    "campaign_confirmation_context_sha256",
]
