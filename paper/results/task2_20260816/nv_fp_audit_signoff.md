# ⚠️ SUPERSEDED — DO NOT SIGN THIS SHEET

**This sheet is obsolete and is retained only as part of the reproducibility
record. Signing it would put a stale claim in the paper.**

It audits **12 verdicts** against the **41-element** NV detector golden. Emily's
2026-08-22 exhaustive pass took that golden to **46 elements**, which annotated 5
of the rows below — so the live audit is **7 verdicts**, not 12, and the ceiling
is 46/53 = 0.8679, not 41/53 = 0.7736.

### ➡️ The sheet to sign is `paper/results/task2_20260822/nv_fp_audit_signoff.md`

### Why this file is kept rather than deleted

Its verdicts are preserved independently in this folder's
`heldout_evidence.json`, so nothing here is the sole copy of any measurement.
It is retained because the two audits together show the verdict methodology is
**stable under a golden change**:

| verdict | this sheet (41-elem golden) | current sheet (46-elem golden) |
|---|---|---|
| `real_repeat_of_matched` | 6 | 6 |
| `real_unannotated` | **5** | **0** |
| `hallucinated` | 1 | 1 |
| verified precision | 0.9811 | 0.9811 |

Every verdict that bears on the reported number is identical. The exhaustive pass
moved 5 rows from "needs a verdict" to "annotated" and changed nothing else —
same 6 reprinted-heading re-detections, same single `SS.CI.PK3` hallucination,
same 0.9811. That equivalence is only demonstrable while both sheets exist.

---

<details>
<summary>Original (superseded) sheet — expand only for the historical record</summary>

# NV false-positive audit — sign-off sheet

**You are the annotator of record.** Task 1b's methodology sentence for the paper is
*"all unmatched in-scope detections of the recorded run were manually audited by the
author"* — that sentence is not true, and NV's verified precision of 0.981 is not
quotable, until this file is signed.

## How to sign off

1. Open `standards/nevada_standards_2023_only_subset.pdf` (15pp).
2. Work through the three groups below. **Group C is the only one that needs real
   scrutiny** — A and B are mechanical.
3. For each row write `AGREE` or replace the verdict with the correct one, in the
   **Your call** column.
4. Fill in the sign-off block directly below, then tell me and I'll fold your
   verdicts into `heldout_evidence.json` (replacing `claude-first-pass-UNSIGNED`).

```
ANNOTATOR:        Emily Cheyne
DATE:             ____-__-__
VERDICTS CHANGED: ____   (0 if you agree with all 12)
SIGNED:           [ ]
```

## Scope — what you are and are not signing

- The detector emitted **53 elements** for NV, all inside annotated domains.
- **41** matched a golden entry (recall 1.000 at every level).
- The **12 rows below** are the leftovers. You are ruling on these 12 only.
- **KY needs no sign-off**: its golden is exhaustive (44 detected, 44 annotated, 0
  leftovers), so there is nothing to audit and its precision of 1.000 stands on the
  golden alone.

Verified precision = (in-scope detections − hallucinations) / in-scope detections.
With one hallucination that is **52/53 = 0.981**. Every row you move *into* or *out
of* the `hallucinated` bucket moves that number by ~0.019.

## Group A — real content the golden deliberately skipped (5 rows)

**Why I'm confident:** each title occurs verbatim and contiguously in the extraction,
and your own `test_case_id` numbering leaves exactly the matching gaps — you annotated
`NV-STR-01,02,03`, then `06,07`, then `10,11`, skipping 04/05, 08/09 and 12. These five
are precisely those skipped standards.

**What to check:** that each really is a Standard heading on the page cited.

| # | Page | Level | Document code | Title | My verdict | Your call |
|---|---|---|---|---|---|---|
| A1 | 3 | strand | `Social Studies Standard 4` | Demonstrate the ability to differentiate between the concepts of past, | real, unannotated | |
| A2 | 3 | strand | `Social Studies Standard 5` | Demonstrate an awareness of basic economic concepts. | real, unannotated | |
| A3 | 8 | strand | `Science Standard 3` | Demonstrate the ability to describe, analyze, and draw conclusions abo | real, unannotated | |
| A4 | 8 | strand | `Science Standard 4` | Demonstrate the ability to communicate about observations, investigati | real, unannotated | |
| A5 | 12 | strand | `Technology Standard 3` | Demonstrate safe and responsible use of technology and resources. | real, unannotated | |

