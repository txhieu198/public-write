#!/bin/bash
# Process revision queue until empty or max tasks reached.
#
# Usage:
#   AUTOMATION_KEY=xxx AQ_AGENT=HLA03-Cursor-orchestrator-1 ./process_revision_batch.sh [max_tasks]
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
MAX="${1:-999}"
DONE=0
FAIL=0
EMPTY=0

log() { echo "[$(date '+%H:%M:%S')] $*"; }

while [ "$((DONE + FAIL))" -lt "$MAX" ]; do
  OUT=$("$SCRIPT_DIR/process_one_revision.sh" 2>&1) || true
  echo "$OUT"

  if echo "$OUT" | grep -q "^NO_TASK"; then
    EMPTY=1
    break
  fi
  if echo "$OUT" | grep -q "^DONE task="; then
    DONE=$((DONE + 1))
    continue
  fi
  if echo "$OUT" | grep -q "^FAIL"; then
    FAIL=$((FAIL + 1))
    continue
  fi
  FAIL=$((FAIL + 1))
  sleep 1
done

log "Batch finished: done=${DONE} fail=${FAIL} empty=${EMPTY}"
exit 0
