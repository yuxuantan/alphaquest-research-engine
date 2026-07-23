"""Local Research Studio process lifecycle helpers."""

from __future__ import annotations

from contextlib import contextmanager
from datetime import datetime, timezone
import fcntl
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import time
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen
import webbrowser

from alphaquest.research.storage import load_storage_layout


STATE_FILENAME = "studio-process.json"
LOG_FILENAME = "studio.log"
WORKER_LOG_FILENAME = "worker.log"
REACT_FASTAPI_RUNTIME = "react-fastapi"
LEGACY_STREAMLIT_RUNTIME = "legacy-streamlit"


def studio_status(*, project_root: str | Path = ".") -> dict[str, Any]:
    root = Path(project_root).resolve()
    state_path, log_path, worker_log_path = _runtime_paths(root)
    state = _read_state(state_path)
    pid = _integer(state.get("pid"))
    ui_runtime = _state_ui_runtime(state)
    running = bool(pid and _pid_matches_studio(pid, state.get("app_path"), ui_runtime))
    worker_pid = _integer(state.get("worker_pid"))
    worker_running = bool(worker_pid and _pid_matches_worker(worker_pid))
    ui_healthy = bool(
        running
        and _studio_http_health(
            state.get("address"),
            state.get("port"),
            ui_runtime,
        )
    )
    return {
        "running": running,
        "healthy": ui_healthy and worker_running,
        "ui_healthy": ui_healthy,
        "ui_runtime": ui_runtime,
        "pid": pid if running else None,
        "worker_running": worker_running,
        "worker_pid": worker_pid if worker_running else None,
        "port": state.get("port"),
        "address": state.get("address"),
        "started_at": state.get("started_at"),
        "url": state.get("url") if running else None,
        "state_path": str(state_path),
        "log_path": str(log_path),
        "worker_log_path": str(worker_log_path),
        "stale_state": bool(state and not (ui_healthy and worker_running)),
    }


def start_studio(
    *,
    project_root: str | Path = ".",
    port: int = 8501,
    address: str = "127.0.0.1",
    background: bool = False,
    open_browser: bool = True,
    legacy_streamlit: bool = False,
) -> dict[str, Any]:
    root = Path(project_root).resolve()
    with _launcher_lock(root):
        return _start_studio_locked(
            project_root=root,
            port=port,
            address=address,
            background=background,
            open_browser=open_browser,
            legacy_streamlit=legacy_streamlit,
        )


