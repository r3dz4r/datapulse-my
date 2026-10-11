"""Check and, when needed, refresh the OpenWiki ChatGPT OAuth credential."""

from __future__ import annotations

import argparse
import base64
from dataclasses import dataclass, field
from datetime import datetime, timezone
import json
import math
import os
from pathlib import Path
import tempfile
import time
from typing import Callable, Mapping
from urllib import error, parse, request


ACCESS = "OPENAI_CHATGPT_ACCESS_TOKEN"
REFRESH = "OPENAI_CHATGPT_REFRESH_TOKEN"
EXPIRES = "OPENAI_CHATGPT_EXPIRES_AT"
ACCOUNT = "OPENAI_CHATGPT_ACCOUNT_ID"
REQUIRED = (ACCESS, REFRESH, EXPIRES, ACCOUNT)
DEFAULT_ENDPOINT = "https://auth.openai.com/oauth/token"
CLIENT_ID = "app_EMoamEEZ73f0CkXaXp7hrann"


@dataclass(frozen=True)
class Decision:
    code: int
    message: str
    updates: Mapping[str, str] = field(default_factory=dict)


Exchange = Callable[[str], tuple[int, Mapping[str, object]]]


def _assignment(line: str) -> tuple[str, str] | None:
    stripped = line.strip()
    if stripped.startswith("export "):
        stripped = stripped[len("export ") :].strip()
    if "=" not in stripped:
        return None
    key, value = stripped.split("=", 1)
    value = value.strip()
    if len(value) >= 2 and value.startswith('"') and value.endswith('"'):
        value = value[1:-1]
    return key.strip(), value


def parse_env(content: bytes) -> dict[str, str]:
    values: dict[str, str] = {}
    for line in content.decode("utf-8").splitlines():
        assignment = _assignment(line)
        if assignment is not None:
            values[assignment[0]] = assignment[1]
    return values


def _jwt_exp(token: str) -> float | None:
    parts = token.split(".")
    if len(parts) != 3:
        return None
    try:
        payload = base64.urlsafe_b64decode(parts[1] + "=" * (-len(parts[1]) % 4))
        exp = json.loads(payload)["exp"]
    except (ValueError, KeyError, TypeError):
        return None
    if isinstance(exp, bool) or not isinstance(exp, (int, float)):
        return None
    try:
        seconds = float(exp)
    except OverflowError:
        return None
    return seconds if math.isfinite(seconds) else None


def _utc(seconds: float) -> str:
    return datetime.fromtimestamp(seconds, tz=timezone.utc).isoformat().replace("+00:00", "Z")


def decide(
    env: Mapping[str, str], now: float, skew_seconds: float, exchange: Exchange,
    check_only: bool = False,
) -> Decision:
    """Return a decision without touching the file; only exchange may do I/O."""
    for key in REQUIRED:
        if not env.get(key):
            return Decision(2, f"{key} is absent or empty")

    exp = _jwt_exp(env[ACCESS])
    if exp is None:
        return Decision(2, f"{ACCESS} is not a JWT with a numeric exp")
    try:
        expiry = _utc(exp)
    except (OverflowError, OSError, ValueError):
        return Decision(2, f"{ACCESS} has an invalid exp")
    if exp > now + skew_seconds:
        return Decision(0, f"access token valid until {expiry}")
    if check_only:
        return Decision(2, f"{ACCESS} expires within the skew; refresh required (--check-only)")

    try:
        status, payload = exchange(env[REFRESH])
    except (OSError, TimeoutError, error.URLError):
        return Decision(4, "OAuth refresh transport failure (network or timeout)")
    if 400 <= status < 500:
        return Decision(
            3,
            f"HTTP {status}: {REFRESH} was rejected; reprovision the six "
            "OPENAI_CHATGPT_* repository secrets in this repository from the "
            "operator's credential file",
        )
    if status != 200:
        return Decision(4, f"OAuth refresh transport returned HTTP {status}")

    needed = ("access_token", "refresh_token", "expires_in")
    missing = [key for key in needed if not payload.get(key)]
    if missing:
        return Decision(5, "OAuth refresh response missing " + ", ".join(missing))
    expires_in = payload["expires_in"]
    if (
        isinstance(expires_in, bool)
        or not isinstance(expires_in, (int, float))
        or not math.isfinite(expires_in)
        or expires_in <= 0
        or not isinstance(payload["access_token"], str)
        or not isinstance(payload["refresh_token"], str)
    ):
        return Decision(5, "OAuth refresh response has invalid access_token, refresh_token or expires_in")
    try:
        refreshed_exp_ms = int(now * 1000 + expires_in * 1000)
        refreshed_expiry = _utc(refreshed_exp_ms / 1000)
    except (OverflowError, OSError, ValueError):
        return Decision(5, "OAuth refresh response has invalid expires_in")
    return Decision(
        0,
        f"access token refreshed until {refreshed_expiry}",
        {
            ACCESS: payload["access_token"],
            REFRESH: payload["refresh_token"],
            EXPIRES: str(refreshed_exp_ms),
        },
    )


