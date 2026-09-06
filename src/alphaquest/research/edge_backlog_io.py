"""Repository-rooted, no-follow filesystem primitives for the P2 backlog."""

from __future__ import annotations

from contextlib import contextmanager
from dataclasses import dataclass
import errno
import os
from pathlib import Path, PurePosixPath
import re
import secrets
import stat
from types import MappingProxyType
from typing import Callable, Iterator, Mapping

import yaml

from alphaquest.research.storage import StorageLayout, load_storage_layout


CANONICAL_EDGE_BACKLOG_RELATIVE = "research/edge_backlog"
_LAYOUT_RELATIVE = "config/storage_layout.yaml"
_DEFAULT_CACHE_RELATIVE = "catalogs/edge_backlog_history.jsonl"
_DEFAULT_RUNTIME_RELATIVE = "run-store/studio-runtime"
_NOFOLLOW = getattr(os, "O_NOFOLLOW", 0)
_DIRECTORY = getattr(os, "O_DIRECTORY", 0)
_CLOEXEC = getattr(os, "O_CLOEXEC", 0)
_TEST_AFTER_PARENT_OPEN: Callable[[str, str], None] | None = None
_TEST_AFTER_DIRECTORY_ENUMERATION: Callable[[str, str], None] | None = None


@dataclass(frozen=True)
class CanonicalBacklogTree:
    """One descriptor-rooted immutable view of the canonical P2 record tree."""

    observation_ids: tuple[str, ...]
    entry_ids: tuple[str, ...]
    files: Mapping[str, bytes]


@dataclass(frozen=True)
class P2RepositoryPaths:
    project_root: Path
    layout: StorageLayout
    backlog_relative: str
    cache_relative: str
    lock_relative: str

    @property
    def backlog_root(self) -> Path:
        return self.project_root / PurePosixPath(self.backlog_relative)

    @property
    def cache_path(self) -> Path:
        return self.project_root / PurePosixPath(self.cache_relative)

    @property
    def lock_path(self) -> Path:
        return self.project_root / PurePosixPath(self.lock_relative)


def validated_p2_repository_paths(
    project_root: str | Path,
    *,
    layout: StorageLayout | None = None,
) -> P2RepositoryPaths:
    """Load only the fixed layout file and validate P2 write destinations."""

    root = Path(project_root).resolve()
    root.mkdir(parents=True, exist_ok=True)
    raw_layout = read_repository_file_optional(root, _LAYOUT_RELATIVE)
    document: dict[str, object] = {}
    if raw_layout is not None:
        try:
            parsed = yaml.safe_load(raw_layout.decode("utf-8")) or {}
        except (UnicodeDecodeError, yaml.YAMLError) as exc:
            raise ValueError(f"P2 storage layout is malformed: {exc}") from exc
        if not isinstance(parsed, dict):
            raise ValueError("P2 storage layout must be a mapping")
        document = parsed

    backlog_value = document.get("edge_backlog_root", CANONICAL_EDGE_BACKLOG_RELATIVE)
    if backlog_value != CANONICAL_EDGE_BACKLOG_RELATIVE:
        raise ValueError(
            f"edge_backlog_root must be exactly {CANONICAL_EDGE_BACKLOG_RELATIVE!r}"
        )
    cache_relative = _canonical_repository_relative(
        document.get("edge_backlog_history_index", _DEFAULT_CACHE_RELATIVE),
        label="edge_backlog_history_index",
    )
    runtime_relative = _canonical_repository_relative(
        document.get("studio_runtime_root", _DEFAULT_RUNTIME_RELATIVE),
        label="studio_runtime_root",
    )
    lock_relative = f"{runtime_relative}/edge-backlog.lock"

    loaded = layout or load_storage_layout(root, layout_path=_LAYOUT_RELATIVE)
    if loaded.project_root.resolve() != root:
        raise ValueError("P2 storage layout project_root does not match project_root")
    expected_backlog = root / PurePosixPath(CANONICAL_EDGE_BACKLOG_RELATIVE)
    expected_cache = root / PurePosixPath(cache_relative)
    expected_runtime = root / PurePosixPath(runtime_relative)
    if loaded.edge_backlog_root != expected_backlog:
        raise ValueError("P2 canonical backlog root does not match the fixed repository path")
    if loaded.edge_backlog_history_index != expected_cache:
        raise ValueError("P2 derived cache path does not match the lexical layout path")
    if loaded.studio_runtime_root != expected_runtime:
        raise ValueError("P2 lock directory does not match the lexical layout path")

    validate_repository_path_chain(
        root,
        CANONICAL_EDGE_BACKLOG_RELATIVE,
        target_kind="directory",
        allow_missing=True,
    )
    validate_repository_path_chain(root, cache_relative, target_kind="file", allow_missing=True)
    validate_repository_path_chain(root, lock_relative, target_kind="file", allow_missing=True)
    return P2RepositoryPaths(
        project_root=root,
        layout=loaded,
        backlog_relative=CANONICAL_EDGE_BACKLOG_RELATIVE,
        cache_relative=cache_relative,
        lock_relative=lock_relative,
    )


