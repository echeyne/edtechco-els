# KY false-positive audit — sign-off sheet

**You are the annotator of record.** The paper will say:

> *all unmatched in-scope detections of the recorded run were manually audited by the author*

That sentence is **not true for KY until you sign this**, and KY's verified precision **1.0** is not quotable before then. Every verdict below carries `verified_by: "claude-first-pass-UNSIGNED"`.

## ✅ No candidate hallucinations in this state

All **0** unmatched detections classify as real document content. There is **no row here needing the deep scrutiny** that Nevada's `SS.CI.PK3` required — no title in this state failed the in-order reconstruction test.

So verified precision is **44/44 = 1.0**: signing this sheet asserts that the rows below are real, not that any of them is a defect.

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

- The detector emitted **44** in-scope elements for KY.
- **44** matched a golden entry and are not in question.
- The **0** rows below are the leftovers. You are ruling on these 0 only.

Verified precision = (in-scope detections − hallucinations) / in-scope detections. With 0 hallucination(s) that is **44/44 = 1.0**.

⚠️ **Do not judge a row by searching the extraction for its title.** This document's layout breaks titles across lines and columns, so real text often does not appear as one contiguous string. That is what Group C is about, and it is why a plain substring test is not the instrument here.

## If you disagree

If any row above is in fact **not** in the document, tell me which and KY's verified precision drops by 0.0227 per row. A null result is just as useful — I would rather correct the analysis than carry a wrong claim into the paper.
