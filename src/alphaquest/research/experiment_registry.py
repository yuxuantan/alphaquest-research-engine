"""Append-only accounting for every reserved PnL-bearing experiment.

The experiment registry is intentionally separate from the generated research
catalog.  A reservation exists before a PnL-bearing stage starts and continues
to count as a trial even when execution fails or is cancelled.  JSONL records
are chained by SHA-256 so mutation, deletion, reordering, and conflicting
attempt reuse fail closed.  An atomically replaced head receipt binds the
terminal record hash and record count so tail truncation is detectable too.
"""

from __future__ import annotations

from collections import Counter
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime
import hashlib
import json
import os
from pathlib import Path
import re
from typing import Any, Iterable, Iterator, Mapping

try:  # AlphaQuest is developed on POSIX; the fallback still preserves validation.
    import fcntl
except ImportError:  # pragma: no cover - exercised only on non-POSIX platforms
    fcntl = None


EXPERIMENT_EVENT_SCHEMA = "alphaquest.experiment-registry-event/v1"
EXPERIMENT_HEAD_SCHEMA = "alphaquest.experiment-registry-head/v1"
RESERVED = "RESERVED"
RUNNING = "RUNNING"
TERMINAL_STATUSES = frozenset({"COMPLETED", "FAILED", "CANCELLED"})
STRICT_RESEARCH_VERDICTS = frozenset({"PASS", "FAIL", "NEEDS MANUAL REVIEW"})
_SHA256 = re.compile(r"^[0-9a-f]{64}$")
_IDENTIFIER = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]{0,127}$")
_KIND = re.compile(r"^[a-z][a-z0-9_]{0,63}$")


class ExperimentRegistryError(RuntimeError):
    """Base class for experiment accounting errors."""


class ExperimentConflictError(ExperimentRegistryError):
    """Raised when an attempt identifier is reused with different inputs."""


class ExperimentIntegrityError(ExperimentRegistryError):
    """Raised when the append-only log or its state machine has been altered."""


class ExperimentTransitionError(ExperimentRegistryError):
    """Raised when a requested state transition is not legal."""