def _start_studio_locked(
    *,
    project_root: str | Path,
    port: int,
    address: str,
    background: bool,
    open_browser: bool,
    legacy_streamlit: bool,
) -> dict[str, Any]:
    root = Path(project_root).resolve()
    if not 1 <= int(port) <= 65535:
        raise ValueError("Studio port must be between 1 and 65535")
    if address not in {"127.0.0.1", "localhost"}:
        raise ValueError("V1 Research Studio binds only to the local workstation")

    if legacy_streamlit:
        ui_runtime = LEGACY_STREAMLIT_RUNTIME
        app_path = root / "apps" / "research_studio.py"
        if not app_path.is_file():
            raise FileNotFoundError(f"Legacy Research Studio app is missing: {app_path}")
        try:
            import streamlit  # noqa: F401
        except ImportError as exc:
            raise RuntimeError(
                "Legacy Streamlit dependencies are missing; install the 'dashboard' optional dependencies"
            ) from exc
        command = [
            sys.executable,
            "-m",
            "streamlit",
            "run",
            str(app_path),
            "--server.address",
            address,
            "--server.port",
            str(int(port)),
            "--server.headless",
            "true",
            "--browser.gatherUsageStats",
            "false",
        ]
    else:
        ui_runtime = REACT_FASTAPI_RUNTIME
        app_path = Path(__file__).with_name("web.py").resolve()
        try:
            import fastapi  # noqa: F401
            import uvicorn  # noqa: F401
        except ImportError as exc:
            raise RuntimeError(
                "Research Studio dependencies are missing; an administrator must run `make studio-setup`"
            ) from exc
        command = [
            sys.executable,
            "-m",
            "alphaquest.studio.web",
            "--project-root",
            str(root),
            "--host",
            address,
            "--port",
            str(int(port)),
        ]

    current = studio_status(project_root=root)

    state_path, log_path, worker_log_path = _runtime_paths(root)
    state_path.parent.mkdir(parents=True, exist_ok=True)
    environment = dict(os.environ)
    package_source_root = Path(__file__).resolve().parents[2]
    python_paths = [root / "src", package_source_root]
    for item in (environment.get("PYTHONPATH") or "").split(os.pathsep):
        if item:
            path = Path(item)
            python_paths.append(path if path.is_absolute() else (Path.cwd() / path).resolve())
    environment["PYTHONPATH"] = os.pathsep.join(
        str(path) for path in dict.fromkeys(path.resolve() for path in python_paths if path.exists())
    )
    worker_command = [
        sys.executable,
        "-m",
        "alphaquest.cli",
        "studio",
        "worker",
        "--project-root",
        str(root),
    ]

    if current["running"] and current.get("ui_runtime") != ui_runtime:
        # Interface migrations are coordinated under the same launcher lock.
        # Stop the complete old UI/worker pair before starting the requested
        # runtime so a stale legacy process is never silently revived.
        _stop_studio_locked(project_root=root, timeout_seconds=5.0)
        current = studio_status(project_root=root)
    if current["running"] and current["worker_running"]:
        if current["healthy"] and open_browser and current.get("url"):
            _open_studio_browser(str(current["url"]))
        return current
    if current["running"] and not current["worker_running"]:
        with worker_log_path.open("a", encoding="utf-8") as worker_log:
            worker = subprocess.Popen(  # noqa: S603 - fixed interpreter/module command
                worker_command,
                cwd=root,
                env=environment,
                stdin=subprocess.DEVNULL,
                stdout=worker_log,
                stderr=subprocess.STDOUT,
                start_new_session=True,
            )
        state = _read_state(state_path)
        state["worker_pid"] = worker.pid
        state["worker_started_at"] = datetime.now(timezone.utc).isoformat()
        _atomic_write_json(state_path, state)
        return studio_status(project_root=root)

    if not current["running"] and current["worker_running"]:
        # A dead browser process must never cause a second local worker to be
        # launched. Stop the orphan under the launcher file lock, then start a
        # clean UI/worker pair with one authoritative state record.
        _terminate_pid(
            int(current["worker_pid"]),
            label="orphaned Research Studio worker",
            timeout_seconds=5.0,
        )
        state_path.unlink(missing_ok=True)

    with worker_log_path.open("a", encoding="utf-8") as worker_log:
        worker = subprocess.Popen(  # noqa: S603 - fixed interpreter/module command
            worker_command,
            cwd=root,
            env=environment,
            stdin=subprocess.DEVNULL,
            stdout=worker_log,
            stderr=subprocess.STDOUT,
            start_new_session=True,
        )
    try:
        with log_path.open("a", encoding="utf-8") as log:
            process = subprocess.Popen(  # noqa: S603 - fixed interpreter/module command
                command,
                cwd=root,
                env=environment,
                stdin=subprocess.DEVNULL,
                stdout=log,
                stderr=subprocess.STDOUT,
                start_new_session=True,
            )
    except Exception:
        _terminate_process(worker, label="Research Studio worker", timeout_seconds=5.0)
        raise
    state = {
        "pid": process.pid,
        "port": int(port),
        "address": address,
        "url": f"http://{address}:{int(port)}",
        "started_at": datetime.now(timezone.utc).isoformat(),
        "app_path": str(app_path),
        "ui_runtime": ui_runtime,
        "worker_pid": worker.pid,
        "worker_started_at": datetime.now(timezone.utc).isoformat(),
    }
    _atomic_write_json(state_path, state)
    try:
        status = _wait_for_background_start(
            project_root=root,
            ui_process=process,
            worker_process=worker,
        )
    except Exception:
        if process.poll() is None:
            _terminate_process(process, label="Research Studio", timeout_seconds=5.0)
        if worker.poll() is None:
            _terminate_process(worker, label="Research Studio worker", timeout_seconds=5.0)
        state_path.unlink(missing_ok=True)
        raise

    if open_browser:
        _open_studio_browser(str(status["url"]))
    if background:
        return status

    try:
        exit_code = process.wait()
    finally:
        if process.poll() is None:
            _terminate_process(process, label="Research Studio", timeout_seconds=5.0)
        if worker.poll() is None:
            _terminate_process(worker, label="Research Studio worker", timeout_seconds=5.0)
        state_path.unlink(missing_ok=True)
    return {
        "running": False,
        "worker_running": False,
        "healthy": False,
        "ui_healthy": False,
        "ui_runtime": ui_runtime,
        "exit_code": exit_code,
        "url": f"http://{address}:{port}",
    }


