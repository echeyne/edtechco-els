# TX false-positive audit — sign-off sheet

**You are the annotator of record.** The paper will say:

> *all unmatched in-scope detections of the recorded run were manually audited by the author*

That sentence is **not true for TX until you sign this**, and TX's verified precision **1.0** is not quotable before then. Every verdict below carries `verified_by: "claude-first-pass-UNSIGNED"`.

## ✅ No candidate hallucinations in this state

All **17** unmatched detections classify as real document content. There is **no row here needing the deep scrutiny** that Nevada's `SS.CI.PK3` required — no title in this state failed the in-order reconstruction test.

So verified precision is **25/25 = 1.0**: signing this sheet asserts that the rows below are real, not that any of them is a defect.

## How to sign off

1. Open `the state's trimmed subset PDF in standards/`.
2. Work the groups below — they are ordered least-to-most consequential, and each says how hard to look.
3. Write `AGREE`, or the corrected verdict, in the **Your call** column.
4. Fill the block and tell Claude, who will fold the verdicts into the evidence JSON, replacing `claude-first-pass-UNSIGNED`.

```
ANNOTATOR:        Emily Cheyne
DATE:             2026-08-29
VERDICTS CHANGED: 0
SIGNED:           Emily Cheyne
```

## Scope — what you are and are not signing

- The detector emitted **25** in-scope elements for TX.
- **8** matched a golden entry and are not in question.
- The **17** rows below are the leftovers. You are ruling on these 17 only.

Verified precision = (in-scope detections − hallucinations) / in-scope detections. With 0 hallucination(s) that is **25/25 = 1.0**.

⚠️ **Do not judge a row by searching the extraction for its title.** This document's layout breaks titles across lines and columns, so real text often does not appear as one contiguous string. That is what Group C is about, and it is why a plain substring test is not the instrument here.

## Group A — real content the golden simply did not annotate (5 rows)

**Why I'm confident:** Each title occurs **verbatim and contiguously** in the extraction. The golden is a spot-check, so unannotated real content is expected and is not a defect.

**What to check:** Confirm a couple really are elements on the page cited. Spot-checking two is enough.

| # | Page | Level | Code | Title | My verdict | Your call |
|---|---|---|---|---|---|---|
| A1 | 4 | sub_strand | `1` | Behavior Control | real, unannotated | AGREE |
| A2 | 4 | indicator | `PK4.I.B.1.a` | Child follows classroom rules and routines with occasional | real, unannotated | AGREE |
| A3 | 5 | indicator | `PK3.I.B.1.b` | Child takes care of and manages classroom materials with a | real, unannotated | AGREE |
| A4 | 5 | indicator | `PK4.I.B.1.b` | Child takes care of and manages classroom materials. | real, unannotated | AGREE |
| A5 | 6 | indicator | `PK3.I.B.2.c` | Child manages intensity of emotions with adult assistance. | real, unannotated | AGREE |

## Group C — real titles split across lines or columns (12 rows)

**Why I'm confident:** The title is **not** a contiguous string in the extraction, but every span reconstructs **in reading order** within a small window. That is the signature of a real title broken by a line break or an interleaved neighbouring column — an invented tail does not reconstruct in order.

⚠️ These rows would have been reported as `hallucinated` before 2026-08-23. They are not. Do not read the old label as a defect count.

**What to check:** Skim the window sizes below — all small means all local. Open the two largest against the PDF if you want a check.

| # | Page | Level | Code | Title | In-order window | My verdict | Your call |
|---|---|---|---|---|---|---|---|
| C1 | 2 | indicator | `PK3.I.A.1` | Child is building competence in controlling own body movem | 111 chars | real, split | AGREE |
| C2 | 2 | indicator | `PK4.I.A.1` | Child is aware of where own body is in space and respects  | 109 chars | real, split | AGREE |
| C3 | 3 | indicator | `PK3.I.A.3` | Child begins to show awareness of own abilities. | 51 chars | real, split | AGREE |
| C4 | 3 | indicator | `PK4.I.A.3` | Child shows reasonable opinion of his own abilities and li | 115 chars | real, split | AGREE |
| C5 | 4 | indicator | `PK3.I.A.4` | Child shows initiative in trying new activities but may no | 148 chars | real, split | AGREE |
| C6 | 4 | indicator | `PK4.I.A.4` | Child shows initiative in trying new activities and demons | 196 chars | real, split | AGREE |
| C7 | 4 | indicator | `PK3.I.B.1.a` | Child follows simple rules and routines when assisted by a | 157 chars | real, split | AGREE |
| C8 | 5 | indicator | `PK3.I.B.1.c` | Child manages own behavior with adult guidance and assista | 109 chars | real, split | AGREE |
| C9 | 5 | indicator | `PK4.I.B.1.c` | Child regulates own behavior with occasional reminders or  | 124 chars | real, split | AGREE |
| C10 | 5 | indicator | `PK3.I.B.2.a` | Child recognizes and expresses a range of emotions. | 125 chars | real, split | AGREE |
| C11 | 5 | indicator | `PK4.I.B.2.a` | Child begins to understand the connection between emotions | 85 chars | real, split | AGREE |
| C12 | 6 | indicator | `PK4.I.B.2.c` | Child is able to manage intensity of emotions more consist | 182 chars | real, split | AGREE |

## If you disagree

If any row above is in fact **not** in the document, tell me which and TX's verified precision drops by 0.04 per row. A null result is just as useful — I would rather correct the analysis than carry a wrong claim into the paper.
