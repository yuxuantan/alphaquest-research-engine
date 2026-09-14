"""Disk-only subprocess proofs of the store-wide canonical prefix barrier."""

from __future__ import annotations

import json
from pathlib import Path
import shutil

import pytest

from alphaquest.research.literature.contracts import canonical_json_bytes
from alphaquest.research.literature.store import LiteratureStore
from tests.test_literature_stage1 import (
    REPO,
    _canonical_paths,
    _completed_retry_inputs,
    _initial_slice,
    _project,
    _python_subprocess,
)


_A = "research/literature/protocols/protocol.prefix-a/revisions/000001.json"

_PROBE = r"""
import json
import os
from pathlib import Path
import sys

root, test_directory, scenario = sys.argv[1:]
root = Path(root)
scenario = json.loads(scenario)
sys.path.insert(0, str(Path(test_directory).parent))
from tests.test_literature_stage1 import NOW, _actor, _protocol_payload
from alphaquest.research.literature.contracts import LiteratureError
from alphaquest.research.literature.emission import emit_prepared, reconcile_emission
from alphaquest.research.literature.store import LiteratureStore
import alphaquest.research.literature.store as store_module
import alphaquest.research.literature.publication as publication

events = []
fault = scenario.get("fault")
action = scenario["action"]
target = scenario.get("target", "research/literature/protocols/protocol.prefix-a/revisions/000001.json")
leaf = str(Path(target).parent)
real_file = publication._fsync_file
real_directory = publication._fsync_directory
real_recover = store_module.recover_canonical_record
real_prefix = LiteratureStore._ensure_durable_canonical_prefix
linked = False

def durability(kind, relative):
    events.append([kind, relative])

def publication_event(phase, relative):
    global linked
    events.append(["publication", phase, relative])
    if phase == "after_atomic_publish_before_directory_fsync":
        linked = True
        if action == "seed-death":
            os._exit(73)

def file_sync(fd, relative):
    if fault == "file" and relative == target:
        raise OSError("injected prefix file fsync failure")
    real_file(fd, relative)

def directory_sync(directory):
    if action == "seed-exception" and linked and directory.relative == leaf:
        raise OSError("injected post-link directory fsync failure")
    if fault == "leaf" and directory.relative == leaf:
        raise OSError("injected prefix leaf fsync failure")
    if fault == "ancestor" and directory.relative == "research":
        raise OSError("injected prefix ancestor fsync failure")
    real_directory(directory)

def recover(project_root, relative, expected):
    if fault == "reopen" and relative == target:
        raise OSError("injected inability to reopen prefix record")
    real_recover(project_root, relative, expected)
    events.append(["recovered", relative])

def prefix(self, records):
    if fault == "malformed":
        raise AssertionError("malformed history reached durability recovery")
    events.append(["prefix-start", len(records)])
    if fault == "changed":
        (root / target).write_bytes((root / target).read_bytes() + b"\n")
    if fault == "missing":
        (root / target).unlink()
    real_prefix(self, records)
    events.append(["prefix-complete", len(records)])

publication._TEST_DURABILITY_HOOK = durability
publication._TEST_PUBLICATION_HOOK = publication_event
publication._fsync_file = file_sync
publication._fsync_directory = directory_sync
store_module.recover_canonical_record = recover
LiteratureStore._ensure_durable_canonical_prefix = prefix
store = LiteratureStore(root)

def protocol(name, *, key=None, annotations=None):
    return store.append_protocol(
        _protocol_payload(
            protocol_id="protocol." + name, lineage="lineage." + name,
            **({"administrative_annotations": annotations, "change_reason": "revision"}
               if annotations is not None else {}),
        ),
        actor=_actor(), idempotency_key=key or name, recorded_at=NOW,
    )

try:
    if action in {"seed-death", "seed-exception", "exact"}:
        result = protocol("prefix-a")
    elif action == "same-object":
        result = protocol("prefix-a", key="revision-b", annotations=["successor"])
    elif action == "changed-intent":
        result = protocol("prefix-a", key="prefix-a", annotations=["conflict"])
    elif action == "different-object":
        result = protocol("prefix-b")
    elif action == "different-family":
        result = store.append_work({
            "work_id": "work.prefix-b", "source_category": "ACADEMIC",
            "title": "Prefix successor", "authors": ["Fixture Author"],
            "strong_identifiers": {"doi": "10.0000/prefix"},
            "locators": ["https://example.test/prefix"],
            "identity_status": "VERIFIED_STRONG", "change_reason": "Prefix test",
        }, actor=_actor(), idempotency_key="work.prefix-b", recorded_at=NOW)
    elif action == "legacy-successors":
        # Construct valid history from the pre-prefix-barrier publication era.
        # This bypass is ONLY a fixture, never the successor under test.
        LiteratureStore._ensure_durable_canonical_prefix = lambda self, records: None
        protocol("legacy-b")
        result = protocol("legacy-c")
    elif action == "complete":
        result = store.complete_emission_operation(
            **scenario["completion"], actor=_actor(), recorded_at=NOW,
        )[1]
    elif action == "public-retry":
        from datetime import datetime, timezone
        result = getattr(store, scenario["method"])(
            *scenario["args"], actor=_actor("fresh-retry"),
            idempotency_key=scenario["key"],
            recorded_at=datetime(2030, 1, 1, tzinfo=timezone.utc),
        )
    elif action == "emit":
        result = emit_prepared(root, operation_id=scenario["operation_id"], actor=_actor())
    elif action == "reconcile":
        result = reconcile_emission(root, operation_id=scenario["operation_id"], actor=_actor())
    elif action == "freeze":
        result = store.freeze_dossier(
            scenario["freeze"], actor=_actor(), idempotency_key="freeze.prefix-new", recorded_at=NOW,
        )
    else:
        raise AssertionError(action)
except (OSError, LiteratureError) as exc:
    if action == "seed-exception":
        assert linked
        os._exit(76)
    print(json.dumps({"error": type(exc).__name__, "message": str(exc), "events": events}))
    sys.exit(0)
print(json.dumps({"record_id": result.record_id, "record_sha256": result.record_sha256, "events": events}))
"""


