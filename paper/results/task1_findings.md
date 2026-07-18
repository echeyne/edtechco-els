# Task 1 — Headline evals on the 4 golden states: results & sanity-check findings

**Date:** 2026-07-18 (re-run after the depth-map IAM fix) · **Commit:** `0d2f887` · **Corpus tier: `_only_subset` (9–15pp trimmed subset PDFs — NOT full documents)** · Outputs: `outputs/07-17-26` · Models: detector `us.anthropic.claude-opus-4-6-v1`, depth-map `us.anthropic.claude-haiku-4-5-20251001-v1:0`, parser `us.anthropic.claude-sonnet-4-6`.

Supersedes the 2026-07-16 run against `outputs/07-16-26-2`, whose **deployed detections were corrupted** by a missing `bedrock:InvokeModel` grant on the detection-batch-preparer role (see finding 3). All numbers regenerate from the commands in `task1_manifest.json`; raw suite reports are `task1_detector_golden4_v2.json` / `task1_parser_golden4_v2.json`; consolidated paper-facing numbers are `task1_summary_v2.json` (built by `paper/analysis/consolidate_task1.py`).

## Headline results

### Detector (fresh direct-path run, graded against detector goldens)

| State | Recall (this run) | Recall (07-16 run) | Raw "precision" | Precision ceiling from annotation coverage | Depth map | Level misclass. (level-agnostic) | Age-band drops |
|---|---|---|---|---|---|---|---|
| AZ | 1.000 | 1.000 | 0.500 | 0.556 (5 golden / 9 in-scope) | PASS | 0 | 0 |
| CA | 1.000 | 1.000 | 0.205 | 0.205 (25 / 122) | PASS | 0 | 0 |
| CO | 1.000 | 0.857 | 0.159 | 0.152 (7 / 44) | PASS | 0 | 0 |
| TX | 1.000 | 0.750 | 0.276 | 0.286 (8 / 29) | PASS | 0 | 0 |

Per-level recall is 1.000 at every level in every state this run (CO strand 0.500→1.000; TX indicator 0.500→1.000). All 11 detector regression cases PASS. Depth-map inference produced the exact expected canonical-level sequence for all four states (CO correctly 3-level, no sub_strand).

**Do not report the two recall columns as a before/after improvement.** They are two samples of a nondeterministic instrument run on byte-identical input — see finding 1.

### Parser (frozen batched-path detections from outputs/07-17-26)

| State | Coverage | Field accuracy | Fully correct | ID collisions |
|---|---|---|---|---|
| AZ | 1.000 (18/18) | 0.923 | 0/18 | 0 |
| CA | 1.000 (21/21) | 0.995 | 19/21 | 0 |
| CO | **1.000 (9/9)** *(was 0.333)* | 0.994 | 8/9 | 0 |
| TX | 1.000 (8/8) | 0.958 | 2/8 | 0 |

## What the paper may and may not claim from these numbers

