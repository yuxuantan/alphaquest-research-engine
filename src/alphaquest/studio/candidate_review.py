"""Independent reviewer sign-off for terminal candidate-strategy results."""

from __future__ import annotations

from datetime import UTC, datetime
import hashlib
import json
import os
from pathlib import Path
from tempfile import NamedTemporaryFile
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator
import yaml

from alphaquest.studio.results import ResultBundleV2, load_result_bundle
from alphaquest.studio.finalization import inspect_finalized_result
from alphaquest.validation.promotion_gate import APPROVAL_SCHEMA, inspect_validation_gate


CANDIDATE_REVIEW_SCHEMA = "alphaquest.candidate-review/v1"
CANDIDATE_REVIEW_FILENAME = "candidate_review.json"


class CandidateReviewV1(BaseModel):
    """Hash-bound independent decision for a terminal PASS result."""

    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    schema_name: Literal["alphaquest.candidate-review/v1"] = Field(
        default=CANDIDATE_REVIEW_SCHEMA,
        alias="schema",
        serialization_alias="schema",
    )
    campaign_id: str
    variant_id: str
    run_id: str
    decision: Literal["approved_candidate", "rejected", "needs_manual_review"]
    reviewer: str
    reviewed_at: datetime
    notes: str
    result_bundle_sha256: str
    mechanics_approval_sha256: str
    config_hash: str
    input_data_hash: str
    mechanics_reviewer: str
    review_scope: Literal["independent_candidate_assessment"] = "independent_candidate_assessment"
    lifecycle_state: Literal["candidate", "rejected", "needs_manual_review"]

    @field_validator(
        "campaign_id",
        "variant_id",
        "run_id",
        "reviewer",
        "notes",
        "result_bundle_sha256",
        "mechanics_approval_sha256",
        "config_hash",
        "input_data_hash",
        "mechanics_reviewer",
    )
    @classmethod
    def _nonblank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("value must be non-empty")
        return value.strip()

    @field_validator("reviewed_at")
    @classmethod
    def _timezone_aware(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("reviewed_at must be timezone-aware")
        return value


class CandidateReviewService:
    """Create and validate independent candidate decisions."""

    def review(
        self,
        *,
        result_bundle_path: str | Path,
        config_path: str | Path,
        reviewer: str,
        decision: Literal["approved_candidate", "rejected", "needs_manual_review"],
        notes: str,
        output_path: str | Path | None = None,
        reviewed_at: datetime | str | None = None,
    ) -> CandidateReviewV1:
        result_path = Path(result_bundle_path).resolve()
        config = Path(config_path).resolve()
        finalized = inspect_finalized_result(result_path, config_path=config)
        if not finalized["valid"]:
            raise ValueError(
                "candidate review requires a complete hash-valid finalization transaction: "
                + "; ".join(finalized["errors"])
            )
        bundle = finalized["bundle"]
        assert isinstance(bundle, ResultBundleV2)
        cfg = _load_yaml(config)
        gate = inspect_validation_gate(cfg, config)
        if gate.get("status") != "APPROVED_FOR_TESTING":
            raise ValueError(
                "candidate review requires a current mechanics approval: "
                + "; ".join(gate.get("errors") or [str(gate.get("status"))])
            )
        approval_path = Path(str(gate.get("approval_path")))
        approval = _load_json_mapping(approval_path, "mechanics approval")
        if approval.get("schema") != APPROVAL_SCHEMA or approval.get("status") != "approved_for_testing":
            raise ValueError("candidate review requires an approved mechanics-validation decision")
        mechanics_reviewer = str(approval.get("reviewer") or "").strip()
        reviewer_value = reviewer.strip()
        notes_value = notes.strip()
        if not reviewer_value or not notes_value:
            raise ValueError("reviewer and review notes are required")
        if reviewer_value.casefold() == mechanics_reviewer.casefold():
            raise ValueError("candidate reviewer must be different from the mechanics reviewer")
        if decision == "approved_candidate" and bundle.verdict != "PASS":
            raise ValueError("only a terminal PASS may be approved as a candidate strategy")

        lifecycle = {
            "approved_candidate": "candidate",
            "rejected": "rejected",
            "needs_manual_review": "needs_manual_review",
        }[decision]
        review = CandidateReviewV1(
            campaign_id=bundle.campaign_id,
            variant_id=bundle.variant_id,
            run_id=bundle.run_id,
            decision=decision,
            reviewer=reviewer_value,
            reviewed_at=_aware_datetime(reviewed_at),
            notes=notes_value,
            result_bundle_sha256=_file_sha256(result_path),
            mechanics_approval_sha256=_file_sha256(approval_path),
            config_hash=str(gate.get("config_hash") or ""),
            input_data_hash=str(gate.get("input_data_hash") or ""),
            mechanics_reviewer=mechanics_reviewer,
            lifecycle_state=lifecycle,
        )
        target = Path(output_path).resolve() if output_path else result_path.parent / CANDIDATE_REVIEW_FILENAME
        previous = target.read_bytes() if target.is_file() else None
        _write_review(target, review)
        report = self.inspect(
            candidate_review_path=target,
            result_bundle_path=result_path,
            config_path=config,
        )
        if not report["valid"]:
            if previous is None:
                target.unlink(missing_ok=True)
            else:
                _atomic_write_bytes(target, previous)
            raise ValueError("candidate review failed verification: " + "; ".join(report["errors"]))
        return review

    def inspect(
        self,
        *,
        candidate_review_path: str | Path,
        result_bundle_path: str | Path,
        config_path: str | Path,
    ) -> dict[str, Any]:
        errors: list[str] = []
        try:
            review = CandidateReviewV1.model_validate(
                _load_json_mapping(Path(candidate_review_path), "candidate review")
            )
        except (ValueError, OSError) as exc:
            return {"valid": False, "lifecycle_state": "review_required", "errors": [str(exc)]}
        try:
            result_path = Path(result_bundle_path).resolve()
            config = Path(config_path).resolve()
            finalized = inspect_finalized_result(result_path, config_path=config)
            if not finalized["valid"]:
                raise ValueError("; ".join(finalized["errors"]))
            bundle = finalized["bundle"]
            if not isinstance(bundle, ResultBundleV2):
                raise ValueError("finalized result bundle is unavailable")
            gate = inspect_validation_gate(_load_yaml(config), config)
            approval_path = Path(str(gate.get("approval_path")))
            approval = _load_json_mapping(approval_path, "mechanics approval")
        except (ValueError, OSError) as exc:
            return {"valid": False, "lifecycle_state": "review_required", "errors": [str(exc)]}

        if gate.get("status") != "APPROVED_FOR_TESTING":
            errors.append("mechanics approval is stale or unresolved")
        if review.result_bundle_sha256 != _file_sha256(result_path):
            errors.append("result bundle hash is stale or mismatched")
        if review.mechanics_approval_sha256 != _file_sha256(approval_path):
            errors.append("mechanics approval hash is stale or mismatched")
        if review.config_hash != str(gate.get("config_hash") or ""):
            errors.append("candidate review config hash is stale or mismatched")
        if review.input_data_hash != str(gate.get("input_data_hash") or ""):
            errors.append("candidate review input-data hash is stale or mismatched")
        if (review.campaign_id, review.variant_id, review.run_id) != (
            bundle.campaign_id,
            bundle.variant_id,
            bundle.run_id,
        ):
            errors.append("candidate review identity does not match ResultBundleV2")
        mechanics_reviewer = str(approval.get("reviewer") or "").strip()
        if review.mechanics_reviewer != mechanics_reviewer:
            errors.append("recorded mechanics reviewer is stale or mismatched")
        if review.reviewer.casefold() == mechanics_reviewer.casefold():
            errors.append("candidate reviewer is not independent from mechanics reviewer")
        if review.decision == "approved_candidate" and bundle.verdict != "PASS":
            errors.append("non-PASS result cannot have candidate lifecycle state")
        return {
            "valid": not errors,
            "lifecycle_state": review.lifecycle_state if not errors else "review_required",
            "errors": errors,
            "review": review,
        }

    def lifecycle_state(
        self,
        *,
        candidate_review_path: str | Path,
        result_bundle_path: str | Path,
        config_path: str | Path,
    ) -> str:
        return str(
            self.inspect(
                candidate_review_path=candidate_review_path,
                result_bundle_path=result_bundle_path,
                config_path=config_path,
            )["lifecycle_state"]
        )


def _write_review(path: Path, review: CandidateReviewV1) -> None:
    payload = review.model_dump(mode="json", by_alias=True)
    _atomic_write_bytes(
        path,
        (json.dumps(payload, indent=2, sort_keys=True, allow_nan=False) + "\n").encode("utf-8"),
    )


def _load_yaml(path: Path) -> dict[str, Any]:
    try:
        value = yaml.safe_load(path.read_text(encoding="utf-8"))
    except (OSError, yaml.YAMLError) as exc:
        raise ValueError(f"could not read config: {exc}") from exc
    if not isinstance(value, dict):
        raise ValueError("config must contain a YAML mapping")
    return value


def _load_json_mapping(path: Path, label: str) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"could not read {label}: {exc}") from exc
    if not isinstance(value, dict):
        raise ValueError(f"{label} must contain a JSON object")
    return value


def _aware_datetime(value: datetime | str | None) -> datetime:
    if value is None:
        result = datetime.now(UTC)
    elif isinstance(value, datetime):
        result = value
    else:
        try:
            result = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        except ValueError as exc:
            raise ValueError("reviewed_at must be ISO-8601") from exc
    if result.tzinfo is None or result.utcoffset() is None:
        raise ValueError("reviewed_at must be timezone-aware")
    return result


def _file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _atomic_write_bytes(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with NamedTemporaryFile(dir=path.parent, prefix=f".{path.name}.", suffix=".tmp", delete=False) as handle:
        temporary = Path(handle.name)
        handle.write(data)
        handle.flush()
        os.fsync(handle.fileno())
    try:
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)
