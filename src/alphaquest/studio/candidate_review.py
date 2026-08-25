"""Independent reviewer sign-off for terminal candidate-strategy results."""

from __future__ import annotations

from collections.abc import Mapping
from datetime import UTC, datetime
import hashlib
import json
import os
from pathlib import Path
from tempfile import NamedTemporaryFile
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator
import yaml

from alphaquest.studio.results import (
    ResultBundleV2,
    ResultBundleV3,
    load_result_bundle_v3,
)
from alphaquest.studio.finalization import inspect_finalized_result
from alphaquest.validation.promotion_gate import APPROVAL_SCHEMA, inspect_validation_gate


CANDIDATE_REVIEW_SCHEMA = "alphaquest.candidate-review/v1"
CANDIDATE_REVIEW_FILENAME = "candidate_review.json"


def candidate_review_filename(account_assessment_id: str | None = None) -> str:
    if not account_assessment_id:
        return CANDIDATE_REVIEW_FILENAME
    safe = "".join(
        character if character.isalnum() or character in {"-", "_"} else "_"
        for character in account_assessment_id
    ).strip("_")
    if not safe:
        raise ValueError("account assessment ID cannot produce an empty review filename")
    return f"candidate_review__{safe}.json"


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
    eligibility_basis: Literal[
        "generic_scientific_pass", "destination_specific_pass"
    ] = "generic_scientific_pass"
    scientific_validity_verdict: Literal["PASS", "FAIL", "NEEDS MANUAL REVIEW"] = "PASS"
    generic_objective_verdict: Literal["PASS", "FAIL", "NEEDS MANUAL REVIEW"] = "PASS"
    result_bundle_v3_path: str | None = None
    result_bundle_v3_sha256: str | None = None
    account_assessment_id: str | None = None
    account_profile_id: str | None = None
    account_profile_version: str | None = None
    account_profile_sha256: str | None = None
    account_assessment_manifest_sha256: str | None = None

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

    @model_validator(mode="after")
    def destination_identity_is_complete(self) -> "CandidateReviewV1":
        destination = (
            self.result_bundle_v3_path,
            self.result_bundle_v3_sha256,
            self.account_assessment_id,
            self.account_profile_id,
            self.account_profile_version,
            self.account_profile_sha256,
            self.account_assessment_manifest_sha256,
        )
        if self.eligibility_basis == "destination_specific_pass":
            if any(not str(value or "").strip() for value in destination):
                raise ValueError("destination-specific candidate reviews require complete account bindings")
            if self.scientific_validity_verdict != "PASS":
                raise ValueError("destination-specific candidate review requires scientific-validity PASS")
        elif any(value is not None for value in destination):
            raise ValueError("generic candidate reviews cannot carry destination-specific bindings")
        return self


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
        eligibility_basis: Literal[
            "generic_scientific_pass", "destination_specific_pass"
        ] = "generic_scientific_pass",
        result_bundle_v3_path: str | Path | None = None,
        account_assessment_id: str | None = None,
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
        destination: tuple[ResultBundleV3, Any, Path] | None = None
        if eligibility_basis == "generic_scientific_pass":
            if decision == "approved_candidate" and (
                bundle.scientific_validity_verdict != "PASS" or bundle.verdict != "PASS"
            ):
                raise ValueError(
                    "generic candidate approval requires scientific-validity PASS and generic objective PASS"
                )
        else:
            if result_bundle_v3_path is None or not account_assessment_id:
                raise ValueError(
                    "destination-specific candidate review requires ResultBundleV3 and an account assessment ID"
                )
            destination = _validated_destination_binding(
                result_path=result_path,
                bundle=bundle,
                result_bundle_v3_path=Path(result_bundle_v3_path).resolve(),
                account_assessment_id=account_assessment_id,
            )
            if decision == "approved_candidate" and not destination[1].destination_candidate_eligible:
                raise ValueError(
                    "destination-specific candidate approval requires scientific-validity PASS and account PASS"
                )
            if decision == "approved_candidate":
                _require_primary_declared_destination(cfg, destination[1])

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
            eligibility_basis=eligibility_basis,
            scientific_validity_verdict=bundle.scientific_validity_verdict,
            generic_objective_verdict=bundle.generic_objective_verdict or bundle.verdict,
            result_bundle_v3_path=(str(destination[2]) if destination else None),
            result_bundle_v3_sha256=(_file_sha256(destination[2]) if destination else None),
            account_assessment_id=(destination[1].assessment_id if destination else None),
            account_profile_id=(destination[1].profile_id if destination else None),
            account_profile_version=(destination[1].profile_version if destination else None),
            account_profile_sha256=(destination[1].profile_sha256 if destination else None),
            account_assessment_manifest_sha256=(
                destination[1].manifest_sha256 if destination else None
            ),
        )
        target = (
            Path(output_path).resolve()
            if output_path
            else result_path.parent / candidate_review_filename(account_assessment_id)
        )
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
        if review.scientific_validity_verdict != bundle.scientific_validity_verdict:
            errors.append("candidate review scientific-validity verdict is stale or mismatched")
        if review.generic_objective_verdict != (bundle.generic_objective_verdict or bundle.verdict):
            errors.append("candidate review generic-objective verdict is stale or mismatched")
        if review.eligibility_basis == "generic_scientific_pass":
            if review.decision == "approved_candidate" and (
                bundle.scientific_validity_verdict != "PASS" or bundle.verdict != "PASS"
            ):
                errors.append(
                    "generic candidate lifecycle requires scientific-validity PASS and generic objective PASS"
                )
        else:
            try:
                destination = _validated_destination_binding(
                    result_path=result_path,
                    bundle=bundle,
                    result_bundle_v3_path=Path(str(review.result_bundle_v3_path)).resolve(),
                    account_assessment_id=str(review.account_assessment_id),
                )
                _, binding, v3_path = destination
                if review.result_bundle_v3_sha256 != _file_sha256(v3_path):
                    errors.append("ResultBundleV3 hash is stale or mismatched")
                for label, actual, expected in (
                    ("account profile ID", review.account_profile_id, binding.profile_id),
                    ("account profile version", review.account_profile_version, binding.profile_version),
                    ("account profile hash", review.account_profile_sha256, binding.profile_sha256),
                    (
                        "account assessment manifest hash",
                        review.account_assessment_manifest_sha256,
                        binding.manifest_sha256,
                    ),
                ):
                    if actual != expected:
                        errors.append(f"{label} is stale or mismatched")
                if review.decision == "approved_candidate" and not binding.destination_candidate_eligible:
                    errors.append("destination-specific eligibility is no longer satisfied")
                if review.decision == "approved_candidate":
                    try:
                        _require_primary_declared_destination(_load_yaml(config), binding)
                    except ValueError as exc:
                        errors.append(str(exc))
            except (ValueError, OSError) as exc:
                errors.append(str(exc))
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


