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
DATE:             ____-__-__
VERDICTS CHANGED: ____   (0 if you agree with all 97)
SIGNED:           [ ]
```

## Scope — what you are and are not signing

- The detector emitted **122** in-scope elements for CA.
- **25** matched a golden entry and are not in question.
- The **97** rows below are the leftovers. You are ruling on these 97 only.

Verified precision = (in-scope detections − hallucinations) / in-scope detections. With 0 hallucination(s) that is **122/122 = 1.0**.

⚠️ **Do not judge a row by searching the extraction for its title.** This document's layout breaks titles across lines and columns, so real text often does not appear as one contiguous string. That is what Group C is about, and it is why a plain substring test is not the instrument here.

## Group A — real content the golden simply did not annotate (91 rows)

**Why I'm confident:** Each title occurs **verbatim and contiguously** in the extraction. The golden is a spot-check, so unannotated real content is expected and is not a defect.

**What to check:** Confirm a couple really are elements on the page cited. Spot-checking two is enough.

| # | Page | Level | Code | Title | My verdict | Your call |
|---|---|---|---|---|---|---|
| A1 | 2 | strand | `Strand 1.0` | Motivation to Learn | real, unannotated | |
| A2 | 2 | sub_strand | `CI` | Curiosity and Interest | real, unannotated | |
| A3 | 2 | indicator | `Foundation 1.1` | Curiosity and Interest | real, unannotated | |
| A4 | 2 | indicator | `Foundation 1.1` | Curiosity and Interest | real, unannotated | |
| A5 | 2 | sub_strand | `INIT` | Initiative | real, unannotated | |
| A6 | 2 | sub_strand | `ENGA` | Engagement | real, unannotated | |
| A7 | 2 | indicator | `Foundation 1.3` | Engagement | real, unannotated | |
| A8 | 2 | indicator | `Foundation 1.3` | Engagement | real, unannotated | |
| A9 | 3 | sub_strand | `PERS` | Perseverance | real, unannotated | |
| A10 | 3 | indicator | `Foundation 1.4` | Persisting Despite Difficulties | real, unannotated | |
| A11 | 3 | indicator | `Foundation 1.4` | Persisting Despite Difficulties | real, unannotated | |
| A12 | 3 | sub_strand | `WM` | Working Memory | real, unannotated | |
| A13 | 3 | indicator | `Foundation 2.1` | Working Memory | real, unannotated | |
| A14 | 3 | indicator | `Foundation 2.1` | Working Memory | real, unannotated | |
| A15 | 3 | indicator | `Foundation 2.2` | Managing Impulsive Behaviors | real, unannotated | |
| A16 | 3 | indicator | `Foundation 2.2` | Managing Impulsive Behaviors | real, unannotated | |
| A17 | 4 | indicator | `Foundation 2.3` | Managing Attention and Distractions | real, unannotated | |
| A18 | 4 | indicator | `Foundation 2.3` | Managing Attention and Distractions | real, unannotated | |
| A19 | 4 | sub_strand | `FLEX` | Flexibility | real, unannotated | |
| A20 | 4 | indicator | `Foundation 2.4` | Flexibility | real, unannotated | |
| A21 | 4 | indicator | `Foundation 2.4` | Flexibility | real, unannotated | |
| A22 | 4 | strand | `Strand 3.0` | Goal-Directed Learning | real, unannotated | |
| A23 | 4 | sub_strand | `PROB` | Problem-Solving | real, unannotated | |
| A24 | 4 | indicator | `Foundation 3.1` | Planning | real, unannotated | |
| A25 | 4 | indicator | `Foundation 3.1` | Planning | real, unannotated | |
| A26 | 4 | indicator | `Foundation 3.2` | Reflecting and Analyzing | real, unannotated | |
| A27 | 4 | indicator | `Foundation 3.2` | Reflecting and Analyzing | real, unannotated | |
| A28 | 5 | sub_strand | `CE` | Collaborative Effort | real, unannotated | |
| A29 | 5 | indicator | `Foundation 3.3` | Problem-Solving Together | real, unannotated | |
| A30 | 5 | indicator | `Foundation 3.3` | Problem-Solving Together | real, unannotated | |
| A31 | 5 | indicator | `Foundation 3.4` | Understanding Others | real, unannotated | |
| A32 | 5 | indicator | `Foundation 3.4` | Understanding Others | real, unannotated | |
| A33 | 6 | indicator | `Foundation 1.2` | Understanding and Using Words for Categories | real, unannotated | |
| A34 | 6 | indicator | `Foundation 1.2` | Understanding and Using Words for Categories | real, unannotated | |
| A35 | 6 | indicator | `Foundation 1.3` | Understanding and Using Size and Location Words | real, unannotated | |
| A36 | 6 | indicator | `Foundation 1.3` | Understanding and Using Size and Location Words | real, unannotated | |
| A37 | 7 | indicator | `Foundation 1.4` | Using Grammatical Features and Sentence Structure | real, unannotated | |
| A38 | 7 | indicator | `Foundation 1.4` | Using Grammatical Features and Sentence Structure | real, unannotated | |
| A39 | 7 | indicator | `Foundation 1.5` | Asking Questions | real, unannotated | |
| A40 | 7 | indicator | `Foundation 1.5` | Asking Questions | real, unannotated | |
| A41 | 7 | indicator | `Foundation 1.6` | Constructing Narratives | real, unannotated | |
| A42 | 7 | indicator | `Foundation 1.6` | Constructing Narratives | real, unannotated | |
| A43 | 8 | strand | `Strand 2.0` | Foundational Literacy Skills | real, unannotated | |
| A44 | 8 | sub_strand | `PA` | Phonological Awareness | real, unannotated | |
| A45 | 8 | indicator | `Foundation 2.1` | Isolating Initial Sounds | real, unannotated | |
| A46 | 8 | indicator | `Foundation 2.1` | Isolating Initial Sounds | real, unannotated | |
| A47 | 8 | indicator | `Foundation 2.2` | Recognizing and Blending Sounds | real, unannotated | |
| A48 | 8 | indicator | `Foundation 2.2` | Recognizing and Blending Sounds | real, unannotated | |
| A49 | 8 | indicator | `Foundation 2.3` | Participating in Rhyming and Wordplay | real, unannotated | |
| A50 | 8 | indicator | `Foundation 2.3` | Participating in Rhyming and Wordplay | real, unannotated | |
| A51 | 9 | indicator | `Foundation 1.2` | Using Words | real, unannotated | |
| A52 | 9 | indicator | `Foundation 1.2` | Using Words | real, unannotated | |
| A53 | 9 | indicator | `Foundation 1.2` | Using Words | real, unannotated | |
| A54 | 9 | indicator | `Foundation 1.3` | Using Grammatical Features | real, unannotated | |
| A55 | 9 | indicator | `Foundation 1.3` | Using Grammatical Features | real, unannotated | |
| A56 | 9 | indicator | `Foundation 1.3` | Using Grammatical Features | real, unannotated | |
| A57 | 10 | sub_strand | `LU` | Language Use | real, unannotated | |
| A58 | 10 | indicator | `Foundation 1.5` | Communicating Needs | real, unannotated | |
| A59 | 10 | indicator | `Foundation 1.5` | Communicating Needs | real, unannotated | |
| A60 | 10 | indicator | `Foundation 1.5` | Communicating Needs | real, unannotated | |
| A61 | 10 | indicator | `Foundation 1.6` | Understanding Requests and Directions | real, unannotated | |
| A62 | 10 | indicator | `Foundation 1.6` | Understanding Requests and Directions | real, unannotated | |
| A63 | 10 | indicator | `Foundation 1.6` | Understanding Requests and Directions | real, unannotated | |
| A64 | 11 | indicator | `Foundation 1.7` | Asking Questions | real, unannotated | |
| A65 | 11 | indicator | `Foundation 1.7` | Asking Questions | real, unannotated | |
| A66 | 11 | indicator | `Foundation 1.7` | Asking Questions | real, unannotated | |
| A67 | 11 | indicator | `Foundation 1.8` | Constructing Narratives | real, unannotated | |
| A68 | 11 | indicator | `Foundation 1.8` | Constructing Narratives | real, unannotated | |
| A69 | 11 | indicator | `Foundation 1.8` | Constructing Narratives | real, unannotated | |
| A70 | 12 | strand | `Strand 2.0` | Foundational Literacy Skills | real, unannotated | |
| A71 | 12 | sub_strand | `PA` | Phonological Awareness | real, unannotated | |
| A72 | 12 | indicator | `Foundation 2.1` | Recognizing and Segmenting Sounds | real, unannotated | |
| A73 | 12 | indicator | `Foundation 2.1` | Recognizing and Segmenting Sounds | real, unannotated | |
| A74 | 12 | indicator | `Foundation 2.1` | Recognizing and Segmenting Sounds | real, unannotated | |
| A75 | 12 | indicator | `Foundation 2.2` | Recognizing and Blending Sounds | real, unannotated | |
| A76 | 12 | indicator | `Foundation 2.2` | Recognizing and Blending Sounds | real, unannotated | |
| A77 | 12 | indicator | `Foundation 2.2` | Recognizing and Blending Sounds | real, unannotated | |
| A78 | 12 | indicator | `Foundation 2.3` | Participating in Rhyming and Wordplay | real, unannotated | |
| A79 | 12 | indicator | `Foundation 2.3` | Participating in Rhyming and Wordplay | real, unannotated | |
| A80 | 12 | indicator | `Foundation 2.3` | Participating in Rhyming and Wordplay | real, unannotated | |
| A81 | 13 | sub_strand | `AP` | Alphabetics and Print | real, unannotated | |
| A82 | 13 | indicator | `Foundation 2.4` | Recognizing and Identifying Letters | real, unannotated | |
| A83 | 13 | indicator | `Foundation 2.4` | Recognizing and Identifying Letters | real, unannotated | |
| A84 | 13 | indicator | `Foundation 2.4` | Recognizing and Identifying Letters | real, unannotated | |
| A85 | 13 | indicator | `Foundation 2.5` | Learning Letter-Sound Correspondence | real, unannotated | |
| A86 | 13 | indicator | `Foundation 2.5` | Learning Letter-Sound Correspondence | real, unannotated | |
| A87 | 13 | indicator | `Foundation 2.5` | Learning Letter-Sound Correspondence | real, unannotated | |
| A88 | 13 | sub_strand | `CP` | Concepts About Print | real, unannotated | |
| A89 | 13 | indicator | `Foundation 2.6` | Understanding the Concept of Print | real, unannotated | |
| A90 | 13 | indicator | `Foundation 2.6` | Understanding the Concept of Print | real, unannotated | |
| A91 | 13 | indicator | `Foundation 2.6` | Understanding the Concept of Print | real, unannotated | |

## Group B — correct second detections of a reprinted heading (6 rows)

**Why I'm confident:** Verified **structurally**: each row has the same level and title as an element that already matched a golden entry. The document reprints the heading; the detector is right to emit it again.

**What to check:** Confirm the heading really does appear on the cited page as well as its first location. Spot-checking two is enough.

| # | Page | Level | Code | Title | My verdict | Your call |
|---|---|---|---|---|---|---|
| B1 | 11 | indicator | `Foundation 1.9` | Sharing Explanations and Opinions | real, repeat | |
| B2 | 11 | indicator | `Foundation 1.9` | Sharing Explanations and Opinions | real, repeat | |
| B3 | 11 | indicator | `Foundation 1.9` | Sharing Explanations and Opinions | real, repeat | |
| B4 | 11 | indicator | `Foundation 1.10` | Participating in Conversations | real, repeat | |
| B5 | 11 | indicator | `Foundation 1.10` | Participating in Conversations | real, repeat | |
| B6 | 11 | indicator | `Foundation 1.10` | Participating in Conversations | real, repeat | |

## If you disagree

If any row above is in fact **not** in the document, tell me which and CA's verified precision drops by 0.0082 per row. A null result is just as useful — I would rather correct the analysis than carry a wrong claim into the paper.
