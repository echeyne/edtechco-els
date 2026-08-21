# arXiv cs.CL Paper — Task Plan

> **Working document.** A prioritized, self-contained task list for producing and submitting a technical paper to arXiv under **cs.CL**. Intended to be worked through one task at a time with Claude Code over multiple sessions. Each task is written to be actionable from a cold start.

## Why this exists

The ELS Platform's method and results have never been written up, and the measurements a paper needs have never been consolidated. The evaluation harness can produce metrics, but no results table exists; there is no comparison against any baseline; and the strongest claim available — that the LLM-first approach *generalizes* rather than overfitting the golden states — has never been tested on a fully-annotated held-out state.

**Goal:** an arXiv preprint (cs.CL primary, cross-list cs.AI) framed as **method + system**, leading with the LLM-first methodology (depth-map inference, classify-by-nesting-position prompting, two-stage detection→parsing, serverless batching), with evaluation supporting the method claims.

- **Author:** Emily Cheyne, Founder, EdTech Co. Non-anonymous, ACL template.
- **Rights:** in-paper disclosure only. Prompts, canonical schema, and representative golden examples go in appendices under retained copyright. **No open-source release** of code or dataset. arXiv license = the minimal *"arXiv.org perpetual, non-exclusive license to distribute"*.
- **Working title:** *Classify by Position, Not by Label: LLM-Driven Extraction of Hierarchical Structure from Fragmented US Early Learning Standards*

Full plan (framing, outline, formatting requirements): `~/.claude/plans/i-want-to-create-silly-pnueli.md`. Design guidance this executes against: the "Design direction" section of [CLAUDE.md](../CLAUDE.md).

## The non-negotiable guardrails (apply to EVERY task)

These were established by verifying the live tree during planning. Several contradict what the repo's docs used to say. Violating any one of them puts a false claim in a public, permanently-archived paper attached to Emily's name and NIW portfolio.

1. **State the corpus tier for every table.** All current eval numbers come from 9–15pp `_only_subset` PDFs — *not* full documents. No reader may mistake a subset metric for a full-document one.
2. **Confidence gates nothing.** The detector emits a `confidence` float on `DetectedElement`, but nothing thresholds it and there is no `needs_review` field anywhere in `src/`. Human verification is a **separate** concept — `human_verified` / `verified_at` / `verified_by` on all four levels (`infra/migrations/005_add_verification_columns.sql`). Never describe a confidence-based review gate; older doc revisions did, and were wrong.
3. **Disclose the manual PDF trimming.** Front matter, introductions, and acknowledgements were removed to produce the `_trimmed` tier. This is favorable preprocessing and must be stated with retained page ranges, not buried.
4. **No unmeasured numbers from the Medium articles.** `documentation/medium-articles/01..05` are prose seed only. Every factual/numeric claim from them must be re-verified against code or re-measured — notably "85–90% of indicators at 0.95+ confidence."
5. **Never invent a fine-tuning cost to compare against.** Argue cost on **no-labeled-corpus** grounds — the dominant cost of the fine-tuning alternative is annotation, not compute — and report real measured per-run cost.
6. **Every number must be regenerable.** Record each result as JSON under `paper/results/` alongside the exact command that produced it, plus the model IDs and `outputs/` run used. Tables regenerate from those files; they are never hand-typed.
7. **Report generalization honestly.** If the held-out states collapse, that is the most interesting finding either way — it becomes a stated limitation, not a quiet omission.
8. **Never report the detector suite's raw "precision" as detector quality** — *unless that state's golden is verifiably exhaustive.* (Established by Task 1, decided 2026-07-17; the exhaustive-golden carve-out added by Task 2, 2026-08-16.) **Kentucky is the one state that qualifies today**: 44 golden elements against 44 in-scope detections with identical per-level counts and zero unmatched detections, so its raw precision 1.000 is a real hallucination rate. Establish exhaustiveness from `heldout_evidence.json`'s `golden_is_exhaustive` before invoking this — never assume it. Every other state still follows the rule below. The detector goldens are partial spot-checks (5–25 elements) while the detector emits 9–122 elements inside annotated domains; the suite counts every unmatched in-scope detection as a false positive even when it is correct document content, so raw precision mostly measures annotation coverage (verified: all of AZ's "FPs" are real unannotated elements). The paper reports **recall (per-level) from the suite** plus a **verified precision / hallucination rate from the manual FP audit (Task 1b)**. Decision made: no exhaustive golden extension, no further PDF trimming — trimming smaller invalidates the frozen measurement chain and weakens the eval without fixing the artifact.

## How to run evaluations

Use **`outputs/08-16-26/`** — it supersedes every earlier `outputs/` folder. Cache is on by default; use `--no-cache` for final recorded numbers.

> **Depth map is healthy in this folder (verified 2026-08-16).** The old warning about the detection-batch-preparer role lacking `bedrock:InvokeModel` applied to `outputs/07-16-26-2` and was fixed and deployed 2026-07-17. `outputs/08-16-26` shows the post-fix signature on the state that diagnoses it: CO detection is 61 elements with **0 sub_strands** (the pre-fix run was 93 with 9), and CO parser coverage is 1.000 with field accuracy 1.000. All four states' depth maps also PASS on a fresh direct-path run.

