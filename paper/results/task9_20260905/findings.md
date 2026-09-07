# Task 9 — quality at scale: the subset goldens graded inside the trimmed-tier run

**⚠️ STATUS: PROVISIONAL — one item remains.** The author is grading
`ground_truth_detector/KY.json` exhaustively against the PDF; nothing here may
be cited in `paper/sections/` until that is done and this measurement is re-run.

**The `age_band` verdict is CLOSED: `RUN`** (2026-09-06). The run
over-attributes, the golden is right and does not change, and this is reported
as a detector defect at scale. **No code change** — `code_version_hash` stays at
`14374dba` and no recorded result is invalidated.

**Colorado is NOT being annotated exhaustively** (decided 2026-09-06). Its
golden stays a seven-element spot check, its precision stays a coverage
artifact and is labelled as one, and it contributes the recall half of this
result only. Any earlier note in this directory proposing a CO annotation pass
is withdrawn.

Recorded 2026-09-05 at `code_version_hash` **`14374dba`**. No new annotation and
no new model call: this regrades the **existing** trimmed-tier run of 2026-08-29
(`full08292026`, Task 6) against the **existing** subset goldens.

## ⚠️ Correction, 2026-09-06 — the first version of this file was wrong

The first version reported **0 duplicates surviving the merge** and read
Kentucky's 11 unmatched detections as evidence that the golden was not
page-exhaustive. **Both conclusions are withdrawn.** The duplicate check was
keyed on `eval_detector._match_key`, which ends in `age_band` — and the
duplicates differ in exactly that field. Keying the audit on the field the
duplicates disagree about hid all eleven, in the direction that flatters the
system.

The corrected reading is simpler and is the one the assessment predicted:
**precision does drop at scale, and it drops because duplicates survive the
merge.** The generalizable lesson is in `duplicate_analysis`'s docstring — a
duplicate check must be keyed more loosely than the merge it audits, or it can
only ever confirm that merge's opinion of itself.

## Headline

| | KY | CO |
|---|---|---|
| golden elements | 44 | 7 |
| elements in the whole trimmed run | 329 | 300 |
| elements inside the graded page window | **55** | **61** |
| distinct elements in that window | **44** | **61** |
| **absent at scale** | **0** | **0** |
| **hallucination candidates** | **0** | **0** |
| **duplicates surviving the merge** | **11** | **0** |
| recall by level + title | **1.000** | **1.000** |
| headline recall (strict `_match_key`) | 0.545 | 0.857 |
| precision by level + title | **0.800** | not reported — coverage artifact |

## Finding 1 — nothing is lost at scale

Every one of Kentucky's 44 golden elements and every one of Colorado's 7 is
present in the trimmed run, on the mapped page, at the right level, with the
right title. The 6.5× (KY) and 4.1× (CO) increase in page count, and the move
from one detection batch to four, cost the detector **no element** and produced
**no hallucination**. That is the claim the paper was most exposed on, and it
holds.

## Finding 2 — precision drops at scale, and one cause explains all of it

Kentucky's 55 in-window detections are **44 distinct elements plus 11 duplicate
copies**. Precision is therefore 44/55 = **0.800**, and the entire 0.200
shortfall is duplication. Every one of the eleven is the same shape: one
element, on one page, emitted **twice** — once carrying
`age_band: "THREE AND FOUR YEAR OLDS"` and once carrying `null`.

| level | surplus copies |
|---|---|
| strand | 2 |
| sub_strand | 2 |
| indicator | 7 |

**`_dedup_elements` did not merge them because the two copies disagree on
`age_band`.** So this is not a merge that failed to run; it is a merge whose key
was defeated by an unstable field. Colorado, whose document has no age-band
column, shows **0** duplicates in the same measurement — which is what makes the
attribution to `age_band` rather than to chunking itself credible.

## Finding 3 — age-band attribution is unstable at scale, three ways in one document

The same instability drives the strict-recall figure. Across Kentucky's graded
window the run treats one document three different ways:

- **20** golden elements emitted **banded only** (golden says `null`) — these
  are the entire difference between strict recall 0.545 and 1.000;
- **11** emitted **twice**, once each way — Finding 2's duplicates;
- **13** emitted **null only**, agreeing with the golden.

And it is not a per-page decision: **5 of the 7 content pages emit both values**
(trimmed p4: 5 banded / 4 null; p22: 5 / 8; p15: 1 / 7). Document-wide the run
stamps the band on 152 of 329 elements. The subset run of the same document
emitted `null` for all 44.

