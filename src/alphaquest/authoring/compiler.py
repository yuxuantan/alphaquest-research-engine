from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
from datetime import date, timedelta
import hashlib
import json
from pathlib import Path
from types import MappingProxyType
from typing import Any, Mapping

from pydantic import ValidationError

from alphaquest.authoring.catalog import CERTIFIED_MODULE_CATALOG, CertifiedModuleCatalog
from alphaquest.authoring.models import CampaignDraftV1, ModuleBindingV1, VariantDraftV1


AUTHORING_MANIFEST_SCHEMA = "alphaquest.authoring-manifest/v1"
STRATEGY_SPEC_SCHEMA = "alphaquest.strategy-spec/v1"


class CampaignCompilationError(ValueError):
    """Raised when a draft cannot safely become an executable campaign."""


@dataclass(frozen=True)
class CompiledCampaign:
    draft: CampaignDraftV1
    campaign: Mapping[str, Any]
    variant_configs: Mapping[str, Mapping[str, Any]]
    authoring_manifest: Mapping[str, Any]
    strategy_spec: Mapping[str, Any]
    draft_sha256: str

    @property
    def campaign_id(self) -> str:
        return self.draft.campaign_id

    @property
    def relative_paths(self) -> tuple[str, ...]:
        paths = ["campaign.yaml", "authoring_manifest.json", "strategy_spec.yaml"]
        paths.extend(f"variants/{variant_id}/config.yaml" for variant_id in self.variant_configs)
        return tuple(paths)


