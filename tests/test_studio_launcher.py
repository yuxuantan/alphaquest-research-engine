from __future__ import annotations

import json
import os
from pathlib import Path
import shutil
import signal
import socket
import time
from urllib.request import urlopen

from alphaquest.cli import _parser
from alphaquest.studio.launcher import start_studio, stop_studio, studio_status


def _free_port() -> int:
    with socket.socket() as listener:
        listener.bind(("127.0.0.1", 0))
        return int(listener.getsockname()[1])


def _web_assets(root: Path) -> Path:
    assets = root / "compiled-studio-assets"
    assets.mkdir()
    (assets / "index.html").write_text(
        "<!doctype html><title>AlphaQuest Research Studio</title><div id='root'></div>",
        encoding="utf-8",
    )
    return assets


def test_background_launcher_starts_ui_and_durable_worker_then_stops(
    tmp_path: Path,
    monkeypatch,
) -> None:
    monkeypatch.setenv("ALPHAQUEST_STUDIO_ASSETS_DIR", str(_web_assets(tmp_path)))
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
        assert started["ui_healthy"] is True
        assert started["ui_runtime"] == "react-fastapi"
        assert started["url"] == f"http://127.0.0.1:{port}"
        assert studio_status(project_root=tmp_path)["healthy"] is True
        with urlopen(f"http://127.0.0.1:{port}/healthz", timeout=2) as response:
            health = json.load(response)
        assert health == {
            "status": "ok",
            "ui_runtime": "react-fastapi",
            "assets_ready": True,
        }
    finally:
        stopped = stop_studio(project_root=tmp_path)

    assert stopped["running"] is False
    assert stopped["worker_running"] is False


def test_restart_replaces_orphan_worker_instead_of_launching_a_second_one(
    tmp_path: Path,
    monkeypatch,
) -> None:
    monkeypatch.setenv("ALPHAQUEST_STUDIO_ASSETS_DIR", str(_web_assets(tmp_path)))
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


def test_browser_opens_only_after_http_and_worker_are_healthy(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("ALPHAQUEST_STUDIO_ASSETS_DIR", str(_web_assets(tmp_path)))
    opened: list[tuple[str, bool]] = []

    def record_open(url: str) -> bool:
        opened.append((url, studio_status(project_root=tmp_path)["healthy"]))
        return True

    monkeypatch.setattr("alphaquest.studio.launcher._open_studio_browser", record_open)
    port = _free_port()
    try:
        started = start_studio(project_root=tmp_path, port=port, background=True, open_browser=True)
        assert started["healthy"] is True
        assert opened == [(f"http://127.0.0.1:{port}", True)]
    finally:
        stop_studio(project_root=tmp_path)


def test_already_running_healthy_pair_reopens_browser_without_restarting(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("ALPHAQUEST_STUDIO_ASSETS_DIR", str(_web_assets(tmp_path)))
    opened: list[str] = []
    monkeypatch.setattr(
        "alphaquest.studio.launcher._open_studio_browser",
        lambda url: opened.append(url) or True,
    )
    port = _free_port()

    try:
        first = start_studio(project_root=tmp_path, port=port, background=True, open_browser=False)
        state_path = Path(first["state_path"])
        state_before = state_path.read_bytes()

        reopened = start_studio(project_root=tmp_path, port=port, background=True, open_browser=True)

        assert reopened["healthy"] is True
        assert reopened["pid"] == first["pid"]
        assert reopened["worker_pid"] == first["worker_pid"]
        assert state_path.read_bytes() == state_before
        assert opened == [f"http://127.0.0.1:{port}"]
    finally:
        stop_studio(project_root=tmp_path)


def test_legacy_streamlit_is_an_explicit_cli_fallback() -> None:
    current = _parser().parse_args(["studio", "start"])
    legacy = _parser().parse_args(["studio", "start", "--legacy-streamlit"])

    assert current.legacy_streamlit is False
    assert legacy.legacy_streamlit is True


def test_launcher_migrates_running_legacy_pair_to_requested_react_runtime(tmp_path: Path, monkeypatch) -> None:
    apps = tmp_path / "apps"
    apps.mkdir()
    source_app = Path(__file__).resolve().parents[1] / "apps/research_studio.py"
    shutil.copy2(source_app, apps / "research_studio.py")
    monkeypatch.setenv("ALPHAQUEST_STUDIO_ASSETS_DIR", str(_web_assets(tmp_path)))
    port = _free_port()

    try:
        legacy = start_studio(
            project_root=tmp_path,
            port=port,
            background=True,
            open_browser=False,
            legacy_streamlit=True,
        )
        assert legacy["healthy"] is True
        assert legacy["ui_runtime"] == "legacy-streamlit"

        migrated = start_studio(
            project_root=tmp_path,
            port=port,
            background=True,
            open_browser=False,
        )
        assert migrated["healthy"] is True
        assert migrated["ui_runtime"] == "react-fastapi"
        assert migrated["pid"] != legacy["pid"]
        assert migrated["worker_pid"] != legacy["worker_pid"]
    finally:
        stopped = stop_studio(project_root=tmp_path)

    assert stopped["running"] is False
