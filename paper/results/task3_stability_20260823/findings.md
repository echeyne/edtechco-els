# Task 3 stability — is the depth-map ablation reproducible?

**COMPLETE at n=3.** Runs 2026-08-23T18:32Z–18:58Z (samples 1–2) and
2026-08-24T16:25Z–16:39Z (sample 3), `outputs/08-22-26-4`, `--no-cache`, code
version hash **`288c64f1`**, commit `628829b` / `9aa025b` (neither touches
`detector.py` or `parser.py`, so the hash is unchanged across both sessions).
Sample 1 is the frozen recorded run (`task1_20260822` + `task2_20260822` for ON,
`task3_20260822` for OFF); samples 2–3 are repeats at the same hash on the same
inputs.

**Corpus tier: `_only_subset`.** No number here is a full-document number.

> **n=3 per arm per state, all six states — 36 graded runs.** The 2026-08-23
> sweep was cut short by a Bedrock Opus daily throttle at 16 of 24 runs; the
> remaining 9 completed 2026-08-24 in 14 minutes for **454,113 Opus tokens
> (17.5% of the 2,592,000/day quota), $4.04**. The throttled `off_run3_CA` and
> its review directory stay quarantined as `INVALID_THROTTLED_*`; the run was
> re-executed cleanly.

---

## Headline: the DIRECTION is perfectly reproducible; the MAGNITUDE is not, and one categorical case is not either

| State | ON recall by run | OFF recall by run | gap by run |
|---|---|---|---|
| AZ | 1.000, 1.000, 1.000 | 1.000, 1.000, 1.000 | 0, 0, 0 |
| CA | 1.000, 1.000, 1.000 | 1.000, 1.000, 1.000 | 0, 0, 0 |
| **CO** | 1.000, 1.000, 1.000 | **0.857, 0.714, 0.857** | −0.143, −0.286, −0.143 |
| **KY** | 1.000, 1.000, 1.000 | **0.909, 0.977, 0.886** | −0.091, −0.023, −0.114 |
| NV | 1.000, 1.000, 1.000 | 1.000, 1.000, 1.000 | 0, 0, 0 |
| TX | 1.000, 1.000, 1.000 | 1.000, 1.000, 1.000 | 0, 0, 0 |

Four things are measured rather than assumed:

1. **The ON arm is perfectly stable.** Recall 1.000 in **all 18 ON runs**,
   stdev **0.000** in every state. The headline detector claim does not move
   between samples.
2. **The null holds at n=3.** AZ, CA, NV and TX are at recall 1.000 in the OFF
   arm too, in every run, stdev **0.000**. "Four of six states are unaffected"
   is now a three-sample result. This is the half of the conditional claim a
   CO/KY-only repeat would have left unmeasured, and it includes the held-out
   canary NV.
3. **The recall gap never changes sign** in any state, in any run.
4. **One categorical case DID change status** — see below. The 2026-08-23
   finding that "zero regression cases changed status across any run" was true
   at n=2 and is **false at n=3**.

### The effect SIZE swings substantially — quote ranges, never point estimates

| | run 1 | run 2 | run 3 | stdev | range |
|---|---|---|---|---|---|
| CO off-arm recall | 0.857 | **0.714** | 0.857 | 0.083 | 0.714 – 0.857 |
| KY off-arm recall | 0.909 | **0.977** | **0.886** | 0.047 | 0.886 – 0.977 |

KY's widest samples are 0.886 and 0.977 — the latter close to no effect at all.
On CO's 7-element golden one element is 0.143 of recall. **Off-arm recall falls
to 0.71–0.86 on CO and 0.89–0.98 on KY**; any single-run figure, including the
frozen `task3_20260822` numbers, is one draw from that spread.

---

## What is reproducible is the MECHANISM, not the rate — and that is the stronger claim

Level counts per run tell the story the recall percentages obscure. KY's golden
is 3 domain / 5 strand / 10 sub_strand / 26 indicator.

| KY | domain | strand | sub_strand | indicator |
|---|---|---|---|---|
| golden | 3 | **5** | **10** | 26 |
| ON run 1 / 2 / 3 | 3 / 3 / 3 | **5 / 5 / 5** | **10 / 10 / 10** | 26 / 26 / 26 |
| OFF run 1 / 2 / 3 | 3 / 3 / 3 | **8 / 7 / 10** | **7 / 9 / 6** | 26 / 26 / 26 |

The ON arm reproduces the golden's level distribution **exactly, in all three
runs**. The OFF arm inflates strand and deflates sub_strand **in all three
runs** — 3, 1 and 4 `Benchmark N.N` elements promoted from sub_strand to strand.
Domain and indicator counts are untouched at 3 and 26 throughout. That is the
paper's claim in one table: removing the depth map degrades exactly the levels
whose identity depends on *nesting position* rather than on a distinctive
surface form, and it does so every time. Only the *number* of collapsed
elements varies.

