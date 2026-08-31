#!/usr/bin/env bash
# Wait for run 1 to finish, re-probe the Opus quota, then start run 2.
# The probe matters: rule 3 of the compute budget says never commit to a long
# run without one, and the reset boundary is NOT UTC midnight.
set -uo pipefail
cd /Users/emilycheyne/Development/kinder-readiness
export AWS_PROFILE=kinder-readiness-dev-cli

while pgrep -f 'run_task5.sh 1 both' >/dev/null; do sleep 30; done
echo "run1 finished $(date -u +%H:%M:%SZ)"

source venv/bin/activate
SPENT=$(aws cloudwatch get-metric-statistics --namespace AWS/Bedrock \
  --metric-name InputTokenCount --dimensions Name=ModelId,Value=us.anthropic.claude-opus-4-6-v1 \
  --start-time "2026-08-30T00:00:00" --end-time "$(date -u +%Y-%m-%dT%H:%M:00)" \
  --period 86400 --statistics Sum --region us-east-1 --query 'sum(Datapoints[].Sum)' --output text 2>/dev/null)
echo "opus input tokens spent today: ${SPENT}"

# Refuse to start run 2 if today's spend is already past ~1.6M input tokens.
# One detector sweep is ~315K total; leaving >900K of headroom keeps a mid-sweep
# throttle (which would record a state as n_detected=0) off the table.
if python -c "import sys; sys.exit(0 if float('${SPENT}') < 1600000 else 1)" 2>/dev/null; then
  echo "headroom OK -> starting run 2 $(date -u +%H:%M:%SZ)"
  ./paper/results/task5_20260830/run_task5.sh 2 both \
    > paper/results/task5_20260830/logs/sweep_run2.log 2>&1
  echo "run2 finished $(date -u +%H:%M:%SZ)"
else
  echo "REFUSING to start run 2: today's Opus spend ${SPENT} is at or past the 1.6M guard."
fi
