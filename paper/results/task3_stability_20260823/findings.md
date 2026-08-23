# Task 3 stability — is the depth-map ablation reproducible?

Runs 2026-08-23T18:32Z–18:58Z, `outputs/08-22-26-4`, `--no-cache`, code version
hash **`288c64f1`**, commit `628829b`. Sample 1 is the frozen recorded run
(`task1_20260822` + `task2_20260822` for ON, `task3_20260822` for OFF); samples
2–3 are repeats at the same hash on the same inputs.

**Corpus tier: `_only_subset`.** No number here is a full-document number.

> ⚠️ **Partial sweep: n=2 for four states, n=3 for AZ and (ON-arm only) CA.**
> The sweep was cut short by a Bedrock Opus daily-token throttle after 16 of 24
> runs. `off_run3_CA` was written with `n_detected=0` and is quarantined as
> `INVALID_THROTTLED_*`. **Run 2 completed for all six states in both arms**, so
> every state has at least two independent samples per arm.

---

## Headline: the DIRECTION is perfectly reproducible; the MAGNITUDE is not

| State | n | ON recall by run | OFF recall by run | gap by run |
|---|---|---|---|---|
| AZ | 3 | 1.000, 1.000, 1.000 | 1.000, 1.000, 1.000 | 0, 0, 0 |
| CA | 3/2 | 1.000, 1.000, 1.000 | 1.000, 1.000 | 0, 0 |
| **CO** | 2 | 1.000, 1.000 | **0.857, 0.714** | −0.143, −0.286 |
| **KY** | 2 | 1.000, 1.000 | **0.909, 0.977** | −0.091, −0.023 |
| NV | 2 | 1.000, 1.000 | 1.000, 1.000 | 0, 0 |
| TX | 2 | 1.000, 1.000 | 1.000, 1.000 | 0, 0 |

Three things are now measured rather than assumed:

1. **The ON arm is perfectly stable.** Recall 1.000 in every run of every state,
   stdev **0.000**. The headline detector claim does not move between samples.
2. **The null holds.** AZ, CA, NV and TX are at recall 1.000 in the OFF arm too,
   in every run, stdev **0.000**. "Four of six states are unaffected" is a
   reproduced result, not a single sample. This is the half of the conditional
   claim that a CO/KY-only repeat would have left unmeasured.
3. **The recall gap never changes sign** in any state.

### But the effect SIZE swings substantially, and the paper must not quote a point estimate

| | run 1 | run 2 | stdev | range |
|---|---|---|---|---|
| CO off-arm recall | 0.857 | **0.714** | 0.101 | 0.714 – 0.857 |
| KY off-arm recall | 0.909 | **0.977** | 0.048 | 0.909 – 0.977 |

KY's second sample is **0.977**, close to no effect at all; CO's is **0.714**,
substantially worse than recorded. On CO's 7-element golden one element is 0.143
of recall, so this is the fragility predicted before the runs — now quantified.

**Report ranges, not point values:** off-arm recall falls to **0.71–0.86** on CO
and **0.91–0.98** on KY. Any single-run figure — including the frozen
`task3_20260822` numbers — is one draw from that spread.

---

## The categorical evidence is rock solid, and it is what the paper should lead on

**Zero regression cases changed status across any run, in either arm.** Three
cases fail in the OFF arm and pass in the ON arm in **every** sample:

| case | what it detects |
|---|---|
| `CO-NO-SUB-STRAND` | detector invents a sub_strand level in a document that has none |
| `KY-BENCHMARK-IS-SUB-STRAND` | `Benchmark N.N` promoted to strand — classifying by LABEL |
| `KY-STRAND-CODE-KEEPS-FULL-LABEL` | labelled heading loses part of its own label |

This is the asymmetry that should shape the write-up. The *rates* are noisy
because two goldens are small; the *categorical* findings are invariant across
every run and do not depend on golden size at all. A regression case is a
yes/no assertion about document structure, and all three answer the same way
every time.

**Recommended framing for Task 12:** lead with the three reproducible
categorical failures and the level-wise pooled table, and report recall as a
range. Do not build the argument on a mean of two noisy samples.

---

## What this does NOT establish

- **n=2 is not a distribution.** For CO and KY the "range" is literally two
  points. It is enough to show the magnitude is unstable — which is the claim
  being made — but not enough to characterise the spread. Completing run 3
  (8 runs, ~400K Opus) would give n=3; more would be better still.
- **CA's OFF arm is n=2 while its ON arm is n=3**, because the throttle landed
  mid-pair. Its gap is 0 in both available samples.
- **It says nothing about the parser**, which never receives a depth map.
- **Corpus tier is unchanged.** These are 8–15pp subsets; Task 6 is where full
  documents get tested.

## Instrument notes

- `paper/analysis/ablation_stability.py` produces `stability_analysis.json`.
  It **refuses** any report whose `n_detected == 0` (a throttled run graded as
  recall 0.0 would fabricate catastrophic instability) or whose
  `depth_map_passed` does not match its arm, raising rather than averaging the
  bad row in.
- Deliberately **not** built on `eval_detector.measure_stability` (gotcha 6),
  which compares only its own probe runs and excludes the graded run. These are
  plain repeats with one report file per (arm, run, state), so the graded run is
  always part of the comparison.
- The sweep's per-run arm assertion **caught a real bug before any spend**: the
  first attempt used `${ARM@Q}`, a bash 4.4+ construct, on macOS bash 3.2.
  Without the guard the sweep could have run 24 mislabelled arms and produced a
  confidently wrong central result.
