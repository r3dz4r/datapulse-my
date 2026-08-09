#!/usr/bin/env bash
# watch_gov_verification.sh — periodic alert for Malaysia gov moving into verification
#
# Strategy (per odin-number-one-strategy-2026-08-09.md #4): if data.gov.my /
# datagovmy-meta adds freshness verification, schema-drift detection, or
# independent verification, our differentiator narrows. This watch catches
# that signal early.
#
# Signals watched:
#   1. New commits in data-gov-my/datagovmy-meta mentioning
#      "freshness|verified|stale|trust|schema.drift|quality"
#   2. New repos in data-gov-my org
#   3. data.gov.my homepage mentions of "freshness|verified|stale|trust"
#
# Output: short note only if signal detected (silent on healthy).
# Designed for cron + alert delivery.
set -u

ORG="data-gov-my"
META_REPO="datagovmy-meta"
OUT="${HOME}/.hermes/memory_traces/gov-verification-watch-$(date -u +%Y-%m-%d).md"
mkdir -p "$(dirname "$OUT")"

alert() { printf '%s\n' "$@" >> "$OUT"; }
hits=0

# --- 1. datagovmy-meta commits (last 7 days) mentioning verification terms ---
echo "[$(date -u +'%Y-%m-%dT%H:%M:%SZ')] Watching $META_REPO + $ORG + data.gov.my" >> "$OUT"

recent_commits=$(curl -sL --max-time 15 \
  "https://api.github.com/repos/$ORG/$META_REPO/commits?per_page=30&since=$(date -u -d '7 days ago' +'%Y-%m-%dT%H:%M:%SZ' 2>/dev/null || date -u +'%Y-%m-%dT%H:%M:%SZ')" 2>/dev/null)

if [[ -n "$recent_commits" ]]; then
  interesting=$(echo "$recent_commits" | jq -r '
    .[]? | select(
      (.commit.message // "" | test("freshness|verified|stale|trust|schema.drift|quality|verification"; "i"))
    ) | "[\(.sha[0:7])] \(.commit.message | split("\n")[0])"
  ' 2>/dev/null)

  if [[ -n "$interesting" ]]; then
    alert ""
    alert "## 🔔 datagovmy-meta commits mentioning verification (last 7 days)"
    echo "$interesting" | while read -r line; do alert "  $line"; done
    hits=$((hits + 1))
  fi
fi

# --- 2. New repos in data-gov-my org ---
org_repos=$(curl -sL --max-time 15 "https://api.github.com/orgs/$ORG/repos?per_page=100&sort=created&direction=desc" 2>/dev/null)
new_repos=$(echo "$org_repos" | jq -r '
  .[]? | select(
    (.created_at // "" | . >= (now - 7*86400 | strftime("%Y-%m-%dT%H:%M:%SZ")))
    and (.name // "" | test("freshness|verified|stale|trust|quality|monitor|verify|verif"))
  ) | "  [\(.name)] \(.description // "(no description)")"
' 2>/dev/null)

if [[ -n "$new_repos" ]]; then
  alert ""
  alert "## 🔔 New data-gov-my repos with verification-relevant names (last 7 days)"
  echo "$new_repos" | while read -r line; do alert "$line"; done
  hits=$((hits + 1))
fi

# --- 3. data.gov.my homepage text — does it mention verification terms? ---
home_text=$(curl -sL --max-time 15 https://data.gov.my/ 2>/dev/null | grep -oiE '[a-z]*fresh[a-z]*|[a-z]*verif[a-z]*|[a-z]*stale[a-z]*|[a-z]*trust[a-z]*' 2>/dev/null | sort -u | head -10)

if [[ -n "$home_text" ]]; then
  alert ""
  alert "## ℹ️ data.gov.my homepage keywords (verification-relevant)"
  echo "$home_text" | while read -r word; do alert "  $word"; done
fi

# --- Final verdict ---
if [[ "$hits" -gt 0 ]]; then
  alert ""
  alert "VERDICT: signal detected ($hits categories). Run a deeper scan."
  echo "ALERT"  # signal to cron wrapper
else
  # silent: only keep a short heartbeat
  echo "" > "$OUT"  # truncate so we don't accumulate noise
  echo "[$(date -u +'%Y-%m-%dT%H:%M:%SZ')] No new gov verification signal." >> "$OUT"
fi

# Also print summary to stdout (for cron to capture)
if [[ "$hits" -gt 0 ]]; then
  echo "ALERT: $hits signal category(ies). See $OUT"
else
  echo "OK: no new gov verification signal as of $(date -u +'%Y-%m-%dT%H:%M:%SZ')"
fi
