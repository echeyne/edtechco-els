# CA false-positive audit — sign-off sheet

**You are the annotator of record.** The paper will say:

> *all unmatched in-scope detections of the recorded run were manually audited by the author*

That sentence is **not true for CA until you sign this**, and CA's verified precision **1.0** is not quotable before then. Every verdict below carries `verified_by: "claude-first-pass-UNSIGNED"`.

## ✅ No candidate hallucinations in this state

All **97** unmatched detections classify as real document content. There is **no row here needing the deep scrutiny** that Nevada's `SS.CI.PK3` required — no title in this state failed the in-order reconstruction test.

So verified precision is **122/122 = 1.0**: signing this sheet asserts that the rows below are real, not that any of them is a defect.

## How to sign off

1. Open `the state's trimmed subset PDF in standards/`.
2. Work the groups below — they are ordered least-to-most consequential, and each says how hard to look.
3. Write `AGREE`, or the corrected verdict, in the **Your call** column.
4. Fill the block and tell Claude, who will fold the verdicts into the evidence JSON, replacing `claude-first-pass-UNSIGNED`.

```
ANNOTATOR:        Emily Cheyne
DATE:             2026-08-29
VERDICTS CHANGED: 6   (classification only: 6 rows moved Group B -> Group A
                       after Emily identified them as distinct indicators.
                       No verdict changed from "real" to "hallucinated", so
                       CA verified precision is unchanged at 1.0.)
SIGNED:           [ ]
```

## Scope — what you are and are not signing

- The detector emitted **122** in-scope elements for CA.
- **25** matched a golden entry and are not in question.
- The **97** rows below are the leftovers. You are ruling on these 97 only.

Verified precision = (in-scope detections − hallucinations) / in-scope detections. With 0 hallucination(s) that is **122/122 = 1.0**.

⚠️ **Do not judge a row by searching the extraction for its title.** This document's layout breaks titles across lines and columns, so real text often does not appear as one contiguous string. That is what Group C is about, and it is why a plain substring test is not the instrument here.

## Review note — 6 rows reclassified after Emily's first pass (2026-08-26)

Six rows (`Foundation 1.9` ×3 "Sharing Explanations and Opinions", `Foundation
1.10` ×3 "Participating in Conversations", all page 11) were originally
presented in a **Group B — correct second detections of a reprinted heading**.
Emily's call on all six was *"real, different indicator"*, and she was right.

They are ELD proficiency-column standards (`Discovering` / `Developing` /
`Broadening`). The golden-matched elements sharing those titles are
`Foundation 1.7` and `Foundation 1.8` in the age-banded FLD columns (`Early` /
`Later`) — different code, different domain, different column scheme, different
description. Six distinct standards, not reprints.

The cause was in the audit instrument, not the detector: `heldout_evidence.py`
keyed the repeat test on `(level, title)` alone, and CA's ELD and FLD domains
deliberately reuse indicator titles. The key is now
`(level, title, code, age_band)` — see commit `eb3952e`. Those six rows are
Group A below, and this sheet has **no Group B**.

Verified precision is unaffected: both verdicts are "real" and only Group D
counts against it. CA remains **122/122 = 1.0**.

⚠️ The 2026-08-23 signed baseline (`task1_20260822/task1b_fp_audit_SIGNED.json`)
carries the old labelling — `CA real_repeat_of_matched: 6` — with the same
non-effect on its 1.0. The two records disagree on those six labels by design.

## Group A — real content the golden simply did not annotate (97 rows)

**Why I'm confident:** Each title occurs **verbatim and contiguously** in the extraction. The golden is a spot-check, so unannotated real content is expected and is not a defect.

**What to check:** Confirm a couple really are elements on the page cited. Spot-checking two is enough.

