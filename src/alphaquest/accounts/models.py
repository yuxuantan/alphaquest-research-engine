from __future__ import annotations

from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, HttpUrl, model_validator


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, allow_inf_nan=False)


class OfficialSourceV1(StrictModel):
    title: str = Field(min_length=1)
    url: HttpUrl
    accessed_at: date
    supports: list[str] = Field(min_length=1)


class ProfileProvenanceV1(StrictModel):
    verification_status: Literal["reviewed", "synthetic", "stale", "needs_manual_review"]
    reviewed_at: datetime | None = None
    reviewer: str | None = None
    official_sources: list[OfficialSourceV1] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def reviewed_profiles_need_sources(self) -> "ProfileProvenanceV1":
        if self.verification_status == "reviewed" and not self.official_sources:
            raise ValueError("reviewed account profiles require at least one official source")
        return self


class AccountIdentityV1(StrictModel):
    provider: str = Field(min_length=1)
    program: str = Field(min_length=1)
    account_label: str = Field(min_length=1)
    account_kind: Literal["prop_challenge", "prop_funded", "live"]
    nominal_balance: float = Field(gt=0)
    currency: str = Field(default="USD", min_length=3, max_length=3)
    timezone: str = Field(min_length=1)
    session_reset_time: str = Field(pattern=r"^\d{2}:\d{2}:\d{2}$")
    eod_snapshot_time: str = Field(pattern=r"^\d{2}:\d{2}:\d{2}$")
    simulated_account: bool


class ScalingTierV1(StrictModel):
    minimum_profit: float
    maximum_profit_exclusive: float | None = None
    maximum_contracts: int = Field(ge=1)
    daily_loss_limit: float = Field(gt=0)

    @model_validator(mode="after")
    def valid_range(self) -> "ScalingTierV1":
        if self.maximum_profit_exclusive is not None and self.maximum_profit_exclusive <= self.minimum_profit:
            raise ValueError("tier maximum must be greater than its minimum")
        return self


class EodDrawdownRuleV1(StrictModel):
    amount: float = Field(gt=0)
    initial_threshold: float
    trailing_basis: Literal["highest_eod_balance"]
    recalculation: Literal["end_of_day"]
    enforcement: Literal["intraday_equity"]
    breach_operator: Literal["touch_or_below"] = "touch_or_below"
    locked_threshold: float | None = None
    never_moves_down: Literal[True] = True


class EvaluationRuleV1(StrictModel):
    profit_target: float = Field(gt=0)
    access_period_calendar_days: int = Field(ge=1)
    minimum_trading_days: int = Field(ge=0)
    consistency_limit: float | None = Field(default=None, gt=0, le=1)
    activation_window_calendar_days: int | None = Field(default=None, ge=1)


class PayoutRuleV1(StrictModel):
    qualifying_profit_days: int = Field(ge=1)
    minimum_daily_profit: float = Field(gt=0)
    consistency_limit: float = Field(gt=0, le=1)
    consistency_operator: Literal["strictly_less_than"] = "strictly_less_than"
    safety_net_balance: float = Field(gt=0)
    minimum_request_balance: float = Field(gt=0)
    minimum_payout: float = Field(gt=0)
    maximum_payouts: int = Field(ge=1)
    payout_caps: list[float] = Field(min_length=1)
    payout_profit_share: float = Field(gt=0, le=1)
    request_policy: Literal["maximum_when_eligible"] = "maximum_when_eligible"

    @model_validator(mode="after")
    def payout_caps_cover_cycle(self) -> "PayoutRuleV1":
        if len(self.payout_caps) != self.maximum_payouts:
            raise ValueError("payout_caps must contain one cap for every permitted payout")
        if self.minimum_request_balance < self.safety_net_balance + self.minimum_payout:
            raise ValueError("minimum request balance must preserve the safety net plus minimum payout")
        return self


class InactivityRuleV1(StrictModel):
    rolling_calendar_days: int = Field(ge=1)
    required_profit_days: int = Field(ge=1)
    minimum_daily_profit: float = Field(gt=0)
    consequence: Literal["account_closed"]


class AcquisitionRuleV1(StrictModel):
    prerequisite_profile_id: str | None = None
    evaluation_price_mode: Literal["assessment_input_required", "not_applicable"]
    activation_fee_mode: Literal["assessment_input_required", "zero", "not_applicable"]
    retry_requires_new_evaluation: bool = False


