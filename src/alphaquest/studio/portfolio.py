"""Governed portfolio, deployment, and post-deployment review services.

This module consumes immutable research evidence; it never runs a campaign,
submits an order, changes an allocation, or retires a strategy.  Portfolio
statistics are computed only from finalized acceptance-OOS trade logs.  Every
published review and decision is hash-bound to the exact inputs inspected at
the time it was written.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, date, datetime
import fcntl
import hashlib
import json
import math
import os
from pathlib import Path
from tempfile import NamedTemporaryFile
from typing import Any, Literal, Mapping, Sequence

import numpy as np
import pandas as pd
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator
import yaml

from alphaquest.studio.candidate_review import CandidateReviewService, CandidateReviewV1
from alphaquest.studio.finalization import inspect_finalized_result
from alphaquest.studio.results import ResultBundleV2


PORTFOLIO_REVIEW_SCHEMA = "alphaquest.portfolio-review/v1"
DEPLOYMENT_DECISION_SCHEMA = "alphaquest.deployment-decision/v1"
MONITORING_EVENT_SCHEMA = "alphaquest.deployment-monitoring-event/v1"
MONITORING_HEAD_SCHEMA = "alphaquest.deployment-monitoring-head/v1"
ACCEPTANCE_TRADE_LOG = "acceptance_oos_test/trade_log.csv"
ACCEPTANCE_SUMMARY = "acceptance_oos_test/acceptance_oos_summary.json"
ACCEPTANCE_SESSION_CALENDAR = "acceptance_oos_test/validation/tradingview_comparison.csv"


@dataclass(frozen=True)
class CandidateEvidencePaths:
    """Current immutable evidence required for one candidate."""

    result_bundle_path: str | Path
    candidate_review_path: str | Path
    config_path: str | Path


@dataclass(frozen=True)
class _CandidateDailyEvidence:
    pnl: pd.Series
    observed_trade_sessions: frozenset[date]


class PortfolioCandidateBindingV1(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, allow_inf_nan=False)

    candidate_key: str
    campaign_id: str
    variant_id: str
    run_id: str
    instrument: str
    initial_balance: float = Field(gt=0)
    result_bundle_path: str
    result_bundle_sha256: str
    finalization_manifest_path: str
    finalization_manifest_sha256: str
    candidate_review_path: str
    candidate_review_sha256: str
    config_path: str
    config_sha256: str
    acceptance_trade_log_path: str
    acceptance_trade_log_sha256: str
    acceptance_summary_path: str
    acceptance_summary_sha256: str
    acceptance_session_calendar_path: str
    acceptance_session_calendar_sha256: str
    coverage_start: date
    coverage_end: date
    evaluation_sessions: int = Field(ge=2)
    observed_trade_sessions: int = Field(ge=1)
    no_trade_sessions: int = Field(ge=0)
    acceptance_trades: int = Field(ge=1)
    eligibility_basis: Literal[
        "generic_scientific_pass", "destination_specific_pass"
    ] = "generic_scientific_pass"
    account_assessment_id: str | None = None
    account_profile_id: str | None = None
    account_profile_version: str | None = None

    @field_validator(
        "candidate_key",
        "campaign_id",
        "variant_id",
        "run_id",
        "instrument",
        "result_bundle_path",
        "result_bundle_sha256",
        "finalization_manifest_path",
        "finalization_manifest_sha256",
        "candidate_review_path",
        "candidate_review_sha256",
        "config_path",
        "config_sha256",
        "acceptance_trade_log_path",
        "acceptance_trade_log_sha256",
        "acceptance_summary_path",
        "acceptance_summary_sha256",
        "acceptance_session_calendar_path",
        "acceptance_session_calendar_sha256",
    )
    @classmethod
    def _nonblank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("value must be non-empty")
        return value.strip()

    @model_validator(mode="after")
    def _ordered_coverage(self) -> "PortfolioCandidateBindingV1":
        if self.coverage_end < self.coverage_start:
            raise ValueError("coverage_end must not precede coverage_start")
        if self.observed_trade_sessions + self.no_trade_sessions != self.evaluation_sessions:
            raise ValueError("candidate session counts do not reconcile")
        account_values = (
            self.account_assessment_id,
            self.account_profile_id,
            self.account_profile_version,
        )
        if self.eligibility_basis == "destination_specific_pass":
            if any(not str(value or "").strip() for value in account_values):
                raise ValueError("destination-specific portfolio candidates require account identity")
        elif any(value is not None for value in account_values):
            raise ValueError("generic portfolio candidates cannot carry account identity")
        return self


class PairwisePortfolioMetricV1(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, allow_inf_nan=False)

    candidate_a: str
    candidate_b: str
    common_sessions: int = Field(ge=1)
    pnl_correlation: float = Field(ge=-1, le=1)
    return_correlation: float = Field(ge=-1, le=1)
    overlapping_loss_days: int = Field(ge=0)
    overlapping_loss_fraction: float = Field(ge=0, le=1)
    overlapping_loss_jaccard: float = Field(ge=0, le=1)


class PortfolioContributionV1(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, allow_inf_nan=False)

    candidate_key: str
    common_period_net_pnl: float
    common_period_max_drawdown: float = Field(ge=0)
    gross_pnl_activity_share: float = Field(ge=0, le=1)
    marginal_combined_max_drawdown: float
    observed_trade_sessions: int = Field(ge=1)
    zero_filled_sessions: int = Field(ge=0)


class PortfolioAnalysisV1(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, allow_inf_nan=False)

    methodology: Literal[
        "intersection_of_hash_bound_acceptance_session_calendars_zero_filled_equal_weight_v1"
    ] = "intersection_of_hash_bound_acceptance_session_calendars_zero_filled_equal_weight_v1"
    minimum_common_sessions: int = Field(ge=2)
    common_coverage_start: date
    common_coverage_end: date
    common_session_count: int = Field(ge=2)
    common_sessions_with_any_trade: int = Field(ge=1)
    common_sessions_with_no_trades: int = Field(ge=0)
    zero_filled_candidate_sessions: int = Field(ge=0)
    pairwise: list[PairwisePortfolioMetricV1]
    contributions: list[PortfolioContributionV1]
    combined_common_period_net_pnl: float
    combined_max_drawdown: float = Field(ge=0)
    combined_equal_weight_max_drawdown_return: float = Field(ge=0)
    maximum_pairwise_absolute_pnl_correlation: float = Field(ge=0, le=1)
    largest_gross_pnl_activity_share: float = Field(ge=0, le=1)
    gross_pnl_activity_hhi: float = Field(gt=0, le=1)


class PortfolioReviewV1(BaseModel):
    """Immutable, verdict-neutral review of two or more candidates."""

    model_config = ConfigDict(
        extra="forbid", populate_by_name=True, strict=True, allow_inf_nan=False
    )

    schema_name: Literal["alphaquest.portfolio-review/v1"] = Field(
        default=PORTFOLIO_REVIEW_SCHEMA,
        alias="schema",
        serialization_alias="schema",
    )
    review_id: str
    generated_at: datetime
    status: Literal["READY_FOR_HUMAN_REVIEW"] = "READY_FOR_HUMAN_REVIEW"
    candidates: list[PortfolioCandidateBindingV1] = Field(min_length=2)
    analysis: PortfolioAnalysisV1
    scientific_disposition: Literal["NEEDS MANUAL REVIEW"] = "NEEDS MANUAL REVIEW"
    automatic_deployment_permitted: Literal[False] = False

    @field_validator("review_id")
    @classmethod
    def _review_id(cls, value: str) -> str:
        if len(value) != 64 or any(character not in "0123456789abcdef" for character in value):
            raise ValueError("review_id must be a lowercase SHA-256 digest")
        return value

    @field_validator("generated_at")
    @classmethod
    def _aware_datetime(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("generated_at must be timezone-aware")
        return value

    @model_validator(mode="after")
    def _candidate_identity_is_unique(self) -> "PortfolioReviewV1":
        keys = [candidate.candidate_key for candidate in self.candidates]
        if len(set(keys)) != len(keys):
            raise ValueError("portfolio candidates must be unique")
        return self


class PortfolioReviewService:
    """Build and revalidate immutable multi-candidate OOS reviews."""

    def create(
        self,
        *,
        candidates: Sequence[CandidateEvidencePaths | Mapping[str, Any]],
        output_dir: str | Path,
        minimum_common_sessions: int = 20,
        generated_at: datetime | str | None = None,
    ) -> tuple[PortfolioReviewV1, Path]:
        if len(candidates) < 2:
            raise ValueError("portfolio review requires at least two finalized candidates")
        if minimum_common_sessions < 2:
            raise ValueError("minimum_common_sessions must be at least 2")
        resolved = [_coerce_candidate_paths(item) for item in candidates]
        bindings, daily = _load_current_candidates(resolved)
        analysis = _analyze_portfolio(
            bindings,
            daily,
            minimum_common_sessions=minimum_common_sessions,
        )
        timestamp = _aware_datetime(generated_at)
        review_id = _portfolio_review_id(bindings, analysis, timestamp)
        review = PortfolioReviewV1(
            review_id=review_id,
            generated_at=timestamp,
            candidates=bindings,
            analysis=analysis,
        )
        target = Path(output_dir).resolve() / f"portfolio_review_{review_id}.json"
        _write_new_model(target, review)
        return review, target

    def inspect(self, review_path: str | Path) -> dict[str, Any]:
        errors: list[str] = []
        path = Path(review_path).resolve()
        try:
            review = PortfolioReviewV1.model_validate_json(path.read_text(encoding="utf-8"))
        except (OSError, ValueError) as exc:
            return {"valid": False, "status": "NEEDS MANUAL REVIEW", "errors": [str(exc)]}

        candidates = [
            CandidateEvidencePaths(
                result_bundle_path=item.result_bundle_path,
                candidate_review_path=item.candidate_review_path,
                config_path=item.config_path,
            )
            for item in review.candidates
        ]
        try:
            bindings, daily = _load_current_candidates(candidates)
            analysis = _analyze_portfolio(
                bindings,
                daily,
                minimum_common_sessions=review.analysis.minimum_common_sessions,
            )
        except (OSError, ValueError) as exc:
            return {
                "valid": False,
                "status": "NEEDS MANUAL REVIEW",
                "errors": [str(exc)],
                "review": review,
            }
        if bindings != review.candidates:
            errors.append("portfolio candidate evidence or hashes are stale or mismatched")
        if analysis != review.analysis:
            errors.append("portfolio analysis no longer matches current immutable inputs")
        expected_id = _portfolio_review_id(review.candidates, review.analysis, review.generated_at)
        if review.review_id != expected_id:
            errors.append("portfolio review_id does not match its bound inputs")
        return {
            "valid": not errors,
            "status": review.status if not errors else "NEEDS MANUAL REVIEW",
            "errors": errors,
            "review": review,
            "review_sha256": _file_sha256(path),
        }


@dataclass(frozen=True)
class DeploymentCandidateRequest:
    """One requested manual allocation and its governed source evidence."""

    result_bundle_path: str | Path
    candidate_review_path: str | Path
    config_path: str | Path
    attempt_id: str
    requested_contracts: int


class AccountContractLimitsV1(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, allow_inf_nan=False)

    account_label: str
    maximum_total_contracts: int = Field(ge=1)
    maximum_contracts_per_candidate: int = Field(ge=1)
    instrument_contract_limits: dict[str, int] = Field(min_length=1)
    maximum_daily_loss_currency: float = Field(gt=0)
    maximum_total_drawdown_currency: float = Field(gt=0)

    @field_validator("account_label")
    @classmethod
    def _account_label(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("account_label must be non-empty")
        return value.strip()

    @field_validator("instrument_contract_limits")
    @classmethod
    def _instrument_limits(cls, value: dict[str, int]) -> dict[str, int]:
        cleaned: dict[str, int] = {}
        for instrument, limit in value.items():
            name = str(instrument).strip()
            if not name or isinstance(limit, bool) or int(limit) < 1:
                raise ValueError("instrument contract limits require non-empty names and positive integers")
            cleaned[name] = int(limit)
        return cleaned


class MonitoringThresholdsV1(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, allow_inf_nan=False)

    daily_loss_alert_currency: float = Field(gt=0)
    drawdown_alert_currency: float = Field(gt=0)
    retirement_review_drawdown_currency: float = Field(gt=0)
    losing_streak_alert: int = Field(ge=1)
    retirement_review_losing_streak: int = Field(ge=1)
    rolling_window_trades: int = Field(ge=2)
    minimum_rolling_expectancy_currency: float
    maximum_average_slippage_per_contract: float = Field(ge=0)

    @model_validator(mode="after")
    def _retirement_thresholds_follow_alerts(self) -> "MonitoringThresholdsV1":
        if self.retirement_review_drawdown_currency < self.drawdown_alert_currency:
            raise ValueError("retirement-review drawdown cannot be below the alert threshold")
        if self.retirement_review_losing_streak < self.losing_streak_alert:
            raise ValueError("retirement-review losing streak cannot be below the alert threshold")
        return self


class ForwardIncubationBindingV1(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    status: Literal["ELIGIBLE_FOR_REVIEW"]
    plan_path: str
    plan_sha256: str
    events_path: str
    events_sha256: str
    event_count: int = Field(ge=0)
    last_event_sha256: str
    governed_config_hash: str
    research_objectives_sha256: str


class DeploymentCandidateBindingV1(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    candidate: PortfolioCandidateBindingV1
    attempt_id: str
    requested_contracts: int = Field(ge=1)
    forward_incubation: ForwardIncubationBindingV1


class DeploymentDecisionV1(BaseModel):
    """Human decision record; approval only authorizes a separate manual action."""

    model_config = ConfigDict(
        extra="forbid", populate_by_name=True, strict=True, allow_inf_nan=False
    )

    schema_name: Literal["alphaquest.deployment-decision/v1"] = Field(
        default=DEPLOYMENT_DECISION_SCHEMA,
        alias="schema",
        serialization_alias="schema",
    )
    decision_id: str
    decided_at: datetime
    reviewer: str
    decision: Literal["APPROVE", "REJECT", "NEEDS MANUAL REVIEW"]
    decision_notes: str
    candidates: list[DeploymentCandidateBindingV1] = Field(min_length=1)
    portfolio_review_path: str | None = None
    portfolio_review_sha256: str | None = None
    account_limits: AccountContractLimitsV1
    rollback_criteria: list[str] = Field(min_length=1)
    kill_criteria: list[str] = Field(min_length=1)
    monitoring_thresholds: MonitoringThresholdsV1
    checklist_status: Literal["ELIGIBLE_FOR_HUMAN_DECISION", "BLOCKED"]
    checklist_blockers: list[str]
    deployment_state: Literal[
        "APPROVED_FOR_MANUAL_DEPLOYMENT", "REJECTED", "NEEDS MANUAL REVIEW"
    ]
    order_submission_permitted: Literal[False] = False
    automatic_retirement_permitted: Literal[False] = False
    execution_capability: Literal["none"] = "none"

    @field_validator("decision_id")
    @classmethod
    def _decision_id(cls, value: str) -> str:
        if len(value) != 64 or any(character not in "0123456789abcdef" for character in value):
            raise ValueError("decision_id must be a lowercase SHA-256 digest")
        return value

    @field_validator("decided_at")
    @classmethod
    def _decision_time(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("decided_at must be timezone-aware")
        return value

    @field_validator("reviewer", "decision_notes")
    @classmethod
    def _decision_text(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("reviewer and decision notes must be non-empty")
        return value.strip()

    @field_validator("rollback_criteria", "kill_criteria")
    @classmethod
    def _criteria(cls, values: list[str]) -> list[str]:
        cleaned = [str(item).strip() for item in values]
        if any(not item for item in cleaned):
            raise ValueError("rollback and kill criteria must be non-empty")
        if len(set(cleaned)) != len(cleaned):
            raise ValueError("rollback and kill criteria must be unique")
        return cleaned

    @model_validator(mode="after")
    def _decision_consistency(self) -> "DeploymentDecisionV1":
        if self.checklist_status == "ELIGIBLE_FOR_HUMAN_DECISION" and self.checklist_blockers:
            raise ValueError("eligible checklist cannot contain blockers")
        if self.checklist_status == "BLOCKED" and not self.checklist_blockers:
            raise ValueError("blocked checklist requires blockers")
        if self.decision == "APPROVE":
            if self.checklist_status != "ELIGIBLE_FOR_HUMAN_DECISION":
                raise ValueError("APPROVE requires every governed checklist item")
            if self.deployment_state != "APPROVED_FOR_MANUAL_DEPLOYMENT":
                raise ValueError("APPROVE has an inconsistent deployment state")
        elif self.decision == "REJECT" and self.deployment_state != "REJECTED":
            raise ValueError("REJECT has an inconsistent deployment state")
        elif self.decision == "NEEDS MANUAL REVIEW" and self.deployment_state != "NEEDS MANUAL REVIEW":
            raise ValueError("manual-review decision has an inconsistent deployment state")
        if len(self.candidates) > 1 and not self.portfolio_review_path:
            raise ValueError("multi-candidate deployment must bind a portfolio review")
        if bool(self.portfolio_review_path) != bool(self.portfolio_review_sha256):
            raise ValueError("portfolio review path and hash must be supplied together")
        return self


class DeploymentDecisionService:
    """Validate the deployment checklist and record an explicit human decision."""

    def __init__(self, project_root: str | Path = ".") -> None:
        self.project_root = Path(project_root).resolve()

    def decide(
        self,
        *,
        candidates: Sequence[DeploymentCandidateRequest | Mapping[str, Any]],
        account_limits: AccountContractLimitsV1 | Mapping[str, Any],
        rollback_criteria: Sequence[str],
        kill_criteria: Sequence[str],
        monitoring_thresholds: MonitoringThresholdsV1 | Mapping[str, Any],
        reviewer: str,
        decision: Literal["APPROVE", "REJECT", "NEEDS MANUAL REVIEW"],
        decision_notes: str,
        output_dir: str | Path,
        portfolio_review_path: str | Path | None = None,
        decided_at: datetime | str | None = None,
    ) -> tuple[DeploymentDecisionV1, Path]:
        if not candidates:
            raise ValueError("deployment decision requires at least one candidate")
        limits = (
            account_limits
            if isinstance(account_limits, AccountContractLimitsV1)
            else AccountContractLimitsV1.model_validate(account_limits)
        )
        thresholds = (
            monitoring_thresholds
            if isinstance(monitoring_thresholds, MonitoringThresholdsV1)
            else MonitoringThresholdsV1.model_validate(monitoring_thresholds)
        )
        requests = [_coerce_deployment_request(item) for item in candidates]
        bindings, blockers = self._current_bindings(requests, limits)
        portfolio_path_value: str | None = None
        portfolio_hash: str | None = None
        if len(bindings) > 1:
            if portfolio_review_path is None:
                blockers.append("multiple candidates require a current hash-valid portfolio review")
            else:
                portfolio_path = Path(portfolio_review_path).resolve()
                portfolio_report = PortfolioReviewService().inspect(portfolio_path)
                if not portfolio_report.get("valid"):
                    blockers.extend(
                        "portfolio review: " + str(item)
                        for item in portfolio_report.get("errors") or ["verification failed"]
                    )
                else:
                    portfolio = portfolio_report.get("review")
                    expected = {
                        item.candidate.result_bundle_sha256 for item in bindings
                    }
                    actual = (
                        {item.result_bundle_sha256 for item in portfolio.candidates}
                        if isinstance(portfolio, PortfolioReviewV1)
                        else set()
                    )
                    if actual != expected:
                        blockers.append("portfolio review does not bind the exact deployment candidates")
                    portfolio_path_value = str(portfolio_path)
                    portfolio_hash = _file_sha256(portfolio_path)
        elif portfolio_review_path is not None:
            portfolio_path = Path(portfolio_review_path).resolve()
            portfolio_report = PortfolioReviewService().inspect(portfolio_path)
            if not portfolio_report.get("valid"):
                blockers.extend(
                    "portfolio review: " + str(item)
                    for item in portfolio_report.get("errors") or ["verification failed"]
                )
            else:
                portfolio_path_value = str(portfolio_path)
                portfolio_hash = _file_sha256(portfolio_path)

        blockers.extend(_threshold_limit_blockers(thresholds, limits))
        blockers = sorted(set(blockers))
        checklist_status = "BLOCKED" if blockers else "ELIGIBLE_FOR_HUMAN_DECISION"
        if decision == "APPROVE" and blockers:
            raise ValueError("deployment approval is blocked: " + "; ".join(blockers))
        state = {
            "APPROVE": "APPROVED_FOR_MANUAL_DEPLOYMENT",
            "REJECT": "REJECTED",
            "NEEDS MANUAL REVIEW": "NEEDS MANUAL REVIEW",
        }[decision]
        timestamp = _aware_datetime(decided_at)
        decision_id = _deployment_decision_id(
            bindings=bindings,
            portfolio_review_sha256=portfolio_hash,
            limits=limits,
            rollback_criteria=list(rollback_criteria),
            kill_criteria=list(kill_criteria),
            monitoring_thresholds=thresholds,
            reviewer=reviewer,
            decision=decision,
            notes=decision_notes,
            decided_at=timestamp,
        )
        record = DeploymentDecisionV1(
            decision_id=decision_id,
            decided_at=timestamp,
            reviewer=reviewer,
            decision=decision,
            decision_notes=decision_notes,
            candidates=bindings,
            portfolio_review_path=portfolio_path_value,
            portfolio_review_sha256=portfolio_hash,
            account_limits=limits,
            rollback_criteria=list(rollback_criteria),
            kill_criteria=list(kill_criteria),
            monitoring_thresholds=thresholds,
            checklist_status=checklist_status,
            checklist_blockers=blockers,
            deployment_state=state,
        )
        target = Path(output_dir).resolve() / f"deployment_decision_{decision_id}.json"
        _write_new_model(target, record)
        return record, target

    def inspect(self, decision_path: str | Path) -> dict[str, Any]:
        path = Path(decision_path).resolve()
        try:
            record = DeploymentDecisionV1.model_validate_json(path.read_text(encoding="utf-8"))
        except (OSError, ValueError) as exc:
            return {"valid": False, "status": "NEEDS MANUAL REVIEW", "errors": [str(exc)]}
        requests = [
            DeploymentCandidateRequest(
                result_bundle_path=item.candidate.result_bundle_path,
                candidate_review_path=item.candidate.candidate_review_path,
                config_path=item.candidate.config_path,
                attempt_id=item.attempt_id,
                requested_contracts=item.requested_contracts,
            )
            for item in record.candidates
        ]
        bindings, blockers = self._current_bindings(requests, record.account_limits)
        if bindings != record.candidates:
            blockers.append("deployment candidate or incubation bindings are stale or mismatched")
        portfolio_hash = None
        if record.portfolio_review_path:
            portfolio_path = Path(record.portfolio_review_path).resolve()
            portfolio_report = PortfolioReviewService().inspect(portfolio_path)
            if not portfolio_report.get("valid"):
                blockers.extend(
                    "portfolio review: " + str(item)
                    for item in portfolio_report.get("errors") or ["verification failed"]
                )
            elif _file_sha256(portfolio_path) != record.portfolio_review_sha256:
                blockers.append("portfolio review hash is stale or mismatched")
            else:
                portfolio_hash = record.portfolio_review_sha256
        elif len(record.candidates) > 1:
            blockers.append("multi-candidate deployment no longer has a portfolio review")
        blockers.extend(_threshold_limit_blockers(record.monitoring_thresholds, record.account_limits))
        expected_id = _deployment_decision_id(
            bindings=record.candidates,
            portfolio_review_sha256=record.portfolio_review_sha256,
            limits=record.account_limits,
            rollback_criteria=record.rollback_criteria,
            kill_criteria=record.kill_criteria,
            monitoring_thresholds=record.monitoring_thresholds,
            reviewer=record.reviewer,
            decision=record.decision,
            notes=record.decision_notes,
            decided_at=record.decided_at,
        )
        if record.decision_id != expected_id:
            blockers.append("deployment decision_id does not match its bound inputs")
        blockers = sorted(set(blockers))
        return {
            "valid": not blockers,
            "status": record.deployment_state if not blockers else "NEEDS MANUAL REVIEW",
            "errors": blockers,
            "decision": record,
            "decision_sha256": _file_sha256(path),
            "portfolio_review_sha256": portfolio_hash,
            "order_submission_permitted": False,
        }

    def _current_bindings(
        self,
        requests: Sequence[DeploymentCandidateRequest],
        limits: AccountContractLimitsV1,
    ) -> tuple[list[DeploymentCandidateBindingV1], list[str]]:
        blockers: list[str] = []
        bindings: list[DeploymentCandidateBindingV1] = []
        seen: set[str] = set()
        total_contracts = 0
        by_instrument: dict[str, int] = {}
        for request in requests:
            try:
                candidate, _ = _load_current_candidate(
                    CandidateEvidencePaths(
                        result_bundle_path=request.result_bundle_path,
                        candidate_review_path=request.candidate_review_path,
                        config_path=request.config_path,
                    )
                )
            except (OSError, ValueError) as exc:
                blockers.append(str(exc))
                continue
            if candidate.candidate_key in seen:
                blockers.append(f"duplicate deployment candidate: {candidate.candidate_key}")
                continue
            seen.add(candidate.candidate_key)
            if isinstance(request.requested_contracts, bool) or request.requested_contracts < 1:
                blockers.append(f"{candidate.candidate_key} requested contracts must be positive")
                continue
            total_contracts += request.requested_contracts
            by_instrument[candidate.instrument] = (
                by_instrument.get(candidate.instrument, 0) + request.requested_contracts
            )
            if request.requested_contracts > limits.maximum_contracts_per_candidate:
                blockers.append(
                    f"{candidate.candidate_key} exceeds maximum contracts per candidate"
                )
            try:
                forward = _current_forward_binding(
                    project_root=self.project_root,
                    candidate=candidate,
                    attempt_id=request.attempt_id,
                )
            except (OSError, ValueError) as exc:
                blockers.append(f"{candidate.candidate_key} forward incubation: {exc}")
                continue
            bindings.append(
                DeploymentCandidateBindingV1(
                    candidate=candidate,
                    attempt_id=request.attempt_id,
                    requested_contracts=request.requested_contracts,
                    forward_incubation=forward,
                )
            )
        if total_contracts > limits.maximum_total_contracts:
            blockers.append("requested allocation exceeds maximum total contracts")
        for instrument, count in sorted(by_instrument.items()):
            limit = limits.instrument_contract_limits.get(instrument)
            if limit is None:
                blockers.append(f"instrument {instrument} is not allowed by account limits")
            elif count > limit:
                blockers.append(f"instrument {instrument} exceeds its contract limit")
        bindings.sort(key=lambda item: item.candidate.candidate_key)
        return bindings, blockers


def _current_forward_binding(
    *,
    project_root: Path,
    candidate: PortfolioCandidateBindingV1,
    attempt_id: str,
) -> ForwardIncubationBindingV1:
    from alphaquest.studio.forward_incubation import ForwardIncubationService

    service = ForwardIncubationService(project_root)
    detail = service.detail(candidate.campaign_id, candidate.variant_id, attempt_id)
    errors = list(detail.get("errors") or [])
    if detail.get("schema") != "alphaquest.forward-incubation-detail/v1":
        errors.append("unexpected forward-incubation detail schema")
    if detail.get("status") != "ELIGIBLE_FOR_REVIEW":
        errors.append("status is not ELIGIBLE_FOR_REVIEW")
    if detail.get("automatic_pass_permitted") is not False:
        errors.append("forward incubation must explicitly forbid automatic pass")
    plan = detail.get("plan")
    if not isinstance(plan, Mapping):
        errors.append("forward-incubation plan is unavailable")
        plan = {}
    expected_identity = (
        candidate.campaign_id,
        candidate.variant_id,
        attempt_id,
        candidate.run_id,
    )
    actual_identity = (
        str(plan.get("campaign_id") or ""),
        str(plan.get("variant_id") or ""),
        str(plan.get("attempt_id") or ""),
        str(plan.get("run_id") or ""),
    )
    if actual_identity != expected_identity:
        errors.append("forward-incubation candidate identity is stale or mismatched")
    if str(plan.get("result_bundle_sha256") or "") != candidate.result_bundle_sha256:
        errors.append("forward-incubation result-bundle hash is stale or mismatched")
    if str(plan.get("candidate_review_sha256") or "") != candidate.candidate_review_sha256:
        errors.append("forward-incubation candidate-review hash is stale or mismatched")
    if str(plan.get("config_sha256") or "") != candidate.config_sha256:
        errors.append("forward-incubation config hash is stale or mismatched")
    config = _read_yaml_mapping(Path(candidate.config_path))
    objectives_hash = str(config.get("research_objectives_sha256") or "")
    if not objectives_hash or str(plan.get("research_objectives_sha256") or "") != objectives_hash:
        errors.append("forward-incubation research-objectives hash is stale or mismatched")
    review = CandidateReviewV1.model_validate(
        _read_json_mapping(Path(candidate.candidate_review_path), "candidate review")
    )
    if str(plan.get("governed_config_hash") or "") != review.config_hash:
        errors.append("forward-incubation governed config hash is stale or mismatched")
    required_detail = (
        "plan_path",
        "plan_sha256",
        "events_path",
        "events_sha256",
        "last_event_sha256",
    )
    for field in required_detail:
        if not str(detail.get(field) or ""):
            errors.append(f"forward-incubation detail is missing {field}")
    if errors:
        raise ValueError("; ".join(str(item) for item in errors))
    return ForwardIncubationBindingV1(
        status="ELIGIBLE_FOR_REVIEW",
        plan_path=str(detail["plan_path"]),
        plan_sha256=str(detail["plan_sha256"]),
        events_path=str(detail["events_path"]),
        events_sha256=str(detail["events_sha256"]),
        event_count=int(detail.get("event_count") or 0),
        last_event_sha256=str(detail["last_event_sha256"]),
        governed_config_hash=str(plan["governed_config_hash"]),
        research_objectives_sha256=objectives_hash,
    )


def _coerce_deployment_request(
    value: DeploymentCandidateRequest | Mapping[str, Any],
) -> DeploymentCandidateRequest:
    if isinstance(value, DeploymentCandidateRequest):
        return value
    if not isinstance(value, Mapping):
        raise ValueError("deployment candidate must be a mapping or DeploymentCandidateRequest")
    required = (
        "result_bundle_path",
        "candidate_review_path",
        "config_path",
        "attempt_id",
        "requested_contracts",
    )
    missing = [field for field in required if field not in value]
    if missing:
        raise ValueError("deployment candidate is missing: " + ", ".join(missing))
    return DeploymentCandidateRequest(**{field: value[field] for field in required})


def _threshold_limit_blockers(
    thresholds: MonitoringThresholdsV1,
    limits: AccountContractLimitsV1,
) -> list[str]:
    blockers: list[str] = []
    if thresholds.daily_loss_alert_currency > limits.maximum_daily_loss_currency:
        blockers.append("daily-loss monitoring alert exceeds the hard account limit")
    if thresholds.drawdown_alert_currency > limits.maximum_total_drawdown_currency:
        blockers.append("drawdown monitoring alert exceeds the hard account limit")
    if thresholds.retirement_review_drawdown_currency > limits.maximum_total_drawdown_currency:
        blockers.append("retirement-review drawdown exceeds the hard account limit")
    return blockers


def _deployment_decision_id(
    *,
    bindings: Sequence[DeploymentCandidateBindingV1],
    portfolio_review_sha256: str | None,
    limits: AccountContractLimitsV1,
    rollback_criteria: list[str],
    kill_criteria: list[str],
    monitoring_thresholds: MonitoringThresholdsV1,
    reviewer: str,
    decision: str,
    notes: str,
    decided_at: datetime,
) -> str:
    return _sha256_json(
        {
            "schema": DEPLOYMENT_DECISION_SCHEMA,
            "candidates": [item.model_dump(mode="json") for item in bindings],
            "portfolio_review_sha256": portfolio_review_sha256,
            "account_limits": limits.model_dump(mode="json"),
            "rollback_criteria": rollback_criteria,
            "kill_criteria": kill_criteria,
            "monitoring_thresholds": monitoring_thresholds.model_dump(mode="json"),
            "reviewer": reviewer,
            "decision": decision,
            "notes": notes,
            "decided_at": decided_at.isoformat(),
        }
    )


class MonitoringDailyObservationV1(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, allow_inf_nan=False)

    session_date: date
    net_pnl: float
    trades: int = Field(ge=1)
    slippage_cost: float = Field(ge=0)
    contract_sides: int = Field(ge=1)


class MonitoringMetricsV1(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, allow_inf_nan=False)

    cumulative_net_pnl: float
    rolling_net_pnl: float
    rolling_trade_count: int = Field(ge=1)
    rolling_window_complete: bool
    maximum_drawdown: float = Field(ge=0)
    worst_daily_pnl: float
    current_losing_session_streak: int = Field(ge=0)
    average_slippage_per_contract_side: float = Field(ge=0)
    observed_sessions: int = Field(ge=1)
    observed_trades: int = Field(ge=1)


class DeploymentMonitoringEventV1(BaseModel):
    """One source-bound, append-only monitoring observation."""

    model_config = ConfigDict(
        extra="forbid", populate_by_name=True, strict=True, allow_inf_nan=False
    )

    schema_name: Literal["alphaquest.deployment-monitoring-event/v1"] = Field(
        default=MONITORING_EVENT_SCHEMA,
        alias="schema",
        serialization_alias="schema",
    )
    sequence: int = Field(ge=1)
    recorded_at: datetime
    period_start: date
    period_end: date
    recorded_by: str
    notes: str
    deployment_decision_sha256: str
    previous_event_sha256: str
    event_sha256: str
    source_trade_log_path: str
    source_trade_log_sha256: str
    daily_observations: list[MonitoringDailyObservationV1] = Field(min_length=1)
    metrics: MonitoringMetricsV1
    triggered_alerts: list[str]
    status: Literal["HEALTHY", "ALERT", "RETIREMENT_REVIEW"]
    order_submission_permitted: Literal[False] = False
    automatic_retirement_permitted: Literal[False] = False

    @field_validator("recorded_at")
    @classmethod
    def _monitoring_time(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("recorded_at must be timezone-aware")
        return value

    @field_validator(
        "recorded_by",
        "notes",
        "deployment_decision_sha256",
        "previous_event_sha256",
        "event_sha256",
        "source_trade_log_path",
        "source_trade_log_sha256",
    )
    @classmethod
    def _monitoring_text(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("monitoring identity and notes fields must be non-empty")
        return value.strip()

    @model_validator(mode="after")
    def _monitoring_shape(self) -> "DeploymentMonitoringEventV1":
        if self.period_end < self.period_start:
            raise ValueError("monitoring period_end must not precede period_start")
        if self.daily_observations[0].session_date != self.period_start:
            raise ValueError("monitoring period_start does not match daily observations")
        if self.daily_observations[-1].session_date != self.period_end:
            raise ValueError("monitoring period_end does not match daily observations")
        dates = [item.session_date for item in self.daily_observations]
        if dates != sorted(set(dates)):
            raise ValueError("monitoring daily observations must be unique and chronological")
        if self.status == "HEALTHY" and self.triggered_alerts:
            raise ValueError("HEALTHY monitoring event cannot contain alerts")
        if self.status != "HEALTHY" and not self.triggered_alerts:
            raise ValueError("non-healthy monitoring event requires triggered alerts")
        return self


class DeploymentMonitoringService:
    """Append and verify post-decision observations without automated actions."""

    def __init__(
        self,
        *,
        project_root: str | Path,
        deployment_decision_path: str | Path,
        output_root: str | Path | None = None,
    ) -> None:
        self.project_root = Path(project_root).resolve()
        self.decision_path = Path(deployment_decision_path).resolve()
        decision = DeploymentDecisionV1.model_validate_json(
            self.decision_path.read_text(encoding="utf-8")
        )
        root = Path(output_root).resolve() if output_root else self.decision_path.parent / "monitoring"
        self.record_dir = root / decision.decision_id
        self.events_path = self.record_dir / "events.jsonl"
        self.head_path = self.record_dir / "events.head.json"

    def append(
        self,
        *,
        source_trade_log_path: str | Path,
        recorded_by: str,
        notes: str,
        recorded_at: datetime | str | None = None,
    ) -> dict[str, Any]:
        decision_report = DeploymentDecisionService(self.project_root).inspect(self.decision_path)
        decision = decision_report.get("decision")
        if not decision_report.get("valid") or not isinstance(decision, DeploymentDecisionV1):
            raise ValueError(
                "monitoring requires a current hash-valid deployment decision: "
                + "; ".join(str(item) for item in decision_report.get("errors") or [])
            )
        if decision.deployment_state != "APPROVED_FOR_MANUAL_DEPLOYMENT":
            raise ValueError("monitoring requires an approved manual-deployment decision")
        actor = recorded_by.strip()
        note = notes.strip()
        if not actor or not note:
            raise ValueError("recorded_by and notes are required")
        source_path = Path(source_trade_log_path).resolve()
        if not source_path.is_file() or source_path.suffix.casefold() != ".csv":
            raise ValueError("monitoring source evidence must be an available CSV file")
        decision_sha256 = _file_sha256(self.decision_path)

        self.record_dir.mkdir(parents=True, exist_ok=True)
        with self.events_path.open("a+b") as handle:
            fcntl.flock(handle.fileno(), fcntl.LOCK_EX)
            handle.seek(0)
            raw = handle.read()
            events, errors = _parse_monitoring_events(
                raw,
                decision=decision,
                decision_sha256=decision_sha256,
                verify_sources=True,
            )
            errors.extend(_monitoring_head_errors(self.head_path, raw, events, decision_sha256))
            if errors:
                raise RuntimeError("cannot append to invalid monitoring evidence: " + "; ".join(errors))
            governed_source = _copy_monitoring_source(
                source_path,
                destination_root=self.record_dir / "evidence",
                sequence=len(events) + 1,
            )
            observations = _read_monitoring_trade_log(governed_source)
            if events and observations[0].session_date <= events[-1].period_end:
                raise ValueError("monitoring periods must be chronological and non-overlapping")
            timestamp = _aware_datetime(recorded_at)
            if events and timestamp <= events[-1].recorded_at:
                raise ValueError("monitoring recorded_at timestamps must strictly increase")
            if observations[-1].session_date > timestamp.date():
                raise ValueError("monitoring evidence cannot contain future session dates")
            all_observations = [
                point for event in events for point in event.daily_observations
            ] + observations
            metrics, alerts, status = _monitoring_evaluation(
                all_observations,
                decision.monitoring_thresholds,
            )
            payload: dict[str, Any] = {
                "schema": MONITORING_EVENT_SCHEMA,
                "sequence": len(events) + 1,
                "recorded_at": timestamp.isoformat(),
                "period_start": observations[0].session_date.isoformat(),
                "period_end": observations[-1].session_date.isoformat(),
                "recorded_by": actor,
                "notes": note,
                "deployment_decision_sha256": decision_sha256,
                "previous_event_sha256": events[-1].event_sha256 if events else decision_sha256,
                "event_sha256": "0" * 64,
                "source_trade_log_path": str(governed_source),
                "source_trade_log_sha256": _file_sha256(governed_source),
                "daily_observations": [item.model_dump(mode="json") for item in observations],
                "metrics": metrics.model_dump(mode="json"),
                "triggered_alerts": alerts,
                "status": status,
                "order_submission_permitted": False,
                "automatic_retirement_permitted": False,
            }
            normalized = DeploymentMonitoringEventV1.model_validate_json(
                json.dumps(payload, allow_nan=False)
            ).model_dump(
                mode="json", by_alias=True
            )
            normalized["event_sha256"] = _monitoring_event_sha256(normalized)
            event = DeploymentMonitoringEventV1.model_validate_json(
                json.dumps(normalized, allow_nan=False)
            )
            line = (
                json.dumps(
                    event.model_dump(mode="json", by_alias=True),
                    sort_keys=True,
                    separators=(",", ":"),
                    allow_nan=False,
                ).encode("utf-8")
                + b"\n"
            )
            handle.seek(0, os.SEEK_END)
            handle.write(line)
            handle.flush()
            os.fsync(handle.fileno())
            updated = raw + line
            _write_monitoring_head(
                self.head_path,
                updated,
                event_count=len(events) + 1,
                last_event_sha256=event.event_sha256,
                decision_sha256=decision_sha256,
            )
            fcntl.flock(handle.fileno(), fcntl.LOCK_UN)
        return self.detail()

    def detail(self) -> dict[str, Any]:
        decision_report = DeploymentDecisionService(self.project_root).inspect(self.decision_path)
        decision = decision_report.get("decision")
        errors = list(decision_report.get("errors") or [])
        if not isinstance(decision, DeploymentDecisionV1):
            return {
                "schema": "alphaquest.deployment-monitoring-detail/v1",
                "status": "NEEDS MANUAL REVIEW",
                "errors": errors or ["deployment decision is unavailable"],
                "events": [],
                "order_submission_permitted": False,
                "automatic_retirement_permitted": False,
            }
        decision_sha256 = _file_sha256(self.decision_path)
        try:
            raw = self.events_path.read_bytes()
        except OSError as exc:
            raw = b""
            errors.append(f"monitoring event journal is unavailable: {exc}")
        events, event_errors = _parse_monitoring_events(
            raw,
            decision=decision,
            decision_sha256=decision_sha256,
            verify_sources=True,
        )
        errors.extend(event_errors)
        errors.extend(_monitoring_head_errors(self.head_path, raw, events, decision_sha256))
        status = "NEEDS MANUAL REVIEW" if errors or not events else events[-1].status
        return {
            "schema": "alphaquest.deployment-monitoring-detail/v1",
            "decision_id": decision.decision_id,
            "deployment_decision_sha256": decision_sha256,
            "status": status,
            "metrics": events[-1].metrics.model_dump(mode="json") if events else None,
            "triggered_alerts": events[-1].triggered_alerts if events else [],
            "event_count": len(events),
            "events": [event.model_dump(mode="json", by_alias=True) for event in events],
            "errors": errors,
            "order_submission_permitted": False,
            "automatic_retirement_permitted": False,
        }


def _read_monitoring_trade_log(path: Path) -> list[MonitoringDailyObservationV1]:
    try:
        frame = pd.read_csv(path)
    except Exception as exc:
        raise ValueError(f"could not read monitoring trade log: {exc}") from exc
    required = {"session_date", "net_pnl", "slippage_cost", "contracts"}
    missing = sorted(required - set(frame.columns))
    if missing:
        raise ValueError("monitoring trade log is missing required columns: " + ", ".join(missing))
    if frame.empty:
        raise ValueError("monitoring trade log contains no trades")
    dates = pd.to_datetime(frame["session_date"], errors="coerce")
    pnl = pd.to_numeric(frame["net_pnl"], errors="coerce")
    slippage = pd.to_numeric(frame["slippage_cost"], errors="coerce")
    contracts = pd.to_numeric(frame["contracts"], errors="coerce")
    if dates.isna().any():
        raise ValueError("monitoring trade log contains invalid session_date values")
    for label, values in (("net_pnl", pnl), ("slippage_cost", slippage), ("contracts", contracts)):
        if values.isna().any() or not np.isfinite(values.to_numpy(dtype=float)).all():
            raise ValueError(f"monitoring trade log contains invalid {label} values")
    if (slippage < 0).any() or (contracts <= 0).any() or not np.equal(contracts, np.floor(contracts)).all():
        raise ValueError("monitoring slippage must be non-negative and contracts must be positive integers")
    normalized = pd.DataFrame(
        {
            "session_date": dates.dt.date,
            "net_pnl": pnl.astype(float),
            "slippage_cost": slippage.astype(float),
            "contracts": contracts.astype(int),
        }
    )
    observations: list[MonitoringDailyObservationV1] = []
    for session_date, group in normalized.groupby("session_date", sort=True):
        observations.append(
            MonitoringDailyObservationV1(
                session_date=session_date,
                net_pnl=float(group["net_pnl"].sum()),
                trades=int(len(group)),
                slippage_cost=float(group["slippage_cost"].sum()),
                contract_sides=int(group["contracts"].sum()),
            )
        )
    return observations


def _monitoring_evaluation(
    observations: Sequence[MonitoringDailyObservationV1],
    thresholds: MonitoringThresholdsV1,
) -> tuple[MonitoringMetricsV1, list[str], Literal["HEALTHY", "ALERT", "RETIREMENT_REVIEW"]]:
    pnl = pd.Series([item.net_pnl for item in observations], dtype=float)
    max_drawdown = _max_drawdown(pnl)
    cumulative = float(pnl.sum())
    losing_streak = 0
    for value in reversed(pnl.tolist()):
        if value < 0:
            losing_streak += 1
        else:
            break
    selected: list[MonitoringDailyObservationV1] = []
    selected_trades = 0
    for item in reversed(observations):
        selected.append(item)
        selected_trades += item.trades
        if selected_trades >= thresholds.rolling_window_trades:
            break
    rolling_pnl = float(sum(item.net_pnl for item in selected))
    total_slippage = float(sum(item.slippage_cost for item in observations))
    total_contract_sides = int(sum(item.contract_sides for item in observations))
    average_slippage = total_slippage / total_contract_sides
    total_trades = int(sum(item.trades for item in observations))
    worst_daily = float(pnl.min())
    metrics = MonitoringMetricsV1(
        cumulative_net_pnl=cumulative,
        rolling_net_pnl=rolling_pnl,
        rolling_trade_count=selected_trades,
        rolling_window_complete=selected_trades >= thresholds.rolling_window_trades,
        maximum_drawdown=max_drawdown,
        worst_daily_pnl=worst_daily,
        current_losing_session_streak=losing_streak,
        average_slippage_per_contract_side=average_slippage,
        observed_sessions=len(observations),
        observed_trades=total_trades,
    )
    alerts: list[str] = []
    retirement = False
    if worst_daily <= -thresholds.daily_loss_alert_currency:
        alerts.append("daily loss alert threshold reached")
    if max_drawdown >= thresholds.drawdown_alert_currency:
        alerts.append("drawdown alert threshold reached")
    if losing_streak >= thresholds.losing_streak_alert:
        alerts.append("losing-session streak alert threshold reached")
    if metrics.rolling_window_complete and rolling_pnl / selected_trades < thresholds.minimum_rolling_expectancy_currency:
        alerts.append("rolling expectancy fell below its frozen threshold")
    if average_slippage > thresholds.maximum_average_slippage_per_contract:
        alerts.append("average slippage exceeded its frozen threshold")
    if max_drawdown >= thresholds.retirement_review_drawdown_currency:
        alerts.append("retirement-review drawdown threshold reached")
        retirement = True
    if losing_streak >= thresholds.retirement_review_losing_streak:
        alerts.append("retirement-review losing-session threshold reached")
        retirement = True
    status: Literal["HEALTHY", "ALERT", "RETIREMENT_REVIEW"]
    status = "RETIREMENT_REVIEW" if retirement else "ALERT" if alerts else "HEALTHY"
    return metrics, alerts, status


def _parse_monitoring_events(
    raw: bytes,
    *,
    decision: DeploymentDecisionV1,
    decision_sha256: str,
    verify_sources: bool,
) -> tuple[list[DeploymentMonitoringEventV1], list[str]]:
    events: list[DeploymentMonitoringEventV1] = []
    errors: list[str] = []
    previous_hash = decision_sha256
    previous_time: datetime | None = None
    previous_end: date | None = None
    all_observations: list[MonitoringDailyObservationV1] = []
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError as exc:
        return [], [f"monitoring journal is not UTF-8: {exc}"]
    for line_number, line in enumerate(text.splitlines(), start=1):
        if not line.strip():
            errors.append(f"monitoring journal line {line_number} is blank")
            continue
        try:
            payload = json.loads(line)
            event = DeploymentMonitoringEventV1.model_validate_json(line)
        except (json.JSONDecodeError, ValueError) as exc:
            errors.append(f"invalid monitoring event at line {line_number}: {exc}")
            continue
        if event.sequence != line_number:
            errors.append(f"monitoring event sequence is non-contiguous at line {line_number}")
        if event.deployment_decision_sha256 != decision_sha256:
            errors.append(f"monitoring decision hash is stale at line {line_number}")
        if event.previous_event_sha256 != previous_hash:
            errors.append(f"monitoring event hash chain is broken at line {line_number}")
        if event.event_sha256 != _monitoring_event_sha256(payload):
            errors.append(f"monitoring event content hash is stale at line {line_number}")
        if previous_time is not None and event.recorded_at <= previous_time:
            errors.append(f"monitoring chronology is non-increasing at line {line_number}")
        if previous_end is not None and event.period_start <= previous_end:
            errors.append(f"monitoring periods overlap at line {line_number}")
        if verify_sources:
            try:
                if _file_sha256(Path(event.source_trade_log_path)) != event.source_trade_log_sha256:
                    errors.append(f"monitoring source hash drifted at line {line_number}")
            except OSError as exc:
                errors.append(f"monitoring source is unavailable at line {line_number}: {exc}")
        all_observations.extend(event.daily_observations)
        expected_metrics, expected_alerts, expected_status = _monitoring_evaluation(
            all_observations,
            decision.monitoring_thresholds,
        )
        if event.metrics != expected_metrics or event.triggered_alerts != expected_alerts or event.status != expected_status:
            errors.append(f"monitoring threshold evaluation is stale at line {line_number}")
        events.append(event)
        previous_hash = event.event_sha256
        previous_time = event.recorded_at
        previous_end = event.period_end
    return events, errors


def _monitoring_event_sha256(payload: Mapping[str, Any]) -> str:
    return _sha256_json({key: value for key, value in payload.items() if key != "event_sha256"})


def _monitoring_head_errors(
    path: Path,
    raw: bytes,
    events: Sequence[DeploymentMonitoringEventV1],
    decision_sha256: str,
) -> list[str]:
    if not raw and not path.exists():
        return []
    try:
        head = _read_json_mapping(path, "monitoring journal head")
    except (OSError, ValueError) as exc:
        return [str(exc)]
    errors: list[str] = []
    expected_last = events[-1].event_sha256 if events else decision_sha256
    expected = {
        "schema": MONITORING_HEAD_SCHEMA,
        "deployment_decision_sha256": decision_sha256,
        "event_count": len(events),
        "last_event_sha256": expected_last,
        "events_sha256": hashlib.sha256(raw).hexdigest(),
    }
    if head != expected:
        errors.append("monitoring journal head is stale or mismatched")
    return errors


def _write_monitoring_head(
    path: Path,
    raw: bytes,
    *,
    event_count: int,
    last_event_sha256: str,
    decision_sha256: str,
) -> None:
    payload = {
        "schema": MONITORING_HEAD_SCHEMA,
        "deployment_decision_sha256": decision_sha256,
        "event_count": event_count,
        "last_event_sha256": last_event_sha256,
        "events_sha256": hashlib.sha256(raw).hexdigest(),
    }
    _atomic_replace_bytes(
        path,
        (json.dumps(payload, indent=2, sort_keys=True, allow_nan=False) + "\n").encode("utf-8"),
    )


def _copy_monitoring_source(
    source: Path,
    *,
    destination_root: Path,
    sequence: int,
) -> Path:
    data = source.read_bytes()
    digest = hashlib.sha256(data).hexdigest()
    safe_name = source.name
    if not safe_name or source.suffix.casefold() != ".csv":
        raise ValueError("monitoring source evidence must be a CSV file")
    target = destination_root / f"{sequence:06d}_{digest[:16]}_{safe_name}"
    if target.exists():
        if not target.is_file() or _file_sha256(target) != digest:
            raise ValueError("governed monitoring evidence destination is occupied or drifted")
        return target
    target.parent.mkdir(parents=True, exist_ok=True)
    with NamedTemporaryFile(
        dir=target.parent,
        prefix=f".{target.name}.",
        suffix=".tmp",
        delete=False,
    ) as handle:
        temporary = Path(handle.name)
        handle.write(data)
        handle.flush()
        os.fsync(handle.fileno())
    try:
        try:
            os.link(temporary, target)
        except FileExistsError as exc:
            raise ValueError("governed monitoring evidence already exists") from exc
    finally:
        temporary.unlink(missing_ok=True)
    return target


def _load_current_candidates(
    candidates: Sequence[CandidateEvidencePaths],
) -> tuple[list[PortfolioCandidateBindingV1], dict[str, _CandidateDailyEvidence]]:
    bindings: list[PortfolioCandidateBindingV1] = []
    daily: dict[str, _CandidateDailyEvidence] = {}
    seen: set[str] = set()
    for paths in candidates:
        binding, series = _load_current_candidate(paths)
        if binding.candidate_key in seen:
            raise ValueError(f"duplicate portfolio candidate: {binding.candidate_key}")
        seen.add(binding.candidate_key)
        bindings.append(binding)
        daily[binding.candidate_key] = series
    bindings.sort(key=lambda item: item.candidate_key)
    return bindings, {item.candidate_key: daily[item.candidate_key] for item in bindings}


def _load_current_candidate(
    paths: CandidateEvidencePaths,
) -> tuple[PortfolioCandidateBindingV1, _CandidateDailyEvidence]:
    result_path = Path(paths.result_bundle_path).resolve()
    candidate_review_path = Path(paths.candidate_review_path).resolve()
    config_path = Path(paths.config_path).resolve()
    finalized = inspect_finalized_result(result_path, config_path=config_path)
    if not finalized.get("valid"):
        raise ValueError(
            "portfolio review requires a complete hash-valid finalized result: "
            + "; ".join(str(item) for item in finalized.get("errors") or [])
        )
    bundle = finalized.get("bundle")
    if not isinstance(bundle, ResultBundleV2):
        raise ValueError("portfolio review could not load strict ResultBundleV2")
    review_report = CandidateReviewService().inspect(
        candidate_review_path=candidate_review_path,
        result_bundle_path=result_path,
        config_path=config_path,
    )
    review = review_report.get("review")
    if (
        not review_report.get("valid")
        or review_report.get("lifecycle_state") != "candidate"
        or not isinstance(review, CandidateReviewV1)
        or review.decision != "approved_candidate"
    ):
        raise ValueError(
            "portfolio review requires a current approved independent candidate review: "
            + "; ".join(str(item) for item in review_report.get("errors") or ["review is not approved"])
        )

    manifest = finalized.get("manifest")
    manifest_path = Path(str(finalized.get("manifest_path") or "")).resolve()
    if not isinstance(manifest, Mapping) or not manifest_path.is_file():
        raise ValueError("finalization manifest is unavailable")
    evidence_hashes = manifest.get("evidence_artifact_sha256")
    required_acceptance_artifacts = (
        ACCEPTANCE_TRADE_LOG,
        ACCEPTANCE_SUMMARY,
        ACCEPTANCE_SESSION_CALENDAR,
    )
    if not isinstance(evidence_hashes, Mapping) or any(
        artifact not in evidence_hashes for artifact in required_acceptance_artifacts
    ):
        raise ValueError(
            "finalization does not bind the acceptance OOS trade log, evaluation summary, "
            "and complete session calendar"
        )
    run_dir = result_path.parent.parent
    acceptance_path = (run_dir / ACCEPTANCE_TRADE_LOG).resolve()
    summary_path = (run_dir / ACCEPTANCE_SUMMARY).resolve()
    calendar_path = (run_dir / ACCEPTANCE_SESSION_CALENDAR).resolve()
    acceptance_artifact_paths = {
        ACCEPTANCE_TRADE_LOG: acceptance_path,
        ACCEPTANCE_SUMMARY: summary_path,
        ACCEPTANCE_SESSION_CALENDAR: calendar_path,
    }
    artifact_hashes: dict[str, str] = {}
    for relative, artifact_path in acceptance_artifact_paths.items():
        if not artifact_path.is_file():
            raise ValueError(f"required acceptance OOS artifact is missing: {relative}")
        digest = _file_sha256(artifact_path)
        if digest != str(evidence_hashes.get(relative) or ""):
            raise ValueError(f"acceptance OOS artifact hash drifted from finalization: {relative}")
        artifact_hashes[relative] = digest

    config = _read_yaml_mapping(config_path)
    instrument = str(config.get("symbol") or config.get("instrument") or "").strip()
    if not instrument:
        raise ValueError("candidate config does not declare its instrument")
    core = config.get("core") if isinstance(config.get("core"), Mapping) else {}
    try:
        initial_balance = float(core.get("initial_balance"))
    except (TypeError, ValueError) as exc:
        raise ValueError("candidate config core.initial_balance must be a positive number") from exc
    if not math.isfinite(initial_balance) or initial_balance <= 0:
        raise ValueError("candidate config core.initial_balance must be a positive number")

    frame = _read_acceptance_trade_log(acceptance_path)
    observed_series = frame.groupby("session_date", sort=True)["net_pnl"].sum().astype(float)
    evaluation_start, evaluation_end, calendar_dates = _read_acceptance_evaluation_contract(
        summary_path,
        calendar_path,
    )
    observed_dates = frozenset(observed_series.index.tolist())
    outside = sorted(observed_dates - set(calendar_dates))
    if outside:
        raise ValueError(
            "acceptance OOS trades fall outside the hash-bound evaluation session calendar: "
            + ", ".join(item.isoformat() for item in outside[:5])
        )
    series = observed_series.reindex(calendar_dates, fill_value=0.0).astype(float)
    key = _candidate_key(
        bundle.campaign_id,
        bundle.variant_id,
        bundle.run_id,
        eligibility_basis=review.eligibility_basis,
        account_assessment_id=review.account_assessment_id,
    )
    binding = PortfolioCandidateBindingV1(
        candidate_key=key,
        campaign_id=bundle.campaign_id,
        variant_id=bundle.variant_id,
        run_id=bundle.run_id,
        instrument=instrument,
        initial_balance=initial_balance,
        result_bundle_path=str(result_path),
        result_bundle_sha256=_file_sha256(result_path),
        finalization_manifest_path=str(manifest_path),
        finalization_manifest_sha256=_file_sha256(manifest_path),
        candidate_review_path=str(candidate_review_path),
        candidate_review_sha256=_file_sha256(candidate_review_path),
        config_path=str(config_path),
        config_sha256=_file_sha256(config_path),
        acceptance_trade_log_path=str(acceptance_path),
        acceptance_trade_log_sha256=artifact_hashes[ACCEPTANCE_TRADE_LOG],
        acceptance_summary_path=str(summary_path),
        acceptance_summary_sha256=artifact_hashes[ACCEPTANCE_SUMMARY],
        acceptance_session_calendar_path=str(calendar_path),
        acceptance_session_calendar_sha256=artifact_hashes[ACCEPTANCE_SESSION_CALENDAR],
        coverage_start=evaluation_start,
        coverage_end=evaluation_end,
        evaluation_sessions=len(calendar_dates),
        observed_trade_sessions=len(observed_dates),
        no_trade_sessions=len(calendar_dates) - len(observed_dates),
        acceptance_trades=int(len(frame)),
        eligibility_basis=review.eligibility_basis,
        account_assessment_id=review.account_assessment_id,
        account_profile_id=review.account_profile_id,
        account_profile_version=review.account_profile_version,
    )
    return binding, _CandidateDailyEvidence(
        pnl=series,
        observed_trade_sessions=observed_dates,
    )


def _read_acceptance_trade_log(path: Path) -> pd.DataFrame:
    try:
        frame = pd.read_csv(path)
    except Exception as exc:
        raise ValueError(f"could not read acceptance OOS trade log: {exc}") from exc
    required = {"session_date", "net_pnl"}
    missing = sorted(required - set(frame.columns))
    if missing:
        raise ValueError("acceptance OOS trade log is missing required columns: " + ", ".join(missing))
    if frame.empty:
        raise ValueError("acceptance OOS trade log contains no trades")
    dates = pd.to_datetime(frame["session_date"], errors="coerce")
    pnl = pd.to_numeric(frame["net_pnl"], errors="coerce")
    if dates.isna().any():
        raise ValueError("acceptance OOS trade log contains invalid session_date values")
    if pnl.isna().any() or not np.isfinite(pnl.to_numpy(dtype=float)).all():
        raise ValueError("acceptance OOS trade log contains invalid net_pnl values")
    normalized = frame.copy()
    normalized["session_date"] = dates.dt.date
    normalized["net_pnl"] = pnl.astype(float)
    return normalized


def _read_acceptance_evaluation_contract(
    summary_path: Path,
    calendar_path: Path,
) -> tuple[date, date, list[date]]:
    summary = _read_json_mapping(summary_path, "acceptance OOS evaluation summary")
    try:
        start = pd.Timestamp(summary["test_start"]).date()
        end = pd.Timestamp(summary["test_end"]).date()
    except (KeyError, TypeError, ValueError, OverflowError) as exc:
        raise ValueError(
            "acceptance OOS summary requires valid test_start and test_end"
        ) from exc
    if end < start:
        raise ValueError("acceptance OOS evaluation end precedes its start")
    try:
        calendar = pd.read_csv(calendar_path)
    except Exception as exc:
        raise ValueError(f"could not read acceptance OOS session calendar: {exc}") from exc
    if calendar.empty or "session_date" not in calendar.columns:
        raise ValueError("acceptance OOS session calendar is empty or lacks session_date")
    parsed = pd.to_datetime(calendar["session_date"], errors="coerce")
    if parsed.isna().any():
        raise ValueError("acceptance OOS session calendar contains invalid session_date values")
    dates = [value.date() for value in parsed]
    if dates != sorted(set(dates)):
        raise ValueError("acceptance OOS session calendar must be unique and chronological")
    dates = [value for value in dates if start <= value <= end]
    if len(dates) < 2:
        raise ValueError("acceptance OOS session calendar has fewer than two evaluation sessions")
    return start, end, dates


def _analyze_portfolio(
    bindings: Sequence[PortfolioCandidateBindingV1],
    daily: Mapping[str, _CandidateDailyEvidence],
    *,
    minimum_common_sessions: int,
) -> PortfolioAnalysisV1:
    latest_start = max(item.coverage_start for item in bindings)
    earliest_end = min(item.coverage_end for item in bindings)
    if latest_start > earliest_end:
        raise ValueError("candidate acceptance OOS coverage periods do not overlap")
    aligned = pd.concat(
        [daily[item.candidate_key].pnl.rename(item.candidate_key) for item in bindings],
        axis=1,
        join="inner",
    ).sort_index()
    # Each input series is already reindexed to its independently hash-bound
    # acceptance session calendar, so the inner join is the complete common
    # evaluation calendar—not the biased intersection of days with trades.
    if len(aligned) < minimum_common_sessions:
        raise ValueError(
            "portfolio review has too few common acceptance evaluation sessions: "
            f"{len(aligned)} < {minimum_common_sessions}"
        )
    if aligned.isna().any().any():
        raise ValueError("portfolio alignment unexpectedly contains missing PnL")
    returns = aligned.copy()
    for item in bindings:
        returns[item.candidate_key] = aligned[item.candidate_key] / item.initial_balance
    if any(float(aligned[column].std(ddof=0)) <= 0 for column in aligned.columns):
        raise ValueError("portfolio PnL correlation is undefined for a constant candidate series")
    if any(float(returns[column].std(ddof=0)) <= 0 for column in returns.columns):
        raise ValueError("portfolio return correlation is undefined for a constant candidate series")

    pnl_corr = aligned.corr()
    return_corr = returns.corr()
    pairwise: list[PairwisePortfolioMetricV1] = []
    for left_index, left in enumerate(bindings):
        for right in bindings[left_index + 1 :]:
            left_loss = aligned[left.candidate_key] < 0
            right_loss = aligned[right.candidate_key] < 0
            overlap = int((left_loss & right_loss).sum())
            any_loss = int((left_loss | right_loss).sum())
            pairwise.append(
                PairwisePortfolioMetricV1(
                    candidate_a=left.candidate_key,
                    candidate_b=right.candidate_key,
                    common_sessions=int(len(aligned)),
                    pnl_correlation=_finite_correlation(
                        pnl_corr.loc[left.candidate_key, right.candidate_key], "PnL"
                    ),
                    return_correlation=_finite_correlation(
                        return_corr.loc[left.candidate_key, right.candidate_key], "return"
                    ),
                    overlapping_loss_days=overlap,
                    overlapping_loss_fraction=overlap / len(aligned),
                    overlapping_loss_jaccard=(overlap / any_loss if any_loss else 0.0),
                )
            )

    gross_activity = aligned.abs().sum(axis=0)
    gross_total = float(gross_activity.sum())
    if not math.isfinite(gross_total) or gross_total <= 0:
        raise ValueError("portfolio gross PnL activity is zero or undefined")
    shares = gross_activity / gross_total
    combined_pnl = aligned.sum(axis=1)
    combined_returns = returns.mean(axis=1)
    combined_drawdown = _max_drawdown(combined_pnl)
    contributions: list[PortfolioContributionV1] = []
    common_dates = set(aligned.index.tolist())
    observed_by_candidate = {
        item.candidate_key: daily[item.candidate_key].observed_trade_sessions & common_dates
        for item in bindings
    }
    for item in bindings:
        without = aligned.drop(columns=[item.candidate_key]).sum(axis=1)
        contributions.append(
            PortfolioContributionV1(
                candidate_key=item.candidate_key,
                common_period_net_pnl=float(aligned[item.candidate_key].sum()),
                common_period_max_drawdown=_max_drawdown(aligned[item.candidate_key]),
                gross_pnl_activity_share=float(shares[item.candidate_key]),
                marginal_combined_max_drawdown=combined_drawdown - _max_drawdown(without),
                observed_trade_sessions=len(observed_by_candidate[item.candidate_key]),
                zero_filled_sessions=len(aligned) - len(observed_by_candidate[item.candidate_key]),
            )
        )
    max_abs_corr = max(abs(item.pnl_correlation) for item in pairwise)
    observed_any = set().union(*observed_by_candidate.values())
    return PortfolioAnalysisV1(
        minimum_common_sessions=minimum_common_sessions,
        common_coverage_start=aligned.index.min(),
        common_coverage_end=aligned.index.max(),
        common_session_count=int(len(aligned)),
        common_sessions_with_any_trade=len(observed_any),
        common_sessions_with_no_trades=len(aligned) - len(observed_any),
        zero_filled_candidate_sessions=sum(
            len(aligned) - len(observed_by_candidate[item.candidate_key])
            for item in bindings
        ),
        pairwise=pairwise,
        contributions=contributions,
        combined_common_period_net_pnl=float(combined_pnl.sum()),
        combined_max_drawdown=combined_drawdown,
        combined_equal_weight_max_drawdown_return=_max_drawdown(combined_returns),
        maximum_pairwise_absolute_pnl_correlation=max_abs_corr,
        largest_gross_pnl_activity_share=float(shares.max()),
        gross_pnl_activity_hhi=float((shares**2).sum()),
    )


def _max_drawdown(increments: pd.Series) -> float:
    values = np.asarray(increments, dtype=float)
    equity = np.concatenate(([0.0], np.cumsum(values)))
    peaks = np.maximum.accumulate(equity)
    return float(np.max(peaks - equity))


def _finite_correlation(value: Any, label: str) -> float:
    result = float(value)
    if not math.isfinite(result):
        raise ValueError(f"portfolio {label} correlation is undefined")
    return max(-1.0, min(1.0, result))


def _portfolio_review_id(
    candidates: Sequence[PortfolioCandidateBindingV1],
    analysis: PortfolioAnalysisV1,
    generated_at: datetime,
) -> str:
    payload = {
        "schema": PORTFOLIO_REVIEW_SCHEMA,
        "generated_at": generated_at.isoformat(),
        "candidates": [item.model_dump(mode="json") for item in candidates],
        "methodology": analysis.methodology,
        "minimum_common_sessions": analysis.minimum_common_sessions,
    }
    return _sha256_json(payload)


def _candidate_key(
    campaign_id: str,
    variant_id: str,
    run_id: str,
    *,
    eligibility_basis: str = "generic_scientific_pass",
    account_assessment_id: str | None = None,
) -> str:
    base = f"{campaign_id}/{variant_id}/{run_id}"
    if eligibility_basis != "destination_specific_pass":
        return base
    return f"{base}/account/{account_assessment_id}"


def _coerce_candidate_paths(value: CandidateEvidencePaths | Mapping[str, Any]) -> CandidateEvidencePaths:
    if isinstance(value, CandidateEvidencePaths):
        return value
    if not isinstance(value, Mapping):
        raise ValueError("candidate evidence input must be a mapping or CandidateEvidencePaths")
    try:
        return CandidateEvidencePaths(
            result_bundle_path=value["result_bundle_path"],
            candidate_review_path=value["candidate_review_path"],
            config_path=value["config_path"],
        )
    except KeyError as exc:
        raise ValueError(f"candidate evidence input is missing {exc.args[0]}") from exc


def _read_yaml_mapping(path: Path) -> dict[str, Any]:
    try:
        value = yaml.safe_load(path.read_text(encoding="utf-8"))
    except (OSError, yaml.YAMLError) as exc:
        raise ValueError(f"could not read candidate config: {exc}") from exc
    if not isinstance(value, dict):
        raise ValueError("candidate config must contain a YAML mapping")
    return value


def _read_json_mapping(path: Path, label: str) -> dict[str, Any]:
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
            raise ValueError("timestamp must be an ISO-8601 datetime") from exc
    if result.tzinfo is None or result.utcoffset() is None:
        raise ValueError("timestamp must be timezone-aware")
    return result


def _sha256_json(value: Any) -> str:
    payload = json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
        allow_nan=False,
    ).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def _file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _write_new_model(path: Path, model: BaseModel) -> None:
    """Publish once without an overwrite race; governed records are immutable."""

    path.parent.mkdir(parents=True, exist_ok=True)
    payload = model.model_dump(mode="json", by_alias=True)
    data = (json.dumps(payload, indent=2, sort_keys=True, allow_nan=False) + "\n").encode("utf-8")
    with NamedTemporaryFile(dir=path.parent, prefix=f".{path.name}.", suffix=".tmp", delete=False) as handle:
        temporary = Path(handle.name)
        handle.write(data)
        handle.flush()
        os.fsync(handle.fileno())
    try:
        try:
            os.link(temporary, path)
        except FileExistsError as exc:
            raise ValueError(f"governed artifact already exists and cannot be overwritten: {path}") from exc
    finally:
        temporary.unlink(missing_ok=True)


def _atomic_replace_bytes(path: Path, data: bytes) -> None:
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
