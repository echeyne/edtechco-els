# Task 1 re-record — golden four (2026-08-26)

Re-records both arms of Task 1 on AZ, CA, CO and TX at `code_version_hash`
**`7da92182`**, against the `task1_20260822` baseline (**`288c64f1`**, commit
`628829b34b40`) — which is what `generate_tables.py` currently reads via
`RUN_TAG`.

**Headline: nothing moved. One cell in the entire re-record differs, and it is
a detection count outside the scored set.**

## Detector

| | AZ | CA | CO | TX |
|---|---|---|---|---|
| golden | 5 | 25 | 7 | 8 |
| detected `288c64f1` → `7da92182` | 66 → **67** | 122 | 61 | 33 |
| matched | 5 | 25 | 7 | 8 |
| recall | 1.0000 | 1.0000 | 1.0000 | 1.0000 |
| precision (raw, in-scope) | 0.4167 | 0.2049 | 0.1667 | 0.3200 |
| code accuracy | 4/4 | 25/25 | 7/7 | 8/8 |
| description accuracy | 4/4 | 14/14 | 4/4 | 3/3 |

Every scored dimension is identical to the baseline. **Recall is 1.000 on all
four states and code accuracy is perfect on all four.** The single difference is
AZ's total detection count, 66 → 67 — and its in-scope precision is unchanged
at 0.4167 (5 of 12 in-scope), so the extra element landed outside the annotated
domains and is not scored either way.

## Parser

| | AZ | CA | CO | TX |
|---|---|---|---|---|
| coverage | 1.0000 | 1.0000 | 1.0000 | 1.0000 |
| field accuracy | 0.9969 | 1.0000 | 1.0000 | 1.0000 |
| fully correct | 17/18 | 21/21 | 9/9 | 8/8 |
| id collisions | none | none | none | none |

**Byte-identical to the baseline on every state and every field.** Seven
code-version moves — three detection-prompt changes and six new deterministic
repairs — changed nothing on the golden four.

That is the intended result. Every repair added between `288c64f1` and
`7da92182` was validated beforehand by offline replay showing zero rows changed
across the golden four; this arm is the live confirmation of that prediction.

## ⚠️ The AZ duplicate-detection drop does NOT appear here

A batched-path observation on pipeline run 043 showed AZ detection falling
77 → 65 elements, entirely listing-page duplicate `sub_strand`s (`Vocabulary`,
`Concepts of Print`, `Book Handling Skills` each detected twice — once from the
p2-p4 listing page and once from the body). That prompted a prediction that AZ's
raw precision would rise, inverting the caution recorded at
`tasking/arxiv_paper.md` line 127.

**That prediction does not transfer to this arm.** On the direct path AZ went
66 → 67 detections and its in-scope precision did not move at all. The two paths
disagree, as they have repeatedly. The line-127 caution stands unmodified for
the eval numbers; the batched-path observation remains an open question about
production output, not about this table.

## Guardrail 8 is unaffected

Raw precision on the golden four remains what it has always been — a measure of
annotation coverage, not detector quality — because these goldens are 5-25
element spot checks against 12-122 in-scope detections. AZ 0.4167, CA 0.2049,
CO 0.1667, TX 0.3200 are all unchanged, and none may be reported as detector
precision. The verified-precision path via the Task 1b FP audit is still
required, and that audit has **not** been re-signed at this hash — see below.

## What this establishes for the paper

The golden-four table is unchanged by this week's work, which is the answer that
lets the held-out improvements in `task2_20260826` be read as generalization
rather than as a global shift. NV's code accuracy moved 44/46 → 46/46 while the
four states used to tune the system moved not at all.

## Re-graded at `14374dba` — still unchanged

The `_delabel_parent_code` repair added on 2026-08-26 was replayed over this
recording's saved parser output and re-graded with `eval_parser.grade_parser`:
**0 rows changed in any of the four states**, and every metric identical (AZ
17/18, CA 21/21, CO 9/9, TX 8/8). The detector arm is unaffected by
construction — the repair is in `parser.py`, which `eval_detector` never loads.

Results in `parser_regraded.json`; reproduce with
`paper/analysis/regrade_parser_repairs.py`. The repair fires only on the
held-out KY sample (9 rows), which is the state that exhibited the defect.

## ⚠️ Not done

1. **`task1b_fp_audit_SIGNED.json` is stale.** The existing signature was
   computed against the `288c64f1` detection counts; AZ's total moved. It must
   be re-signed with `paper/analysis/make_fp_signoff.py` before verified
   precision can be quoted at this hash.
2. **`RUN_TAG` has not been moved.** See `task2_20260826/manifest.json` for the
   full list of what the migration still needs.
