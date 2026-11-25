#!/usr/bin/env bash
# derive-on-merge: a dataset change lands without carrying the generated surfaces the
# health pipeline rewrites on main, and the pull-request lane still fails a wrong change.
#
# The fixture is a clone of this checkout with its uncommitted changes laid over HEAD.
# "The PR lane" here is the real run blocks of the deterministic-safety-net steps that
# judge these files, read out of .github/workflows/ci.yml by name and executed on genuine
# merge commits (HEAD^1 = base), as GitHub executes them. The regeneration step is not
# run: gen_json_envelope.py --force downloads every dataset, and no gate below reads its
# output. Every expected failure must fail at the expected step with the expected
# diagnostic, and every expected pass must print derive-on-merge's success line, so a
# broken fixture cannot report success.
set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$repo_root"
# Use the checkout's test dependencies locally; Actions supplies Python on PATH.
if [[ -x "$repo_root/.venv/bin/python3" ]]; then
  export PATH="$repo_root/.venv/bin:$PATH"
fi
fixture="$(mktemp -d -p . .derive-on-merge-test.XXXXXX)"
trap 'rm -r -- "$fixture"' EXIT
fixture="$(cd "$fixture" && pwd)"
repo="$fixture/repo"
export TMPDIR="$fixture/tmp"
mkdir -p "$TMPDIR"

fail() {
  printf 'FAIL: %s\n' "$*" >&2
  exit 1
}

gitf() {
  git -C "$repo" -c user.name=derive-on-merge-fixture -c user.email=fixture@example.invalid \
    -c commit.gpgsign=false -c core.hooksPath=/dev/null "$@"
}

OWNED=(README.md catalog-graph.json catalog-snapshot.json changelog.json datapulse_summary.json
  health/latest.json health/trends.json health/drift.json)
DATASET=derive_on_merge_fixture

# --- The workflow wiring this test models must be the workflow that runs. -------------
python3 - .github/workflows/ci.yml <<'PY'
import sys
import yaml

steps = yaml.safe_load(open(sys.argv[1], encoding="utf-8"))["jobs"]["deterministic-safety-net"]["steps"]
names = [step.get("name") or "" for step in steps]
derive = [i for i, name in enumerate(names) if name.startswith("derive-on-merge")]
if len(derive) != 1:
    raise SystemExit(f"expected exactly one derive-on-merge step, found {len(derive)}")
step = steps[derive[0]]
run = step.get("run") or ""
problems = []
if step.get("if") != "env.FULL_VERIFICATION == 'true'":
    problems.append("derive-on-merge is not bound to full verification")
if step.get("continue-on-error"):
    problems.append("derive-on-merge is allowed to fail")
if not run.lstrip().startswith("set -Eeuo pipefail"):
    problems.append("a failing derive-on-merge would not fail the step")
for needle in ("scripts/derive_on_merge.sh check --base", "HEAD^1"):
    if needle not in run:
        problems.append(f"derive-on-merge run block lacks {needle!r}")
order = ["Install verification dependencies", names[derive[0]],
         "Detect README changes for the template precheck",
         "Verify README matches its template before regeneration",
         "Generate README from canonical inputs", "Verify live documentation counts",
         "Run repository-contract and MCP tests",
         "Verify repository contract"]
missing = [name for name in order if name not in names]
if missing:
    problems.append(f"steps missing: {missing}")
elif [names.index(name) for name in order] != sorted(names.index(name) for name in order):
    problems.append(f"steps are not in the order {order}")
regeneration = [i for i, name in enumerate(names) if name.startswith("Regenerate derived artefacts")]
if len(regeneration) != 1 or regeneration[0] < derive[0]:
    problems.append("derive-on-merge must precede the single regeneration step")
elif not names.index("Verify README matches its template before regeneration") < regeneration[0] < names.index("Verify live documentation counts"):
    problems.append("main's README precheck/regeneration/documentation-count order changed")
precheck = steps[names.index("Verify README matches its template before regeneration")]
if precheck.get("if") != "env.FULL_VERIFICATION == 'true' && steps.readme_precheck.outputs.changed == 'true'":
    problems.append("main's conditional README precheck changed")
if problems:
    raise SystemExit("ci.yml wiring: " + "; ".join(problems))
PY
printf 'PASS: ci.yml runs derive-on-merge on full verification, before the gates that judge README\n'

# --- Fixture: this checkout, uncommitted changes included, as "main". -----------------
git clone -q --shared --no-checkout "$repo_root" "$repo"
gitf checkout -q --detach "$(git rev-parse HEAD)"
while IFS= read -r -d '' path; do
  case "$path" in .derive-on-merge-test.*) continue ;; esac
  if [[ -e "$path" ]]; then
    mkdir -p "$repo/$(dirname "$path")"
    cp -p -- "$path" "$repo/$path"
  else
    rm -f -- "$repo/$path"
  fi