def validate_repository_path_chain(
    project_root: str | Path,
    relative_path: str,
    *,
    target_kind: str,
    allow_missing: bool,
) -> None:
    """Reject symlinks/non-directories in parents and invalid existing targets."""

    root = Path(project_root).resolve()
    relative = _canonical_repository_relative(relative_path, label="repository path")
    try:
        with repository_parent_fd(root, relative, create=False) as (parent_fd, name):
            try:
                metadata = os.stat(name, dir_fd=parent_fd, follow_symlinks=False)
            except FileNotFoundError:
                if allow_missing:
                    return
                raise ValueError(f"required repository path is missing: {relative}") from None
            if target_kind == "directory" and not stat.S_ISDIR(metadata.st_mode):
                raise ValueError(f"repository path is not a real directory: {relative}")
            if target_kind == "file" and not stat.S_ISREG(metadata.st_mode):
                raise ValueError(f"repository path is not a regular file: {relative}")
    except FileNotFoundError:
        if allow_missing:
            return
        raise ValueError(f"required repository parent is missing: {relative}") from None
    except OSError as exc:
        raise ValueError(f"unsafe repository path component for {relative}: {exc}") from exc


@contextmanager
def repository_parent_fd(
    project_root: str | Path,
    relative_path: str,
    *,
    create: bool,
) -> Iterator[tuple[int, str]]:
    """Open a validated parent directory by walking from the repository fd."""

    root = Path(project_root).resolve()
    relative = _canonical_repository_relative(relative_path, label="repository path")
    parts = PurePosixPath(relative).parts
    root_fd = os.open(root, os.O_RDONLY | _DIRECTORY | _NOFOLLOW | _CLOEXEC)
    current_fd = os.dup(root_fd)
    os.close(root_fd)
    try:
        for component in parts[:-1]:
            if create:
                try:
                    os.mkdir(component, mode=0o755, dir_fd=current_fd)
                except FileExistsError:
                    pass
            next_fd = os.open(
                component,
                os.O_RDONLY | _DIRECTORY | _NOFOLLOW | _CLOEXEC,
                dir_fd=current_fd,
            )
            os.close(current_fd)
            current_fd = next_fd
        yield current_fd, parts[-1]
    finally:
        os.close(current_fd)


def read_repository_file(project_root: str | Path, relative_path: str) -> bytes:
    data = read_repository_file_optional(project_root, relative_path)
    if data is None:
        raise FileNotFoundError(f"repository file not found: {relative_path}")
    return data


