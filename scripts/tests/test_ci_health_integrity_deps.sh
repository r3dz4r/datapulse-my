#!/usr/bin/env bash
set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
CI_WORKFLOW="${CI_WORKFLOW_PATH:-$repo_root/.github/workflows/ci.yml}" \
  python3 - "$repo_root" <<'PY'
import ast
import re
import shlex
import sys
from pathlib import Path

root = Path(sys.argv[1])
workflow_path = Path(__import__("os").environ["CI_WORKFLOW"])
lines = workflow_path.read_text(encoding="utf-8").splitlines()
try:
    job_start = next(i for i, line in enumerate(lines) if line == "  health-integrity:")
except StopIteration:
    raise SystemExit("health-integrity dependency check: job not found")
job_end = next(
    (i for i in range(job_start + 1, len(lines)) if re.match(r"^  [A-Za-z0-9_-]+:$", lines[i])),
    len(lines),
)
job = lines[job_start:job_end]


def step_run(step_name):
    marker = f"      - name: {step_name}"
    try:
        start = next(i for i, line in enumerate(job) if line == marker)
    except StopIteration:
        raise SystemExit(f"health-integrity dependency check: step not found: {step_name}")
    for index in range(start + 1, len(job)):
        if job[index].startswith("      - "):
            break
        match = re.match(r"^        run: (.*)$", job[index])
        if match:
            value = match.group(1)
            if value == "|":
                block = []
                for line in job[index + 1 :]:
                    if line.startswith("          "):
                        block.append(line[10:])
                    elif not line.strip():
                        block.append("")
                    else:
                        break
                return "\n".join(block)
            return value
    raise SystemExit(f"health-integrity dependency check: run command not found: {step_name}")


install = step_run("Install health integrity dependencies")
install_tokens = shlex.split(install)
try:
    pip_index = install_tokens.index("pip")
    install_index = install_tokens.index("install", pip_index + 1)
except ValueError:
    raise SystemExit("health-integrity dependency check: install step must run pip install")
installed = {
    token.split("[", 1)[0].split("=", 1)[0].split(">", 1)[0].split("<", 1)[0]
    for token in install_tokens[install_index + 1 :]
    if not token.startswith("-")
}

validation = step_run("Validate health snapshot and attestation lineage")
commands = [shlex.split(line) for line in validation.splitlines() if line.strip()]
queue = []
required = set()
for command in commands:
    if "-m" in command:
        module_index = command.index("-m") + 1
        if module_index < len(command):
            module = command[module_index]
            top = module.split(".", 1)[0]
            if top not in sys.stdlib_module_names:
                required.add(top)
    for index, token in enumerate(command[:-1]):
        if token in {"python3", "python"} and command[index + 1].endswith(".py"):
            script = root / command[index + 1]
            if script.is_file():
                queue.append(script)

seen = set()
while queue:
    path = queue.pop()
    if path in seen:
        continue
    seen.add(path)
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            modules = [alias.name for alias in node.names]
        elif isinstance(node, ast.ImportFrom) and node.module:
            modules = [node.module]
        else:
            continue
        for module in modules:
            top = module.split(".", 1)[0]
            relative = module.split(".")
            candidates = [root.joinpath(*relative), root.joinpath("scripts", *relative)]
            local_file = next((candidate.with_suffix(".py") for candidate in candidates
                               if candidate.with_suffix(".py").is_file()), None)
            local_package = next((candidate / "__init__.py" for candidate in candidates
                                  if (candidate / "__init__.py").is_file()), None)
            if local_file:
                queue.append(local_file)
            elif local_package:
                queue.append(local_package)
            elif top not in sys.stdlib_module_names and top != "scripts":
                required.add(top)

missing = sorted(required - installed)
if missing:
    for module in missing:
        print(f"health-integrity dependency check: missing installed module: {module}", file=sys.stderr)
    raise SystemExit(1)
for module in sorted(required):
    print(f"health-integrity dependency check: {module} is installed")
PY
