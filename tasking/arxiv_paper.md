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
8. **Never report the detector suite's raw "precision" as detector quality** — *unless that state's golden is verifiably exhaustive.* (Established by Task 1, decided 2026-07-17; the exhaustive-golden carve-out added by Task 2, 2026-08-16.) **Kentucky is still the one state that qualifies**: 44 golden elements against 44 in-scope detections with identical per-level counts and zero unmatched detections, so its raw precision 1.000 is a real hallucination rate. Establish exhaustiveness from `heldout_evidence.json`'s `golden_is_exhaustive` before invoking this — never assume it. Every other state still follows the rule below.

   ⚠️ **NV does NOT qualify, despite the 2026-08-22 exhaustive pass — measured, not assumed.** `HELD_OUT_ANNOTATION_GUIDE.md` states that both held-out goldens are now exhaustive and that NV's raw precision is therefore a real hallucination rate. The first half is true in one sense and the second does not follow. Two different properties are involved:
   - **Content-exhaustive** — the golden annotates every distinct structural element the subset prints. NV is now this: 46 elements, up from 41, including all twelve `<Domain> Standard N:` headings.
   - **Detection-exhaustive** — every in-scope detection is accounted for by a golden entry. NV is **not** this, and cannot be while the golden holds one entry per element: the detector emits **53** in-scope elements for NV because the document reprints 6 headings on a second page spread (verified: 6 duplicate `(level, title)` pairs in the detection, 0 in the golden) and one is the known `SS.CI.PK3` hallucination.

   So NV's ceiling is **46/53 = 0.8679**, and reporting its raw precision as a hallucination rate would count 6 *correct re-detections of genuinely reprinted headings* as hallucinations. **NV keeps the verified-precision path**: (in-scope − hallucinations)/in-scope. The audit is now 7 verdicts instead of 12, because the 5 previously-unannotated standards are annotated. Only `golden_is_exhaustive` in the `n_golden == n_in_scope` sense licenses this carve-out — content coverage alone does not. The detector goldens are partial spot-checks (5–25 elements) while the detector emits 9–122 elements inside annotated domains; the suite counts every unmatched in-scope detection as a false positive even when it is correct document content, so raw precision mostly measures annotation coverage (verified: all of AZ's "FPs" are real unannotated elements). The paper reports **recall (per-level) from the suite** plus a **verified precision / hallucination rate from the manual FP audit (Task 1b)**. Decision made: no exhaustive golden extension, no further PDF trimming — trimming smaller invalidates the frozen measurement chain and weakens the eval without fixing the artifact.

## Next session — the run queue (as of 2026-08-23)

Everything below is blocked ONLY on the Opus daily quota resetting. Probe first
(see the Compute budget section); the reset boundary is not UTC midnight.

**Run in this order — the total is ~2.3M Opus tokens, ~89% of a daily quota, so
these two fill a day and nothing else Opus-heavy should share it.**

1. **Finish Task 3's stability run 3** — 8 runs (CA off-arm, plus CO/TX/NV/KY in
   both arms). **~400K tokens, ~20 min.** Cheap, and it takes CO and KY, which
   carry the entire ablation effect, from n=2 to n=3. Do this FIRST: if the day
   throttles early, this is the piece that most improves a claim already in the
   paper.