class CampaignCompiler:
    """Pure, deterministic compiler from a reviewed draft to source contracts."""

    def __init__(
        self,
        catalog: CertifiedModuleCatalog | None = None,
        *,
        evidence_root: str | Path = "research/evidence/runs",
        research_artifact_root: str | Path = "research_artifacts",
    ) -> None:
        self.catalog = catalog or CERTIFIED_MODULE_CATALOG
        self.evidence_root = Path(evidence_root).as_posix().rstrip("/")
        self.research_artifact_root = Path(research_artifact_root).as_posix().rstrip("/")

    def compile(self, draft: CampaignDraftV1 | Mapping[str, Any]) -> CompiledCampaign:
        try:
            parsed = draft if isinstance(draft, CampaignDraftV1) else CampaignDraftV1.model_validate(dict(draft))
        except (ValidationError, TypeError, ValueError) as exc:
            raise CampaignCompilationError(f"campaign draft is invalid: {exc}") from exc
        self._validate_publishable(parsed)

        normalized: list[tuple[VariantDraftV1, ModuleBindingV1, ModuleBindingV1, ModuleBindingV1]] = []
        for variant in parsed.variants:
            entry_input = self._bind_context(parsed, variant.entry)
            stop_input = self._bind_context(parsed, variant.stop)
            target_input = self._bind_context(parsed, variant.target)
            try:
                entry = self.catalog.validate_binding("entry", entry_input, dataset=parsed.dataset)
                stop = self.catalog.validate_binding("sl", stop_input, dataset=parsed.dataset)
                target = self.catalog.validate_binding("tp", target_input, dataset=parsed.dataset)
            except ValueError as exc:
                raise CampaignCompilationError(f"variant {variant.variant_id}: {exc}") from exc
            normalized.append((variant, entry, stop, target))

        draft_document = parsed.model_dump(mode="json", by_alias=True)
        draft_sha256 = _object_sha256(draft_document)
        campaign = self._campaign_document(parsed, normalized)
        variant_configs = {
            variant.variant_id: self._variant_config(parsed, variant, entry, stop, target)
            for variant, entry, stop, target in normalized
        }
        strategy_spec = self._strategy_spec(parsed, normalized, draft_sha256)
        manifest = self._authoring_manifest(
            parsed,
            normalized,
            draft_sha256,
            campaign=campaign,
            variant_configs=variant_configs,
            strategy_spec=strategy_spec,
        )
        return CompiledCampaign(
            draft=parsed.model_copy(deep=True),
            campaign=MappingProxyType(deepcopy(campaign)),
            variant_configs=MappingProxyType(
                {key: MappingProxyType(deepcopy(value)) for key, value in variant_configs.items()}
            ),
            authoring_manifest=MappingProxyType(deepcopy(manifest)),
            strategy_spec=MappingProxyType(deepcopy(strategy_spec)),
            draft_sha256=draft_sha256,
        )

    def _validate_publishable(self, draft: CampaignDraftV1) -> None:
        if not draft.frozen:
            raise CampaignCompilationError("draft must be frozen before compilation")
        if draft.dataset.quality_verdict != "PASS":
            raise CampaignCompilationError("selected dataset must have a PASS quality verdict")
        if draft.dataset.timestamp_semantics != "bar_open":
            raise CampaignCompilationError(
                "executable Studio datasets must use canonical bar-open timestamps; normalize bar-close input first"
            )
        if draft.dataset.contract_count > 1 and draft.dataset.continuous_contract == "none":
            raise CampaignCompilationError(
                "multi-contract datasets require a governed executable continuous-contract selection rule"
            )
        if draft.dataset.continuous_contract in {"dominant_session_volume", "session_volume"}:
            raise CampaignCompilationError(
                "Studio does not certify session-final volume contract selection because it is unavailable "
                "at earlier decision bars; use a predeclared explicit roll calendar"
            )
        if draft.dataset.continuous_contract != "none" and draft.dataset.contract_column != "contract_symbol":
            raise CampaignCompilationError(
                "continuous-contract selection requires preserved canonical contract_symbol lineage"
            )
        if draft.dataset.continuous_contract == "explicit_roll_calendar" and not draft.dataset.roll_calendar:
            raise CampaignCompilationError("explicit_roll_calendar requires a governed roll calendar")
        if not draft.timeframe.endswith("m"):
            raise CampaignCompilationError("Studio v1 executable campaigns require intraday minute bars")
        if draft.duplicate_review.conclusion != "distinct":
            raise CampaignCompilationError("duplicate review must conclude distinct before executable publication")
        if not all(variant.confirmed for variant in draft.variants):
            raise CampaignCompilationError("all five variant mechanics must be individually confirmed")
        substantive = {
            "duplicate distinction": draft.duplicate_review.substantive_distinction,
            **{
                f"{variant.variant_id} mechanic": variant.mechanic_rationale
                for variant in draft.variants
            },
            **{
                f"{variant.variant_id} material difference": variant.material_difference
                for variant in draft.variants
            },
            **{
                f"{variant.variant_id} entry rationale": variant.entry_rationale
                for variant in draft.variants
            },
            **{
                f"{variant.variant_id} stop rationale": variant.stop_rationale
                for variant in draft.variants
            },
            **{
                f"{variant.variant_id} target rationale": variant.target_rationale
                for variant in draft.variants
            },
            **{
                f"{variant.variant_id} known failure modes": " ".join(variant.known_failure_modes)
                for variant in draft.variants
            },
        }
        short = [label for label, value in substantive.items() if len(value.strip()) < 80]
        if short:
            raise CampaignCompilationError(
                "governance rationales must contain at least 80 characters: " + ", ".join(short)
            )
        fingerprint = draft.economic_edge_fingerprint
        fingerprint_values = [
            fingerprint.market_behavior,
            fingerprint.causal_mechanism,
            ", ".join(fingerprint.signal_inputs),
            fingerprint.market_context,
            fingerprint.holding_period,
        ]
        if any(len(value.strip()) < 20 for value in fingerprint_values):
            raise CampaignCompilationError("every economic edge fingerprint field must contain at least 20 characters")

    def _bind_context(self, draft: CampaignDraftV1, binding: ModuleBindingV1) -> ModuleBindingV1:
        params = deepcopy(binding.params)
        timeframe_minutes = _timeframe_minutes(draft.timeframe)
        if binding.module in {"safe_bar_rule", "calendar_session_bias", "opening_range_breakout", "daily_time_series_momentum"}:
            if binding.module == "safe_bar_rule":
                rule = deepcopy(params.get("rule")) if isinstance(params.get("rule"), dict) else {}
                rule.setdefault("bar_interval_minutes", timeframe_minutes)
                configured_interval = float(rule["bar_interval_minutes"])
                if configured_interval != timeframe_minutes:
                    raise CampaignCompilationError(
                        f"safe_bar_rule bar_interval_minutes {configured_interval} does not match {draft.timeframe}"
                    )
                if str(rule.get("signal_start_time", "09:30:00")) < draft.execution.session_start:
                    raise CampaignCompilationError("safe_bar_rule signal window starts before the reviewed session")
                if str(rule.get("signal_end_time", "15:45:00")) > draft.execution.latest_entry_time:
                    raise CampaignCompilationError("safe_bar_rule signal window extends beyond latest_entry_time")
                params["rule"] = rule
            else:
                configured_interval = float(params.get("bar_interval_minutes", timeframe_minutes))
                if configured_interval != timeframe_minutes:
                    raise CampaignCompilationError(
                        f"{binding.module} bar_interval_minutes {configured_interval} does not match {draft.timeframe}"
                    )
                params["bar_interval_minutes"] = timeframe_minutes
        if binding.module == "calendar_session_bias":
            params.setdefault("max_trades_per_day", 1)
        if binding.module == "opening_range_breakout":
            params.setdefault("rth_start", draft.execution.session_start)
            params.setdefault("last_entry_time", draft.execution.latest_entry_time)
        if binding.module == "daily_time_series_momentum":
            params.setdefault("rth_end", draft.execution.session_end)
        if binding.module == "fixed_dollar_per_contract":
            _require_matching_or_set(params, "tick_value", draft.execution.tick_value)
        if binding.module == "cost_adjusted_fixed_r":
            for name, value in (
                ("tick_size", draft.execution.tick_size),
                ("tick_value", draft.execution.tick_value),
                ("commission_per_contract", draft.execution.commission_per_contract),
                ("slippage_ticks", draft.execution.slippage_ticks),
            ):
                _require_matching_or_set(params, name, value)
        return ModuleBindingV1(module=binding.module, params=params, parameter_grid=deepcopy(binding.parameter_grid))

    def _campaign_document(
        self,
        draft: CampaignDraftV1,
        variants: list[tuple[VariantDraftV1, ModuleBindingV1, ModuleBindingV1, ModuleBindingV1]],
    ) -> dict[str, Any]:
        fingerprint = draft.economic_edge_fingerprint
        return {
            "campaign_id": draft.campaign_id,
            "title": draft.title,
            "status": "authored_for_testing",
            "created_at": draft.created_at,
            "instrument": draft.instrument,
            "timeframe": draft.timeframe,
            "governance_contract_version": 2,
            "authoring_lane": draft.authoring_lane,
            "certified_recipe": draft.certified_recipe,
            "edge_family": draft.edge_family,
            "hypothesis": draft.hypothesis,
            "economic_edge_fingerprint": {
                "market_behavior": fingerprint.market_behavior,
                "causal_mechanism": fingerprint.causal_mechanism,
                "signal_inputs": ", ".join(fingerprint.signal_inputs),
                "market_context": fingerprint.market_context,
                "holding_period": fingerprint.holding_period,
            },
            "duplicate_edge_review": {
                "reviewed_campaign_ids": list(draft.duplicate_review.reviewed_campaign_ids),
                "ledger_queries": list(draft.duplicate_review.ledger_queries),
                "conclusion": "distinct",
                "substantive_distinction": draft.duplicate_review.substantive_distinction,
            },
            "sources": [
                {
                    "title": source.title,
                    "authors": ", ".join(source.authors),
                    "year": source.year,
                    "link": source.link or f"https://doi.org/{source.doi}",
                    "doi": source.doi,
                    "relevance": source.relevance,
                }
                for source in draft.sources
            ],
            "variants": [variant.variant_id for variant, *_ in variants],
            "variant_distinctions": {
                variant.variant_id: {
                    "mechanic": variant.mechanic_rationale,
                    "material_difference": variant.material_difference,
                    "mechanic_signature": variant.mechanic_signature,
                }
                for variant, *_ in variants
            },
            "rescue_policy": {"allowed": False, "max_rescues_per_failed_variant": 1},
        }

    def _variant_config(
        self,
        draft: CampaignDraftV1,
        variant: VariantDraftV1,
        entry: ModuleBindingV1,
        stop: ModuleBindingV1,
        target: ModuleBindingV1,
    ) -> dict[str, Any]:
        data_key = "raw_parquet" if draft.dataset.source == "parquet" else "raw_csv"
        full_subset = {
            "start_date": draft.dataset.coverage_start[:10],
            "end_date": draft.dataset.coverage_end[:10],
            "session_labels": ["RTH"],
        }
        validation_subset = mechanics_validation_subset(
            draft.dataset.coverage_start,
            draft.dataset.coverage_end,
            entry=entry,
        )
        grid = _parameter_grid(entry, stop, target)
        profitability = f"{draft.expected_mechanism} {variant.mechanic_rationale}".strip()
        failures = " ".join(variant.known_failure_modes)
        config: dict[str, Any] = {
            "campaign_id": draft.campaign_id,
            "variant_id": variant.variant_id,
            "attempt_id": "original",
            "attempt_kind": "original",
            "attempt_provenance": "authored",
            "strategy_name": variant.variant_id,
            "symbol": draft.instrument,
            "dataset_id": draft.dataset.dataset_id,
            "timeframe": draft.timeframe,
            "research_metadata": {
                "authoring_contract": "alphaquest.campaign-draft/v1",
                "mechanic_signature": variant.mechanic_signature,
                "mechanics_review_required": True,
                "mechanics_review_version": 1,
                "mechanics_review": {
                    "mechanic_expresses_edge": variant.mechanic_rationale,
                    "entry_logic_rationale": variant.entry_rationale,
                    "stop_loss_rationale": variant.stop_rationale,
                    "target_exit_rationale": variant.target_rationale,
                    "profitability_rationale": profitability,
                    "known_failure_modes": failures,
                    "pre_test_decision": "approve_for_testing",
                },
                "timeframe_rationale": variant.timeframe_session_rationale,
                "validation_gate": {
                    "required": True,
                    "lane": "bar",
                    "data_subset": validation_subset,
                    "evidence_dir": (
                        f"{self.evidence_root}/{draft.campaign_id}/{variant.variant_id}/"
                        f"{draft.instrument}/mechanics_validation/validation_runs/core"
                    ),
                    "approval_path": (
                        f"{self.research_artifact_root}/validation_approvals/{draft.campaign_id}/"
                        f"{variant.variant_id}/approval.json"
                    ),
                },
            },
            "data": {
                "dataset_id": draft.dataset.dataset_id,
                "source_timeframe": draft.dataset.timeframe,
                "source": draft.dataset.source,
                data_key: draft.dataset.path,
                "symbol": draft.instrument,
                "timezone": draft.dataset.exchange_timezone,
                "source_timezone": draft.dataset.timezone,
                "exchange_timezone": draft.dataset.exchange_timezone,
                "timestamp_semantics": draft.dataset.timestamp_semantics,
                "source_timestamp_semantics": (
                    draft.dataset.source_timestamp_semantics or draft.dataset.timestamp_semantics
                ),
                "source_sha256": draft.dataset.source_sha256,
                "canonical_sha256": draft.dataset.canonical_sha256,
                "roll_policy": draft.dataset.roll_policy,
                "continuous_contract": draft.dataset.continuous_contract,
                "contract_column": draft.dataset.contract_column,
                "contract_count": draft.dataset.contract_count,
                "certified_features": list(draft.dataset.certified_features),
                "rth_start": draft.execution.session_start,
                "rth_end": draft.execution.session_end,
            },
            "apex_rules": {
                "enabled": True,
                "timezone": draft.dataset.exchange_timezone,
                "force_flatten_enabled": True,
                "force_flatten_time": draft.execution.flatten_time,
                "latest_flat_time": draft.execution.latest_flat_time,
                "latest_entry_time": draft.execution.latest_entry_time,
                "cancel_pending_orders_before_flatten": True,
                "no_overnight_positions": True,
                "reject_if_position_after_flatten_deadline": True,
                "reject_if_pending_order_after_flatten_deadline": True,
                "reject_if_entry_after_latest_entry_time": True,
            },
            "strategy": {
                "entry": _executable_binding(entry),
                "sl": _executable_binding(stop),
                "tp": _executable_binding(target),
                "flatten_time": draft.execution.flatten_time,
            },
            "core": {
                "data_subset": full_subset,
                "initial_balance": draft.execution.initial_balance,
                "tick_size": draft.execution.tick_size,
                "point_value": draft.execution.point_value,
                "tick_value": draft.execution.tick_value,
                "commission_per_contract": draft.execution.commission_per_contract,
                "slippage_ticks": draft.execution.slippage_ticks,
                "position_sizing": {"mode": "fixed_contracts", "contracts": draft.execution.contracts},
                "flatten_time": draft.execution.flatten_time,
                "max_trades_per_day": 1,
            },
            "benchmarks": _benchmark_defaults(),
            "core_grid": {
                "data_subset": deepcopy(full_subset),
                "objective": "MAR",
                "min_profitable_iteration_rate": 0.7,
                "retain_iteration_reports": False,
                "parameters": deepcopy(grid),
            },
            "monkey": {
                "data_subset": deepcopy(full_subset),
                "runs": 300,
                "seed": 7,
                "beat_threshold": 0.9,
                "retain_iteration_reports": False,
                "constraints": {
                    "trade_count_tolerance_pct": 0.05,
                    "long_short_ratio_tolerance": 0.05,
                    "average_bars_tolerance_pct": 0.1,
                    "duration_shape": 0.7,
                    "rth_only": True,
                    "enforce_non_overlapping": True,
                },
            },
            "wfa": {
                "data_subset": deepcopy(full_subset),
                "mode": "unanchored",
                "train_months": 48,
                "test_months": 12,
                "step_months": 12,
                "objective": "MAR",
                "selection_exclusive_min_trades_per_year": 50,
                "early_exit_min_train_profit_factor": 1.0,
                "parameters": deepcopy(grid),
            },
            "campaign_tests": {
                "stage_order": [
                    "limited_core_grid_test",
                    "limited_monkey_test",
                    "walk_forward_analysis",
                    "wfa_oos_monkey_test",
                    "wfa_oos_monte_carlo",
                    "simulated_incubation_core",
                    "simulated_incubation_monkey",
                    "acceptance_oos_test",
                ],
                "limited_core_grid_test": {"enabled": True},
                "limited_monkey_test": {"enabled": True},
                "walk_forward_analysis": {"enabled": True},
                "wfa_oos_monkey_test": {"enabled": True},
                "wfa_oos_monte_carlo": {"enabled": True},
                "simulated_incubation_core": {"enabled": True},
                "simulated_incubation_monkey": {"enabled": True},
                "acceptance_oos_test": {"enabled": True, "train_months": 24, "test_months": 6},
            },
            "prop_rules": {
                "profile": draft.execution.prop_profile,
                "starting_balance": draft.execution.initial_balance,
                "max_contracts": draft.execution.contracts,
                "no_overnight_positions": True,
                "force_flatten_time": draft.execution.flatten_time,
            },
            "monte_carlo": {
                "trade_source": "core",
                "runs": 300,
                "seed": 11,
                "path_months": 6,
                "skip_trade_probability": 0.05,
                "adverse_slippage_per_trade": draft.execution.tick_value,
                "position_sizing": {"mode": "fixed_contracts", "contracts": draft.execution.contracts},
                "cluster_losses": True,
                "retain_path_trades": False,
                "retain_path_events": False,
            },
            "test_run_id": "run1",
        }
        if draft.dataset.roll_calendar:
            config["data"]["roll_calendar"] = draft.dataset.roll_calendar
            config["data"]["roll_calendar_sha256"] = draft.dataset.roll_calendar_sha256
        return config

    def _strategy_spec(
        self,
        draft: CampaignDraftV1,
        variants: list[tuple[VariantDraftV1, ModuleBindingV1, ModuleBindingV1, ModuleBindingV1]],
        draft_sha256: str,
    ) -> dict[str, Any]:
        return {
            "schema": STRATEGY_SPEC_SCHEMA,
            "campaign_id": draft.campaign_id,
            "draft_sha256": draft_sha256,
            "frozen": True,
            "hypothesis": draft.hypothesis,
            "expected_mechanism": draft.expected_mechanism,
            "holding_horizon": draft.holding_horizon,
            "known_failure_modes": list(draft.known_failure_modes),
            "authoring_lane": draft.authoring_lane,
            "certified_recipe": draft.certified_recipe,
            "dataset": draft.dataset.model_dump(mode="json", by_alias=True),
            "execution": draft.execution.model_dump(mode="json"),
            "variants": [
                {
                    "variant_id": variant.variant_id,
                    "title": variant.title,
                    "mechanic_signature": variant.mechanic_signature,
                    "entry": entry.model_dump(mode="json"),
                    "stop": stop.model_dump(mode="json"),
                    "target": target.model_dump(mode="json"),
                    "rationales": {
                        "mechanic": variant.mechanic_rationale,
                        "entry": variant.entry_rationale,
                        "stop": variant.stop_rationale,
                        "target": variant.target_rationale,
                        "timeframe_session": variant.timeframe_session_rationale,
                    },
                }
                for variant, entry, stop, target in variants
            ],
        }

    def _authoring_manifest(
        self,
        draft: CampaignDraftV1,
        variants: list[tuple[VariantDraftV1, ModuleBindingV1, ModuleBindingV1, ModuleBindingV1]],
        draft_sha256: str,
        *,
        campaign: Mapping[str, Any],
        variant_configs: Mapping[str, Mapping[str, Any]],
        strategy_spec: Mapping[str, Any],
    ) -> dict[str, Any]:
        return {
            "schema": AUTHORING_MANIFEST_SCHEMA,
            "campaign_id": draft.campaign_id,
            "draft_schema": "alphaquest.campaign-draft/v1",
            "draft_sha256": draft_sha256,
            "dataset_id": draft.dataset.dataset_id,
            "dataset_canonical_sha256": draft.dataset.canonical_sha256,
            "authoring_lane": draft.authoring_lane,
            "certified_recipe": draft.certified_recipe,
            "compiler": "alphaquest.authoring.CampaignCompiler/v1",
            "created_at": draft.created_at,
            "variant_count": 5,
            "variant_mechanic_signatures": {
                variant.variant_id: variant.mechanic_signature for variant, *_ in variants
            },
            "compiled_document_sha256": {
                "campaign.yaml": _object_sha256(campaign),
                "strategy_spec.yaml": _object_sha256(strategy_spec),
                **{
                    f"variants/{variant_id}/config.yaml": _object_sha256(config)
                    for variant_id, config in variant_configs.items()
                },
            },
            "planned_files": [
                "campaign.yaml",
                "strategy_spec.yaml",
                "authoring_manifest.json",
                *[f"variants/{variant.variant_id}/config.yaml" for variant, *_ in variants],
            ],
            "generated_python_stubs": False,
        }