def _validated_destination_binding(
    *,
    result_path: Path,
    bundle: ResultBundleV2,
    result_bundle_v3_path: Path,
    account_assessment_id: str,
) -> tuple[ResultBundleV3, Any, Path]:
    bundle_v3 = load_result_bundle_v3(result_bundle_v3_path)
    if bundle_v3.result_bundle_v2_sha256 != _file_sha256(result_path):
        raise ValueError("ResultBundleV3 does not bind the current ResultBundleV2")
    if (bundle_v3.campaign_id, bundle_v3.variant_id, bundle_v3.run_id) != (
        bundle.campaign_id,
        bundle.variant_id,
        bundle.run_id,
    ):
        raise ValueError("ResultBundleV3 identity does not match ResultBundleV2")
    matches = [
        item for item in bundle_v3.account_evaluations if item.assessment_id == account_assessment_id
    ]
    if len(matches) != 1:
        raise ValueError("ResultBundleV3 does not contain exactly one requested account assessment")
    return bundle_v3, matches[0], result_bundle_v3_path


def _require_primary_declared_destination(
    config: Mapping[str, Any],
    binding: Any,
) -> None:
    contract = config.get("destination_benchmark_contract")
    if not isinstance(contract, Mapping):
        return
    recorded_hash = str(
        config.get("destination_benchmark_contract_sha256") or ""
    )
    computed_hash = hashlib.sha256(
        json.dumps(
            contract,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
        ).encode("utf-8")
    ).hexdigest()
    if not recorded_hash or recorded_hash != computed_hash:
        raise ValueError(
            "destination-specific candidate approval requires a current frozen benchmark contract hash"
        )
    if (
        contract.get("scientific_validity_required") is not True
        or contract.get("generic_objective_pass_required") is not False
        or contract.get("approval_scope") != "exact_primary_profile_only"
    ):
        raise ValueError(
            "destination-specific candidate approval benchmark policy is invalid"
        )
    profiles = contract.get("profiles")
    primary = [
        item
        for item in profiles or []
        if isinstance(item, Mapping) and item.get("role") == "primary"
    ]
    if len(primary) != 1:
        raise ValueError(
            "destination-specific candidate approval requires exactly one frozen primary benchmark"
        )
    expected = primary[0]
    if (
        expected.get("profile_id"),
        expected.get("profile_version"),
        expected.get("profile_sha256"),
    ) != (
        binding.profile_id,
        binding.profile_version,
        binding.profile_sha256,
    ):
        raise ValueError(
            "destination-specific candidate approval is limited to the exact frozen primary profile"
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