This is the shape `models._blank_to_none` and `_canonicalize_code` exist to
absorb — one fact with two spellings — and per CLAUDE.md's standing argument it
is the shape a prompt rule can reduce but not drive to zero.

**⚠️ The verdict is open and is the author's.** `review/KY_age_band_review.md`
puts it three ways: the pages genuinely carry the band and the golden is wrong
(`GOLDEN`); the band belongs to some elements and not others and the run is
over-attributing (`RUN`); or the band is a property of the *page* and should
never have been inherited onto an element at all (`SCHEMA`). The third is the
most interesting and would make Finding 2 a schema finding rather than a
detector one.

## Finding 4 — the Kentucky golden is vindicated, and "detection-exhaustive" survives

The first version of this file suggested KY's golden might under-annotate.
**It does not.** All 11 unmatched detections are duplicates of elements the
golden already covers; **0** are unannotated content. Kentucky's golden accounts
for every *distinct* element the larger run finds on its pages, which is the
property the paper relies on, and it holds at 4 detection batches as well as at
1.

Two further scans on 2026-09-06 close the question completely: the union of
**all 13** KY detection files contains no `(level, title)` the golden lacks, and
no block of text on subset pages 2–8 (≥25 chars, page furniture excluded) is
unaccounted for by a golden title or description at ≥0.9 word coverage. **The
subset golden has no missing test cases.** The worklist sheet it used to
generate is therefore deleted; the author's exhaustive pass against the PDF
supersedes anything derivable from system output anyway.

## Colorado — the recall half, and deliberately only that

CO was added so the recall result would not rest on one document, and it does
that job: **0 absent, 0 duplicates, 0 hallucinations** across four detection
batches, on a document whose multi-column layout is the corpus's hardest.

It contributes **nothing to precision, by design**. Its golden is a 7-element
spot check, so 55 of 61 in-window detections are simply content it never
annotated (none of them duplicates, none ungrounded); its 0.098 precision
measures annotation coverage, not quality, and `scale_grade.py` labels it that
way in the output rather than letting a reader mistake it for a quality figure.

⚠️ **Do not report CO precision, and do not describe CO as exhaustive
anywhere.** An earlier version of this file proposed annotating its 10-page
window to make it a second precision-bearing state; **that is withdrawn**
(2026-09-06). Colorado's role in this task is recall and duplication only.

CO's single strict-recall miss is **not** a miss. `CO-STR-01` "Health, Safety
and Nutrition" was emitted as *"Health, Safety and Nutrition: The maintenance of
healthy and age appropriate physical…"* — found at the right level with the
description folded into `title`. Composition drift, reported in its own bucket,
and a second instance of the field-composition instability §6.3 documents.

## Finding 5 — the chain closes: age-band drift ends as fabricated primary keys

The parser counterpart of this task (`scale_grade_parser.py`,
`{KY,CO}_scale_grade_parser.json`) completes the causal chain.

Kentucky's trimmed run produces **214 standards with 214 distinct
`standard_id`s** — and **7 of them are duplicates**, pairs sharing parents and
indicator name, separated only by
`disambiguate_colliding_standards`' numeric last-resort suffix:
`US-KY-2021-AL.2.1.FNWUF` beside `US-KY-2021-AL.2.1.FNWUF.2`, same page, same
parents, same name. `.2` names a standard that does not exist.

⚠️ **"Distinct" is not "collision-free" here, and the difference matters.**
`grade_parser.id_collisions` runs *after* the resolver, so it reports zero by
construction; uniqueness at scale is achieved by **renaming** a collision, not
by the absence of one. Any claim built on that field must carry the duplicate
count beside it.

The chain, end to end:

1. the detector emits one element twice, once age-banded and once `null`
   (Finding 3);
2. `_dedup_elements` does not merge them, because its key includes `age_band`
   (Finding 2);
3. the parser canonicalizes both bands to the document's single band, at which
   point the two rows are identical and collide;
4. the resolver breaks the tie with `.2`, and a fabricated primary key reaches
   persistence.

**Colorado has 0 duplicates in 240 standards, and Colorado's document has no
age-band column.** That is the control, and it is what makes the attribution to
`age_band` a measurement rather than an assumption.

## Method, and the four things that would have made it lie

Deterministic throughout; no model call, no annotation.

