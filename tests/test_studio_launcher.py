from __future__ import annotations

import os
from pathlib import Path
import shutil
import signal
import socket
import time

from alphaquest.studio.launcher import start_studio, stop_studio, studio_status


def _free_port() -> int:
    with socket.socket() as listener:
        listener.bind(("127.0.0.1", 0))
        return int(listener.getsockname()[1])


def test_background_launcher_starts_ui_and_durable_worker_then_stops(tmp_path: Path) -> None:
    apps = tmp_path / "apps"
    apps.mkdir()
    source_app = Path(__file__).resolve().parents[1] / "apps/research_studio.py"
    shutil.copy2(source_app, apps / "research_studio.py")
    port = _free_port()

    try:
        started = start_studio(
            project_root=tmp_path,
            port=port,
            background=True,
            open_browser=False,
        )
        assert started["running"] is True
        assert started["worker_running"] is True
        assert started["healthy"] is True
        assert started["url"] == f"http://127.0.0.1:{port}"
        assert studio_status(project_root=tmp_path)["healthy"] is True
    finally:
        stopped = stop_studio(project_root=tmp_path)

    assert stopped["running"] is False
    assert stopped["worker_running"] is False


def test_restart_replaces_orphan_worker_instead_of_launching_a_second_one(tmp_path: Path) -> None:
    apps = tmp_path / "apps"
    apps.mkdir()
    source_app = Path(__file__).resolve().parents[1] / "apps/research_studio.py"
    shutil.copy2(source_app, apps / "research_studio.py")
    port = _free_port()

    try:
        first = start_studio(
            project_root=tmp_path,
            port=port,
            background=True,
            open_browser=False,
        )
        old_worker = int(first["worker_pid"])
        os.kill(int(first["pid"]), signal.SIGTERM)
        deadline = time.monotonic() + 10
        while studio_status(project_root=tmp_path)["running"] and time.monotonic() < deadline:
            time.sleep(0.1)
        orphaned = studio_status(project_root=tmp_path)
        assert orphaned["running"] is False
        assert orphaned["worker_running"] is True

        restarted = start_studio(
            project_root=tmp_path,
            port=port,
            background=True,
            open_browser=False,
        )
        assert restarted["healthy"] is True
        assert restarted["worker_pid"] != old_worker
    finally:
        stop_studio(project_root=tmp_path)
