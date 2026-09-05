from __future__ import annotations

import multiprocessing
from pathlib import Path
import shutil
import subprocess

import pytest

from alphaquest.research.edge_backlog import (
    EdgeBacklogAuthorityError,
    EdgeBacklogIntegrityError,
    EdgeBacklogStore,
)
from alphaquest.research.edge_backlog_io import (
    atomic_replace_repository_file,
    exclusive_write_repository_file,
    repository_file_lock,
)
from alphaquest.research.edge_backlog_taxonomy import bundled_taxonomy_ref


def _write_layout(root: Path) -> None:
    target = root / "config/storage_layout.yaml"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes((Path(__file__).parents[1] / "config/storage_layout.yaml").read_bytes())


def _initialize_git(root: Path) -> None:
    subprocess.run(["git", "init", "-q", str(root)], check=True)
    subprocess.run(["git", "-C", str(root), "config", "user.name", "P2 Security Test"], check=True)
    subprocess.run(
        ["git", "-C", str(root), "config", "user.email", "p2-security@example.test"],
        check=True,
    )
    subprocess.run(["git", "-C", str(root), "add", "config/storage_layout.yaml"], check=True)
    subprocess.run(["git", "-C", str(root), "commit", "-q", "-m", "initial layout"], check=True)


def _capture_entry(store: EdgeBacklogStore):
    observation = store.capture_observation(
        {
            "observation_id": "obs.security",
            "statement": "Inventory pressure persisted after the observed interval.",
            "statement_kind": "RESEARCHER_SUMMARY",
            "evidence_refs": [
                {
                    "source_id": "source.security",
                    "source_kind": "PAPER",
                    "locator": "doi:10/security",
                    "claim_locator": "result-one",
                    "evidence_time": "2026-09-01T00:00:00Z",
                    "integrity": "LOCATOR_ONLY",
                    "content_sha256": None,
                }
            ],
            "known_conflicts": [],
        },
        actor_id="codex",
    )
    return store.create_entry(
        {
            "classification_status": "CLASSIFIED",
            "taxonomy_ref": bundled_taxonomy_ref().model_dump(mode="json"),
            "governance_scope": "PRE_HYPOTHESIS_BACKLOG_ONLY",
            "p1_evidence_eligibility": "NOT_CURRENT_P1_EVIDENCE",
            "economic_concepts": {
                "instrument_ids": ["ES"],
                "market_behavior_code": "INVENTORY_IMBALANCE",
                "causal_mechanism_code": "DELAYED_INVENTORY_ADJUSTMENT",
                "beneficiary_counterparty_codes": ["LIQUIDITY_PROVIDERS"],
                "cost_bearer_counterparty_codes": ["HEDGERS"],
                "transfer_rationale_code": "INVENTORY_RISK_COMPENSATION",
                "information_input_codes": ["POSITIONING_AND_INVENTORY_PROXY", "PRICE"],
                "information_availability_code": "AVAILABLE_AFTER_INTERVAL",
                "expected_effect_code": "PRICE_CONTINUATION",
                "holding_horizon_code": "INTRASESSION",
                "market_context_codes": ["OPENING_AUCTION"],
            },
            "unclassified_reason": None,
            "observation_refs": [
                {
                    "observation_id": observation.observation_id,
                    "observation_revision_sha256": observation.record_sha256,
                    "role": "MOTIVATING",
                }
            ],
        },
        actor_id="codex",
    )


@pytest.mark.parametrize("boundary", ["canonical-root", "cache-parent", "lock-parent"])
def test_p2_boundaries_reject_external_symlinks_without_external_writes(
    tmp_path: Path,
    boundary: str,
) -> None:
    _write_layout(tmp_path)
    external = tmp_path / "external-target"
    external.mkdir()
    if boundary == "canonical-root":
        target = tmp_path / "research/edge_backlog"
    elif boundary == "cache-parent":
        target = tmp_path / "catalogs"
    else:
        target = tmp_path / "run-store/studio-runtime"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.symlink_to(external, target_is_directory=True)

    with pytest.raises(EdgeBacklogIntegrityError, match="storage boundary"):
        EdgeBacklogStore(tmp_path)

    assert list(external.iterdir()) == []


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("edge_backlog_root", "research/relocated-edge-backlog"),
        ("edge_backlog_root", "../outside"),
        ("edge_backlog_history_index", "/tmp/outside-cache.jsonl"),
        ("studio_runtime_root", "../outside-runtime"),
    ],
)
def test_p2_layout_paths_reject_alternative_absolute_or_escaping_targets(
    tmp_path: Path,
    field: str,
    value: str,
) -> None:
    _write_layout(tmp_path)
    layout = tmp_path / "config/storage_layout.yaml"
    lines = layout.read_text(encoding="utf-8").splitlines()
    layout.write_text(
        "\n".join(f"{field}: {value}" if line.startswith(f"{field}:") else line for line in lines)
        + "\n",
        encoding="utf-8",
    )

    with pytest.raises(EdgeBacklogIntegrityError, match="storage boundary"):
        EdgeBacklogStore(tmp_path)


