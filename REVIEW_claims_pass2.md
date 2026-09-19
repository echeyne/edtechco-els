# Claim review, pass 2

Reviewed 2026-09-19. Method: re-ran the three generators and diffed the
committed tables; then read the JSON, the goldens and where necessary the raw
run outputs behind every number in the material added since pass 1, rather
than the `findings.md` that summarizes them. `per_level` recall was computed as
`tp/(tp+fn)`; `main.log` was read with `grep -a`; the pages holding the
restructured tables were rasterized and inspected.

## Table regeneration

All eleven generated tables and both generated appendices regenerated
byte-identically from `paper/results/` before any edit in this pass
(`git status` clean on `paper/tables` and `paper/anc` after running
`generate_tables.py`, `make_prompt_appendix.py` and
`make_goldens_appendix.py`). No recording has drifted from the paper. The
tables that differ from HEAD now differ only because this pass edited the
generators (dash removal, two caption wordings); every number is unchanged.

`SUPERSEDED_TAGS` is `{"20260816"}` and no generator reads it. The two
superseded-freeze numbers in prose are the ones pass 1 licensed: the 89.7%
confidence figure, quoted as the earlier freeze's value, and the Task 3 repeat
ranges at hash `288c64f1`, labelled as such. `task2_20260826/nv_attribution_ab.json`
is superseded by `task11_20260905` and is cited nowhere in the paper.

## Pass 1's corrections: all held

| Correction | Status |
|---|---|
| 297 in-scope detections, not 296 | Holds in all four places (abstract, \S1, \S7.3, \S8). \S1's contribution 4 was the one occurrence not tier-qualified at the point of use, two paragraphs from the 277 count; now qualified. |
| Depth-map cost share 0.3% KY / 0.5% CO; detection 57--59% | Caption computes 0.3--0.5% and 57--59% at build time. **Prose said 0.3--0.6% and 57--60%**; now matches the caption. |
| NV chain-break 24/24 | Holds (\S5.3, "every one of the 24 annotated Nevada standards"). |
| NV same-session runs "same set, one differing in the Science code" | Holds (\S6.6). |
| Ablation repeats labelled as an earlier code version | Holds, in prose and the generated caption. |
| ECS citation moved | Holds. |
| Figure 1 caption reconciled with "six-stage pipeline" | Holds (Appendix F). |

## 1. Claims verified

### \S6.4, the whole-document arm (`task10_20260905`)

| Claim | Artifact field | Verdict |
|---|---|---|
| AZ and NV recall 1.000 with full code accuracy (4/4, 46/46) | `comparison.AZ`, `comparison.NV` | verified |
| KY 44/44 to 28/44; TX 8/8 to 5/8; recall 1.000 in both | `comparison.KY`, `comparison.TX` | verified |
| CO recall 0.429 with level collapse (both strands lost) | `comparison.CO`, finding 4 (strand tp=0 fn=2 fp=7) | verified |
| CA emitted exactly 16,000 output tokens, nothing parsed, 0/25 | finding 1; `detector.LLM_MAX_TOKENS` | verified |
| AZ emitted 14,292 tokens, within 11% of the cap | finding 1 (14,292/16,000 = 0.893) | verified |
| Subset extractions 3.7K--7.9K tokens | manifest `⚠️_scope` | verified |
| Single draw per state; not tabulated | manifest `⚠️_STATUS` | verified; the paper says so |

### \S6.8 and Table 8, quality at scale (`task9_20260905`, `task13_20260907`)

| Claim | Artifact field | Verdict |
|---|---|---|
| 277 elements / 207 standards in the trimmed goldens | `KY_trimmed.json` files: 277 elements (9/15/51/202), 207 standards | verified |
| 277/277 found in all three runs; 0 absent; 0 hallucination candidates | `headline.detector.absent`, `hallucination_candidates`, `recall_ignoring_age_band` | verified |
| strict recall 0.59 | `recall_strict` 0.592/0.588/0.592 | verified |
| 164 banded elements per run, sd 0.0 | `age_band_emitted` | verified as a count; see \S2 for the identity claim |
| roughly 15% surplus duplicates | 51/50/51 of 328/327/328 = 15.5%/15.3%/15.5% | verified |
| ten to eleven fabricated `.N` keys per run | `parser.fabricated_keys` 10/11/11 | verified |
| coverage 0.807 / 0.927 / 0.841, twelve-point swing | `parser.coverage` | verified |
| field accuracy 0.995 ± 0.002 | `parser.field_accuracy` mean 0.995, sd 0.002 | verified |
| collisions 0 by construction | `parser.id_collisions`; `findings.md` finding 5 | verified |
| four detection batches per run | not in the recording; recomputed by running `detector.chunk_text_blocks` on each run's saved extraction: 1,741 blocks, 18 chunks, 4 batches in all three | verified by recomputation |
| 6.5× page increase | 52/8 | verified |
| subset goldens regraded inside the trimmed run: 0 absent, 0 ungrounded, KY and CO | `task9` manifest headline | verified |
| CO control: 0 duplicates, 0 fabricated keys, 240 standards | `CO_scale_grade_parser.json` `identifier_uniqueness_over_whole_run` (240/240), `task9` finding 5 | verified |
| subset run emitted null age band for all 44 KY elements | `task9` finding 3 | verified |
| dropped standards are those assigned a narrower band | `task13 findings.md` (36-48 where the document has one band) | verified from the findings file only; not re-derived from the parse output |