def _probe(root: Path, action: str, **scenario):
    return _python_subprocess(
        _PROBE, str(root), str(REPO / "tests"), json.dumps({"action": action, **scenario}),
    )


def _result(root: Path, action: str, **scenario) -> dict:
    process = _probe(root, action, **scenario)
    assert process.returncode == 0, process.stderr
    return json.loads(process.stdout)


def _seed(root: Path, *, exception: bool = False) -> None:
    writer = _probe(root, "seed-exception" if exception else "seed-death")
    assert writer.returncode == (76 if exception else 73), writer.stderr
    assert (root / _A).is_file()
    assert len(LiteratureStore(root).records()) == 1
    if exception:
        assert not list((root / "run-store/literature/canonical-staging").glob("*.staging"))


def _prefix_paths(root: Path) -> list[str]:
    store = LiteratureStore(root)
    return [store._record_relative(record) for record in store.records()]


def _assert_prefix_before_publication(result: dict, paths: list[str]) -> None:
    assert "error" not in result, result
    events = result["events"]
    completed = events.index(["prefix-complete", len(paths)])
    recovery = events[:completed]
    assert [event[1] for event in recovery if event[0] == "recovered"] == paths
    # Each real file fsync is followed by its exact complete ancestry, not a
    # count or a union that could hide omission of a sibling record directory.
    for path in paths:
        index = recovery.index(["file", path])
        directories = [["directory", str(parent)] for parent in Path(path).parents]
        assert recovery[index + 1:index + 1 + len(directories)] == directories
        assert ["recovered", path] in recovery
    assert not any(event[0] == "publication" for event in recovery)


@pytest.mark.parametrize("action", ("exact", "same-object", "different-object", "different-family"))
def test_prefix_durability_recovers_ambiguous_predecessor_before_successor(
    tmp_path: Path, action: str,
) -> None:
    _seed(tmp_path)
    predecessor = LiteratureStore(tmp_path).records()[0]
    exact_bytes = (tmp_path / _A).read_bytes()
    result = _result(tmp_path, action)
    _assert_prefix_before_publication(result, [_A])
    assert (tmp_path / _A).read_bytes() == exact_bytes == canonical_json_bytes(predecessor)
    records = LiteratureStore(tmp_path).records()
    assert len(records) == (1 if action == "exact" else 2)
    if action != "exact":
        assert records[-1].previous_store_record_sha256 == predecessor.record_sha256
        assert records[-1].append_sequence == 2
    else:
        assert not any(event[0] == "publication" for event in result["events"])


