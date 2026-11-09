"""The stage journal is append-shaped data and must be written by appending.

2026-11-09: the observer journal held a record torn mid-JSON because
append_event rewrote the whole file with write_text, so a killed cycle could
leave the live journal truncated or half-written. These tests pin the write
path: no truncating open of the journal, one append per record, rotation by
atomic replace, a stated record-size bound, and serialised writers.
"""

from __future__ import annotations

import builtins
import io
import json
import os
import signal
import subprocess
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import pytest

from scripts import check_heartbeat

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts/check_heartbeat.py"
MAX_RECORD_BYTES = 4096


def _ts(moment: datetime) -> str:
    return moment.isoformat(timespec="seconds").replace("+00:00", "Z")


def _event(moment: datetime, stage: str = "probe", **extra: Any) -> dict[str, Any]:
    return {
        "ts": _ts(moment),
        "stage": stage,
        "duration_ms": 1,
        "status": "success",
        "cycle": "cycle-a",
        "extra": extra,
    }


def _line(event: dict[str, Any]) -> str:
    return json.dumps(event, separators=(",", ":"), sort_keys=True)


class _Recorder:
    """Record every open/truncate/write that reaches the journal."""

    def __init__(self, journal: Path) -> None:
        self.journal = journal.resolve()
        self.opens: list[tuple[str, Any]] = []
        self.truncations: list[str] = []
        self.writes: list[bytes] = []
        self._fds: dict[int, Path] = {}

    def _is_journal(self, target: Any) -> bool:
        try:
            return Path(os.fsdecode(target)).resolve() == self.journal
        except TypeError:
            return False

    def install(self, monkeypatch: pytest.MonkeyPatch) -> None:
        real_io_open = io.open
        real_os_open = os.open
        real_os_write = os.write
        real_truncate = os.truncate
        real_ftruncate = os.ftruncate

        def recording_open(file: Any, mode: str = "r", *args: Any, **kwargs: Any) -> Any:
            if not isinstance(file, int) and self._is_journal(file):
                self.opens.append(("io", mode))
                if "w" in mode:
                    self.truncations.append(f"io.open mode {mode!r}")
            return real_io_open(file, mode, *args, **kwargs)

        def recording_os_open(path: Any, flags: int, *args: Any, **kwargs: Any) -> int:
            fd = real_os_open(path, flags, *args, **kwargs)
            if self._is_journal(path):
                self.opens.append(("os", flags))
                self._fds[fd] = self.journal
                if flags & os.O_TRUNC:
                    self.truncations.append("os.open O_TRUNC")
            return fd

        def recording_write(fd: int, data: bytes) -> int:
            if fd in self._fds:
                self.writes.append(bytes(data))
            return real_os_write(fd, data)

        def recording_truncate(path: Any, length: int) -> None:
            if self._is_journal(path):
                self.truncations.append("os.truncate")
            real_truncate(path, length)

        def recording_ftruncate(fd: int, length: int) -> None:
            if fd in self._fds:
                self.truncations.append("os.ftruncate")
            real_ftruncate(fd, length)

        monkeypatch.setattr(io, "open", recording_open)
        monkeypatch.setattr(builtins, "open", recording_open)
        monkeypatch.setattr(os, "open", recording_os_open)
        monkeypatch.setattr(os, "write", recording_write)
        monkeypatch.setattr(os, "truncate", recording_truncate)
        monkeypatch.setattr(os, "ftruncate", recording_ftruncate)


