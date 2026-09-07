from __future__ import annotations

import hashlib
import json
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
from alphaquest.research.edge_backlog_taxonomy import (
    EconomicEdgeTaxonomyV1,
    bundled_taxonomy_ref,
    bundled_taxonomy_root,
    canonical_taxonomy_file_bytes,
    load_taxonomy_catalog_bytes,
    validate_taxonomy_contract_file_bytes,
)


def _write_layout(root: Path) -> None:
    target = root / "config/storage_layout.yaml"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes((Path(__file__).parents[1] / "config/storage_layout.yaml").read_bytes())


def _install_taxonomy_contracts(root: Path) -> Path:
    target = root / "research/edge_backlog/contracts"
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copytree(bundled_taxonomy_root(), target)
    return target


def _initialize_git(root: Path) -> None:
    subprocess.run(["git", "init", "-q", str(root)], check=True)
    subprocess.run(["git", "-C", str(root), "config", "user.name", "P2 Security Test"], check=True)
    subprocess.run(
        ["git", "-C", str(root), "config", "user.email", "p2-security@example.test"],
        check=True,
    )
    subprocess.run(["git", "-C", str(root), "add", "config/storage_layout.yaml"], check=True)
    subprocess.run(["git", "-C", str(root), "commit", "-q", "-m", "initial layout"], check=True)


def _commit_paths(root: Path, message: str, *paths: str) -> None:
    subprocess.run(["git", "-C", str(root), "add", "-A", "--", *paths], check=True)
    subprocess.run(["git", "-C", str(root), "commit", "-q", "-m", message], check=True)


def _anchored_taxonomy_fixture(root: Path) -> tuple[Path, bytes]:
    _write_layout(root)
    _initialize_git(root)
    contracts = _install_taxonomy_contracts(root)
    contract = contracts / "economic-edge-taxonomy-v1.json"
    original = contract.read_bytes()
    _commit_paths(root, "anchor taxonomy v1", "research/edge_backlog/contracts")
    assert EdgeBacklogStore(root).validate()["status"] == "PASS"
    return contract, original


def _changed_taxonomy_bytes(original: bytes, field: str = "definition") -> bytes:
    payload = json.loads(original)
    concept = payload["code_sets"]["market_behavior"][0]
    if field == "definition":
        concept["definition"] += " A descendant must not redefine this concept."
    elif field == "label":
        concept["display_label"] += " changed"
    elif field == "alias":
        concept["recall_aliases"] = sorted(
            {*concept["recall_aliases"], "descendant-only alias"}
        )
    else:  # pragma: no cover - helper guard
        raise AssertionError(field)
    return canonical_taxonomy_file_bytes(EconomicEdgeTaxonomyV1.model_validate(payload))


def _additive_taxonomy_bytes(previous: bytes, version: int) -> bytes:
    payload = json.loads(previous)
    payload["taxonomy_version"] = version
    payload["previous_taxonomy_sha256"] = hashlib.sha256(previous).hexdigest()
    concept = payload["code_sets"]["market_behavior"][0]
    concept["recall_aliases"] = sorted(
        {*concept["recall_aliases"], f"additive v{version} recall alias"}
    )
    return canonical_taxonomy_file_bytes(EconomicEdgeTaxonomyV1.model_validate(payload))


def _additive_taxonomy_v2_bytes(v1: bytes) -> bytes:
    return _additive_taxonomy_bytes(v1, 2)


def _canonical_json_document_bytes(payload: dict) -> bytes:
    return (
        json.dumps(
            payload,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
            allow_nan=False,
        ).encode("utf-8")
        + b"\n"
    )


_CATALOG_SEMANTIC_DRAFT_DEFECTS = (
    "redefined-concept",
    "removed-concept",
    "removed-recall-alias",
    "incorrect-predecessor",
    "non-contiguous-version",
    "changed-protected-dimension",
    "changed-fingerprint-rule",
    "changed-hash-generation-rule",
    "changed-existing-invariant",
    "removed-existing-invariant",
    "new-invariant-existing-trigger",
    "removed-prohibited-category",
)