CO shows the same asymmetry with a different failure:

| CO | domain | strand | sub_strand | indicator | total |
|---|---|---|---|---|---|
| ON run 1 / 2 / 3 | 3 / 3 / 3 | 10 / 10 / 10 | **0 / 0 / 0** | 48 / 48 / 48 | 61 / 61 / 61 |
| OFF run 1 / 2 / 3 | 3 / 3 / 3 | 10 / 10 / 10 | **9 / 9 / 0** | 25 / 25 / 48 | 47 / 47 / **61** |

CO's document has no sub_strand level at all. The OFF arm invents one in runs 1
and 2 (9 spurious sub_strands, absorbing 23 elements that belong at indicator),
and in run 3 **does not** — its level distribution is identical to the ON arm's.

---

## The categorical evidence: two of three cases survive n=3

`CO-NO-SUB-STRAND` is **unstable**: `FAIL, FAIL, PASS`. It is exactly the run-3
behaviour above — the OFF arm happened not to invent the sub_strand level that
draw. It must **not** be cited as reproducible ablation evidence.

Two cases fail in the OFF arm and pass in the ON arm in **every** sample:

| case | what it detects | ON | OFF |
|---|---|---|---|
| `KY-BENCHMARK-IS-SUB-STRAND` | `Benchmark N.N` promoted to strand — classifying by LABEL | PASS ×3 | FAIL ×3 |
| `KY-STRAND-CODE-KEEPS-FULL-LABEL` | labelled heading loses part of its own label | PASS ×3 | FAIL ×3 |

**Note that CO still degrades in run 3 even with its regression case passing** —
recall 0.857, because it drops the golden strand `Health, Safety and Nutrition`,
which the ON arm never drops. The state-level degradation is reproducible in
all three runs; only its *surface form* on CO is not.

**Recommended framing for Task 12** (revised from the n=2 version): lead with
the **level-distribution table** — it is the mechanism, it is invariant across
runs, and it does not depend on golden size — supported by the two KY
regression cases and the pooled per-level recall. Report recall as a range.
Do **not** claim that no regression case changed status; one did.

---

## What this does NOT establish

- **n=3 is a small sample.** It is enough to show the direction is reproducible
  and the magnitude is not, and enough to catch one categorical case that n=2
  called stable. It is not enough for a confidence interval, and none is
  reported.
- **It says nothing about the parser**, which never receives a depth map.
- **Corpus tier is unchanged.** These are 8–15pp subsets; Task 6 is where full
  documents get tested.
- **AZ's ON-arm detection count moved (66, 76, 76) with recall pinned at
  1.000.** That is the known listing-page duplication interacting with a
  5-element spot-check golden, not an ablation effect — it appears in the ON arm
  and is orthogonal to this experiment.

## Instrument notes

- `paper/analysis/ablation_stability.py` produces `stability_analysis.json`.
  It **refuses** any report whose `n_detected == 0` (a throttled run graded as
  recall 0.0 would fabricate catastrophic instability) or whose
  `depth_map_passed` does not match its arm, raising rather than averaging the
  bad row in.
- **Sample size is now derived, not asserted** (2026-08-24). The script records
  `sample_sizes` from the runs it actually read, and
  `generate_tables.py` prints the caption's $n$ from that field. The previous
  hardcoded `n=3` in `what_this_measures` was wrong for the entire duration of
  the partial sweep, and a hardcoded `n{=}2$--$3` in the table caption would
  have silently survived this repair.
- **The table caption now names only the reproducible cases** (2026-08-24).
  `build_ablation_table` previously took its case list from the single frozen
  run, which would have printed `CO-NO-SUB-STRAND` as evidence that it "fails
  with the depth map disabled and passes with it enabled" — a claim this sweep
  refutes. Where a stability file is present it overrules the single run, and
  the demoted case is reported explicitly as unstable.
- Deliberately **not** built on `eval_detector.measure_stability` (gotcha 6),
  which compares only its own probe runs and excludes the graded run. These are
  plain repeats with one report file per (arm, run, state), so the graded run is
  always part of the comparison.
- The sweep's per-run arm assertion **caught a real bug before any spend**: the
  first attempt used `${ARM@Q}`, a bash 4.4+ construct, on macOS bash 3.2.
  Without the guard the sweep could have run 24 mislabelled arms and produced a
  confidently wrong central result. The run-3 driver keeps the same assertion
  and adds an immediate post-run verdict check that quarantines and aborts on
  `n_detected == 0` rather than continuing to spend into a throttle.