def test_prefix_durability_recovers_older_non_tail_sibling(tmp_path: Path) -> None:
    _seed(tmp_path)
    historical = _result(tmp_path, "legacy-successors")
    assert "error" not in historical
    assert ["directory", str(Path(_A).parent)] not in historical["events"]
    paths = _prefix_paths(tmp_path)
    assert len(paths) == 3 and paths[0] == _A
    result = _result(tmp_path, "different-object")
    _assert_prefix_before_publication(result, paths)
    assert len(LiteratureStore(tmp_path).records()) == 4


def test_prefix_durability_recovers_post_link_exception_without_residue(tmp_path: Path) -> None:
    _seed(tmp_path, exception=True)
    result = _result(tmp_path, "different-object")
    _assert_prefix_before_publication(result, [_A])
    assert len(LiteratureStore(tmp_path).records()) == 2


@pytest.mark.parametrize("fault", ("file", "leaf", "ancestor", "reopen", "changed", "missing"))
def test_prefix_durability_failure_prevents_successor_and_sequence_consumption(
    tmp_path: Path, fault: str,
) -> None:
    _seed(tmp_path)
    original = (tmp_path / _A).read_bytes()
    failed = _result(tmp_path, "different-object", fault=fault)
    assert "error" in failed
    assert not any(event[0] == "publication" for event in failed["events"])
    assert not (tmp_path / "research/literature/protocols/protocol.prefix-b").exists()
    if fault not in {"missing", "changed"}:
        assert len(LiteratureStore(tmp_path).records()) == 1
        assert (tmp_path / _A).read_bytes() == original
    else:
        # Restore only the test-injected damage, never production recovery.
        (tmp_path / _A).write_bytes(original)
    retried = _result(tmp_path, "different-object")
    _assert_prefix_before_publication(retried, [_A])
    records = LiteratureStore(tmp_path).records()
    assert [record.append_sequence for record in records] == [1, 2]


def test_prefix_durability_does_not_recover_malformed_history(tmp_path: Path) -> None:
    _seed(tmp_path)
    (tmp_path / _A).write_bytes(b"{}\n")
    result = _result(tmp_path, "different-object", fault="malformed")
    assert result["error"] == "LiteratureIntegrityError"
    assert result["events"] == []


@pytest.mark.parametrize("fault", (None, "file", "reopen", "leaf", "ancestor"))
def test_prefix_durability_does_not_turn_changed_intent_into_exact_retry(tmp_path: Path, fault) -> None:
    _seed(tmp_path)
    before = (tmp_path / _A).read_bytes()
    result = _result(tmp_path, "changed-intent", fault=fault)
    assert result["error"] == "LiteratureConflictError"
    assert "idempotency" in result["message"]
    assert result["events"] == []
    assert (tmp_path / _A).read_bytes() == before
    assert len(LiteratureStore(tmp_path).records()) == 1


@pytest.fixture(scope="module")
def prefix_completed_root(tmp_path_factory: pytest.TempPathFactory) -> Path:
    root = _project(tmp_path_factory.mktemp("prefix-completion"))
    _initial_slice(root)
    return root


@pytest.mark.parametrize("mode", ("new-completion", "receipt-tail", "completed", "emit", "freeze"))
@pytest.mark.parametrize("fault", (None, "file"))
def test_prefix_durability_specialized_completion_retry_and_immutable_paths(
    tmp_path: Path, prefix_completed_root: Path, mode: str, fault: str | None,
) -> None:
    root = tmp_path / "case"
    shutil.copytree(prefix_completed_root, root)
    store, snapshot, receipt, completed, payload = _completed_retry_inputs(root)
    if mode in {"new-completion", "receipt-tail"}:
        (root / store._record_relative(completed)).unlink()
    if mode == "new-completion":
        (root / store._record_relative(receipt)).unlink()
    paths = _prefix_paths(root)
    before = {path.relative_to(root): path.read_bytes() for path in _canonical_paths(root)}
    p2_before = {path.relative_to(root): path.read_bytes() for path in (root / "research/edge_backlog").rglob("*.json")}
    scenario = {"target": paths[0], "fault": fault}
    if mode in {"new-completion", "completed"}:
        action = "complete"
        scenario["completion"] = {
            "operation_id": completed.operation_id,
            "snapshot_revision_sha256": snapshot.record_sha256,
            "receipt_payload": payload,
            "receipt_idempotency_key": f"{completed.operation_id}.receipt",
            "completion_idempotency_key": f"{completed.operation_id}.completed",
        }
    elif mode in {"receipt-tail", "emit"}:
        action = "reconcile" if mode == "receipt-tail" else "emit"
        scenario["operation_id"] = completed.operation_id
    else:
        action = "freeze"
        freeze = next(item for item in store.records() if type(item).family == "dossier-freezes")
        scenario["freeze"] = {
            "freeze_id": "freeze.prefix-new", "dossier_id": freeze.dossier_id,
            "dossier_revision_sha256": freeze.dossier_revision_sha256,
        }
    result = _result(root, action, **scenario)
    if fault:
        assert "error" in result
        assert not any(event[0] == "publication" for event in result["events"])
        assert {path.relative_to(root): path.read_bytes() for path in _canonical_paths(root)} == before
        scenario["fault"] = None
        result = _result(root, action, **scenario)
    _assert_prefix_before_publication(result, paths)
    expected_delta = {"new-completion": 2, "receipt-tail": 1, "completed": 0, "emit": 0, "freeze": 1}[mode]
    assert len(LiteratureStore(root).records()) == len(paths) + expected_delta
    assert LiteratureStore(root).validate()["status"] == "PASS"
    assert {path.relative_to(root): path.read_bytes() for path in (root / "research/edge_backlog").rglob("*.json")} == p2_before