@dataclass(frozen=True)
class AttemptReservation:
    campaign_id: str
    variant_id: str
    attempt_id: str
    kind: str
    economic_edge_fingerprint_sha256: str
    research_objectives_sha256: str
    config_sha256: str
    data_sha256: str
    parameter_grid_sha256: str
    stages: tuple[str, ...]
    reserved_at: str
    parent_attempt_id: str | None = None
    parent_recorded_in_registry: bool | None = None
    parent_evidence_sha256: str | None = None

    def __post_init__(self) -> None:
        for label, value in (
            ("campaign_id", self.campaign_id),
            ("variant_id", self.variant_id),
            ("attempt_id", self.attempt_id),
        ):
            _require_identifier(value, label)
        if self.parent_attempt_id is not None:
            _require_identifier(self.parent_attempt_id, "parent_attempt_id")
            if self.parent_attempt_id == self.attempt_id:
                raise ExperimentRegistryError("An experiment attempt cannot be its own parent.")
            if not isinstance(self.parent_recorded_in_registry, bool):
                raise ExperimentRegistryError(
                    "A child attempt must explicitly declare whether its parent is recorded in this registry."
                )
            if self.parent_recorded_in_registry:
                if self.parent_evidence_sha256 is not None:
                    raise ExperimentRegistryError(
                        "A registry-recorded parent must use the registry chain, not external parent evidence."
                    )
            else:
                _require_sha256(self.parent_evidence_sha256, "parent_evidence_sha256")
        elif self.parent_recorded_in_registry is not None or self.parent_evidence_sha256 is not None:
            raise ExperimentRegistryError("Parent lineage fields require parent_attempt_id.")
        if not _KIND.fullmatch(self.kind):
            raise ExperimentRegistryError(
                "Experiment kind must start with a lowercase letter and contain only lowercase letters, digits, or '_'."
            )
        for label, value in (
            ("economic_edge_fingerprint_sha256", self.economic_edge_fingerprint_sha256),
            ("research_objectives_sha256", self.research_objectives_sha256),
            ("config_sha256", self.config_sha256),
            ("data_sha256", self.data_sha256),
            ("parameter_grid_sha256", self.parameter_grid_sha256),
        ):
            _require_sha256(value, label)
        if not isinstance(self.stages, tuple) or not self.stages:
            raise ExperimentRegistryError("A PnL-bearing attempt must reserve at least one stage.")
        if len(self.stages) != len(set(self.stages)):
            raise ExperimentRegistryError("Reserved PnL-bearing stages must be unique and ordered.")
        for stage in self.stages:
            if not isinstance(stage, str) or not _IDENTIFIER.fullmatch(stage):
                raise ExperimentRegistryError(f"Invalid reserved stage name {stage!r}.")
        _require_aware_timestamp(self.reserved_at, "reserved_at")

    def event_payload(self) -> dict[str, Any]:
        return {
            "schema": EXPERIMENT_EVENT_SCHEMA,
            "event_type": "ATTEMPT_RESERVED",
            "campaign_id": self.campaign_id,
            "variant_id": self.variant_id,
            "attempt_id": self.attempt_id,
            "parent_attempt_id": self.parent_attempt_id,
            "parent_recorded_in_registry": self.parent_recorded_in_registry,
            "parent_evidence_sha256": self.parent_evidence_sha256,
            "kind": self.kind,
            "economic_edge_fingerprint_sha256": self.economic_edge_fingerprint_sha256,
            "research_objectives_sha256": self.research_objectives_sha256,
            "config_sha256": self.config_sha256,
            "data_sha256": self.data_sha256,
            "parameter_grid_sha256": self.parameter_grid_sha256,
            "stages": list(self.stages),
            "recorded_at": self.reserved_at,
            "status": RESERVED,
        }

    @classmethod
    def from_event(cls, event: Mapping[str, Any]) -> "AttemptReservation":
        try:
            stages = event["stages"]
            if not isinstance(stages, list):
                raise TypeError("stages")
            return cls(
                campaign_id=str(event["campaign_id"]),
                variant_id=str(event["variant_id"]),
                attempt_id=str(event["attempt_id"]),
                parent_attempt_id=(
                    None if event.get("parent_attempt_id") is None else str(event["parent_attempt_id"])
                ),
                parent_recorded_in_registry=event.get("parent_recorded_in_registry"),
                parent_evidence_sha256=(
                    None if event.get("parent_evidence_sha256") is None else str(event["parent_evidence_sha256"])
                ),
                kind=str(event["kind"]),
                economic_edge_fingerprint_sha256=str(event["economic_edge_fingerprint_sha256"]),
                research_objectives_sha256=str(event["research_objectives_sha256"]),
                config_sha256=str(event["config_sha256"]),
                data_sha256=str(event["data_sha256"]),
                parameter_grid_sha256=str(event["parameter_grid_sha256"]),
                stages=tuple(str(item) for item in stages),
                reserved_at=str(event["recorded_at"]),
            )
        except (KeyError, TypeError) as exc:
            raise ExperimentIntegrityError(f"Malformed reservation record: missing {exc}.") from exc


