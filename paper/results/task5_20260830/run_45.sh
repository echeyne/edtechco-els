#!/usr/bin/env bash
# Runs 4 and 5, executed 2026-08-31 — ~18h after runs 1-3, which is the
# cross-day separation Task 5's blocker 2 requires. Runs 1-3 were one session
# despite run 3 carrying an Aug-31 UTC stamp (it merely crossed UTC midnight).
set -uo pipefail
cd /Users/emilycheyne/Development/kinder-readiness
export AWS_PROFILE=kinder-readiness-dev-cli
BASE=paper/results/task5_20260830

spent() {
  aws cloudwatch get-metric-statistics --namespace AWS/Bedrock --metric-name InputTokenCount \
    --dimensions Name=ModelId,Value=us.anthropic.claude-opus-4-6-v1 \
    --start-time "$(date -u +%Y-%m-%dT00:00:00)" --end-time "$(date -u +%Y-%m-%dT%H:%M:00)" \
    --period 86400 --statistics Sum --region us-east-1 \
    --query 'sum(Datapoints[].Sum)' --output text 2>/dev/null
}

for N in 4 5; do
  S=$(spent)
  echo "=== before run ${N}: opus input tokens today = ${S} ==="
  # ⚠️ Use the venv interpreter explicitly. A bare `python` is NOT on PATH here
  # (run_task5.sh activates the venv internally, but this wrapper runs before
  # that), so the guard exited nonzero for "command not found" and was read as
  # "over budget" -- it refused run 4 at 257k against a 1.6M limit.
  GUARD=$(./venv/bin/python - "$S" <<'PY' 2>&1
import sys
try:
    spent = float(sys.argv[1])
except (ValueError, IndexError):
    print("UNREADABLE"); raise SystemExit
print("OK" if spent < 1600000 else "OVER")
PY
)
  if [[ "$GUARD" != "OK" ]]; then
    echo "REFUSING run ${N}: guard says '${GUARD}' for spend '${S}' (limit 1.6M)."
    break
  fi
  ./"$BASE"/run_task5.sh "$N" both > "$BASE"/logs/sweep_run${N}.log 2>&1
  echo "run ${N} done $(date -u +%H:%M:%SZ)"
done
echo "=== runs 4-5 sequence finished $(date -u +%Y-%m-%dT%H:%M:%SZ) ==="