def _history_bytes(root: Path) -> dict[str, bytes]:
    return {
        str(path.relative_to(root)): path.read_bytes()
        for directory in ("research/literature", "research/edge_backlog")
        for path in (root / directory).rglob("*.json")
    }


@pytest.fixture(scope="module")
def m1_public_retries(tmp_path_factory):
    from tests.test_literature_stage1 import (
        MANAGED_FIELDS, _actor, _attempt_payload, _protocol, _source,
        _start_capture, _start_lane_search, _terminal_attempt_payload,
    )

    root = _project(tmp_path_factory.mktemp("m1-public"))
    store = LiteratureStore(root)
    protocol = _protocol(store)
    search = _start_lane_search(store, protocol, "search.m1", "fixture-provider")
    failed = {"status": "FAILED", "failure_reason": "fixture failure"}
    search_done = store.finish_search(
        search.search_run_id, failed, actor=_actor(), idempotency_key="search.m1.finish",
    )
    work, version, _, _ = _source(store, "m1", b"Fixture source")
    capture = _start_capture(store, version, "capture.m1-retry")
    capture_payload = {"capture_id": capture.capture_id, **failed}
    capture_done = store.append_capture(
        capture_payload, actor=_actor(), idempotency_key="capture.m1.finish",
    )
    attempt_payload = _attempt_payload("attempt.m1")
    attempt = store.append_codex_attempt(
        attempt_payload, actor=_actor(), idempotency_key="attempt.m1.start",
    )
    terminal_attempt = _terminal_attempt_payload(attempt, "FAILED")
    attempt_done = store.append_codex_attempt(
        terminal_attempt, actor=_actor(), idempotency_key="attempt.m1.finish",
    )
    excluded = MANAGED_FIELDS | {"record_id", "revision", "previous_revision_sha256"}
    cases = [
        ("start_search", [search.model_dump(mode="json", exclude=excluded)], search, "query"),
        ("finish_search", [search.search_run_id, failed], search_done, "failure_reason"),
        ("append_capture", [capture.model_dump(mode="json", exclude=excluded)], capture, "retrieval_locator"),
        ("append_capture", [capture_payload], capture_done, "failure_reason"),
        ("append_codex_attempt", [attempt_payload], attempt, "model"),
        ("append_codex_attempt", [terminal_attempt], attempt_done, "failure_reason"),
        # The normalized work defaults and automatically advanced revision envelope
        # must not create a false conflict for an older generic revision retry.
        ("append_work", [work.model_dump(mode="json", exclude=excluded)], work, "title"),
    ]
    return root, cases