1. **DETECTOR OUTPUT IS NOT REPRODUCIBLE ACROSS SESSIONS — this is the most important result of the re-run, and it is a methodological constraint on every detector number in the paper.** The 07-16 and 07-18 detector evals ran on **byte-identical extraction input** (verified: the two extraction JSONs differ only in `source_version_id` and `extraction_timestamp`; the text payload hashes match for all four states) with **identical detector code** (`detector.py` / `prompts.py` / `config.py` untouched since `0d2f887`, working tree clean). They produced materially different detections:

   | State | 07-16 elements | 07-18 elements | Nature of the difference |
   |---|---|---|---|
   | AZ | 66 | 64 | 07-16 emitted duplicate uppercase strands (`EMERGENT LITERACY`, `EMERGENT WRITING`) |
   | CA | 122 | 122 | **identical element sequence** |
   | CO | 65 | 63 | 07-16 fused definition sentences into strand titles (`Health, Safety and Nutrition: The maintenance of…`); 07-18 emitted the bare name |
   | TX | 28 | **37** | 07-18 additionally detected the `Science` domain and the SED indicators that 07-16 dropped/truncated |

   Consequences: (a) the three "genuine, diagnosable detector defects" recorded in the 07-16 findings (CO strand title-fusion, TX-IND-02-PK3 truncation, TX-IND-02-PK4 drop) **did not recur** — they were samples, not defects; (b) a single-run recall figure is not a reportable instrument in *either* direction, so neither "0.750" nor "1.000" may be presented as *the* TX detector recall; (c) the 07-18 run is uniformly *better* than 07-16 on all three states that moved, which is itself suspicious — a plausible hypothesis is a Bedrock-side serving/snapshot change behind the `us.anthropic.claude-opus-4-6-v1` alias, but **this run does not establish that** and it should not be asserted without evidence.

   **The suite's own stability check understates this and must not be cited as evidence of determinism.** `--stability-runs 3` on CO and TX reports level-disagreement 0.000 and output-size stdev 0.00 (genuine fresh calls — `measure_stability` passes `use_cache=False` with a per-run cache suffix), i.e. three *consecutive same-session* runs were identical while a 24h-separated run differed by up to 9 elements. Worse, the metric is **structurally blind to the failure mode actually observed**: it keys elements on `(code, title)` and only counts a disagreement when a matched pair differs in `level`, so a truncated or definition-fused *title* drops out of the comparison instead of counting against stability. **Recommended for the paper: report detector recall as a range or mean±spread over N independent sessions (N≥3, separated in time), not a point estimate from one run, and do not use `--stability-runs` as the variance instrument without fixing its match key.**

2. **"Precision" here is NOT a hallucination rate.** The detector goldens are partial spot-checks (5–25 elements) while the detector emits 9–122 elements inside annotated domains; every unmatched in-domain detection counts as a false positive *even when it is correct document content*. Verified by inspection: all 5 AZ "false positives" are real unannotated document elements. CA's raw precision (0.205) exactly equals its coverage ceiling — every golden matched and every "FP" is unannotated real content. **Recall and per-level recall are the trustworthy detector-quality numbers from this suite** (subject to finding 1's variance caveat). The paper's precision number comes from the Task 1b manual FP audit, not from this suite (guardrail 8).

