"""Authoritative campaign -> variant -> run explanation projection."""

from __future__ import annotations

import json
from pathlib import Path
import sqlite3
from typing import Any

import yaml

from alphaquest.research.lineage import inspect_run_lineage
from alphaquest.research.storage import load_storage_layout, resolve_recorded_path


def explain_research(
    campaign_id: str,
    *,
    database_path: str | Path = "catalogs/research_registry.sqlite",
    project_root: str | Path = ".",
    variant_id: str | None = None,
    run_id: str | None = None,
) -> dict[str, Any]:
    root = Path(project_root).resolve()
    database = _resolve(root, database_path)
    layout = load_storage_layout(root)
    campaign_path = next(
        (
            campaign_root / campaign_id / "campaign.yaml"
            for campaign_root in (*layout.campaign_roots, root / "campaigns")
            if (campaign_root / campaign_id / "campaign.yaml").is_file()
        ),
        layout.active_campaign_root / campaign_id / "campaign.yaml",
    )
    campaign = _read_yaml(campaign_path)
    if not campaign:
        raise ValueError(f"authored campaign definition is missing: {campaign_path}")

    with sqlite3.connect(database) as connection:
        connection.row_factory = sqlite3.Row
        campaign_row = connection.execute("SELECT * FROM campaigns WHERE campaign_id = ?", (campaign_id,)).fetchone()
        if campaign_row is None:
            raise ValueError(f"campaign is not registered: {campaign_id}")
        variants = [
            dict(row)
            for row in connection.execute(
                "SELECT * FROM variants WHERE campaign_id = ? ORDER BY variant_id", (campaign_id,)
            ).fetchall()
        ]
        selected_variant = _select_variant(variants, variant_id)
        run = _select_run(connection, campaign_id, selected_variant, run_id)
        artifacts = []
        if run:
            artifacts = [
                dict(row)
                for row in connection.execute(
                    "SELECT artifact_kind, path, sha256, size_bytes FROM artifacts WHERE run_uid = ? ORDER BY artifact_kind",
                    (run["run_uid"],),
                ).fetchall()
            ]

    variant_explanations = [_variant_explanation(root, campaign, row) for row in variants]
    lineage = inspect_run_lineage(run["output_dir"], project_root=root) if run and run.get("output_dir") else None
    final_verdict = run["verdict"] if run else (campaign_row["authored_decision"] or "NEEDS MANUAL REVIEW")
    if final_verdict not in {"PASS", "FAIL", "NEEDS MANUAL REVIEW"}:
        final_verdict = "NEEDS MANUAL REVIEW"
    payload = {
        "schema": "alphaquest.research-explanation/v1",
        "generated_projection": True,
        "authority_note": (
            "This card is generated from authored definitions, immutable run manifests/config snapshots, "
            "hashes, and the rebuildable registry. The card and registry are navigation, not result authority."
        ),
        "campaign": {
            "campaign_id": campaign_id,
            "title": campaign.get("title"),
            "hypothesis": campaign.get("hypothesis"),
            "sources": campaign.get("sources") or [],
            "edge_family": campaign.get("edge_family"),
            "economic_edge_fingerprint": campaign.get("economic_edge_fingerprint"),
            "duplicate_edge_review": campaign.get("duplicate_edge_review"),
            "definition_path": _display(root, campaign_path),
            "definition_status": campaign.get("status"),
            "authored_decision": campaign.get("decision"),
            "lifecycle_state": campaign_row["lifecycle_state"],
            "variant_count": campaign_row["variant_count"],
            "attempt_count": campaign_row["attempt_count"],
        },
        "variants": variant_explanations,
        "selected_variant": selected_variant,
        "run": run,
        "lineage": lineage,
        "registry_artifacts": artifacts,
        "final_verdict": final_verdict,
        "final_verdict_reason": _verdict_reason(run, lineage, campaign),
    }
    return payload


