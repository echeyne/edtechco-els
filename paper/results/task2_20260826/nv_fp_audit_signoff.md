# NV false-positive audit — sign-off sheet

**You are the annotator of record.** The paper will say:

> *all unmatched in-scope detections of the recorded run were manually audited by the author*

That sentence is **not true for NV until you sign this**, and NV's verified precision **0.9808** is not quotable before then. Every verdict below carries `verified_by: "claude-first-pass-UNSIGNED"`.

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

- The detector emitted **52** in-scope elements for NV.
- **46** matched a golden entry and are not in question.
- The **6** rows below are the leftovers. You are ruling on these 6 only.

Verified precision = (in-scope detections − hallucinations) / in-scope detections. With 1 hallucination(s) that is **51/52 = 0.9808**.

⚠️ **Do not judge a row by searching the extraction for its title.** This document's layout breaks titles across lines and columns, so real text often does not appear as one contiguous string. That is what Group C is about, and it is why a plain substring test is not the instrument here.

## Group B — correct second detections of a reprinted heading (5 rows)

**Why I'm confident:** Verified **structurally**: each row has the same level and title as an element that already matched a golden entry. The document reprints the heading; the detector is right to emit it again.

**What to check:** Confirm the heading really does appear on the cited page as well as its first location. Spot-checking two is enough.

| # | Page | Level | Code | Title | My verdict | Your call |
|---|---|---|---|---|---|---|
| B1 | 5 | strand | `Social Studies Standard 2` | Demonstrate a basic understanding of roles, rights, and re | real, repeat | AGREE |
| B2 | 6 | strand | `Social Studies Standard 3` | Demonstrate knowledge of the relationship between people a | real, repeat | AGREE |
| B3 | 10 | sub_strand | `S.EO` | Exploration, Observation, and Hypotheses | real, repeat | AGREE |
| B4 | 10 | strand | `Science Standard 2` | Demonstrate the ability to use information gathered in dif | real, repeat | AGREE |
| B5 | 15 | strand | `Technology Standard 2` | Use technology for communication and to gather and share i | real, repeat | AGREE |

## Group D — candidate hallucinations — THESE ARE THE ROWS THAT MATTER (1 rows)

**Why I'm confident:** Not a repeat, not contiguous, and the spans **cannot** be reconstructed in reading order anywhere in the extraction. This is the signature of an invented tail.

**What to check:** Open the PDF at the cited page and confirm the text really is absent.


**Row D1 — page 5, indicator, code `SS.CI.PK3`**

> *"Recognize and resolve conflicts with peers with adult guidance."*

Another element carries the **same code**:

| | title |
|---|---|
| matched (correct) | Recognize and resolve conflicts with peers in an age-appropriate manner. |
| this row | Recognize and resolve conflicts with peers with adult guidance. |

- Diverging text: **"with adult guidance."**
- That phrase occurs **0 times** in the extraction.
- This row's `source_text` is a truncated prefix of the twin's: **True**

**What to check on page 5:** confirm this text is genuinely absent from the document.

| # | Page | Level | Code | My verdict | Your call |
|---|---|---|---|---|---|
| D1 | 5 | indicator | `SS.CI.PK3` | **hallucinated** | AGREE |

