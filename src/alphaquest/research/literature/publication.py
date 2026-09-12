"""Crash-safe P3 canonical-record and runtime-artifact publication."""

from __future__ import annotations

from contextlib import contextmanager
from dataclasses import dataclass
import hashlib
import os
from pathlib import Path, PurePosixPath
import secrets
import stat
from typing import Callable, Iterator


LITERATURE_CANONICAL_RELATIVE = "research/literature"
LITERATURE_RUNTIME_RELATIVE = "run-store/literature"
LITERATURE_CANONICAL_STAGING_RELATIVE = f"{LITERATURE_RUNTIME_RELATIVE}/canonical-staging"
LITERATURE_ARTIFACT_STAGING_RELATIVE = f"{LITERATURE_RUNTIME_RELATIVE}/artifact-staging"
LITERATURE_ARTIFACT_QUARANTINE_RELATIVE = f"{LITERATURE_RUNTIME_RELATIVE}/artifact-quarantine"
LITERATURE_ARTIFACT_KINDS = frozenset(
    {"artifacts", "extracted", "provider-traces", "codex-io"}
)
_NOFOLLOW = getattr(os, "O_NOFOLLOW", 0)
_DIRECTORY = getattr(os, "O_DIRECTORY", 0)
_CLOEXEC = getattr(os, "O_CLOEXEC", 0)
_TEST_PUBLICATION_HOOK: Callable[[str, str], None] | None = None
_TEST_ARTIFACT_PUBLICATION_HOOK: Callable[[str, str], None] | None = None
_TEST_DURABILITY_HOOK: Callable[[str, str], None] | None = None


@dataclass(frozen=True)
class _Directory:
    descriptor: int
    relative: str


@dataclass(frozen=True)
class _CreatedDirectory:
    name: str
    descriptor: int
    relative: str
    parent_descriptor: int
    parent_relative: str


@dataclass(frozen=True)
class _PublicationTarget:
    directories: tuple[_Directory, ...]
    created_directories: tuple[_CreatedDirectory, ...]
    name: str
    relative: str

    @property
    def parent(self) -> _Directory:
        return self.directories[-1]


def _repository_relative(relative_path: str, *, label: str) -> str:
    if (
        not isinstance(relative_path, str)
        or not relative_path
        or relative_path != relative_path.strip()
        or relative_path.startswith("/")
        or "\\" in relative_path
        or "\x00" in relative_path
        or relative_path.endswith("/")
    ):
        raise ValueError(f"{label} must be a canonical repository-relative POSIX path")
    path = PurePosixPath(relative_path)
    if any(part in {"", ".", ".."} for part in path.parts) or path.as_posix() != relative_path:
        raise ValueError(f"{label} must be a canonical repository-relative POSIX path")
    return path.as_posix()


def _canonical_relative(relative_path: str) -> str:
    relative = _repository_relative(relative_path, label="P3 canonical record path")
    path = PurePosixPath(relative)
    canonical_parts = PurePosixPath(LITERATURE_CANONICAL_RELATIVE).parts
    if len(path.parts) <= len(canonical_parts) or path.parts[: len(canonical_parts)] != canonical_parts:
        raise ValueError("P3 canonical records must be beneath research/literature")
    return relative


def _artifact_relative(relative_path: str) -> str:
    relative = _repository_relative(relative_path, label="P3 runtime artifact path")
    parts = PurePosixPath(relative).parts
    runtime_parts = PurePosixPath(LITERATURE_RUNTIME_RELATIVE).parts
    if (
        len(parts) != len(runtime_parts) + 4
        or parts[: len(runtime_parts)] != runtime_parts
        or parts[len(runtime_parts)] not in LITERATURE_ARTIFACT_KINDS
        or parts[len(runtime_parts) + 1] != "sha256"
    ):
        raise ValueError("P3 runtime artifact path does not use the canonical content-addressed layout")
    prefix, digest = parts[-2:]
    if (
        len(digest) != 64
        or any(character not in "0123456789abcdef" for character in digest)
        or prefix != digest[:2]
    ):
        raise ValueError("P3 runtime artifact path does not match its lowercase SHA-256 digest")
    return relative


def _run_hook(
    hook: Callable[[str, str], None] | None,
    phase: str,
    relative_path: str,
) -> None:
    if hook is not None:
        hook(phase, relative_path)