@dataclass(frozen=True)
class AttemptStatusTransition:
    campaign_id: str
    variant_id: str
    attempt_id: str
    from_status: str
    to_status: str
    recorded_at: str
    reason: str

    def __post_init__(self) -> None:
        for label, value in (
            ("campaign_id", self.campaign_id),
            ("variant_id", self.variant_id),
            ("attempt_id", self.attempt_id),
        ):
            _require_identifier(value, label)
        if (self.from_status, self.to_status) != (RESERVED, RUNNING):
            raise ExperimentTransitionError("Non-terminal experiment transitions are limited to RESERVED -> RUNNING.")
        _require_aware_timestamp(self.recorded_at, "recorded_at")
        _require_reason(self.reason)

    def event_payload(self) -> dict[str, Any]:
        return {
            "schema": EXPERIMENT_EVENT_SCHEMA,
            "event_type": "ATTEMPT_STATUS_TRANSITION",
            "campaign_id": self.campaign_id,
            "variant_id": self.variant_id,
            "attempt_id": self.attempt_id,
            "from_status": self.from_status,
            "to_status": self.to_status,
            "recorded_at": self.recorded_at,
            "reason": self.reason,
        }

    @classmethod
    def from_event(cls, event: Mapping[str, Any]) -> "AttemptStatusTransition":
        try:
            return cls(
                campaign_id=str(event["campaign_id"]),
                variant_id=str(event["variant_id"]),
                attempt_id=str(event["attempt_id"]),
                from_status=str(event["from_status"]),
                to_status=str(event["to_status"]),
                recorded_at=str(event["recorded_at"]),
                reason=str(event["reason"]),
            )
        except (KeyError, TypeError) as exc:
            raise ExperimentIntegrityError(f"Malformed status transition record: missing {exc}.") from exc


@dataclass(frozen=True)
class AttemptResolution:
    campaign_id: str
    variant_id: str
    attempt_id: str
    from_status: str
    terminal_status: str
    recorded_at: str
    reason: str
    research_verdict: str
    result_sha256: str | None = None

    def __post_init__(self) -> None:
        for label, value in (
            ("campaign_id", self.campaign_id),
            ("variant_id", self.variant_id),
            ("attempt_id", self.attempt_id),
        ):
            _require_identifier(value, label)
        if self.from_status not in {RESERVED, RUNNING}:
            raise ExperimentTransitionError("A resolution must start from RESERVED or RUNNING.")
        if self.terminal_status not in TERMINAL_STATUSES:
            raise ExperimentTransitionError(
                f"terminal_status must be one of {sorted(TERMINAL_STATUSES)}."
            )
        _require_aware_timestamp(self.recorded_at, "recorded_at")
        _require_reason(self.reason)
        if self.research_verdict not in STRICT_RESEARCH_VERDICTS:
            raise ExperimentRegistryError(
                f"research_verdict must be one of {sorted(STRICT_RESEARCH_VERDICTS)}."
            )
        if self.terminal_status == "COMPLETED" and self.result_sha256 is None:
            raise ExperimentRegistryError("A completed experiment requires a hash-bound result.")
        if self.result_sha256 is not None:
            _require_sha256(self.result_sha256, "result_sha256")

    def event_payload(self) -> dict[str, Any]:
        return {
            "schema": EXPERIMENT_EVENT_SCHEMA,
            "event_type": "ATTEMPT_RESOLVED",
            "campaign_id": self.campaign_id,
            "variant_id": self.variant_id,
            "attempt_id": self.attempt_id,
            "from_status": self.from_status,
            "terminal_status": self.terminal_status,
            "recorded_at": self.recorded_at,
            "reason": self.reason,
            "research_verdict": self.research_verdict,
            "result_sha256": self.result_sha256,
        }

    @classmethod
    def from_event(cls, event: Mapping[str, Any]) -> "AttemptResolution":
        try:
            return cls(
                campaign_id=str(event["campaign_id"]),
                variant_id=str(event["variant_id"]),
                attempt_id=str(event["attempt_id"]),
                from_status=str(event["from_status"]),
                terminal_status=str(event["terminal_status"]),
                recorded_at=str(event["recorded_at"]),
                reason=str(event["reason"]),
                research_verdict=str(event["research_verdict"]),
                result_sha256=None if event.get("result_sha256") is None else str(event["result_sha256"]),
            )
        except (KeyError, TypeError) as exc:
            raise ExperimentIntegrityError(f"Malformed resolution record: missing {exc}.") from exc