done < <(git ls-files -z -m -o -d --exclude-standard)
gitf add -A
gitf commit -q --allow-empty -m 'fixture: main with the change under test'
M0="$(gitf rev-parse HEAD)"

step_run() {
  python3 - "$repo/.github/workflows/ci.yml" "$1" <<'PY'
import sys
import yaml

steps = yaml.safe_load(open(sys.argv[1], encoding="utf-8"))["jobs"]["deterministic-safety-net"]["steps"]
matches = [step for step in steps if (step.get("name") or "").startswith(sys.argv[2])]
if len(matches) != 1:
    raise SystemExit(f"step {sys.argv[2]!r}: expected one match, found {len(matches)}")
sys.stdout.write(matches[0]["run"])
PY
}
LANE_STEPS=("derive-on-merge" "Detect README changes for the template precheck"
  "Verify README matches its template before regeneration" "Generate README from canonical inputs"
  "Verify live documentation counts" "Verify repository contract")
declare -A LANE_RUN
for name in "${LANE_STEPS[@]}"; do
  LANE_RUN["$name"]="$(step_run "$name")"
done

# Runs the lane on a merge commit; prints its log and the name of the failing step.
lane_output=""
lane_failed_step=""
lane() {
  gitf checkout -q -f --detach "$1"
  gitf clean -fdq
  [[ "$(gitf rev-parse HEAD^1)" == "$2" ]] || fail "merge commit $1 does not have base $2 as HEAD^1"
  lane_output=""
  lane_failed_step=""
  local name output status
  local step_output="$fixture/step-output"
  : > "$step_output"
  for name in "${LANE_STEPS[@]}"; do
    if [[ "$name" == "Verify README matches its template before regeneration" ]] &&
      ! grep -Fxq 'changed=true' "$step_output"; then
      lane_output+="== $name (skipped: README unchanged)"$'\n'
      continue
    fi
    set +e
    output="$(cd "$repo" && GITHUB_EVENT_NAME=pull_request BEFORE_SHA="" \
      FULL_VERIFICATION=true GITHUB_OUTPUT="$step_output" \
      bash --noprofile --norc -eo pipefail -c "${LANE_RUN[$name]}" 2>&1)"
    status=$?
    set -e
    lane_output+="== $name (exit $status)"$'\n'"$output"$'\n'
    if (( status != 0 )); then
      lane_failed_step="$name"
      return 1
    fi
  done
}

# A PR's merge ref: base as first parent, the PR head as second.
merge_ref() {
  gitf checkout -q -f --detach "$1"
  gitf merge -q --no-ff --no-edit -m "fixture: merge $2 into $1" "$2" >/dev/null
  gitf rev-parse HEAD
}

expect_pass() {
  local label="$1" commit="$2" base="$3"
  if ! lane "$commit" "$base"; then
    printf '%s\n' "$lane_output" >&2
    fail "$label: lane failed at '$lane_failed_step'"
  fi
  [[ "$lane_output" == *'derive-on-merge: merge result derived; every touched derivable path matches its source'* ]] \
    || { printf '%s\n' "$lane_output" >&2; fail "$label: derive-on-merge did not report success"; }
  [[ "$lane_output" == *'Repository contract verification passed'* ]] \
    || { printf '%s\n' "$lane_output" >&2; fail "$label: repository contract did not report success"; }
  printf 'PASS: %s\n' "$label"
}

expect_fail() {
  local label="$1" commit="$2" base="$3" step="$4" diagnostic="$5"
  if lane "$commit" "$base"; then
    printf '%s\n' "$lane_output" >&2
    fail "$label: lane passed a change it must reject"
  fi
  [[ "$lane_failed_step" == "$step" ]] \
    || { printf '%s\n' "$lane_output" >&2; fail "$label: failed at '$lane_failed_step', expected '$step'"; }
  [[ "$lane_output" == *"$diagnostic"* ]] \
    || { printf '%s\n' "$lane_output" >&2; fail "$label: missing diagnostic: $diagnostic"; }
  printf 'PASS: %s (rejected at %s)\n' "$label" "$step"
}

owned_unchanged_since() {
  gitf diff --quiet "$1" HEAD -- "${OWNED[@]}"
}