def _catalog_semantic_draft(v1: bytes, defect: str) -> tuple[str, bytes, bool]:
    payload = json.loads(_additive_taxonomy_v2_bytes(v1))
    standalone_valid = True
    if defect == "redefined-concept":
        payload["code_sets"]["market_behavior"][0]["definition"] += " Redefined in a draft."
    elif defect == "removed-concept":
        payload["code_sets"]["market_behavior"] = [
            item
            for item in payload["code_sets"]["market_behavior"]
            if item["code"] != "INVENTORY_IMBALANCE"
        ]
    elif defect == "removed-recall-alias":
        existing_alias = json.loads(v1)["code_sets"]["market_behavior"][0][
            "recall_aliases"
        ][0]
        payload["code_sets"]["market_behavior"][0]["recall_aliases"].remove(
            existing_alias
        )
    elif defect == "incorrect-predecessor":
        payload["previous_taxonomy_sha256"] = "0" * 64
    elif defect == "non-contiguous-version":
        payload["taxonomy_version"] = 3
    elif defect == "changed-protected-dimension":
        payload["dimensions"][0], payload["dimensions"][1] = (
            payload["dimensions"][1],
            payload["dimensions"][0],
        )
        standalone_valid = False
    elif defect == "changed-fingerprint-rule":
        payload["fingerprint_schema"] = "alphaquest.edge-backlog-fingerprint/v999"
        standalone_valid = False
    elif defect == "changed-hash-generation-rule":
        payload["taxonomy_hash_generation"]["digest"] = "SHA512"
        standalone_valid = False
    elif defect == "changed-existing-invariant":
        payload["cross_field_invariants"][0]["definition"] += " Changed in a draft."
    elif defect == "removed-existing-invariant":
        payload["cross_field_invariants"].pop(0)
    elif defect == "new-invariant-existing-trigger":
        payload["cross_field_invariants"].append(
            {
                "definition": "An invalid draft restriction on an existing concept.",
                "if_any": [
                    {
                        "codes": ["INVENTORY_IMBALANCE"],
                        "field": "market_behavior_code",
                    }
                ],
                "invariant_id": "preexisting_inventory_requires_nq",
                "require_all": [{"codes": ["NQ"], "field": "instrument_ids"}],
                "require_any": [],
            }
        )
        payload["cross_field_invariants"].sort(key=lambda item: item["invariant_id"])
    elif defect == "removed-prohibited-category":
        payload["prohibited_concept_categories"].pop(0)
        standalone_valid = False
    else:  # pragma: no cover - parametrization guard
        raise AssertionError(defect)
    version = payload["taxonomy_version"]
    name = f"economic-edge-taxonomy-v{version}.json"
    return name, _canonical_json_document_bytes(payload), standalone_valid


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


@pytest.mark.parametrize("node_kind", ["fifo", "executable"])
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
    try:
        if node_kind == "fifo":
            os.mkfifo(record)
        else:
            shutil.copy2(held, record)
            record.chmod(0o755)
        with pytest.raises(EdgeBacklogIntegrityError, match="filesystem topology"):
            store.validate()
    finally:
        record.unlink(missing_ok=True)
        held.rename(record)


def test_canonical_record_reader_rejects_socket_descriptor(
    tmp_path: Path,
    monkeypatch,
) -> None:
    from alphaquest.research import edge_backlog_io

    _write_layout(tmp_path)
    store = EdgeBacklogStore(tmp_path)
    _capture_entry(store)
    original_open = edge_backlog_io.os.open
    left, right = socket.socketpair()

    def substitute_socket(path, flags, *args, **kwargs):
        if path == "000001.json":
            return os.dup(left.fileno())
        return original_open(path, flags, *args, **kwargs)

    monkeypatch.setattr(edge_backlog_io.os, "open", substitute_socket)
    try:
        with pytest.raises(EdgeBacklogIntegrityError, match="not a regular file"):
            store.validate()
    finally:
        left.close()
        right.close()


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


@pytest.mark.production_taxonomy
def test_production_taxonomy_root_is_fixed_and_rejects_external_override(tmp_path: Path) -> None:
    _write_layout(tmp_path)
    _install_taxonomy_contracts(tmp_path)
    external = tmp_path / "external-taxonomy"
    shutil.copytree(bundled_taxonomy_root(), external)

    with pytest.raises(TypeError, match="taxonomy_root"):
        EdgeBacklogStore(tmp_path, taxonomy_root=external)  # type: ignore[call-arg]

    assert EdgeBacklogStore(tmp_path).current_taxonomy_ref() == bundled_taxonomy_ref()


@pytest.mark.production_taxonomy
def test_external_taxonomy_directory_symlink_fails_before_any_canonical_write(
    tmp_path: Path,
) -> None:
    _write_layout(tmp_path)
    contracts = _install_taxonomy_contracts(tmp_path)
    store = EdgeBacklogStore(tmp_path)
    entry = _capture_entry(store)
    first_revision = store.root / f"entries/{entry.entry_id}/revisions/000001.json"
    first_revision_bytes = first_revision.read_bytes()
    managed = {
        "schema",
        "record_id",
        "append_sequence",
        "revision",
        "previous_revision_sha256",
        "recorded_at",
        "actor",
        "record_sha256",
    }
    revision_payload = entry.model_dump(mode="json", by_alias=True, exclude=managed)
    external = tmp_path / "external-taxonomy"
    shutil.copytree(contracts, external)
    external_before = _path_bytes(external)
    shutil.rmtree(contracts)
    contracts.symlink_to(external, target_is_directory=True)

    with pytest.raises(EdgeBacklogIntegrityError, match="taxonomy"):
        store.revise_entry(
            entry.entry_id,
            revision_payload,
            actor_id="codex",
        )

    assert _path_bytes(external) == external_before
    assert first_revision.read_bytes() == first_revision_bytes
    assert not first_revision.with_name("000002.json").exists()


