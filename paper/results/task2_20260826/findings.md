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

**Headline (parser, re-run live at `14374dba` on 2026-08-29): NV 24/24 and
KY 26/26, both at field accuracy 1.0000.** The KY regression recorded below was
measured at `7da92182`, before `_delabel_parent_code`; the section is kept as
the diagnosis that motivated the repair. The numbers in the paper's tables are
the live `14374dba` ones.

**Headline (parser, as first recorded at `7da92182`): NV unchanged and perfect
at 24/24. KY regressed to 17/26 on parser sampling — see "Parser arm" below. The detection input is
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

### ✅ Attribution: the Pass-1 SAMPLER, confirmed by A/B (2026-08-26)

Settled by a controlled three-arm test on one frozen extraction, all at
`14374dba`, all `--no-cache`, all graded by the same `evaluate_state`. The only
thing that varies between A and B is which blocks Pass-1 sees:

| arm | code | desc |
|---|---|---|
| **A** — new layout-stratified sampler | **46/46** | **3/3** |
| **B** — old stride sampler, everything else identical | **43/46** | **2/3** |
| **C** — depth map disabled entirely | 44/46 | 2/3 |

**Reverting only the sampler reproduces both failures**, including the same two
domain mismatches `288c64f1` recorded (`NV-DOM-02` S→`Science`, `NV-DOM-03`
T→`TECH`). Rule 4's prompt clarification (`b35b9666`) is **exonerated** — it is
present in both arms and the failure returns anyway.

Arm C brackets the effect: with no depth map at all NV scores 44/46 with the
same domain pair, so the failure is depth-map-mediated and the sampler
determines whether the map is good enough to prevent it.

⚠️ Arm B scores 43/46, slightly worse than the 44/46 `288c64f1` recorded, because
of a third mismatch (`NV-SUB-06` `T.TT`→`TT`) that is ordinary detector sampling
variance. The two DOMAIN mismatches are the stable part and are what the A/B
turns on. Full record in `nv_attribution_ab.json`.

## Description accuracy 2/3 → 3/3 — also the sampler

The `288c64f1` miss was one truncation — the NV Science domain intro cut at 2410
of 3500 chars on the page 7→8 seam. The A/B above settles this too: arm B (old
sampler) scores **2/3** and arm A **3/3**, so the sampler fixed the description
as well as the codes.

⚠️ This is NOT `_splice_overlapping_prose`, which CLAUDE.md records as inert on
the direct path the eval runs. The mechanism is the depth map injected into the
detection prompt being built from a better sample.

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
