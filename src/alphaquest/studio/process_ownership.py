"""OS-process ownership for durable Studio jobs.

Campaign runs may create multiprocessing descendants.  Queue state alone cannot
stop those descendants, so every production campaign subprocess owns a
dedicated POSIX process group and a durable registry record.
"""

from __future__ import annotations

from datetime import UTC, datetime
import json
import os
from pathlib import Path
import signal
import subprocess
import time
from typing import Any, Iterable

from alphaquest.research.storage import load_storage_layout


PROCESS_REGISTRY_SCHEMA = "alphaquest.studio-owned-process-group/v1"


def process_registry_root(project_root: str | Path) -> Path:
    root = Path(project_root).resolve()
    return load_storage_layout(root).studio_runtime_root / "job-processes"


def register_process_group(
    project_root: str | Path,
    *,
    job_id: str,
    leader_pid: int,
    process_group_id: int,
    owner_pid: int,
    command: Iterable[str],
) -> Path:
    path = process_registry_root(project_root) / f"{job_id}.json"
    payload = {
        "schema": PROCESS_REGISTRY_SCHEMA,
        "job_id": str(job_id),
        "leader_pid": int(leader_pid),
        "process_group_id": int(process_group_id),
        "owner_pid": int(owner_pid),
        "command": [str(item) for item in command],
        "member_pids": process_group_members(process_group_id),
        "started_at": datetime.now(UTC).isoformat(),
        "updated_at": datetime.now(UTC).isoformat(),
    }
    _atomic_write_json(path, payload)
    return path


def refresh_process_group_record(path: str | Path) -> dict[str, Any] | None:
    record_path = Path(path)
    record = _read_record(record_path)
    if record is None:
        return None
    record["member_pids"] = process_group_members(int(record["process_group_id"]))
    record["updated_at"] = datetime.now(UTC).isoformat()
    _atomic_write_json(record_path, record)
    return record


def unregister_process_group(path: str | Path) -> None:
    Path(path).unlink(missing_ok=True)


def registered_process_groups(project_root: str | Path) -> list[dict[str, Any]]:
    records = []
    for path in sorted(process_registry_root(project_root).glob("*.json")):
        record = _read_record(path)
        if record is not None:
            record["_registry_path"] = str(path)
            records.append(record)
    return records


def terminate_registered_process_groups(
    project_root: str | Path,
    *,
    term_timeout: float = 5.0,
    kill_timeout: float = 5.0,
) -> list[dict[str, Any]]:
    outcomes = []
    for record in registered_process_groups(project_root):
        path = Path(str(record["_registry_path"]))
        pgid = int(record["process_group_id"])
        before = process_group_members(pgid)
        try:
            terminate_process_group(
                pgid,
                term_timeout=term_timeout,
                kill_timeout=kill_timeout,
            )
        except Exception as exc:
            outcomes.append(
                {
                    "job_id": record.get("job_id"),
                    "process_group_id": pgid,
                    "member_pids": before,
                    "terminated": False,
                    "error": f"{type(exc).__name__}: {exc}",
                }
            )
            continue
        unregister_process_group(path)
        outcomes.append(
            {
                "job_id": record.get("job_id"),
                "process_group_id": pgid,
                "member_pids": before,
                "terminated": True,
                "error": None,
            }
        )
    return outcomes


def terminate_process_group(
    process_group_id: int,
    *,
    term_timeout: float = 5.0,
    kill_timeout: float = 5.0,
) -> None:
    pgid = int(process_group_id)
    if pgid <= 1:
        raise ValueError("refusing to terminate an invalid process group")
    if pgid == os.getpgrp():
        raise RuntimeError("refusing to terminate the caller's process group")
    if not process_group_members(pgid):
        return
    _signal_process_group(pgid, signal.SIGTERM)
    if _wait_for_process_group_exit(pgid, term_timeout):
        return
    _signal_process_group(pgid, signal.SIGKILL)
    if not _wait_for_process_group_exit(pgid, kill_timeout):
        members = process_group_members(pgid)
        raise RuntimeError(f"process group {pgid} still has live members after SIGKILL: {members}")


def process_group_members(process_group_id: int) -> list[int]:
    pgid = int(process_group_id)
    try:
        output = subprocess.run(
            ["ps", "-axo", "pid=,pgid=,state="],
            check=False,
            capture_output=True,
            text=True,
            timeout=2.0,
        ).stdout
    except (OSError, subprocess.SubprocessError):
        return _process_group_members_by_signal(pgid)
    members = []
    for line in output.splitlines():
        fields = line.split()
        if len(fields) < 3:
            continue
        try:
            pid_value = int(fields[0])
            pgid_value = int(fields[1])
        except ValueError:
            continue
        state = fields[2].upper()
        if pgid_value == pgid and not state.startswith("Z"):
            members.append(pid_value)
    return sorted(set(members))


def _process_group_members_by_signal(pgid: int) -> list[int]:
    try:
        os.killpg(pgid, 0)
    except ProcessLookupError:
        return []
    except PermissionError:
        return [pgid]
    return [pgid]


def _signal_process_group(pgid: int, sig: signal.Signals) -> None:
    try:
        os.killpg(pgid, sig)
    except ProcessLookupError:
        return


def _wait_for_process_group_exit(pgid: int, timeout: float) -> bool:
    deadline = time.monotonic() + max(0.1, float(timeout))
    while time.monotonic() < deadline:
        if not process_group_members(pgid):
            return True
        time.sleep(0.05)
    return not process_group_members(pgid)


def _read_record(path: Path) -> dict[str, Any] | None:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    if payload.get("schema") != PROCESS_REGISTRY_SCHEMA:
        return None
    try:
        int(payload["process_group_id"])
        int(payload["leader_pid"])
        int(payload["owner_pid"])
    except (KeyError, TypeError, ValueError):
        return None
    return payload


def _atomic_write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(f"{path.suffix}.tmp-{os.getpid()}")
    temporary.write_text(
        json.dumps(payload, sort_keys=True, separators=(",", ":")),
        encoding="utf-8",
    )
    temporary.replace(path)


__all__ = [
    "PROCESS_REGISTRY_SCHEMA",
    "process_group_members",
    "process_registry_root",
    "refresh_process_group_record",
    "register_process_group",
    "registered_process_groups",
    "terminate_process_group",
    "terminate_registered_process_groups",
    "unregister_process_group",
]