@pytest.mark.production_taxonomy
@pytest.mark.parametrize(
    "defect",
    [
        "file-symlink",
        "device-symlink",
        "fifo",
        "executable",
        "unexpected",
        "missing",
        "malformed",
        "noncanonical",
    ],
)
def test_production_taxonomy_reader_fails_closed_for_unsafe_or_invalid_contracts(
    tmp_path: Path,
    defect: str,
) -> None:
    _write_layout(tmp_path)
    contracts = _install_taxonomy_contracts(tmp_path)
    contract = contracts / "economic-edge-taxonomy-v1.json"
    original = contract.read_bytes()
    held = tmp_path / "held-economic-edge-taxonomy-v1.json"
    if defect in {"file-symlink", "device-symlink", "fifo"}:
        contract.rename(held)
    if defect == "file-symlink":
        external = tmp_path / "external-taxonomy.json"
        external.write_bytes(original)
        contract.symlink_to(external)
    elif defect == "device-symlink":
        contract.symlink_to("/dev/null")
    elif defect == "fifo":
        os.mkfifo(contract)
    elif defect == "executable":
        contract.chmod(0o755)
    elif defect == "unexpected":
        (contracts / "notes.txt").write_text("not a taxonomy contract\n", encoding="utf-8")
    elif defect == "missing":
        contract.unlink()
    elif defect == "malformed":
        contract.write_bytes(b'{"schema":')
    elif defect == "noncanonical":
        contract.write_text(json.dumps(json.loads(original), indent=2) + "\n", encoding="utf-8")
    else:  # pragma: no cover - parametrization guard
        raise AssertionError(defect)

    with pytest.raises(EdgeBacklogIntegrityError, match="taxonomy"):
        EdgeBacklogStore(tmp_path).validate()


@pytest.mark.production_taxonomy
@pytest.mark.parametrize("node_kind", ["socket", "device"])
def test_production_taxonomy_reader_rejects_special_file_descriptor(
    tmp_path: Path,
    monkeypatch,
    node_kind: str,
) -> None:
    from alphaquest.research import edge_backlog_io

    _write_layout(tmp_path)
    _install_taxonomy_contracts(tmp_path)
    original_open = edge_backlog_io.os.open
    left: socket.socket | None = None
    right: socket.socket | None = None
    device_fd = -1
    if node_kind == "socket":
        left, right = socket.socketpair()
        injected_fd = left.fileno()
    else:
        device_fd = original_open("/dev/null", os.O_RDONLY)
        injected_fd = device_fd

    def substitute_special_file(path, flags, *args, **kwargs):
        if path == "economic-edge-taxonomy-v1.json":
            return os.dup(injected_fd)
        return original_open(path, flags, *args, **kwargs)

    monkeypatch.setattr(edge_backlog_io.os, "open", substitute_special_file)
    try:
        with pytest.raises(EdgeBacklogIntegrityError, match="not a regular file"):
            EdgeBacklogStore(tmp_path).validate()
    finally:
        if left is not None:
            left.close()
        if right is not None:
            right.close()
        if device_fd >= 0:
            os.close(device_fd)


def _taxonomy_read_race_worker(root: str, barrier, results) -> None:
    from alphaquest.research import edge_backlog_io

    triggered = False

    def pause(operation: str, relative: str) -> None:
        nonlocal triggered
        if not triggered and operation == "taxonomy-contracts":
            triggered = True
            barrier.wait(timeout=20)
            barrier.wait(timeout=20)

    edge_backlog_io._TEST_AFTER_DIRECTORY_ENUMERATION = pause
    try:
        reference = EdgeBacklogStore(root).current_taxonomy_ref()
        results.put(("PASS", reference.taxonomy_sha256))
    except Exception as exc:  # pragma: no cover - asserted in parent
        results.put(("ERROR", f"{type(exc).__name__}: {exc}"))
    finally:
        edge_backlog_io._TEST_AFTER_DIRECTORY_ENUMERATION = None


