# Task 2 re-record — held-out detector arm (2026-08-26)

Re-records the **detector arm only** of Task 2 on the held-out states, at
`code_version_hash` **`7da92182`**. The parser arm was not re-run.

**Baseline is `task2_20260822` (hash `288c64f1`), not `task2_20260816`.**
`paper/analysis/generate_tables.py` has `RUN_TAG = "20260822"`, so 20260822 is
what currently feeds the paper's tables. It also uses the same 46-element NV
golden as this run, which makes the comparison apples-to-apples — the 20260816
recording predates the golden extension and has a 41-element denominator.

**Headline: NV detector code accuracy 44/46 (0.9565) → 46/46 (1.000) and
description accuracy 2/3 → 3/3, on an unchanged golden. KY is unchanged at
44/44 on every dimension.**

## Numbers

| | NV `288c64f1` | NV `7da92182` | KY `288c64f1` | KY `7da92182` |
|---|---|---|---|---|
| golden elements | 46 | 46 | 44 | 44 |
| detected | 53 | **52** | 44 | 44 |
| matched | 46 | 46 | 44 | 44 |
| recall | 1.0000 | 1.0000 | 1.0000 | 1.0000 |
| precision (raw) | 0.8679 | 0.8846 | 1.0000 | 1.0000 |
| f1 | 0.9293 | 0.9388 | 1.0000 | 1.0000 |
| **code accuracy** | **44/46 (0.9565)** | **46/46 (1.0000)** | 44/44 (1.0000) | 44/44 (1.0000) |
| **description accuracy** | **2/3 (0.6667)** | **3/3 (1.0000)** | 26/26 (1.0000) | 26/26 (1.0000) |
| depth-map | PASS | PASS | PASS | PASS |
| regression cases | — | 3/3 PASS | — | 3/3 PASS |

`n_golden` and `matched` are identical on both sides for both states, so unlike
the 20260816 comparison there is no denominator artifact here. Every moved cell
is a code result.

## The two NV domain-code misses are fixed

`288c64f1` recorded exactly two mismatches, both domains:

```
NV-DOM-02  domain  golden 'S'  detected 'Science'
NV-DOM-03  domain  golden 'T'  detected 'TECH'
```

`7da92182` records `code_mismatches: []`. The run log shows cross-chunk drift
now resolving toward the document's codes rather than away from them:

```
Code normalization: domain 'science' — canonical code 'S', replaced: ['SCIE']
Code normalization: domain 'technology' — canonical code 'T', replaced: ['TECH']
```

This closes the failure that `task2_20260816/findings.md` §4 diagnosed at
length — `Science` losing to drift because lowercase fails the derivable shape,
`TECH` being derivable-but-ungrounded and recomputed away from the recovered
`T`. That section's *mechanism* is still correct and should be kept; its
*outcome* is superseded.

### ⚠️ Attribution: the delta is this week's code, but not isolated to one change

The improvement sits entirely inside `288c64f1 → 7da92182` on the **direct**
path. Two changes in that window can plausibly move NV detection:

1. **Pass-1 layout-stratified sampling** (`99b853cc`). NV is over the
   `DEPTH_MAP_SAMPLE_TOKENS` budget and does sample, and the new sampler spans
   pages 1-15 rather than 1-12 and sees 32 layout buckets rather than 29 — so
   the depth map injected into the detection prompt is built from different
   evidence.
2. **Rule 4's "code is REQUIRED, never null" clarification** (`b35b9666`), a
   detection-prompt change that could shift domain-code emission.

The parser-side repairs (`04e4924c`, `61b7243e`, `51056ea2`) cannot affect this
arm, and the widened `_DERIVABLE_CODE_RE` (`7da92182`) cannot either — `TECH` is
four characters and already matched the old `{1,5}` bound. **Do not attribute
the fix to a single change without an A/B.**

⚠️ An earlier reading of this — that the batched run `outputs/08-22-26-4`
already produced `S`/`SS`/`T` before this week, so the fix predated it — is
**not** evidence against the above. That is the direct-vs-batched divergence
again: the batched path had it right on 2026-08-22 while the direct path,
recorded the same day at `288c64f1`, still emitted `Science`/`TECH`. The two
paths simply disagreed.

