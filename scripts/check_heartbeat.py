#!/usr/bin/env python3
"""Append structured DataPulse cycle-stage telemetry."""

from __future__ import annotations

import argparse
import fcntl
import json
import os
import re
import signal
import stat
import sys
import tempfile
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_LOG = ROOT / "var/log/stages.jsonl"
STAGES = {
    "probe",
    "history",
    "snapshot",
    "deltas",
    "validate",
    "publish",
    "kv-index",
    "passports",
    "mcp-sync",
    "attestation-score",
    "evidence",
    "sigstore-request",
    "observation-capture",
}
STATUSES = {"success", "fail", "skipped"}
SUBSTAGE_TOKEN = re.compile(r"[a-z0-9][a-z0-9_-]*")
MAX_RECORD_BYTES = 4096
TERMINATION_SIGNALS = {signal.SIGHUP, signal.SIGINT, signal.SIGQUIT, signal.SIGTERM}


def parse_stage(value: str) -> str:
    """Validate a root stage or a closed-vocabulary sub-stage."""
    root, separator, token = value.partition(".")
    if root in STAGES and (not separator or SUBSTAGE_TOKEN.fullmatch(token)):
        return value
    roots = ", ".join(sorted(STAGES))
    raise argparse.ArgumentTypeError(
        f"must be a stage root or root.token; accepted roots: {roots}"
    )