```bash
source venv/bin/activate
python -m evaluation.eval_detector --state CA
python -m evaluation.eval_detector --state CA --stability-runs 3   # LLM-determinism check
python -m evaluation.eval_parser --detection-dir outputs/08-16-26 --state CA
```

- Detector grades against `evaluation/ground_truth_detector/{STATE}.json` (flat element list, run on `{STATE}-extraction.json`).
- Parser grades against `evaluation/ground_truth_parser/{STATE}.json` (nested `NormalizedStandard`, run on `{STATE}-detection.json`).
- The two golden sets are **decoupled** — a change to one suite does not imply a change to the other.
- The `evaluation-runner` skill runs both suites and auto-runs additional states.

## Key background (read before starting)

- **Corpus has three tiers**, not two: full → `_trimmed` (front matter removed) → `_only_subset` (~1–2 domains, fully annotated, cheap to iterate on).

  | State | Role | Full | `_trimmed` | `_only_subset` |
  |---|---|---|---|---|
  | AZ | golden | 217 | 65 | **15** |
  | CA | golden | 68 | — | **13** |
  | CO | golden | 187 (b–8) / 41 (3–5) | 41 | **10** |
  | TX | golden | 87 | 71 | **9** |
  | NV-2023 | held-out | 98 | 71 | **15** |
  | KY | held-out | 120 | 52 | **8** |

  (All page counts re-verified with PyMuPDF 2026-08-16. KY's subset is 8pp, not the 9 previously recorded here.)

- **The held-out canary is NV-2023** (`nevada_standards_2023_only_subset.pdf`, multi-domain). **Not** NV-SES-2025 — that document is Social-Emotional Standards only, a single domain, and far too narrow to support a generalization claim.
- **California's source is the PTKLF "at a glance" document** (`ptklfataglance.pdf`, 68pp) — confirmed correct, not an error in `standards/standards_tracking.md`. Name it precisely in the paper.
- **Batched vs. direct path.** The detector eval runs the direct path; the parser eval and production run on the batched path's output (`detection_batching.py`, `parse_batching.py`). **Measured 2026-08-16:** at the `_only_subset` tier every state produces ≤5 chunks (AZ 4, CA 3, CO 4, TX 3, NV 5, KY 3) against `MAX_CHUNKS_PER_BATCH=5` and ≤3 domains against `MAX_DOMAINS_PER_BATCH=3`, so **both** batching layers run as exactly one batch per state — the Map has a single iteration and the merge is a no-op. Detection consequently converges almost exactly (CA/CO/TX identical, AZ differs by two footnote characters), but that is structural, not evidence. Parsing does **not** converge (12 of CA's 94 `standard_id`s differ). The batching claim needs a full-document run (Task 6).
- **Model assignment is deliberate** — Haiku 4.5 for the depth map, Opus 4.6 for detection, Sonnet 4.6 for parsing (`config.py:15-21`). The principle is "cheapest model that suffices per stage"; the model-tier ablation (Task 7) is its evidence.
- **Cost data already exists.** `PipelineRunMetrics.summary()` (`src/els_pipeline/metrics.py`) gives per-stage tokens/cost/latency/call-counts; the `els-pipeline-metrics-{env}` CloudWatch dashboard (`infra/cdk/lib/constructs/pipeline-dashboard.ts`) is the cross-check. `BEDROCK_PRICING` rates are hardcoded as of April 2026 — re-verify and cite the date.

---

## Tasks (work in order — lowest number first)

Priority = risk first. Tasks 1–2 are the two real risks: Task 1 validates the measuring instrument everything downstream depends on, and Task 2 is the long pole that gates the paper's strongest claim. Tasks 3–4 are the must-have ablations that turn central claims from assertions into evidence. Task 6 rescues the batching/scale claim. Tasks 9–13 are the writing chain; Task 9 has a long lead time and should start early in parallel.

### Task 1 — Run headline evals on the 4 golden states and sanity-check every metric