def reservation_from_campaign_config(
    config: Mapping[str, Any],
    *,
    config_sha256: str,
    data_sha256: str,
    economic_edge_fingerprint: Mapping[str, Any] | str,
    reserved_at: str,
    parent_recorded_in_registry: bool | None = None,
    parent_evidence_sha256: str | None = None,
) -> AttemptReservation:
    """Build a reservation from a canonicalized, approved campaign config.

    ``config_sha256`` and ``data_sha256`` should come from the current mechanics
    approval gate.  The economic fingerprint may be passed as the campaign
    mapping or as its already-canonicalized SHA-256 digest.
    """

    if not isinstance(config, Mapping):
        raise ExperimentRegistryError("Campaign config must be a mapping before attempt reservation.")
    campaign_tests = config.get("campaign_tests")
    stage_order = campaign_tests.get("stage_order") if isinstance(campaign_tests, Mapping) else None
    if not isinstance(stage_order, list) or not stage_order:
        raise ExperimentRegistryError("Campaign config must declare the ordered PnL-bearing stage set.")
    grid_section = config.get("core_grid")
    parameter_grid = grid_section.get("parameters") if isinstance(grid_section, Mapping) else None
    if not isinstance(parameter_grid, Mapping):
        raise ExperimentRegistryError("Campaign config must declare core_grid.parameters before reservation.")
    objectives = config.get("research_objectives")
    objectives_sha256 = config.get("research_objectives_sha256")
    _require_sha256(objectives_sha256, "research_objectives_sha256")
    if isinstance(objectives, Mapping) and _sha256_json(objectives) != objectives_sha256:
        raise ExperimentRegistryError("Campaign research objectives have drifted from their declared hash.")
    edge_sha256 = (
        economic_edge_fingerprint
        if isinstance(economic_edge_fingerprint, str)
        else _sha256_json(economic_edge_fingerprint)
    )
    _require_sha256(edge_sha256, "economic_edge_fingerprint_sha256")
    attempt_kind = str(config.get("attempt_kind") or "")
    parent_attempt_id = (
        None if config.get("parent_attempt_id") in (None, "") else str(config["parent_attempt_id"])
    )
    if parent_attempt_id is not None and parent_recorded_in_registry is None:
        raise ExperimentRegistryError(
            "Child campaign config requires an explicit registered-parent decision or hash-bound legacy parent evidence."
        )
    return AttemptReservation(
        campaign_id=str(config.get("campaign_id") or ""),
        variant_id=str(config.get("variant_id") or ""),
        attempt_id=str(config.get("attempt_id") or ""),
        parent_attempt_id=parent_attempt_id,
        parent_recorded_in_registry=parent_recorded_in_registry,
        parent_evidence_sha256=parent_evidence_sha256,
        kind=attempt_kind,
        economic_edge_fingerprint_sha256=edge_sha256,
        research_objectives_sha256=str(objectives_sha256),
        config_sha256=config_sha256,
        data_sha256=data_sha256,
        parameter_grid_sha256=_sha256_json(parameter_grid),
        stages=tuple(str(item) for item in stage_order),
        reserved_at=reserved_at,
    )


