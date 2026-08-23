# ⚠️ THE `INVALID_THROTTLED_*` FILES ARE INVALID — DO NOT QUOTE THEM

> **STATUS UPDATE 2026-08-23T16:14Z — the off-arm was successfully re-run.**
> The valid arm is `detector_nodepthmap.json` (six states, every one with
> `n_detected > 0` and `depth_map_passed = null`), with the comparison in
> `ablation_comparison.json` and the write-up in `findings.md`.
>
> **This document now covers ONLY the aborted first attempt**, whose output is
> retained under the `INVALID_THROTTLED_` prefix for the reproducibility record.
> Never quote those files and never merge them with the valid report.

## The original failure (2026-08-23T00:21–00:25Z)

Run 2026-08-23T00:21:56Z–00:25:38Z aborted with rc=1.

## What happened
Bedrock returned `ThrottlingException: "Too many tokens per day"` partway
through. The account's DAILY token quota was exhausted by the Task 1 + Task 2
arms that ran immediately before (35 min of Opus detection + Sonnet parsing).
This was NOT a concurrency problem — the run was strictly sequential. A daily
cap is not avoidable by pacing within the same day.

## Why the file is dangerous, not merely incomplete
`INVALID_THROTTLED_detector_nodepthmap.json` records SIX states, and five of
them read:

    n_detected=0  matched=0  recall=0.0  precision=0.0

Those zeros are the throttle, NOT the ablation. `detect_structure` raised, the
harness recorded an empty detection, and the grader scored the empty set. A
reader who takes this file at face value concludes that removing the depth map
drops detector recall from 1.000 to 0.000 on 5 of 6 states — i.e. that the
paper's central experiment produced a catastrophic effect. That would be a
fabricated result of exactly the kind guardrail 6 exists to prevent.

## What IS valid here
Exactly one state: **AZ**, which completed before the quota ran out.
  - off-arm: n_detected=65, recall=1.000, precision=0.500, depth_map=ABLATED (None)
  - on-arm  (task1_20260822): n_detected=66, recall=1.000, precision=0.4167, depth_map=PASS
One state is not a result. Do not report it.

## Confirmed working (the one genuinely good news here)
The ablation mechanism itself is verified end-to-end:
  - the pre-flight assertion passed: `Config.DEPTH_MAP_ENABLED = False`
  - the log carries `DEPTH_MAP_ABLATION: Pass-1 depth-map inference DISABLED`
  - detection proceeded via the real graceful-degradation path
    (`Depth-map inference failed; falling back to no-depth-map mode`)
  - the eval reported the third state `ABLATED` (`depth_map_passed=None`)
    rather than grading a map that was never produced
  - the `nodepthmap-` cache key kept the off-arm off the on-arm's cache
So the Task 3 instrument is sound; only the compute budget failed.

## The quota is Opus-specific (measured 2026-08-23T00:45Z)

Probed each model directly after the failure:

| model | used by | status |
|---|---|---|
| `us.anthropic.claude-opus-4-6-v1` | detector | **ThrottlingException — still exhausted** |
| `us.anthropic.claude-sonnet-4-6` | parser | OK |
| `us.anthropic.claude-haiku-4-5-20251001-v1:0` | depth map | OK |

Task 3's off-arm is detector-only, so it is blocked specifically on the Opus
daily token budget. Parser and depth-map work are unaffected. Probe cheaply
before committing to a full re-run rather than discovering the throttle 4
minutes in.

## How the re-run avoided this (kept for future reference)
Done 2026-08-23T16:05Z. Tasks 1 and 2 were NOT re-run (they are frozen).
Measured at the time: our own Task 1 + Task 2 arms consumed only 407,044 Opus
tokens, ~15.7% of the 2,592,000/day cross-region Opus 4.6 quota — so the day had
already been ~84% consumed by earlier activity before the first attempt started.
The off-arm was never the expensive part.

The re-run used SIX SEPARATE per-state invocations rather than one six-state
call, so a mid-sweep throttle could only cost one state. Command shape:

    source venv/bin/activate
    export AWS_PROFILE=kinder-readiness-dev-cli
    ELS_DEPTH_MAP_ENABLED=false python -m evaluation.eval_detector \
      --extraction-dir outputs/08-22-26-4 \
      --state AZ --state CA --state CO --state TX --state NV --state KY --no-cache \
      --report-json paper/results/task3_20260822/detector_nodepthmap.json \
      --output-dir paper/results/task3_20260822/review_detector_off

Verify before trusting the output:
  - every state must have n_detected > 0 (n_detected == 0 means throttled again,
    NOT ablated);
  - every state must show depth_map_passed = null (ABLATED) -- a true/false there
    means the flag did not take and the arm is invalid;
  - the log must carry 'DEPTH_MAP_ABLATION: Pass-1 depth-map inference DISABLED'
    once per state.

Consider running the six states as SEPARATE invocations with six report files.
A single six-state call loses five states to one mid-run throttle, which is
exactly what happened here.
