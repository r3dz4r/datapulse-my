from __future__ import annotations

import io
import json
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import parse_qs, urlparse
from urllib.request import Request

import pytest

from scripts import verify_registry_distribution as verifier


VERSION = "3.55.21"
TITLE = "DataPulse"
DESCRIPTION = "Read-only discovery for 440 Malaysian public datasets."


def _server(version: str, *, title: str = TITLE) -> dict[str, str]:
    return {"version": version, "title": title, "description": DESCRIPTION}


def _page(server: dict[str, str], next_cursor: str | None = None) -> dict[str, object]:
    return {
        "servers": [{"server": server}],
        "metadata": {"nextCursor": next_cursor},
    }


def _root(tmp_path: Path) -> Path:
    (tmp_path / "server.json").write_text(
        json.dumps(_server(VERSION)), encoding="utf-8"
    )
    return tmp_path


def _serve_pages(monkeypatch: pytest.MonkeyPatch, pages: dict[str | None, object]) -> list[str | None]:
    requested: list[str | None] = []

    def fake_urlopen(request: Request, timeout: int) -> io.BytesIO:
        assert timeout == 30
        cursor = parse_qs(urlparse(request.full_url).query).get("cursor", [None])[0]
        requested.append(cursor)
        payload = pages[cursor]
        if isinstance(payload, Exception):
            raise payload
        if isinstance(payload, bytes):
            return io.BytesIO(payload)
        return io.BytesIO(json.dumps(payload).encode("utf-8"))

    monkeypatch.setattr(verifier, "urlopen", fake_urlopen)
    return requested


@pytest.mark.parametrize("last_title,expected_exit", [(TITLE, 0), ("Stale title", 1)])
def test_canonical_version_on_last_page_is_compared(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    last_title: str,
    expected_exit: int,
) -> None:
    root = _root(tmp_path)
    requested = _serve_pages(
        monkeypatch,
        {
            None: _page(_server("3.55.19", title="Older title"), "page/2"),
            "page/2": _page(_server("3.55.20", title="Older title"), "page+3"),
            "page+3": _page(_server(VERSION, title=last_title)),
        },
    )

    assert verifier.main(["--root", str(root)]) == expected_exit
    output = capsys.readouterr()
    assert requested == [None, "page/2", "page+3"]
    if expected_exit == 0:
        assert f"registry entry {VERSION} matches canonical surfaces" in output.out
    else:
        assert "title: published='Stale title' canonical='DataPulse'" in output.err


def test_absent_version_after_all_pages_is_drift(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    root = _root(tmp_path)
    requested = _serve_pages(
        monkeypatch,
        {None: _page(_server("3.55.19"), "next"), "next": _page(_server("3.55.20"))},
    )

    assert verifier.main(["--root", str(root)]) == 1
    output = capsys.readouterr()
    assert requested == [None, "next"]
    assert VERSION in output.err
    assert "fully-read" in output.err
    assert "cannot determine" not in output.err
    requested.clear()
    assert verifier.main(["--root", str(root)]) == 1
    assert capsys.readouterr() == output
    assert requested == [None, "next"]


def test_unreadable_later_page_cannot_determine(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    root = _root(tmp_path)
    requested = _serve_pages(
        monkeypatch,
        {None: _page(_server("3.55.19"), "next"), "next": b"{broken-json"},
    )

    assert verifier.main(["--root", str(root)]) == 2
    output = capsys.readouterr()
    assert requested == [None, "next"]
    assert "cannot determine" in output.err
    assert "unparseable JSON" in output.err
    assert "not published" not in output.err


@pytest.mark.parametrize(
    "failure",
    [URLError("temporary timeout"), HTTPError("https://registry.example", 503, "busy", {}, None)],
)
def test_transport_or_http_failure_is_retried_once(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    failure: Exception,
) -> None:
    root = _root(tmp_path)
    calls = 0

    def flaky_urlopen(request: Request, timeout: int) -> io.BytesIO:
        nonlocal calls
        calls += 1
        if calls == 1:
            raise failure
        return io.BytesIO(json.dumps(_page(_server(VERSION))).encode("utf-8"))

    monkeypatch.setattr(verifier, "urlopen", flaky_urlopen)

    assert verifier.main(["--root", str(root)]) == 0
    assert calls == 2
    assert "matches canonical surfaces" in capsys.readouterr().out


def test_repeated_cursor_cannot_claim_full_listing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    root = _root(tmp_path)
    requested = _serve_pages(
        monkeypatch,
        {None: _page(_server("3.55.19"), "next"), "next": _page(_server("3.55.20"), "next")},
    )

    assert verifier.main(["--root", str(root)]) == 2
    assert requested == [None, "next"]
    assert "cannot determine: registry pagination repeats a cursor" in capsys.readouterr().err


def test_page_limit_cannot_claim_full_listing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    root = _root(tmp_path)
    monkeypatch.setattr(verifier, "MAX_REGISTRY_PAGES", 2)
    requested = _serve_pages(
        monkeypatch,
        {None: _page(_server("3.55.19"), "next"), "next": _page(_server("3.55.20"), "more")},
    )

    assert verifier.main(["--root", str(root)]) == 2
    assert requested == [None, "next"]
    assert "cannot determine: registry pagination exceeds 2 pages" in capsys.readouterr().err
