# Task 13 — three fresh KY trimmed runs against the VERIFIED goldens (2026-09-07)

Runs `pipeline-US-KY-2021-full09072026-{1,2,3}`, all at `code_version_hash`
**`14374dba`**, same `kentucky_all_standards_2021_trimmed.pdf`, graded against
`ground_truth_{detector,parser}/KY_trimmed.json` (277 elements / 207 standards,
annotated by Emily Cheyne 2026-09-07).

## Why these numbers mean something and the previous grade did not

The goldens were seeded from the run of 2026-08-29 and then checked against the
PDF. Grading *that* run against them measured self-consistency. These three runs
are independent draws, so a miss is a real miss and an extra element is either a
real false positive or a golden gap.

⚠️ **Recall still has a ceiling.** The golden's coverage is bounded by what the
seeding run emitted, so an element **no** run produces is absent from the golden
too and cannot be detected here. Every recall figure below is *against a
verified reference set of 277 elements*, never against the document. Closing
that gap needs a cold read of the pages; it has not been done.

## Detector — complete, clean, and stable

| | run1 | run2 | run3 | seed (08-29) |
|---|---|---|---|---|
| elements emitted | 328 | 327 | 328 | 329 |
| **elements absent vs the golden** | **0** | **0** | **0** | — |
| **recall by level + title** | **1.000** | **1.000** | **1.000** | — |
| **hallucination candidates** | **0** | **0** | **0** | 0 |
| recall, strict `_match_key` | 0.592 | 0.588 | 0.592 | — |

**All 277 verified elements are found by all three runs.** Not one is missed,
and not one ungrounded element is emitted. That is the strongest quality
statement this project has produced at full-document scale, and it is now
non-circular.

The strict figure of ~0.59 is entirely `age_band` (below) and is not a quality
number.

## The two defects reproduce, and one is far larger than the window showed

| | run1 | run2 | run3 | seed | stdev |
|---|---|---|---|---|---|
| elements carrying the spurious band | 164 (50%) | 164 (50%) | 164 (50%) | 152 (46%) | **0.0** across the three |
| **surplus duplicate detections** | **51** | **50** | **51** | **52** | 0.58 |
| fabricated `.N` primary keys | 10 | 11 | 11 | 7 | 0.58 |

⚠️ **Duplication is ~15% of detector output, not the 11 elements the 8-page
window suggested.** Task 9 measured 11 surviving duplicates inside the annotated
window; document-wide it is **50–52 across all four runs** (4 strand, 9
sub_strand, 39 indicator on the seed). The window under-stated it by a factor of
five, and the figure is reproducible to ±1.

⚠️ **The `age_band` count is identical across three independent runs (164, stdev
0.0).** This is not sampling noise — it is a systematic misreading of the page
banner that lands on the same elements every time. That is a stronger and more
reportable claim than "unstable", and it argues the `SCHEMA` fix would be
deterministic in effect.

## Parser — coverage swings 12 points, and every point is `age_band`

| | run1 | run2 | run3 | mean | stdev |
|---|---|---|---|---|---|
| standards parsed | 214 | 220 | 220 | | |
| **coverage** | 0.807 | **0.927** | 0.841 | 0.858 | **0.062** |
| standards dropped | 40 | 15 | 33 | | |
| field accuracy | 0.9973 | 0.9939 | 0.9939 | **0.995** | 0.002 |
| `standard_id` collisions | 0 | 0 | 0 | 0 | 0 |

**Field accuracy is excellent and stable (0.995, stdev 0.002); coverage is
neither.** The 12-point swing tracks the dropped count exactly, and the drops
are standards the run put at `36-48` where the document has one band — the same
defect, one stage later. A paper reporting a single parser coverage figure for
this document would be reporting a draw from a 0.81–0.93 range.

⚠️ **`standard_id` collisions are 0 by construction and must not be cited as
evidence.** `disambiguate_colliding_standards` renames every collision before
the check runs. The honest figure is the fabricated-key count above: 10–11
standards per run whose id exists only to break a collision.

## What this establishes for the paper

1. **Detection quality survives full-document scale**: 277/277 verified elements
   found, zero hallucinations, three independent runs. Report with the ceiling
   caveat.
2. **`age_band` is a systematic defect, not variance** — identical count across
   three runs, and it accounts for the entire strict-recall shortfall, the ~51
   surviving duplicates and the 12-point parser coverage swing.
3. **Parser field accuracy 0.995 ± 0.002; parser coverage 0.858 ± 0.062.**
   Report both as ranges over n=3, never as point values.

## Regenerate

```
python -m paper.analysis.grade_ky_trimmed \
    --run outputs/ky-3runs-09-07-26/run1 \
    --run outputs/ky-3runs-09-07-26/run2 \
    --run outputs/ky-3runs-09-07-26/run3 \
    --out paper/results/task13_20260907
```

## ⚠️ Correction, 2026-09-19: "the same elements every time" was inferred, not measured

The sentence above ("a systematic misreading of the page banner that lands on
the same elements every time") was written from the count alone. Checked
against the three detection files by `(level, title)` of every element with a
non-null `age_band`: runs 1 and 3 carry an identical set of 164, run 2 differs
from them on five elements, and **159 elements are common to all three runs**.
The count is identical; the set is not. The systematic reading survives at
159 of 164, and the paper (§6.8, §7.5) now states the count and the 159
rather than identity. The original sentence is left in place above as the
record of what was claimed; this note supersedes it.
