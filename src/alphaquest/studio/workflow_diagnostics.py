"""Read-only Studio workflow diagnostics and conservative planning forecasts."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Any, Mapping, Sequence
from math import prod

from alphaquest.research.policy import load_research_policy
from alphaquest.research.storage import load_storage_layout


def dataset_readiness_forecast(dataset: Mapping[str, Any]) -> dict[str, Any]:
    """Estimate policy coverage before PnL without claiming strategy feasibility."""

    policy = load_research_policy()
    wfa = policy.walk_forward_analysis
    objective_floors = policy.objective_floors
    minimum_windows = int(objective_floors["minimum_complete_wfa_windows"])
    required_months = (
        int(wfa["train_months"])
        + int(wfa["test_months"])
        + int(wfa["step_months"]) * max(0, minimum_windows - 1)
        + int(policy.simulated_incubation["test_months"])
        + int(policy.acceptance_oos["test_months"])
    )
    start = _parse_datetime(dataset.get("coverage_start"))
    end = _parse_datetime(dataset.get("coverage_end"))
    available_months = None
    if start is not None and end is not None and end >= start:
        available_months = round((end - start).total_seconds() / (30.4375 * 86400), 1)
    quality = str(dataset.get("quality_verdict") or "").upper()
    blockers: list[str] = []
    if quality != "PASS":
        blockers.append("Dataset quality must be PASS before publication or testing.")
    if available_months is None:
        blockers.append("Coverage start and end are unavailable or invalid.")
    elif available_months < required_months:
        blockers.append(
            f"Only {available_months:g} months are available; the current sequential policy needs "
            f"about {required_months} months for three WFA windows plus both locked holdouts."
        )
    return {
        "schema": "alphaquest.data-readiness-forecast/v1",
        "status": "READY" if not blockers else "NOT_READY",
        "required_months": required_months,
        "available_months": available_months,
        "minimum_wfa_windows": minimum_windows,
        "coverage_start": dataset.get("coverage_start"),
        "coverage_end": dataset.get("coverage_end"),
        "blockers": blockers,
        "limitations": [
            "This checks calendar coverage and governed data quality only.",
            "It cannot predict signal frequency, trade count, profitability, or whether every session is usable.",
        ],
    }


def workspace_diagnostics(
    project_root: str | Path,
    *,
    index_refresh: Mapping[str, Any],
) -> dict[str, Any]:
    root = Path(project_root).resolve()
    layout = load_storage_layout(root)
    registry = layout.catalog_root / "research_registry.sqlite"
    frontend_index = root / "src" / "alphaquest" / "studio" / "web_assets" / "index.html"
    required_roots = {
        "active_campaigns": layout.active_campaign_root,
        "evidence": layout.evidence_roots[0],
        "datasets": layout.dataset_root,
        "runtime": layout.studio_runtime_root,
    }
    checks = [
        {
            "id": "research_registry",
            "label": "Research registry",
            "status": "PASS" if registry.is_file() else "FAIL",
            "repairable": True,
        },
        {
            "id": "studio_assets",
            "label": "Built Studio assets",
            "status": "PASS" if frontend_index.is_file() else "FAIL",
            "repairable": False,
        },
        *[
            {
                "id": f"storage_{name}",
                "label": f"{name.replace('_', ' ').title()} root",
                "status": "PASS" if path.is_dir() else "FAIL",
                "repairable": False,
            }
            for name, path in required_roots.items()
        ],
    ]
    failed = [check for check in checks if check["status"] != "PASS"]
    return {
        "schema": "alphaquest.workspace-diagnostics/v1",
        "status": "PASS" if not failed and not index_refresh.get("error") else "NEEDS_ATTENTION",
        "checks": checks,
        "index_refresh": dict(index_refresh),
        "repair": {
            "available": any(check["repairable"] for check in failed),
            "scope": "Rebuild derived registry, exports, and views only; source definitions and evidence are never rewritten.",
        },
        "cache_policy": {
            "event_precompute_cache": "ENABLED_EXACT_INPUTS_ONLY",
            "cross_attempt_result_cache": "DISABLED",
            "required_identity": [
                "dataset SHA-256",
                "compiled config SHA-256",
                "implementation SHA-256",
                "certification-manifest SHA-256",
                "methodology-policy SHA-256",
                "stage name and deterministic seed",
            ],
            "note": "A completed attempt is never silently reused as a new attempt's scientific result.",
        },
        "legacy_parity": {
            "decision": "RETAIN_LEGACY_FALLBACK",
            "safe_to_remove": False,
            "verified_surfaces": [
                "React authoring and publication",
                "mechanics and candidate review",
                "campaign testing and governed results",
                "forward incubation and deployment review",
            ],
            "remaining_gate": (
                "Remove a legacy interface only in a dedicated migration after route-by-route parity, "
                "accessibility, failure recovery, and expert escape-hatch tests pass."
            ),
        },
    }


def workload_forecast(config: Mapping[str, Any]) -> dict[str, Any]:
    """Return exact declared counts and a non-promissory workload class."""

    policy = load_research_policy()
    core = config.get("core_grid") if isinstance(config.get("core_grid"), Mapping) else {}
    parameters = core.get("parameters") if isinstance(core.get("parameters"), Mapping) else {}
    dimensions = [len(value) for value in parameters.values() if isinstance(value, list)]
    combinations = prod(dimensions) if dimensions else 1
    monte = config.get("wfa_oos_monte_carlo")
    monte_runs = (
        int(monte.get("runs") or policy.wfa_oos_monte_carlo["runs"])
        if isinstance(monte, Mapping)
        else int(policy.wfa_oos_monte_carlo["runs"])
    )
    minimum_windows = int(policy.objective_floors["minimum_complete_wfa_windows"])
    workload_units = combinations * (1 + minimum_windows) + monte_runs
    if workload_units < 10_000:
        workload_class = "BOUNDED"
    elif workload_units < 50_000:
        workload_class = "SUBSTANTIAL"
    else:
        workload_class = "HEAVY"
    return {
        "schema": "alphaquest.workload-forecast/v1",
        "parameter_combinations": combinations,
        "minimum_wfa_windows": minimum_windows,
        "monte_carlo_paths": monte_runs,
        "declared_workload_units": workload_units,
        "workload_class": workload_class,
        "retention": {
            "iteration_reports": "not retained" if not core.get("retain_iteration_reports") else "retained",
            "monte_carlo_path_trades": "not retained",
        },
        "limitations": (
            "Counts are exact from the frozen contract; workload units are a relative planning measure, "
            "not a wall-clock or disk-size promise. Event density and hardware dominate actual runtime."
        ),
    }
def global_next_actions(
    *,
    drafts: Sequence[Mapping[str, Any]],
    campaigns: Sequence[Mapping[str, Any]],
    reviews: Sequence[Mapping[str, Any]],
    jobs: Sequence[Mapping[str, Any]],
) -> list[dict[str, Any]]:
    actions: list[dict[str, Any]] = []
    for review in reviews:
        review_type = str(review.get("type") or "mechanics")
        campaign_id = str(review.get("campaign_id") or "")
        actions.append(
            {
                "priority": 10 if review_type == "mechanics" else 20,
                "kind": "review",
                "campaign_id": campaign_id,
                "label": "Review mechanics" if review_type == "mechanics" else "Review candidate",
                "detail": "Human decision required; no automated job can clear this gate.",
                "href": f"/reviews?type={review_type}&campaign={campaign_id}",
            }
        )
    for job in jobs:
        state = str(job.get("operational_state") or job.get("state") or "")
        if state not in {"BLOCKED", "FAILED_OPERATIONAL"}:
            continue
        campaign_id = str(job.get("campaign_id") or "")
        actions.append(
            {
                "priority": 5,
                "kind": "operational_exception",
                "campaign_id": campaign_id,
                "label": "Resolve blocked job",
                "detail": str(job.get("blocked_reason") or job.get("error") or "Inspect the durable job record."),
                "href": f"/research/{campaign_id}/testing" if campaign_id else "/research",
            }
        )
    for campaign in campaigns:
        action = (campaign.get("workflow_context") or {}).get("primary_action") or {}
        if not action:
            continue
        campaign_id = str(campaign.get("campaign_id") or "")
        section = str(action.get("section") or "overview")
        href = (
            f"/reviews?type=mechanics&campaign={campaign_id}"
            if section == "reviews"
            else f"/research/{campaign_id}/{section}"
        )
        actions.append(
            {
                "priority": 30,
                "kind": "campaign",
                "campaign_id": campaign_id,
                "label": str(action.get("label") or "Continue campaign"),
                "detail": str(campaign.get("title") or campaign_id),
                "href": href,
            }
        )
    for draft in drafts:
        campaign_id = str(draft.get("campaign_id") or "")
        step = max(1, int(draft.get("wizard_step") or 1))
        actions.append(
            {
                "priority": 40,
                "kind": "draft",
                "campaign_id": campaign_id,
                "label": f"Continue draft at step {step}",
                "detail": str(draft.get("title") or campaign_id),
                "href": f"/research/{campaign_id}/design/{step}",
            }
        )
    deduplicated: dict[tuple[str, str, str], dict[str, Any]] = {}
    for action in actions:
        key = (action["kind"], action["campaign_id"], action["label"])
        deduplicated.setdefault(key, action)
    return sorted(deduplicated.values(), key=lambda item: (item["priority"], item["campaign_id"]))


def _parse_datetime(value: Any) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        return None


__all__ = [
    "dataset_readiness_forecast",
    "global_next_actions",
    "workload_forecast",
    "workspace_diagnostics",
]
