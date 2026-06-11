from __future__ import annotations

from collections.abc import Callable, Iterable
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from datetime import date, datetime, time
import json
import os
from pathlib import Path
import threading
import time as time_module
from typing import Any
from zoneinfo import ZoneInfo

import pandas as pd

from propstack.utils.time import parse_time


DEFAULT_DATASET = "GLBX.MDP3"
DEFAULT_SYMBOLS = "ES.FUT"
DEFAULT_SCHEMA = "trades"
DEFAULT_STYPE_IN = "parent"
DEFAULT_STYPE_OUT = "instrument_id"
DEFAULT_TIMEZONE = "America/New_York"
DEFAULT_RTH_START = "09:30:00"
DEFAULT_RTH_END = "16:00:00"


@dataclass(frozen=True)
class RthSession:
    session_date: date
    start: datetime
    end: datetime


@dataclass(frozen=True)
class DownloadConfig:
    output_dir: Path
    dataset: str = DEFAULT_DATASET
    symbols: str = DEFAULT_SYMBOLS
    schema: str = DEFAULT_SCHEMA
    stype_in: str = DEFAULT_STYPE_IN
    stype_out: str = DEFAULT_STYPE_OUT
    timezone: str = DEFAULT_TIMEZONE
    file_prefix: str = "glbx-mdp3"
    workers: int = 8
    request_rate_limit_per_sec: float = 50.0
    retries: int = 5
    force: bool = False


class RateLimiter:
    def __init__(self, per_second: float):
        if per_second <= 0:
            raise ValueError("per_second must be greater than 0.")
        self._interval = 1.0 / per_second
        self._lock = threading.Lock()
        self._next_at = 0.0

    def wait(self) -> None:
        with self._lock:
            now = time_module.monotonic()
            wait_seconds = max(0.0, self._next_at - now)
            self._next_at = max(now, self._next_at) + self._interval
        if wait_seconds:
            time_module.sleep(wait_seconds)


def iter_rth_sessions(
    start_date: str | date,
    end_date: str | date,
    *,
    timezone: str = DEFAULT_TIMEZONE,
    rth_start: str = DEFAULT_RTH_START,
    rth_end: str = DEFAULT_RTH_END,
    weekdays_only: bool = True,
) -> list[RthSession]:
    start = pd.Timestamp(start_date).date()
    end = pd.Timestamp(end_date).date()
    if end < start:
        raise ValueError("end_date must be greater than or equal to start_date.")

    tz = ZoneInfo(timezone)
    start_t = parse_time(rth_start)
    end_t = parse_time(rth_end)
    sessions = []
    for day_ts in pd.date_range(start, end, freq="D"):
        day = day_ts.date()
        if weekdays_only and day.weekday() >= 5:
            continue
        sessions.append(
            RthSession(
                session_date=day,
                start=datetime.combine(day, start_t, tzinfo=tz),
                end=datetime.combine(day, end_t, tzinfo=tz),
            )
        )
    return sessions


def filter_available_sessions(
    sessions: Iterable[RthSession],
    conditions: Iterable[dict[str, Any]],
) -> list[RthSession]:
    available_dates = {
        pd.Timestamp(row["date"]).date()
        for row in conditions
        if str(row.get("condition", "")).lower() in {"available", "degraded"}
    }
    return [session for session in sessions if session.session_date in available_dates]


def session_output_path(config: DownloadConfig, session: RthSession) -> Path:
    day = session.session_date.strftime("%Y%m%d")
    return config.output_dir / f"{config.file_prefix}-{day}.rth.trades.dbn.zst"


def build_download_plan(
    sessions: Iterable[RthSession],
    config: DownloadConfig,
) -> list[RthSession]:
    if config.force:
        return list(sessions)
    return [session for session in sessions if not session_output_path(config, session).exists()]


def get_api_key(env_name: str = "DATABENTO_API_KEY") -> str:
    value = os.getenv(env_name)
    if not value:
        raise ValueError(f"Missing Databento API key. Set ${env_name} before running.")
    return value


def get_dataset_conditions(
    *,
    api_key: str,
    dataset: str,
    start_date: str | date,
    end_date: str | date,
) -> list[dict[str, Any]]:
    import databento as db

    client = db.Historical(api_key)
    return client.metadata.get_dataset_condition(
        dataset=dataset,
        start_date=str(pd.Timestamp(start_date).date()),
        end_date=str(pd.Timestamp(end_date).date()),
    )


def estimate_download_cost(
    sessions: list[RthSession],
    *,
    api_key: str,
    config: DownloadConfig,
    mode: str = "exact",
    sample_days: int = 20,
    status_callback: Callable[[str], None] | None = None,
) -> dict[str, Any]:
    if mode not in {"exact", "sample"}:
        raise ValueError("mode must be exact or sample.")
    if not sessions:
        return {"mode": mode, "sessions": 0, "sampled_sessions": 0, "estimated_cost": 0.0}

    if mode == "sample":
        selected = _even_sample(sessions, sample_days)
    else:
        selected = sessions

    import databento as db

    client = db.Historical(api_key)
    limiter = RateLimiter(18.0)
    costs = []
    samples = []
    for index, session in enumerate(selected, start=1):
        limiter.wait()
        cost = client.metadata.get_cost(
            dataset=config.dataset,
            symbols=config.symbols,
            schema=config.schema,
            stype_in=config.stype_in,
            start=session.start,
            end=session.end,
        )
        costs.append(float(cost))
        samples.append(
            {
                "date": session.session_date.isoformat(),
                "start": session.start.isoformat(),
                "end": session.end.isoformat(),
                "cost": float(cost),
            }
        )
        if status_callback and (index == 1 or index == len(selected) or index % 25 == 0):
            status_callback(f"Estimated {index:,}/{len(selected):,} session costs...")

    sampled_total = float(sum(costs))
    if mode == "sample":
        estimate = sampled_total / len(selected) * len(sessions)
    else:
        estimate = sampled_total
    return {
        "mode": mode,
        "sessions": len(sessions),
        "sampled_sessions": len(selected),
        "samples": samples,
        "sample_cost": sampled_total,
        "estimated_cost": estimate,
        "average_session_cost": sampled_total / len(selected),
    }