**1. Page translation.** The goldens' `source_page` values are `_only_subset`
page numbers and the run's are `_trimmed` ones.
`paper/results/corpus_page_ranges.json` records the published page behind each
tier page, so composing one map with the inverse of the other is exact. KY
subset 1–8 → trimmed 1, 2, 3, 4, 5, 15, 21, 22; CO subset 1–10 → trimmed 1, 3,
4, 5, 6, 7, 8, 9, 11, 12. Confirmed empirically: every golden element that
matched did so on precisely its mapped page.

**2. Domain tagging must precede the page filter.** `_tag_domains` reads the
enclosing domain by walking a list in document order. A page-filtered slice
opens part-way through a domain and jumps gaps between windows, so tagging it
directly assigns the wrong domain or none, and domain-scoped precision then
silently discards real false positives as out-of-scope. The full run is tagged
first and the slice passed with `grade_elements(detected_pretagged=True)` — the
one additive change to the grader, which no other caller sees.

**3. Grounding must not assume single-column reading order.** Contiguous-substring
grounding reported **39 hallucinations on Colorado** that do not exist:
extraction flattens a multi-column page into one reading order, so *"Complete
personal care tasks, such"* and its continuation *"as dressing, brushing teeth,
toileting,"* are two blocks apart with other-column text between. Grounding is
therefore exact-substring **or** ≥0.9 distinct-word coverage, which is immune to
reading order. Both states then show **0** ungrounded.

**4. The duplicate check must be keyed more loosely than the merge it audits.**
See the correction above. This is the one that actually bit.

**Page-tolerance sensitivity.** Every arm is computed at tolerance 0 and 1.
Recall conclusions are identical at both. Grounding is *not* meaningful at
tolerance 1 — widening the window admits trimmed pages the subset PDF never
contained, so KY shows 16 ungrounded there by construction. Read tolerance 1
for recall only.

## Open before this can be cited

1. **KY:** the author's exhaustive grading of `ground_truth_detector/KY.json`
   against the PDF. This is the only open item.
2. **Re-run** this measurement, and the parser counterpart, after any golden
   change — and re-record Tasks 1 and 2 too, because every recorded detector
   number for a changed state becomes historical.

The `age_band` verdict is closed (`RUN`) and needs no re-run: it changes no code
and no golden.

Colorado needs nothing. Its golden is not changing.

## What to read when auditing a row

Four JSON layers feed this task. Only the first is editable annotation; the
other three are derived or fetched.

| layer | file | role |
|---|---|---|
| 1. the annotation | `evaluation/ground_truth_detector/{KY,CO}.json` | **the golden — this is what a review verdict edits** |
| 2. the run | `outputs/scale-08-29-26/{KY,CO}-detection.json` | the trimmed-tier detection, 329 / 300 elements, fetched from S3 unmodified |
| 3. **the graded input** | `graded_input/{KY,CO}_graded_input_tol{0,1}.json` | **the exact pair handed to `grade_elements`** — golden verbatim, plus the run filtered to the page window and carrying the `_domain` tag it was graded with |
| 4. the result | `{KY,CO}_scale_grade.json` | every metric, decomposition and worklist |

Layer 3 was added 2026-09-06. Before that the graded slice existed only in
memory, so auditing a row meant re-deriving the page window and the domain
tagging by hand before you could see what the grader saw — which is exactly the
kind of un-regenerable step guardrail 6 exists to forbid. It is written at both
page tolerances, because which arm a number came from is part of the number.

The first row of `KY_graded_input_tol0.json` is the age-band question in
miniature: the golden's `KY-DOM-01` carries no `age_band` key at all, and the
run's matching element carries `"THREE AND FOUR YEAR OLDS"`.

## Regenerate

```
python -m paper.analysis.scale_grade --state KY --state CO \
    --detection-dir outputs/scale-08-29-26 \
    --source-extraction-dir outputs/subset-for-scale \
    --out paper/results/task9_20260905
python -m paper.analysis.scale_grade_parser --state KY --state CO \
    --parsing-dir outputs/scale-08-29-26 --out paper/results/task9_20260905
python -m paper.analysis.make_review_sheets
```

Inputs are the S3 artifacts of `pipeline-US-{KY,CO}-{2021,2020}-full08292026`
(detection) and `test-pipeline-US-{KY,CO}-{2021,2020}-044` (subset extraction),
bucket `els-processed-json-dev-390888050716`.
