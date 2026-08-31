#!/usr/bin/env bash
# Task 5 — stability/determinism, plain repeats (NOT --stability-runs).
#
# WHY PLAIN REPEATS: --stability-runs N executes all N observations inside ONE
# invocation, i.e. one session. Task 5's blocker 2 requires observations to span
# at least two days, because July's finding was that 3 same-session runs agreed
# perfectly while a 24h-separated run differed by up to 9 elements. One
# --report-json per run is also the shape paper/analysis/ablation_stability.py
# already consumes.
#
# RULE 2 (compute budget): ONE INVOCATION PER STATE, separate --report-json, so
# a mid-sweep throttle costs one state instead of recording the rest as
# n_detected=0.
#
# Usage:  ./run_task5.sh <RUN_NUMBER> [detector|parser|both]
set -uo pipefail

RUN="${1:?usage: run_task5.sh <RUN_NUMBER> [detector|parser|both]}"
WHICH="${2:-both}"
STATES=(AZ CA CO TX NV KY)
OUTPUTS="outputs/08-26-26-2"
BASE="paper/results/task5_20260830"

cd "$(git rev-parse --show-toplevel)"
source venv/bin/activate

echo "=== Task 5 run ${RUN} (${WHICH}) started $(date -u +%Y-%m-%dT%H:%M:%SZ) ==="
echo "code_version_hash: $(python -c 'from evaluation.eval_common import code_version_hash; print(code_version_hash())')"

for ST in "${STATES[@]}"; do
  DET_REPORT="$BASE/reports/detector_run${RUN}_${ST}.json"
  if [[ ( "$WHICH" == "detector" || "$WHICH" == "both" ) && -s "$DET_REPORT" ]]; then
    echo "--- detector run${RUN} ${ST} SKIPPED (report already exists) ---"
  elif [[ "$WHICH" == "detector" || "$WHICH" == "both" ]]; then
    echo "--- detector run${RUN} ${ST} $(date -u +%H:%M:%SZ) ---"
    python -m evaluation.eval_detector \
      --extraction-dir "$OUTPUTS" --state "$ST" --no-cache \
      --report-json "$BASE/reports/detector_run${RUN}_${ST}.json" \
      --output-dir  "$BASE/review/detector_run${RUN}" \
      >> "$BASE/logs/detector_run${RUN}_${ST}.log" 2>&1
    echo "    exit=$? $(date -u +%H:%M:%SZ)"
  fi
  PAR_REPORT="$BASE/reports/parser_run${RUN}_${ST}.json"
  if [[ ( "$WHICH" == "parser" || "$WHICH" == "both" ) && -s "$PAR_REPORT" ]]; then
    echo "--- parser   run${RUN} ${ST} SKIPPED (report already exists) ---"
  elif [[ "$WHICH" == "parser" || "$WHICH" == "both" ]]; then
    echo "--- parser   run${RUN} ${ST} $(date -u +%H:%M:%SZ) ---"
    python -m evaluation.eval_parser \
      --detection-dir "$OUTPUTS" --state "$ST" --no-cache \
      --report-json "$BASE/reports/parser_run${RUN}_${ST}.json" \
      --output-dir  "$BASE/review/parser_run${RUN}" \
      >> "$BASE/logs/parser_run${RUN}_${ST}.log" 2>&1
    echo "    exit=$? $(date -u +%H:%M:%SZ)"
  fi
done
echo "=== Task 5 run ${RUN} (${WHICH}) finished $(date -u +%Y-%m-%dT%H:%M:%SZ) ==="