### \S6.6, the Nevada non-reproduction (`task5_20260830`, `task11_20260905`)

| Claim | Artifact field | Verdict |
|---|---|---|
| 46/46 recorded; repeats 44, 45, 44, 44, 44 | `task5` reports; `task11` arm A | verified |
| One domain code fails in every draw of both arms | `NV-DOM-03` 5/5 in both | verified |
| Layout sampler mean 0.965 vs stride 0.935; worst A draw beats best B draw | arm A min 44/46 = 0.957 > arm B 43/46 = 0.935 | verified |
| Sampler drops a golden element in 2 of 5 draws; stride in none | arm A recall 0.978 twice; arm B 1.000 ×5 | verified |
| The paper never reports 46/46 as stable | grep: every occurrence is qualified or is the arm's own single draw | verified |

### \S7.5, the `age_band` defect

| Claim | Artifact | Verdict |
|---|---|---|
| Does not affect any subset-tier number | subset run: 44/44 null | verified |
| Fix is a prompt rule, so the hash would move | `code_version_hash` covers `detector.py`/`parser.py` | verified by construction |
| Colorado has no banner and no age-band column | `task9` finding 5; CO golden | verified |

### Abstract and submission copy

`arxiv_abstract.txt` matched the LaTeX abstract word for word apart from
dashes and the dropped `\S\ref` (checked programmatically) at 1,888
characters. After this pass's dash removal both were regenerated together and
match at **1,864 characters** after the "collision-free" wording was also
dropped at the author's request. Every number in it (1.000, 297, one
hallucination, 0.920, 0.833, three known places) traces to the artifacts
above. The "On an annotated subset" qualifier covers every quality figure the
abstract quotes, and \S1's scope paragraph names the trimmed-tier exception.

### Cross-references after the cut

Zero undefined references or citations. Every "above"/"below" in the body
refers to material that is still above or below it (checked each occurrence).
The Appendix D lead-in says its table is "read by \S6.5", which is where the
prose lives. \S5.6 points at Appendix F for the architecture. No term is
defined only in an appendix and used in the body.

### Guardrail sweep

| Guardrail | Result |
|---|---|
| 1, tier on every table and headline number | Holds for tables. **Four prose or caption sites said every quality number is subset-tier**, which \S6.8 contradicts: \S3, \S7.2, the dataset-stats caption and the corpus-appendix caption. `TODO_remaining.md` item 3 fixed the abstract and \S1 only. All four now say "headline" and name the exception. |
| 2, confidence gates nothing | Holds. Every "gate"/"threshold" in the paper and appendices is a negation; `needs_review` absent from `src/`. |
| 6, every number regenerable | The three qualitative \S5 statements have not crept back as figures. New material: every number traces, with two exceptions listed in \S3 below. |
| 8, raw precision not quality | Holds; only Table 5 prints it, with the caveat, and \S7.3 names it as coverage. CO's trimmed-tier precision is not reported. |
| `_trimmed` keeps 100% | Holds in \S3, \S6.7, \S7.2 and both trimmed-tier captions. |
| NV 46/46 never stable | Holds. |
| `.N` suffixes not a resolver defect | Holds (\S6.8 item 3, Table 8 dagger). |
| Zero at small n has its denominator | Holds (Table 6 denominators; \S6.6 "lower bounds"). |
| Duplicate check keyed loosely | Holds; \S6.8 says collisions are zero by construction. |

## 2. Claims that were wrong (corrected value and source)