def read_repository_file_optional(
    project_root: str | Path,
    relative_path: str,
) -> bytes | None:
    root = Path(project_root).resolve()
    relative = _canonical_repository_relative(relative_path, label="repository file")
    try:
        with repository_parent_fd(root, relative, create=False) as (parent_fd, name):
            try:
                descriptor = os.open(
                    name,
                    os.O_RDONLY | _NOFOLLOW | _CLOEXEC,
                    dir_fd=parent_fd,
                )
            except FileNotFoundError:
                return None
            try:
                if not stat.S_ISREG(os.fstat(descriptor).st_mode):
                    raise ValueError(f"repository target is not a regular file: {relative}")
                with os.fdopen(descriptor, "rb", closefd=False) as handle:
                    return handle.read()
            finally:
                os.close(descriptor)
    except FileNotFoundError:
        return None
    except OSError as exc:
        raise ValueError(f"unsafe repository file path for {relative}: {exc}") from exc


def read_canonical_backlog_tree(project_root: str | Path) -> CanonicalBacklogTree:
    """Read the complete canonical record tree without following any path.

    Every directory remains descriptor-bound while its children are enumerated
    and opened.  Consequently a rename or symlink substitution cannot redirect
    a read to a different tree between discovery and record opening.
    """

    root = Path(project_root).resolve()
    files: dict[str, bytes] = {}
    try:
        with repository_directory_fd(
            root,
            CANONICAL_EDGE_BACKLOG_RELATIVE,
            allow_missing=True,
        ) as backlog_fd:
            if backlog_fd is None:
                return CanonicalBacklogTree((), (), MappingProxyType(files))
            backlog_names = frozenset(os.listdir(backlog_fd))
            _run_test_directory_enumeration_hook(
                "canonical-root",
                CANONICAL_EDGE_BACKLOG_RELATIVE,
            )
            observation_ids = _read_canonical_collection(
                backlog_fd,
                collection="observations",
                present="observations" in backlog_names,
                allowed_children=("revisions",),
                required_children=("revisions",),
                files=files,
            )
            entry_ids = _read_canonical_collection(
                backlog_fd,
                collection="entries",
                present="entries" in backlog_names,
                allowed_children=("revisions", "decisions", "links"),
                required_children=("revisions",),
                files=files,
            )
    except OSError as exc:
        raise ValueError(f"unsafe canonical backlog topology: {exc}") from exc
    return CanonicalBacklogTree(
        observation_ids,
        entry_ids,
        MappingProxyType(files),
    )


@contextmanager
def repository_directory_fd(
    project_root: str | Path,
    relative_path: str,
    *,
    allow_missing: bool,
) -> Iterator[int | None]:
    """Open a repository directory component-by-component without following links."""

    root = Path(project_root).resolve()
    relative = _canonical_repository_relative(relative_path, label="repository directory")
    current_fd = os.open(root, os.O_RDONLY | _DIRECTORY | _NOFOLLOW | _CLOEXEC)
    missing = False
    try:
        for component in PurePosixPath(relative).parts:
            try:
                next_fd = _open_directory_at(current_fd, component)
            except FileNotFoundError:
                if not allow_missing:
                    raise
                missing = True
                break
            os.close(current_fd)
            current_fd = next_fd
        yield None if missing else current_fd
    finally:
        os.close(current_fd)


def _read_canonical_collection(
    backlog_fd: int,
    *,
    collection: str,
    present: bool,
    allowed_children: tuple[str, ...],
    required_children: tuple[str, ...],
    files: dict[str, bytes],
) -> tuple[str, ...]:
    if not present:
        return ()
    collection_fd = _open_directory_at(backlog_fd, collection)
    relative = f"{CANONICAL_EDGE_BACKLOG_RELATIVE}/{collection}"
    try:
        object_ids = tuple(sorted(os.listdir(collection_fd)))
        _run_test_directory_enumeration_hook("canonical-collection", relative)
        for object_id in object_ids:
            object_fd = _open_directory_at(collection_fd, object_id)
            try:
                _read_canonical_object(
                    object_fd,
                    relative=f"{relative}/{object_id}",
                    allowed_children=allowed_children,
                    required_children=required_children,
                    files=files,
                )
            finally:
                os.close(object_fd)
        return object_ids
    finally:
        os.close(collection_fd)


