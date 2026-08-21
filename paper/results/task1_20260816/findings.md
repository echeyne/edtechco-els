# Task 1 (re-run from scratch) — headline evals on the 4 golden states

**Date:** 2026-08-16 · **Commit:** `fbff414` (src/ and evaluation/ clean at run time) · **Corpus tier: `_only_subset` (9–15pp manually trimmed subset PDFs — NOT full documents)** · Outputs: `outputs/08-16-26` · Models: detector `us.anthropic.claude-opus-4-6-v1`, depth-map `us.anthropic.claude-haiku-4-5-20251001-v1:0`, parser `us.anthropic.claude-sonnet-4-6`, temperature 0.

Supersedes the 2026-07-18 run (`paper/results/task1_*`). That run graded code that no longer exists: `derive_code_from_title` / `_resolve_code` landed 2026-08-01, and rule 4's code-lookup clause, `_anchor_parent_chain`, `disambiguate_colliding_standards` and `models._blank_to_none` landed 2026-08-15. Regenerating commands, provenance and caveats: `manifest.json`. Raw suite reports: `detector_golden4.json` / `parser_golden4.json`. Consolidated paper-facing numbers: `summary.json`.

## Headline results

### Detector — fresh direct-path run, `--no-cache`, graded against the detector goldens

| State | Recall | Per-level recall | Raw "precision" | Precision ceiling from annotation coverage | Code acc. | Desc. acc. | Depth map | Age-band drops |
|---|---|---|---|---|---|---|---|---|
| AZ | **1.000** (5/5) | 1.00 at all 4 levels | 0.417 | 0.455 (5 golden / 11 in-scope) | 4/4 | 4/4 | PASS | 0 |
| CA | **1.000** (25/25) | 1.00 at all 4 levels | 0.205 | **0.205** (25 / 122) | 25/25 | 14/14 | PASS | 0 |
| CO | **1.000** (7/7) | 1.00 at all 3 levels | 0.167 | **0.167** (7 / 42) | 7/7 | 4/4 | PASS | 0 |
| TX | **1.000** (8/8) | 1.00 at all 4 levels | 0.320 | **0.320** (8 / 25) | 8/8 | 3/3 | PASS | 0 |

All 11 detector regression cases PASS. Depth-map inference produced the exact expected canonical-level sequence for all four states (CO correctly 3-level, no sub_strand).

### Parser — run on the DEPLOYED BATCHED detections in `outputs/08-16-26`

| State | Coverage | Field accuracy | Field acc. over asserted cells only | Fully correct | ID collisions |
|---|---|---|---|---|---|
| AZ | 1.000 (18/18) | 0.997 | 0.997 | 17/18 | 0 |
| CA | 1.000 (21/21) | 0.984 | 0.982 | 18/21 | 0 |
| CO | 1.000 (9/9) | **1.000** | 1.000 | 9/9 | 0 |
| TX | 1.000 (8/8) | **1.000** | 1.000 | 8/8 | 0 |

`standard_id` uniqueness: 0 collisions in every state's full output (45 / 94 / 48 / 25 standards). All 8 parser regression cases PASS — two of them for the first time meaningfully (see finding 4).

## What the paper may and may not claim

### 1. The detector suite's "precision" is arithmetically annotation coverage. It is not a hallucination rate.

For CA, CO and TX the raw precision **equals the annotation-coverage ceiling to four decimal places** (0.2049 = 25/122, 0.1667 = 7/42, 0.3200 = 8/25). That identity is only possible if every single unmatched in-scope detection is real, unannotated document content — the metric has no room left to be measuring anything else. Guardrail 8 is now confirmed arithmetically rather than by spot-check.

AZ is the one state where the two differ (0.4167 vs 0.4545), and the gap is a **scoping artifact, not a hallucination** — see finding 3. All 7 AZ in-scope "false positives" were inspected and are real AZ content: `Strand 2: Relationships and Skills`, `Concept 2: Recognizes and Expresses Feelings`, `Concept 3: Self-Regulation`, and indicators b–e under Concept 1.

**Recall, per-level recall, code accuracy and description accuracy are the trustworthy detector numbers from this suite.** The paper's precision number comes from the Task 1b manual FP audit.

### 2. Recall 1.000 also carries the level claim — but two other metrics are then redundant, and the paper must not present them as independent.

`level` is part of the match key, so a match implies the element was classified at its annotated level. Recall 1.000 across all four states therefore means **all 45 annotated elements were placed at the correct level** — which is the direct evidence for the classify-by-position claim.

Two consequences the paper must not overstate:

- **"0 level misclassifications" is not a second measurement.** The suite's confusion matrix is structurally diagonal (level is in the match key in both matching tiers), and `consolidate_task1.py`'s level-agnostic re-pairing only does work when goldens go unmatched. With recall 1.000 there are none, so its 0 off-diagonal is arithmetic, not evidence.
- **"0 age-band drops" is not a second measurement either.** `age_band_drops` is a strict subset of `missing_test_cases`, so it follows from recall 1.000.

### 3. The domain scoping does real work — verified, not assumed — and it costs AZ one point of precision.

A new match-path audit (`consolidate_task1.match_path_audit`, importing the suite's own key functions so the two cannot drift) replays `grade_elements`' two-tier lookup and records which tier fired:

| State | Matched domain-scoped | Matched via domain-agnostic fallback | Fallback crossed a domain boundary |
|---|---|---|---|
| AZ | 4 | 1 | 1 |
| CA | **25** | 0 | 0 |
| CO | 7 | 0 | 0 |
| TX | 8 | 0 | 0 |

CA is the case that matters: its FLD and ELD domains both contain a `Vocabulary` sub_strand, a `Grammar` sub_strand and a `Listening and Speaking` strand. All 25 CA goldens matched **domain-scoped with zero fallback**, so those pairs were genuinely disambiguated by enclosing domain rather than cross-matched. (This was not guaranteed: the CA source is an "at-a-glance" document, and had the detector front-loaded its three domain headers on one page, `_tag_domains`' last-seen-domain heuristic would have tagged all body content to the last domain. It does not — the detector emits the domains interleaved at pages 2, 6 and 9, in document order.)

AZ's single fallback match is `AZ-IND-LL-1-2-b`, annotated in the golden **without its Language-and-Literacy domain header**. The golden therefore tags it to Social Emotional Development while the detection correctly places it in Language and Literacy. `grade_elements` pairs them through the fallback, which adds 1 to `matched` without adding its detection to the in-scope pool — so AZ's precision denominator is 12 where the strictly-scoped count is 11. **This is Task 1b step 3's open item, now precisely measured.**

### 4. Two parser regression cases had been passing on an empty population since the disambiguator moved into the code. Repaired.

`CA-EARLY-LATER-DISTINCT-IDS` and `TX-PK3-PK4-DISTINCT-IDS` both reported `PASS — 0 multi-variant indicator code(s) all kept distinct ids+bands`. The `0` is the tell: `_distinct_within_code_groups` grouped standards by `(domain code, indicator code)`, but the parser now carries the disambiguator **inside** the indicator code (`…1.1.36-54` vs `…1.1.48-66`, `…1.1.DISC` vs `…1.1.DEVE`). Every variant therefore landed in its own singleton group, no group ever reached two members, and the check could not fail. It has reported PASS in every run including July's, while guarding nothing.

Repaired to group by the indicator code with a trailing *disambiguator* segment stripped (an age range or an all-caps token), with two additional constraints that the KY corpus forced: a group only counts as a variant set if its members share one indicator name (CA's Early/Later and Discovering/Developing/Broadening) or have pairwise-distinct age bands (TX's PK3/PK4) — otherwise KY's derived-abbreviation leaf codes (`AL.1.1.1.EASPT`, `…MFAAD`, `…SADGA`) would be mistaken for variants of one indicator. And **an empty population now FAILS**, since for these two states it would mean the variant columns collapsed.

Both callers now pass on a real population: **CA 39 variant groups, TX 10**. This is a tightening, never a loosening. Scores are unchanged (verified by re-grading the identical cached parser output: every coverage / field-accuracy / fully-correct / collision figure identical, only the two regression detail lines changed).

### 5. THE MOST IMPORTANT DEFECT THIS RUN — an intermittent, per-chunk failure that writes a malformed Aurora primary key. Full evidence: `parser_code_label_variance.json`.

The parser sometimes leaves the document's structural label inside the indicator code segment:

```
bad     ELD.1.0.VOCA.Foundation 1.1.DISC     →  standard_id US-CA-2021-ELD.1.0.VOCA.Foundation 1.1.DISC
good    ELD.1.0.VOCA.1.1.DISC
```

**This is not a stale-deployment or code-version artifact — checked directly.** `git diff 29b22f0 HEAD -- src/` is empty; the pipeline Lambdas were deployed `2026-08-16T20:37:52Z` from that commit, 90 s before the run; `fbff414` changed only the AZ golden and `outputs/`; neither `els-parse-batch-dev` nor `els-hierarchy-parser-dev` overrides `BEDROCK_PARSER_LLM_MODEL_ID`, so both used `claude-sonnet-4-6`; and both paths run `normalize_element_codes` → `chunk_elements_by_domain` identically.

**Rate on current code: 2 hits in 18 end-to-end runs, and the unbiased estimate is 1 in 17 (~6%).** The first observation is the *trigger* for the investigation, not a random draw, so including it biases the rate upward; only post-trigger samples count. A 1/17 rate carries a 95% CI of roughly 0.2–30%, so describe it as "a few percent", never as a point estimate. **The source component is not localized** — 8 instrumented runs that record every chunk's raw output failed to catch an occurrence. Scoping matters here too and an earlier draft got it wrong — see the withdrawal note below. `eval_common.code_version_hash()` is a SHA-256 over `detector.py` + `parser.py` and is embedded in every run-cache filename, so each artifact carries a cryptographic record of the source that produced it. At HEAD it is `3b445471`, and the failing eval artifact is `evaluation/.cache/parser-CA-54239bf51ad930e8-3b445471-.json`.

| Sample (all on `3b445471`, input `CA-detection.json`) | Path | Runs | Bad codes |
|---|---|---|---|
| Task 1 parser eval (`--no-cache`) — **the trigger** | direct | 1 | **12** / 94 |
| repeats 1–2 | direct | 2 | 0 |
| batch-of-6 run 5 | direct | 1 | **12** / 94 |
| batch-of-6 runs 1–4, 6 | direct | 5 | 0 |
| `outputs/08-16-26` (deployed, Lambdas built `20:37:52Z` from `29b22f0`) | batched | 1 | 0 |
| `localize.py` attempts 1–8 (instrumented, records raw per-chunk output) | direct | 8 | 0 |

A per-chunk probe — `build_parsing_prompt` → `call_bedrock_llm` → `parse_llm_response` on one chunk, verified to reproduce the end-to-end shape — was also clean everywhere: chunk 4 **0/12**, chunk 6 **0/13**, chunk 7 **0/12**, chunk 9 **0/12**. That argues against a ~20% *per-chunk* rate (p = 0.055) but says little about 5–10% (p = 0.25–0.51), so it refutes nothing.

**⚠️ Withdrawn:** an earlier version of this finding reported "2 of 7 (~29%), a different chunk each time" by pooling runs across **three different `parser.py` versions**. `outputs/08-13-26` (parsed 08-13 19:59Z) and `outputs/08-15-26` (08-15 20:30Z) both ran `6e31777` (08-01) — two commits back, and the intervening `0b222f7` is exactly the commit that reworked code composition. Those runs are not evidence about current behaviour and have been removed from the rate.

**The two current-code hits are byte-identical**, so this is chunk-**localized**, not chunk-random (the "different chunk each time" claim rested on the withdrawn 08-13 run). Both produce the same 12 codes: `chunk_elements_by_domain`'s **chunk 6 of 9** — domain ELD, sub_strands VOCA + GRAM, Foundations 1.1–1.4, each ×3 proficiency columns.

Four things follow:

1. **It changes the Aurora primary key.** `US-CA-2021-ELD.1.0.VOCA.Foundation 1.1.DISC` contains a space and a label word. Same failure class CLAUDE.md documents for KY (58% of KY `standard_id`s moved across three runs), and the existing deterministic remedy does not cover it: `derive_code_from_title` governs the *abbreviation* branch of rule 4, and `_canonicalize_code` folds `<Label>: <id>` → `<Label> <id>` by shape, but nothing strips a label word out of a segment when the parser composes the qualified indicator code.
2. **The detector is not at fault, and the work is not an edge case.** All 94 CA detector indicator codes carry the `Foundation N.N` label (detector code accuracy is 25/25 against a golden that annotates them that way), so stripping it is something the parser does on every CA indicator — 82 of 94 times in each failing run.
3. **The column-shape hypothesis is dead; the source component is still unknown.** Chunks 7, 8 and 9 carry the identical three-proficiency-column shape and have never failed, so the shape is not the trigger. Narrowing the alternative: only two steps run after the chunk loop, and `normalize_parsed_codes` builds counters for domain/strand/sub_strand **only** and never rewrites `s.indicator` — despite a docstring claiming it "works at every hierarchy level: domain, strand, sub_strand, indicator". (I believe the implementation is right and the docstring wrong — cross-chunk reconciliation works by outvoting, and an indicator appears in exactly one chunk — but the line would mislead anyone diagnosing this, and it sits in `parser.py`, which I have not touched.) That leaves `disambiguate_colliding_standards` as the only post-merge step that rewrites indicator codes, and CLAUDE.md records it as having **no confirmed live case**.
4. **The batched path is untested here.** Only one current-code deployed sample exists (clean), and both hits are on the direct path. With 2 hits total there is no power to compare paths — do not claim either that batching is safer or that the rates match.

When it fires, the eval reports 6 field mismatches (chunk 6 contains 3 of the golden's 9 annotated CA indicators); the other 9 bad standards are invisible to the golden.

**Recommended fix follows the CLAUDE.md pairing doctrine:** keep the prompt rule, and add a document-agnostic post-processor that rejects a code segment containing whitespace or a leading label word when the element's document code is available in bare form — shape only, never a per-state list. **Needs Emily's decision before implementing** (it touches `parser.py`, which the design direction guards closely).

### 6. Detection converged between the direct and the deployed batched path — but at this corpus tier that is close to structural, not evidential.

| State | Direct | Batched | Shared (level, title, age_band) | Jaccard | Code disagreements |
|---|---|---|---|---|---|
| AZ | 66 | 66 | 65 | 0.970 | 0 |
| CA | 122 | 122 | 122 | **1.000** | 0 |
| CO | 61 | 61 | 61 | **1.000** | 0 |
| TX | 33 | 33 | 33 | **1.000** | 0 |

The single AZ difference is two superscript footnote characters in one out-of-scope indicator title (`information¹²` vs `information`).

**This must not be reported as evidence that batching is safe.** `chunk_text_blocks` yields 4/3/4/3 chunks for AZ/CA/CO/TX against `MAX_CHUNKS_PER_BATCH=5`, so detection runs as exactly **one batch per state** — the Step Functions Map has a single iteration and `merge_detection_batches` merges one batch. The detector emits 2/3/3/2 domains against `MAX_DOMAINS_PER_BATCH=3`, so parsing is also **one batch per state**. NV (5 chunks) and KY (3 chunks) are single-batch too. Both batching layers — the fan-out and the merge that is the actual risk — are entirely unexercised at the `_only_subset` tier. **Task 6 is required before any batching or scale claim.**

### 7. AZ's parser jump is real extraction work, not golden drift — but two golden cells were edited toward the pipeline today.

AZ moved from field accuracy 0.923 / **0 of 18** fully correct (July) to 0.997 / **17 of 18**. Almost all of that is a genuine extraction fix: July's word-fusion artifacts are gone from the extraction (`firmfoundation` 0 occurrences, `andphysical` 0; `firm foundation` and `and physical` present), consistent with the PyMuPDF hybrid extractor repairing Textract's spacing. AZ's one remaining mismatch is an OCR confusion of `[I]` for `[1]` in the source text — upstream noise, not a hierarchy error.

Two of the 324 AZ cells changed value in commit `fbff414` the same day; Emily has since confirmed (2026-08-16) that both were annotation errors being corrected, not accommodations of pipeline output. The numbers above stand as reported.

### 8. `models._blank_to_none` is landed, deployed and holding; the July TX description question resolved itself.

Across all six states' deployed parsing outputs there are **zero** empty-string descriptions — absence is spelled `None` everywhere. The July open question 2 (TX golden expects `indicator.description: None`, parser emitted the "Child Behaviors" text) is **closed**: the parser now emits `None` for all 8 TX indicators and TX field accuracy is 1.000.

## Golden data corrections made during this task

All verified score-neutral by re-grading the identical cached detector output: every precision / recall / f1 / matched / code / description / depth-map / regression figure unchanged (0 diffs).

- **CA detector golden `version_year` 2008 → 2021.** The CA source is the PTKLF *At-a-Glance* document (`standards_tracking.md` records year 2021, `ptklfataglance.pdf`; the S3 key is `US/CA/2021/…`, and the CA *parser* golden already said 2021). The detector suite never reads this field, so it could not affect a score — but the paper's corpus appendix (Task 11) will.
- **CO detector golden: `annotator` and `annotation_date` values were swapped** (`annotator: "05-31-26"`, `annotation_date: "Emily Cheyne"`). Unswapped. The same swap in the **CO parser golden** was fixed by Emily directly (2026-08-16).
- **CO detector golden `source_document`** `colorado_3_5_trimmed_2020_subset.pdf` → `colorado_3_5_trimmed_2020_only_subset.pdf` (the file that exists).

## Corrections to `tasking/arxiv_paper.md`'s background table

Verified with PyMuPDF against the files on disk:

- KY `_only_subset` is **8pp**, not 9.
- The NV held-out subset file is `nevada_standards_2023_only_subset.pdf`, not `nevada_standards_2023_trimmed_only_subset.pdf`.
- Every other page count in the table is correct (AZ 217/65/15, CA 68/–/13, CO 187 b–8 & 41 3–5/10, TX 87/71/9, NV-2023 98/71/15, KY 120/52).

## Open questions for Emily

1. **The `Foundation N.N` code defect (finding 5).** Confirmed on current code: 2 byte-identical hits, unbiased rate ~6% (1 in 17), writing 12 malformed Aurora primary keys when it fires. The chunk-shape lead is dead and the source component is **not localized** — 8 instrumented runs failed to catch one, and catching one costs ~17 parses (~1.7 h, ~$12) on average. **Recommendation: don't pay to reproduce it.** The failure shape is unambiguous and document-agnostic (an indicator code segment containing whitespace or a leading label word is always wrong), so add a shape guard **outside** `parser.py` — in `validator.py` or the db write path, neither of which CLAUDE.md guards — that both blocks the write and logs the raw per-chunk output beside the final code. The next natural occurrence then localizes the defect for free, and Aurora is protected meanwhile. **Still BLOCKING for any table that reports `standard_id` stability.**
2. ~~Two AZ parser-golden cells edited toward the pipeline~~ — **RESOLVED 2026-08-16 by Emily: both edits stand.** She confirmed both were annotation errors in the previous golden, not accommodations of pipeline output, and the current values are correct:
   - `"The fat cat sat on the _."` → `"The fat cat sat on the_."`
   - `"…in a conventional manner. "` → `"…in a conventional manner. 15 "` (a superscript endnote marker the page does carry)

   Both therefore count as matches in this run's numbers, and AZ's field accuracy 0.997 / 17-of-18 stands as reported. **Annotator of record: Emily Cheyne.** Recorded here because the paper's methodology sentence for Task 1b ("all unmatched in-scope detections were manually audited by the author") rests on the same authority, and because the July findings used AZ's mismatches as the illustration of "parser field accuracy includes upstream text-fidelity noise" — that illustration is now carried by AZ's single remaining mismatch (`[I]` read as `[1]`), not by these two cells.
3. **How many detector runs back the paper's recall number?** Still open from July. This run is a single sample per state; July's headline finding was that the same input and code produced materially different detections across sessions. Recall came out 1.000 in every state on both the 07-18 and this run, which is reassuring but is still N=2. Task 5 needs a decision on N and on whether `--stability-runs` is repaired first (it keys elements on `(code, title)` and counts only level disagreements, so title-fidelity variance — the failure mode actually observed — is invisible to it).
4. **The CO parser golden's swapped `annotator`/`annotation_date`** — confirm before I edit a file the parser suite reads.

## Instrument notes (for the paper's evaluation section)

- Detector matching: domain-scoped, code-agnostic key `(enclosing domain, level, normalized title, normalized age-band)`, with a domain-agnostic fallback; exact title match after whitespace/case folding. **The `eval_detector` module docstring is now accurate** — July recorded it as stale (`"(level, code) tuples"`) and it has since been corrected.
- Precision scoping: detections outside golden-annotated domains are excluded (neither TP nor FP). Recall denominator is the golden set only. A golden matched via the fallback still enters precision's numerator even when its detection is out of scope (finding 3).
- **Code and description accuracy are conditioned on the title already matching exactly.** Both are graded over matched pairs only, and matching requires an exact title match, so a garbled title removes an element from both denominators. Vacuous this run (recall 1.000 everywhere), but the metric names do not say so.
- Description accuracy has a thin denominator by design — the goldens annotate a description on 4/25 (AZ), 14/25 (CA), 4/7 (CO), 3/8 (TX) elements. Report matches/total, never the bare rate.
- Depth-map grade: per-state exact match of the canonical-level sequence (a boolean), computed by calling `infer_depth_map` on the full extraction blocks — the same call shape as production (both `detect_structure` and `detection_batching.prepare_detection_batches` call it on the full block list, which samples ~6000 tokens internally). **It is a SECOND call, not the one that drove the graded detection**: the eval makes 2 Haiku calls per state and grades the second. They agreed for all four states this run (verified from the run log), so the risk did not materialize — but a PASS is not proof the detection ran on a correct map.
- Parser matching: `(indicator name, canonicalized age-band, proficiency-variant code suffix)`. Verified unambiguous — **zero colliding match keys** in any golden or in any state's full parser output, so pairing is deterministic and not order-dependent.
- Parser field accuracy averages over cells whose golden is null (5.6% AZ, 11.6% CA, 22.2% CO, 16.7% TX — chiefly the three `sub_strand.*` cells per standard on a 3-level document). Those cells are not free: a spuriously invented sub_strand fails there, which is how July's depth-map regression surfaced. `summary.json` reports both the headline and the accuracy over asserted cells only; **there were 0 spurious values in any state this run**, so the two barely differ.