@pytest.mark.production_taxonomy
@pytest.mark.parametrize("substitution", ["directory", "file"])
def test_taxonomy_substitution_cannot_mix_catalog_or_read_external_content(
    tmp_path: Path,
    substitution: str,
) -> None:
    _write_layout(tmp_path)
    contracts = _install_taxonomy_contracts(tmp_path)
    contract = contracts / "economic-edge-taxonomy-v1.json"
    external = tmp_path / f"external-taxonomy-{substitution}"
    if substitution == "directory":
        external.mkdir()
        (external / contract.name).write_bytes(b'{"external":"malformed"}\n')
        target = contracts
    else:
        external.write_bytes(b'{"external":"malformed"}\n')
        target = contract
    external_before = _path_bytes(external)
    context = multiprocessing.get_context("fork")
    barrier = context.Barrier(2)
    results = context.Queue()
    process = context.Process(
        target=_taxonomy_read_race_worker,
        args=(str(tmp_path), barrier, results),
    )
    process.start()
    barrier.wait(timeout=20)
    held = target.with_name(target.name + ".held")
    target.rename(held)
    target.symlink_to(external, target_is_directory=substitution == "directory")
    barrier.wait(timeout=20)
    process.join(timeout=20)
    try:
        assert process.exitcode == 0
        status, detail = results.get(timeout=5)
        if substitution == "directory":
            assert (status, detail) == (
                "PASS",
                "a9789e806f4c4471147ccdf35aa8d06e1a9b2d4559347850599a411e8f5742bb",
            )
        else:
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


@pytest.mark.production_taxonomy
def test_transaction_reuses_one_taxonomy_snapshot_after_first_dependent_operation(
    tmp_path: Path,
) -> None:
    _write_layout(tmp_path)
    contracts = _install_taxonomy_contracts(tmp_path)
    contract = contracts / "economic-edge-taxonomy-v1.json"
    original = contract.read_bytes()
    store = EdgeBacklogStore(tmp_path)

    try:
        with store._transaction(exclusive=False):
            first = store.current_taxonomy_ref()
            contract.write_bytes(b'{"external":"malformed"}\n')
            second = store.current_taxonomy_ref()
            assert second == first
            assert store._taxonomy_catalog() is store._taxonomy_catalog()
    finally:
        contract.write_bytes(original)

    assert store.current_taxonomy_ref().taxonomy_sha256 == (
        "a9789e806f4c4471147ccdf35aa8d06e1a9b2d4559347850599a411e8f5742bb"
    )


@pytest.mark.production_taxonomy
@pytest.mark.parametrize("field", ["definition", "label", "alias"])
def test_committed_taxonomy_version_rejects_descendant_redefinition(
    tmp_path: Path,
    field: str,
) -> None:
    contract, original = _anchored_taxonomy_fixture(tmp_path)
    contract.write_bytes(_changed_taxonomy_bytes(original, field))
    _commit_paths(tmp_path, f"change anchored taxonomy {field}", str(contract.relative_to(tmp_path)))

    with pytest.raises(EdgeBacklogIntegrityError, match="taxonomy"):
        EdgeBacklogStore(tmp_path).validate()


@pytest.mark.production_taxonomy
@pytest.mark.parametrize(
    "mutation",
    [
        "delete",
        "rename",
        "altered-readd",
        "original-readd",
        "multi-commit-readd",
        "executable",
        "symlink",
        "object-type",
    ],
)
def test_anchored_taxonomy_rejects_every_path_history_mutation(
    tmp_path: Path,
    mutation: str,
) -> None:
    contract, original = _anchored_taxonomy_fixture(tmp_path)
    relative = contract.relative_to(tmp_path).as_posix()
    if mutation == "delete":
        contract.unlink()
        _commit_paths(tmp_path, "delete anchored taxonomy", relative)
    elif mutation == "rename":
        renamed = contract.with_name("economic-edge-taxonomy-v2.json")
        contract.rename(renamed)
        _commit_paths(tmp_path, "rename anchored taxonomy version", str(contract.parent.relative_to(tmp_path)))
    elif mutation in {"altered-readd", "original-readd", "multi-commit-readd"}:
        contract.unlink()
        _commit_paths(tmp_path, "delete anchored taxonomy before re-add", relative)
        if mutation == "multi-commit-readd":
            marker = tmp_path / "notes/taxonomy-disappearance.txt"
            marker.parent.mkdir(parents=True)
            marker.write_text("taxonomy remained absent\n", encoding="utf-8")
            _commit_paths(tmp_path, "retain taxonomy disappearance", str(marker.relative_to(tmp_path)))
        contract.parent.mkdir(parents=True, exist_ok=True)
        contract.write_bytes(
            _changed_taxonomy_bytes(original) if mutation == "altered-readd" else original
        )
        _commit_paths(tmp_path, "re-add anchored taxonomy path", relative)
    elif mutation == "executable":
        contract.chmod(0o755)
        _commit_paths(tmp_path, "make taxonomy executable", relative)
    elif mutation == "symlink":
        external = tmp_path / "external-taxonomy-v1.json"
        external.write_bytes(original)
        contract.unlink()
        contract.symlink_to(external)
        _commit_paths(tmp_path, "replace taxonomy with symlink", relative)
    elif mutation == "object-type":
        contract.unlink()
        contract.mkdir()
        (contract / "payload").write_bytes(original)
        _commit_paths(tmp_path, "replace taxonomy blob with tree", relative)
    else:  # pragma: no cover - parametrization guard
        raise AssertionError(mutation)

    with pytest.raises(EdgeBacklogIntegrityError, match="taxonomy"):
        EdgeBacklogStore(tmp_path).validate()