⚠️ `SS` still passes **by coincidence**: `derive_code_from_title("Social
Studies")` happens to return `SS` (task2_20260816 §4). A future change to
`derive_code_from_title` or the connector list turns 46/46 into 45/46 with
nothing else moving.

## Description accuracy 2/3 → 3/3

The `288c64f1` miss was one truncation — the NV Science domain intro cut at 2410
of 3500 chars on the page 7→8 seam. It is now correct on the direct path.

⚠️ CLAUDE.md records `_splice_overlapping_prose` as fixing this on the
**batched** path while being inert on the **direct** path, because a single
chunk holds one truncated view with nothing to splice against. This run is the
direct path, so the splice is not what fixed it — the likeliest cause is again
the changed Pass-1 sample altering the detection prompt. **One run, not
isolated.** If the page-break question is reopened, start here.

## Guardrail 8 still applies to NV — unchanged

NV raw precision moved 0.8679 → 0.8846 only because `n_detected` fell 53 → 52.
It is **not** a hallucination rate. The six in-scope non-golden detections:

```
('indicator',  'SS.CI.PK3')              ← the known detector defect
('strand',     'Social Studies Standard 2')
('strand',     'Social Studies Standard 3')
('strand',     'Science Standard 2')
('strand',     'Technology Standard 2')
('sub_strand', 'S.EO')
```

Five of six are correct re-detections of headings the document reprints on a
second page spread. Counting them as hallucinations is precisely the error
guardrail 8 exists to prevent. **NV keeps the verified-precision path**; the
signed audit in `task2_20260822/nv_fp_audit_SIGNED.json` was computed against
53 detections and has **not** been re-signed for this run's 52 — see
"Not done" below. KY remains the one detection-exhaustive golden (44 golden vs
44 in-scope, zero unmatched), so its raw precision 1.000 is a real hallucination
rate.

## KY: unchanged, and that is the result

Every KY dimension is identical to `288c64f1`: 44/44 matched, precision, recall
and f1 all 1.000, code 44/44, description 26/26, depth-map PASS. Seven
code-version moves — three prompt changes and six new deterministic repairs —
moved nothing on the state whose golden is exhaustive.

⚠️ The `ICOPPPTM` over-long-code defect that motivated `7da92182` does **not**
appear in this arm: KY's direct-path run coded `ICOPP` correctly at both hashes.
It was observed on the **batched** path (pipeline run 043), which is why that
fix was validated by offline replay across `outputs/` rather than by this suite.

## Regression cases — 6/6 PASS

NV: `NV-NO-COLUMN-HEADER-AS-ELEMENT`, `NV-SUB-STRAND-CODE-FROM-DOCUMENT` (all 8
sub_strands carry the document's `XX.YY` caption code), `NV-FOUR-LEVEL-HIERARCHY`.
KY: `KY-BENCHMARK-IS-SUB-STRAND`, `KY-FOUR-LEVEL-HIERARCHY`,
`KY-STRAND-CODE-KEEPS-FULL-LABEL`.

## ⚠️ Not done — this does NOT yet reach the paper's tables

`generate_tables.py` reads `task1_<RUN_TAG>/summary.json` **and**
`task2_<RUN_TAG>/summary.json` for a single shared `RUN_TAG`. Three things are
missing before the tag can move to `20260826`:

1. **`task1_20260826/` does not exist.** The golden four (AZ, CA, CO, TX) have
   not been re-recorded at `7da92182`. Moving `RUN_TAG` now would break table
   generation outright.
2. **No `summary.json` here.** `consolidate_task1.py --state NV --state KY`
   produces it, and it needs a parser report to consolidate against — which
   this task did not re-run.
3. **No re-signed `nv_fp_audit_SIGNED.json`.** The verified-precision path
   depends on it, and the existing signature covers 53 detections, not 52.

Until all three land, the tables keep reporting `20260822` and this recording
stands as the detector-arm evidence only. That is deliberate: a half-migrated
`RUN_TAG` would silently mix hashes across the generalization table, which
guardrail 6 exists to prevent.
