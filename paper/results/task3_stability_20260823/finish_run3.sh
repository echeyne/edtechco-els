#!/bin/bash
# Task 3 stability -- finish run 3.
# Remaining after the 2026-08-23 Opus throttle: off/CA, and both arms for CO/TX/NV/KY.
# bash 3.2 compatible (macOS): no ${VAR@Q}, no associative arrays.
set -u

ROOT=/Users/emilycheyne/Development/kinder-readiness
OUT="$ROOT/paper/results/task3_stability_20260823"
LOG="$OUT/stability_run_finish3.log"
EXTRACT=outputs/08-22-26-4
RUN=3

cd "$ROOT" || exit 1
# shellcheck disable=SC1091
source venv/bin/activate || exit 1

: > "$LOG"
: > "$OUT/FAILURES_finish3.txt"

# (arm state) pairs, effect-carrying states FIRST so an early throttle costs least.
PAIRS="off:CO on:CO off:KY on:KY off:CA off:NV on:NV off:TX on:TX"

for PAIR in $PAIRS; do
  ARM="${PAIR%%:*}"
  ST="${PAIR##*:}"

  if [ "$ARM" = "off" ]; then
    export ELS_DEPTH_MAP_ENABLED=false
    EXPECT=False
  else
    unset ELS_DEPTH_MAP_ENABLED
    EXPECT=True
  fi

  # GUARD 1: assert the flag the *library* will actually read matches the arm.
  ACTUAL=$(python -c "from els_pipeline.config import Config; print(Config.DEPTH_MAP_ENABLED)")
  echo "arm=$ARM run=$RUN state=$ST DEPTH_MAP_ENABLED=$ACTUAL" | tee -a "$LOG"
  if [ "$ACTUAL" != "$EXPECT" ]; then
    echo "ABORT: arm=$ARM expected DEPTH_MAP_ENABLED=$EXPECT but got $ACTUAL" | tee -a "$LOG"
    exit 2
  fi

  REPORT="$OUT/reports/${ARM}_run${RUN}_${ST}.json"
  REVIEW="$OUT/review/${ARM}_run${RUN}/${ST}"
  mkdir -p "$REVIEW"

  echo "=== START $ARM run$RUN $ST $(date -u +%Y-%m-%dT%H:%M:%SZ) ===" | tee -a "$LOG"
  python -m evaluation.eval_detector \
      --extraction-dir "$EXTRACT" \
      --state "$ST" \
      --no-cache \
      --report-json "$REPORT" \
      --output-dir "$REVIEW" >> "$LOG" 2>&1
  RC=$?
  echo "=== END $ARM run$RUN $ST rc=$RC $(date -u +%Y-%m-%dT%H:%M:%SZ) ===" | tee -a "$LOG"

  # rc=1 is EXPECTED where regression cases fail (off-arm CO/KY), so rc alone is
  # not the health check. n_detected == 0 is the throttle signature.
  if [ $RC -ne 0 ]; then
    echo "$ARM run$RUN $ST rc=$RC" >> "$OUT/FAILURES_finish3.txt"
  fi

  VERDICT=$(python - "$REPORT" "$ARM" <<'PY'
import json, sys, pathlib
p, arm = pathlib.Path(sys.argv[1]), sys.argv[2]
if not p.exists():
    print("MISSING"); raise SystemExit
rows = json.loads(p.read_text())
if not rows:
    print("EMPTY"); raise SystemExit
for r in rows:
    if r.get("n_detected", 0) == 0:
        print("THROTTLED"); raise SystemExit
    expect_ablated = (arm == "off")
    if (r.get("depth_map_passed") is None) != expect_ablated:
        print("ARM_MISMATCH"); raise SystemExit
print("OK recall=%.4f n=%d dm=%s" % (
    rows[0]["recall"], rows[0]["n_detected"],
    "ABLATED" if rows[0]["depth_map_passed"] is None
    else ("PASS" if rows[0]["depth_map_passed"] else "FAIL")))
PY
)
  echo "  verdict: $VERDICT" | tee -a "$LOG"

  case "$VERDICT" in
    OK*) ;;
    *)
      # Quarantine immediately so ablation_stability.py can never read it, and
      # stop the sweep -- a throttle does not clear by retrying.
      if [ -f "$REPORT" ]; then
        mv "$REPORT" "$OUT/reports/INVALID_THROTTLED_${ARM}_run${RUN}_${ST}.json"
        mv "$REVIEW" "$OUT/review/INVALID_THROTTLED_${ARM}_run${RUN}_${ST}"
      fi
      echo "ABORT after $ARM/$ST: $VERDICT" | tee -a "$LOG"
      echo "$ARM run$RUN $ST QUARANTINED ($VERDICT)" >> "$OUT/FAILURES_finish3.txt"
      exit 3
      ;;
  esac
done

echo "ALL RUN-3 PAIRS COMPLETE $(date -u +%Y-%m-%dT%H:%M:%SZ)" | tee -a "$LOG"