def parse_ts(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(UTC)


def log_path() -> Path:
    return Path(os.environ.get("DATAPULSE_TELEMETRY_FILE", str(DEFAULT_LOG)))


class RecordTooLarge(ValueError):
    """A record exceeds the size the journal append is bounded to."""


def _open_locked(path: Path) -> int:
    """Open the live journal for append and hold its exclusive flock.

    Every writer serialises on this lock, so two appends cannot interleave and
    an append cannot race a rotation. Rotation swaps a new inode in under the
    lock, so a writer that waited on the old inode reopens the path instead of
    appending to a file that is no longer the journal.
    """
    while True:
        fd = os.open(path, os.O_RDWR | os.O_APPEND | os.O_CREAT | os.O_CLOEXEC, 0o666)
        try:
            fcntl.flock(fd, fcntl.LOCK_EX)
            held, current = os.fstat(fd), os.stat(path)
            if (held.st_dev, held.st_ino) == (current.st_dev, current.st_ino):
                return fd
        except FileNotFoundError:
            pass
        except BaseException:
            os.close(fd)
            raise
        os.close(fd)


def _read_all(fd: int) -> bytes:
    size = os.fstat(fd).st_size
    chunks: list[bytes] = []
    offset = 0
    while offset < size:
        chunk = os.pread(fd, size - offset, offset)
        if not chunk:
            break
        chunks.append(chunk)
        offset += len(chunk)
    return b"".join(chunks)


def _write_all(fd: int, data: bytes) -> None:
    view = memoryview(data)
    while view:
        view = view[os.write(fd, view):]


def _append(fd: int, payload: bytes) -> None:
    """Append whole lines in one write, isolating any torn tail first.

    A file that does not end in a newline holds a record torn by an earlier
    crash. Starting the write with a newline keeps that fragment on its own
    line, where it is retained as unparseable, instead of fusing it with the
    record being written now.
    """
    size = os.fstat(fd).st_size
    if size and os.pread(fd, 1, size - 1) != b"\n":
        payload = b"\n" + payload
    _write_all(fd, payload)


def _rotate(fd: int, path: Path, retained: list[str], old_events: dict[str, list[str]]) -> None:
    """Move aged lines to per-date files, then swap in the retained journal.

    The live journal is never truncated: the retained lines and the new record
    are written to a temporary file in the same directory, fsynced, and
    renamed over the journal, so it is always either the complete old file or
    the complete new one. Rotated files are appended and fsynced before the
    swap; a crash between the two can duplicate aged lines in a rotated file
    on the next rotation, but never lose them.
    """
    for date, lines in old_events.items():
        rotated = path.with_name(f"{path.stem}.{date}{path.suffix}")
        rotated_fd = os.open(rotated, os.O_RDWR | os.O_APPEND | os.O_CREAT | os.O_CLOEXEC, 0o666)
        try:
            _append(rotated_fd, ("\n".join(lines) + "\n").encode("utf-8", "surrogateescape"))
            os.fsync(rotated_fd)
        finally:
            os.close(rotated_fd)
    temp_fd, temp_name = tempfile.mkstemp(dir=path.parent, prefix=f".{path.name}.", suffix=".tmp")
    try:
        try:
            os.fchmod(temp_fd, stat.S_IMODE(os.fstat(fd).st_mode))
            _write_all(temp_fd, ("\n".join(retained) + "\n").encode("utf-8", "surrogateescape"))
            os.fsync(temp_fd)
        finally:
            os.close(temp_fd)
        os.replace(temp_name, path)
    except BaseException:
        Path(temp_name).unlink(missing_ok=True)
        raise
    dir_fd = os.open(path.parent, os.O_RDONLY | os.O_DIRECTORY | os.O_CLOEXEC)
    try:
        os.fsync(dir_fd)
    finally:
        os.close(dir_fd)


def append_event(event: dict[str, Any], path: Path) -> None:
    """Append one event to the journal, rotating lines older than one day.

    The record is bounded to MAX_RECORD_BYTES (newline included) and is
    rejected above it. 4096 bytes is PIPE_BUF, the only size POSIX makes a
    single-write atomicity promise for, and one page: Linux serialises
    O_APPEND writers on the inode, but a write can still be cut short at a
    page-cache boundary by a fatal signal, ENOSPC or RLIMIT_FSIZE. Writers here
    also hold an exclusive flock, so interleaving does not depend on the bound;
    termination signals are blocked across the locked section, so SIGTERM
    lands only after the record is whole; and a tail torn by SIGKILL or a
    crash is isolated by the next append. Live records are about 300 bytes.
    """
    record = json.dumps(event, separators=(",", ":"), sort_keys=True)
    payload = (record + "\n").encode("utf-8")
    if len(payload) > MAX_RECORD_BYTES:
        raise RecordTooLarge(
            f"record is {len(payload)} bytes; the journal append is bounded to "
            f"{MAX_RECORD_BYTES} bytes"
        )
    path.parent.mkdir(parents=True, exist_ok=True)
    now = parse_ts(event["ts"])
    cutoff = now - timedelta(days=1)
    fd = _open_locked(path)
    try:
        masked = signal.pthread_sigmask(signal.SIG_BLOCK, TERMINATION_SIGNALS)
        try:
            retained: list[str] = []
            old_events: dict[str, list[str]] = {}
            lines = _read_all(fd).decode("utf-8", "surrogateescape").split("\n")
            if lines[-1] == "":
                lines.pop()
            for line in lines:
                try:
                    previous = json.loads(line)
                    previous_ts = parse_ts(previous["ts"])
                except (json.JSONDecodeError, KeyError, TypeError, ValueError):
                    retained.append(line)
                    continue
                if previous_ts < cutoff:
                    old_events.setdefault(previous_ts.date().isoformat(), []).append(line)
                else:
                    retained.append(line)
            if old_events:
                _rotate(fd, path, retained + [record], old_events)
            else:
                _append(fd, payload)
        finally:
            signal.pthread_sigmask(signal.SIG_SETMASK, masked)
    finally:
        os.close(fd)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)
    append = subparsers.add_parser("append", help="append one stage completion event")
    append.add_argument("--stage", required=True, type=parse_stage)
    append.add_argument("--duration", required=True, type=int)
    append.add_argument("--status", required=True, choices=sorted(STATUSES))
    append.add_argument("--cycle", default=os.environ.get("DATAPULSE_CYCLE"))
    append.add_argument("--extra-json", default="{}", help="JSON object merged into extra")
    append.add_argument("--lag-ms", type=int, help="publication lag, for publish events")
    args = parser.parse_args()
    try:
        extra = json.loads(args.extra_json)
        if not isinstance(extra, dict):
            raise ValueError("--extra-json must be a JSON object")
    except (json.JSONDecodeError, ValueError) as exc:
        parser.error(str(exc))
    if args.lag_ms is not None:
        extra["lag_ms"] = args.lag_ms
        extra["publication_lag_ms"] = args.lag_ms
    now = datetime.now(UTC)
    event = {
        "ts": now.isoformat(timespec="seconds").replace("+00:00", "Z"),
        "stage": args.stage,
        "duration_ms": args.duration,
        "status": args.status,
        "cycle": args.cycle or now.strftime("%Y-%m-%dT%H:%M"),
        "extra": extra,
    }
    try:
        append_event(event, log_path())
    except RecordTooLarge as exc:
        print(f"check_heartbeat: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