class ExperimentRegistry:
    """A hash-chained JSONL registry with an immutable attempt state machine."""

    def __init__(self, path: str | Path):
        self.path = Path(path)
        self.lock_path = self.path.with_suffix(f"{self.path.suffix}.lock")
        self.head_path = self.path.with_suffix(f"{self.path.suffix}.head.json")

    def reserve(self, reservation: AttemptReservation) -> dict[str, Any]:
        """Reserve a PnL-bearing attempt, idempotently for identical inputs."""

        payload = reservation.event_payload()
        with self._write_lock():
            events, state = self._load_and_replay()
            exact = _event_by_fingerprint(events, _event_fingerprint(payload))
            if exact is not None:
                return exact
            key = _attempt_key(payload)
            if key in state["reservations"]:
                raise ExperimentConflictError(
                    f"Attempt {reservation.campaign_id}/{reservation.variant_id}/{reservation.attempt_id} "
                    "is already reserved with different immutable inputs."
                )
            if reservation.parent_attempt_id is not None:
                parent_matches = [
                    candidate
                    for candidate in state["reservations"]
                    if candidate[0] == reservation.campaign_id and candidate[2] == reservation.parent_attempt_id
                ]
                if reservation.parent_recorded_in_registry and not parent_matches:
                    raise ExperimentConflictError(
                        f"Parent attempt {reservation.parent_attempt_id!r} is not reserved in campaign "
                        f"{reservation.campaign_id!r}."
                    )
                if not reservation.parent_recorded_in_registry and parent_matches:
                    raise ExperimentConflictError(
                        f"Parent attempt {reservation.parent_attempt_id!r} is already in this registry; "
                        "reserve the child with parent_recorded_in_registry=True."
                    )
            return self._append(payload, events)

    def transition(self, transition: AttemptStatusTransition) -> dict[str, Any]:
        payload = transition.event_payload()
        with self._write_lock():
            events, state = self._load_and_replay()
            exact = _event_by_fingerprint(events, _event_fingerprint(payload))
            if exact is not None:
                return exact
            key = _attempt_key(payload)
            _require_reserved_key(state, key)
            current = state["statuses"][key]
            if current != transition.from_status:
                raise ExperimentTransitionError(
                    f"Attempt {_format_key(key)} is {current}, not {transition.from_status}."
                )
            return self._append(payload, events)

    def resolve(self, resolution: AttemptResolution) -> dict[str, Any]:
        payload = resolution.event_payload()
        with self._write_lock():
            events, state = self._load_and_replay()
            exact = _event_by_fingerprint(events, _event_fingerprint(payload))
            if exact is not None:
                return exact
            key = _attempt_key(payload)
            _require_reserved_key(state, key)
            current = state["statuses"][key]
            if current != resolution.from_status:
                raise ExperimentTransitionError(
                    f"Attempt {_format_key(key)} is {current}, not {resolution.from_status}."
                )
            return self._append(payload, events)

    def events(self) -> list[dict[str, Any]]:
        events, _ = self._load_and_replay()
        return events

    def attempts(self) -> list[dict[str, Any]]:
        """Return reservation identities with current operational state."""

        _, state = self._load_and_replay()
        rows: list[dict[str, Any]] = []
        for key, reservation in state["reservations"].items():
            rows.append(
                {
                    **_event_core(reservation),
                    "current_status": state["statuses"][key],
                    "resolution": (
                        None if key not in state["resolutions"] else _event_core(state["resolutions"][key])
                    ),
                }
            )
        return sorted(rows, key=lambda item: (item["campaign_id"], item["variant_id"], item["attempt_id"]))

    def current_status(self, campaign_id: str, variant_id: str, attempt_id: str) -> str:
        _, state = self._load_and_replay()
        key = (campaign_id, variant_id, attempt_id)
        _require_reserved_key(state, key)
        return str(state["statuses"][key])

    def trial_count(self, economic_edge_fingerprint_sha256: str) -> int:
        """Count all reservations for an edge, including failed/cancelled work."""

        _require_sha256(economic_edge_fingerprint_sha256, "economic_edge_fingerprint_sha256")
        _, state = self._load_and_replay()
        return sum(
            1
            for reservation in state["reservations"].values()
            if reservation["economic_edge_fingerprint_sha256"] == economic_edge_fingerprint_sha256
        )

    def trial_counts_by_edge(self) -> dict[str, int]:
        _, state = self._load_and_replay()
        counts = Counter(
            reservation["economic_edge_fingerprint_sha256"]
            for reservation in state["reservations"].values()
        )
        return dict(sorted(counts.items()))

    def _load_and_replay(self) -> tuple[list[dict[str, Any]], dict[str, Any]]:
        events = _read_events(self.path, self.head_path)
        state: dict[str, Any] = {"reservations": {}, "statuses": {}, "resolutions": {}}
        seen_fingerprints: set[str] = set()
        for event in events:
            fingerprint = event["event_fingerprint_sha256"]
            if fingerprint in seen_fingerprints:
                raise ExperimentIntegrityError(f"Duplicate experiment event fingerprint {fingerprint}.")
            seen_fingerprints.add(fingerprint)
            key = _attempt_key(event)
            event_type = event["event_type"]
            try:
                if event_type == "ATTEMPT_RESERVED":
                    reservation = AttemptReservation.from_event(event)
                    if event.get("status") != RESERVED:
                        raise ExperimentIntegrityError("Reservation status must be RESERVED.")
                    if key in state["reservations"]:
                        raise ExperimentIntegrityError(f"Attempt {_format_key(key)} has multiple reservations.")
                    if reservation.parent_attempt_id is not None:
                        parents = [
                            candidate
                            for candidate in state["reservations"]
                            if candidate[0] == reservation.campaign_id
                            and candidate[2] == reservation.parent_attempt_id
                        ]
                        if reservation.parent_recorded_in_registry and not parents:
                            raise ExperimentIntegrityError(
                                f"Attempt {_format_key(key)} names a parent that was not reserved earlier."
                            )
                        if not reservation.parent_recorded_in_registry and parents:
                            raise ExperimentIntegrityError(
                                f"Attempt {_format_key(key)} marks a registry parent as external legacy evidence."
                            )
                    state["reservations"][key] = event
                    state["statuses"][key] = RESERVED
                elif event_type == "ATTEMPT_STATUS_TRANSITION":
                    transition = AttemptStatusTransition.from_event(event)
                    _require_reserved_key(state, key, integrity=True)
                    if state["statuses"][key] != transition.from_status:
                        raise ExperimentIntegrityError(
                            f"Attempt {_format_key(key)} transition starts from stale status {transition.from_status}."
                        )
                    state["statuses"][key] = transition.to_status
                elif event_type == "ATTEMPT_RESOLVED":
                    resolution = AttemptResolution.from_event(event)
                    _require_reserved_key(state, key, integrity=True)
                    if state["statuses"][key] != resolution.from_status:
                        raise ExperimentIntegrityError(
                            f"Attempt {_format_key(key)} resolution starts from stale status {resolution.from_status}."
                        )
                    state["statuses"][key] = resolution.terminal_status
                    state["resolutions"][key] = event
                else:
                    raise ExperimentIntegrityError(f"Unknown experiment event_type {event_type!r}.")
            except ExperimentIntegrityError:
                raise
            except ExperimentRegistryError as exc:
                raise ExperimentIntegrityError(f"Invalid persisted event for {_format_key(key)}: {exc}.") from exc
        return events, state

    def _append(self, payload: Mapping[str, Any], events: list[dict[str, Any]]) -> dict[str, Any]:
        previous = events[-1]["record_sha256"] if events else None
        event = {
            **_canonical_copy(payload),
            "event_fingerprint_sha256": _event_fingerprint(payload),
            "previous_record_sha256": previous,
        }
        event["record_sha256"] = _sha256_json(event)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        encoded = _canonical_json(event) + "\n"
        with self.path.open("a", encoding="utf-8") as handle:
            handle.write(encoded)
            handle.flush()
            os.fsync(handle.fileno())
        _write_head_receipt(
            self.head_path,
            record_count=len(events) + 1,
            terminal_record_sha256=event["record_sha256"],
        )
        return event

    @contextmanager
    def _write_lock(self) -> Iterator[None]:
        self.lock_path.parent.mkdir(parents=True, exist_ok=True)
        with self.lock_path.open("a+", encoding="utf-8") as handle:
            if fcntl is not None:
                fcntl.flock(handle.fileno(), fcntl.LOCK_EX)
            try:
                yield
            finally:
                if fcntl is not None:
                    fcntl.flock(handle.fileno(), fcntl.LOCK_UN)