| # | Where | As written | Correct | Source | Fixed |
|---|---|---|---|---|---|
| 1 | \S6.8, \S7.5 | 164 banded elements "with a standard deviation of zero, the same elements every time"; "the same 164 elements in three consecutive runs" | The count is 164 in each run, but the sets differ: runs 1 and 3 are identical, run 2 differs on five elements, so **159 are common to all three**. | recomputed from `outputs/ky-3runs-09-07-26/run{1,2,3}/KY-detection.json` (level + title of every element with a non-null `age_band`) | yes, both sites now give the count and the 159; "systematic rather than sampling noise" is retained since it survives |
| 2 | \S7.3 | "Every `Benchmark N.N` identifier the document prints (17 of 17)" | **18 of 18** distinct identifiers (Benchmark 1.1--1.6, 2.1--2.3, 3.1--3.6, 4.1--4.3), all present in the golden. 15 of 15 headings is correct. | `ground_truth_detector/KY_trimmed.json` and the run-1 extraction text | yes |
| 3 | \S5.7 | "fifteen that appear, of which ten are distinctive to a single state's golden and five are domain names shared across states" | **Fifteen distinctive** (10 development + 5 held-out) plus **one shared** title ("Approaches to Learning"). The next sentence already said ten plus five. | `task12_20260905/prompt_example_provenance.json` totals | yes |
| 4 | \S3, \S7.2, two captions | "Every quality number in this paper is computed at [the subset] tier" | False since \S6.8 grades the trimmed tier. | the paper itself | yes; "headline" plus the exception |
| 5 | \S6.7 | depth map 0.3--0.6%, detection 57--60% | 0.3--0.5%, 57--59% (KY 0.32%/59.4%, CO 0.54%/57.1%) | recomputed from `task6` tokens × `BEDROCK_PRICING`, matching the caption | yes |
| 6 | \S1 contribution 4 | 297 audited detections, no tier stated | Same number, subset tier | `TODO_remaining.md` item 3's own rule | yes |
| 7 | \S2 | HiPS in the "learned" cluster; Liu 2022 supporting the ICL sentence; ELOF for "no national framework spans the age band" | see `REVIEW_references_pass2.md` | yes |

Item 1 is the only one that changes a claim's substance, and it weakens it
only slightly: the identity of the affected elements is stable across two of
three runs rather than three of three. Items 2, 3 and 5 are wrong figures with
no downstream effect. Items 4, 6 and 7 are stale or mis-scoped sentences.

One thing outside the paper: `CLAUDE.md`'s "Where `age_band` destabilizes at
scale" section, and `task13_20260907/findings.md`, both stated that the band
lands on the same elements every time, inferred from the count alone. At the
author's request both now carry a dated correction; the findings file keeps
its original sentence with a superseding note, and the manifest's finding text
carries the same correction inline.

## 3. Claims I could not verify

| Claim | Where | Why not | What I did |
|---|---|---|---|
| Kentucky's heading buckets "hold only a small fraction of all blocks" | \S5.2 | Still qualitative, attributed to engineering notes, footnoted. The run-1 extraction has 1,741 blocks, matching CLAUDE.md's figure, so the bucket count could now be recomputed with no model call. | Left as pass 1 left it. |
| "roughly a quarter of the elements received a different code" (3 KY runs, 2026-08-01) | \S5.2 | No recorded artifact; qualitative and attributed. | Left. |
| Trimmed tier retains every standard | \S3, \S6.7, \S7.2 | Author-attested. \S6.8 now corroborates it for Kentucky in the direction of density (277 verified elements across 52 pages) but no golden was built from the published PDF independently of a run, so it remains attested rather than measured. | Left as stated; the attribution is explicit. |
| Dropped standards at the trimmed tier are exactly the ones given a narrower age band | \S6.8 | Stated in `task13 findings.md`; I did not re-derive it from the parse outputs. | Left; the recording says it. |
| The trimmed-tier goldens' 277 elements contain no element that no run emits | \S6.8, \S7.3 | Unknowable from the goldens, by construction; the paper says so at every site. The cold read (TODO item 5) is the only route. | Left; the ceiling language is present everywhere the figure appears. |
| The three 09-07 runs used four detection batches | \S6.8 | Not in the recording; the batch count is a deterministic function of the extraction, and recomputing it gives 18 chunks and 4 batches for each run. | Treated as verified by recomputation, noted here because the recording does not carry it. |
| Whether an unrecorded Arizona full run ever happened | \S7.2 | Same as pass 1. | Left. |

## 4. Build report

| | Baseline (2026-09-19, before edits) | After this pass |
|---|---|---|
| Exit code | 0 | 0 |
| Pages | 28 | 28 |
| Undefined references / citations | 0 | 0 |
| Overfull boxes | 0 | 0 |
| Underfull boxes | 27 | 25 |
| Font warnings | 1 (`T1/zi4/m/it`, pre-existing) | 1 (same) |
| Abstract copy | 1,888 chars, matched LaTeX | 1,864 chars, matched LaTeX |

Pages 9, 10, 11, 14, 25 and 27 (Figure 1, Tables 2--5, 7, 8, 10, 11 and the
goldens appendix) were rasterized after the rebuild; every float renders
inside its column. The two remaining badness-10000 underfull boxes at
`appendix_goldens.tex` lines 29--32 are the long `\paragraph` headings of the
goldens appendix, which justify across the column; they were present in the
baseline and are cosmetic.