class AccountRulesV1(StrictModel):
    permitted_instruments: list[str] = Field(min_length=1)
    overnight_positions_allowed: bool
    position_close_deadline: str = Field(pattern=r"^\d{2}:\d{2}:\d{2}$")
    intraday_equity_required: bool
    eod_drawdown: EodDrawdownRuleV1 | None = None
    fixed_maximum_contracts: int | None = Field(default=None, ge=1)
    fixed_daily_loss_limit: float | None = Field(default=None, gt=0)
    scaling_tiers: list[ScalingTierV1] = Field(default_factory=list)
    evaluation: EvaluationRuleV1 | None = None
    payouts: PayoutRuleV1 | None = None
    inactivity: InactivityRuleV1 | None = None
    acquisition: AcquisitionRuleV1
    manual_attestations_required: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def sizing_is_fully_declared(self) -> "AccountRulesV1":
        if self.fixed_maximum_contracts is None and not self.scaling_tiers:
            raise ValueError("account rules require fixed sizing or scaling tiers")
        if self.scaling_tiers:
            ordered = sorted(self.scaling_tiers, key=lambda item: item.minimum_profit)
            if ordered != self.scaling_tiers:
                raise ValueError("scaling tiers must be ordered by minimum_profit")
            if ordered[0].minimum_profit != 0:
                raise ValueError("scaling tiers must begin at zero profit")
            for previous, current in zip(ordered, ordered[1:]):
                if previous.maximum_profit_exclusive != current.minimum_profit:
                    raise ValueError("scaling tiers must be contiguous")
        return self


class AccountEvaluationPolicyV1(StrictModel):
    minimum_horizon_sessions: int = Field(ge=1)
    monte_carlo_runs: int = Field(ge=1000)
    monte_carlo_horizon_sessions: int = Field(ge=1)
    monte_carlo_block_sessions: int = Field(ge=1)
    maximum_account_closure_probability: float = Field(ge=0, le=1)
    maximum_daily_loss_lock_probability: float = Field(ge=0, le=1)
    minimum_first_payout_probability: float | None = Field(default=None, ge=0, le=1)
    minimum_two_payout_probability: float | None = Field(default=None, ge=0, le=1)
    minimum_expected_net_payout_after_costs: float | None = None
    minimum_expected_payout_to_cost_ratio: float | None = Field(default=None, ge=0)
    maximum_p95_drawdown: float | None = Field(default=None, gt=0)
    deterministic_require_no_closure: bool = True
    deterministic_require_no_daily_loss_lock: bool = True
    deterministic_require_no_position_rejection: bool = True
    recommended_tests: list[str] = Field(min_length=1)


class AccountRuleProfileV1(StrictModel):
    schema_version: Literal["alphaquest.account-rule-profile/v1"] = Field(
        default="alphaquest.account-rule-profile/v1", alias="schema"
    )
    profile_id: str = Field(min_length=1)
    version: str = Field(min_length=1)
    name: str = Field(min_length=1)
    description: str = Field(min_length=1)
    effective_from: date
    effective_until: date | None = None
    novice_visible: bool = True
    promotable: bool = True
    identity: AccountIdentityV1
    provenance: ProfileProvenanceV1
    rules: AccountRulesV1
    evaluation_policy: AccountEvaluationPolicyV1

    @model_validator(mode="after")
    def phase_rules_match_identity(self) -> "AccountRuleProfileV1":
        kind = self.identity.account_kind
        if kind == "prop_challenge" and self.rules.evaluation is None:
            raise ValueError("prop challenge profiles require evaluation rules")
        if kind == "prop_funded" and self.rules.payouts is None:
            raise ValueError("prop funded profiles require payout rules")
        if self.provenance.verification_status != "reviewed" and self.promotable:
            raise ValueError("only reviewed profiles may be promotable")
        return self


class AccountAssessmentCostsV1(StrictModel):
    currency: str = Field(default="USD", min_length=3, max_length=3)
    evaluation_purchase_price: float = Field(ge=0)
    activation_fee: float = Field(ge=0)
    other_upfront_costs: float = Field(default=0.0, ge=0)
    observed_at: datetime
    source: str = Field(min_length=1)
    include_as_replacement_cost: bool = True

    @property
    def total(self) -> float:
        return self.evaluation_purchase_price + self.activation_fee + self.other_upfront_costs


__all__ = [
    "AccountAssessmentCostsV1",
    "AccountEvaluationPolicyV1",
    "AccountRuleProfileV1",
]
