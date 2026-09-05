# Claim review — every number in the paper traced to its artifact

Reviewed 2026-09-04 against the current freeze (`outputs/08-26-26-2`,
`code_version_hash 14374dba`, `RUN_TAG = 20260826`). Method: re-ran all three
generators and diffed the committed tables (byte-identical before my caption
edits); then read the JSON behind every prose number rather than the
`findings.md` that summarizes it. `per_level` recall was recomputed as
`tp/(tp+fn)`; `main.log` was read with `grep -a`; figure pages were rasterized
with Ghostscript and inspected.

Three sections follow: verified, wrong (with the correct value and its source),
and could-not-verify. A fourth lists the consistency defects that were not
numbers but would have misled a reader, since the brief asked for those too.

---

## 1. Claims verified

### Headline quality (Tables 2–3, abstract, §1, §9, §10)

| Claim | Artifact | Verdict |
|---|---|---|
| Detector recall 1.000 at every hierarchy level in all six states | `task1_20260826/summary.json`, `task2_20260826/summary.json` → `per_level` | ✅ `fn = 0` at every level in every state (AZ 1/1/1/2 tp, CA 3/3/5/14, CO 2/2/–/3, TX 1/2/1/4, NV 3/12/7/24, KY 3/5/10/26). |
| Code accuracy 4/4, 25/25, 7/7, 8/8, 46/46, 44/44 | same | ✅ as recorded (but see §2 on NV's 46/46 as a point value). |
| Verified precision 100/100/100/100/98.1/100 | `task1b_fp_audit_SIGNED.json`, `nv_fp_audit_SIGNED.json` | ✅ NV = 1 − 1/52 = 0.9808. Both audits signed by the author, 2026-08-29, hash 14374dba. |
| Exactly one hallucinated element in the corpus (NV `SS.CI.PK3`) | same audits, `counts` | ✅ hallucinated: AZ 0, CA 0, CO 0, TX 0, NV 1, KY 0. |
| Parser coverage 100% everywhere; fully correct 17/18, 21/21, 9/9, 8/8, 24/24, 26/26; AZ field accuracy 99.7; 0 id collisions | `summary.json` → `parser` | ✅ |
| Verified precision "0.997" (§1) and "0.9966" (§8.3) | derived | ✅ 296/297 = 0.99663 — consistent with **297** in-scope detections (see §2). |
| Detector golden sizes 5/25/7/8 vs detection sets 67/122/61/33 (§9.3) | `task1_20260826/findings.md`; `per_level` tp+fp | ✅ |
| NV golden 46 content-exhaustive, 52 in-scope detections, 5 reprinted headings; KY 44 vs 44 detection-exhaustive | `task2_20260826/findings.md`; NV audit verdicts (5 × `real_repeat_of_matched`) | ✅ |
| AZ direct-path 67 vs batched 65 (§9.5) | `task1_20260826/findings.md` (67); `outputs/08-26-26-2/AZ-detection.json` (65 elements) | ✅ |

### Corpus (Table 1, §1, §3, Appendix D)

| Claim | Artifact | Verdict |
|---|---|---|
| Subset pages 15/13/10/9/15/8, total 70 | `corpus_tiers.json` | ✅ |
| Full 217/68/41/87/98/120; trimmed 65/–/41/71/71/52 | `corpus_tiers.json` | ✅ |
| 262 standards, 0 id collisions, every standard carries an age band | `task8_20260904/dataset_stats.json` | ✅ (age-band coverage 1.0 in the manifest) |
| KY's 52 trimmed pages retain every standard; CO's 41 is the whole Ages 3–5 document; CO 3–5 is drawn from the 187pp volume | `corpus_tiers.json` notes, `task6_20260830/manifest.json` | ✅ as recorded (author-attested, 2026-08-31). **Newly measured:** `paper/results/corpus_page_ranges.json` places the CO 3–5 document at pages 1–2, 113–150, 187 of the birth-to-eight volume, and KY's trimmed tier at published pages 1, 52–102. |

### Method constants (§6)

| Claim | Artifact | Verdict |
|---|---|---|
| 6,000-token Pass-1 budget; floor of 12 blocks per bucket; 2,000-token chunks with 500 overlap; 5-char code cap | `src/els_pipeline/detector.py` lines 30, 78, 117, 230, 236 | ✅ |
| Models: Haiku 4.5 (depth map), Opus 4.6 (detection), Sonnet 4.6 (parsing) | `config.py:15-21`; every manifest's `models` block; CloudWatch cross-check recorded in `task5_20260830/manifest.json` | ✅ |
| Batches: ≤5 chunks, ≤3 domains, ≤3 concurrent | `config.py:34-35`; figure script | ✅ |
| Validator conditions: no whitespace; indicator extends nearest ancestor; id ends with indicator code; scoped to the leaf | `validator._validate_code_shape` per CLAUDE.md; `tests/unit/test_validator_code_shape.py` | ✅ (by code reading) |
| No `needs_review` field; confidence gates nothing | `grep -rn needs_review src/` → only a docstring stating it does **not** exist; `confidence_distribution.json → gating` | ✅ **Guardrail 2 holds everywhere.** The paper's only uses of "gate"/"threshold" are negations (§6.5, §8.3, §11). |

### Ablation (Table 4, Figure 3, §8.2)

| Claim | Artifact | Verdict |
|---|---|---|
| Pooled off-arm recall: domain 1.000, strand 0.920, sub-strand 0.833, indicator 1.000 | `task3_20260826/ablation_comparison.json → aggregate.pooled_by_level` | ✅ |
| Only CO and KY lose recall; TX 8/8 → 5/8 code on identical detections; NV 46/46 → 44/46 | `task3_20260826/findings.md` per-state table | ✅ |
| KY level counts, on arm = golden 3/5/10/26; off arm 4/10/6/26 in the recorded run | Figure 3 is generated from `review_detector/KY/KY-detected.json` (on) and `review_detector_off/KY/` (off) | ✅ |
| Repeats: off-arm recall CO 0.71–0.86, KY 0.89–0.98; KY off strand 8/7/10, sub-strand 7/9/6; direction never reverses; on arm 1.000 in all 18 runs | `task3_stability_20260823/stability_analysis.json`, `findings.md` | ✅ **but at hash `288c64f1`, not the current one** — see §2, item 5. |
| One regression case unstable (CO-NO-SUB-STRAND FAIL/FAIL/PASS) | same | ✅ in prose; **the generated caption contradicted it** — fixed, see §4. |

### Baseline (Table 5, §8.3)

| Claim | Artifact | Verdict |
|---|---|---|
| Pooled: domain 13/13 both; strand 6/25 (0.240); sub-strand 16/24 (0.667); indicator 10/73 (0.137); mean 1.000 vs 0.500 | `task4_20260826/baseline_comparison.json → aggregate` | ✅ |
| NV 0.065 → 0.522 with widened numbering; KY 0.295 → 0.409 with mid-line labels | `brittleness_probe` | ✅ |
| 43 of NV's 46 and 31 of KY's 44 never emitted; 0 found-at-wrong-level | `per_state` (matched 3 and 13; `found_but_wrong_level` 0) | ✅ |
| AZ raw precision 0.500 rule vs 0.417 LLM | table row | ✅ |
| Baseline verified precision 1.000 in five of six states, CA 0.9432 with 5 flagged rows that are column fusion | `baseline_fp_audit.per_state` (CA 88 in-scope, 5 hallucinated; the five titles are each a sub-strand name fused with a column header and an indicator) | ✅ |

### Confidence (Table 6, §8.4)

| Claim | Artifact | Verdict |
|---|---|---|
| 379 elements; 5 distinct values {0.90, 0.92, 0.95, 0.96, 0.97}; 357 (94.2%) ≥ 0.95; 22 in 0.80–0.94; 0 below 0.80 | `task8_20260904/confidence_distribution.json → direct_path.overall` | ✅ |
| Indicators 246/263 = 93.5% ≥ 0.95; earlier freeze 89.7% (236/263) | same; `task8_20260904/manifest.json → what_changed` | ✅ (the 89.7% is deliberately quoted *as* the superseded freeze's value, which is the honest use of a superseded number) |
| Three states with no sub-0.95 element (CA, CO, TX); KY 16 of 44 below | `by_state` (CA min 0.95; KY histogram 0.92 → 16) | ✅ |
| Hallucination is the unique 0.90; nothing correct below 0.92; holds across 18 same-configuration runs / 1,157 elements | `separation_stability` (n_samples 18, elements 1157, 1 distinct element below 0.9) | ✅ (the LaTeX *comment* still says 14 runs / 966 — a stale comment, not prose) |
| All 39 real-split-title rows ≥ 0.95; 5 reprinted; 135 matched; 117 real-unannotated | `by_audit_verdict` | ✅ |

### Stability (Table 7, §8.5)

| Claim | Artifact | Verdict |
|---|---|---|
| Detector n=5, parser n=6 (frozen arm folded in); 304 identities / 5 unstable / 0.0164; 201 / 9 / 0.0448 | `task5_20260830/stability_analysis.json` | ✅ |
| Stable states: CA, CO, TX, KY (detector); AZ, CO, TX, KY (parser) | same | ✅ |
| CA parser: 12 malformed codes `ELD.1.0.VOCA.Foundation 1.1.BROA` in 2 of 5 comparisons, all whitespace-bearing | same (`indicator.code` 12, `standard_id` 12) | ✅ |
| NV sizes [54,54,54,53,53]; the indicator lost on the day boundary; runs 1–3 one session | same; `manifest.json → runs` | ✅ |
| NV recorded 46/46 vs repeats 44, 45, 44, 44, 44; `n_detected` 52 vs 54/54/54/53/53 | `task5_20260830/reports/detector_run{1..5}_NV.json` (`code_matches` 44/45/44/44/44) | ✅ |
| AZ run 1 alone under-detected (74 vs 77); graded recall 1.000 every run | `per_state.AZ` | ✅ — and the three missing sub-strands (Attachment, Respect, Social Interactions) are each detected exactly once in runs 2–5, so "duplicate headings its contents page reprints" is a plausible but not directly evidenced characterization (see §3). |

### Scale (Table 8, §8.6)

| Claim | Artifact | Verdict |
|---|---|---|
| KY 52pp / CO 41pp; 18 / 17 chunks; 4 detection batches; 9 parse batches; 363→329 (34) and 390→300 (90) | `task6_20260830/manifest.json → executions, batching_evidence` | ✅ |
| Tokens per stage and totals; 45 calls each; wall clock 13m19s / 9m52s | `per_stage_metrics`, `executions` | ✅ |
| USD rows: KY 0.0143 / 2.6211 / 1.7724 = 4.41; CO 0.0217 / 2.2945 / 1.6999 = 4.02 | recomputed from tokens × `BEDROCK_PRICING` (0.001/0.005, 0.005/0.025, 0.003/0.015 per 1K) | ✅ arithmetic checks to four decimals |
| No throttling, no empty chunks, no validator rejections, 17/17 tasks | `integrity_checks` | ✅ |
| Pass-1 depth counts KY 4 / CO 3 match goldens | `integrity_checks.pass1_depth_map` | ✅ |

---

## 2. Claims that were wrong (corrected value and source)

| # | Where | As written | Correct | Source | Fixed? |
|---|---|---|---|---|---|
| 1 | Abstract, §1 contribution 4, §9.3, §10 | "a manual audit of all **296** in-scope detections" | **297**. In-scope = matched + audited extras: AZ 5+7, CA 25+97, CO 7+35, TX 8+17, NV 46+6, KY 44+0 = 297. | signed audits' `counts`; `confidence_distribution.json → by_audit_verdict.in_scope_detections_audited: 297` | ✅ all four places. Verified precision is unchanged (296/297 = 0.9966 → "0.997"). |
| 2 | Table 8 caption; §8.6 prose | depth-map pass is "under 0.4% of each run's cost … about 1.4 cents on Kentucky"; detection "roughly 60%" | KY 0.32%, **CO 0.54%**; detection KY 59.5%, CO 57.1%. | recomputed from `per_stage_metrics` × pricing | ✅ caption now computes the shares at build time ("0.3–0.5%", "57–59%"); prose says 0.3–0.6% and 57–60%, 1.4¢ KY and 2.2¢ CO. |
| 3 | Table 7 caption; §8.5 "Why the runs were split across days" | NV detector output "identical"/"byte-identical" across the three same-session runs | The element **set** was identical (54/54/54), but run 2 emitted the Science domain's code as `S` while runs 1 and 3 emitted `Science`. | `task5_20260830/stability_analysis.json → detector.per_state.NV.examples[0]` | ✅ both now say "same element set … one of them differing only in the Science domain's code". |
| 4 | §8.5 | NV domain code "drifts between the document's `S` and an abbreviation of its title" | It drifts between `S` and the full name **`Science`** (the `SCIE`/`TECH` abbreviations belong to older runs recorded in CLAUDE.md, not to Task 5). | same | ✅ |
| 5 | §8.2 ablation prose | Repeats "leave domain … untouched at 3" — stated in the same paragraph as Figure 3, whose off arm shows **4** domains | Both are true of different recordings: the repeats (hash `288c64f1`, old Pass-1 sampler, `outputs/08-22-26-4`) held domain at 3; the current recording (`14374dba`) emitted 4. The paragraph mixed them without saying so. | `task3_stability_20260823/manifest.json` (hash, outputs dir); `task3_20260826/review_detector_off/KY/` | ✅ prose now separates the recorded run from the repeats, states the repeats' code version, and notes the recorded run's recall (CO 0.86, KY 0.89) falls inside the repeats' ranges. Table 4's caption now says the same. **This is a superseded-folder number reaching the draft**, as the brief warned; it is legitimate only when labeled, which it now is. |
| 6 | Table 4 caption (generated) | "No regression case changed status in any run." | CO-NO-SUB-STRAND went FAIL/FAIL/PASS in the repeats the caption itself cites; the prose two paragraphs later says so. The generator only reported cases that *also* failed in the single recorded run, and at `20260826` that case passed. | `stability_analysis.json → aggregate.categorical_cases_unstable_across_runs` | ✅ generator fixed; caption now names the case and its statuses. |
| 7 | §6.3 | "requiring it to would corrupt **fifteen of fifteen** Nevada standards" | The current NV parser golden has **24** standards, and all 24 have a sub-strand code that does not extend the strand code. "Fifteen" is the size of a superseded golden quoted from CLAUDE.md. | `evaluation/ground_truth_parser/NV.json` (24 of 24) | ✅ now "every one of the 24 annotated Nevada standards". |
| 8 | §1 introduction | "K–12 academic standards … have machine-readable distribution formats [CASE, ECS 2024 governance]" | The ECS resource is a 50-state comparison of early-care *governance* models and says nothing about K–12 formats. | fetched ecs.org page | ✅ ECS now supports "more than fifty jurisdictions issue them independently"; the formats claim cites ASN and CASE. |
| 9 | §8.5 | "an earlier investigation of a different parser defect found it in roughly one run in six" | That is one graded run of six *within a single invocation*; the broader record is **10 of 20** cached KY parser runs across 8 code versions. "One in six" understates the historical rate by a factor of three. | `tasking/arxiv_paper.md` (Task 2 status), `task2_20260816/heldout_evidence.json → ky_direct_path_cache_runs` | ✅ prose now gives both figures. |
| 10 | Figure 1 caption vs §5 | "eight serverless stages" vs "a six-stage pipeline" | The figure's own numbering runs 1–8 because the two batched stages occupy two positions each; `handlers.py` has ten handlers. | `make_architecture_figure.py` cluster labels; `handlers.py` | ✅ caption reconciled. |

Three of these (1, 2, 3) are false statements of fact; the rest are stale or ambiguous. None changes a conclusion.

---

## 3. Claims I could not verify

| Claim | Where | Why not | What I did |
|---|---|---|---|
| "eleven of 44 elements received a different code on at least one run" (3 KY detector runs, 2026-08-01) | §6.2 | No recorded JSON or command; lives only in CLAUDE.md. Re-measuring costs three live Opus runs over KY. | Rephrased qualitatively ("roughly a quarter … from the project's design notes rather than a paper artifact"); exact figure kept in the LaTeX comment. **Recommend recording it** (three `eval_detector --state KY --no-cache` runs, ~60K Opus tokens) if the author wants the number back. |
| "six heading buckets hold nineteen of 1,741 blocks" (KY full document) | §6.2 | Same; the 1,741-block extraction was a 2026-08-24 pipeline run and is not in `paper/results/`. It *could* be recomputed deterministically (no Bedrock) from a stored KY trimmed extraction with `detector._layout_bucket_key`, but no such extraction is recorded under `paper/results/`. | Rephrased qualitatively; exact figure kept in the comment. **Cheap to record**: a 20-line script over the Task 6 KY extraction, no model call. |
| Trimmed tier "retains every standard" | §3, §8.6, §9.2, Table 8/9 captions, `corpus_tiers.json` | Author-attested (Emily, 2026-08-31), corroborated only indirectly by page-coverage density (50/52 and 37/41 pages carry elements). No golden reaches the trimmed tier, so it is not measured. | Left as stated; it is clearly attributed. The new `corpus_page_ranges.json` shows AZ's trimmed tier keeps 65 scattered pages of 217 and NV's keeps 1, 3, 16–84 of 98 — consistent with removing non-standards matter, but not proof. Grading KY's exhaustive golden inside the trimmed run (the paper's own proposed next step) would settle it for one state. |
| AZ's detector instability is "the duplicate headings its contents page reprints" | §8.5 | Task 5's AZ examples are three sub-strands (Attachment, Respect, Social Interactions) *missing* from run 1 and present once in runs 2–5. That is a presence change, not a duplicate; the listing-page duplication is documented for other AZ sub-strands (Vocabulary, Concepts of Print, Book Handling) in the ablation findings. The two may be the same phenomenon but the JSON does not show it. | **Applied 2026-09-04 (author's request):** §8.5 now reads "alternates on whether it emits three of its sub-strands (present in four runs, absent in one), which changes output size without touching any graded element", which is exactly what the JSON shows. |
| Aggarwal et al. exploit "internal arithmetic structure for validation" | §2.2 | Abstract confirms hierarchical tabular fiscal data; the arithmetic-validation detail is not in the abstract and I did not read the full paper. | Left; noted in REVIEW_references.md. |
| The three NeurIPS page ranges (Brown 2020, Wei 2022, Liu 2022) | bibliography | Proceedings pages and dblp do not print page numbers. | Left; noted in REVIEW_references.md. |
| Detection "is the only stage invoked once per chunk" | §6.4, §8.6 | True of the LLM stages as drawn (parsing is per domain-batch, depth map once per document). Verified by reading `detection_batching.py`/`parse_batching.py` call structure via CLAUDE.md, not by instrumented count. | Left. |
| "no document as large as Arizona's 217-page publication has been run end to end" | §9.2 | True of the recorded artifacts (only KY and CO trimmed runs are recorded). Whether an unrecorded AZ full run ever happened I cannot tell from `paper/results/`. | Left. |

---

## 4. Guardrail sweep (the brief's named checks)

| Guardrail | Result |
|---|---|
| 1 — corpus tier on every table | ✅ Every generated table carries the tier in its comment header **and** its caption. Table 8 is the sole `_trimmed` table and its caption says what the tier means in both directions. The new Table 10 (retained pages) describes the tiers and carries no quality number; its header says so. |
| 2 — confidence gates nothing | ✅ No review-gate language anywhere; every mention of "gate"/"threshold" is a negation. `needs_review` absent from `src/`. |
| 3 — trimming disclosed with retained page ranges | ⚠️ **Was not satisfied.** §3 was an empty stub (table + TODO), and no artifact recorded retained page ranges; the introduction promised §3 would state them. **Now satisfied**: `paper/analysis/corpus_page_ranges.py` recovers the ranges from the PDFs (every tier page matched a published page, 0 unmatched), records them in `paper/results/corpus_page_ranges.json`, and they render as Table 10 in Appendix D; §3 now has prose that states the tiers, the favorable-preprocessing framing, and the CA/CO/NV naming the outline required. |
| 4 — no unmeasured Medium numbers | ✅ The "85–90%" claim is quoted only to say it does not reproduce (93.5%). |
| 5 — no invented fine-tuning cost | ✅ Argued on no-labeled-corpus grounds only. |
| 6 — every number regenerable | ⚠️ Three §6 numbers were not (now rephrased, see §3 above). The ablation repeats are regenerable but from a **different code version** than the point values, which the paper now states. |
| 7 — generalization reported honestly | ✅ NV 46/46 is never quoted as stable in prose. **But Tables 2 and 5 printed `46/46` with no caveat**; Table 2's caption now states "NV 44–45/46 across 5 repeat runs against 46/46 recorded", computed from the Task 5 reports at build time. Table 5 (baseline) still prints 46/46 for the LLM arm; its caption points at Table 2 and its conclusion does not depend on the cell. |
| 8 — raw precision never reported as quality | ✅ Raw precision appears only in Table 5 (both arms, with the caveat) and in §9.3 explicitly *as* annotation coverage. KY is the only state described as having a real hallucination rate. |
| Superseded folders | ⚠️ Two superseded-freeze numbers are used: the 89.7% confidence figure (correctly labeled as the earlier freeze) and the Task 3 repeat ranges (hash 288c64f1, `outputs/08-22-26-4` — now labeled). The AZ ×5 figure the brief mentions is gone. |
| `_trimmed` ≠ coverage | ✅ Never relapses; §3, §8.6 and §9.2 all say the page ratio is not a coverage fraction. |

---

## 5. Build report

| | Before | After |
|---|---|---|
| Errors | 0 | 0 |
| Undefined references / citations | 0 | 0 |
| Overfull `\hbox` | 4 (Table 2 9.9pt; Table 4 63.9pt; two bibliography URLs 101.6pt and 15.1pt) | **0** — Table 2 set `\small`; Table 4's headers shortened; `xurl` loaded so the two agency URLs break |
| Overfull `\vbox` | 0 | 0 |
| Pages | 27 | 28 (§3 prose and the retained-pages table) |
| BibTeX warnings | 1 (empty year, `ncecqa_elgs`, pre-existing and deliberate) | 1 (same) |

Tables regenerate byte-identically from `paper/results/` except for the caption
changes described above, all of which are produced by the generator, not by
hand.