# --- Main advances: one simulated health cycle, written by the generators. ------------
gitf checkout -q -f --detach "$M0"
(cd "$repo" && python3 - <<'PY'
import json
from pathlib import Path

path = Path("health/latest.json")
snapshot = json.loads(path.read_text(encoding="utf-8"))
row = next(row for row in snapshot["datasets"] if row.get("status") == "fresh")
row["status"] = "aging"
counts = snapshot["_trust_summary"]["by_status"]
counts["fresh"] -= 1
counts["aging"] += 1
path.write_text(json.dumps(snapshot, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
PY
bash scripts/derive_on_merge.sh derive >/dev/null
python3 scripts/gen_public_summary.py >/dev/null)
gitf add -A
gitf commit -q -m 'fixture: health cycle rewrites the derived surfaces'
M1="$(gitf rev-parse HEAD)"
rewritten="$(gitf diff --name-only "$M0" "$M1" -- "${OWNED[@]}")"
[[ "$rewritten" == *README.md* && "$rewritten" == *catalog-snapshot.json* ]] \
  || fail "the simulated health cycle did not rewrite README.md and catalog-snapshot.json: $rewritten"

# The health pipeline is the writer: its own change carries every derived path it rewrote,
# and derive-on-merge must accept it rather than fight it.
expect_pass "health-cycle change carrying the paths it derived passes" "$(merge_ref "$M0" "$M1")" "$M0"

# --- A source-only dataset change, branched before that cycle. -------------------------
gitf checkout -q -f --detach "$M0"
datasets_before="$(cd "$repo" && python3 -c 'import json; print(len(json.load(open("datapulse.json"))["datasets"]))')"
(cd "$repo" && python3 - "$DATASET" "$datasets_before" <<'PY'
import json
import re
import sys
from pathlib import Path

dataset_id, before = sys.argv[1], int(sys.argv[2])
after = before + 1


def rewrite_json(relative, mutate):
    path = Path(relative)
    document = json.loads(path.read_text(encoding="utf-8"))
    mutate(document)
    path.write_text(json.dumps(document, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


# The manifest entry.
def add_entry(manifest):
    template = next(row for row in manifest["datasets"] if row["id"] == "air_pollution")
    entry = {key: value for key, value in template.items() if key != "attestation_ref"}
    entry.update(id=dataset_id, name="Derive-on-merge fixture dataset", health_report=f"data/{dataset_id}.md",
                 url=f"https://storage.data.gov.my/environment/{dataset_id}.csv")
    manifest["datasets"].append(entry)


rewrite_json("datapulse.json", add_entry)
# The registry source it needs: its JSON-envelope scope.
rewrite_json("scripts/contract-scope.json",
             lambda scope: scope["json_envelope"]["approved_ids"].append(dataset_id))
# Its per-dataset report and per-dataset artefacts, from the template dataset's.
for template, target in (("data/air_pollution.md", f"data/{dataset_id}.md"),
                         ("data/json/air_pollution.json", f"data/json/{dataset_id}.json"),
                         ("data/jsonld/air_pollution.json", f"data/jsonld/{dataset_id}.json"),
                         ("badges/air_pollution.svg", f"badges/{dataset_id}.svg")):
    Path(target).write_text(Path(template).read_text(encoding="utf-8").replace("air_pollution", dataset_id),
                            encoding="utf-8")
# Count-bearing prose outside the derived surfaces, which no health cycle rewrites.
claim = re.compile(rf"\b{before}(?=(?:-dataset\b| (?:official )?datasets\b))")
for relative in ("AGENTS.md", "mcp/AGENTS.md", "llms.txt", "docs/mcp-reference.md"):
    path = Path(relative)
    path.write_text(claim.sub(str(after), path.read_text(encoding="utf-8")), encoding="utf-8")
PY
)
gitf add -A
gitf commit -q -m 'fixture: add a dataset from source alone'
P="$(gitf rev-parse HEAD)"
owned_unchanged_since "$M0" || fail "the source-only dataset change carries a derived path"

# Control: the structure this replaces. The same change carrying its regenerated surfaces
# conflicts with the health cycle that landed meanwhile, so it could never run checks.
(cd "$repo" && bash scripts/derive_on_merge.sh derive >/dev/null)
gitf add -A
gitf commit -q -m 'fixture: the same dataset change carrying its regenerated surfaces'
P_CARRY="$(gitf rev-parse HEAD)"
gitf checkout -q -f --detach "$M1"
if gitf merge -q --no-ff --no-edit "$P_CARRY" >/dev/null 2>&1; then
  fail "control: a change carrying the derived surfaces merged cleanly; the fixture does not model the race"
fi
gitf merge --abort
printf 'PASS: control: carrying the derived surfaces conflicts with the intervening health cycle\n'

MERGE_P="$(merge_ref "$M1" "$P")"
expect_pass "source-only dataset change merges cleanly after a health cycle and passes" "$MERGE_P" "$M1"

# --- The merge-side derivation: it derives the new dataset, idempotently, in place. ----
gitf checkout -q -f --detach "$MERGE_P"
gitf clean -fdq
datasets_after=$((datasets_before + 1))
hash_owned() { (cd "$repo" && sha256sum -- "${OWNED[@]}"); }
(cd "$repo" && bash scripts/derive_on_merge.sh derive >/dev/null)
first="$(hash_owned)"
(cd "$repo" && bash scripts/derive_on_merge.sh derive >/dev/null)
second="$(hash_owned)"
[[ "$first" == "$second" ]] || fail "derivation is not idempotent: a second run changed bytes"
grep -qF "**${datasets_after} official datasets**" "$repo/README.md" \
  || fail "derivation did not bring README.md to ${datasets_after} datasets"
(cd "$repo" && python3 - "$DATASET" <<'PY'
import json
import sys

dataset_id = sys.argv[1]
health = json.load(open("health/latest.json", encoding="utf-8"))
if dataset_id not in {row["dataset_id"] for row in health["datasets"]}:
    raise SystemExit("derivation did not add the new dataset to health/latest.json")
if dataset_id not in open("catalog-snapshot.json", encoding="utf-8").read():
    raise SystemExit("derivation did not add the new dataset to catalog-snapshot.json")
PY
)
changed="$(gitf status --porcelain --untracked-files=all | cut -c4- | sort)"
expected_changed="$(printf '%s\n' README.md catalog-graph.json catalog-snapshot.json changelog.json health/latest.json | sort)"
[[ "$changed" == "$expected_changed" ]] \
  || fail "derivation wrote outside its derived paths: $(tr '\n' ' ' <<< "$changed")"
[[ "$(gitf rev-parse HEAD)" == "$MERGE_P" ]] && gitf diff --cached --quiet \
  || fail "derivation committed or staged something; the health pipeline is the only writer"
printf 'PASS: merge-side derivation derives the new dataset, is byte-identical across two runs, and writes only the working tree\n'

# --- Wrong changes still fail the lane. ----------------------------------------------
# A hand-edited generated file: README.md, the surface the lane always rejected edits to.
gitf checkout -q -f --detach "$P"
printf '\nHand-written claim the generator never wrote.\n' >> "$repo/README.md"
gitf commit -q -am 'fixture: hand-edit README.md'
expect_fail "hand-edited README.md is rejected" "$(merge_ref "$M0" "$(gitf rev-parse HEAD)")" "$M0" \
  "derive-on-merge" "::error file=README.md,title=derive-on-merge::"

# A hand-edited generated file the lane used to overwrite without judging.
gitf checkout -q -f --detach "$P"
(cd "$repo" && python3 - <<'PY'
from pathlib import Path

path = Path("catalog-graph.json")
text = path.read_text(encoding="utf-8")
if not text.startswith("{"):
    raise SystemExit("catalog-graph.json is not a JSON object")
path.write_text('{"hand_edited": true, ' + text[1:].lstrip(), encoding="utf-8")
PY
)
gitf commit -q -am 'fixture: hand-edit catalog-graph.json'
expect_fail "hand-edited catalog-graph.json is rejected" "$(merge_ref "$M0" "$(gitf rev-parse HEAD)")" "$M0" \
  "derive-on-merge" "::error file=catalog-graph.json,title=derive-on-merge::"

# A wall-clock timestamp is exempt, but every other public-summary field is judged.
gitf checkout -q -f --detach "$M1"
(cd "$repo" && python3 - <<'PY'
import json
from pathlib import Path

path = Path("datapulse_summary.json")
document = json.loads(path.read_text(encoding="utf-8"))
document["datasets_total"] += 1
path.write_text(json.dumps(document, indent=2) + "\n", encoding="utf-8")
PY
)
gitf commit -q -am 'fixture: hand-edit public summary'
expect_fail "hand-edited public summary is rejected apart from its clock" \
  "$(merge_ref "$M0" "$(gitf rev-parse HEAD)")" "$M0" \
  "derive-on-merge" "::error file=datapulse_summary.json,title=derive-on-merge::"

# A manifest entry without its required per-dataset source.
gitf checkout -q -f --detach "$P"
gitf rm -q "data/$DATASET.md"
gitf commit -q -m 'fixture: drop the per-dataset report'
expect_fail "manifest entry without its per-dataset report is rejected" \
  "$(merge_ref "$M1" "$(gitf rev-parse HEAD)")" "$M1" \
  "Verify repository contract" "dataset report: missing required paths: data/$DATASET.md"

printf 'PASS: derive-on-merge: source-only change lands, wrong changes fail, derivation is idempotent\n'
