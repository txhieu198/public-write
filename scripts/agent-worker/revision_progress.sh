#!/bin/bash
# Poll agent-queue stats and count revision tasks by status.
#
# Usage:
#   AUTOMATION_KEY=xxx ./revision_progress.sh
#   AUTOMATION_KEY=xxx ./revision_progress.sh --verbose
#
# Env:
#   AUTOMATION_KEY  (required)
#   BASE_URL        (default: https://hlagency.net)
#   AGENT_ID        (optional, for display only)
set -euo pipefail

AUTOMATION_KEY="${AUTOMATION_KEY:-}"
BASE_URL="${BASE_URL:-https://hlagency.net}"
VERBOSE=false

for arg in "$@"; do
  case "$arg" in
    --verbose|-v) VERBOSE=true ;;
  esac
done

if [ -z "$AUTOMATION_KEY" ]; then
  echo "ERROR: AUTOMATION_KEY env var is required" >&2
  exit 1
fi

API_URL="${BASE_URL}/api/n8n/agent-queue"
HDR=(-H "X-Automation-Key: ${AUTOMATION_KEY}" -H "Accept: application/json")

stats_json=$(curl -s "${API_URL}/stats" "${HDR[@]}")

if ! echo "$stats_json" | jq -e '.success' >/dev/null 2>&1; then
  echo "ERROR: stats request failed" >&2
  echo "$stats_json" >&2
  exit 1
fi

queued=$(echo "$stats_json" | jq -r '.data.queued // .data.by_status.queued // 0')
running=$(echo "$stats_json" | jq -r '.data.running // .data.by_status.running // 0')
done=$(echo "$stats_json" | jq -r '.data.done // .data.by_status.done // 0')
failed=$(echo "$stats_json" | jq -r '.data.failed // .data.by_status.failed // 0')

# Count revision tasks in recent pages (queued + running)
count_revision_status() {
  local status=$1
  local total=0
  local page=1
  local last_page=1

  while [ "$page" -le "$last_page" ] && [ "$page" -le 20 ]; do
    resp=$(curl -s "${API_URL}/list?status=${status}&per_page=100&page=${page}" "${HDR[@]}")
    last_page=$(echo "$resp" | jq -r '.meta.last_page // 1')
    n=$(echo "$resp" | jq '[.data[] | select(.input_json.options.revision_note != null)] | length')
    total=$((total + n))
    page=$((page + 1))
  done
  echo "$total"
}

rev_queued=$(count_revision_status queued)
rev_running=$(count_revision_status running)

echo "Agent Queue — $(date '+%Y-%m-%d %H:%M:%S')"
echo "  All tasks:  queued=${queued}  running=${running}  done=${done}  failed=${failed}"
echo "  Revision:   queued=${rev_queued}  running=${rev_running}"

if [ "$VERBOSE" = true ]; then
  echo ""
  echo "Recent queued revision tasks (first page):"
  curl -s "${API_URL}/list?status=queued&per_page=10" "${HDR[@]}" | \
    jq -r '.data[] | select(.input_json.options.revision_note != null) |
      "  #\(.id) s2d=\(.input_json.options.s2d_job_id // "?") pri=\(.priority) note=\(.input_json.options.revision_note[0:60])..."'
fi