@pytest.mark.production_taxonomy
@pytest.mark.parametrize("staged_change", ["modify", "delete"])
def test_staged_taxonomy_change_with_restored_worktree_bytes_fails_closed(
    tmp_path: Path,
    staged_change: str,
) -> None:
    contract, original = _anchored_taxonomy_fixture(tmp_path)
    relative = contract.relative_to(tmp_path).as_posix()
    if staged_change == "modify":
        contract.write_bytes(_changed_taxonomy_bytes(original))
        subprocess.run(["git", "-C", str(tmp_path), "add", "--", relative], check=True)
    else:
        subprocess.run(["git", "-C", str(tmp_path), "rm", "--", relative], check=True)
    contract.parent.mkdir(parents=True, exist_ok=True)
    contract.write_bytes(original)

    with pytest.raises(EdgeBacklogIntegrityError, match="HEAD and the Git index"):
        EdgeBacklogStore(tmp_path).validate()


@pytest.mark.production_taxonomy
def test_uncommitted_anchored_taxonomy_change_cannot_authorize_entry_creation(
    tmp_path: Path,
) -> None:
    contract, original = _anchored_taxonomy_fixture(tmp_path)
    contract.write_bytes(_changed_taxonomy_bytes(original))
    store = EdgeBacklogStore(tmp_path)

    with pytest.raises(EdgeBacklogIntegrityError, match="taxonomy contract"):
        _capture_entry(store)

    assert not (tmp_path / "research/edge_backlog/observations").exists()


