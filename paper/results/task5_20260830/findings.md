# Task 5 — stability / determinism (2026-08-30/31)

Five runs of both suites over all six states at `code_version_hash` **`14374dba`**,
against `outputs/08-26-26-2`, every invocation `--no-cache`. Runs 1–3 executed
the evening of 2026-08-30; runs 4–5 on 2026-08-31, ~18h later. The parser suite
additionally folds in the Task 1/2 parser arms recorded 2026-08-29 as
observation 0, giving **n=5 detector / n=6 parser**.

Corpus tier `_only_subset`, same as every other quality recording.

## Headline

| suite | identities compared | distinct unstable | rate |
|---|---|---|---|
| detector | 304 | 5 | **0.0164** |
| parser | 201 | 9 | **0.0448** |

Instability is **concentrated, not diffuse**. Four of six states are perfectly
stable on both suites across every run: **CA, CO, KY and TX show zero detector
disagreements**, and **AZ, CO, KY and TX show zero parser disagreements**. All
movement is in AZ (detector), CA (parser) and NV (both).

⚠️ Read every rate here as a **lower bound**. A defect firing in a minority of
runs easily survives five clean draws.

## ⚠️ The most important result: a recorded headline does not reproduce

`paper/results/task2_20260826/` records **NV detector code accuracy 46/46
(1.0000)** and presents it as the held-out generalization gain, with both NV
domain-code mismatches resolved. Five fresh runs give:

| | run1 | run2 | run3 | run4 | run5 | frozen recording |
|---|---|---|---|---|---|---|
| NV code accuracy | 44/46 | **45/46** | 44/46 | 44/46 | 44/46 | **46/46** |
| NV `n_detected` | 54 | 54 | 54 | 53 | 53 | 52 |

**The recorded 46/46 is above everything measured in five runs, and its
`n_detected` of 52 is below everything measured.** `n_golden` is 46 and
`matched` is 46 in all five, so no denominator moved — this is genuine
run-to-run variance in the same quantity.

The comparison is valid, and I checked the obvious confound: the frozen arm was
recorded at `7da92182` and these runs at `14374dba`, but commit `42dd8d3` (the
only change between them) touches **`parser.py` only** — `git diff` on
`detector.py` across it is empty. Identical detector code, identical extraction,
both `--no-cache`.

The mechanism is the documented NV domain-code drift: run 2 emitted `S` for the
Science domain (the golden value) while runs 1, 3, 4 and 5 emitted `Science`.

### Consequence for the sampler attribution

`nv_attribution_ab.json` concludes "**THE SAMPLER**, confirmed by controlled
A/B", from three arms on one frozen extraction: new layout sampler 46/46, old
stride sampler 43/46, depth map disabled 44/46.

Every arm there is **a single draw**. The new-sampler arm's own run-to-run range
is now measured at 44–45, so its recorded 46 was the top of its distribution,
and the 3-point A-vs-B gap sits inside that spread. **The attribution is not
established at n=1 per arm** and should not be reported as settled without
repeating each arm.

This does *not* overturn Task 3's depth-map ablation, which is a different
experiment at n=3 per arm across six states and shows a directional effect that
never changes sign. It bears specifically on the NV domain-code claim.

**Recommended paper treatment:** report NV detector code accuracy as a range
across runs (44–45 of 46), not as 1.000, and downgrade the sampler attribution
from "confirmed" to "suggested, not established at n=1 per arm" (guardrail 7).

## Where the day boundary shows

Runs 1–3 were one session; runs 4–5 were the next day. NV's detector output
splits exactly on that boundary — sizes **[54, 54, 54, 53, 53]** — with one
indicator ("Show curiosity and ask questions about objects, living things, and
nat…") present in all three same-session runs and **missing from both next-day
runs**.

This is July's finding reproduced, and it is the direct justification for
blocker 2: five back-to-back runs would have reported this element as perfectly
stable. Same-session agreement is not evidence of determinism.

## Per-state detail

**Detector.**
- **AZ** — 3 unstable identities, all presence. Sizes [74, 77, 77, 77, 77]: run 1
  alone under-detected, missing `Attachment`, `Respect` and one other
  sub-strand that all four later runs found. Graded recall is 1.000 in every
  run, so this is invisible to the headline metric — it moves only unannotated
  content.
- **NV** — 2 unstable: the `Science` code drift above, and the day-boundary
  presence change.
- **CA, CO, KY, TX** — zero disagreements across five runs.

**Parser.**
- **CA** — 4 identities / 12 rows, in 2 of 5 comparisons. The failing runs emit
  `ELD.1.0.VOCA.Foundation 1.1.BROA`: the documented structural-label-in-code
  defect, in the documented surface form and at the documented ~12-row scale.
  **Every one contains whitespace, so `validator._validate_code_shape` rejects
  all 12 before Aurora.** This is the paper's cleanest live demonstration that
  the guard is load-bearing rather than theoretical.
- **NV** — 5 identities: `strand.code`/`strand.name` on three standards
  (`SS.1` where the golden says `SS.2`) plus one `sub_strand.name`. The
  `NV-STRAND-PARENT-BY-HEADING` regression case failed in runs 1, 2 and 4 and
  passed in 3 and 5.
- **AZ, CO, KY, TX** — zero disagreements across six observations.

⚠️ The NV parser eval exits non-zero when that regression case fails. **That is
a quality signal, not an infrastructure failure** — the report is complete and
valid, and excluding those runs would have hidden the finding entirely.

## What this supports in the paper

1. The pipeline is **stable where it matters most and unstable in known,
   bounded places**: 4 of 6 states are perfectly reproducible on both suites.
2. The instability that exists is **caught by the validator** rather than
   reaching the database — the CA case is 12 malformed primary keys, all
   rejected on shape.
3. A single recorded run is **not** a safe basis for a held-out claim. The NV
   result above is the concrete instance, found by this task.
