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
8. **Never report the detector suite's raw "precision" as detector quality.** (Established by Task 1, decided 2026-07-17.) The detector goldens are partial spot-checks (5–25 elements) while the detector emits 9–122 elements inside annotated domains; the suite counts every unmatched in-scope detection as a false positive even when it is correct document content, so raw precision mostly measures annotation coverage (verified: all of AZ's "FPs" are real unannotated elements). The paper reports **recall (per-level) from the suite** plus a **verified precision / hallucination rate from the manual FP audit (Task 1b)**. Decision made: no exhaustive golden extension, no further PDF trimming — trimming smaller invalidates the frozen measurement chain and weakens the eval without fixing the artifact.

## How to run evaluations

Use **`outputs/07-16-26-2/`** — it supersedes every earlier `outputs/` folder. Cache is on by default; use `--no-cache` for final recorded numbers.

> **⚠️ Known defect in this outputs folder (Task 1 finding 3, root cause corrected 2026-07-17):** every detection in it was produced **without a depth map** — `els-detection-batch-preparer-role-dev` lacks `bedrock:InvokeModel` (and `cloudwatch:PutMetricData`), so the prepare step's Haiku depth-map call fails with AccessDenied and batches run in no-depth-map mode. This craters CO parser coverage to 0.333 (spurious sub_strands; direct-path detection scores 1.000 — `paper/results/task1_parser_CO_on_direct_detection.json`). The grants are missing from the CDK template (`pipeline-stack.ts`, `DetectionBatchPreparerLambdaRole`) — **a plain redeploy does NOT fix it**; the CDK role needs the Bedrock + CloudWatch-metrics policies first. Fix, deploy, re-run, re-download before using S3 outputs for further recorded numbers (gates Tasks 5–6).

```bash
source venv/bin/activate
python -m evaluation.eval_detector --state CA
python -m evaluation.eval_detector --state CA --stability-runs 3   # LLM-determinism check
python -m evaluation.eval_parser --detection-dir outputs/07-16-26-2 --state CA
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
  | KY | held-out | 120 | 52 | **9** |

- **The held-out canary is NV-2023** (`nevada_standards_2023_trimmed_only_subset.pdf`, multi-domain). **Not** NV-SES-2025 — that document is Social-Emotional Standards only, a single domain, and far too narrow to support a generalization claim.
- **California's source is the PTKLF "at a glance" document** (`ptklfataglance.pdf`, 68pp) — confirmed correct, not an error in `standards/standards_tracking.md`. Name it precisely in the paper.
- **Batched vs. direct path diverge.** The evals run the direct path; production runs the batched path (`detection_batching.py`, `parse_batching.py`). A 9-page subset never exercises prepare → Step Functions Map → merge, so the batching claim needs a full-document run (Task 6).
- **Model assignment is deliberate** — Haiku 4.5 for the depth map, Opus 4.6 for detection, Sonnet 4.6 for parsing (`config.py:15-21`). The principle is "cheapest model that suffices per stage"; the model-tier ablation (Task 7) is its evidence.
- **Cost data already exists.** `PipelineRunMetrics.summary()` (`src/els_pipeline/metrics.py`) gives per-stage tokens/cost/latency/call-counts; the `els-pipeline-metrics-{env}` CloudWatch dashboard (`infra/cdk/lib/constructs/pipeline-dashboard.ts`) is the cross-check. `BEDROCK_PRICING` rates are hardcoded as of April 2026 — re-verify and cite the date.

---

## Tasks (work in order — lowest number first)

Priority = risk first. Tasks 1–2 are the two real risks: Task 1 validates the measuring instrument everything downstream depends on, and Task 2 is the long pole that gates the paper's strongest claim. Tasks 3–4 are the must-have ablations that turn central claims from assertions into evidence. Task 6 rescues the batching/scale claim. Tasks 9–13 are the writing chain; Task 9 has a long lead time and should start early in parallel.

### Task 1 — Run headline evals on the 4 golden states and sanity-check every metric

> **STATUS: DONE 2026-07-16.** Results in `paper/results/task1_*` (summary: `task1_summary.json`, narrative: `task1_findings.md`, provenance: `task1_manifest.json`). Open-question resolutions: (1) detector precision — **DECIDED 2026-07-17: recall + manual FP audit** (guardrail 8, Task 1b); (2) TX indicator-description convention (`None` vs the parser's "Child Behaviors" text) — **still needs Emily's call**; (3) production depth-map failure — fix the preparer role's IAM in CDK, then redeploy, before Tasks 5/6 (see the outputs warning above).

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
4. **Extend the same audit to NV/KY after Task 2** so the generalization table's precision column uses the identical methodology as the golden states.
5. Every verified-real extra is a seed golden entry (title/level/page already captured) — if a reviewer later demands exhaustive goldens, upgrade CA first from this file.

**Deliverable:** `paper/results/task1b_fp_audit.json` + verified-precision numbers, Emily-signed.

---

### Task 2 — Annotate held-out goldens for NV-2023 and Kentucky, then run both suites

**Risk:** HIGH + LONG POLE. This is the main net-new effort and it gates the paper's strongest claim. **Start early; it can run in parallel with Task 1.**

1. Annotate `evaluation/ground_truth_detector/{NV,KY}.json` and `evaluation/ground_truth_parser/{NV,KY}.json` per `evaluation/README.md` conventions — ~50 elements per state, verbatim titles/descriptions, `test_case_id` pattern `<STATE>-<KIND>-<N>`.
2. Sources: `standards/nevada_standards_2023_trimmed_only_subset.pdf` (15pp, multi-domain) and `standards/kentucky_all_standards_2021_only_subset.pdf` (9pp). Both already exist.
3. Run both suites on NV and KY; report alongside the golden states.
4. Spot-check annotation is fine (same style as the golden states) — **do not** attempt exhaustive coverage; precision for NV/KY comes from extending the Task 1b audit to their in-scope extras, keeping the generalization table's methodology identical to the golden states'.

**Deliverable:** two held-out golden sets + their scores. Per guardrail 7 — if generalization doesn't hold, report it.

---

### Task 3 — Build the depth-map on/off ablation

**Risk:** medium. **File:** `detector.py`. This is the evidence for the paper's central "classify by nesting POSITION, not document label" claim — without it, that claim is asserted, not shown.

1. Add an env-flag toggle that neutralizes Pass-1 depth-map inference. **Production default must be unchanged.**
2. Run the detector eval with the flag on and off across the golden states.

**Deliverable:** the on/off delta table in `paper/results/`.

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

1. `--stability-runs 3` (or 5) per state, both suites, with `--no-cache` so runs are genuinely independent.
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

The Medium articles cite only a handful of anchors (Brown 2020 GPT-3, Wei 2022 chain-of-thought, Monarch 2021, Mosqueira-Rey 2023). That is a starting point, not a survey.

Cover: document structure/layout extraction; LLM information extraction, in-context vs. fine-tuning; human-in-the-loop IE; education-standards/curriculum NLP.

**Deliverable:** `paper/references.bib` (converted to `.bbl` at submission — see Task 13) + a drafted related-work section.

---

### Task 10 — Set up the ACL LaTeX skeleton in `paper/` with results plumbing

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