@pytest.mark.production_taxonomy
def test_ambiguous_taxonomy_introductions_fail_closed(tmp_path: Path) -> None:
    _write_layout(tmp_path)
    _initialize_git(tmp_path)
    base = subprocess.run(
        ["git", "-C", str(tmp_path), "rev-parse", "HEAD"],
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()
    subprocess.run(["git", "-C", str(tmp_path), "switch", "-q", "-c", "taxonomy-a"], check=True)
    contract = _install_taxonomy_contracts(tmp_path) / "economic-edge-taxonomy-v1.json"
    _commit_paths(tmp_path, "introduce taxonomy on branch A", str(contract.relative_to(tmp_path)))
    subprocess.run(
        ["git", "-C", str(tmp_path), "switch", "-q", "-c", "taxonomy-b", base],
        check=True,
    )
    _install_taxonomy_contracts(tmp_path)
    _commit_paths(tmp_path, "introduce taxonomy on branch B", str(contract.relative_to(tmp_path)))
    subprocess.run(
        [
            "git",
            "-C",
            str(tmp_path),
            "merge",
            "-q",
            "--no-ff",
            "-m",
            "merge ambiguous taxonomy introductions",
            "taxonomy-a",
        ],
        check=True,
    )

    with pytest.raises(EdgeBacklogIntegrityError, match="ambiguous Git introduction"):
        EdgeBacklogStore(tmp_path).validate()


@pytest.mark.production_taxonomy
def test_abandoned_invalid_taxonomy_draft_does_not_become_published(
    tmp_path: Path,
) -> None:
    contract, _original = _anchored_taxonomy_fixture(tmp_path)
    v2 = contract.with_name("economic-edge-taxonomy-v2.json")
    relative = v2.relative_to(tmp_path).as_posix()
    v2.write_bytes(b'{"invalid":"unpublished draft"}\n')
    _commit_paths(tmp_path, "commit invalid taxonomy v2 draft", relative)
    v2.unlink()
    _commit_paths(tmp_path, "abandon invalid taxonomy v2 draft", relative)

    assert EdgeBacklogStore(tmp_path).validate()["status"] == "PASS"


@pytest.mark.production_taxonomy
@pytest.mark.parametrize("defect", _CATALOG_SEMANTIC_DRAFT_DEFECTS)
def test_catalog_semantic_invalid_draft_can_be_abandoned_without_publication(
    tmp_path: Path,
    defect: str,
) -> None:
    contract, original = _anchored_taxonomy_fixture(tmp_path)
    name, draft, standalone_valid = _catalog_semantic_draft(original, defect)
    draft_path = contract.with_name(name)
    relative = draft_path.relative_to(tmp_path).as_posix()
    if standalone_valid:
        validate_taxonomy_contract_file_bytes(name, draft)
    with pytest.raises(ValueError):
        load_taxonomy_catalog_bytes(
            {contract.name: original, name: draft},
            source_label=f"{defect} test catalog",
        )

    draft_path.write_bytes(draft)
    _commit_paths(tmp_path, f"commit {defect} taxonomy draft", relative)
    draft_path.unlink()
    _commit_paths(tmp_path, f"abandon {defect} taxonomy draft", relative)

    assert EdgeBacklogStore(tmp_path).validate()["status"] == "PASS"


@pytest.mark.production_taxonomy
@pytest.mark.parametrize("defect", _CATALOG_SEMANTIC_DRAFT_DEFECTS)
def test_catalog_semantic_invalid_draft_can_precede_valid_publication(
    tmp_path: Path,
    defect: str,
) -> None:
    contract, original = _anchored_taxonomy_fixture(tmp_path)
    name, draft, _standalone_valid = _catalog_semantic_draft(original, defect)
    draft_path = contract.with_name(name)
    relative = draft_path.relative_to(tmp_path).as_posix()
    draft_path.write_bytes(draft)
    _commit_paths(tmp_path, f"commit {defect} taxonomy draft", relative)

    valid_v2 = _additive_taxonomy_v2_bytes(original)
    if name == "economic-edge-taxonomy-v3.json":
        v2 = contract.with_name("economic-edge-taxonomy-v2.json")
        v2.write_bytes(valid_v2)
        published = _additive_taxonomy_bytes(valid_v2, 3)
    else:
        published = valid_v2
    draft_path.write_bytes(published)
    _commit_paths(
        tmp_path,
        f"publish valid taxonomy after {defect} draft",
        str(contract.parent.relative_to(tmp_path)),
    )

    assert EdgeBacklogStore(tmp_path).validate()["status"] == "PASS"


@pytest.mark.production_taxonomy
def test_invalid_taxonomy_draft_can_precede_first_valid_publication(
    tmp_path: Path,
) -> None:
    contract, original = _anchored_taxonomy_fixture(tmp_path)
    v2 = contract.with_name("economic-edge-taxonomy-v2.json")
    relative = v2.relative_to(tmp_path).as_posix()
    v2.write_bytes(b'{"invalid":"unpublished draft"}\n')
    _commit_paths(tmp_path, "commit invalid taxonomy v2 draft", relative)
    v2.write_bytes(_additive_taxonomy_v2_bytes(original))
    _commit_paths(tmp_path, "publish valid additive taxonomy v2", relative)

    assert EdgeBacklogStore(tmp_path).validate()["status"] == "PASS"


@pytest.mark.production_taxonomy
@pytest.mark.parametrize(
    "mutation",
    [
        "delete",
        "rewrite",
        "relocate",
        "executable",
        "symlink",
        "object-type",
        "multi-commit-readd",
        "original-readd",
    ],
)
def test_taxonomy_becomes_immutable_after_invalid_draft_then_valid_publication(
    tmp_path: Path,
    mutation: str,
) -> None:
    contract, original = _anchored_taxonomy_fixture(tmp_path)
    v2 = contract.with_name("economic-edge-taxonomy-v2.json")
    relative = v2.relative_to(tmp_path).as_posix()
    _name, semantic_draft, _standalone_valid = _catalog_semantic_draft(
        original,
        "incorrect-predecessor",
    )
    v2.write_bytes(semantic_draft)
    _commit_paths(tmp_path, "commit invalid taxonomy v2 draft", relative)
    published = _additive_taxonomy_v2_bytes(original)
    v2.write_bytes(published)
    _commit_paths(tmp_path, "publish valid additive taxonomy v2", relative)
    assert EdgeBacklogStore(tmp_path).validate()["status"] == "PASS"

    if mutation == "delete":
        v2.unlink()
        _commit_paths(tmp_path, "delete published taxonomy v2", relative)
    elif mutation == "rewrite":
        v2.write_bytes(_changed_taxonomy_bytes(published, "label"))
        _commit_paths(tmp_path, "rewrite published taxonomy v2", relative)
    elif mutation == "relocate":
        v2.rename(v2.with_name("economic-edge-taxonomy-v3.json"))
        _commit_paths(tmp_path, "relocate published taxonomy v2", str(v2.parent.relative_to(tmp_path)))
    elif mutation == "executable":
        v2.chmod(0o755)
        _commit_paths(tmp_path, "make published taxonomy v2 executable", relative)
    elif mutation == "symlink":
        external = tmp_path / "external-published-taxonomy-v2.json"
        external.write_bytes(published)
        v2.unlink()
        v2.symlink_to(external)
        _commit_paths(tmp_path, "replace published taxonomy v2 with symlink", relative)
    elif mutation == "object-type":
        v2.unlink()
        v2.mkdir()
        (v2 / "payload").write_bytes(published)
        _commit_paths(tmp_path, "replace published taxonomy v2 with tree", relative)
    elif mutation in {"multi-commit-readd", "original-readd"}:
        v2.unlink()
        _commit_paths(tmp_path, "delete published taxonomy v2", relative)
        if mutation == "multi-commit-readd":
            marker = tmp_path / "notes/published-v2-remained-absent.txt"
            marker.parent.mkdir(parents=True, exist_ok=True)
            marker.write_text("published v2 remained absent\n", encoding="utf-8")
            _commit_paths(
                tmp_path,
                "retain published taxonomy v2 disappearance",
                str(marker.relative_to(tmp_path)),
            )
        v2.write_bytes(published)
        _commit_paths(tmp_path, "re-add original published taxonomy v2", relative)
    else:  # pragma: no cover - parametrization guard
        raise AssertionError(mutation)

    with pytest.raises(EdgeBacklogIntegrityError, match="taxonomy"):
        EdgeBacklogStore(tmp_path).validate()


@pytest.mark.production_taxonomy
def test_competing_invalid_taxonomy_drafts_do_not_create_publication_ambiguity(
    tmp_path: Path,
) -> None:
    contract, original = _anchored_taxonomy_fixture(tmp_path)
    v2 = contract.with_name("economic-edge-taxonomy-v2.json")
    relative = v2.relative_to(tmp_path).as_posix()
    base = subprocess.run(
        ["git", "-C", str(tmp_path), "rev-parse", "HEAD"],
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()

    subprocess.run(["git", "-C", str(tmp_path), "switch", "-q", "-c", "invalid-a"], check=True)
    _name, branch_a_draft, standalone_valid = _catalog_semantic_draft(
        original,
        "incorrect-predecessor",
    )
    assert standalone_valid is True
    v2.write_bytes(branch_a_draft)
    _commit_paths(tmp_path, "commit invalid branch A draft", relative)
    v2.unlink()
    _commit_paths(tmp_path, "abandon invalid branch A draft", relative)

    subprocess.run(
        ["git", "-C", str(tmp_path), "switch", "-q", "-c", "invalid-b", base],
        check=True,
    )
    _name, branch_b_draft, standalone_valid = _catalog_semantic_draft(
        original,
        "redefined-concept",
    )
    assert standalone_valid is True
    v2.write_bytes(branch_b_draft)
    _commit_paths(tmp_path, "commit invalid branch B draft", relative)
    v2.unlink()
    _commit_paths(tmp_path, "abandon invalid branch B draft", relative)
    subprocess.run(
        [
            "git",
            "-C",
            str(tmp_path),
            "merge",
            "-q",
            "--no-ff",
            "-m",
            "merge abandoned invalid drafts",
            "invalid-a",
        ],
        check=True,
    )

    assert EdgeBacklogStore(tmp_path).validate()["status"] == "PASS"
    v2.write_bytes(_additive_taxonomy_v2_bytes(original))
    _commit_paths(tmp_path, "publish valid taxonomy after competing drafts", relative)
    assert EdgeBacklogStore(tmp_path).validate()["status"] == "PASS"


@pytest.mark.production_taxonomy
def test_competing_valid_additive_taxonomy_publications_are_ambiguous(
    tmp_path: Path,
) -> None:
    contract, original = _anchored_taxonomy_fixture(tmp_path)
    v2 = contract.with_name("economic-edge-taxonomy-v2.json")
    relative = v2.relative_to(tmp_path).as_posix()
    base = subprocess.run(
        ["git", "-C", str(tmp_path), "rev-parse", "HEAD"],
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()
    valid_v2 = _additive_taxonomy_v2_bytes(original)

    subprocess.run(["git", "-C", str(tmp_path), "switch", "-q", "-c", "valid-a"], check=True)
    v2.write_bytes(valid_v2)
    _commit_paths(tmp_path, "publish valid taxonomy v2 on branch A", relative)
    subprocess.run(
        ["git", "-C", str(tmp_path), "switch", "-q", "-c", "valid-b", base],
        check=True,
    )
    v2.write_bytes(valid_v2)
    _commit_paths(tmp_path, "publish valid taxonomy v2 on branch B", relative)
    subprocess.run(
        [
            "git",
            "-C",
            str(tmp_path),
            "merge",
            "-q",
            "--no-ff",
            "-m",
            "merge competing valid taxonomy publications",
            "valid-a",
        ],
        check=True,
    )

    with pytest.raises(EdgeBacklogIntegrityError, match="ambiguous Git introduction"):
        EdgeBacklogStore(tmp_path).validate()


@pytest.mark.production_taxonomy
def test_valid_taxonomy_publication_ignores_competing_semantic_invalid_draft(
    tmp_path: Path,
) -> None:
    contract, original = _anchored_taxonomy_fixture(tmp_path)
    v2 = contract.with_name("economic-edge-taxonomy-v2.json")
    relative = v2.relative_to(tmp_path).as_posix()
    base = subprocess.run(
        ["git", "-C", str(tmp_path), "rev-parse", "HEAD"],
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()
    valid_v2 = _additive_taxonomy_v2_bytes(original)

    subprocess.run(["git", "-C", str(tmp_path), "switch", "-q", "-c", "valid"], check=True)
    v2.write_bytes(valid_v2)
    _commit_paths(tmp_path, "publish valid taxonomy v2", relative)
    subprocess.run(
        ["git", "-C", str(tmp_path), "switch", "-q", "-c", "invalid", base],
        check=True,
    )
    _name, invalid_v2, standalone_valid = _catalog_semantic_draft(
        original,
        "incorrect-predecessor",
    )
    assert standalone_valid is True
    v2.write_bytes(invalid_v2)
    _commit_paths(tmp_path, "commit semantic-invalid taxonomy v2 draft", relative)
    merge = subprocess.run(
        [
            "git",
            "-C",
            str(tmp_path),
            "merge",
            "-q",
            "--no-ff",
            "--no-commit",
            "valid",
        ],
        capture_output=True,
        text=True,
    )
    assert merge.returncode != 0
    v2.write_bytes(valid_v2)
    subprocess.run(["git", "-C", str(tmp_path), "add", "--", relative], check=True)
    subprocess.run(
        ["git", "-C", str(tmp_path), "commit", "-q", "-m", "resolve with valid publication"],
        check=True,
    )

    assert EdgeBacklogStore(tmp_path).validate()["status"] == "PASS"
    v2.write_bytes(_changed_taxonomy_bytes(valid_v2, "label"))
    _commit_paths(tmp_path, "rewrite the valid taxonomy publication", relative)
    with pytest.raises(EdgeBacklogIntegrityError, match="taxonomy"):
        EdgeBacklogStore(tmp_path).validate()


@pytest.mark.production_taxonomy
@pytest.mark.parametrize("draft_kind", ["malformed", "noncanonical"])
def test_byte_invalid_taxonomy_history_remains_unpublished(
    tmp_path: Path,
    draft_kind: str,
) -> None:
    contract, original = _anchored_taxonomy_fixture(tmp_path)
    v2 = contract.with_name("economic-edge-taxonomy-v2.json")
    relative = v2.relative_to(tmp_path).as_posix()
    if draft_kind == "malformed":
        draft = b'{"schema":'
    else:
        draft = (json.dumps(json.loads(_additive_taxonomy_v2_bytes(original)), indent=2) + "\n").encode(
            "utf-8"
        )
    v2.write_bytes(draft)
    _commit_paths(tmp_path, f"commit {draft_kind} taxonomy draft", relative)
    v2.unlink()
    _commit_paths(tmp_path, f"abandon {draft_kind} taxonomy draft", relative)

    assert EdgeBacklogStore(tmp_path).validate()["status"] == "PASS"


@pytest.mark.production_taxonomy
def test_valid_additive_taxonomy_version_is_allowed_then_git_anchored(tmp_path: Path) -> None:
    contract, original = _anchored_taxonomy_fixture(tmp_path)
    v2 = contract.with_name("economic-edge-taxonomy-v2.json")
    v2.write_bytes(_additive_taxonomy_v2_bytes(original))

    assert EdgeBacklogStore(tmp_path).validate()["status"] == "PASS"
    _commit_paths(tmp_path, "publish additive taxonomy v2", str(v2.relative_to(tmp_path)))
    assert EdgeBacklogStore(tmp_path).validate()["status"] == "PASS"

    anchored_v2 = v2.read_bytes()
    v2.write_bytes(_changed_taxonomy_bytes(anchored_v2, "label"))
    with pytest.raises(EdgeBacklogIntegrityError, match="taxonomy"):
        EdgeBacklogStore(tmp_path).validate()


@pytest.mark.production_taxonomy
def test_unchanged_anchored_taxonomy_v1_retains_exact_identity(tmp_path: Path) -> None:
    _contract, original = _anchored_taxonomy_fixture(tmp_path)

    assert hashlib.sha256(original).hexdigest() == (
        "a9789e806f4c4471147ccdf35aa8d06e1a9b2d4559347850599a411e8f5742bb"
    )
    assert EdgeBacklogStore(tmp_path).current_taxonomy_ref().taxonomy_sha256 == hashlib.sha256(
        original
    ).hexdigest()


@pytest.mark.production_taxonomy
def test_valid_taxonomy_can_establish_a_unique_initial_commit_anchor(tmp_path: Path) -> None:
    _write_layout(tmp_path)
    _install_taxonomy_contracts(tmp_path)
    subprocess.run(["git", "init", "-q", str(tmp_path)], check=True)
    subprocess.run(["git", "-C", str(tmp_path), "config", "user.name", "P2 Security Test"], check=True)
    subprocess.run(
        ["git", "-C", str(tmp_path), "config", "user.email", "p2-security@example.test"],
        check=True,
    )
    subprocess.run(["git", "-C", str(tmp_path), "add", "."], check=True)
    subprocess.run(["git", "-C", str(tmp_path), "commit", "-q", "-m", "initial taxonomy"], check=True)

    assert EdgeBacklogStore(tmp_path).validate()["status"] == "PASS"