def _write_all(descriptor: int, data: bytes) -> None:
    offset = 0
    while offset < len(data):
        written = os.write(descriptor, data[offset:])
        if written <= 0:  # pragma: no cover - defensive platform failure
            raise OSError("P3 staging write made no forward progress")
        offset += written


def _open_directory_at(parent_fd: int, component: str) -> int:
    descriptor = os.open(
        component,
        os.O_RDONLY | _DIRECTORY | _NOFOLLOW | _CLOEXEC,
        dir_fd=parent_fd,
    )
    try:
        if not stat.S_ISDIR(os.fstat(descriptor).st_mode):
            raise ValueError(f"P3 publication path component is not a directory: {component}")
        return descriptor
    except Exception:
        os.close(descriptor)
        raise


@contextmanager
def _publication_target(
    project_root: str | Path,
    relative_path: str,
    *,
    create: bool,
) -> Iterator[_PublicationTarget]:
    """Open/create one P3 path descriptor-relatively and retain its ancestry."""

    root = Path(project_root).resolve()
    relative = _repository_relative(relative_path, label="P3 publication path")
    parts = PurePosixPath(relative).parts
    root_fd = os.open(root, os.O_RDONLY | _DIRECTORY | _NOFOLLOW | _CLOEXEC)
    directories = [_Directory(root_fd, ".")]
    created_directories: list[_CreatedDirectory] = []
    try:
        current_fd = root_fd
        current_parts: list[str] = []
        for component in parts[:-1]:
            created = False
            if create:
                try:
                    os.mkdir(component, mode=0o755, dir_fd=current_fd)
                    created = True
                except FileExistsError:
                    pass
            next_fd = _open_directory_at(current_fd, component)
            current_parts.append(component)
            child_relative = PurePosixPath(*current_parts).as_posix()
            if created:
                created_directories.append(
                    _CreatedDirectory(
                        name=component,
                        descriptor=next_fd,
                        relative=child_relative,
                        parent_descriptor=current_fd,
                        parent_relative=directories[-1].relative,
                    )
                )
            directories.append(_Directory(next_fd, child_relative))
            current_fd = next_fd
        yield _PublicationTarget(
            tuple(directories),
            tuple(created_directories),
            parts[-1],
            relative,
        )
    finally:
        for directory in reversed(directories):
            os.close(directory.descriptor)


def _fsync_file(descriptor: int, relative: str) -> None:
    os.fsync(descriptor)
    _run_hook(_TEST_DURABILITY_HOOK, "file", relative)


def _fsync_directory(directory: _Directory) -> None:
    os.fsync(directory.descriptor)
    _run_hook(_TEST_DURABILITY_HOOK, "directory", directory.relative)


def _fsync_publication_directories(
    target: _PublicationTarget,
    *,
    complete_ancestry: bool,
) -> None:
    """Persist changed entries bottom-up, including every created directory's parent."""

    if complete_ancestry:
        required = set(range(len(target.directories)))
    else:
        required = {len(target.directories) - 1}
        index_by_descriptor = {
            directory.descriptor: index
            for index, directory in enumerate(target.directories)
        }
        for directory in target.created_directories:
            required.add(index_by_descriptor[directory.descriptor])
            required.add(index_by_descriptor[directory.parent_descriptor])
    for index in sorted(required, reverse=True):
        _fsync_directory(target.directories[index])


def _read_open_file(descriptor: int) -> bytes:
    os.lseek(descriptor, 0, os.SEEK_SET)
    chunks: list[bytes] = []
    while True:
        chunk = os.read(descriptor, 1024 * 1024)
        if not chunk:
            return b"".join(chunks)
        chunks.append(chunk)


def _same_filesystem(left_descriptor: int, right_descriptor: int) -> bool:
    return os.fstat(left_descriptor).st_dev == os.fstat(right_descriptor).st_dev


def _verify_existing_target(
    target: _PublicationTarget,
    expected: bytes,
    *,
    collision_message: str,
) -> None:
    descriptor = os.open(
        target.name,
        os.O_RDONLY | _NOFOLLOW | _CLOEXEC,
        dir_fd=target.parent.descriptor,
    )
    try:
        if not stat.S_ISREG(os.fstat(descriptor).st_mode):
            raise ValueError(f"P3 publication target is not a regular file: {target.relative}")
        if _read_open_file(descriptor) != expected:
            raise FileExistsError(collision_message)
        _fsync_file(descriptor, target.relative)
    finally:
        os.close(descriptor)


