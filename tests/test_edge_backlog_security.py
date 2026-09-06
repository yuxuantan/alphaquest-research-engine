from __future__ import annotations

import multiprocessing
import os
from pathlib import Path
import shutil
import socket
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


def _outside_target(root: Path, label: str) -> Path:
    target = root.parent / f"{root.name}-external-{label}"
    if target.exists() or target.is_symlink():
        if target.is_dir() and not target.is_symlink():
            shutil.rmtree(target)
        else:
            target.unlink()
    return target


def _path_bytes(path: Path) -> dict[str, bytes]:
    if path.is_file():
        return {path.name: path.read_bytes()}
    return {
        item.relative_to(path).as_posix(): item.read_bytes()
        for item in sorted(path.rglob("*"))
        if item.is_file()
    }


@pytest.mark.parametrize(
    "boundary",
    [
        "observations",
        "entries",
        "observation-object",
        "entry-object",
        "revisions",
        "decisions",
        "links",
        "record",
    ],
)
def test_canonical_reads_reject_external_symlinks_at_every_topology_boundary(
    tmp_path: Path,
    boundary: str,
) -> None:
    _write_layout(tmp_path)
    store = EdgeBacklogStore(tmp_path)
    entry = _capture_entry(store)
    observation_record = (
        store.root / "observations/obs.security/revisions/000001.json"
    )
    entry_object = store.root / "entries" / entry.entry_id
    (entry_object / "decisions").mkdir()
    (entry_object / "links").mkdir()
    targets = {
        "observations": store.root / "observations",
        "entries": store.root / "entries",
        "observation-object": store.root / "observations/obs.security",
        "entry-object": entry_object,
        "revisions": entry_object / "revisions",
        "decisions": entry_object / "decisions",
        "links": entry_object / "links",
        "record": observation_record,
    }
    target = targets[boundary]
    target_is_directory = target.is_dir()
    external = _outside_target(tmp_path, boundary)
    if target_is_directory:
        shutil.copytree(target, external)
    else:
        external.write_bytes(target.read_bytes())
    external_before = _path_bytes(external)
    held = target.with_name(target.name + ".held")
    target.rename(held)
    target.symlink_to(external, target_is_directory=target_is_directory)
    try:
        operations = (
            store.validate,
            store.list_entries,
            lambda: store.entry_state(entry.entry_id),
            lambda: store.search("inventory"),
            lambda: store.duplicate_candidates(entry.entry_id),
            lambda: store.duplicate_snapshot(entry.entry_id),
            store._next_append_sequence,
        )
        for operation in operations:
            with pytest.raises(EdgeBacklogIntegrityError, match="filesystem topology"):
                operation()
        assert _path_bytes(external) == external_before
    finally:
        target.unlink()
        held.rename(target)
        if external.is_dir():
            shutil.rmtree(external)
        else:
            external.unlink()


@pytest.mark.parametrize("node_kind", ["fifo", "socket", "executable"])
def test_canonical_record_reader_rejects_nonregular_and_executable_nodes(
    tmp_path: Path,
    node_kind: str,
) -> None:
    _write_layout(tmp_path)
    store = EdgeBacklogStore(tmp_path)
    _capture_entry(store)
    record = store.root / "observations/obs.security/revisions/000001.json"
    held = record.with_name("000001.held")
    record.rename(held)
    unix_socket: socket.socket | None = None
    socket_alias: Path | None = None
    try:
        if node_kind == "fifo":
            os.mkfifo(record)
        elif node_kind == "socket":
            unix_socket = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
            socket_alias = Path("/tmp") / f"aq-p2-socket-{os.getpid()}-{tmp_path.name[-8:]}"
            socket_alias.symlink_to(record.parent, target_is_directory=True)
            unix_socket.bind(str(socket_alias / record.name))
        else:
            shutil.copy2(held, record)
            record.chmod(0o755)
        with pytest.raises(EdgeBacklogIntegrityError, match="filesystem topology"):
            store.validate()
    finally:
        if unix_socket is not None:
            unix_socket.close()
        record.unlink(missing_ok=True)
        if socket_alias is not None:
            socket_alias.unlink(missing_ok=True)
        held.rename(record)


def _canonical_read_race_worker(
    root: str,
    operation: str,
    relative: str,
    barrier,
    results,
) -> None:
    from alphaquest.research import edge_backlog_io

    triggered = False

    def pause(selected: str, selected_relative: str) -> None:
        nonlocal triggered
        if not triggered and selected == operation and selected_relative == relative:
            triggered = True
            barrier.wait(timeout=20)
            barrier.wait(timeout=20)

    edge_backlog_io._TEST_AFTER_DIRECTORY_ENUMERATION = pause
    try:
        EdgeBacklogStore(root).validate()
        results.put(("PASS", ""))
    except Exception as exc:  # pragma: no cover - asserted in the parent
        results.put(("ERROR", f"{type(exc).__name__}: {exc}"))
    finally:
        edge_backlog_io._TEST_AFTER_DIRECTORY_ENUMERATION = None


@pytest.mark.parametrize("substitution", ["entry-object", "observation-record"])
def test_descriptor_snapshot_rejects_symlink_substitution_between_enumeration_and_open(
    tmp_path: Path,
    substitution: str,
) -> None:
    _write_layout(tmp_path)
    store = EdgeBacklogStore(tmp_path)
    entry = _capture_entry(store)
    if substitution == "entry-object":
        operation = "canonical-collection"
        relative = "research/edge_backlog/entries"
        target = store.root / "entries" / entry.entry_id
    else:
        operation = "canonical-records"
        relative = "research/edge_backlog/observations/obs.security/revisions"
        target = store.root / "observations/obs.security/revisions/000001.json"

    target_is_directory = target.is_dir()
    external = _outside_target(tmp_path, f"race-{substitution}")
    if target_is_directory:
        shutil.copytree(target, external)
    else:
        external.write_bytes(target.read_bytes())
    external_before = _path_bytes(external)
    context = multiprocessing.get_context("fork")
    barrier = context.Barrier(2)
    results = context.Queue()
    process = context.Process(
        target=_canonical_read_race_worker,
        args=(str(tmp_path), operation, relative, barrier, results),
    )
    process.start()
    barrier.wait(timeout=20)
    held = target.with_name(target.name + ".held")
    target.rename(held)
    target.symlink_to(external, target_is_directory=target_is_directory)
    barrier.wait(timeout=20)
    process.join(timeout=20)
    try:
        assert process.exitcode == 0
        status, detail = results.get(timeout=5)
        assert status == "ERROR"
        assert "EdgeBacklogIntegrityError" in detail
        assert _path_bytes(external) == external_before
    finally:
        target.unlink()
        held.rename(target)
        if external.is_dir():
            shutil.rmtree(external)
        else:
            external.unlink()