def stop_studio(*, project_root: str | Path = ".", timeout_seconds: float = 5.0) -> dict[str, Any]:
    root = Path(project_root).resolve()
    with _launcher_lock(root):
        return _stop_studio_locked(project_root=root, timeout_seconds=timeout_seconds)


def _stop_studio_locked(*, project_root: str | Path, timeout_seconds: float) -> dict[str, Any]:
    root = Path(project_root).resolve()
    state_path, _, _ = _runtime_paths(root)
    state = _read_state(state_path)
    pid = _integer(state.get("pid"))
    worker_pid = _integer(state.get("worker_pid"))
    errors: list[str] = []
    if pid and _pid_matches_studio(pid, state.get("app_path"), _state_ui_runtime(state)):
        try:
            _terminate_pid(pid, label="Research Studio", timeout_seconds=timeout_seconds)
        except RuntimeError as exc:
            errors.append(str(exc))
    if worker_pid and _pid_matches_worker(worker_pid):
        try:
            _terminate_pid(worker_pid, label="Research Studio worker", timeout_seconds=timeout_seconds)
        except RuntimeError as exc:
            errors.append(str(exc))
    state_path.unlink(missing_ok=True)
    if errors:
        raise RuntimeError("; ".join(errors))
    return studio_status(project_root=root)


@contextmanager
def _launcher_lock(root: Path):
    runtime = load_storage_layout(root).studio_runtime_root
    lock_path = runtime / "studio-launch.lock"
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    with lock_path.open("a+", encoding="utf-8") as handle:
        fcntl.flock(handle.fileno(), fcntl.LOCK_EX)
        try:
            yield
        finally:
            fcntl.flock(handle.fileno(), fcntl.LOCK_UN)


def _runtime_paths(root: Path) -> tuple[Path, Path, Path]:
    layout = load_storage_layout(root)
    runtime = getattr(layout, "studio_runtime_root", layout.run_store_root / "studio-runtime")
    return Path(runtime) / STATE_FILENAME, Path(runtime) / LOG_FILENAME, Path(runtime) / WORKER_LOG_FILENAME


def _state_ui_runtime(state: dict[str, Any]) -> str:
    runtime = str(state.get("ui_runtime") or "").strip()
    if runtime in {REACT_FASTAPI_RUNTIME, LEGACY_STREAMLIT_RUNTIME}:
        return runtime
    # State files written before the React migration point at the Streamlit
    # script. Preserve stop/status behavior for an already-running old process.
    app_path = str(state.get("app_path") or "")
    if app_path.endswith("research_studio.py"):
        return LEGACY_STREAMLIT_RUNTIME
    return REACT_FASTAPI_RUNTIME


