# Task 1 (re-record) — headline evals on the 4 golden states

**Date:** 2026-08-22 (run `2026-08-22T23:50:33Z` – `2026-08-23T00:12:52Z` UTC) · **Commit:** `628829b` ("updates for the ablation arm"; working tree clean at run time) · **Code version hash:** `288c64f1` · **Corpus tier: `_only_subset` (9–15pp manually trimmed subset PDFs — NOT full documents)** · Outputs: `outputs/08-22-26-4` · Models: detector `us.anthropic.claude-opus-4-6-v1`, depth-map `us.anthropic.claude-haiku-4-5-20251001-v1:0`, parser `us.anthropic.claude-sonnet-4-6`, temperature 0.

Supersedes `paper/results/task1_20260816/`, which is retained only as the reproducibility record. Three things moved since that folder: **source** (`code_version_hash` `3b445471` → `2ac17ac2` → `288c64f1`), **inputs** (`outputs/08-16-26` → `outputs/08-22-26-4`), and **the held-out goldens** (NV/KY grew under Emily's exhaustive annotation pass — those are Task 2's goldens; **the golden four's detector and parser goldens are unchanged, and none was edited this run**).

Companion: `paper/results/task2_20260822/` ran in the same invocation, at the same `code_version_hash` `288c64f1`, on the same outputs folder, through the same consolidation script — so the golden-four numbers here and the held-out numbers there are directly comparable. Regenerating commands, provenance and caveats: `manifest.json`. Raw suite reports: `detector_golden4.json` / `parser_golden4.json`. Consolidated paper-facing numbers: `summary.json`.

---

## Headline results

### Detector — fresh direct-path run, `--no-cache`, graded against the detector goldens

| State | Recall | Per-level false negatives | Raw "precision" | Ceiling from annotation coverage | Code acc. | Desc. acc. | Depth map | Regressions |
|---|---|---|---|---|---|---|---|---|
| AZ | **1.000** (5/5) | **0 at all 4 levels** | 0.4167 | 0.4545 (5 golden / 11 in-scope) | 4/4 | 4/4 | PASS | 2/2 PASS |
| CA | **1.000** (25/25) | **0 at all 4 levels** | 0.2049 | **0.2049** (25 / 122) | 25/25 | 14/14 | PASS | 4/4 PASS |
| CO | **1.000** (7/7) | **0 at all 3 levels** | 0.1667 | **0.1667** (7 / 42) | 7/7 | 4/4 | PASS | 2/2 PASS |
| TX | **1.000** (8/8) | **0 at all 4 levels** | 0.3200 | **0.3200** (8 / 25) | 8/8 | 3/3 | PASS | 3/3 PASS |

Per-level true positives / false positives / **false negatives** (`summary.json` → `per_level`):

| State | domain | strand | sub_strand | indicator |
|---|---|---|---|---|
| AZ | 1 / 0 / **0** | 1 / 1 / **0** | 1 / 2 / **0** | 2 / 4 / **0** |
| CA | 3 / 0 / **0** | 3 / 4 / **0** | 5 / 13 / **0** | 14 / 80 / **0** |
| CO | 2 / 0 / **0** | 2 / 5 / **0** | — (3-level document) | 3 / 30 / **0** |
| TX | 1 / 0 / **0** | 2 / 0 / **0** | 1 / 1 / **0** | 4 / 16 / **0** |

Direct-path detected element counts: AZ **66**, CA **122**, CO **61**, TX **33**. All **11** detector regression cases PASS.

### Parser — run on the DEPLOYED BATCHED detections in `outputs/08-22-26-4`

| State | Coverage | Field accuracy | Field acc. over asserted cells only | Fully correct | ID collisions | Regressions |
|---|---|---|---|---|---|---|
| AZ | **18/18** | 0.9969 | 0.9967 | 17/18 | 0 | 1/1 PASS |
| CA | **21/21** | **1.0000** | **1.0000** | **21/21** | 0 | 2/2 PASS |
| CO | **9/9** | **1.0000** | **1.0000** | **9/9** | 0 | 2/2 PASS |
| TX | **8/8** | **1.0000** | **1.0000** | **8/8** | 0 | 2/2 PASS |

`standard_id` uniqueness: **0 collisions** in every state's full output (45 / 94 / 48 / 25 standards). All **7** parser regression cases PASS. Three of the four states are perfect on every graded cell; AZ's single defective cell is upstream OCR noise (finding 7).

---

## What the paper may and may not claim

### 1. Recall is 1.000 at every level in all four states, and `fn = 0` per-level is the strong form of that claim.

Every one of the 45 annotated detector elements was found, and the per-level table above shows **zero false negatives at every level of every state** — not merely 1.000 in aggregate. `summary.json` → `match_path.unmatched` is `[]` and `missing_test_cases` is `[]` for all four states, so nothing was rescued by a lenient denominator.

Because `level` is part of the match key, a match implies the element was classified at its annotated level, so this is also the direct evidence for the classify-by-position claim: **all 45 annotated elements were placed at the correct level**.

Two consequences the paper must not overstate, unchanged from 2026-08-16:

- **"0 level misclassifications" is not a second measurement.** The suite's confusion matrix is structurally diagonal (`level` is in the match key in both matching tiers), and `consolidate_task1.py`'s level-agnostic re-pairing only does work when goldens go unmatched. With recall 1.000 there are none, so `off_diagonal_total: 0` is arithmetic, not evidence.
- **"0 age-band drops" is not a second measurement either.** `age_band_drops` is a strict subset of `missing_test_cases`, so it follows from recall 1.000.

### 2. Raw precision EQUALS the annotation-coverage ceiling to four decimals in CA, CO and TX. For those states the metric carries literally no information about correctness.

| State | Raw precision | Ceiling | Identity |
|---|---|---|---|
| CA | 0.2049 | 0.2049 | 25 / 122 |
| CO | 0.1667 | 0.1667 | 7 / 42 |
| TX | 0.3200 | 0.3200 | 8 / 25 |

This is guardrail 8's thesis demonstrated arithmetically rather than by spot-check. The suite's precision denominator is `matched + in-scope extras`, and its ceiling denominator is `n_detected_in_annotated_domains`; with zero fallback matches those are the same set, so raw precision **is** `n_golden / n_in_scope` — a pure restatement of how much of the document a 5–25 element spot-check golden annotates. Say it plainly: **for CA, CO and TX the raw precision number measures the golden's coverage, not the detector's correctness.**

No golden-four detector golden is exhaustive, so guardrail 8's carve-out (Kentucky) applies to none of them. **The paper's precision number for these states must come from the Task 1b manual FP audit, which has never been run** — see finding 8.

### 3. AZ is the one state whose raw precision sits BELOW its ceiling, and the cause is a definitional divergence between two counters — NOT a quality finding about AZ.

AZ raw precision **0.4167** vs ceiling **0.4545**. The two figures use different denominators, and both functions claim to be counting "in-scope detections":

- `eval_detector.grade_elements` divides by **12** = `matched` (5 golden entries that paired) + in-scope extras (7). Its numerator-side term counts **goldens**.
- `consolidate_task1.in_scope_counts` reports `n_detected_in_annotated_domains` = **11**. It walks the detection in reading order tracking the last-seen domain and counts **detections** whose enclosing domain title the golden annotates.

The gap is exactly one element, and it is the same instrument case the 2026-08-16 folder recorded: `AZ-IND-LL-1-2-b` is annotated in the AZ golden **without its Language-and-Literacy domain header**, so the golden tags it to Social Emotional Development (AZ's only annotated domain) while the detection correctly places it under Language and Literacy — which puts that detection among the 54 `ignored_out_of_scope` while `grade_elements` still pairs it through the domain-agnostic fallback (`summary.json` → `match_path.matched_via_fallback: 1`, `fallback_crossed_domain: [AZ-IND-LL-1-2-b]`).

**Nothing failed to match:** `match_path.unmatched` is `[]` and per-level `fn` is 0 at all four AZ levels. The three counters — precision numerator (matched goldens), precision denominator (matched goldens + in-scope extra detections) and ceiling denominator (in-scope detections) — agree whenever fallback matches are zero, which is why CA/CO/TX show the exact identity and AZ does not.

**Recommendation: reconcile the two counters onto one convention before the paper quotes either.** Counting detections consistently on both sides gives AZ 4/11 = **0.3636** (the strictly-scoped figure the 08-16 folder recorded); counting goldens consistently gives 5/12 = 0.4167 (current). The ceiling 5/11 mixes the two. This is a bookkeeping decision, not a measurement, and it must not be written up as an AZ defect.

### 4. The two halves of this folder do not read the same AZ detection, and that is expected.

The fresh direct-path detector run recorded here emits **66** AZ elements (45 indicator / 11 sub_strand / 8 strand / 2 domain, `paper/results/task1_20260822/review_detector/AZ/AZ-detected.json`). The deployed batched detection the parser eval reads emits **77** (45 / 21 / 9 / 2, `outputs/08-22-26-4/AZ-detection.json`). **The detector eval runs the direct path and the parser eval reads the batched detections, so this folder's detector table and parser table are not describing the same AZ detection.** State that explicitly in any AZ discussion.

This is the direct-vs-batched divergence CLAUDE.md documents, and `tasking/arxiv_paper.md` already diagnoses the batched 66 → 77 change as benign. Re-verified here directly against the two files on disk (no Bedrock spend), and the decomposition reproduces exactly:

- **4 genuinely new sub_strands** present only in the batched detection: `Attachment`, `Social Interactions`, `Respect`, `Comprehension and Text Structure`.
- **7 additional cross-page duplicate copies** of strands/sub_strands already present (`Language`, `Vocabulary`, `Concepts of Print`, `Book Handling Skills`, `Phonological Awareness`, `Alphabet Knowledge`, `Writing Processes and Writing Applications`) — and **every one of the seven has page 4 as its first occurrence**, AZ's contents/listing page, with the second occurrence on the later page that actually carries the content (pp. 6 / 8 / 9 / 10 / 11 / 12 / 14).
- **0 same-page duplicates in either detection**, so this is not a de-duplication regression.

Indicator **counts** are identical at **45** in both, which is why the parser's 18/18 coverage is
unaffected — but the indicator **sets** are not quite identical, and the difference is worth recording
because it is what makes the 4 + 7 = 11 arithmetic balance. Exactly one indicator title differs, by a
footnote marker only:

| detection | title |
|---|---|
| direct | `…varies the amount of information`**`¹²`**` to clarify the message.` |
| batched | `…varies the amount of information to clarify the message.` |

So that indicator is a swap (one out, one in), not an addition, which is why 4 new elements plus 7
duplicate copies still nets to 11. This is the same "1 indicator title edited in place" that
`tasking/arxiv_paper.md` records. Verified directly: 5 (level, title) pairs appear in batched but not
direct — the 4 sub_strands above plus the de-footnoted indicator — and 1 appears in direct but not
batched, the footnoted form of that same indicator.

### 5. The depth map PASSed in all four states, which discharges `tasking/arxiv_paper.md`'s instruction to re-verify it on `-4` rather than assume it carried over from `08-16-26`.

| State | Graded canonical-level sequence |
|---|---|
| AZ | `domain → strand → sub_strand → indicator` |
| CA | `domain → strand → sub_strand → indicator` |
| CO | `domain → strand → indicator` (correctly 3-level, no sub_strand) |
| TX | `domain → strand → sub_strand → indicator` |

**The graded map is a SECOND `infer_depth_map` call, not the one that drove the graded detection** — 8 Haiku calls this run, 2 per state, and only the second is graded. Verified from `paper/results/rerecord_20260822.log` that the two calls produced **identical canonical-level sequences in all four states**, so the risk did not materialise; but a PASS is still not proof the detection ran on a correct map.

### 6. The KY-style malformed-primary-key defect did not fire in any golden-four state this run. That is NOT evidence it is fixed.

Zero `standard_id` collisions in all four states, all four `NO-ID-COLLISION` regression cases PASS, and every `indicator.code` and `standard_id` cell is correct in all four states (`summary.json` → `per_field_accuracy`).

Per CLAUDE.md this defect is **sampling variance, not a code regression**: it appears at 8 distinct code versions, and runs over an identical frozen input at temperature 0 disagree with each other. **One clean run cannot retire an intermittent defect**, and the paper must not present a clean run as a fix. The durable mitigation is `validator._validate_code_shape`, which rejects such a record before Aurora; that guard is not exercised by either eval suite and its status is unchanged by this run.

### 7. AZ's single parser defect is upstream text-fidelity noise, not a hierarchy error.

`review_parser/AZ/AZ-review.json` names it: test case **`AZ-IND-15`**, field `indicator.description`, an OCR confusion of `[I]` for `[1]` inside the quoted child example (*"My name starts with an [I]."* read as *"…an [1]."*). Everything else in the string is byte-identical.

That is **1 wrong cell out of 324** (`field_decomposition`: 305 `value_correct`, 18 `null_correct`, 1 `value_wrong`), giving `indicator.description` **17/18** and AZ field accuracy 0.9969. It is the same class of upstream noise the 08-16 folder identified, and it is the only thing standing between the golden four and a clean sweep. **The paper may not call it a parsing error.**

### 8. Nothing here supports a precision, batching or scale claim.

- **No verified-precision figure exists for the golden four.** Task 1b has never been run (`paper/results/task1b_fp_audit.json` does not exist). This run leaves **156** unmatched in-scope detections awaiting verdicts — AZ 7, CA 97, CO 35, TX 17 (`review_detector/{STATE}/{STATE}-review.json` → `extra_in_detected`). `paper/results/task2_20260822/findings.md` quotes the outstanding population as "~165"; the measured count on this run's artifacts is 156.
- **Neither batching layer is exercised at this corpus tier.** `chunk_text_blocks` yields **4/3/4/3** chunks for AZ/CA/CO/TX against `MAX_CHUNKS_PER_BATCH=5`, and the detector emits **2/3/3/2** domains against `MAX_DOMAINS_PER_BATCH=3`, so detection and parsing each run as exactly **one batch per state**: the Step Functions Map has a single iteration and the merge merges one batch. The fan-out and the merge — the actual risk — are entirely untested here. Answering the subset criticism is Task 6's job, not this folder's.
- **The parser eval runs the direct path while production runs the batched path**, so this folder's parser numbers are not production-path numbers even though the detections they consume are.

---

## Instrument repairs made during this task

None. `evaluation/` was not modified for this run; both suites ran as committed at `628829b`.

## Golden data corrections made during this task

None. **No golden-four detector or parser golden was edited this run**, so every number above was produced against the goldens as they stood at `628829b` (`ground_truth_detector`: AZ/TX last touched `2979f61` 2026-08-01, CA/CO `d6ccfa2` 2026-08-21; `ground_truth_parser`: AZ `fbff414` 2026-08-16, CA/TX `0b222f7` 2026-08-15, CO `d6ccfa2` 2026-08-21).


## Task 1b — false-positive audit: COMPLETE and SIGNED (2026-08-23)

All **156** unmatched in-scope detections across the golden four were audited and
signed by Emily Cheyne, **0 verdicts changed**
(`task1b_fp_audit_SIGNED.json`, sheets in `signoff/`).

| state | in-scope | mechanical (verbatim / repeat) | split titles | hallucinations | verified precision |
|---|---|---|---|---|---|
| AZ | 11 | 7 | 0 | **0** | **1.000** |
| CA | 122 | 97 | 0 | **0** | **1.000** |
| CO | 42 | 8 | 27 | **0** | **1.000** |
| TX | 25 | 5 | 12 | **0** | **1.000** |

**Corpus-wide, combining with the held-out states: 297 in-scope detections, ONE
hallucination — verified precision 0.9966.** The single hallucination is NV's
`SS.CI.PK3`. This is the paper's detector-precision number, and it now covers all
six states on one definition.

⚠️ **The 39 CO/TX "split titles" were reported as `hallucinated` before
2026-08-23** and would have read as CO verified precision 0.357. They are real
titles broken across lines/columns; `fp_audit` gained a `real_split_title`
verdict gated on in-order reconstruction. Do not quote any pre-2026-08-23 CO/TX
precision figure.

## Open questions for Emily

1. **Which in-scope convention should the suite use?** (finding 3.) `eval_detector`'s precision denominator and `consolidate_task1.in_scope_counts` disagree by exactly one element on AZ. Pick one and make both functions use it, so the raw-precision/ceiling identity is uniform across states. No paper number should be quoted from the current mixed convention.
2. **Task 1b still owes 156 verdicts for the golden four** (finding 8). Until it runs, the paper has a verified precision for held-out states only, and even that (NV 0.9811) is an unsigned first pass.
3. **Task 3's off-arm must be re-run** once the Bedrock daily Opus token quota resets — `paper/results/task3_20260822/` aborted on a `ThrottlingException` and contains no valid ablation number. Tasks 1 and 2 are recorded and must not be re-run.
4. **How many detector runs back the paper's recall number?** Still open. This run is a single sample per state; recall has now come out 1.000 on 07-18, 08-16 and 08-22, which is N=3 across three different code versions rather than a stability measurement. Task 5 needs a decision on N and on whether `--stability-runs` is repaired first.

## Instrument notes (for the paper's evaluation section)

- Detector matching: domain-scoped, code-agnostic key `(enclosing domain, level, normalized title, normalized age-band)`, with a domain-agnostic fallback; exact title match after whitespace/case folding.
- Precision scoping: detections outside golden-annotated domains are excluded (neither TP nor FP) — 54 / 0 / 19 / 8 ignored for AZ/CA/CO/TX. Recall's denominator is the golden set only. A golden matched via the fallback still enters precision's numerator even when its detection is out of scope (finding 3).
- **Code and description accuracy are conditioned on the title already matching exactly.** Both are graded over matched pairs only, and matching requires an exact title match, so a garbled title silently removes an element from both denominators. Vacuous this run (recall 1.000 everywhere), but the metric names do not say so.
- **Both content denominators are thin — report matches/total, never a bare rate.** Descriptions are annotated on 4/5 (AZ), 14/25 (CA), 4/7 (CO), 3/8 (TX) golden elements; codes on 4/5 (AZ — the AZ domain entry annotates none), 25/25 (CA), 7/7 (CO), 8/8 (TX).
- Depth-map grade: per-state exact match of the canonical-level sequence (a boolean), computed by calling `infer_depth_map` on the full extraction blocks — the same call shape as production. **It is a second call, not the one that drove the graded detection** (finding 5).
- Parser matching: `(indicator name, canonicalized age-band)` with the proficiency/age variant suffix applied as a tie-breaker inside `grade_parser` (the 2026-08-16 `eval_parser._match_key` repair). Zero dropped and zero duplicated standards in any state this run.
- Parser field accuracy averages over cells whose golden is null — **5.56% (AZ), 11.64% (CA), 22.22% (CO), 16.67% (TX)** of graded cells, chiefly the three `sub_strand.*` cells per standard on a 3-level document. Those cells are not free (a spuriously invented sub_strand fails there), but "field accuracy" and "accuracy on the fields the golden asserts" are different numbers; `summary.json` reports both, and with **0 spurious values in any state this run** they differ only for AZ (0.9969 vs 0.9967).