def _durability_barrier(
    project_root: str | Path,
    relative_path: str,
    expected: bytes,
    *,
    collision_message: str,
) -> None:
    """Re-verify exact bytes and conservatively persist the full path ancestry."""

    with _publication_target(project_root, relative_path, create=False) as target:
        _verify_existing_target(target, expected, collision_message=collision_message)
        _fsync_publication_directories(target, complete_ancestry=True)


def _cleanup_staging(staging_target: _PublicationTarget) -> None:
    os.unlink(staging_target.name, dir_fd=staging_target.parent.descriptor)
    _fsync_directory(staging_target.parent)


def _publish_staged(
    project_root: str | Path,
    relative_path: str,
    data: bytes,
    *,
    staging_root: str,
    hook: Callable[[str, str], None] | None,
    complete_ancestry: bool,
    collision_message: str,
    allow_empty: bool,
) -> None:
    if not data and not allow_empty:
        raise ValueError("P3 publication bytes cannot be empty")
    digest = hashlib.sha256(data).hexdigest()
    staging_relative = f"{staging_root}/{digest}.{secrets.token_hex(16)}.staging"

    _run_hook(hook, "before_staging_create", relative_path)
    with _publication_target(project_root, staging_relative, create=True) as staging_target:
        abandoned_same_digest = any(
            name.startswith(f"{digest}.") and name.endswith(".staging")
            for name in os.listdir(staging_target.parent.descriptor)
        )
        descriptor = os.open(
            staging_target.name,
            os.O_RDWR | os.O_CREAT | os.O_EXCL | _NOFOLLOW | _CLOEXEC,
            0o644,
            dir_fd=staging_target.parent.descriptor,
        )
        staging_exists = True
        cleanup_staging_on_error = True
        try:
            _run_hook(hook, "after_staging_create_before_write", relative_path)
            split = max(1, len(data) // 2)
            _write_all(descriptor, data[:split])
            _run_hook(hook, "during_staging_write", relative_path)
            _write_all(descriptor, data[split:])
            _run_hook(hook, "after_staging_write_before_file_fsync", relative_path)
            _fsync_file(descriptor, staging_relative)
            _run_hook(hook, "after_staging_fsync_before_publish", relative_path)

            with _publication_target(project_root, relative_path, create=True) as target:
                if target.created_directories:
                    try:
                        _fsync_publication_directories(
                            target,
                            complete_ancestry=False,
                        )
                    except OSError:
                        cleanup_staging_on_error = False
                        raise
                if not _same_filesystem(descriptor, target.parent.descriptor):
                    raise OSError("P3 staging and destination are not on the same filesystem")
                try:
                    os.link(
                        staging_target.name,
                        target.name,
                        src_dir_fd=staging_target.parent.descriptor,
                        dst_dir_fd=target.parent.descriptor,
                        follow_symlinks=False,
                    )
                except FileExistsError:
                    _cleanup_staging(staging_target)
                    staging_exists = False
                    _verify_existing_target(
                        target,
                        data,
                        collision_message=collision_message,
                    )
                    _fsync_publication_directories(target, complete_ancestry=True)
                    return
                _run_hook(hook, "after_atomic_publish_before_directory_fsync", relative_path)
                _fsync_file(descriptor, relative_path)
                _fsync_publication_directories(
                    target,
                    complete_ancestry=complete_ancestry or abandoned_same_digest,
                )
                _run_hook(hook, "after_canonical_directory_fsync", relative_path)
                _run_hook(hook, "before_staging_cleanup", relative_path)
            os.unlink(staging_target.name, dir_fd=staging_target.parent.descriptor)
            staging_exists = False
            _run_hook(hook, "after_staging_cleanup", relative_path)
            _fsync_directory(staging_target.parent)
        except Exception:
            if staging_exists and cleanup_staging_on_error:
                try:
                    _cleanup_staging(staging_target)
                except OSError:
                    pass
            raise
        finally:
            os.close(descriptor)


def publish_canonical_record(
    project_root: str | Path,
    relative_path: str,
    data: bytes,
) -> None:
    """Stage and fsync complete bytes, then atomically publish a new P3 record."""

    relative = _canonical_relative(relative_path)
    _publish_staged(
        project_root,
        relative,
        data,
        staging_root=LITERATURE_CANONICAL_STAGING_RELATIVE,
        hook=_TEST_PUBLICATION_HOOK,
        # Existing directories may come from an interrupted mkdir/open attempt.
        # Every successful canonical publication must anchor the entire chain.
        complete_ancestry=True,
        collision_message="P3 canonical record already exists with different bytes",
        allow_empty=False,
    )


def recover_canonical_record(
    project_root: str | Path,
    relative_path: str,
    expected: bytes,
) -> None:
    """Finish the conservative durability barrier for an exact existing record."""

    relative = _canonical_relative(relative_path)
    _durability_barrier(
        project_root,
        relative,
        expected,
        collision_message="P3 canonical record already exists with different bytes",
    )


def publish_runtime_artifact(
    project_root: str | Path,
    relative_path: str,
    data: bytes,
) -> None:
    """Publish one complete content-addressed P3 runtime artifact."""

    relative = _artifact_relative(relative_path)
    expected_digest = PurePosixPath(relative).name
    if hashlib.sha256(data).hexdigest() != expected_digest:
        raise ValueError("P3 runtime artifact bytes do not match the destination digest")
    _publish_staged(
        project_root,
        relative,
        data,
        staging_root=LITERATURE_ARTIFACT_STAGING_RELATIVE,
        hook=_TEST_ARTIFACT_PUBLICATION_HOOK,
        complete_ancestry=True,
        collision_message="P3 runtime artifact path already exists with different bytes",
        allow_empty=True,
    )


def recover_runtime_artifact(
    project_root: str | Path,
    relative_path: str,
    expected: bytes,
) -> None:
    """Re-verify and durably anchor an exact existing P3 runtime artifact."""

    relative = _artifact_relative(relative_path)
    if hashlib.sha256(expected).hexdigest() != PurePosixPath(relative).name:
        raise ValueError("P3 runtime artifact bytes do not match the destination digest")
    _durability_barrier(
        project_root,
        relative,
        expected,
        collision_message="P3 runtime artifact path already exists with different bytes",
    )


def quarantine_runtime_artifact(
    project_root: str | Path,
    relative_path: str,
    poisoned: bytes,
) -> str:
    """Move an unreferenced wrong-byte artifact aside without overwriting evidence."""

    relative = _artifact_relative(relative_path)
    parts = PurePosixPath(relative).parts
    kind = parts[len(PurePosixPath(LITERATURE_RUNTIME_RELATIVE).parts)]
    expected_digest = parts[-1]
    actual_digest = hashlib.sha256(poisoned).hexdigest()
    quarantine_relative = (
        f"{LITERATURE_ARTIFACT_QUARANTINE_RELATIVE}/{kind}/"
        f"{expected_digest}.{actual_digest}.{secrets.token_hex(12)}.poisoned"
    )
    with _publication_target(project_root, relative, create=False) as source:
        descriptor = os.open(
            source.name,
            os.O_RDONLY | _NOFOLLOW | _CLOEXEC,
            dir_fd=source.parent.descriptor,
        )
        try:
            if not stat.S_ISREG(os.fstat(descriptor).st_mode):
                raise ValueError(f"P3 runtime artifact is not a regular file: {relative}")
            if _read_open_file(descriptor) != poisoned:
                raise FileExistsError("P3 runtime artifact changed during quarantine")
            _fsync_file(descriptor, relative)
        finally:
            os.close(descriptor)
        with _publication_target(project_root, quarantine_relative, create=True) as quarantine:
            if not _same_filesystem(
                source.parent.descriptor,
                quarantine.parent.descriptor,
            ):
                raise OSError("P3 artifact and quarantine are not on the same filesystem")
            os.link(
                source.name,
                quarantine.name,
                src_dir_fd=source.parent.descriptor,
                dst_dir_fd=quarantine.parent.descriptor,
                follow_symlinks=False,
            )
            _fsync_publication_directories(quarantine, complete_ancestry=True)
            os.unlink(source.name, dir_fd=source.parent.descriptor)
            _fsync_directory(source.parent)
    return quarantine_relative


__all__ = [
    "LITERATURE_ARTIFACT_KINDS",
    "publish_canonical_record",
    "publish_runtime_artifact",
    "quarantine_runtime_artifact",
    "recover_canonical_record",
    "recover_runtime_artifact",
]