def download_rth_trades(
    sessions: list[RthSession],
    *,
    api_key: str,
    config: DownloadConfig,
    status_callback: Callable[[str], None] | None = None,
) -> list[dict[str, Any]]:
    if config.workers <= 0:
        raise ValueError("workers must be greater than 0.")
    config.output_dir.mkdir(parents=True, exist_ok=True)
    limiter = RateLimiter(config.request_rate_limit_per_sec)
    results = []
    completed = 0
    total = len(sessions)
    _emit(status_callback, f"Downloading {total:,} RTH sessions to {config.output_dir}...")
    with ThreadPoolExecutor(max_workers=config.workers) as executor:
        futures = [
            executor.submit(_download_one_session, session, api_key, config, limiter)
            for session in sessions
        ]
        for future in as_completed(futures):
            result = future.result()
            results.append(result)
            completed += 1
            if completed == 1 or completed == total or completed % 25 == 0:
                _emit(
                    status_callback,
                    f"Downloaded/skipped {completed:,}/{total:,} sessions "
                    f"({result['status']}: {result['date']}).",
                )
    return sorted(results, key=lambda row: row["date"])


def write_manifest(
    manifest_path: str | Path,
    *,
    config: DownloadConfig,
    requested_sessions: list[RthSession],
    planned_sessions: list[RthSession],
    results: list[dict[str, Any]] | None = None,
    cost_estimate: dict[str, Any] | None = None,
) -> None:
    manifest = {
        "dataset": config.dataset,
        "symbols": config.symbols,
        "schema": config.schema,
        "stype_in": config.stype_in,
        "stype_out": config.stype_out,
        "timezone": config.timezone,
        "output_dir": str(config.output_dir),
        "requested_sessions": len(requested_sessions),
        "planned_sessions": len(planned_sessions),
        "cost_estimate": cost_estimate,
        "results": results or [],
    }
    path = Path(manifest_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(manifest, indent=2, default=str) + "\n")


def _download_one_session(
    session: RthSession,
    api_key: str,
    config: DownloadConfig,
    limiter: RateLimiter,
) -> dict[str, Any]:
    import databento as db
    from databento.common.error import BentoHttpError

    out = session_output_path(config, session)
    if out.exists() and not config.force:
        return _result(session, out, "skipped", bytes_written=out.stat().st_size)

    tmp = out.with_name(out.name + ".part")
    client = db.Historical(api_key)
    for attempt in range(config.retries + 1):
        try:
            if tmp.exists():
                tmp.unlink()
            limiter.wait()
            client.timeseries.get_range(
                dataset=config.dataset,
                symbols=config.symbols,
                schema=config.schema,
                stype_in=config.stype_in,
                stype_out=config.stype_out,
                start=session.start,
                end=session.end,
                path=tmp,
            )
            tmp.replace(out)
            return _result(session, out, "downloaded", bytes_written=out.stat().st_size)
        except BentoHttpError as exc:
            if tmp.exists():
                tmp.unlink()
            if attempt >= config.retries or not _is_retryable_http_error(exc):
                return _result(session, out, "failed", error=str(exc))
            _sleep_before_retry(exc, attempt)
        except Exception as exc:
            if tmp.exists():
                tmp.unlink()
            if attempt >= config.retries:
                return _result(session, out, "failed", error=str(exc))
            _sleep_before_retry(None, attempt)

    return _result(session, out, "failed", error="retry loop exhausted")


def _is_retryable_http_error(exc) -> bool:
    status = getattr(exc, "http_status", None)
    return status == 429 or status == 408 or (status is not None and int(status) >= 500)


def _sleep_before_retry(exc, attempt: int) -> None:
    retry_after = None
    if exc is not None:
        retry_after = getattr(exc, "headers", {}).get("Retry-After")
    if retry_after is not None:
        try:
            wait_seconds = float(retry_after)
        except (TypeError, ValueError):
            wait_seconds = None
    else:
        wait_seconds = None
    if wait_seconds is None:
        wait_seconds = min(60.0, 2.0**attempt)
    time_module.sleep(wait_seconds)


def _even_sample(values: list[RthSession], sample_size: int) -> list[RthSession]:
    if sample_size <= 0:
        raise ValueError("sample_days must be greater than 0.")
    if len(values) <= sample_size:
        return values
    if sample_size == 1:
        return [values[len(values) // 2]]
    step = (len(values) - 1) / (sample_size - 1)
    indexes = sorted({int(round(index * step)) for index in range(sample_size)})
    return [values[index] for index in indexes]


def _result(
    session: RthSession,
    path: Path,
    status: str,
    *,
    bytes_written: int | None = None,
    error: str | None = None,
) -> dict[str, Any]:
    return {
        "date": session.session_date.isoformat(),
        "start": session.start.isoformat(),
        "end": session.end.isoformat(),
        "path": str(path),
        "status": status,
        "bytes": bytes_written,
        "error": error,
    }


def _emit(callback: Callable[[str], None] | None, message: str) -> None:
    if callback:
        callback(message)
