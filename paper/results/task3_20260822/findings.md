# Task 3 — depth-map ablation: does Pass 1 do real work?

Off-arm run 2026-08-23T16:05:28Z–16:14:12Z UTC, `outputs/08-22-26-4`,
`--no-cache`, code version hash **`288c64f1`**, commit `628829b`.

**The ON-arm was not re-run.** It is the frozen Task 1 + Task 2 detector reports
(`paper/results/task1_20260822/detector_golden4.json`,
`paper/results/task2_20260822/detector_heldout2.json`), which recorded
`depth_map: PASS` in all six states at this same hash and outputs folder.

**Corpus tier: `_only_subset`.** AZ 15pp, CA 13pp, CO 10pp, TX 9pp, NV 15pp of 98,
KY 8pp of 120. No number here is a full-document number.

> ⚠️ An earlier attempt at this arm (2026-08-23T00:21Z) aborted on a Bedrock
> daily-token-quota `ThrottlingException` after one state. Its output is retained
> as `INVALID_THROTTLED_*` and must never be quoted — five of its six states read
> `recall=0.0` because detection raised, not because the ablation did anything.
> See `DO_NOT_USE.md`. **This folder's `detector_nodepthmap.json` is the valid
> arm**; every state in it has `n_detected > 0` and `depth_map_passed = null`.

---

## Headline result

| State | recall ON | recall OFF | Δ | code ON | code OFF | regressions ON → OFF |
|---|---|---|---|---|---|---|
| AZ | 1.000 | 1.000 | 0.000 | 4/4 | 4/4 | 2/2 → 2/2 |
| CA | 1.000 | 1.000 | 0.000 | 25/25 | 25/25 | 4/4 → 4/4 |
| **CO** | 1.000 | **0.857** | **−0.143** | 7/7 | 6/6 | 2/2 → **1/2** |
| TX | 1.000 | 1.000 | 0.000 | 8/8 | **6/8** | 3/3 → 3/3 |
| NV | 1.000 | 1.000 | 0.000 | 44/46 | 45/46 | 3/3 → 3/3 |
| **KY** | 1.000 | **0.909** | **−0.091** | 44/44 | **36/40** | 3/3 → **1/3** |

Mean recall **1.000 → 0.961**. Three regression cases newly fail:
`CO-NO-SUB-STRAND`, `KY-BENCHMARK-IS-SUB-STRAND`, `KY-STRAND-CODE-KEEPS-FULL-LABEL`.

### Pooled by level — this is the actual finding

| level | recall ON | recall OFF | precision ON | precision OFF |
|---|---|---|---|---|
| domain | 1.000 | **1.000** | 1.000 | 1.000 |
| strand | 1.000 | 0.960 | 0.625 | 0.5455 |
| **sub_strand** | 1.000 | **0.875** | 0.5854 | 0.600 |
| indicator | 1.000 | 0.9863 | 0.3578 | 0.3673 |

**The damage concentrates at strand and sub_strand and leaves domain untouched.**
That is the paper's thesis in one table: a domain is identifiable from the page
alone (it is always the top level) and an indicator is identifiable as the leaf,
but a *strand* and a *sub_strand* are defined by **where they sit**, and that is
exactly what Pass 1 supplies.

---

## What the paper may and may not claim

### 1. The ablation degrades quality, but NOT uniformly — and the non-uniformity is the result, not a weakness.

Four of six states are completely unaffected (AZ, CA, TX, NV all hold recall
1.000). Reporting "mean recall 1.000 → 0.961" alone would understate what
happened in CO and KY and overstate what happened in the other four. **Report the
per-state table, not the mean.** The honest claim is *conditional*: the depth map
matters for documents whose level identity depends on nesting position, and is
close to free for documents where it does not.

### 2. Kentucky is the cleanest evidence for the paper's title: the detector literally classifies by LABEL when it cannot reason about position.

KY's confusion matrix is perfectly diagonal in the on-arm and migrates in the
off-arm:

| level | ON (tp) | OFF tp / fp / fn |
|---|---|---|
| domain | 3 | 3 / 0 / 0 |
| strand | 5 | 4 / **4** / 1 |
| sub_strand | 10 | 7 / 0 / **3** |
| indicator | 26 | 26 / 0 / 0 |

Three sub_strands vanish and four spurious strands appear. The failing regression
names the mechanism outright:

> `KY-BENCHMARK-IS-SUB-STRAND`: **4/11 Benchmark elements are not sub_strand**
> (e.g. `level='strand'`, `code='Benchmark 1.1'`, title *"Maintains focus and
> sustains attention."*)

`Benchmark 1.1` is a **sub_strand by position** — it nests under a strand and
above indicators. Without the depth map the detector reads the *word* "Benchmark"
and promotes it to strand. Domain and indicator, whose identity does not depend
on position, stay at 26/26 and 3/3.

The second KY failure is the same defect one level up:

> `KY-STRAND-CODE-KEEPS-FULL-LABEL`: 4/13 labelled headings lost part of their
> label — `strand code='Standard 2'` should be `'Approaches to Learning Standard 2'`.

### 3. Colorado shows the complementary failure: without a depth map the detector INVENTS a level the document does not have.

CO is a genuine 3-level document — domain → strand → indicator, no sub_strand.
The on-arm respects that. The off-arm does not:

> `CO-NO-SUB-STRAND`: **9 unexpected sub_strands present**, e.g.
> `('1', 'Recognize self as a unique individual having own abilities, characteristics, emotions, and interests.')`

Off-arm CO sub_strand is `tp=0, fp=9` — every one is spurious. So Pass 1 is not
only assigning levels correctly, it is establishing **how many levels the document
has**. That is a distinct contribution from per-element classification and the
paper should say so separately.

CO also loses one indicator (`CO-IND-03`) and its indicator false positives
balloon to 23, consistent with elements being redistributed across an invented
level rather than simply dropped.

### 4. Code accuracy degrades independently of recall, which recall-only reporting would hide.

**TX holds recall at 1.000 while its code accuracy falls 8/8 → 6/8.** No element
was missed or misclassified; the *codes* got worse. KY falls 44/44 → 36/40 on top
of its recall loss. Since `standard_id` is
`{country}-{state}-{year}-{indicator_code}`, a code regression is a primary-key
regression — so the depth map contributes to identifier stability, not only to
level assignment.

⚠️ **The code denominators differ between arms** (KY 44 vs 40, CO 7 vs 6) because
code accuracy is graded over matched pairs only, and the off-arm matches fewer
elements. Report `matches/total` for both arms, never a bare rate, and never
compare the two rates as if they shared a denominator.

### 5. NV's code accuracy went UP (44/46 → 45/46). Do not report this as the ablation helping.

One cell moved in the favourable direction on one state. NV's two on-arm code
misses are both `domain.code` and are documented in CLAUDE.md as arising from
`_resolve_code` grounding, a mechanism with no dependence on the depth map. This
is sampling noise at n=1, and the paper should either omit it or label it as
such. It is not evidence of anything.

### 6. What this arm does NOT show.

- **It does not isolate Pass 1 from prompt quality.** The off-arm still runs the
  full detection prompt; only the inferred depth map is withheld. The comparison
  measures the *marginal* contribution of Pass 1 given everything else, not the
  value of hierarchy information in general.
- **It says nothing about the parser**, which never receives a depth map. The
  parser numbers in Tasks 1 and 2 are unaffected by this flag and must not be
  cited in an ablation table.
- **It is one run per state, not a stability study.** CO and KY are the two
  smallest goldens (7 and 44 elements), so a single element moving shifts their
  recall by 0.14 and 0.02 respectively. The direction of the effect is
  corroborated by the regression failures — which are categorical, not
  rate-based — but the magnitudes are single samples. Task 5 is where repetition
  belongs.
- **The graceful-degradation path is real, not a strawman.** `infer_depth_map`
  returns `None`, which is the same signal an inference *failure* already
  produces, and `build_detection_prompt` has carried a `depth_map=None` branch all
  along. The off-arm therefore measures what genuinely happens in production when
  Pass 1 fails, which is worth one sentence in the paper.

### 7. An earlier one-state smoke test over-stated the effect; the recorded run is milder.

The pre-record KY smoke test reported recall 0.886, sub_strand recall 0.60 and
strand precision 0.40, with "6 of 12 `Benchmark N.N` elements" misclassified. The
recorded run gives recall **0.909**, sub_strand recall **0.700** (7/10), strand
precision **0.500** (4/8), and **4 of 11** Benchmark elements misclassified. Same
phenomenon, same direction, smaller magnitude — consistent with LLM sampling
between two single runs. **Quote the recorded numbers, not the smoke test's.**

---

## Instrument notes

- `paper/analysis/compare_ablation.py` produces `ablation_comparison.json`. It
  deliberately does **not** reuse `consolidate_task1.py`, which requires a parser
  report; the parser never sees a depth map, so there is no parser off-arm.
- The script **refuses** to emit a comparison for any state whose off-arm has
  `n_detected == 0` or a non-null `depth_map_passed`, marking it `INVALID` and
  excluding it from every aggregate. Those are the two signatures of the
  2026-08-23T00:25Z throttle failure and of an ablation flag that silently did not
  take. This run: **0 states excluded**.
- **`eval_detector` exits non-zero when a regression case fails.** CO and KY
  returned `rc=1` for that reason, not because the run errored. In an ablation
  off-arm a non-zero exit is the expected signal. Do not read it as a crash — but
  do check the log, since a genuine throttle also produces `rc=1`.
- The six states were run as **six separate invocations** with separate report
  files, precisely so a mid-sweep throttle would cost one state rather than five.
  The merged `detector_nodepthmap.json` is assembled from `per_state/`.

## Open questions for Emily

1. **Does the conditional framing suit the paper's argument?** The strongest
   honest claim is "the depth map is what makes position-dependent levels
   recoverable, and documents without such levels do not need it" — not "the
   depth map improves detection". The latter is unsupported for 4 of 6 states.
2. **CO and KY are the two states where it matters, and both are small goldens.**
   Worth considering whether Task 5's stability runs should cover CO/KY in both
   arms specifically, since they carry the entire effect.