def rewrite_env(path: Path, original: bytes, updates: Mapping[str, str]) -> None:
    """Replace only token values, preserving unrelated bytes and existing quote style."""
    lines = original.splitlines(keepends=True)
    rewritten: list[bytes] = []
    for line in lines:
        body = line.rstrip(b"\r\n")
        newline = line[len(body) :]
        assignment = _assignment(body.decode("utf-8"))
        if assignment is None or assignment[0] not in updates:
            rewritten.append(line)
            continue
        value = updates[assignment[0]]
        if "\n" in value or "\r" in value or '"' in value:
            raise ValueError("OAuth refresh response contains an unsafe token value")
        before, old_value = body.split(b"=", 1)
        leading = old_value[: len(old_value) - len(old_value.lstrip())]
        trailing = old_value[len(old_value.rstrip()) :]
        quoted = old_value.strip().startswith(b'"') and old_value.strip().endswith(b'"')
        encoded = value.encode("utf-8")
        if quoted:
            encoded = b'"' + encoded + b'"'
        rewritten.append(before + b"=" + leading + encoded + trailing + newline)

    temp_name: str | None = None
    try:
        with tempfile.NamedTemporaryFile(dir=path.parent, prefix=f".{path.name}.", delete=False) as temp:
            temp_name = temp.name
            os.fchmod(temp.fileno(), 0o600)
            temp.write(b"".join(rewritten))
            temp.flush()
            os.fsync(temp.fileno())
        os.replace(temp_name, path)
    finally:
        if temp_name is not None and os.path.exists(temp_name):
            os.unlink(temp_name)


def http_exchange(refresh_token: str, endpoint: str) -> tuple[int, Mapping[str, object]]:
    body = parse.urlencode(
        {"grant_type": "refresh_token", "refresh_token": refresh_token, "client_id": CLIENT_ID}
    ).encode("ascii")
    req = request.Request(
        endpoint, data=body, headers={"Content-Type": "application/x-www-form-urlencoded"}, method="POST"
    )
    try:
        with request.urlopen(req, timeout=10) as response:
            status = response.status
            content = response.read() if status == 200 else b""
    except error.HTTPError as exc:
        return exc.code, {}
    if status != 200:
        return status, {}
    try:
        payload = json.loads(content)
    except (ValueError, UnicodeDecodeError):
        return 200, {}
    return 200, payload if isinstance(payload, dict) else {}


def run(path: Path, now: float, skew_seconds: float, exchange: Exchange, check_only: bool = False) -> Decision:
    try:
        original = path.read_bytes()
        env = parse_env(original)
    except (OSError, UnicodeError):
        return Decision(2, f"cannot read credential env file: {path}")
    decision = decide(env, now, skew_seconds, exchange, check_only)
    if decision.updates:
        try:
            rewrite_env(path, original, decision.updates)
        except (OSError, UnicodeError, ValueError):
            return Decision(5, "could not safely write refreshed credential env file")
    return decision


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--env-file", type=Path, default=Path("~/.openwiki/.env").expanduser())
    parser.add_argument("--skew-seconds", type=float, default=300)
    parser.add_argument(
        "--refresh-endpoint", default=os.environ.get("OPENWIKI_OAUTH_TOKEN_URL", DEFAULT_ENDPOINT)
    )
    parser.add_argument("--check-only", action="store_true")
    args = parser.parse_args()
    if not math.isfinite(args.skew_seconds) or args.skew_seconds < 0:
        parser.error("--skew-seconds must be a finite non-negative number")
    result = run(
        args.env_file, time.time(), args.skew_seconds,
        lambda token: http_exchange(token, args.refresh_endpoint), args.check_only,
    )
    print(result.message)
    return result.code


if __name__ == "__main__":
    raise SystemExit(main())
