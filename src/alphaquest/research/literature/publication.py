"""Publish complete P3 canonical records without exposing partial final files."""

from __future__ import annotations

import hashlib
import os
from pathlib import Path, PurePosixPath
import secrets
from typing import Callable

from alphaquest.research.edge_backlog_io import repository_parent_fd


LITERATURE_CANONICAL_RELATIVE = "research/literature"
LITERATURE_STAGING_RELATIVE = "run-store/literature/canonical-staging"
_NOFOLLOW = getattr(os, "O_NOFOLLOW", 0)
_CLOEXEC = getattr(os, "O_CLOEXEC", 0)
_TEST_PUBLICATION_HOOK: Callable[[str, str], None] | None = None


def _canonical_relative(relative_path: str) -> str:
    path = PurePosixPath(relative_path)
    if path.is_absolute() or ".." in path.parts or path.as_posix() != relative_path:
        raise ValueError("P3 canonical record path must be normalized and repository-relative")
    if len(path.parts) < 3 or path.parts[:2] != tuple(PurePosixPath(LITERATURE_CANONICAL_RELATIVE).parts):
        raise ValueError("P3 canonical records must be beneath research/literature")
    return path.as_posix()


def _run_hook(phase: str, relative_path: str) -> None:
    hook = _TEST_PUBLICATION_HOOK
    if hook is not None:
        hook(phase, relative_path)


def _write_all(descriptor: int, data: bytes) -> None:
    offset = 0
    while offset < len(data):
        written = os.write(descriptor, data[offset:])
        if written <= 0:  # pragma: no cover - defensive platform failure
            raise OSError("P3 staging write made no forward progress")
        offset += written


def publish_canonical_record(
    project_root: str | Path,
    relative_path: str,
    data: bytes,
) -> None:
    """Durably stage bytes, then atomically link them at a new canonical name.

    The hard-link publication step is atomic and no-replace.  The staging file
    and canonical parent are explicitly required to be on the same filesystem.
    A process death can therefore leave an ignored staging residue, but it
    cannot expose an empty or partially written final canonical file.
    """

    root = Path(project_root).resolve()
    relative = _canonical_relative(relative_path)
    if not data:
        raise ValueError("P3 canonical record bytes cannot be empty")
    digest = hashlib.sha256(data).hexdigest()
    staging_relative = f"{LITERATURE_STAGING_RELATIVE}/{digest}.{secrets.token_hex(16)}.staging"

    _run_hook("before_staging_create", relative)
    with repository_parent_fd(root, relative, create=True) as (canonical_parent_fd, name):
        with repository_parent_fd(root, staging_relative, create=True) as (
            staging_parent_fd,
            staging_name,
        ):
            descriptor = os.open(
                staging_name,
                os.O_WRONLY | os.O_CREAT | os.O_EXCL | _NOFOLLOW | _CLOEXEC,
                0o644,
                dir_fd=staging_parent_fd,
            )
            staging_exists = True
            try:
                _run_hook("after_staging_create_before_write", relative)
                split = max(1, len(data) // 2)
                _write_all(descriptor, data[:split])
                _run_hook("during_staging_write", relative)
                _write_all(descriptor, data[split:])
                _run_hook("after_staging_write_before_file_fsync", relative)
                os.fsync(descriptor)
                _run_hook("after_staging_fsync_before_publish", relative)

                if os.fstat(descriptor).st_dev != os.fstat(canonical_parent_fd).st_dev:
                    raise OSError("P3 canonical staging and destination are not on the same filesystem")
                os.link(
                    staging_name,
                    name,
                    src_dir_fd=staging_parent_fd,
                    dst_dir_fd=canonical_parent_fd,
                    follow_symlinks=False,
                )
                _run_hook("after_atomic_publish_before_directory_fsync", relative)
                os.fsync(canonical_parent_fd)
                _run_hook("after_canonical_directory_fsync", relative)
                _run_hook("before_staging_cleanup", relative)
                os.unlink(staging_name, dir_fd=staging_parent_fd)
                staging_exists = False
                os.fsync(staging_parent_fd)
            except Exception:
                if staging_exists:
                    try:
                        os.unlink(staging_name, dir_fd=staging_parent_fd)
                        os.fsync(staging_parent_fd)
                    except OSError:
                        pass
                raise
            finally:
                os.close(descriptor)


__all__ = ["publish_canonical_record"]
