#!/usr/bin/env python3
"""Explicit POSIX modes for managed pipeline artefacts.

``tempfile.mkstemp`` always creates its file at mode 0600, and ``os.replace``
carries that mode to the final path. A managed artefact therefore landed
unreadable to any identity other than the writer -- the operator's state probe
reported dataset counts and health timestamps as unknown even though the bytes
were correct on disk.

The helpers here set the mode on every write instead of inheriting it from the
process umask, and create only the directories they own at 0755. They are the
single choke point for that policy; a writer that must keep a stricter mode
(credentials, keys, sockets, the observation store's evidence blobs) must not
use them.
"""

from __future__ import annotations

import os
import tempfile
from pathlib import Path
from typing import Final

FILE_MODE: Final[int] = 0o644
DIRECTORY_MODE: Final[int] = 0o755


def ensure_directory(directory: Path) -> None:
    """Create ``directory`` and missing parents at 0755, independent of umask.

    Existing directories are left untouched: only directories this call created
    are chmodded, so a caller can neither loosen nor tighten a pre-existing tree.
    """
    missing: list[Path] = []
    step = directory
    while not step.exists() and step != step.parent:
        missing.append(step)
        step = step.parent
    if not missing:
        return
    directory.mkdir(parents=True, exist_ok=True)
    for created in missing:
        os.chmod(created, DIRECTORY_MODE)


def replace_file(path: Path, data: bytes) -> None:
    """Atomically replace ``path`` with ``data`` at mode 0644.

    The bytes reach a sibling temporary file, are fsynced, and are renamed into
    place, so a reader never observes a partial file at the final path. The
    temporary file never survives a successful call.
    """
    ensure_directory(path.parent)
    descriptor, temporary_name = tempfile.mkstemp(
        prefix=f".{path.name}.", suffix=".tmp", dir=path.parent
    )
    try:
        os.fchmod(descriptor, FILE_MODE)
        with os.fdopen(descriptor, "wb") as temporary_file:
            temporary_file.write(data)
            temporary_file.flush()
            os.fsync(temporary_file.fileno())
        os.replace(temporary_name, path)
    except BaseException:
        try:
            os.unlink(temporary_name)
        except OSError:
            pass
        raise
