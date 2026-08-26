# Task 2 re-record — held-out detector + parser arms (2026-08-26)

Re-records **both arms** of Task 2 on the held-out states, at `code_version_hash`
**`7da92182`**.

**Baseline is `task2_20260822` (hash `288c64f1`), not `task2_20260816`.**
`paper/analysis/generate_tables.py` has `RUN_TAG = "20260822"`, so 20260822 is
what currently feeds the paper's tables. It also uses the same 46-element NV
golden as this run, which makes the comparison apples-to-apples — the 20260816
recording predates the golden extension and has a 41-element denominator.

**Headline (detector): NV code accuracy 44/46 (0.9565) → 46/46 (1.000) and
description accuracy 2/3 → 3/3, on an unchanged golden. KY unchanged at 44/44
on every dimension.**

**Headline (parser): NV unchanged and perfect at 24/24. KY regressed to 17/26
on parser sampling — see "Parser arm" below. The detection input is
byte-identical to the baseline and the parser prompt did not change, so this is
not a code regression, and in production the validator would reject all nine
affected rows rather than store them.**

⚠️ The two arms disagree about KY. Do not quote "KY unchanged" without saying
which arm.

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

## Parser arm — NV perfect, KY regressed on sampling

| | NV `288c64f1` | NV `7da92182` | KY `288c64f1` | KY `7da92182` |
|---|---|---|---|---|
| coverage | 1.0000 | 1.0000 | 1.0000 | 1.0000 |
| matched | 24 | 24 | 26 | 26 |
| field accuracy | 1.0000 | 1.0000 | 1.0000 | **0.9423** |
| fully correct | 24/24 | 24/24 | 26/26 | **17/26** |

**NV is untouched and perfect.** KY lost 9 rows, each failing on exactly three
fields — `sub_strand.code`, `indicator.code`, `standard_id`:

```
KY-STD-18  sub_strand.code  expected 'LEL.1.1'        got 'Benchmark 1.1'
           indicator.code   expected 'LEL.1.1.AAPWI'  got 'AAPWI'
           standard_id      expected 'US-KY-2021-LEL.1.1.AAPWI'  got 'US-KY-2021-AAPWI'
```

The parser left the detector's label-form sub_strand code unconverted and the
leaf then went bare. All nine are `LEL` (`LEL.1.1` ×4, `LEL.2.1` ×3, `LEL.2.2`
×2); AL and HMW are clean.

### ⚠️ This is sampling, and it is NOT caused by the new repairs

- The detection **input is byte-identical** between this run and the baseline —
  same 44 elements, same codes at domain, strand and sub_strand.
- Parsing batches by domain, and all nine failures sit in **one** domain. That
  is a single parser call sampling badly, not a systematic rule change.
- The **parser prompt did not change** between `288c64f1` and `7da92182`.

`_qualify_bare_indicator_code` **declined these rows by design.** Its
malformed-ancestor guard refuses to prefix a whitespace-bearing ancestor,
because that would inject whitespace into the primary key and swap a
`not nested` rejection for a `whitespace` one, hiding the cause. Removing the
guard would not recover the golden either — it yields `Benchmark 1.1.AAPWI`.

⚠️ **In production these nine rows would be rejected by
`validator._validate_code_shape` and never reach Aurora.** The eval does not run
the validator, so it scores them as field errors rather than as drops. The
recorded 0.9423 is therefore a *parser* number, not a statement about what
Aurora would hold.

### The repair that would close it — measured, not implemented

A deterministic de-label: a parent code shaped
`<token-with-no-leading-digit> <dotted-numeric-id>` is the label form and
rebuilds as `<resolved domain code>.<id>`. Shape-only, no label-word list.

| | |
|---|---|
| failing KY sub_strand codes repaired exactly | **9/9** |
| golden codes changed (106 standards, six states) | **0** |
| production codes changed (1974, two six-state runs) | **0** |

It composes with the existing bare-leaf repair: once the ancestor is
well-formed, `AAPWI` qualifies to `LEL.1.1.AAPWI`.

### ✅ Implemented 2026-08-26 as `_delabel_parent_code` (hash `14374dba`)

Replayed over **this recording's own saved output** — the same LLM sample, so
the repair's effect is isolated from sampling — and re-graded with
`eval_parser.grade_parser`, the identical function that produced the numbers
above:

| | before | after |
|---|---|---|
| KY fully correct | 17/26 | **26/26** |
| KY field accuracy | 0.9423 | **1.0000** |
| KY rows changed by the repairs | — | 9 |
| NV | 24/24 | 24/24 (0 rows changed) |

Reproduce with `paper/analysis/regrade_parser_repairs.py`; results in
`parser_regraded.json`. The golden four were re-graded the same way and **0 rows
changed** in any of them.

⚠️ This is a **replay, not a re-execution**: the repairs run pre-anchoring in
`parse_llm_response`, while the saved output is post-anchoring. For these shapes
the outcome is the same, but treat it as strong evidence for the repair on that
sample rather than as a live recording at `14374dba`.

⚠️ Implementing it also surfaced a **pre-existing** defect:
`_collapse_duplicated_parent_segment` was not idempotent on a code whose
segments repeat, and had shipped that way at `04e4924c`. It now iterates to a
fixed point. Caught by the property suite once the de-label change shifted
Hypothesis's search.

## ⚠️ Not done — this does NOT yet reach the paper's tables

`generate_tables.py` reads `task1_<RUN_TAG>/summary.json` **and**
`task2_<RUN_TAG>/summary.json` for a single shared `RUN_TAG`. Three things are
missing before the tag can move to `20260826`:

1. **No `summary.json` here.** Run `consolidate_task1.py --state NV --state KY`
   against this folder's two reports. (`task1_20260826/` now exists and has
   its own.)
2. **No re-signed `nv_fp_audit_SIGNED.json`.** The verified-precision path
   depends on it, and the existing signature covers 53 detections, not 52.
   `task1_20260826`'s `task1b_fp_audit_SIGNED.json` is stale for the same
   reason — AZ's detection count moved.

Until both land, the tables keep reporting `20260822` and this recording
stands as the detector-arm evidence only. That is deliberate: a half-migrated
`RUN_TAG` would silently mix hashes across the generalization table, which
guardrail 6 exists to prevent.