def _studio_http_health(address: Any, port: Any, ui_runtime: str) -> bool:
    if address not in {"127.0.0.1", "localhost"}:
        return False
    try:
        port_number = int(port)
    except (TypeError, ValueError):
        return False
    if not 1 <= port_number <= 65535:
        return False
    health_path = "/_stcore/health" if ui_runtime == LEGACY_STREAMLIT_RUNTIME else "/healthz"
    request = Request(
        f"http://{address}:{port_number}{health_path}",
        headers={"Accept": "application/json"},
    )
    try:
        with urlopen(request, timeout=0.35) as response:  # noqa: S310 - validated localhost-only URL
            if response.status != 200:
                return False
            if ui_runtime == LEGACY_STREAMLIT_RUNTIME:
                return True
            payload = json.loads(response.read().decode("utf-8"))
    except (HTTPError, URLError, OSError, TimeoutError, json.JSONDecodeError):
        return False
    return (
        isinstance(payload, dict)
        and payload.get("status") == "ok"
        and payload.get("ui_runtime") == REACT_FASTAPI_RUNTIME
        and payload.get("assets_ready") is True
    )


def _open_studio_browser(url: str) -> bool:
    try:
        return bool(webbrowser.open(url, new=1))
    except Exception:  # pragma: no cover - workstation browser integration varies
        return False


def _wait_for_background_start(
    *,
    project_root: Path,
    ui_process: subprocess.Popen,
    worker_process: subprocess.Popen,
    timeout_seconds: float = 15.0,
) -> dict[str, Any]:
    deadline = time.monotonic() + timeout_seconds
    while time.monotonic() < deadline:
        if ui_process.poll() is not None:
            raise RuntimeError(f"Research Studio exited during startup with code {ui_process.returncode}")
        if worker_process.poll() is not None:
            raise RuntimeError(f"Research Studio worker exited during startup with code {worker_process.returncode}")
        status = studio_status(project_root=project_root)
        if status["healthy"]:
            return status
        time.sleep(0.1)
    state = studio_status(project_root=project_root)
    raise RuntimeError(
        f"Research Studio did not become healthy at {state.get('url') or 'its local URL'} "
        f"within {timeout_seconds:g}s"
    )


def _read_state(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return value if isinstance(value, dict) else {}


def _atomic_write_json(path: Path, value: dict[str, Any]) -> None:
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    temporary.replace(path)


def _integer(value: Any) -> int | None:
    try:
        result = int(value)
    except (TypeError, ValueError):
        return None
    return result if result > 0 else None


def _pid_exists(pid: int) -> bool:
    try:
        reaped, _status = os.waitpid(pid, os.WNOHANG)
    except ChildProcessError:
        reaped = 0
    if reaped == pid:
        return False
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    return True


def _pid_matches_studio(pid: int, app_path: Any, ui_runtime: str) -> bool:
    if not _pid_exists(pid):
        return False
    try:
        output = subprocess.run(
            ["ps", "-p", str(pid), "-o", "command="],
            check=False,
            capture_output=True,
            text=True,
            timeout=2,
        ).stdout
    except (OSError, subprocess.SubprocessError):
        return False
    if ui_runtime == LEGACY_STREAMLIT_RUNTIME:
        return "streamlit" in output and (not app_path or str(app_path) in output)
    return "alphaquest.studio.web" in output


def _pid_matches_worker(pid: int) -> bool:
    if not _pid_exists(pid):
        return False
    try:
        output = subprocess.run(
            ["ps", "-p", str(pid), "-o", "command="],
            check=False,
            capture_output=True,
            text=True,
            timeout=2,
        ).stdout
    except (OSError, subprocess.SubprocessError):
        return False
    return "alphaquest.cli" in output and "studio worker" in output


def _terminate_pid(pid: int, *, label: str, timeout_seconds: float) -> None:
    if not _pid_exists(pid):
        return
    os.kill(pid, signal.SIGTERM)
    deadline = time.monotonic() + max(0.1, timeout_seconds)
    while time.monotonic() < deadline and _pid_exists(pid):
        time.sleep(0.1)
    if _pid_exists(pid):
        raise RuntimeError(f"{label} process {pid} did not stop cleanly")


def _terminate_process(process: subprocess.Popen, *, label: str, timeout_seconds: float) -> None:
    if process.poll() is not None:
        return
    process.terminate()
    try:
        process.wait(timeout=max(0.1, timeout_seconds))
    except subprocess.TimeoutExpired as exc:
        raise RuntimeError(f"{label} process {process.pid} did not stop cleanly") from exc