def explanation_markdown(payload: dict[str, Any]) -> str:
    campaign = payload["campaign"]
    lines = [
        f"# Research Card: {campaign['campaign_id']}",
        "",
        "> Generated projection. Authoritative evidence remains in the linked authored definition and run artifacts.",
        "",
        "## Hypothesis And Economic Identity",
        "",
        f"- Thesis: {campaign.get('hypothesis') or 'NEEDS MANUAL REVIEW - hypothesis missing'}",
        f"- Edge family: `{campaign.get('edge_family') or 'missing'}`",
        f"- Economic fingerprint: `{json.dumps(campaign.get('economic_edge_fingerprint'), sort_keys=True)}`",
        f"- Duplicate-edge review: `{json.dumps(campaign.get('duplicate_edge_review'), sort_keys=True)}`",
        f"- Authored definition: `{campaign.get('definition_path')}`",
        "",
        "## Variant Mechanics",
        "",
    ]
    for variant in payload["variants"]:
        lines.extend(
            [
                f"### {variant['variant_id']}",
                "",
                f"- Material distinction: {variant.get('material_difference') or 'NEEDS MANUAL REVIEW'}",
                f"- Mechanics lock: `{json.dumps(variant.get('mechanics'), sort_keys=True)}`",
                f"- Parameter space: `{json.dumps(variant.get('parameter_space'), sort_keys=True)}`",
                f"- Source config: `{variant.get('definition_path')}` (`{variant.get('config_hash')}`)",
                "",
            ]
        )
    run = payload.get("run")
    lineage = payload.get("lineage")
    lines.extend(["## Selected Run", ""])
    if not run:
        lines.extend(["No generated run was selected or registered.", ""])
    else:
        lines.extend(
            [
                f"- Run UID: `{run.get('run_uid')}`",
                f"- Variant / run ID: `{run.get('variant_id')}` / `{run.get('test_run_id')}`",
                f"- Recorded verdict: **{run.get('verdict')}**",
                f"- Failed stage: `{run.get('failed_stage') or 'none'}`",
                f"- Summary: `{run.get('summary_path')}`",
                "",
            ]
        )
    if lineage:
        data = lineage["data"]
        lines.extend(
            [
                "## Data, Execution, And Lineage",
                "",
                f"- Dataset/source/vendor: `{data.get('dataset_id')}` / `{data.get('source_type')}` / `{data.get('vendor')}`",
                f"- Date range: `{json.dumps(data.get('date_range'), sort_keys=True)}`",
                f"- Timezone/session: `{data.get('timezone')}` / `{json.dumps(data.get('session'), sort_keys=True)}`",
                f"- Contracts/roll: `{json.dumps(data.get('contract'), sort_keys=True)}`",
                f"- Costs: `{json.dumps(data.get('costs'), sort_keys=True)}`",
                f"- Transformations: `{json.dumps(data.get('transformations'), sort_keys=True)}`",
                f"- Hash reconciliation: `{json.dumps(lineage.get('hashes'), sort_keys=True)}`",
                f"- Lineage verdict: **{lineage.get('lineage_verdict')}**",
                "",
                "## Validation And Stages",
                "",
                f"- Validation: `{json.dumps(lineage.get('validation'), sort_keys=True)}`",
            ]
        )
        for stage in lineage.get("stages") or []:
            lines.append(
                f"- `{stage.get('stage')}`: `{stage.get('status')}`; passed={stage.get('passed')}; "
                f"reason={stage.get('reason') or 'none recorded'}"
            )
        lines.extend(["", "## Authoritative Artifacts", ""])
        lines.extend(f"- `{path}`" for path in lineage.get("authoritative_artifacts") or [])
        lines.extend(["", f"> {lineage.get('snapshot_caveat')}", ""])
        if lineage.get("errors") or lineage.get("missing_evidence"):
            lines.extend(["## Retained Risks", ""])
            lines.extend(f"- ERROR: {item}" for item in lineage.get("errors") or [])
            lines.extend(f"- NEEDS MANUAL REVIEW: {item}" for item in lineage.get("missing_evidence") or [])
            lines.append("")
    lines.extend(
        [
            "## Final Verdict",
            "",
            payload["final_verdict_reason"],
            "",
            f"**{payload['final_verdict']}**",
            "",
        ]
    )
    return "\n".join(lines)