def test_common_case_is_one_append_without_truncation(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    journal = tmp_path / "stages.jsonl"
    now = datetime.now(UTC)
    existing = "".join(_line(_event(now - timedelta(minutes=m))) + "\n" for m in (30, 20, 10))
    existing += "not json\n"
    journal.write_text(existing, encoding="utf-8")
    inode = journal.stat().st_ino
    event = _event(now, "publish.gate", reason="ok")

    recorder = _Recorder(journal)
    recorder.install(monkeypatch)
    check_heartbeat.append_event(event, journal)
    monkeypatch.undo()

    assert recorder.truncations == [], recorder.truncations
    journal_opens = [flags for kind, flags in recorder.opens if kind == "os"]
    write_opens = [flags for flags in journal_opens if flags & (os.O_WRONLY | os.O_RDWR)]
    assert write_opens and all(flags & os.O_APPEND for flags in write_opens)
    record = (_line(event) + "\n").encode()
    assert recorder.writes == [record]
    assert journal.stat().st_ino == inode
    assert journal.read_bytes() == existing.encode() + record


def test_torn_tail_is_isolated_so_the_new_record_stays_whole(tmp_path: Path) -> None:
    journal = tmp_path / "stages.jsonl"
    now = datetime.now(UTC)
    whole = _line(_event(now - timedelta(minutes=5)))
    journal.write_text(whole + '\n{"ts":"x","stage":"publish.gat', encoding="utf-8")
    event = _event(now)

    check_heartbeat.append_event(event, journal)

    lines = journal.read_text(encoding="utf-8").split("\n")
    assert lines == [whole, '{"ts":"x","stage":"publish.gat', _line(event), ""]


def test_termination_signals_are_blocked_during_the_journal_write(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    journal = tmp_path / "stages.jsonl"
    seen: list[set[signal.Signals]] = []
    real_write = os.write

    def checking_write(fd: int, data: bytes) -> int:
        seen.append(set(signal.pthread_sigmask(signal.SIG_BLOCK, [])))
        return real_write(fd, data)

    monkeypatch.setattr(os, "write", checking_write)
    check_heartbeat.append_event(_event(datetime.now(UTC)), journal)
    monkeypatch.undo()

    assert seen, "the record was not written with os.write"
    for mask in seen:
        assert {signal.SIGTERM, signal.SIGINT, signal.SIGHUP} <= mask
    assert signal.SIGTERM not in signal.pthread_sigmask(signal.SIG_BLOCK, [])


def test_rotation_replaces_atomically_and_preserves_every_line(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    journal = tmp_path / "stages.jsonl"
    now = datetime.now(UTC)
    two_days = now - timedelta(days=2)
    three_days = now - timedelta(days=3)
    aged_a = _line(_event(three_days, "history"))
    aged_b = _line(_event(two_days, "deltas"))
    fresh = _line(_event(now - timedelta(hours=1), "validate"))
    lines = [aged_a, "garbage line", aged_b, fresh, '{"no_ts":true}']
    journal.write_text("\n".join(lines) + "\n", encoding="utf-8")
    rotated_b = tmp_path / f"stages.{two_days.date().isoformat()}.jsonl"
    rotated_b.write_text("prior rotated line\n", encoding="utf-8")
    event = _event(now, "publish")
    journal_before = journal.read_bytes()

    replaced: list[tuple[str, bytes]] = []
    real_replace = os.replace

    def checking_replace(src: Any, dst: Any) -> None:
        if Path(dst).resolve() == journal.resolve():
            # The live journal is untouched up to the instant of the swap.
            assert journal.read_bytes() == journal_before
            replaced.append((os.fsdecode(src), Path(src).read_bytes()))
        real_replace(src, dst)

    recorder = _Recorder(journal)
    recorder.install(monkeypatch)
    monkeypatch.setattr(os, "replace", checking_replace)
    check_heartbeat.append_event(event, journal)
    monkeypatch.undo()

    assert recorder.truncations == [], recorder.truncations
    expected_live = "\n".join(["garbage line", fresh, '{"no_ts":true}', _line(event)]) + "\n"
    assert replaced and replaced[0][1] == expected_live.encode()
    assert journal.read_text(encoding="utf-8") == expected_live
    rotated_a = tmp_path / f"stages.{three_days.date().isoformat()}.jsonl"
    assert rotated_a.read_text(encoding="utf-8") == aged_a + "\n"
    assert rotated_b.read_text(encoding="utf-8") == "prior rotated line\n" + aged_b + "\n"
    leftovers = sorted(p.name for p in tmp_path.iterdir())
    assert leftovers == sorted(["stages.jsonl", rotated_a.name, rotated_b.name])


def test_failed_rotation_leaves_the_live_journal_intact(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    journal = tmp_path / "stages.jsonl"
    now = datetime.now(UTC)
    content = _line(_event(now - timedelta(days=2))) + "\n" + _line(_event(now)) + "\n"
    journal.write_text(content, encoding="utf-8")

    def crashing_replace(src: Any, dst: Any) -> None:
        raise OSError("simulated crash before the swap")

    monkeypatch.setattr(os, "replace", crashing_replace)
    with pytest.raises(OSError, match="simulated crash"):
        check_heartbeat.append_event(_event(now, "publish"), journal)
    monkeypatch.undo()

    assert journal.read_text(encoding="utf-8") == content
    assert not [p for p in tmp_path.iterdir() if p.name.startswith(".stages.jsonl.")]


def test_record_over_the_atomic_bound_is_rejected(tmp_path: Path) -> None:
    journal = tmp_path / "stages.jsonl"
    now = datetime.now(UTC)
    journal.write_text(_line(_event(now)) + "\n", encoding="utf-8")
    before = journal.read_bytes()
    assert check_heartbeat.MAX_RECORD_BYTES == MAX_RECORD_BYTES

    with pytest.raises(ValueError, match="4096"):
        check_heartbeat.append_event(_event(now, blob="x" * MAX_RECORD_BYTES), journal)
    assert journal.read_bytes() == before

    result = subprocess.run(
        [sys.executable, str(SCRIPT), "append", "--stage", "probe", "--duration", "1",
         "--status", "success", "--extra-json", json.dumps({"blob": "x" * MAX_RECORD_BYTES})],
        env={"DATAPULSE_TELEMETRY_FILE": str(journal)},
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode != 0
    assert "4096" in result.stderr
    assert journal.read_bytes() == before


def test_record_at_the_atomic_bound_is_written(tmp_path: Path) -> None:
    journal = tmp_path / "stages.jsonl"
    event = _event(datetime.now(UTC), blob="")
    padding = MAX_RECORD_BYTES - len(_line(event).encode()) - 1
    event["extra"]["blob"] = "x" * padding
    assert len((_line(event) + "\n").encode()) == MAX_RECORD_BYTES

    check_heartbeat.append_event(event, journal)

    assert journal.read_text(encoding="utf-8") == _line(event) + "\n"


def test_concurrent_appends_never_interleave_or_lose_lines(tmp_path: Path) -> None:
    journal = tmp_path / "stages.jsonl"
    aged_moment = datetime.now(UTC) - timedelta(days=2)
    aged = [_line(_event(aged_moment, "history", n=n)) for n in range(50)]
    journal.write_text("\n".join(aged) + "\n", encoding="utf-8")
    writers = 24
    procs = [
        subprocess.Popen(
            [sys.executable, str(SCRIPT), "append", "--stage", "probe", "--duration", str(n),
             "--status", "success", "--extra-json", json.dumps({"writer": n, "pad": "y" * 3000})],
            env={"DATAPULSE_TELEMETRY_FILE": str(journal)},
            stderr=subprocess.PIPE,
            text=True,
        )
        for n in range(writers)
    ]
    for proc in procs:
        _, stderr = proc.communicate(timeout=60)
        assert proc.returncode == 0, stderr

    rows = [json.loads(line) for line in journal.read_text(encoding="utf-8").splitlines()]
    assert sorted(row["extra"]["writer"] for row in rows) == list(range(writers))
    rotated = tmp_path / f"stages.{aged_moment.date().isoformat()}.jsonl"
    assert rotated.read_text(encoding="utf-8").splitlines() == aged