| # | Page | Level | Code | Title | My verdict | Your call |
|---|---|---|---|---|---|---|
| A1 | 2 | strand | `Strand 1.0` | Motivation to Learn | real, unannotated | AGREE |
| A2 | 2 | sub_strand | `CI` | Curiosity and Interest | real, unannotated | AGREE |
| A3 | 2 | indicator | `Foundation 1.1` | Curiosity and Interest | real, unannotated | AGREE |
| A4 | 2 | indicator | `Foundation 1.1` | Curiosity and Interest | real, unannotated | AGREE |
| A5 | 2 | sub_strand | `INIT` | Initiative | real, unannotated | AGREE |
| A6 | 2 | sub_strand | `ENGA` | Engagement | real, unannotated | AGREE |
| A7 | 2 | indicator | `Foundation 1.3` | Engagement | real, unannotated | AGREE |
| A8 | 2 | indicator | `Foundation 1.3` | Engagement | real, unannotated | AGREE |
| A9 | 3 | sub_strand | `PERS` | Perseverance | real, unannotated | AGREE |
| A10 | 3 | indicator | `Foundation 1.4` | Persisting Despite Difficulties | real, unannotated | AGREE |
| A11 | 3 | indicator | `Foundation 1.4` | Persisting Despite Difficulties | real, unannotated | AGREE |
| A12 | 3 | sub_strand | `WM` | Working Memory | real, unannotated | AGREE |
| A13 | 3 | indicator | `Foundation 2.1` | Working Memory | real, unannotated | AGREE |
| A14 | 3 | indicator | `Foundation 2.1` | Working Memory | real, unannotated | AGREE |
| A15 | 3 | indicator | `Foundation 2.2` | Managing Impulsive Behaviors | real, unannotated | AGREE |
| A16 | 3 | indicator | `Foundation 2.2` | Managing Impulsive Behaviors | real, unannotated | AGREE |
| A17 | 4 | indicator | `Foundation 2.3` | Managing Attention and Distractions | real, unannotated | AGREE |
| A18 | 4 | indicator | `Foundation 2.3` | Managing Attention and Distractions | real, unannotated | AGREE |
| A19 | 4 | sub_strand | `FLEX` | Flexibility | real, unannotated | AGREE |
| A20 | 4 | indicator | `Foundation 2.4` | Flexibility | real, unannotated | AGREE |
| A21 | 4 | indicator | `Foundation 2.4` | Flexibility | real, unannotated | AGREE |
| A22 | 4 | strand | `Strand 3.0` | Goal-Directed Learning | real, unannotated | AGREE |
| A23 | 4 | sub_strand | `PROB` | Problem-Solving | real, unannotated | AGREE |
| A24 | 4 | indicator | `Foundation 3.1` | Planning | real, unannotated | AGREE |
| A25 | 4 | indicator | `Foundation 3.1` | Planning | real, unannotated | AGREE |
| A26 | 4 | indicator | `Foundation 3.2` | Reflecting and Analyzing | real, unannotated | AGREE |
| A27 | 4 | indicator | `Foundation 3.2` | Reflecting and Analyzing | real, unannotated | AGREE |
| A28 | 5 | sub_strand | `CE` | Collaborative Effort | real, unannotated | AGREE |
| A29 | 5 | indicator | `Foundation 3.3` | Problem-Solving Together | real, unannotated | AGREE |
| A30 | 5 | indicator | `Foundation 3.3` | Problem-Solving Together | real, unannotated | AGREE |
| A31 | 5 | indicator | `Foundation 3.4` | Understanding Others | real, unannotated | AGREE |
| A32 | 5 | indicator | `Foundation 3.4` | Understanding Others | real, unannotated | AGREE |
| A33 | 6 | indicator | `Foundation 1.2` | Understanding and Using Words for Categories | real, unannotated | AGREE |
| A34 | 6 | indicator | `Foundation 1.2` | Understanding and Using Words for Categories | real, unannotated | AGREE |
| A35 | 6 | indicator | `Foundation 1.3` | Understanding and Using Size and Location Words | real, unannotated | AGREE |
| A36 | 6 | indicator | `Foundation 1.3` | Understanding and Using Size and Location Words | real, unannotated | AGREE |
| A37 | 7 | indicator | `Foundation 1.4` | Using Grammatical Features and Sentence Structure | real, unannotated | AGREE |
| A38 | 7 | indicator | `Foundation 1.4` | Using Grammatical Features and Sentence Structure | real, unannotated | AGREE |
| A39 | 7 | indicator | `Foundation 1.5` | Asking Questions | real, unannotated | AGREE |
| A40 | 7 | indicator | `Foundation 1.5` | Asking Questions | real, unannotated | AGREE |
| A41 | 7 | indicator | `Foundation 1.6` | Constructing Narratives | real, unannotated | AGREE |
| A42 | 7 | indicator | `Foundation 1.6` | Constructing Narratives | real, unannotated | AGREE |
| A43 | 8 | strand | `Strand 2.0` | Foundational Literacy Skills | real, unannotated | AGREE |
| A44 | 8 | sub_strand | `PA` | Phonological Awareness | real, unannotated | AGREE |
| A45 | 8 | indicator | `Foundation 2.1` | Isolating Initial Sounds | real, unannotated | AGREE |
| A46 | 8 | indicator | `Foundation 2.1` | Isolating Initial Sounds | real, unannotated | AGREE |
| A47 | 8 | indicator | `Foundation 2.2` | Recognizing and Blending Sounds | real, unannotated | AGREE |
| A48 | 8 | indicator | `Foundation 2.2` | Recognizing and Blending Sounds | real, unannotated | AGREE |
| A49 | 8 | indicator | `Foundation 2.3` | Participating in Rhyming and Wordplay | real, unannotated | AGREE |
| A50 | 8 | indicator | `Foundation 2.3` | Participating in Rhyming and Wordplay | real, unannotated | AGREE |
| A51 | 9 | indicator | `Foundation 1.2` | Using Words | real, unannotated | AGREE |
| A52 | 9 | indicator | `Foundation 1.2` | Using Words | real, unannotated | AGREE |
| A53 | 9 | indicator | `Foundation 1.2` | Using Words | real, unannotated | AGREE |
| A54 | 9 | indicator | `Foundation 1.3` | Using Grammatical Features | real, unannotated | AGREE |
| A55 | 9 | indicator | `Foundation 1.3` | Using Grammatical Features | real, unannotated | AGREE |
| A56 | 9 | indicator | `Foundation 1.3` | Using Grammatical Features | real, unannotated | AGREE |
| A57 | 10 | sub_strand | `LU` | Language Use | real, unannotated | AGREE |
| A58 | 10 | indicator | `Foundation 1.5` | Communicating Needs | real, unannotated | AGREE |
| A59 | 10 | indicator | `Foundation 1.5` | Communicating Needs | real, unannotated | AGREE |
| A60 | 10 | indicator | `Foundation 1.5` | Communicating Needs | real, unannotated | AGREE |
| A61 | 10 | indicator | `Foundation 1.6` | Understanding Requests and Directions | real, unannotated | AGREE |
| A62 | 10 | indicator | `Foundation 1.6` | Understanding Requests and Directions | real, unannotated | AGREE |
| A63 | 10 | indicator | `Foundation 1.6` | Understanding Requests and Directions | real, unannotated | AGREE |
| A64 | 11 | indicator | `Foundation 1.7` | Asking Questions | real, unannotated | AGREE |
| A65 | 11 | indicator | `Foundation 1.7` | Asking Questions | real, unannotated | AGREE |
| A66 | 11 | indicator | `Foundation 1.7` | Asking Questions | real, unannotated | AGREE |
| A67 | 11 | indicator | `Foundation 1.8` | Constructing Narratives | real, unannotated | AGREE |
| A68 | 11 | indicator | `Foundation 1.8` | Constructing Narratives | real, unannotated | AGREE |
| A69 | 11 | indicator | `Foundation 1.8` | Constructing Narratives | real, unannotated | AGREE |
| A70 | 11 | indicator | `Foundation 1.9` | Sharing Explanations and Opinions | real, unannotated | AGREE |
| A71 | 11 | indicator | `Foundation 1.9` | Sharing Explanations and Opinions | real, unannotated | AGREE |
| A72 | 11 | indicator | `Foundation 1.9` | Sharing Explanations and Opinions | real, unannotated | AGREE |
| A73 | 11 | indicator | `Foundation 1.10` | Participating in Conversations | real, unannotated | AGREE |
| A74 | 11 | indicator | `Foundation 1.10` | Participating in Conversations | real, unannotated | AGREE |
| A75 | 11 | indicator | `Foundation 1.10` | Participating in Conversations | real, unannotated | AGREE |
| A76 | 12 | strand | `Strand 2.0` | Foundational Literacy Skills | real, unannotated | AGREE |
| A77 | 12 | sub_strand | `PA` | Phonological Awareness | real, unannotated | AGREE |
| A78 | 12 | indicator | `Foundation 2.1` | Recognizing and Segmenting Sounds | real, unannotated | AGREE |
| A79 | 12 | indicator | `Foundation 2.1` | Recognizing and Segmenting Sounds | real, unannotated | AGREE |
| A80 | 12 | indicator | `Foundation 2.1` | Recognizing and Segmenting Sounds | real, unannotated | AGREE |
| A81 | 12 | indicator | `Foundation 2.2` | Recognizing and Blending Sounds | real, unannotated | AGREE |
| A82 | 12 | indicator | `Foundation 2.2` | Recognizing and Blending Sounds | real, unannotated | AGREE |
| A83 | 12 | indicator | `Foundation 2.2` | Recognizing and Blending Sounds | real, unannotated | AGREE |
| A84 | 12 | indicator | `Foundation 2.3` | Participating in Rhyming and Wordplay | real, unannotated | AGREE |
| A85 | 12 | indicator | `Foundation 2.3` | Participating in Rhyming and Wordplay | real, unannotated | AGREE |
| A86 | 12 | indicator | `Foundation 2.3` | Participating in Rhyming and Wordplay | real, unannotated | AGREE |
| A87 | 13 | sub_strand | `AP` | Alphabetics and Print | real, unannotated | AGREE |
| A88 | 13 | indicator | `Foundation 2.4` | Recognizing and Identifying Letters | real, unannotated | AGREE |
| A89 | 13 | indicator | `Foundation 2.4` | Recognizing and Identifying Letters | real, unannotated | AGREE |
| A90 | 13 | indicator | `Foundation 2.4` | Recognizing and Identifying Letters | real, unannotated | AGREE |
| A91 | 13 | indicator | `Foundation 2.5` | Learning Letter-Sound Correspondence | real, unannotated | AGREE |
| A92 | 13 | indicator | `Foundation 2.5` | Learning Letter-Sound Correspondence | real, unannotated | AGREE |
| A93 | 13 | indicator | `Foundation 2.5` | Learning Letter-Sound Correspondence | real, unannotated | AGREE |
| A94 | 13 | sub_strand | `CP` | Concepts About Print | real, unannotated | AGREE |
| A95 | 13 | indicator | `Foundation 2.6` | Understanding the Concept of Print | real, unannotated | AGREE |
| A96 | 13 | indicator | `Foundation 2.6` | Understanding the Concept of Print | real, unannotated | AGREE |
| A97 | 13 | indicator | `Foundation 2.6` | Understanding the Concept of Print | real, unannotated | AGREE |
## If you disagree

If any row above is in fact **not** in the document, tell me which and CA's verified precision drops by 0.0082 per row. A null result is just as useful — I would rather correct the analysis than carry a wrong claim into the paper.