def _read_canonical_object(
    object_fd: int,
    *,
    relative: str,
    allowed_children: tuple[str, ...],
    required_children: tuple[str, ...],
    files: dict[str, bytes],
) -> None:
    children = tuple(sorted(os.listdir(object_fd)))
    _run_test_directory_enumeration_hook("canonical-object", relative)
    unexpected = sorted(set(children) - set(allowed_children))
    if unexpected:
        raise ValueError(
            f"unexpected canonical object component at {relative}: {unexpected[0]}"
        )
    missing = sorted(set(required_children) - set(children))
    if missing:
        raise ValueError(f"missing canonical object directory at {relative}: {missing[0]}")
    for child in children:
        child_fd = _open_directory_at(object_fd, child)
        try:
            _read_canonical_record_directory(
                child_fd,
                relative=f"{relative}/{child}",
                files=files,
            )
        finally:
            os.close(child_fd)


def _read_canonical_record_directory(
    directory_fd: int,
    *,
    relative: str,
    files: dict[str, bytes],
) -> None:
    names = tuple(sorted(os.listdir(directory_fd)))
    _run_test_directory_enumeration_hook("canonical-records", relative)
    for name in names:
        if re.fullmatch(r"[0-9]{6}\.json", name) is None:
            raise ValueError(f"unexpected canonical record name at {relative}: {name}")
        descriptor = os.open(
            name,
            os.O_RDONLY | os.O_NONBLOCK | _NOFOLLOW | _CLOEXEC,
            dir_fd=directory_fd,
        )
        try:
            metadata = os.fstat(descriptor)
            if not stat.S_ISREG(metadata.st_mode):
                raise ValueError(f"canonical record is not a regular file: {relative}/{name}")
            if metadata.st_mode & (stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH):
                raise ValueError(f"canonical record must not be executable: {relative}/{name}")
            with os.fdopen(descriptor, "rb", closefd=False) as handle:
                files[f"{relative}/{name}"] = handle.read()
        finally:
            os.close(descriptor)


def _open_directory_at(parent_fd: int, name: str) -> int:
    descriptor = os.open(
        name,
        os.O_RDONLY | _DIRECTORY | _NOFOLLOW | _CLOEXEC,
        dir_fd=parent_fd,
    )
    try:
        if not stat.S_ISDIR(os.fstat(descriptor).st_mode):
            raise ValueError(f"canonical component is not a directory: {name}")
        return descriptor
    except Exception:
        os.close(descriptor)
        raise


def exclusive_write_repository_file(
    project_root: str | Path,
    relative_path: str,
    data: bytes,
) -> None:
    root = Path(project_root).resolve()
    relative = _canonical_repository_relative(relative_path, label="canonical record")
    with repository_parent_fd(root, relative, create=True) as (parent_fd, name):
        _run_test_parent_open_hook("exclusive-write", relative)
        descriptor = os.open(
            name,
            os.O_WRONLY | os.O_CREAT | os.O_EXCL | _NOFOLLOW | _CLOEXEC,
            0o644,
            dir_fd=parent_fd,
        )
        try:
            with os.fdopen(descriptor, "wb", closefd=False) as handle:
                handle.write(data)
                handle.flush()
                os.fsync(handle.fileno())
            os.fsync(parent_fd)
        except Exception:
            try:
                os.unlink(name, dir_fd=parent_fd)
            except OSError:
                pass
            raise
        finally:
            os.close(descriptor)


def unlink_repository_file(project_root: str | Path, relative_path: str) -> None:
    root = Path(project_root).resolve()
    relative = _canonical_repository_relative(relative_path, label="canonical record")
    with repository_parent_fd(root, relative, create=False) as (parent_fd, name):
        os.unlink(name, dir_fd=parent_fd)
        os.fsync(parent_fd)