@pytest.mark.parametrize("case_index", range(7))
def test_m1_public_retry_conflict_before_recovery_and_exact_retry_still_recovers(
    tmp_path, m1_public_retries, case_index,
):
    source, cases = m1_public_retries
    root = tmp_path / "case"
    shutil.copytree(source, root)
    method, args, original, changed_field = cases[case_index]
    paths = _prefix_paths(root)
    before = _history_bytes(root)
    changed = json.loads(json.dumps(args))
    changed[-1][changed_field] += " changed"
    common = {"method": method, "key": original.idempotency_key, "target": paths[0]}
    rejected = _result(root, "public-retry", args=changed, fault="file", **common)
    assert rejected["error"] == "LiteratureConflictError", rejected
    assert rejected["events"] == []
    assert _history_bytes(root) == before
    exact_failed = _result(root, "public-retry", args=args, fault="file", **common)
    assert exact_failed["error"] == "OSError", exact_failed
    assert exact_failed["events"] == [["prefix-start", len(paths)]]
    assert _history_bytes(root) == before
    exact = _result(root, "public-retry", args=args, **common)
    _assert_prefix_before_publication(exact, paths)
    assert exact["record_sha256"] == original.record_sha256
    assert _history_bytes(root) == before


@pytest.mark.parametrize("fault", ("file", "reopen", "leaf", "ancestor"))
def test_m1_owned_key_wrong_family_precedes_recovery(tmp_path, m1_public_retries, fault):
    source, cases = m1_public_retries
    root = tmp_path / "case"
    shutil.copytree(source, root)
    store = LiteratureStore(root)
    owner = store.records()[0]
    before = _history_bytes(root)
    result = _result(
        root, "public-retry", method="append_work", args=cases[-1][1],
        key=owner.idempotency_key, target=store._record_relative(owner), fault=fault,
    )
    assert result["error"] == "LiteratureConflictError", result
    assert result["events"] == []
    assert _history_bytes(root) == before


@pytest.mark.parametrize("fault", ("file", "reopen", "leaf", "ancestor"))
def test_m1_exact_retry_failure_preserves_original_history(tmp_path, fault):
    _seed(tmp_path)
    before = _history_bytes(tmp_path)
    result = _result(tmp_path, "exact", fault=fault)
    assert result["error"] == "OSError", result
    assert result["events"][0] == ["prefix-start", 1]
    assert not any(event[0] == "publication" for event in result["events"])
    assert _history_bytes(tmp_path) == before
    exact = _result(tmp_path, "exact")
    _assert_prefix_before_publication(exact, [_A])
    assert _history_bytes(tmp_path) == before


@pytest.mark.parametrize("mode", ("completed", "receipt-tail", "new-completion", "invalid-state"))
@pytest.mark.parametrize("mutation", ("receipt-key", "completion-key", "snapshot", "operation", "intent"))
def test_m1_completion_conflict_precedes_prefix_io(
    tmp_path, prefix_completed_root, mode, mutation,
):
    root = tmp_path / "case"
    shutil.copytree(prefix_completed_root, root)
    store, snapshot, receipt, completed, payload = _completed_retry_inputs(root)
    if mode != "completed":
        (root / store._record_relative(completed)).unlink()
    if mode in {"new-completion", "invalid-state"}:
        (root / store._record_relative(receipt)).unlink()
    if mode == "invalid-state":
        (root / store._record_relative(snapshot)).unlink()
    request = {
        "operation_id": completed.operation_id,
        "snapshot_revision_sha256": snapshot.record_sha256,
        "receipt_payload": payload,
        "receipt_idempotency_key": f"{completed.operation_id}.receipt",
        "completion_idempotency_key": f"{completed.operation_id}.completed",
    }
    if mutation == "receipt-key":
        request["receipt_idempotency_key"] = "wrong.receipt"
    elif mutation == "completion-key":
        request["completion_idempotency_key"] = "wrong.completed"
    elif mutation == "snapshot":
        request["snapshot_revision_sha256"] = "f" * 64
    elif mutation == "operation":
        request.update(operation_id="wrong.operation", receipt_idempotency_key="wrong.operation.receipt",
                       completion_idempotency_key="wrong.operation.completed")
    else:
        request["receipt_payload"] = {
            **payload,
            "operational_status": "NEEDS_MANUAL_REVIEW" if payload["operational_status"] == "CLEAN" else "CLEAN",
        }
    paths = _prefix_paths(root)
    before = _history_bytes(root)
    result = _result(root, "complete", completion=request, target=paths[0], fault="file")
    expected = "LiteratureIntegrityError" if mutation == "intent" and mode in {
        "receipt-tail", "new-completion",
    } else "LiteratureConflictError"
    assert result["error"] == expected, result
    assert result["events"] == []
    assert _history_bytes(root) == before