def _dirfd_race_worker(
    root: str,
    operation: str,
    relative: str,
    barrier,
    results,
) -> None:
    from alphaquest.research import edge_backlog_io

    def pause(selected: str, _relative: str) -> None:
        if selected == operation:
            barrier.wait(timeout=20)
            barrier.wait(timeout=20)

    edge_backlog_io._TEST_AFTER_PARENT_OPEN = pause
    try:
        if operation == "exclusive-write":
            exclusive_write_repository_file(root, relative, b"canonical\n")
        elif operation == "cache-replace":
            atomic_replace_repository_file(root, relative, b"cache\n")
        else:
            with repository_file_lock(root, relative, exclusive=True):
                pass
        results.put(("PASS", ""))
    except Exception as exc:  # pragma: no cover - asserted in the parent
        results.put(("ERROR", f"{type(exc).__name__}: {exc}"))


@pytest.mark.parametrize(
    ("operation", "relative", "swapped_relative"),
    [
        (
            "exclusive-write",
            "research/edge_backlog/observations/obs.race/revisions/000001.json",
            "research/edge_backlog",
        ),
        ("cache-replace", "catalogs/edge_backlog_history.jsonl", "catalogs"),
        ("lock-open", "run-store/studio-runtime/edge-backlog.lock", "run-store/studio-runtime"),
    ],
)
def test_repository_dirfds_prevent_symlink_substitution_from_redirecting_writes(
    tmp_path: Path,
    operation: str,
    relative: str,
    swapped_relative: str,
) -> None:
    _write_layout(tmp_path)
    external = tmp_path / "external-race-target"
    external.mkdir()
    context = multiprocessing.get_context("fork")
    barrier = context.Barrier(2)
    results = context.Queue()
    process = context.Process(
        target=_dirfd_race_worker,
        args=(str(tmp_path), operation, relative, barrier, results),
    )
    process.start()
    barrier.wait(timeout=20)
    swapped = tmp_path / swapped_relative
    held = swapped.with_name(swapped.name + ".held")
    swapped.rename(held)
    swapped.symlink_to(external, target_is_directory=True)
    barrier.wait(timeout=20)
    process.join(timeout=20)

    assert process.exitcode == 0
    assert results.get(timeout=5) == ("PASS", "")
    assert list(external.iterdir()) == []
    swapped.unlink()
    held.rename(swapped)
    assert (tmp_path / relative).is_file()


def test_human_decision_creation_and_forged_history_fail_outside_git(tmp_path: Path) -> None:
    attempted_root = tmp_path / "attempted"
    _write_layout(attempted_root)
    attempted_store = EdgeBacklogStore(attempted_root)
    attempted_entry = _capture_entry(attempted_store)
    snapshot = attempted_store.duplicate_snapshot(attempted_entry.entry_id)

    with pytest.raises(EdgeBacklogAuthorityError, match="Git-backed"):
        attempted_store.record_human_decision(
            attempted_entry.entry_id,
            disposition="REVIEWED_CONTINUE",
            duplicate_resolution="DISTINCT_EDGE",
            candidate_snapshot_sha256=snapshot["snapshot_sha256"],
            reason_codes=["OTHER"],
            rationale="This human decision must not exist without a Git authority.",
            reviewer_id="owner",
        )
    assert not list(attempted_store.root.glob("entries/*/decisions/*.json"))
    assert attempted_store.validate()["status"] == "PASS"

    git_root = tmp_path / "git-source"
    _write_layout(git_root)
    _initialize_git(git_root)
    git_store = EdgeBacklogStore(git_root)
    git_entry = _capture_entry(git_store)
    git_snapshot = git_store.duplicate_snapshot(git_entry.entry_id)
    git_store.record_human_decision(
        git_entry.entry_id,
        disposition="REVIEWED_CONTINUE",
        duplicate_resolution="DISTINCT_EDGE",
        candidate_snapshot_sha256=git_snapshot["snapshot_sha256"],
        reason_codes=["OTHER"],
        rationale="This provisional record is copied to forge a non-Git history.",
        reviewer_id="owner",
    )
    forged_root = tmp_path / "forged"
    _write_layout(forged_root)
    shutil.copytree(git_store.root, forged_root / "research/edge_backlog")

    with pytest.raises(EdgeBacklogIntegrityError, match="Git|replayed"):
        EdgeBacklogStore(forged_root).validate()


def test_source_empty_non_git_repository_remains_supported_without_decisions(tmp_path: Path) -> None:
    _write_layout(tmp_path)
    store = EdgeBacklogStore(tmp_path)
    entry = _capture_entry(store)

    assert store.duplicate_snapshot(entry.entry_id)["historical_source_commit"] is None
    report = store.validate()
    assert report["status"] == "PASS"
    assert report["decisions"] == 0
    assert report["git_anchored_decisions"] == 0
    assert report["provisional_decisions"] == 0