@contextmanager
def repository_file_lock(
    project_root: str | Path,
    relative_path: str,
    *,
    exclusive: bool,
) -> Iterator[None]:
    import fcntl

    root = Path(project_root).resolve()
    relative = _canonical_repository_relative(relative_path, label="P2 lock")
    with repository_parent_fd(root, relative, create=True) as (parent_fd, name):
        _run_test_parent_open_hook("lock-open", relative)
        descriptor = os.open(
            name,
            os.O_RDWR | os.O_CREAT | _NOFOLLOW | _CLOEXEC,
            0o644,
            dir_fd=parent_fd,
        )
        try:
            if not stat.S_ISREG(os.fstat(descriptor).st_mode):
                raise ValueError("P2 lock target is not a regular file")
            fcntl.flock(descriptor, fcntl.LOCK_EX if exclusive else fcntl.LOCK_SH)
            try:
                yield
            finally:
                fcntl.flock(descriptor, fcntl.LOCK_UN)
        finally:
            os.close(descriptor)


def atomic_replace_repository_file(
    project_root: str | Path,
    relative_path: str,
    data: bytes,
) -> None:
    root = Path(project_root).resolve()
    relative = _canonical_repository_relative(relative_path, label="derived cache")
    with repository_parent_fd(root, relative, create=True) as (parent_fd, name):
        _run_test_parent_open_hook("cache-replace", relative)
        try:
            metadata = os.stat(name, dir_fd=parent_fd, follow_symlinks=False)
        except FileNotFoundError:
            metadata = None
        if metadata is not None and not stat.S_ISREG(metadata.st_mode):
            raise ValueError("derived cache target is not a regular file")

        temporary_name = ""
        descriptor = -1
        for _attempt in range(64):
            temporary_name = f".{name}.{secrets.token_hex(12)}.tmp"
            try:
                descriptor = os.open(
                    temporary_name,
                    os.O_WRONLY | os.O_CREAT | os.O_EXCL | _NOFOLLOW | _CLOEXEC,
                    0o600,
                    dir_fd=parent_fd,
                )
                break
            except FileExistsError:
                continue
        if descriptor < 0:
            raise OSError(errno.EEXIST, "could not allocate derived-cache temporary file")
        try:
            with os.fdopen(descriptor, "wb", closefd=False) as handle:
                handle.write(data)
                handle.flush()
                os.fsync(handle.fileno())
            os.close(descriptor)
            descriptor = -1
            os.replace(
                temporary_name,
                name,
                src_dir_fd=parent_fd,
                dst_dir_fd=parent_fd,
            )
            temporary_name = ""
            os.fsync(parent_fd)
        finally:
            if descriptor >= 0:
                os.close(descriptor)
            if temporary_name:
                try:
                    os.unlink(temporary_name, dir_fd=parent_fd)
                except FileNotFoundError:
                    pass


def _canonical_repository_relative(value: object, *, label: str) -> str:
    if not isinstance(value, str) or not value or value != value.strip():
        raise ValueError(f"{label} must be a nonblank lexical repository-relative path")
    if value.startswith("/") or "\\" in value or "\x00" in value or value.endswith("/"):
        raise ValueError(f"{label} must be a canonical repository-relative POSIX path")
    path = PurePosixPath(value)
    if any(part in {"", ".", ".."} for part in path.parts) or path.as_posix() != value:
        raise ValueError(f"{label} must be a canonical repository-relative POSIX path")
    return value


def _run_test_parent_open_hook(operation: str, relative_path: str) -> None:
    """Test-only deterministic race hook; production leaves it unset."""

    hook = _TEST_AFTER_PARENT_OPEN
    if hook is not None:
        hook(operation, relative_path)


def _run_test_directory_enumeration_hook(operation: str, relative_path: str) -> None:
    """Test-only deterministic read-race hook; production leaves it unset."""

    hook = _TEST_AFTER_DIRECTORY_ENUMERATION
    if hook is not None:
        hook(operation, relative_path)


__all__ = [
    "CANONICAL_EDGE_BACKLOG_RELATIVE",
    "CanonicalBacklogTree",
    "P2RepositoryPaths",
    "atomic_replace_repository_file",
    "exclusive_write_repository_file",
    "read_repository_file",
    "read_repository_file_optional",
    "read_canonical_backlog_tree",
    "repository_directory_fd",
    "repository_file_lock",
    "unlink_repository_file",
    "validate_repository_path_chain",
    "validated_p2_repository_paths",
]