@pytest.mark.parametrize("action", ("changed-intent", "exact"))
def test_m1_malformed_history_precedes_retry_handling(tmp_path, action):
    _seed(tmp_path)
    (tmp_path / _A).write_bytes(b"{}\n")
    before = _history_bytes(tmp_path)
    result = _result(tmp_path, action, fault="malformed")
    assert result["error"] == "LiteratureIntegrityError"
    assert result["events"] == []
    assert _history_bytes(tmp_path) == before


def test_m1_immutable_freeze_intent_and_exact_retry(tmp_path, prefix_completed_root):
    root = tmp_path / "case"
    shutil.copytree(prefix_completed_root, root)
    store = LiteratureStore(root)
    freeze = next(item for item in store.records() if type(item).family == "dossier-freezes")
    payload = {
        "freeze_id": freeze.freeze_id, "dossier_id": freeze.dossier_id,
        "dossier_revision_sha256": freeze.dossier_revision_sha256,
    }
    paths = _prefix_paths(root)
    before = _history_bytes(root)
    common = {"method": "freeze_dossier", "key": freeze.idempotency_key, "target": paths[0]}
    result = _result(root, "public-retry", args=[{**payload, "freeze_id": "freeze.changed"}],
                     fault="file", **common)
    assert result["error"] == "LiteratureConflictError", result
    assert result["events"] == []
    assert _history_bytes(root) == before
    exact = _result(root, "public-retry", args=[payload], **common)
    _assert_prefix_before_publication(exact, paths)
    assert exact["record_sha256"] == freeze.record_sha256
    assert _history_bytes(root) == before


@pytest.mark.parametrize("owned_phase", ("receipt", "completed"))
def test_m1_completion_owned_key_conflict_precedes_recovery(
    tmp_path, prefix_completed_root, owned_phase,
):
    from tests.test_literature_stage1 import _actor, _protocol_payload

    root = tmp_path / "case"
    shutil.copytree(prefix_completed_root, root)
    store, snapshot, receipt, completed, payload = _completed_retry_inputs(root)
    (root / store._record_relative(completed)).unlink()
    (root / store._record_relative(receipt)).unlink()
    store.append_protocol(
        _protocol_payload(protocol_id="protocol.key-owner", lineage="lineage.key-owner"),
        actor=_actor(), idempotency_key=f"{completed.operation_id}.{owned_phase}",
    )
    before = _history_bytes(root)
    paths = _prefix_paths(root)
    request = {
        "operation_id": completed.operation_id, "snapshot_revision_sha256": snapshot.record_sha256,
        "receipt_payload": payload, "receipt_idempotency_key": f"{completed.operation_id}.receipt",
        "completion_idempotency_key": f"{completed.operation_id}.completed",
    }
    result = _result(root, "complete", completion=request, target=paths[0], fault="file")
    assert result["error"] == "LiteratureConflictError", result
    assert "already owned" in result["message"]
    assert result["events"] == []
    assert _history_bytes(root) == before


def test_m1_tampered_receipt_tail_precedes_invalid_completion(tmp_path, prefix_completed_root):
    root = tmp_path / "case"
    shutil.copytree(prefix_completed_root, root)
    store, snapshot, receipt, completed, payload = _completed_retry_inputs(root)
    (root / store._record_relative(completed)).unlink()
    receipt_path = root / store._record_relative(receipt)
    material = json.loads(receipt_path.read_bytes())
    material["operation_id"] = "wrong.operation"
    receipt_path.write_bytes(canonical_json_bytes(material))
    before = _history_bytes(root)
    result = _result(root, "complete", fault="malformed", completion={
        "operation_id": completed.operation_id, "snapshot_revision_sha256": snapshot.record_sha256,
        "receipt_payload": payload, "receipt_idempotency_key": "wrong.receipt",
        "completion_idempotency_key": "wrong.completed",
    })
    assert result["error"] == "LiteratureIntegrityError", result
    assert result["events"] == []
    assert _history_bytes(root) == before


def test_m1_fresh_append_keeps_existing_recovery_before_normalization(tmp_path, m1_public_retries):
    source, cases = m1_public_retries
    root = tmp_path / "case"
    shutil.copytree(source, root)
    payload = {**cases[-1][1][0], "source_category": "INVALID"}
    paths = _prefix_paths(root)
    before = _history_bytes(root)
    result = _result(root, "public-retry", method="append_work", args=[payload],
                     key="fresh.invalid", target=paths[0], fault="file")
    assert result["error"] == "OSError", result
    assert result["events"] == [["prefix-start", len(paths)]]
    assert _history_bytes(root) == before
