#!/usr/bin/env bash
set -euo pipefail

python3 - <<'PY'
import json
import re
import subprocess
import sys
from pathlib import Path

manifest = json.loads(Path('datapulse.json').read_text(encoding='utf-8'))
for dataset in manifest['datasets']:
    dataset_id = dataset['id']
    if not isinstance(dataset_id, str) or not re.fullmatch(r'[a-z0-9][a-z0-9_-]*', dataset_id):
        raise ValueError(f'Invalid dataset id: {dataset_id!r}')
    generator = Path('scripts') / f'gen_{dataset_id}.py'
    if generator.is_file():
        result = subprocess.run([sys.executable, str(generator)], check=False)
        if result.returncode:
            print(f'Per-dataset generator failed for {dataset_id}: {generator} (exit {result.returncode})', file=sys.stderr)
            sys.exit(1)
PY