def _read_events(path: Path, head_path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        if head_path.exists():
            raise ExperimentIntegrityError(
                f"Experiment head receipt exists without its registry: {head_path}."
            )
        return []
    events: list[dict[str, Any]] = []
    previous: str | None = None
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError as exc:
        raise ExperimentIntegrityError(f"Could not read experiment registry {path}: {exc}.") from exc
    for line_number, line in enumerate(lines, start=1):
        if not line.strip():
            raise ExperimentIntegrityError(f"Blank line at {path}:{line_number}; registry framing is ambiguous.")
        try:
            event = json.loads(line)
        except json.JSONDecodeError as exc:
            raise ExperimentIntegrityError(f"Invalid JSON at {path}:{line_number}: {exc}.") from exc
        if not isinstance(event, dict):
            raise ExperimentIntegrityError(f"Registry record at {path}:{line_number} must be a JSON object.")
        if event.get("schema") != EXPERIMENT_EVENT_SCHEMA:
            raise ExperimentIntegrityError(f"Unsupported registry schema at {path}:{line_number}.")
        if event.get("previous_record_sha256") != previous:
            raise ExperimentIntegrityError(f"Broken experiment hash chain at {path}:{line_number}.")
        declared_record = event.get("record_sha256")
        _require_persisted_sha256(declared_record, f"record_sha256 at {path}:{line_number}")
        without_record = dict(event)
        without_record.pop("record_sha256", None)
        actual_record = _sha256_json(without_record)
        if declared_record != actual_record:
            raise ExperimentIntegrityError(f"Experiment record hash mismatch at {path}:{line_number}.")
        declared_fingerprint = event.get("event_fingerprint_sha256")
        _require_persisted_sha256(
            declared_fingerprint, f"event_fingerprint_sha256 at {path}:{line_number}"
        )
        if declared_fingerprint != _event_fingerprint(_event_core(event)):
            raise ExperimentIntegrityError(f"Experiment event fingerprint mismatch at {path}:{line_number}.")
        events.append(event)
        previous = declared_record
    _validate_head_receipt(head_path, events)
    return events


def _write_head_receipt(
    path: Path,
    *,
    record_count: int,
    terminal_record_sha256: str,
) -> None:
    _require_persisted_sha256(terminal_record_sha256, "terminal_record_sha256")
    payload: dict[str, Any] = {
        "schema": EXPERIMENT_HEAD_SCHEMA,
        "record_count": int(record_count),
        "terminal_record_sha256": terminal_record_sha256,
    }
    payload["receipt_sha256"] = _sha256_json(payload)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    try:
        with temporary.open("w", encoding="utf-8") as handle:
            handle.write(_canonical_json(payload) + "\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
        _fsync_directory(path.parent)
    finally:
        if temporary.exists():
            temporary.unlink()


def _validate_head_receipt(path: Path, events: list[dict[str, Any]]) -> None:
    if not events:
        if path.exists():
            raise ExperimentIntegrityError(
                f"Experiment head receipt exists for an empty registry: {path}."
            )
        return
    if not path.is_file():
        raise ExperimentIntegrityError(f"Experiment registry is missing its head receipt: {path}.")
    try:
        receipt = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ExperimentIntegrityError(f"Could not read experiment head receipt {path}: {exc}.") from exc
    if not isinstance(receipt, dict) or receipt.get("schema") != EXPERIMENT_HEAD_SCHEMA:
        raise ExperimentIntegrityError(f"Unsupported or malformed experiment head receipt: {path}.")
    declared_receipt = receipt.get("receipt_sha256")
    _require_persisted_sha256(declared_receipt, f"receipt_sha256 in {path}")
    unsigned = dict(receipt)
    unsigned.pop("receipt_sha256", None)
    if declared_receipt != _sha256_json(unsigned):
        raise ExperimentIntegrityError(f"Experiment head receipt hash mismatch: {path}.")
    if receipt.get("record_count") != len(events):
        raise ExperimentIntegrityError(
            f"Experiment registry tail/count mismatch: receipt has {receipt.get('record_count')}, "
            f"registry has {len(events)}."
        )
    if receipt.get("terminal_record_sha256") != events[-1]["record_sha256"]:
        raise ExperimentIntegrityError("Experiment registry terminal hash does not match its head receipt.")


def _fsync_directory(path: Path) -> None:
    try:
        descriptor = os.open(path, os.O_RDONLY)
    except OSError as exc:
        raise ExperimentIntegrityError(f"Could not open registry directory for fsync: {path}: {exc}.") from exc
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def _event_core(event: Mapping[str, Any]) -> dict[str, Any]:
    return {
        key: _canonical_copy(value)
        for key, value in event.items()
        if key not in {"event_fingerprint_sha256", "previous_record_sha256", "record_sha256"}
    }


def _event_fingerprint(payload: Mapping[str, Any]) -> str:
    return _sha256_json(_event_core(payload))


def _event_by_fingerprint(events: Iterable[dict[str, Any]], fingerprint: str) -> dict[str, Any] | None:
    return next((event for event in events if event["event_fingerprint_sha256"] == fingerprint), None)


def _attempt_key(event: Mapping[str, Any]) -> tuple[str, str, str]:
    try:
        return str(event["campaign_id"]), str(event["variant_id"]), str(event["attempt_id"])
    except KeyError as exc:
        raise ExperimentIntegrityError(f"Experiment event is missing identity field {exc}.") from exc


def _require_reserved_key(
    state: Mapping[str, Any], key: tuple[str, str, str], *, integrity: bool = False
) -> None:
    if key in state["reservations"]:
        return
    message = f"Attempt {_format_key(key)} has no reservation."
    if integrity:
        raise ExperimentIntegrityError(message)
    raise ExperimentTransitionError(message)


def _format_key(key: tuple[str, str, str]) -> str:
    return "/".join(key)


def _canonical_copy(value: Any) -> Any:
    return json.loads(_canonical_json(value))


def _canonical_json(value: Any) -> str:
    try:
        return json.dumps(
            value,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
            allow_nan=False,
        )
    except (TypeError, ValueError) as exc:
        raise ExperimentRegistryError(f"Experiment records must be canonical JSON: {exc}.") from exc


def _sha256_json(value: Any) -> str:
    return hashlib.sha256(_canonical_json(value).encode("utf-8")).hexdigest()


def _require_identifier(value: str, label: str) -> None:
    if not isinstance(value, str) or not _IDENTIFIER.fullmatch(value):
        raise ExperimentRegistryError(f"Invalid experiment {label} {value!r}.")


def _require_sha256(value: str, label: str) -> None:
    if not isinstance(value, str) or not _SHA256.fullmatch(value):
        raise ExperimentRegistryError(f"{label} must be a lowercase SHA-256 hex digest.")


def _require_persisted_sha256(value: Any, label: str) -> None:
    try:
        _require_sha256(value, label)
    except ExperimentRegistryError as exc:
        raise ExperimentIntegrityError(str(exc)) from exc


def _require_aware_timestamp(value: str, label: str) -> None:
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except (AttributeError, ValueError) as exc:
        raise ExperimentRegistryError(f"{label} must be an ISO-8601 timestamp.") from exc
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ExperimentRegistryError(f"{label} must include an explicit timezone offset.")


def _require_reason(value: str) -> None:
    if not isinstance(value, str) or not value.strip():
        raise ExperimentRegistryError("Experiment transition/resolution reason must be substantive.")


__all__ = [
    "EXPERIMENT_EVENT_SCHEMA",
    "EXPERIMENT_HEAD_SCHEMA",
    "RESERVED",
    "RUNNING",
    "STRICT_RESEARCH_VERDICTS",
    "TERMINAL_STATUSES",
    "AttemptReservation",
    "AttemptResolution",
    "AttemptStatusTransition",
    "ExperimentConflictError",
    "ExperimentIntegrityError",
    "ExperimentRegistry",
    "ExperimentRegistryError",
    "ExperimentTransitionError",
    "reservation_from_campaign_config",
]
