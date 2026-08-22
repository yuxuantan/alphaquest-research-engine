from __future__ import annotations

import os
from pathlib import Path
import subprocess
import sys

from alphaquest.studio.process_ownership import (
    process_group_members,
    process_registry_root,
    register_process_group,
    terminate_registered_process_groups,
)


def test_registered_process_group_termination_kills_real_descendants(tmp_path: Path):
    script = """
import signal
import subprocess
import sys
import time

signal.signal(signal.SIGTERM, signal.SIG_IGN)
child = subprocess.Popen([
    sys.executable,
    "-c",
    "import signal,time; signal.signal(signal.SIGTERM, signal.SIG_IGN); time.sleep(60)",
])
print(child.pid, flush=True)
time.sleep(60)
"""
    leader = subprocess.Popen(
        [sys.executable, "-c", script],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        start_new_session=True,
    )
    try:
        assert leader.stdout is not None
        child_pid = int(leader.stdout.readline().strip())
        pgid = os.getpgid(leader.pid)
        registry_path = register_process_group(
            tmp_path,
            job_id="real-process-pool-test",
            leader_pid=leader.pid,
            process_group_id=pgid,
            owner_pid=os.getpid(),
            command=[sys.executable, "-c", script],
        )

        assert leader.pid in process_group_members(pgid)
        assert child_pid in process_group_members(pgid)
        assert registry_path.is_file()

        outcomes = terminate_registered_process_groups(
            tmp_path,
            term_timeout=0.2,
            kill_timeout=2.0,
        )

        leader.wait(timeout=3.0)
        assert outcomes == [
            {
                "job_id": "real-process-pool-test",
                "process_group_id": pgid,
                "member_pids": sorted([leader.pid, child_pid]),
                "terminated": True,
                "error": None,
            }
        ]
        assert process_group_members(pgid) == []
        assert list(process_registry_root(tmp_path).glob("*.json")) == []
    finally:
        if leader.poll() is None:
            os.killpg(os.getpgid(leader.pid), 9)
            leader.wait(timeout=3.0)
