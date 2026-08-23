# NV false-positive audit — sign-off sheet (re-record, 7 verdicts)

> ## ✅ SIGNED 2026-08-23 by Emily Cheyne — 0 verdicts changed.
>
> NV verified precision **0.9811 (52/53)** is now quotable, and the paper's
> methodology sentence *"all unmatched in-scope detections of the recorded run
> were manually audited by the author"* is TRUE FOR NEVADA. Kentucky needed no
> audit (exhaustive golden, zero unmatched detections).
>
> ⚠️ Still NOT true for the golden four — Task 1b owes 156 verdicts for
> AZ/CA/CO/TX. Until those are done the sentence must be scoped to the held-out
> states, or the paper overclaims.
>
> *(Date corrected from a slip reading `08-23-2023`; this audit is of a run
> dated 2026-08-22, so 2023 is not a possible signing date.)*

**You are the annotator of record.** The paper will say:

> *all unmatched in-scope detections of the recorded run were manually audited by the author*

That sentence is **not true until you sign this**, and NV's verified precision
**0.9811** is not quotable before then. Every verdict below currently carries
`verified_by: "claude-first-pass-UNSIGNED"` in `heldout_evidence.json`.

⚠️ **This supersedes `paper/results/task2_20260816/nv_fp_audit_signoff.md`, which
was built for the OLD 12-verdict audit against the 41-element golden. Do not sign
that one.** Your exhaustive pass took the golden to 46 elements, which annotated
5 of the previous leftovers; the audit is now 7 rows, and the
`real_unannotated` bucket is empty.

## How to sign off

1. Open `standards/nevada_ses_standards_2025*.pdf` (the 15pp trimmed subset).
2. Work the two groups below. **Group A is mechanical — spot-checking two of the
   six is enough. Group B is the one row that actually matters.**
3. Write `AGREE`, or the corrected verdict, in the **Your call** column.
4. Fill the block and tell Claude, who will fold the verdicts into
   `heldout_evidence.json`, replacing `claude-first-pass-UNSIGNED`.

```
ANNOTATOR:        Emily Cheyne
DATE:             2026-08-23
VERDICTS CHANGED: 0
SIGNED:           Emily Cheyne
```

## Scope — what you are and are not signing

- The detector emitted **53** in-scope elements for NV.
- **46** matched a golden entry and are not in question.
- The **7** rows below are the leftovers. You are ruling on these 7 only.
- **Kentucky needs no sign-off**: its golden is exhaustive (44 golden vs 44
  in-scope) and there were zero unmatched detections, so there is nothing to
  audit.

Verified precision = (in-scope detections − hallucinations) / in-scope
detections. With one hallucination that is **52/53 = 0.9811**. Every row you move
into or out of the `hallucinated` bucket moves that number by ~0.019.

⚠️ **Before you use the "does this text appear in the document?" test, read this.**
NV pages 5 and 10 are multi-column tables that flatten into *interleaved* reading
order. Correct text therefore often does **not** appear as a contiguous string in
the extraction. In the row that matters below, the *true* indicator text scores
zero contiguous matches too. Judge by the reconstructed column, not by a plain
substring search — otherwise correct rows look fabricated.

## Group A — correct second detections of a reprinted heading (6 rows)

**Why I'm confident:** NV reprints its `<Domain> Standard N:` headings on a
second page spread (the "The `<Domain>` Standards include:" listing pages). Each
row below is a re-detection of a heading that ALSO matched a golden entry
elsewhere — so the element is real document content, printed twice, detected
twice. The golden holds one entry per element, which is why the second copy has
nothing to match against. Five of the six titles are contiguous in the
extraction.

**What to check:** confirm the heading genuinely appears on the cited page as
well as its first location. Spot-checking two of the six is enough.

| # | Page | Level | Document code | Title | My verdict | Your call |
|---|---|---|---|---|---|---|
| A1 | 5 | strand | `Social Studies Standard 2` | Demonstrate a basic understanding of roles, rights, and re | real, repeat | AGREE |
| A2 | 6 | strand | `Social Studies Standard 3` | Demonstrate knowledge of the relationship between people a | real, repeat | AGREE |
| A3 | 10 | strand | `Science Standard 1` | Demonstrate the ability to use senses and tools to explore | real, repeat | AGREE |
| A4 | 10 | sub_strand | `S.EO` | Exploration, Observation, and Hypotheses | real, repeat | AGREE |
| A5 | 10 | strand | `Science Standard 2` | Demonstrate the ability to use information gathered in dif | real, repeat | AGREE |
| A6 | 15 | strand | `Technology Standard 2` | Use technology for communication and to gather and share i | real, repeat | AGREE |

> **Note on A4 (`S.EO`, page 10).** This is the one row whose title is flagged
> `title_contiguous_in_extraction: false`. That is the column-interleaving
> artifact described above, not evidence of fabrication — page 10 interleaves the
> sub_strand caption with an adjacent column. It is still classified real. If you
> want one extra check beyond the two spot-checks, make it this one.

## Group B — the one hallucination. THIS IS THE ROW THAT MATTERS. (1 row)

**Row B1 — page 5, indicator, code `SS.CI.PK3`**

> *"Recognize and resolve conflicts with peers **with adult guidance**."*

**The evidence is structural AND textual, and I verified it directly against
`outputs/08-22-26-4/NV-extraction.json` this run.**

1. **The phrase "with adult guidance" occurs 0 times in the entire NV
   extraction.** Not once, on any page.
2. **`SS.CI.PK3` appears in exactly ONE extraction block** — index 218, page 5.
   The document prints one such indicator, not two.
3. **Its true text reconstructs from the indicator column** — blocks 218, 221,
   223, 226, reading past the interposed activities column:

   | block | text |
   |---|---|
   | [218] | `SS.CI.PK3. Recognize` |
   | [221] | `and resolve conflicts with` |
   | [223] | `peers in an age-appropriate` |
   | [226] | `manner.` |

   → **"SS.CI.PK3. Recognize and resolve conflicts with peers in an
   age-appropriate manner."**

   The blocks interleaved between those ([219], [222], [224], [227]) belong to
   the adjacent activities column — *"Make connections to children's name writing
   as their signature."*, *"Sing songs and chants…"*, *"Tell a peer that they will
   share a toy when they"*, *"are finished with it."*

So the detector produced a second `SS.CI.PK3` whose `source_text` is a truncated
prefix of the real one and whose title carries a **fabricated tail**. This matches
CLAUDE.md's standing diagnosis of this element exactly.

**What to check on page 5 of the PDF:** find `SS.CI.PK3`. Confirm (a) there is
exactly one, and (b) it ends **"in an age-appropriate manner"**, with nothing
anywhere reading **"with adult guidance"**.

| # | Page | Level | Code | My verdict | Your call |
|---|---|---|---|---|---|
| B1 | 5 | indicator | `SS.CI.PK3` | **hallucinated** | AGREE |

## If you disagree with B1

If page 5 does print a second `SS.CI.PK3` reading "with adult guidance", then NV
has **0 hallucinations** and verified precision becomes **53/53 = 1.000**. That
would also mean the extraction is dropping text the PDF contains, which is a
finding about the *extractor*, not the detector — and it would require correcting
CLAUDE.md, which currently documents this element as a known detector
hallucination.

A null result here is just as useful, and I'd rather correct the doc than carry a
wrong claim into the paper.