def _select_variant(variants: list[dict[str, Any]], variant_id: str | None) -> str | None:
    if variant_id is None:
        return None
    if not any(row["variant_id"] == variant_id for row in variants):
        raise ValueError(f"unknown authored variant: {variant_id}")
    return variant_id


def _select_run(
    connection: sqlite3.Connection,
    campaign_id: str,
    variant_id: str | None,
    run_id: str | None,
) -> dict[str, Any] | None:
    where = ["campaign_id = ?"]
    params: list[Any] = [campaign_id]
    if variant_id:
        where.append("variant_id = ?")
        params.append(variant_id)
    if run_id:
        where.append("(run_uid = ? OR test_run_id = ?)")
        params.extend((run_id, run_id))
    query = "SELECT * FROM runs WHERE " + " AND ".join(where) + " ORDER BY COALESCE(updated_at, '') DESC LIMIT 1"
    row = connection.execute(query, tuple(params)).fetchone()
    if run_id and row is None:
        raise ValueError(f"unknown run for campaign {campaign_id}: {run_id}")
    return dict(row) if row else None


def _variant_explanation(root: Path, campaign: dict[str, Any], row: dict[str, Any]) -> dict[str, Any]:
    path = _resolve(root, row["definition_path"])
    cfg = _read_yaml(path)
    strategy = cfg.get("strategy") if isinstance(cfg.get("strategy"), dict) else {}
    research = cfg.get("research_metadata") if isinstance(cfg.get("research_metadata"), dict) else {}
    distinctions = campaign.get("variant_distinctions") if isinstance(campaign.get("variant_distinctions"), dict) else {}
    distinction = distinctions.get(row["variant_id"]) if isinstance(distinctions.get(row["variant_id"]), dict) else {}
    parameter_space = {}
    for section in ("core_grid", "wfa"):
        value = cfg.get(section)
        if isinstance(value, dict) and isinstance(value.get("parameters"), dict):
            parameter_space[section] = value["parameters"]
    return {
        "variant_id": row["variant_id"],
        "symbol": row.get("symbol"),
        "timeframe": row.get("timeframe"),
        "dataset_id": row.get("dataset_id"),
        "definition_path": row["definition_path"],
        "config_hash": row.get("config_hash"),
        "material_difference": distinction.get("material_difference") or research.get("mechanic"),
        "mechanics": {
            "entry": strategy.get("entry"),
            "stop": strategy.get("sl"),
            "target_exit": strategy.get("tp"),
            "forced_flatten": strategy.get("flatten_time"),
            "mechanics_review": research.get("mechanics_review"),
        },
        "parameter_space": parameter_space,
        "validation_gate": research.get("validation_gate"),
    }


def _verdict_reason(run: dict[str, Any] | None, lineage: dict[str, Any] | None, campaign: dict[str, Any]) -> str:
    if run:
        if lineage and lineage["lineage_verdict"] != "PASS":
            return (
                f"Recorded run verdict is {run['verdict']}; independent lineage coverage is "
                f"{lineage['lineage_verdict']}. Missing or mismatched evidence is retained above."
            )
        return f"Terminal verdict is taken from immutable generated run evidence: {run['verdict']}."
    decision = campaign.get("decision")
    if decision in {"PASS", "FAIL", "NEEDS MANUAL REVIEW"}:
        return f"No run selected; terminal verdict is taken from the authored campaign decision: {decision}."
    return "No authoritative terminal run or strict authored decision is available."


def _resolve(root: Path, path: str | Path) -> Path:
    return resolve_recorded_path(path, project_root=root)


def _display(root: Path, path: Path) -> str:
    try:
        return str(path.resolve().relative_to(root))
    except ValueError:
        return str(path.resolve())


def _read_yaml(path: Path) -> dict[str, Any]:
    if not path.is_file():
        return {}
    value = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    return value if isinstance(value, dict) else {}