## Group B — correct second detections of a reprinted heading (6 rows)

**Why I'm confident:** this is verified *structurally*, not by text search — each row
has the same level and title as an element that already matched a golden. NV reprints
its `<Domain> Standard N:` heading on every page spread the standard governs, so the
detector is right to emit it again; the parser collapses the duplicates (24 standards
out of 25 detected indicators).

**What to check:** that the heading really does appear on both pages cited. Spot-
checking two of the six is enough.

| # | Page | Level | Document code | Title | Repeat of | My verdict | Your call |
|---|---|---|---|---|---|---|---|
| B1 | 5 | strand | `Social Studies Standard 2` | Demonstrate a basic understanding of roles, rights,  | matched element, same title | real, repeat | |
| B2 | 6 | strand | `Social Studies Standard 3` | Demonstrate knowledge of the relationship between pe | matched element, same title | real, repeat | |
| B3 | 10 | strand | `Science Standard 1` | Demonstrate the ability to use senses and tools to e | matched element, same title | real, repeat | |
| B4 | 10 | sub_strand | `S.EO` | Exploration, Observation, and Hypotheses | matched element, same title | real, repeat | |
| B5 | 10 | strand | `Science Standard 2` | Demonstrate the ability to use information gathered  | matched element, same title | real, repeat | |
| B6 | 15 | strand | `Technology Standard 2` | Use technology for communication and to gather and s | matched element, same title | real, repeat | |

> One note on B4 (`S.EO`, *Exploration, Observation, and Hypotheses*): the full title
> is **not contiguous** in the extraction, because NV's multi-column table interleaves
> a *Supportive Practices* cell into the middle of it. Both halves — `Exploration,
> Observation,` and `and Hypotheses` — occur twice. That is a reading-order artifact,
> not an invention, and the row is classified on the structural match instead.

## Group C — the one hallucination. THIS IS THE ROW THAT MATTERS. (1 row)

**Row C1 — page 5, indicator, code `SS.CI.PK3`**

> Detected title: *"Recognize and resolve conflicts with peers with adult guidance."*

**The evidence is structural, not a text search.** The detector emitted **two**
elements carrying the code `SS.CI.PK3`:

| | Title | `source_text` |
|---|---|---|
| matched (correct) | …with peers **in an age-appropriate manner.** | complete: `SS.CI.PK3. Recognize\nand resolve conflicts with\npeers in an age-appropriate\nmanner.` |
| this row (defect) | …with peers **with adult guidance.** | **truncated**: `SS.CI.PK3. Recognize\nand resolve conflicts with` |

The phrase **"with adult guidance" occurs 0 times** in the NV extraction. The twin's
`source_text` stops mid-sentence and the title continues past it with text that is not
on the page. The trigger is visible in the extraction — p5 is a multi-column table
whose reading order interleaves columns:

> `SS.CI.PK3. Recognize Make connections to children's name writing as their
> signature.* conflict. and resolve conflicts with Sing songs and c…`

This is the defect CLAUDE.md already documents; it reproduced on current code.

**What to check on page 5 of the PDF:** that there is exactly **one** `SS.CI.PK3`
indicator, and that its text ends *"in an age-appropriate manner"* — with no variant
anywhere reading *"with adult guidance"*.

| # | Page | Level | Code | My verdict | Your call |
|---|---|---|---|---|---|
| C1 | 5 | indicator | `SS.CI.PK3` | **hallucinated** | |

## If you disagree with C1

If *"with adult guidance"* does appear on the page, then NV has **0 hallucinations**,
verified precision becomes **53/53 = 1.000**, and the CLAUDE.md note describing this as
a fabricated tail needs correcting. Tell me either way — a null result here is just as
useful and I'd rather correct the doc than carry a wrong claim into the paper.


</details>