2. **Task 6 — full documents, KY + CO first** (Emily's call, 2026-08-23).
   **~1.9M tokens.** KY 8pp→120pp is the largest relative jump AND its golden is
   detection-exhaustive, so the 44 annotated elements can be graded *inside* the
   full run — the only quality-at-scale evidence available without new
   annotation. CO 10pp→187pp is the other state carrying the Task 3 effect, so it
   also informs the framing question. AZ (217pp, the real batching stress test)
   and the remaining three follow on a later day; all six is ~3.5M, over one
   day's cap.

**Zero-Opus work available any time** (does not compete for quota): ~~Task 8~~
**(done 2026-08-23)**, Task 11's local figures and the corpus appendix table —
note it should now EXTEND Task 8's dataset table rather than duplicate it — and
Task 12 drafting for every section whose numbers are recorded (Tasks 1, 1b, 2,
3, 4, 8, 9 are all done). The `measure_stability` repair that blocked Task 5 has
also landed (`fa0b0ed`).

## Compute budget — the Bedrock Opus daily token quota (measured 2026-08-23)

The dev account has a **per-model daily token quota**, and the detector runs on
Opus, so detector-heavy work is what exhausts it. `us.anthropic.claude-opus-4-6-v1`
is capped at **2,592,000 tokens/day** (cross-region). Sonnet and Haiku have their
own budgets and were unaffected when Opus was exhausted, so parser work and
depth-map work can continue after an Opus throttle.

Measured costs, for planning:

| work | Opus tokens | share of daily quota |
|---|---|---|
| Task 1 detector (4 states) | 208,835 | 8% |
| Task 2 detector (2 states) | 106,606 | 4% |
| Task 3 off-arm (6 states) | 299,216 | 12% |
| one ON+OFF ablation pair, 6 states | ~615,000 | 24% |
| ablation stability, 2 extra runs × both arms × 6 states | ~1,230,000 | 47% |
| **Task 6, all six FULL documents** | **~3,500,000** | **135% — needs two days** |

Full documents are **777pp against 70pp of subsets, 11.1x**: AZ 217, CO 187,
KY 120, NV 98, TX 87, CA 68.

**Three rules learned the hard way:**

1. **Sequential execution does NOT avoid a daily cap.** The 2026-08-23T00:25Z
   throttle happened during a strictly sequential run. Budget across days.
2. **Prefer one invocation per state**, with separate `--report-json` files, over
   one multi-state call. A mid-run throttle in a six-state call recorded five
   states as `n_detected=0, recall=0.0` — which reads as a catastrophic result
   rather than an infrastructure failure. Every analysis script under
   `paper/analysis/` now refuses such a row rather than averaging it in.
3. **Probe before committing to a long run:**
   ```
   python -c "import boto3,json;boto3.client('bedrock-runtime',region_name='us-east-1').invoke_model(modelId='us.anthropic.claude-opus-4-6-v1',body=json.dumps({'anthropic_version':'bedrock-2023-05-31','max_tokens':5,'messages':[{'role':'user','content':'hi'}]}))"
   ```
   The reset boundary is **not** UTC midnight — a throttle was observed at
   00:25Z with only ~198K tokens spent that UTC day.

## How to run evaluations

Use **`outputs/08-22-26-4/`** (set 2026-08-22) — it supersedes every earlier `outputs/` folder, including `08-16-26`, `08-22-26`, `-2` and `-3`. Cache is on by default; use `--no-cache` for final recorded numbers.

> **Why `-4` and not `08-22-26`.** `-4` is run 040, the first carrying `detector._splice_overlapping_prose`. Its NV detection differs from `08-22-26` in **exactly one field** — the Science `domain.description`, 2410 → **3500 chars**, byte-exact against the golden — and is otherwise identical across all 53 elements. `ground_truth_parser/NV.json` still names `outputs/08-22-26/NV-detection.json` in `source_detection`; the drift is in the favorable direction and needs a one-line provenance update, **not** re-annotation.
>
> **Do NOT use `08-22-26-2`** — its KY detection is 38 elements against the other runs' 44, which breaks KY's exhaustive detector golden and drops parser coverage to 21/26. `-4` restores KY to 44 with levels matching the golden exactly (3/5/10/26).
>
> **Depth map is healthy on `-4` — verified 2026-08-23, not assumed.** PASS in all six states in the re-record, which discharges the earlier instruction to re-verify rather than carry the `08-16-26` result forward. (The detection-batch-preparer IAM fix landed 2026-07-17.)
>
> **AZ detection changed in this folder — diagnosed 2026-08-22, and it is benign.** 66 → **77** elements, sub_strands 11 → **21**, indicators unchanged at 45. Decomposed against the extraction (no Bedrock spend — both detections were already on disk):
> - **4 genuinely new sub_strands**, all verbatim in the extraction: `Attachment`, `Social Interactions`, `Respect` (SED, p2) and `Comprehension and Text Structure` (p4).
> - **7 additional cross-page duplicate copies** of strands/sub_strands that were already present.
> - 1 indicator title edited in place.
>
> The duplicates are **not** a de-duplication regression: **0 same-page duplicates in either folder**, and every duplicated title has **page 4 as its first occurrence** — AZ's contents/listing page, which prints the strand and concept headings whose content lives on later pages. `08-16-26` already showed the same pattern on two titles (`Emergent Literacy` ×3, `Emergent Writing` ×2); the new run simply emits the listing page's entries consistently. This is the same phenomenon `HELD_OUT_ANNOTATION_GUIDE.md` documents for NV's "The `<Domain>` Standards include:" pages.
>
> Consequence for the re-record: AZ's raw precision will fall because those copies are unmatched in-scope detections, and that is an **artifact of a listing page plus a 5-element spot-check golden**, not a quality change. AZ was already on the verified-precision path (guardrail 8) and stays there.

```bash
source venv/bin/activate
python -m evaluation.eval_detector --extraction-dir outputs/08-22-26-4 --state CA
# ⚠️ --stability-runs is BROKEN (gotcha: measure_stability compares only its own
# probe runs and EXCLUDES the graded run; it reported 0.000 disagreement in the
# same invocation whose graded output had 4 malformed primary keys). For real
# stability use plain repeats with one --report-json per run, as
# paper/analysis/ablation_stability.py expects.
# ^ REPAIRED 2026-08-23: --stability-runs now includes the graded run, keys
# identity on title (not code), compares presence, and reports denominators.
python -m evaluation.eval_detector --extraction-dir outputs/08-22-26-4 --state CA --stability-runs 3
python -m evaluation.eval_parser --detection-dir outputs/08-22-26-4 --state CA
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
- **Batched vs. direct path.** The detector eval runs the direct path; the parser eval and production run on the batched path's output (`detection_batching.py`, `parse_batching.py`). ⚠️ **The chunk/domain counts below were measured on `outputs/08-16-26` and are stale for AZ** — its detection grew 66 → 77 elements in `08-22-26-4`, so re-derive them during the re-record. **Measured 2026-08-16:** at the `_only_subset` tier every state produces ≤5 chunks (AZ 4, CA 3, CO 4, TX 3, NV 5, KY 3) against `MAX_CHUNKS_PER_BATCH=5` and ≤3 domains against `MAX_DOMAINS_PER_BATCH=3`, so **both** batching layers run as exactly one batch per state — the Map has a single iteration and the merge is a no-op. Detection consequently converges almost exactly (CA/CO/TX identical, AZ differs by two footnote characters), but that is structural, not evidence. Parsing does **not** converge (12 of CA's 94 `standard_id`s differ). The batching claim needs a full-document run (Task 6).
- **Model assignment is deliberate** — Haiku 4.5 for the depth map, Opus 4.6 for detection, Sonnet 4.6 for parsing (`config.py:15-21`). The principle is "cheapest model that suffices per stage"; the model-tier ablation (Task 7) is its evidence.
- **Cost data already exists.** `PipelineRunMetrics.summary()` (`src/els_pipeline/metrics.py`) gives per-stage tokens/cost/latency/call-counts; the `els-pipeline-metrics-{env}` CloudWatch dashboard (`infra/cdk/lib/constructs/pipeline-dashboard.ts`) is the cross-check. `BEDROCK_PRICING` rates are hardcoded as of April 2026 — re-verify and cite the date.

---

## Tasks (work in order — lowest number first)

Priority = risk first. Tasks 1–2 are the two real risks: Task 1 validates the measuring instrument everything downstream depends on, and Task 2 is the long pole that gates the paper's strongest claim. Tasks 3–4 are the must-have ablations that turn central claims from assertions into evidence. Task 6 rescues the batching/scale claim. Tasks 9–13 are the writing chain; Task 9 has a long lead time and should start early in parallel.

### Task 1 — Run headline evals on the 4 golden states and sanity-check every metric

> ✅ **RE-RECORDED 2026-08-22/23 at `288c64f1` — COMPLETE. Results: `paper/results/task1_20260822/`.** Recall **1.000 in all four states and at every level** (`fn=0` per level); code accuracy 4/4, 25/25, 7/7, 8/8; description 4/4, 14/14, 4/4, 3/3; depth map PASS ×4; all 18 regression cases PASS. Parser: coverage 100% in all four, field accuracy AZ 0.9969 / CA, CO, TX 1.0000, **zero `standard_id` collisions**. `paper/results/task1_20260816/` is retained ONLY as the reproducibility record and every figure in it is historical — its hash was `3b445471`, then `2ac17ac2` (commit `92c8288`), now **`288c64f1`**. ⚠️ `paper/analysis/generate_tables.py` was hard-pinned to the superseded folder and rendered its numbers into the paper until 2026-08-23; it now carries a `RUN_TAG` constant and refuses a superseded tag.
> 1. **pipeline source** (hash above);
> 2. **inputs** — AZ detection 66 → **77** elements (sub_strands 11 → **21**), which is unmeasured and is the single most important thing the re-record must explain;
> 3. **the harness** — `eval_parser._match_key` no longer derives identity from the code (Task 2 repair, verified score-neutral on these four at the old hash, but that verification does not carry across a source change).
>
> Retain `task1_20260816/` as the reproducibility record; write the new run to `paper/results/task1_2026MMDD/`.
>
> **STATUS (historical): DONE (re-run from scratch) 2026-08-16 against `outputs/08-16-26`.** Results in **`paper/results/task1_20260816/`** — narrative `findings.md`, consolidated numbers `summary.json`, provenance + regenerating commands `manifest.json`, raw suite reports `detector_golden4.json` / `parser_golden4.json`, path comparison `direct_vs_batched.json`. The July results (`paper/results/task1_*`) are **superseded** — they graded code that no longer exists (`derive_code_from_title` 2026-08-01; rule 4's code-lookup clause, `_anchor_parent_chain`, `disambiguate_colliding_standards`, `models._blank_to_none` 2026-08-15) — and are retained only for the reproducibility narrative.
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

**Deliverable:** verified-precision numbers, Emily-signed.

> ✅ **DONE 2026-08-23. Signed by Emily Cheyne, 156 verdicts, 0 changed.** Artifacts: `paper/results/task1_20260822/task1b_fp_audit_SIGNED.json` (authoritative — the evidence JSON's `verified_by` is reset by regeneration), `task1b_evidence.json`, and per-state sheets in `task1_20260822/signoff/`.
>
> **Verified precision 1.000 for AZ, CA, CO and TX — zero hallucinations.** Combined with NV (53 in-scope, 1) and KY (44, 0): **297 in-scope detections corpus-wide, ONE hallucination, verified precision 0.9966.** The methodology sentence is now true for all six states.
>
> The count is **156**, not the ~165 estimated here (AZ 7 + CA 97 + CO 35 + TX 17, from each state's `extra_in_detected`).
>
> ⚠️ **`fp_audit` had a defect that this task exposed.** Its `hallucinated` verdict was a catch-all for "not contiguous and not a structural repeat", so it flagged **39 CO/TX rows** that are real titles merely split across lines/columns — CO would have reported verified precision **0.357** against a state with recall 1.000 and a perfect parser. Fixed 2026-08-23 with a fourth verdict `real_split_title`, gated on whether the title's spans reconstruct **in reading order**. Validated against the one known hallucination: NV's `SS.CI.PK3` returns no ordering, while NV's real split `S.EO` reconstructs in 118 chars and all 39 CO/TX rows in 51–456. **Mere presence of every span proves nothing** — the greedy decomposition shatters NV's fabricated tail into `'peers with'`/`'adult'`/`'guidance'`, all present, though the phrase occurs 0 times. NV/KY verdicts re-verified bit-identical after the fix.

---

### Task 2 — Annotate held-out goldens for NV-2023 and Kentucky, then run both suites

**Risk:** HIGH + LONG POLE. This is the main net-new effort and it gates the paper's strongest claim. **Start early; it can run in parallel with Task 1.**

> ✅ **RE-RECORDED 2026-08-22/23 at `288c64f1` against the NEW goldens — COMPLETE. Results: `paper/results/task2_20260822/`.** **Generalization holds, and the parser half is perfect on both held-out states.** Detector recall **1.000** at every level in both; NV code 44/46, description 2/3, verified precision **0.9811**; KY code 44/44, description 26/26, raw precision **1.000** (its golden is detection-exhaustive). Parser: NV **24/24** and KY **26/26** fully correct at field accuracy **1.0000**, zero collisions, all 7 parser regression cases PASS. The NV FP audit is **7 verdicts, signed by Emily 2026-08-23, 0 changed**. `paper/results/task2_20260816/` is retained only as the reproducibility record; its `nv_fp_audit_signoff.md` is the OLD 12-verdict sheet and carries a DO-NOT-SIGN banner. Still true and unchanged below: the NV golden moved 41→46 (detector) and 15→24 (parser), so
> - **NV detector golden 41 → 46 elements**, **NV parser golden 15 → 24 standards** (exhaustive pass, Emily, 2026-08-22). NV's annotation-coverage ceiling therefore moves **0.7736 → 0.8679** and its raw precision moves with it — **that is an annotation-coverage change, not a quality improvement, and must be labelled as such.**
> - KY goldens unchanged (44 / 26).
> - The drafted NV FP audit shrinks from **12 verdicts to 7** (the 5 real-but-unannotated standards are now annotated), so `nv_fp_audit_signoff.md` must be regenerated before sign-off — **do not sign the 12-row version.**
> - NV's `SS.CI.PK3` hallucination and the 6 reprinted-heading duplicates both persist in `08-22-26-4`, so verified precision should land at **52/53 = 0.981** again. If it does, that is a genuine cross-golden replication and worth saying so.
>
> Re-run against **`outputs/08-22-26-4`**, `--no-cache`. Retain `task2_20260816/` as the record; write the new run to `paper/results/task2_2026MMDD/`.
>
> **STATUS (historical): DONE 2026-08-16 against `outputs/08-16-26`** (code version hash `3b445471` — the same code Task 1 graded, so the two are directly comparable). Results in **`paper/results/task2_20260816/`** — narrative `findings.md`, consolidated numbers `summary.json`, provenance + regenerating commands `manifest.json`, raw suite reports `detector_heldout2.json` / `parser_heldout2.json`, evidence `heldout_evidence.json`, determinism probe `parser_KY_stability5.json`.
>
> **Headline — generalization HOLDS.** Detector recall **1.000 at every level in both states**, depth map PASS ×2, 0 level confusion, 100% domain-scoped matches (0 fallback). Parser coverage **1.000** ×2, 0 `standard_id` collisions. **KY is a clean sweep: precision 1.000, code 44/44, description 26/26, all 3 detector regressions PASS — against an EXHAUSTIVE golden.** NV: code 39/41, description 2/3, 3/3 regressions PASS. Parser field accuracy NV 0.974 / KY 0.983.
>
> **The load-bearing fact: KY's detector golden is EXHAUSTIVE** (44 golden vs 44 in-scope detections, identical level counts, zero unmatched), so KY's precision is a genuine hallucination rate and not the annotation-coverage figure guardrail 8 warns about. NV is the familiar case — ceiling **0.8679** (46/53) after the exhaustive pass, raw precision equal to it to four decimals. (The 0.7736 figure predates the 41→46 golden change.)
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
4. ~~Spot-check annotation is fine (same style as the golden states) — **do not** attempt exhaustive coverage; precision for NV/KY comes from extending the Task 1b audit to their in-scope extras, keeping the generalization table's methodology identical to the golden states'.~~ **SUPERSEDED 2026-08-16 by what the run found.** KY's golden turned out exhaustive, so its precision needs no audit; NV's audit is 12 verdicts and is drafted in `paper/results/task2_20260816/heldout_evidence.json`. Methodological uniformity is preserved by reporting **verified precision** (in-scope detections minus hallucinations, over in-scope detections) for all six states on that one definition — not by keeping every golden equally thin. ~~**Still owed: Emily's sign-off on the 12 NV verdicts, and Task 1b's ~165 verdicts for the golden four.**~~ **BOTH DONE 2026-08-23** — NV signed at 7 verdicts (the audit shrank from 12 when the 5 unannotated standards were annotated), and Task 1b signed at 156 verdicts for the golden four. Corpus-wide verified precision **0.9966**.

**Deliverable:** two held-out golden sets + their scores. Per guardrail 7 — if generalization doesn't hold, report it. **Delivered:** it holds; see the STATUS block.

---

### Task 3 — Build the depth-map on/off ablation

**Risk:** medium. **File:** `detector.py`. This is the evidence for the paper's central "classify by nesting POSITION, not document label" claim — without it, that claim is asserted, not shown.

1. Add an env-flag toggle that neutralizes Pass-1 depth-map inference. **Production default must be unchanged.**
2. Run the detector eval with the flag on and off across the golden states.

**Deliverable:** the on/off delta table in `paper/results/`.

> ✅ **BOTH ARMS RECORDED 2026-08-23 across all six states. Results: `paper/results/task3_20260822/`; repeated-run stability in `paper/results/task3_stability_20260823/`.**
>
> ⚠️ **THE STABILITY SWEEP IS PARTIAL AND ONE ACTION REMAINS.** 16 of 24 runs completed before a Bedrock Opus daily throttle. **Run 2 finished for all six states in both arms**, so every state has n=2; AZ has n=3, and CA has n=3 on the ON arm only. `off_run3_CA` was written with `n_detected=0` and is quarantined as `INVALID_THROTTLED_*`.
>
> **OUTSTANDING: finish run 3** — 8 runs (CA off, plus CO/TX/NV/KY in both arms), **~400K Opus tokens, ~15% of a daily quota, ~20 min.** That takes CO and KY — the two states carrying the entire effect — from n=2 to n=3. n=2 is enough to show the magnitude is unstable, which is the claim being made, but it is not a distribution and no mean or interval may be computed from it. Command shape is in `paper/results/task3_stability_20260823/manifest.json`; keep one report file per (arm, run, state) so `ablation_stability.py` can read them.
>
> **The effect is real, reproducible in direction, and CONDITIONAL.** Pooled by level, removing the depth map leaves **domain recall untouched at 1.000** and degrades exactly the levels whose identity depends on nesting position: strand 1.000→0.960, **sub_strand 1.000→0.875**, indicator 1.000→0.986. Per state, only **CO** and **KY** degrade; AZ, CA, TX and NV hold recall 1.000 in both arms.
>
> **Lead on the categorical evidence, not the rates.** Three regression cases fail with the depth map off and pass with it on, in *every* run: `CO-NO-SUB-STRAND` (the detector invents a sub_strand level in a document that has none — 9 spurious, tp=0/fp=9), `KY-BENCHMARK-IS-SUB-STRAND` (`Benchmark N.N` promoted to strand — literally classifying by LABEL), and `KY-STRAND-CODE-KEEPS-FULL-LABEL`.
>
> ⚠️ **Report off-arm recall as a RANGE, never a point value.** Repeated runs (n=2–3 per arm per state) reproduce the direction in every sample and never flip its sign, and **zero regression cases changed status**, but the magnitude swings: CO **0.71–0.86**, KY **0.91–0.98**. KY's second sample (0.977) is close to no effect at all. The frozen `task3_20260822` figures are one draw each.
>
> ⚠️ **The first off-arm attempt (2026-08-23T00:21Z) aborted on a Bedrock Opus daily-token throttle** and left a report in which five of six states read `recall=0.0` having never run. Quarantined as `INVALID_THROTTLED_*` with a `DO_NOT_USE.md`; never quote it. `compare_ablation.py` and `ablation_stability.py` both now REFUSE any state with `n_detected == 0` or a `depth_map_passed` that does not match its arm.

> **STATUS: FLAG LANDED 2026-08-22. Both arms still need recording.** `code_version_hash` is now **`288c64f1`** (this edit touched `detector.py`), which is the hash the combined re-record of Tasks 1 + 2 + this ablation must run at.
>
> **What landed.** `Config.DEPTH_MAP_ENABLED` (`ELS_DEPTH_MAP_ENABLED=false` to ablate; production default ON, asserted by a test). The gate is **inside `infer_depth_map`**, not at its call sites, so `detect_structure` and `detection_batching.prepare_detection_batches` cannot drift apart. Returning `None` reuses the signal an inference failure already produces, so the off-arm exercises the system's real graceful-degradation path rather than a strawman. `eval_detector` reports a third state, **`ABLATED`**, instead of grading a depth map that was never produced. 19 unit tests in `tests/unit/test_depth_map_ablation.py`; full suite 436 pass.
>
> ⚠️ **A cache-collision hazard was found and fixed before any run — read this before touching the cache key.** The flag lives in `config.py`, which `eval_common.code_version_hash` does **not** cover, so flipping it does not invalidate the cache. Without a key component the on-arm's cached detection would be replayed for the off-arm and the ablation would report **"no difference" having never run the off-arm at all** — a fabricated null result for the paper's central experiment. `--no-cache` does not save you either: it still WRITES to the shared key, poisoning the other arm's next cached run. `run_detector_cached` now appends `nodepthmap-` to the key when the flag is off.
>
> **Live smoke test (KY, off-arm, `--no-cache`, `outputs/08-22-26-4`) — the effect is large and lands exactly where the thesis predicts.** Against the on-arm's frozen Task 2 numbers (recall 1.000 every level, precision 1.000, code 44/44, 3/3 regressions PASS):
>
> | | on-arm (frozen, `3b445471`) | off-arm (`288c64f1`) |
> |---|---|---|
> | recall | **1.000** | 0.886 |
> | precision | **1.000** | 0.867 |
> | sub_strand recall | 1.00 | **0.60** |
> | strand precision | 1.00 | **0.40** |
> | code accuracy | 44/44 | 35/39 |
> | regressions | 3/3 PASS | **2 of 3 FAIL** |
>
> The failure mode is **level collapse, classified by label**: 6 of 12 `Benchmark N.N` elements came back as **strand** instead of sub_strand (`KY-BENCHMARK-IS-SUB-STRAND` FAIL), which is what drives sub_strand recall to 0.60 and strand precision to 0.40 simultaneously — the same 6 elements counted as both misses and false positives. `KY-STRAND-CODE-KEEPS-FULL-LABEL` also fails (4 strand codes lost their domain prefix). Indicators and domains are untouched (recall and precision 1.000 at both), so the depth map's contribution is specifically at the levels whose identity depends on *position* rather than on a distinctive surface form.
>
> ⚠️ This is **one run on one state** and the parser is known to vary between runs; treat it as a promising smoke test, not the recorded result. Record both arms across all six states before quoting anything.
>
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

> ✅ **DONE 2026-08-23 at `288c64f1`. Results: `paper/results/task4_20260823/`.** Zero Bedrock spend — the baseline is pure Python and the LLM arm is the frozen Task 1/Task 2 record, so no Opus quota was touched. Table: `paper/tables/baseline_comparison.tex`, generated by `build_baseline_table` in `generate_tables.py` (new `BASELINE_TAG`); wired into `sections/experiments_results.tex` as `sec:experiments-baseline` with a Task 12 prose brief.
>
> **The headline is the per-level row, not the mean.** The rule-based arm ties the LLM exactly at **domain (13/13 both)** and collapses below it — strand 0.240, sub_strand 0.667, indicator 0.137, against 1.000 at every level. Per state 1.000 → AZ 0.800, CA 0.640, CO 0.571, TX 0.625, NV **0.065**, KY **0.295**. Reporting a mean ("1.000 vs 0.500") hides exactly the gradient that makes the point: typography identifies a document's top division in all six states and nothing below it.
>
> **Three things the deliverable must carry, all in `findings.md`:**
> 1. **The handoff's precision warning points the OTHER way.** `fp_audit`'s verdicts turn on whether a title appears in the extraction — a test for *invention*. A rule-based extractor copies text verbatim and so scores verified precision **1.000 in five of six states** against the LLM's 0.9966. That number is real and substantively backwards; it must never sit in a table beside the LLM's. **Raw** precision is reported for both arms instead, with guardrail 8 attached to both columns. (CA is the one non-1.000 at 0.9432, and its 5 "hallucinations" are all *column fusion*, not fabrication — a finding about the audit instrument.)
> 2. **AZ raw precision is HIGHER for the baseline** (0.500 vs 0.417) — guardrail 7. Not a quality result: raw precision rewards under-emission, and the baseline puts 8 detections in scope where the LLM puts 12 against a 5-element golden.
> 3. **The brittleness probe must travel with the held-out numbers.** NV 0.065 is dominated by ONE unseen token shape (`SS.ID.PK1` — multi-letter code segments, which no development state prints); widening the pattern post hoc recovers **0.522**, and KY 0.295 → 0.409 with mid-line label recognition. Neither widening is adopted — both were motivated by inspecting the held-out states after the recorded run. Quoting the collapse without the probe overstates the case and invites the obvious "your regex was under-specified" objection; quoting it with the probe survives that objection and is the stronger claim.
>
> **A prior expectation was refuted and the paper must not repeat it.** The baseline's dominant failure is NOT misclassification. The failure decomposition (four buckets, summing to `n_golden` in all six states) shows missing elements are overwhelmingly *never emitted at all* — NV 43 of 46, KY 31 of 44 — not emitted at the wrong level. Where it does emit a golden title it usually places it correctly (level accuracy given title found: 1.000 on AZ/CA/NV/KY). Do not write this up as "rules find the text but mislabel it."
>
> **Instrument changes, all outside `code_version_hash`.** `evaluate_state` gained `detect_fn` / `grade_depth_map_pass` (optional, defaults unchanged) so the baseline is graded by the LLM's own path rather than a parallel grader, and `--report-json`'s row construction moved verbatim into `report_to_dict`. **Verified score-neutral: the frozen detected JSON replayed through the refactor gives all 26 graded fields identical in all six states.** ⚠️ A first neutrality check ran against `evaluation/.cache` and showed two false diffs — the cache holds a *different detector sample* than the recorded run (AZ 76 vs 66 elements; NV's Science description 3500 vs 2410 chars). **The cache is not the recorded run**; replay the frozen JSON.
>
> Three dead June-2026 files were deleted: `evaluation/baseline_detector.py` (never importable — `from .models` resolves to nothing), `run_comparison.py` (imports a module path that never existed), `compare_approaches.py` (graded through `evaluation/evaluate.py`, a second, older grader — the exact parallel-grader hazard this task forbids). **`evaluation/evaluate.py` is now orphaned and is still a second grading path — removing it was out of scope, and it remains a trap for a future session.**

1. Build a regex/heuristic structure extractor (bold/numbering/indentation) under `evaluation/baselines/`.
2. Grade it with the **same** `eval_detector` suite and the **same** goldens, so numbers are directly comparable.

**Note:** this baseline is a deliberate throwaway that lives only in `evaluation/baselines/`. It is not a licence to reintroduce rule-driven logic into `detector.py` / `parser.py` — see the CLAUDE.md design direction. It carries no per-document branch (enforced by `tests/unit/test_baseline_rule_based.py::test_no_state_name_appears_in_the_source`) and was developed against AZ/CA/CO/TX with NV/KY held out; **tuning it against a held-out state would void the comparison it exists to support.**

**Deliverable:** baseline-vs-LLM comparison table in `paper/results/`.

---

### Task 5 — Run stability/determinism passes for both suites

**Risk:** low. Supports the determinism claim; a known reviewer question for any LLM pipeline.

> ✅ **BLOCKER 1 CLEARED 2026-08-23 — `measure_stability` is repaired and Task 5 is unblocked.**
> `evaluation/eval_detector.py::measure_stability` was rewritten; 9 tests in
> `tests/unit/test_measure_stability.py` pin each fixed blind spot. Full suite: 475 pass.
> **This does NOT invalidate any recorded measurement** — `eval_common.code_version_hash`
> covers `detector.py` and `parser.py` only, and it is still `288c64f1`.
>
> Three blind spots fixed, all three of which the old code needed simultaneously to
> report its misleading 0.000:
> 1. **The graded run is now observation 0.** It previously spawned N probes and compared
>    them only to each other, so the run the suite actually scored was never in the
>    comparison. Costs nothing — that run already happened.
> 2. **Identity is the normalized TITLE, and `code` is now a compared FIELD.** Keying on
>    `(code, title)` meant an element whose code changed got a different key, failed the
>    membership test, and was silently skipped — the instrument was blindest to exactly the
>    intermittent malformed-code defect it most needed to catch. ⚠️ **Never put a field
>    under test back into the identity key**; that is the same bug in a new place, which is
>    why `level` is not in the key either.
> 3. **Presence and multiplicity are compared.** An element present in one run and absent
>    from another previously showed up only in the size stdev.
>
> It now returns a **dict, not a bare rate**: observation count and labels, size per
> observation and range, distinct unstable titles over titles compared, a per-dimension
> breakdown, how many observations differ from the graded run, up to 20 concrete examples,
> and an explicit warning that 0.000 at small N is not evidence of determinism. The
> rendered report prints denominators, and a clean result prints the NOTE rather than a
> bare 0.000.
>
> ⚠️ One bug was caught only by rendering a report, not by the unit tests written first:
> summing the per-dimension counters produced a "rate" of **2.000** — a title unstable in
> level, code and description counted three times against a denominator of one. The rate
> now counts DISTINCT unstable titles and is bounded [0, 1]; the per-dimension sum is
> reported separately as `n_dimension_disagreements`.
>
> **Blocker 2 still stands: split the runs across at least two sessions/days** (see below).
>
> **N DECIDED 2026-08-16: 5 runs per state per suite.** Budget is not the constraint (~60 runs ≈ $30–40, a few hours of wall time). Two things bind before N does, and both must be handled or the 5 runs measure the wrong thing:
>
> 1. ~~**Repair `measure_stability` first.**~~ **DONE 2026-08-23 — see the block above.** Historical detail: It keys elements on `(code, title)` and counts a disagreement only when a matched pair differs in `level`. It is therefore blind to the two failure modes actually observed — title truncation/fusion (July) and the `Foundation N.N` code defect (2026-08-16), the latter because a changed CODE changes the key, so the element silently drops out of the comparison instead of counting against stability. Fix the match key before spending the runs.
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

> 🔗 **This task carries an attached chore list — do it in the same window.** `detector.py` and `parser.py` are cost-gated between re-records: `eval_common.code_version_hash` hashes their raw bytes, currently **`288c64f1`**, and every recorded manifest under `paper/results/` cites it. So a docstring fix that would otherwise cost ~315K Opus tokens (12% of a daily quota) to re-validate is free once you are re-recording anyway.
>
> **The queue lives in [CLAUDE.md](../CLAUDE.md), "These two files are COST-GATED right now"** — that is the canonical copy, because it is the file a session reads *before* deciding to edit. As of 2026-08-23 it holds four items: three stale/missing claims in `detect_structure`'s docstring (wrong model, a confidence review-gate that does not exist, and Pass-1 depth-map inference omitted entirely) plus adding pre-normalization code logging inside `parser.py` so `validator._validate_code_shape` rejections can be localized.
>
> **Order matters.** Apply the queue, re-run, and record the **new** hash in this run's manifest — do not carry `288c64f1` forward. Then update `RUN_TAG`/`STATS_TAG` in `paper/analysis/generate_tables.py` and add the superseded tag to `SUPERSEDED_TAGS`, or the tables will silently keep rendering the old freeze (that failure has happened once already — see Task 1).

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

> ✅ **COMPLETE 2026-08-23 at `288c64f1`. Results: `paper/results/task8_20260823/`.** Zero Bedrock tokens — every input was already on disk. Regenerate with `python paper/analysis/dataset_stats.py && python paper/analysis/generate_tables.py`. Two tables now `\input` from the paper: `tables/dataset_stats.tex` in **§Corpus** (it describes the corpus, not a result) and `tables/confidence_distribution.tex` in §Experiments. LaTeX verified — 7pp, 0 undefined refs/citations, 0 warnings, and an A/B build confirms the two new tables add **zero** overfull boxes.
>
> **Descriptive:** 6 states, 70pp, 390 detected elements → **262 standards, 0 `standard_id` collisions**, age-band coverage **1.000** in every state (6 distinct bands). CO/TX realize no or almost no sub-strand tier — a four-level schema is not a four-level document. `blank_string` is 0 at every level, which is the standing check that `models._blank_to_none` is holding.
>
> **Confidence — the finding is NEGATIVE and must stay that way.** 7 distinct values in [0.85, 0.97] over 379 elements; the prompt's `<0.70` "guessing" band is used **zero** times and the `0.80–0.94` band only 32 times. The Medium claim splits: "85–90% of indicators at 0.95+" **reproduces** (236/263 = 89.7%, cite the measurement not the article), its second half — that the tail is "tables, footnotes, or unusual formatting" — is **REFUTED** (4 of 6 states have no sub-0.95 indicator; the tail is essentially all of KY, where all 26 score below the line, so the score moves per *document*), and the same article's 0.70 review gate is dead twice over — it does not exist, and zero elements would have tripped it.
>
> ⚠️ **The one trap in this result.** The single confirmed hallucination (NV `SS.CI.PK3`, 0.85) is also the single lowest-scoring element, and that reproduces across 14 same-config runs (966 elements, nothing else below 0.90). It looks like a working gate. It is not one, and the paper must say so in the same breath: there is exactly ONE distinct invented element, so a cut's false-negative rate is unmeasurable here; the prompt's own 0.80 boundary catches nothing; and the score is blind to the corpus's other non-verbatim category (all 39 `real_split_title` rows score ≥0.95). KY is the cleanest illustration — the best-evidenced detection in the corpus (recall/code/verified-precision all 1.000, detection-exhaustive golden) carries the *lowest* confidence.
>
> **Guardrail 2 re-verified against the live tree**, with a trap recorded: a repo-wide grep hits `needs_review`/`CONFIDENCE_THRESHOLD` under `infra/cdk/dist/` and `infra/cdk/cdk.out.deploy-dev/`. Those are stale build artifacts of a pre-2026 revision that really did gate; both are gitignored and untracked, so absent from a clean checkout and the arXiv tarball.
>
> **Repairs identified and deliberately deferred.** A sweep of both frozen files found `detector.detect_structure`'s docstring carries **three** defects: it names the wrong model ("Claude Sonnet 4.5"; it is Opus 4.6), it claims a step that does not exist ("Flags low-confidence elements for review" — precisely the false claim guardrail 2 exists to catch, in the function a reader opens first), and it **omits Pass-1 depth-map inference entirely** despite `detect_structure` calling `infer_depth_map` before chunking — the paper's central method claim, missing from the docstring of the function that implements it. `parser.py` swept clean; its one item is an addition (pre-normalization code logging). Fixing any of them changes `code_version_hash` `288c64f1`, which every recorded manifest cites, so they wait for the next hash-busting window — **Task 6**, which now carries the pointer. **Canonical queue: [CLAUDE.md](../CLAUDE.md), "These two files are COST-GATED right now."**
>
> **Note for Task 11:** the dataset table already carries the guardrail-1 tier columns, so the "corpus appendix table" should EXTEND it (adding `_trimmed` and source document names) rather than restate the same page counts in a second table.

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

**Risk:** low.

1. Create `paper/` with the current ACL template (`acl.sty` + `acl_natbib.bst`), two-column, final/non-anonymous mode. Author block: **Emily Cheyne, Founder, EdTech Co.**
2. Scaffold the 12 outline sections as stubs (see the plan file).
3. Set up `paper/results/` so every table regenerates from recorded JSON rather than being hand-typed (guardrail 6).
4. Confirm it builds: `cd paper && pdflatex main && pdflatex main`.

**Deliverable:** a building ACL skeleton.

---

### Task 11 — Produce figures and the corpus appendix table

**Risk:** low. **Has a dependency on Emily.**

1. Generate locally from `paper/results/`: confidence distribution, level-confusion matrix, cost-by-tier. Plus a canonical-schema tree diagram. **Still to do.**

   > **PROPOSED, decide during Task 12 when the figure budget is known: a small eval-methodology figure showing the DIRECT-vs-BATCHED split.** This is the hardest part of the methodology to convey in prose and it is load-bearing: `eval_detector` **re-runs detection live in-process** (direct path) against `{STATE}-extraction.json`, while `eval_parser` reads `{STATE}-detection.json`, the **deployed batched** detection. So the detector and parser tables in the same results folder are **not describing the same detection of the same document** — for AZ that is literally 66 elements vs 77. It also explains a result the paper must otherwise assert without mechanism: NV's Science description grades as `truncated 2410/3500` in the detector eval while the batched pipeline produces the full 3500 byte-exact, same code and same document. The figure would also carry the two-decoupled-goldens point (flat element list vs nested `NormalizedStandard`, annotated independently), currently documented only in `evaluation/README.md`. **Draw it in TikZ, not `diagrams`** — it is boxes and arrows with no AWS services, so icons add nothing — and place it in §Experiments rather than §System Architecture. If the figure budget forces a cut, this one outranks cost-by-tier: it is a correctness caveat rather than a nice-to-have.
2. ~~**Request from Emily:** the AWS architecture diagram, and any Standards Explorer / CloudWatch dashboard screenshots.~~ **RESOLVED 2026-08-23, with one item still OUTSTANDING:**
   - **Architecture diagram — DONE, and it is generated, not hand-drawn.** `paper/analysis/make_architecture_figure.py` renders `paper/figures/fig_architecture.{pdf,png}` from `documentation/ARCHITECTURE.md` using `diagrams` + graphviz with official AWS icons (`brew install graphviz && pip install diagrams`). Embedded as `\label{fig:architecture}` in `sections/system_architecture.tex`; the paper builds to 6pp with 0 undefined refs. Emily confirmed the stage order and that validation → persistence → Aurora is correct (see `persister.py`: `_load_validation_summary` reads the validation summary from the processed bucket, `_persist_single_record` loads each canonical record from S3, then `persist_standard` writes to Aurora). Model labels carry versions and were checked against `config.py`: Opus 4.6 (detection), **Haiku 4.5** (depth map — NOT 4.6), Sonnet 4.6 (parsing).
   - **CloudWatch dashboards — DROPPED, by Emily's call (2026-08-23).** They carry a lot of errors and support no claim the paper makes. Do not reinstate without a specific claim that needs them.
   - ⚠️ **OUTSTANDING — EMILY: retake the Standards Explorer screenshot once standards without the `SUBSET - ` prefix exist.** The current screenshot (AZ, `LL` → `LL.1` → `LL.1.1` → `LL.1.1.a`, age bands, page numbers, `Unverified` status) is good and shows no account IDs, ARNs, internal URLs or emails — but its document title reads **`SUBSET - Arizona Early Learning Standards`**. In a paper that already discloses subset-tier *evaluation*, a screenshot captioned SUBSET invites the reader to conclude the *product* only ever holds subsets, which is a stronger and false claim. **Task 6 produces full-document runs, so retake it after Task 6 lands.** The screenshot is worth keeping regardless: its `Unverified` status column is the `human_verified` workflow, which guardrail 2 requires be kept distinct from confidence scores.
3. **Emily confirmed every row of `standards/standards_tracking.md` is accurate (2026-08-23)**, so the source URLs are ready to use. Build the table from the **seven `File Cleaned: true` rows** (CA, AZ, TX, CO, NV-2023, KY — plus NV-2025, which is collected but has no golden); the two Florida rows and NV-2025 are `false` and are **not** in the six-state corpus. List them as collected-but-unused rather than dropping them silently, so the table does not imply the corpus is larger than it is. Build the corpus appendix table from `standards/standards_tracking.md` — source URL, year, retained page ranges after trimming. **This is what replaces shipping the PDFs** (they are third-party state-agency documents; only US *federal* works are automatically public domain under 17 USC §105, so redistributing them isn't ours to grant). Name California's source precisely.
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