3. **RESOLVED — the CO parser collapse was the depth-map IAM defect, and it is fixed.** *(Root-caused 2026-07-17; fix deployed and verified here.)* `els-detection-batch-preparer-role-dev` lacked `bedrock:InvokeModel`, so the prepare step's Pass-1 depth-map inference (Haiku) failed with `AccessDeniedException`, an empty `{}` depth map was persisted, and every detection batch ran in **no-depth-map mode**, misclassifying CO's Social-Emotional goal statements as `sub_strand`. Fix: `BedrockInvokeAccess` + `CloudWatchMetricsAccess` added to `DetectionBatchPreparerLambdaRole` in `infra/cdk/lib/pipeline-stack.ts`. **Post-fix confirmation:** CO deployed detection 93 elements / 9 `sub_strand`s → **63 / 0**; CO parser coverage **0.333 → 1.000** (9/9), fully-correct 2→8, dropped 6→0; the `CO-INDICATOR-PARENT-IS-STRAND` regression **FAIL → PASS**. The failure was pipeline-wide, not CO-only: AZ 67→65, CA 126→123, TX 40→37 deployed elements also shifted.

   **Batched ≈ direct convergence confirmed** (resolves the old open question 3): the parser on the post-fix *batched* CO detection now matches the *direct-path* diagnostic — both 9/9 coverage and `n_parsed=48` (batched field-acc 0.994 / 8 fully-correct vs direct 0.969 / 7, a gap within run-to-run variance). **The paper may take its parser numbers from the deployed batched path.**

   The 07-16 incident remains usable as an unplanned **depth-map-off ablation** (CO's structure collapses without the depth map while AZ/CA/TX largely survive), corroborating — not replacing — Task 3. That evidence lives in the preserved 07-16 reports and `outputs/07-16-26-2`.

4. **Zero level misclassifications on the golden slice, both runs.** The suite's built-in confusion matrix is structurally diagonal (level is in the match key), so we compute a level-agnostic re-pairing (`consolidate_task1.py`): across all four states, no golden element was detected at the wrong level. Every recall miss in the 07-16 run was a *form* defect (title fidelity), not a *position* defect — supports the classify-by-position claim, and this held under both samples.

5. **Parser field accuracy includes upstream text-fidelity noise.** AZ's mismatches are single-space word fusions from Textract (`firmfoundation`, `andphysical`) surviving into descriptions — hierarchy is correct, and AZ `fully_correct=0` is entirely attributable to this (worst fields: `sub_strand.description` 0.278, `indicator.description` 0.667, `domain.description` 0.722). TX's `strand.description` mismatches (0.750) are curly-vs-straight quote differences. Genuine parser errors do exist: CA swapped the Discovering/Developing column descriptions for CA-IND-07 (`indicator.description` 0.905, 2/21 not fully correct).

6. **standard_id uniqueness: 0 collisions in every state's full output** (25–94 standards each).

## Golden-data corrections made during this task (never matcher loosening)

- **CA detector golden:** the FLD Grammar/Sharing/Participating block (doc pages 7–8) was listed after the ELD entries, breaking document-order domain tagging; 5 elements silently matched cross-domain via the fallback. Reordered to true document order. Verified score-neutral (25/25 matched before and after; cross-domain pairings 5→0).
- **TX parser golden:** duplicated `test_case_id` TX-IND-04-PK4. Entry for indicator VI.A.1 had `source_page: 9` (VI.A.1 is on subset page 7) — fixed. Entry for VI.A.4 had `strand.code: "IV.A"`, a transposition typo (TX Science is domain VI) — fixed, re-id'd TX-IND-05-PK4.
- Pre-fix raw reports preserved as `task1_*_pre_goldenfix.json`.

## Open questions for Emily

1. **Detector precision** — **DECIDED 2026-07-17: recall + manual FP audit.** No exhaustive golden extension, no further trimming. The suite's raw precision never reaches the paper (guardrail 8); the paper's precision number comes from the Task 1b audit (Claude first pass, Emily verifies as annotator of record → `paper/results/task1b_fp_audit.json`). **Now unblocked** — the frozen run the paper publishes against is `outputs/07-17-26`.
2. **TX indicator descriptions** — golden expects `None`; the parser emits the "Child Behaviors" outcome text as the description (`indicator.description` 0.500 for TX). Annotation-convention call; not changed. **STILL OPEN.**
3. **Parser-suite input** — **RESOLVED:** batched and direct now converge (finding 3). Use the deployed batched detections.
4. **NEW — how many detector runs back the paper's recall number?** Finding 1 shows one run is not enough. Recommend ≥3 time-separated sessions per state and reporting a range; needs a decision because it costs LLM budget and changes every detector table in the paper. **NEEDS EMILY.**

## Instrument notes (for the paper's evaluation section)

- Detector matching: domain-scoped, code-agnostic key `(enclosing domain, level, normalized title, normalized age-band)`, with a domain-agnostic fallback; exact title match after whitespace/case folding. The `eval_detector` module docstring ("precision/recall on (level, code) tuples") is stale.
- Precision scoping: detections outside golden-annotated domains are excluded (neither TP nor FP). Recall denominator is the golden set only. AZ has one golden indicator outside any annotated domain (matched via fallback; its domain excluded from precision scoping).
- Depth-map grade: per-state exact match of the canonical-level sequence (a boolean), computed standalone via `infer_depth_map` on full extraction blocks — same call shape as production. It re-runs live (Haiku) on every eval invocation regardless of cache.
- **Detector stability instrument is inadequate** — see finding 1: `measure_stability` counts only level disagreements among elements whose `(code, title)` already match, so title-fidelity variance (the observed failure mode) is invisible to it, and it samples only within a single session.
- Parser matching: `(indicator name, canonicalized age-band, proficiency-variant code suffix)`; all NormalizedStandard fields graded except source_text; string compare is whitespace-insensitive but punctuation-sensitive (curly quotes count as mismatches).
</content>
