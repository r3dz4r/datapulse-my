#!/usr/bin/env bash
set -Eeuo pipefail
# per-dataset-derivation: populate dataset surfaces before aggregate generators.
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
python3 scripts/gen_health_trust_summary.py
python3 scripts/gen_quality_profile.py
checked_at=$(python3 -c 'import json; print(json.load(open("health/latest.json"))["checked_at"])')
python3 scripts/gen_trends.py --history /dev/null --daily health/history_daily.json --now "$checked_at"
python3 scripts/gen_drift.py --history /dev/null --daily health/history_daily.json
python3 scripts/gen_reconciliation.py
python3 scripts/gen_public_summary.py
python3 scripts/gen_catalog_snapshot.py
python3 scripts/gen_catalog_graph.py
python3 scripts/gen_public_discovery.py
# dashboard-after-derivation: docs/index.html is read by the parity tests as their
# served fixture, and nothing regenerated it here. A source-only PR therefore left it
# at main's dataset count and every parity test compared 448 against a stale 447.
# Carrying the file was what made this pass before; deriving it does the same without
# the churn, so its three producers run in the same order the release profile uses.
python3 scripts/gen_dashboard_sections.py
python3 scripts/gen_dashboard_filters.py
python3 scripts/embed_dashboard_data.py
python3 scripts/gen_jsonld_catalog.py
python3 scripts/gen_readme.py
python3 scripts/gen_llms_summary.py
python3 scripts/gen_mcp_reference.py
python3 scripts/gen_ai_catalog.py
python3 scripts/gen_json_envelope.py --force
python3 scripts/gen_changelog.py