> **STATUS: DONE (re-run from scratch) 2026-08-16 against `outputs/08-16-26`.** Results in **`paper/results/task1_20260816/`** — narrative `findings.md`, consolidated numbers `summary.json`, provenance + regenerating commands `manifest.json`, raw suite reports `detector_golden4.json` / `parser_golden4.json`, path comparison `direct_vs_batched.json`. The July results (`paper/results/task1_*`) are **superseded** — they graded code that no longer exists (`derive_code_from_title` 2026-08-01; rule 4's code-lookup clause, `_anchor_parent_chain`, `disambiguate_colliding_standards`, `models._blank_to_none` 2026-08-15) — and are retained only for the reproducibility narrative.
>
> **Headline:** detector recall **1.000 at every level in all four states**, code accuracy 4/4 · 25/25 · 7/7 · 8/8, description accuracy 4/4 · 14/14 · 4/4 · 3/3, depth map PASS ×4, all 11 detector regression cases PASS. Parser coverage **1.000** ×4, field accuracy 0.997 / 0.984 / 1.000 / 1.000, 0 `standard_id` collisions, all 8 parser regression cases PASS.
>
> **Two instrument defects found and fixed:** (a) `CA-EARLY-LATER-DISTINCT-IDS` and `TX-PK3-PK4-DISTINCT-IDS` had been passing on an **empty population** ever since the disambiguator moved inside the indicator code — repaired in `evaluation/regression_checks.py`, now 39 and 10 real variant groups; (b) CA detector golden `version_year` was 2008 (correct: 2021) and the CO detector golden had `annotator`/`annotation_date` swapped. All repairs verified score-neutral.
>
> **Open for Emily** (detail in `findings.md`, evidence in `parser_code_label_variance.json`): (1) **NEW, blocking** — the parser intermittently keeps the structural label in CA indicator codes (`ELD.1.0.VOCA.Foundation 1.1.DISC` instead of `…VOCA.1.1.DISC`), writing **12 malformed Aurora primary keys** when it fires. Confirmed on **current** code (`code_version_hash 3b445471`, which the run cache records per artifact): 2 byte-identical hits in 18 end-to-end runs; **unbiased rate ~6%** (1 in 17 post-trigger; 95% CI ≈ 0.2–30%, so call it "a few percent"). Ruled out: stale deploy, model override, direct-vs-batched prompt differences, and the three-proficiency-column shape (chunks 7/8/9 share it and never fail). **Source component NOT localized** — 8 instrumented runs and 49 per-chunk samples failed to catch one. **Recommended: add a document-agnostic shape guard outside `parser.py`** (validator or db write path) that blocks a code segment containing whitespace or a leading label word and logs raw-vs-final when it fires — protecting Aurora now and localizing the defect for free at the next natural occurrence. (2) ~~Two AZ parser-golden cells~~ **RESOLVED 2026-08-16 — Emily confirmed both were annotation-error corrections; both stand.** (3) How many detector runs back the paper's recall number — **DECIDED: 5** (see Task 5). (4) ~~CO parser golden annotator/date swap~~ **fixed by Emily 2026-08-16.**
>
> Resolved since July: TX indicator-description convention (the parser now emits `None`; TX field accuracy 1.000), and the production depth-map IAM failure (fixed 2026-07-17, healthy in `outputs/08-16-26`).

**Risk:** HIGH — these metrics have never been consolidated. If a matcher doesn't count what its name implies, every downstream table is wrong. **Do this before any table or prose depends on the numbers.**

1. Run both suites on AZ, CA, CO, TX against `outputs/07-16-26-2`.
2. **Scrutinize before trusting.** Confirm each matcher counts what its name implies; that precision/recall denominators are the annotated slice and not the whole document; that depth-map accuracy is graded standalone from per-chunk extraction; that domain-scoped matching actually disambiguates same-titled strands (CA's ELD/FLD share strand and sub_strand titles).
3. Expect surprises. Investigate anything that looks too good as hard as anything that looks bad.

**Deliverable:** per-state precision/recall/F1, per-level breakdown, confusion matrix, age-band drops, depth-map accuracy, parser coverage/field-accuracy/ID-uniqueness — recorded as JSON in `paper/results/` with generating commands.

---

### Task 1b — Manual false-positive audit → verified precision (hallucination rate)

**Risk:** medium. **Decided 2026-07-17** as the resolution to Task 1's precision finding (guardrail 8). This produces the paper's actual detector-precision number; without it the paper has recall only.

**Method:** audit every unmatched in-annotated-domain detection ("extra") from the recorded detector run — ~165 verdicts total (AZ 5, CA ~97, CO ~40, TX ~22; enumerated in `paper/results/task1_review_detector/{STATE}/{STATE}-review.json` under `extra_in_detected`). Each verdict is binary with a reason: *real document content at the correct level* vs *hallucinated / misclassified / malformed*. Claude drafts the first pass against the source subset PDFs; **Emily verifies and signs off as annotator of record** (this also cures the circularity of same-model-family drafting). Paper methodology sentence: "all unmatched in-scope detections of the recorded run were manually audited by the author."

1. **Sequencing:** run AFTER the pipeline redeploy settles which frozen outputs the paper publishes against — the audit is tied to one frozen detector run (currently the Task 1 recorded run at commit `0d2f887`). If Task 1's detector run is re-recorded post-redeploy, audit that run instead.
2. Record as `paper/results/task1b_fp_audit.json`: per-element `{state, level, code, title, page, verdict, reason, verified_by}` plus the derived per-state and pooled **verified precision** = matched+verified-real / all in-scope detections, and the **hallucination count** (expected near zero based on the AZ spot-check).
3. Resolve the AZ scoping quirk in the same pass: golden `AZ-IND-LL-1-2-b` sits in the unannotated Language-and-Literacy domain (matched only via the domain-agnostic fallback; its domain excluded from precision scoping). Either annotate the LL domain header in the AZ golden or exclude that indicator from the audit's denominators — state which.
4. ~~**Extend the same audit to NV/KY after Task 2**~~ **DONE (drafted, unsigned) 2026-08-16 — see `paper/results/task2_20260816/heldout_evidence.json`.** NV: 12 verdicts (6 correct re-detections of a reprinted heading, 5 real-but-unannotated, 1 hallucinated) → verified precision 52/53 = 0.981. KY: 0 extras, exhaustive golden → 1.000. Both carry `verified_by: claude-first-pass-UNSIGNED` and need Emily's sign-off. **Adopt the held-out verdict vocabulary for the golden four**, since it separates two things a binary verdict conflates: a *correct re-detection of content the document genuinely reprints* is not the same as *content the golden merely failed to annotate*, and neither is a hallucination.
5. Every verified-real extra is a seed golden entry (title/level/page already captured) — if a reviewer later demands exhaustive goldens, upgrade CA first from this file.

**Deliverable:** `paper/results/task1b_fp_audit.json` + verified-precision numbers, Emily-signed.

---

### Task 2 — Annotate held-out goldens for NV-2023 and Kentucky, then run both suites

**Risk:** HIGH + LONG POLE. This is the main net-new effort and it gates the paper's strongest claim. **Start early; it can run in parallel with Task 1.**

> **STATUS: DONE 2026-08-16 against `outputs/08-16-26`** (code version hash `3b445471` — the same code Task 1 graded, so the two are directly comparable). Results in **`paper/results/task2_20260816/`** — narrative `findings.md`, consolidated numbers `summary.json`, provenance + regenerating commands `manifest.json`, raw suite reports `detector_heldout2.json` / `parser_heldout2.json`, evidence `heldout_evidence.json`, determinism probe `parser_KY_stability5.json`.
>
> **Headline — generalization HOLDS.** Detector recall **1.000 at every level in both states**, depth map PASS ×2, 0 level confusion, 100% domain-scoped matches (0 fallback). Parser coverage **1.000** ×2, 0 `standard_id` collisions. **KY is a clean sweep: precision 1.000, code 44/44, description 26/26, all 3 detector regressions PASS — against an EXHAUSTIVE golden.** NV: code 39/41, description 2/3, 3/3 regressions PASS. Parser field accuracy NV 0.974 / KY 0.983.
>
> **The load-bearing fact: KY's detector golden is EXHAUSTIVE** (44 golden vs 44 in-scope detections, identical level counts, zero unmatched), so KY's precision is a genuine hallucination rate and not the annotation-coverage figure guardrail 8 warns about. NV is the familiar case — ceiling 0.7736, raw precision equal to it to four decimals.
>
> **Step 4 revised — its premise did not survive contact.** Task 1b has never been run (`paper/results/task1b_fp_audit.json` does not exist), so there was nothing to "extend"; and the held-out goldens are dense enough that the audit is nearly free — **12 verdicts for NV, 0 for KY**, vs ~165 for the golden four. All 12 NV verdicts are drafted in `heldout_evidence.json`, each checked against the extraction text: 6 correct re-detections of headings the document reprints, 5 real-but-unannotated (the golden's `test_case_id` gaps confirm they were skipped deliberately), and **1 hallucination**. **NV verified precision 52/53 = 0.981; KY 44/44 = 1.000.** ⚠️ Verdicts carry `verified_by: claude-first-pass-UNSIGNED` — Emily must sign off before the Task 1b methodology sentence is true or 0.981 is quotable. Recommend the paper report *verified precision* for all six states on this one definition; KY needs no audit simply because it has no extras.
>
> **Three defects found, one blocking.** (1) **BLOCKING (and not new)** — KY's parser emitted 4 **unqualified** indicator codes (bare `TCPHS`/`IHFC`/`PARTO`/`PSGPB` instead of `HMW.1.1.TCPHS`), writing malformed Aurora primary keys. Not a detector-input problem (HMW's detector elements are structurally identical to the domains that parsed correctly). **Intermittent and sampling-driven:** 2 of 6 deployed batched runs, and **10 of 20 cached direct-path runs across 8 code hashes**, affecting 2–15 of 26 standards when it fires. Two same-input clusters settle causation (`c335e73a`: 0/6/0/4; `6c193627`: 0/4/0/15). **Do not attribute it to a recent change, and do not cite the direct-vs-batched disagreement as path evidence** — given the within-path variance it is a draw from the same distribution. Same class as Task 1's CA `Foundation N.N` defect but a **different surface form** — Task 1's proposed shape guard would **not** catch it, since `TCPHS` has no whitespace and no label word; the guard needs the **parent-prefix** condition added. (2) NV's two wrong domain codes are the failure CLAUDE.md predicted, mechanism now pinned — and `SS` is correct only **by coincidence**. (3) NV's Science domain description truncates at 2410/3500 chars, costing 3 parser cells. NV's only hallucination is the already-documented `SS.CI.PK3` twin, reproduced with evidence.
>
> **Two instrument defects found; one fixed, one diagnosed and left for Task 5.** (a) **Fixed:** `eval_parser._match_key` keyed identity on a component derived **from the code**, so a malformed code stopped a standard pairing at all and reported it as *dropped* — removing it from `field_accuracy`. KY first graded as coverage 0.846 / **field accuracy 1.000**, a perfect score that existed only because the four malformed rows had been excluded from the denominator of the metric meant to catch them. The suffix is now a tie-breaker applied only when candidates collide. Verified score-neutral on all four golden states (**0 diffs**). (b) **Diagnosed, blocks Task 5:** `measure_stability` compares only its own N probe runs and excludes the graded run, so it reported **0.000 disagreement** for KY in the same invocation whose graded output carried 4 malformed primary keys — see Task 5 for the three fixes needed before its ~60 runs are spent.
>
> No golden was edited during this task. KY's parser golden was annotated against `outputs/08-13-26`; the drift to `outputs/08-16-26` is 3 benign landed changes (documented in `manifest.json`).

1. Annotate `evaluation/ground_truth_detector/{NV,KY}.json` and `evaluation/ground_truth_parser/{NV,KY}.json` per `evaluation/README.md` conventions — ~50 elements per state, verbatim titles/descriptions, `test_case_id` pattern `<STATE>-<KIND>-<N>`.
2. Sources: `standards/nevada_standards_2023_trimmed_only_subset.pdf` (15pp, multi-domain) and `standards/kentucky_all_standards_2021_only_subset.pdf` (9pp). Both already exist.
3. Run both suites on NV and KY; report alongside the golden states.
4. ~~Spot-check annotation is fine (same style as the golden states) — **do not** attempt exhaustive coverage; precision for NV/KY comes from extending the Task 1b audit to their in-scope extras, keeping the generalization table's methodology identical to the golden states'.~~ **SUPERSEDED 2026-08-16 by what the run found.** KY's golden turned out exhaustive, so its precision needs no audit; NV's audit is 12 verdicts and is drafted in `paper/results/task2_20260816/heldout_evidence.json`. Methodological uniformity is preserved by reporting **verified precision** (in-scope detections minus hallucinations, over in-scope detections) for all six states on that one definition — not by keeping every golden equally thin. **Still owed: Emily's sign-off on the 12 NV verdicts, and Task 1b's ~165 verdicts for the golden four.**

**Deliverable:** two held-out golden sets + their scores. Per guardrail 7 — if generalization doesn't hold, report it. **Delivered:** it holds; see the STATUS block.

---

### Task 3 — Build the depth-map on/off ablation

**Risk:** medium. **File:** `detector.py`. This is the evidence for the paper's central "classify by nesting POSITION, not document label" claim — without it, that claim is asserted, not shown.

1. Add an env-flag toggle that neutralizes Pass-1 depth-map inference. **Production default must be unchanged.**
2. Run the detector eval with the flag on and off across the golden states.

**Deliverable:** the on/off delta table in `paper/results/`.

> **Concrete outline (scoped 2026-08-20 against the live tree).**
>
> **The off-state already exists — do not write a second prompt.** `build_detection_prompt(chunk, depth_map=None)` is already a supported path with its own `depth_map_block` else-branch (`detector.py:334-344`); it is the graceful-degradation route used when Bedrock fails mid-run. The ablation only has to force it. That also makes the off-arm honest: it is the system's real no-depth-map behavior, not a strawman built for the paper.
>
> **Two call sites, and BOTH must be flagged or the arms leak.** `infer_depth_map` is called at `detector.py:1470` (`detect_structure` — the direct path, which is what `eval_detector` runs) and at `detection_batching.py:85` (`prepare_detection_batches` — production). Flagging only the first leaves production unablated and any batched comparison meaningless.
>
> **The trap: the eval grades a depth map it did not use.** `evaluate_state` calls `infer_depth_map` a SECOND time purely for grading (Task 1 caveat, `task1_20260816/manifest.json`). With the flag off, that grading call still runs and the report will print `depth-map: PASS` for a run that never had one. Neutralize the grading call under the same flag, or the off-arm's own report contradicts it.
>
> **Budget for a re-record; the flag busts the cache.** `eval_common.code_version_hash` hashes `detector.py` AND `parser.py`, so ANY edit to `detector.py` invalidates every cached detector *and parser* artifact. Tasks 1 and 2 stay behaviorally valid (the flag defaults to current behavior) but stop being byte-reproducible from cache. **Cleanest sequencing: land the flag, then re-record Tasks 1 + 2 and run both ablation arms in one session on the new hash** — one freeze, one hash, no ambiguity about which numbers describe which code. Roughly 1 hour wall time and $25-40 for all six states.
>
> **What to measure.** Recall per level is the headline (the claim is about correct *classification by position*), but the off-arm's most likely failure is level COLLAPSE, which recall alone can hide — a 4-level document flattened to 3 still "finds" the text. Report per-level recall, the level-agnostic confusion re-pairing from `consolidate_task1.py`, and the four-level regression cases (`CA-`/`AZ-`/`KY-`/`NV-FOUR-LEVEL-HIERARCHY`), which are exactly the assertions the depth map exists to satisfy.
>
> **Run the held-out states in both arms too.** NV and KY are where the claim is most falsifiable — NV's namespace skips a level and KY's `Benchmark N.N` is the level most likely to collapse into strand. A depth-map lift that appears only on the states whose prompts were developed against them is a much weaker result than one that appears on the held-out pair.

---

### Task 4 — Build a rule-based baseline and grade it with the detector suite

**Risk:** medium. Closes the "no external baseline" gap — the codebase currently reports no comparison against anything, so the LLM lift is unquantified.

1. Build a regex/heuristic structure extractor (bold/numbering/indentation) under `evaluation/baselines/`.
2. Grade it with the **same** `eval_detector` suite and the **same** goldens, so numbers are directly comparable.

**Note:** this baseline is a deliberate throwaway that lives only in `evaluation/baselines/`. It is not a licence to reintroduce rule-driven logic into `detector.py` / `parser.py` — see the CLAUDE.md design direction.

**Deliverable:** baseline-vs-LLM comparison table in `paper/results/`.

---

### Task 5 — Run stability/determinism passes for both suites

**Risk:** low. Supports the determinism claim; a known reviewer question for any LLM pipeline.

> **N DECIDED 2026-08-16: 5 runs per state per suite.** Budget is not the constraint (~60 runs ≈ $30–40, a few hours of wall time). Two things bind before N does, and both must be handled or the 5 runs measure the wrong thing:
>
> 1. **Repair `measure_stability` first.** It keys elements on `(code, title)` and counts a disagreement only when a matched pair differs in `level`. It is therefore blind to the two failure modes actually observed — title truncation/fusion (July) and the `Foundation N.N` code defect (2026-08-16), the latter because a changed CODE changes the key, so the element silently drops out of the comparison instead of counting against stability. Fix the match key before spending the runs.
>
>    **Half done, and a SECOND blind spot found — Task 2, 2026-08-16.** The key half is fixed on the parser side: `eval_parser._match_key` no longer derives identity from the code, so a run-to-run code change now counts as a field disagreement (`_sig` covers `indicator.code` and `standard_id`) instead of vanishing. The detector-side key still needs the same treatment. **But the remaining defect is about which runs get compared, not what gets compared:** `measure_stability` spawns its own N runs and compares them **only to each other** — the run the suite actually GRADED is never in the comparison. Live proof: `--state KY --stability-runs 5 --no-cache` reported **field disagreement rate 0.000** in the very same invocation whose graded output carried **4 malformed `standard_id`s**. Five probe runs agreed; the graded run three minutes earlier did not. Fix before spending the budget: **(a)** include the graded run in the comparison (N+1 observations, zero extra cost); **(b)** report the observed range and the denominator, not only the rate — "1 of 6 runs differed in 8 cells" and "5 runs, 0 disagreements" are both true of that invocation and only the first is informative; **(c)** treat a 0.000 at N=5 as *not yet a null result* for a defect that fires in a minority of runs. Evidence: `paper/results/task2_20260816/heldout_evidence.json` → `ky_direct_path_cache_runs`, where **10 of 20** cached KY parser runs fired across 8 code hashes.
> 2. **Split the runs across at least two sessions/days.** July's headline finding was that 3 same-session runs agreed perfectly while a 24h-separated run differed by up to 9 elements. Five back-to-back runs risk measuring a falsely low variance.
>
> **Do not inflate N to chase a defect rate.** A per-chunk probe (`build_parsing_prompt` → `call_bedrock_llm` → `parse_llm_response` on one chunk, repeated) costs ~1/9 as much per observation as a full-document run and attributes the failure to a specific chunk — that is the right instrument for rates, and Task 5 is for the headline stability table.

1. `--stability-runs 5` per state, both suites, with `--no-cache` so runs are genuinely independent.
2. Report level-disagreement rate and per-standard field-disagreement rate.

**Deliverable:** stability table in `paper/results/`.

---

### Task 6 — Run a full document through the batched path for cost/latency/scale

**Risk:** HIGH for the system claim. Every current number comes from a 9–15pp subset, which never exercises prepare → Map → merge. Without this, the paper's large-document/batching claim is unsupported by its own experiments.

1. Re-verify `BEDROCK_PRICING` rates in `src/els_pipeline/metrics.py` against current Bedrock pricing and cite the date (Haiku entry is already added; rates are hardcoded as of April 2026).
2. Run at least one **full or `_trimmed`** document through the **batched production path** — AZ full (217pp) is the best stress case, CO birth-to-8 (187pp) a second.
3. Pull per-stage tokens/cost/latency/call-counts from `PipelineRunMetrics.summary()`; cross-check totals against the `els-pipeline-metrics-{env}` CloudWatch dashboard.
4. Report **tokens as the primary hard number**, cost as derived with the pricing date stated. Confirm depth-map cost is now non-zero.

**Deliverable:** a cost/latency/scale table, explicitly labelled as full-document tier and separate from the subset-tier quality tables.

---

### Task 7 — Run secondary ablations: model tier, chunk overlap, two-stage vs single-stage

**Risk:** low. Emily wants all of these if time allows; drop from the bottom if it runs short.

1. **Model tier** — swap detector/depth-map/parser model IDs via `config.py` env vars. This is the evidence for the paper's "cheapest model that suffices" principle; without it that section is an assertion.
2. **Chunk overlap** — 500 vs 0 tokens; quantifies the boundary-loss claim.
3. **Two-stage vs single-stage** — one combined detect+parse prompt vs. the decoupled pipeline. Highest effort; **drop this one first** if time runs short.

**Deliverable:** ablation tables in `paper/results/`.

---

### Task 8 — Compute dataset descriptive stats and re-measure the confidence distribution

**Risk:** low.

1. States, indicators, domains, age-band coverage, `standard_id` collision count (should be 0).
2. **Re-measure the confidence distribution from scratch** — per guardrail 4, the "85–90% at 0.95+" figure is unvalidated Medium prose and must not enter the paper unmeasured. Remember confidence gates nothing (guardrail 2).

**Deliverable:** descriptive stats + confidence distribution data in `paper/results/`.

---

### Task 9 — Do the related-work literature survey

**Risk:** low, but **long lead time and fully independent — start early, in parallel with Tasks 1–2.** Emily: "budget a fair amount."

> **STATUS: DRAFT DELIVERED 2026-08-17.** `paper/references.bib` (36 entries, organized by the four coverage areas, per-entry provenance comments recording the verification source — publisher page, ACL Anthology, arXiv abs page, or dblp, all checked 2026-08-17) and `paper/sections/related_work.tex` (four subsections mirroring the coverage areas, natbib citations, written to be `\input` by the Task 10 skeleton). The note that the plan file `~/.claude/plans/i-want-to-create-silly-pnueli.md` referenced above **no longer exists locally** — the survey was scoped from this task's own coverage list.
>
> **Positioning found by the survey, for Task 12:** (a) the hierarchical-document-structure line (DocParser AAAI'21, HRDoc AAAI'23, Detect-Order-Construct Pattern Recognition 2024, HiPS 2025) all needs layout supervision and uniform-typography corpora — our depth-map pass is the zero-shot analogue of Comp-HRDoc's TOC subtask, which is the paper's cleanest contrast; (b) closest applied neighbor is Aggarwal et al. 2025 (arXiv:2511.10659), LLM extraction of Indian government fiscal PDFs validated by the documents' own arithmetic structure — we validate by hierarchical/namespace structure, a parallel worth one sentence; (c) GoLLIE (ICLR 2024) is the guidelines-as-prompt precedent for our prompt-rule methodology; (d) for the education area, ASN/CASE presuppose already-structured standards and alignment work (Porter SEC; Polikoff/Porter/Smithson 2011; arXiv:2510.05129) aligns content *to* known standards — nobody automates the PDF→hierarchy step itself, which is the gap claim. Guardrails honored in the draft: no confidence-gate language, no Medium numbers, fine-tuning argued on no-labeled-corpus grounds only (with Liu et al. 2022 T-Few cited as the honest counterpoint).
>
> **Still open:** (1) Emily should read the draft for framing/voice; (2) citations to our own measured claims (stability, hallucination audit) currently reference sections that don't exist yet — reconcile wording during Task 12; (3) a page-number sweep at Task 13 (`.bbl` build) — entries where pages couldn't be verified deliberately omit them rather than guess; (4) if reviewers-in-spirit want more depth in LLM-for-education, the survey found the area thin as of 2026-08 — that thinness is itself citable.

The Medium articles cite only a handful of anchors (Brown 2020 GPT-3, Wei 2022 chain-of-thought, Monarch 2021, Mosqueira-Rey 2023). That is a starting point, not a survey.

Cover: document structure/layout extraction; LLM information extraction, in-context vs. fine-tuning; human-in-the-loop IE; education-standards/curriculum NLP.

**Deliverable:** `paper/references.bib` (converted to `.bbl` at submission — see Task 13) + a drafted related-work section.

---

### Task 10 — Set up the ACL LaTeX skeleton in `paper/` with results plumbing

> **STATUS: DONE 2026-08-17.** `paper/main.tex` builds clean (5 pages, 0 errors/undefined refs after a full `pdflatex → bibtex → pdflatex → pdflatex` cycle) against the official `acl.sty`/`acl_natbib.bst`/`acl_latex.tex` pulled from `github.com/acl-org/acl-style-files`, in final/non-anonymous mode (`\usepackage{acl}`, two-column via the style file's own `\twocolumn`), author block **Emily Cheyne, Founder, EdTech Co.**
>
> **The plan file this task pointed to is gone.** `~/.claude/plans/i-want-to-create-silly-pnueli.md` was removed by an automatic cleanup at `2026-08-17T01:11:44Z`, hours before this task started; a full-disk search found no other copy. Outline sections 6–12 were recovered verbatim from a partial `Read`/`grep` of the file captured in an old session transcript (`8047c900-...jsonl`, 2026-07-18). Sections 1, 3, 4 and 5 are **not** recovered — `paper/sections/{introduction,corpus,schema,pipeline_overview}.tex` are Task 10's reconstruction, not the original wording. Full provenance in `paper/OUTLINE_NOTES.md`. Cheap to fix: `main.tex` only `\input`s files, so reordering/renaming a section costs nothing.
>
> **A concurrent session was independently running Task 9** while this task ran — `paper/references.bib` and `paper/sections/related_work.tex` already existed (36 citations, all resolving cleanly against the bibliography) and were left untouched; `main.tex` just `\input`s them per the note the other session left in its own file header.
>
> **Results plumbing (guardrail 6) is wired and demonstrated, not just scaffolded:** `paper/analysis/generate_tables.py` reads `paper/results/task{1,2}_20260816/summary.json` + `paper/results/corpus_tiers.json` and writes `paper/tables/{detector,parser}_headline.tex`, `\input` from `sections/experiments_results.tex`. Regenerate with `python paper/analysis/generate_tables.py`. Every other section is a `% TODO(Task 12)` stub with an outline comment (verbatim for 6–12, reconstructed for 1/3/4/5) — no prose was drafted.
>
> **No local LaTeX toolchain exists on this machine and installing one needs an interactive sudo password** (`brew install --cask basictex` fails non-interactively: `sudo: a password is required`) — not something this session can supply. Built and verified instead via `docker run --rm -v "$PWD":/paper -w /paper texlive/texlive:latest ...` (image pulled fresh, 5.65GB). Regenerate the PDF with:
> ```
> cd paper && docker run --rm -v "$PWD":/paper -w /paper texlive/texlive:latest bash -c \
>   "pdflatex -interaction=nonstopmode main.tex && bibtex main && \
>    pdflatex -interaction=nonstopmode main.tex && pdflatex -interaction=nonstopmode main.tex"
> ```
> **Open for Emily:** the author block currently has a placeholder correspondence email (`author@edtechco.example`) — this is permanently public once submitted (Task 13), so it needs Emily's real preferred address before final compile, not a guess.

**Risk:** low.

1. Create `paper/` with the current ACL template (`acl.sty` + `acl_natbib.bst`), two-column, final/non-anonymous mode. Author block: **Emily Cheyne, Founder, EdTech Co.**
2. Scaffold the 12 outline sections as stubs (see the plan file).
3. Set up `paper/results/` so every table regenerates from recorded JSON rather than being hand-typed (guardrail 6).
4. Confirm it builds: `cd paper && pdflatex main && pdflatex main`.

**Deliverable:** a building ACL skeleton.

---

### Task 11 — Produce figures and the corpus appendix table

**Risk:** low. **Has a dependency on Emily.**

1. Generate locally from `paper/results/`: confidence distribution, level-confusion matrix, cost-by-tier. Plus a canonical-schema tree diagram.
2. **Request from Emily:** the AWS architecture diagram, and any Standards Explorer / CloudWatch dashboard screenshots. Ask with specifics when you get here.
3. Build the corpus appendix table from `standards/standards_tracking.md` — source URL, year, retained page ranges after trimming. **This is what replaces shipping the PDFs** (they are third-party state-agency documents; only US *federal* works are automatically public domain under 17 USC §105, so redistributing them isn't ours to grant). Name California's source precisely.
4. All figures: vector PDF, fonts embedded, flat filenames (they get flattened to root in Task 13).

**Deliverable:** all figures + the corpus appendix table.

---

### Task 12 — Draft the paper sections

**Risk:** medium — this is where guardrail violations actually reach the page.

Draft sections 1–12 per the outline in the plan file. Re-read **all seven guardrails** before writing, and again before considering a section done. The ones most likely to be violated in prose: corpus tier on every table (1), no confidence-based review gate (2), trimming disclosed (3), no unmeasured Medium numbers (4).

**Deliverable:** a complete draft.

---

### Task 13 — Clean the arXiv tarball and submit

**Risk:** low, but irreversible — everything uploaded is public and permanently archived.

- Flatten figures out of `figures/` into `paper/` root; update `\includegraphics` paths; delete empty dirs.
- Keep the precompiled **`.bbl`**; **DELETE the `.bib`**.
- Remove `.aux .log .out .blg .pdf`; delete hidden files (`.git`, `.DS_Store`) and unused `.tex/.sty/.cls`.
- **Strip ALL LaTeX comments** — everything uploaded is public.
- Remove any "submitted to / under review" boilerplate.
- `\appendix` goes **AFTER** the references.
- Add after `\end{document}`: `\typeout{get arXiv to do 4 passes: Label(s) may have changed. Rerun}`
- `tar -cvvf ax.tar *` from inside `paper/`, extract to a scratch dir, confirm only intended files + `.bbl`, and that it compiles standalone.
- Web-form metadata as plain text: title initial caps no macros; authors comma-separated, no "and"; abstract with newlines/whitespace stripped.
- License: the minimal **"arXiv.org perpetual, non-exclusive license to distribute"** — retains Emily's copyright, permits no redistribution or derivatives.
- Categories: **cs.CL** primary, cross-list **cs.AI**.

**Emily submits. Do not submit on her behalf.**