def _executable_binding(binding: ModuleBindingV1) -> dict[str, Any]:
    return {"module": binding.module, "params": deepcopy(binding.params)}


def _parameter_grid(
    entry: ModuleBindingV1,
    stop: ModuleBindingV1,
    target: ModuleBindingV1,
) -> dict[str, list[Any]]:
    grid: dict[str, list[Any]] = {}
    for prefix, binding in (("entry", entry), ("sl", stop), ("tp", target)):
        for parameter, values in binding.parameter_grid.items():
            grid[f"{prefix}.params.{parameter}"] = deepcopy(values)
    return grid


def _benchmark_defaults() -> dict[str, Any]:
    return {
        "min_trades_per_year": 50,
        "preferred_min_total_trades": 500,
        "min_profit_factor": 1.3,
        "min_total_net_profit": 0,
        "min_expectancy_r": 0.05,
        "min_win_rate": 0.4,
        "max_drawdown_pct": 0.1,
        "min_cagr": 0.0,
        "min_mar": 0.5,
        "max_daily_loss": 1500,
        "max_consecutive_losses": 8,
        "max_best_day_concentration": 0.4,
        "min_positive_month_rate": 0.5,
        "min_wfa_profitable_window_rate": 0.7,
        "min_monte_carlo_prop_pass_chance": 0.5,
    }


