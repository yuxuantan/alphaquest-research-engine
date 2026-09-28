"""Transport admission for existing immutable reviews; never approval evidence.

An intent pins the first server-admitted decision across browser origins and
process restarts. Only the ordinary reviewed artifact grants the existing
proposal-stage authority. There is no automatic retry with changed human input.
"""
from __future__ import annotations

import json
from typing import Any, Literal

from pydantic import Field, model_validator

from alphaquest.studio.factory_reviews import (
    ReviewedEngineeringHandoffIntentArtifactV1,
    ReviewedHypothesisArtifactV1,
    ReviewedSourceEvidenceArtifactV1,
    ReviewedSourceEvidenceArtifactV2,
)
from alphaquest.studio.research_factory import FactoryModel, SHA256_PATTERN, object_sha256

ReviewArtifact = (
    ReviewedSourceEvidenceArtifactV1 | ReviewedSourceEvidenceArtifactV2 | ReviewedHypothesisArtifactV1
    | ReviewedEngineeringHandoffIntentArtifactV1
)


class ReviewDeliveryV1(FactoryModel):
    operation_id: str = Field(pattern=r"^[A-Za-z0-9][A-Za-z0-9_.-]{0,127}$")
    proposal_id: str = Field(min_length=1)
    payload_sha256: str = Field(pattern=SHA256_PATTERN)
    validation_sha256: str = Field(pattern=SHA256_PATTERN)

    def matches(self, artifact: ReviewArtifact) -> bool:
        return (
            self.proposal_id == artifact.proposal_id
            and self.payload_sha256 == artifact.proposal_payload_sha256
            and self.validation_sha256 == artifact.proposal_validation_sha256
        )


def substantive_review(artifact: ReviewArtifact) -> dict[str, Any]:
    """Exclude only server-generated attribution identity/time and derived hash.

    Every human field, nested claim, proposal binding and upstream artifact
    remains in the comparison. The first admission retains the excluded values.
    """
    value = artifact.model_dump(mode="json", by_alias=True)
    value.pop("artifact_sha256")
    review = value.get("human_verification", value.get("human_acceptance"))
    review.pop("review_id")
    review.pop("reviewed_at")
    return value


class ReviewDeliveryIntentV1(FactoryModel):
    schema_name: Literal["alphaquest.review-delivery-intent/v1"] = Field(
        default="alphaquest.review-delivery-intent/v1", alias="schema"
    )
    delivery: ReviewDeliveryV1
    artifact: ReviewArtifact
    request_sha256: str = Field(pattern=SHA256_PATTERN)
    intent_sha256: str = Field(pattern=SHA256_PATTERN)

    @model_validator(mode="after")
    def _integrity(self) -> "ReviewDeliveryIntentV1":
        if not self.delivery.matches(self.artifact):
            raise ValueError("review delivery proposal binding mismatch")
        if self.request_sha256 != object_sha256(substantive_review(self.artifact)):
            raise ValueError("review delivery request hash mismatch")
        value = self.model_dump(mode="json", by_alias=True, exclude={"intent_sha256"})
        if self.intent_sha256 != object_sha256(value):
            raise ValueError("review delivery intent hash mismatch")
        return self


def build_delivery_intent(delivery: ReviewDeliveryV1, artifact: ReviewArtifact) -> ReviewDeliveryIntentV1:
    value = {
        "schema": "alphaquest.review-delivery-intent/v1",
        "delivery": delivery.model_dump(mode="json"),
        "artifact": artifact.model_dump(mode="json", by_alias=True),
        "request_sha256": object_sha256(substantive_review(artifact)),
    }
    return ReviewDeliveryIntentV1.model_validate_json(
        json.dumps({**value, "intent_sha256": object_sha256(value)}, allow_nan=False)
    )
