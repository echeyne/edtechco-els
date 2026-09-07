# Grading the trimmed run against the two DRAFT goldens (2026-09-06)

⚠️ **The quality numbers here are CIRCULAR and must never be reported.** Both
drafts were generated from this run, so recall, precision, code accuracy and
field accuracy are tautological — detector code accuracy came back 177/177
(1.000) and means nothing. What is informative is anything that **fails**
(a self-derived golden the run does not satisfy is an internal inconsistency),
plus the regression cases and depth map, which are hand-written assertions
carried over from the subset golden and were never derived from output.

## 🔴 1. `eval_parser._match_key` collides on genuinely distinct standards

**The highest-priority item, and it is live today, not only at scale.**

`_match_key` is `(indicator name, age_band)`. In KY's 214-standard trimmed run
**7 key groups are non-unique, covering 14 standards** — and four of them are
*real, distinct standards that share an indicator name under different
sub-strands*:

| indicator name | standards |
|---|---|
| "Attempts challenging experiences." | `AL.4.1.ACE` and `AL.4.2.ACE` |
| "Recovers from setbacks." | `AL.4.1.RS` and `AL.4.2.RS` |
| "Creates patterns…" | `CA.1.2.CPSPM` (dance) and `CA.1.3.CPSPM` (music) |
| "Demonstrates…" | `CA.1.2.DIMAP` and `CA.1.3.DIMAP` |

`grade_parser` takes `cands[0]` when several candidates share a key, so it pairs
the golden's `CA.1.2` row with the run's `CA.1.3` row and then reports every
field that differs. **12 of the 17 field mismatches in this grade are phantom** —
artifacts of pairing the wrong twin, not disagreements.

⚠️ **Colorado is not the canary here; California is, and it is already
affected.** The recorded `_only_subset` CA parsing output has **16 colliding
keys** among its 94 standards (`"understanding words"`, `"using words"`). So the
defect is present in the corpus the paper measures.

✅ **No recorded number is wrong.** All six recorded parser reports show
`duplicated: []` — the goldens annotate 8–26 standards each, too few to hit a
collision. The defect bites only when the golden is large relative to the run,
which is exactly what a trimmed-tier golden is.

⚠️ **The obvious fix is wrong.** Adding the sub-strand code to the key trades a
phantom mismatch for a phantom *drop*: a standard whose code the parser got
wrong would stop pairing at all, which is precisely the failure
`_match_key`'s own docstring says it is shaped to avoid. The right change is to
keep the key and **tie-break among multiple candidates on parent-code
agreement** instead of taking `cands[0]` — the same shape as the existing
`_variant_suffix` tie-break, which already handles the proficiency-column case.

**This must be fixed before any trimmed-tier parser grading is trustworthy.**

## 🔴 2. The `age_band` defect is document-wide, and it explains every miss

| | affected | of | share |
|---|---|---|---|
| detector elements carrying the spurious band | **152** | 329 | **46%** |
| parser standards at `36-48` instead of `36-60` | **66** | 214 | **31%** |

- **All 100 detector "missing" rows are this field.** Zero golden rows fail to
  find a `(level, title)` match anywhere in the run — the drafts annotate
  `age_band: null` (correct per the `RUN` verdict) and the run disagrees on 152
  elements.
- **All 66 parser "dropped" rows are this field**, exactly the 66 standards the
  run put at `36-48`.

This confirms the `RUN` verdict and sizes it: the 8-page window suggested the
problem, the full document shows it touches nearly half of detection output.

## 🟡 3. The surviving duplicates are not identical twins

Three descriptions came back **truncated** against their own draft entry:
236/624, 167/604 and 328/513 characters. The draft keeps the richer copy of each
duplicate pair, so this says the two un-merged copies carry *different amounts of
prose*. The duplication documented in Task 9 therefore costs description
completeness as well as identifier integrity, and `_merge_duplicate`'s
longest-wins rule never gets to run because the merge never fires.

## ✅ 4. What genuinely passes, and is not circular

The regression cases and the depth map are hand-written assertions carried from
the subset golden. They were never derived from output, and **all eight hold at
6.5× the page count**:

| | |
|---|---|
| depth map | **PASS** — `domain > strand > sub_strand > indicator` over all 52 pages |
| `KY-BENCHMARK-IS-SUB-STRAND` | PASS — all **60** Benchmark elements classified `sub_strand` |
| `KY-FOUR-LEVEL-HIERARCHY` | PASS |
| `KY-STRAND-CODE-KEEPS-FULL-LABEL` | PASS — all **70** labelled headings keep the full label |
| `NO-ID-COLLISION` | PASS — 214 unique ids |
| `KY-FOUR-LEVEL-RESOLVED` | PASS — all 214 standards carry both a strand and a sub_strand |
| `KY-BENCHMARK-CODE-NORMALIZED` | PASS — no label text in any code; all **642** child codes prefixed by their parent |
| `KY-SUB-STRAND-NOT-INDICATOR-CODE` | PASS — all 214 keep the two codes distinct and nested |

That is the real result of this exercise: the structural invariants the paper
claims hold on a full document, at four detection batches, and they are testable
without any annotation at all.

## Reproduce

Grade the recorded run rather than re-running detection — inject it through
`evaluate_state(detect_fn=...)`, as `eval_baseline` does. Re-running would cost
18 Opus calls and measure a different draw.