def mechanics_validation_subset(
    start_value: str,
    end_value: str,
    *,
    entry: ModuleBindingV1 | None = None,
) -> dict[str, str]:
    try:
        start = date.fromisoformat(start_value[:10])
        end = date.fromisoformat(end_value[:10])
    except ValueError as exc:
        raise CampaignCompilationError("dataset coverage must start with ISO dates") from exc
    if end < start:
        raise CampaignCompilationError("dataset coverage_end cannot precede coverage_start")
    window_days = 14
    if entry is not None and entry.module == "daily_time_series_momentum":
        # Mechanics validation must include causal warm-up plus several unseen
        # decision sessions.  This window depends only on the frozen module
        # contract, never on PnL or favorable dates.
        lookback = int(entry.params.get("lookback_sessions", 20))
        confirmation = int(entry.params.get("confirmation_sessions", 1))
        required_sessions = lookback + confirmation + 10
        window_days = max(window_days, (required_sessions * 7 + 4) // 5 + 7)
    return {
        "start_date": start.isoformat(),
        "end_date": min(end, start + timedelta(days=window_days)).isoformat(),
    }


def _timeframe_minutes(value: str) -> float:
    amount = int(value[:-1])
    unit = value[-1]
    if unit == "m":
        return float(amount)
    if unit == "h":
        return float(amount * 60)
    return float(amount * 1440)


def _require_matching_or_set(params: dict[str, Any], name: str, expected: float) -> None:
    if name in params and float(params[name]) != float(expected):
        raise CampaignCompilationError(
            f"module parameter {name!r} must match the reviewed execution setting {expected}"
        )
    params[name] = expected


def _object_sha256(value: Any) -> str:
    encoded = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


__all__ = [
    "AUTHORING_MANIFEST_SCHEMA",
    "STRATEGY_SPEC_SCHEMA",
    "CampaignCompilationError",
    "CampaignCompiler",
    "CompiledCampaign",
    "mechanics_validation_subset",
]
