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
print(json.dumps({"record_id": result.record_id, "events": events}))
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


def test_prefix_durability_does_not_turn_changed_intent_into_exact_retry(tmp_path: Path) -> None:
    _seed(tmp_path)
    result = _result(tmp_path, "changed-intent")
    assert result["error"] == "LiteratureConflictError"
    assert "idempotency" in result["message"]
    assert not any(event[0] == "publication" for event in result["events"])
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
