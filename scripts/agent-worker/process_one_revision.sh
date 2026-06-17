#!/bin/bash
# Process one revision task end-to-end (claim → fix → qc → complete).
#
# Usage:
#   AUTOMATION_KEY=xxx AQ_AGENT=HLA03-Cursor-orchestrator-1 ./process_one_revision.sh
#   ... --claim-only   # only claim + bootstrap, no submit
#   ... --task-id=123  # process already-claimed task (skip /next)
#
# NOTE: the --task-id= path shells out to export_task_json.php / assign_task.php,
# which live in the happykitemedia Laravel app and are NOT included in this repo
# (they need DB access). That flag only works when run from the happykitemedia
# checkout. The default /next-based claim flow below does not need them and
# works standalone from this repo.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO="$(cd "$SCRIPT_DIR/../.." && pwd)"

AUTOMATION_KEY="${AUTOMATION_KEY:-}"
AQ_AGENT="${AQ_AGENT:-HLA03-Cursor-orchestrator-1}"
BASE_URL="${BASE_URL:-https://hlagency.net}"
AQ_BASE="${BASE_URL}/api/n8n/agent-queue"
SCRATCH="${SCRATCH:-/tmp/agy_scratch}"
CLAIM_ONLY=false
TASK_ID=""

for arg in "$@"; do
  case "$arg" in
    --claim-only) CLAIM_ONLY=true ;;
    --task-id=*) TASK_ID="${arg#*=}" ;;
  esac
done

if [ -z "$AUTOMATION_KEY" ]; then
  echo "ERROR: AUTOMATION_KEY required" >&2
  exit 1
fi

mkdir -p "$SCRATCH"
HDR=(-H "X-Automation-Key: ${AUTOMATION_KEY}" -H "X-Agent-Id: ${AQ_AGENT}" -H "Accept: application/json")

if [ -z "$TASK_ID" ]; then
  curl -s "${AQ_BASE}/next?agent_id=${AQ_AGENT}" "${HDR[@]}" > "$SCRATCH/task.json"
  TASK_ID=$(python3 -c "import json; d=json.load(open('$SCRATCH/task.json')); print(d.get('data',{}).get('task_id','') or '')")
  if [ -z "$TASK_ID" ]; then
    echo "NO_TASK"
    exit 0
  fi
  curl -s -X POST "${AQ_BASE}/${TASK_ID}/start" "${HDR[@]}" > /dev/null
else
  php "$SCRIPT_DIR/export_task_json.php" "$TASK_ID" "$SCRATCH/task.json"
  php "$SCRIPT_DIR/assign_task.php" "$TASK_ID" "$AQ_AGENT"
  curl -s -X POST "${AQ_BASE}/${TASK_ID}/start" "${HDR[@]}" > /dev/null
fi

TASK_DIR="$SCRATCH/task_${TASK_ID}"
python3 "$SCRIPT_DIR/bootstrap_revision.py" "$SCRATCH/task.json" "$TASK_DIR"

if [ ! -f "$SCRATCH/cinematic_qc.py" ]; then
  curl -s "${AQ_BASE}/qc" -H "X-Automation-Key: ${AUTOMATION_KEY}" > "$SCRATCH/cinematic_qc.py"
fi

python3 "$SCRIPT_DIR/apply_mechanical_fix.py" "$TASK_DIR"

QC_ROUNDS=0
while [ "$QC_ROUNDS" -lt 4 ]; do
  if python3 "$SCRATCH/cinematic_qc.py" "$TASK_DIR"; then
    break
  fi
  python3 "$SCRIPT_DIR/apply_mechanical_fix.py" "$TASK_DIR" --aggressive
  QC_ROUNDS=$((QC_ROUNDS + 1))
done

if ! python3 "$SCRATCH/cinematic_qc.py" "$TASK_DIR" >/dev/null 2>&1; then
  echo "FAIL_QC task=${TASK_ID}" >&2
  curl -s -X POST "${AQ_BASE}/${TASK_ID}/fail" "${HDR[@]}" \
    -H "Content-Type: application/json" \
    -d "{\"error_message\":\"cinematic_qc failed after mechanical fix\"}" > /dev/null
  exit 1
fi

if [ "$CLAIM_ONLY" = true ]; then
  echo "BOOTSTRAP_OK task=${TASK_ID} dir=${TASK_DIR}"
  exit 0
fi

python3 "$SCRIPT_DIR/build_payload.py" "$TASK_DIR"
HTTP=$(curl -s -o "$TASK_DIR/resp.json" -w "%{http_code}" \
  -X POST "${AQ_BASE}/${TASK_ID}/complete" \
  "${HDR[@]}" -H "Content-Type: application/json" \
  -d @"$TASK_DIR/payload.json")

if [[ "$HTTP" =~ ^2 ]]; then
  echo "DONE task=${TASK_ID} http=${HTTP}"
  rm -rf "$TASK_DIR"
  exit 0
fi

echo "FAIL_SUBMIT task=${TASK_ID} http=${HTTP}" >&2
cat "$TASK_DIR/resp.json" >&2
exit 1
