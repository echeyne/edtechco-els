# Drafting notes stripped from `paper/sections/*.tex`

Moved here 2026-09-07, before posting. These were LaTeX comments in the section
sources: drafting briefs, guardrail warnings, and the record of which readings
of a result were rejected and why. They are invisible in the PDF but ship in an
arXiv source tarball, several were long, and several had gone stale --- the
§8.7 brief had already been corrected once for saying quality at scale was not
measured.

They are kept rather than deleted because a few carry warnings a future editor
of this repo needs and that nothing else records: the guardrail-6 note on which
three numbers in the method section are *not* regenerable from
`paper/results/`, and the guardrail-1 warning that the scale table's own
`run_id` says `full08292026` and that name is wrong.

Ordered by source file. Line numbers are from the pre-strip files; use
`git show HEAD:paper/sections/<file>` for the exact originals.


## `sections/artifacts_statement.tex`


_lines 1--9_

```
% artifacts_statement.tex — Task 10 stub. Outline recovered verbatim from
% the original plan file fragment (see ../OUTLINE_NOTES.md). Draft at Task 12.
%
% Prompts/schema/golden examples in appendices; code and dataset not
% released; rights retained. Rights (tasking/arxiv_paper.md): in-paper
% disclosure only. No open-source release of code or dataset. arXiv
% license = the minimal "arXiv.org perpetual, non-exclusive license to
% distribute" (Task 13) — retains Emily's copyright, permits no
% redistribution or derivatives.
```

## `sections/conclusion.tex`


_lines 1--7_

```
% conclusion.tex — Task 10 stub. Outline recovered verbatim from the
% original plan file fragment (see ../OUTLINE_NOTES.md). Draft at Task 12.
%
% More states toward a national dataset; an MCP server exposing the
% normalized DB so external applications and agents can query standards
% directly, extending the existing els-explorer-api / agentcore-agent;
% downstream apps (Standards Explorer, Planning).
```

## `sections/corpus.tex`


_lines 1--33_

```
% corpus.tex — Task 10 stub. Reconstructed section (see ../OUTLINE_NOTES.md).
% Draft at Task 12. Outline:
%   - Three corpus tiers, not two: full -> _trimmed -> _only_subset. The two
%     reductions are NOT the same kind of reduction and the prose must not
%     blur them (correction of 2026-08-31):
%       * _trimmed removes NON-STANDARDS matter only -- front matter, preamble,
%         guiding-principles essays, appendices, acknowledgements -- and
%         retains 100% of the standards. It reduces page count and therefore
%         cost, NOT coverage. KY's 52pp of a 120pp publication is all of
%         Kentucky's standards.
%       * _only_subset is a genuine coverage reduction: ~1-2 domains, fully
%         annotated, cheap to iterate on. THIS is the tier guardrail 3's
%         "favorable preprocessing" disclosure is really about.
%     Both get disclosed with retained page ranges (guardrail 3); only
%     _only_subset gets the "favorable preprocessing" framing.
%   - CO is a special case worth one sentence: colorado_3_5_trimmed_2020.pdf
%     (41pp) equals the FULL Ages 3-5 document (41pp) -- nothing was cut from
%     it. The 187pp birth-to-8 file is the wider publication that band is drawn
%     from (its TOC puts "Ages 3-5" at p77), so CO's out-of-scope content is
%     other AGE BANDS, not trimmed-away standards.
%   - The corpus tier table (Task 11 deliverable, sourced from
%     paper/results/corpus_tiers.json) belongs here.
%   - Name California's source precisely: the PTKLF "at a glance" document
%     (ptklfataglance.pdf, 68pp), not an error in standards_tracking.md.
%   - The held-out canary is NV-2023 (nevada_standards_2023_only_subset.pdf,
%     multi-domain) — explicitly NOT NV-SES-2025 (single-domain, too narrow
%     to support a generalization claim).
%   - State which numbers in the paper are subset-tier vs. trimmed-tier
%     (guardrail 1) — this section is the one place that distinction gets
%     explained once, rather than re-derived at every table. Say explicitly
%     that the trimmed tier is COMPLETE in standards content, or a reader
%     takes the word "trimmed" for "excerpt" and reads Task 6's cost/scale
%     numbers as partial-document numbers.
```

_lines 38--44_

```
% DRAFTED 2026-09-04 (review pass). The section previously held only the table
% and the TODO below; the introduction promised that this section states the
% tiers and the RETAINED PAGE RANGES (guardrail 3), which nothing in the repo
% recorded. paper/analysis/corpus_page_ranges.py now derives them from the
% PDFs themselves (text match of every tier page back to the published PDF)
% into paper/results/corpus_page_ranges.json, rendered as
% tables/corpus_pages.tex in Appendix D.
```

_lines 91--109_

```
% Earlier brief, retained: The table below is Task 8's deliverable and it already
% carries the guardrail-1 tier columns (Subset pp / Full pp), so Task 11's
% "corpus appendix table" should EXTEND this one -- adding the _trimmed tier
% and the source document names -- rather than introduce a second table that
% restates the same page counts.
%
% Three things the prose must do that the table cannot:
%   1. Disclose the manual trimming (guardrail 3) with retained page ranges.
%      The subset tier is favourable preprocessing and must be stated plainly,
%      not inferred from a page-count column.
%   2. Name California's source precisely: the PTKLF "at a glance" document
%      (ptklfataglance.pdf, 68pp).
%   3. Say that the held-out canary is NV-2023, explicitly NOT NV-SES-2025.
%
% Read the "Age bands" column carefully before writing about it: it is the
% count of DISTINCT bands in that state, not coverage. Coverage is 1.000
% everywhere -- every one of the 262 standards carries an age band -- which is
% worth a sentence because it is a schema-completeness result, not a document
% property.
```

## `sections/discussion_limitations.tex`


_lines 1--30_

```
% discussion_limitations.tex — Task 10 stub. Outline recovered verbatim
% from the original plan file fragment (see ../OUTLINE_NOTES.md). Draft at
% Task 12; re-read all guardrails in tasking/arxiv_paper.md before writing.
%
% Subset-scoped quality metrics; 4 golden + 2 held-out states; English/
% US-only; LLM nondeterminism; Textract dependence; trimming as favorable
% preprocessing (guardrail 3 — disclose with retained page ranges, don't bury).
%
% ⚠️ CORRECTED 2026-08-31 — do NOT write the scale limitation as a COVERAGE
% limitation. An earlier draft of Task 6's findings read KY 52/120pp and CO
% 41/187pp as coverage fractions and made full-document scale a stated
% limitation on that basis. It is not: the _trimmed tier removes only
% non-standards matter (front matter, essays, appendices) and retains 100% of
% the standards, so Task 6's runs cover every standard in both documents.
%
% What IS still a limitation, and the honest way to write it:
%   1. PAGE-COUNT scale, as a cost/batching claim rather than a coverage one.
%      Task 6 exercises 18 and 17 detection chunks over 4 Map iterations; its
%      token and latency figures must not be extrapolated to untrimmed page
%      counts, and no document as large as AZ (217pp published) has been run
%      end to end.
%   2. Trimming is still preprocessing a deployment would have to do or absorb
%      — the pipeline was never asked to ignore 68pp of Kentucky preamble on
%      its own. Say that plainly; it is the real residual cost of the tier.
%   3. QUALITY at the trimmed tier is measured only where a golden reaches it.
%      KY's detector golden is detection-exhaustive, which is the one avenue to
%      quality-at-scale evidence without new annotation (Task 6 step 4, owed).
%   4. CO's out-of-scope content is other AGE BANDS (birth-to-3 and 5-8 of the
%      187pp birth-to-8 publication), not trimmed-away standards. Every CO
%      number in the paper is the Ages 3-5 band.
```

## `sections/ethics.tex`


_lines 1--4_

```
% ethics.tex — Task 10 stub. Outline recovered verbatim from the original
% plan file fragment (see ../OUTLINE_NOTES.md). Draft at Task 12.
%
% Education-data stewardship, human verification, no student data.
```

## `sections/experiments_results.tex`


_lines 1--23_

```
% experiments_results.tex — Task 10 stub, but with the results-plumbing
% mechanism (guardrail 6) wired in and demonstrated: the two \input tables
% below are auto-generated from paper/results/task{1,2}_20260816/summary.json
% by paper/analysis/generate_tables.py — regenerate with
% `python paper/analysis/generate_tables.py`, never hand-edit
% paper/tables/*.tex directly.
%
% Subsections to add as later tasks land (Task 3-8 each contribute a table
% via the same generate_tables.py mechanism — extend it, don't hand-type):
%   - Headline quality (below) — DONE, Tasks 1/2.
%   - Verified precision / hallucination rate (Task 1b) — not yet run.
%   - Depth-map on/off ablation (Task 3).
%   - Rule-based baseline comparison (Task 4) — DONE.
%   - Stability/determinism (Task 5).
%   - Cost/latency/scale, _trimmed tier (complete standards content, NOT the
%     full published PDF and NOT an excerpt -- see
%     paper/results/task6_20260830/findings.md), clearly separated from the
%     subset-tier quality tables above (Task 6, guardrail 1).
%   - Model tier / chunk overlap / two-stage ablations (Task 7).
%   - Dataset descriptive stats + re-measured confidence distribution
%     (Task 8, guardrail 4 — no unmeasured Medium numbers) — DONE. The
%     confidence half is below; the descriptive-stats table lives in
%     \S\ref{sec:corpus}, where it describes the corpus rather than a result.
```

_lines 61--88_

```
% DRAFTED 2026-09-04. The brief below is RETAINED as the reasoning behind the
% prose above -- it records which readings were rejected and why, which the
% prose itself cannot carry. Task 13 strips all comments before submission. Lead on the LEVEL-WISE result, not on a mean across
% states: four of six states are unaffected, so an aggregate understates CO/KY
% and overstates the rest. The supportable claim is conditional -- the depth map
% is what makes position-dependent levels recoverable.
%
% STRONGEST EVIDENCE IS THE LEVEL DISTRIBUTION, not recall and not the
% regression cases. KY's golden is 3 domain / 5 strand / 10 sub_strand / 26
% indicator. The ON arm reproduces that EXACTLY in all three runs; the OFF arm
% inflates strand and deflates sub_strand in all three (5 -> 8/7/10, 10 ->
% 7/9/6) with domain and indicator untouched at 3 and 26. Invariant across runs
% and independent of golden size, which recall is not (CO's golden is 7
% elements).
%
% Report off-arm recall as a RANGE, never a point value: CO 0.71-0.86, KY
% 0.89-0.98 at n=3. The ON arm is 1.000 in all 18 runs, stdev 0.000.
%
% ⚠️ DO NOT write "no regression case changed status across runs" -- that was an
% n=2 finding and n=3 REFUTED it (2026-08-24). CO-NO-SUB-STRAND went FAIL, FAIL,
% PASS. Two cases are reproducible, both KY: KY-BENCHMARK-IS-SUB-STRAND and
% KY-STRAND-CODE-KEEPS-FULL-LABEL. The table caption is generated from
% stability_analysis.json and already says this correctly -- do not contradict
% it in prose. CO still degrades in run 3 (recall 0.857, dropping a golden
% strand the ON arm never drops), so the state-level effect IS reproducible;
% only its surface form on CO is not.
%
% See paper/results/task3_stability_20260823/findings.md.
```

_lines 143--186_

```
% DRAFTED 2026-09-04. The brief below is RETAINED as the reasoning behind the
% prose above -- it records which readings were rejected and why, which the
% prose itself cannot carry. Task 13 strips all comments before submission. Four things to lead with, in this order.
%
% 1. LEAD ON THE PER-LEVEL POOLED ROW, not the mean. The rule-based arm matches
%    the LLM exactly at DOMAIN (13/13 both) and collapses below it: strand
%    24.0%, sub_strand 66.7%, indicator 13.7%. That gradient is the paper's
%    thesis measured on its own foil -- typography identifies the top division
%    in every document, and nothing below it is identifiable without nesting
%    position. A mean ("1.000 vs 0.500") hides exactly the structure that makes
%    the point.
%
% 2. DO NOT READ THE RAW-PRECISION COLUMNS AS QUALITY (guardrail 8). AZ shows
%    the rule-based arm ABOVE the LLM (50.0 vs 41.7) purely because it emits
%    fewer in-scope detections against a 5-element spot-check golden. Say so in
%    the same breath, or the table invites the wrong reading. KY is the one
%    state where precision means what it says.
%
% 3. THE HELD-OUT COLLAPSE IS THE GENERALIZATION EVIDENCE, and it must be
%    reported with the brittleness probe attached or it overstates the case: NV
%    6.5% is dominated by one token shape the four development documents never
%    printed (SS.ID.PK1), and widening the pattern post hoc recovers 52.2%.
%    The honest claim is the one that survives the repair -- rules encode the
%    shapes their author has seen, and even repaired they reach roughly half
%    the LLM's recall.
%
% 4. VERIFIED PRECISION IS ABSENT FROM THE TABLE ON PURPOSE, and the prose must
%    say why or a reader will ask. The false-positive audit decides its verdicts
%    by asking whether a detected title appears in the source text -- a test for
%    INVENTION. A rule-based extractor copies text verbatim and cannot invent,
%    so it measures 1.000 in five of six states against the LLM's 0.9966. That
%    number is real and substantively backwards. (CA is the lone exception at
%    0.9432, and all five of its flagged rows are column FUSION, not
%    fabrication -- a finding about the audit instrument, worth a sentence in
%    \S\ref{sec:discussion-limitations}.) Evidence: baseline_fp_audit in
%    paper/results/task4_20260823/baseline_comparison.json.
%
% 5. Note what the baseline is NOT: it has no depth-map stage, so that column
%    reads ABLATED rather than FAIL, and it is deterministic, so a single run
%    is sufficient (contrast \S\ref{sec:experiments-ablation}).
%
% ⚠️ Keep tables/baseline_comparison.tex's caption SHORT when revising it. The
% first version carried all of the above and ran to 13 lines, which made the
% float overflow page 4 -- bottom margin 2pt, bibliography off the sheet edge.
```

_lines 395--459_

```
% DRAFTED 2026-09-04. The brief below is RETAINED as the reasoning behind the
% prose above -- it records which readings were rejected and why, which the
% prose itself cannot carry. Task 13 strips all comments before submission.
%
% ⚠️ GUARDRAIL 1 IS THE WHOLE POINT OF THIS SUBSECTION. Table~\ref{tab:scale} is
% the ONLY table in the paper that is not the _only_subset tier. It is _trimmed:
% Kentucky 52 pages, Colorado 41. The pipeline run_id literally says
% "full08292026" and that name is WRONG -- verified against the Step Functions
% execution input and PyMuPDF page counts. NEVER call these full-document
% numbers, and never let a reader carry a quality number from the subset tables
% into this table or vice versa.
%
% ⚠️ BUT THE OTHER MISREADING IS NOW THE LIKELIER ONE (corrected 2026-08-31).
% _trimmed removes NON-STANDARDS matter only -- front matter, essays,
% appendices -- and retains 100% OF THE STANDARDS. 52/120 and 41/187 are NOT
% coverage fractions, and an earlier draft of task6_20260830/findings.md read
% them as such. The prose must say what the tier means in the same breath as
% the label, or "trimmed" reads as "excerpt" and these become partial-document
% numbers in the reader's head. Kentucky's 52 pages are all of Kentucky's
% standards; Colorado's 41 are the COMPLETE Ages 3-5 document (identical to its
% full page count -- nothing was cut), the band every CO number in this paper
% uses, drawn from a wider 187pp birth-to-8 publication whose other age bands
% are out of scope rather than trimmed away.
%
% THE CLAIM THIS TABLE SUPPORTS, and the only one it supports: the
% prepare -> Map -> merge batching path is genuinely exercised. At the subset
% tier every state produces <=5 chunks against MAX_CHUNKS_PER_BATCH=5 and <=3
% domains against MAX_DOMAINS_PER_BATCH=3, so both batching layers collapse to a
% single batch, the Map has ONE iteration and the merge is a NO-OP. That is why
% no subset-tier measurement could support the batching claim at all. Here the
% Map iterates 4 times per run and the merge removes 34 (KY) and 90 (CO)
% duplicate elements. Say that contrast explicitly -- it is the reason the
% table exists.
%
% DO NOT claim quality at scale from THIS table -- it carries cost, latency and
% batching evidence only, and its runs are not graded against goldens.
% ⚠️ UPDATED 2026-09-07: quality at scale IS now measured, but in
% \S\ref{sec:experiments-scale-quality} and from different runs. Keep the two
% apart: this table says the batching path is exercised, that subsection says
% what the output is worth. Neither number may be carried into the other's
% table.
%
% NO COST COLUMN, DELIBERATELY. None of the five hardcoded BEDROCK_PRICING rates
% could be verified on 2026-08-30: the AWS Price List API's AmazonBedrock
% service code carries only legacy Claude 2.x/3.x models, and the current-gen
% code has no entry for Opus 4.6 or Sonnet 4.6. Report tokens. If Emily later
% supplies verified rates, add cost WITH the rate date cited inline (guardrail:
% "report real measured per-run cost", not an invented one).
%
% WORTH ONE SENTENCE, ties back to \S\ref{sec:method-model-assignment}: the
% depth-map pass costs about 6-9% of detection's input tokens (12,153/201,574 KY,
% 19,613/223,276 CO; an earlier draft of this comment said 3%, which is wrong)
% and runs ONCE per document, while detection -- the hard classification -- is the only stage
% invoked once per chunk. That is the "cheapest model that suffices" principle
% showing up in the token budget rather than being asserted.
%
% LIMITATION TO CARRY INTO \S\ref{sec:discussion-limitations}, and write it as
% a PAGE-COUNT limitation, not a coverage one: these runs chunk 18 and 17 times
% over 4 Map iterations, so the token and latency figures must not be
% extrapolated to untrimmed page counts, and no document as large as AZ (217pp
% published) has been run end to end. Trimming is also still preprocessing a
% deployment would have to do or absorb -- the pipeline was never asked to
% ignore 68pp of Kentucky preamble on its own. State both; do not bury them.
% Do NOT write "full documents remain unmeasured" without that qualification:
% every standard in both documents WAS processed.
```

## `sections/introduction.tex`


_lines 1--6_

```
% introduction.tex — drafted Task 12 (2026-08-30).
% Guardrails observed: corpus tier stated explicitly for every quality number
% (1); no confidence-gate language (2); trimming disclosed here and in
% \S\ref{sec:corpus} (3); no unmeasured Medium numbers (4); the in-context
% argument is made on no-labeled-corpus grounds, with no invented fine-tuning
% cost (5); held-out results reported as measured (7).
```

## `sections/method.tex`


_lines 1--31_

```
% method.tex — drafted Task 12 (2026-08-30).
% Outline for this section was recovered verbatim from the original plan file
% fragment (see ../OUTLINE_NOTES.md); subsection order follows it.
%
% Constants verified against the live tree (detector.py, config.py):
%   DEFAULT_TARGET_TOKENS 2000, DEFAULT_OVERLAP_TOKENS 500,
%   DEPTH_MAP_SAMPLE_TOKENS 6000, DEPTH_MAP_MIN_PER_BUCKET 12,
%   DERIVED_CODE_MAX_LEN 5, MAX_CHUNKS_PER_BATCH 5, MAX_DOMAINS_PER_BATCH 3.
% Model IDs from config.py:15-21.
%
% GUARDRAIL 2 IS LIVE IN 6.5. Confidence gates nothing; there is no
% needs_review field anywhere in src/. Do not reintroduce review-gate language.
%
% ⚠️ GUARDRAIL 6 — RESOLVED 2026-09-04 (review). Three numbers in this section
% were NOT regenerable from paper/results/: they live in CLAUDE.md's engineering
% record with no recorded JSON or generating command. Numbers 1 and 2 are now
% stated QUALITATIVELY in the prose, explicitly attributed to the project's
% design notes rather than to a paper artifact; number 3 is now stated as a
% count over the annotated NV parser golden (24 of 24), which IS regenerable
% from evaluation/ground_truth_parser/NV.json (every annotated standard has a
% sub_strand code that does not extend its strand code). The original figures
% and their provenance are kept below so a future recording can restore them:
%   1. "eleven of 44 elements received a different code on at least one run"
%      (\S6.2) — CLAUDE.md, "The one derivation that came back to Python",
%      measured 2026-08-01 over 3 KY runs on one frozen extraction.
%   2. "six heading buckets hold nineteen of 1,741 blocks" (\S6.2) —
%      CLAUDE.md, "Where Pass-1 loses a LEVEL", KY full document.
%   3. "fifteen of fifteen Nevada standards" break the chain (\S6.3) —
%      CLAUDE.md, "Where a printed code is not unique" / the code-shape guard.
% Number 3 is the cheapest to discharge: it is derivable from
% evaluation/ground_truth_parser/NV.json plus the recorded NV parser report.
```

## `sections/related_work.tex`


_lines 1--14_

```
% related_work.tex — Task 9 deliverable (drafted 2026-08-17); condensed and
% re-argued 2026-09-05. The 2026-08-17 draft enumerated systems roughly one per
% sentence and ran ~940 words. Each subsection now carries a single claim and
% groups its citations under it, at ~735 words (-22%). Citation COVERAGE is
% unchanged — every key cited by the earlier draft is still cited here, and
% nothing else in the paper cites a key that this section dropped.
% Citations use natbib (\citep/\citet) against ../references.bib.
% Guardrails observed: no unmeasured Medium numbers; no confidence-gate claim
% (verification is blanket, confidence gates nothing); no invented fine-tuning
% cost comparison — the in-context argument is made on no-labeled-corpus grounds.
% One factual softening vs. the 2026-08-17 draft: aggarwal2025fiscal is credited
% with validating against the documents' "own internal consistency", not
% specifically their "arithmetic structure", which REVIEW_references.md
% (2026-09-04) could not confirm from the abstract.
```

## `sections/schema.tex`


_lines 1--6_

```
% schema.tex — drafted Task 12 (2026-08-30).
% Facts verified against the live tree: models.py (HierarchyLevelEnum,
% NormalizedStandard, HierarchyLevel), parser.py generate_standard_id,
% infra/migrations/005_add_verification_columns.sql. Guardrail 2 observed:
% human_verified is a separate per-element workflow and is NOT a confidence
% gate -- see \S\ref{sec:method-confidence}.
```

_lines 36--36_

```
%
```

_lines 41--41_

```
%
```

## `sections/system_architecture.tex`


_lines 1--8_

```
% system_architecture.tex — Task 10 stub. Outline recovered verbatim from
% the original plan file fragment (see ../OUTLINE_NOTES.md). Draft at Task 12.
%
% Serverless stages ingestion -> extraction -> detection -> parsing ->
% validation -> persistence; prepare -> Step Functions Map -> merge
% batching; S3-as-bus intermediates. Note the batched production path
% differs from the direct path the evals use — say so (see
% tasking/arxiv_paper.md's batched-vs-direct background note).
```

_lines 38--45_

```
% Standards Explorer screenshot — supplied by Emily 2026-09-04 as
% figures/colorado_els.png, replacing an earlier Arizona capture whose document
% title read "SUBSET - Arizona Early Learning Standards". That title would have
% invited the reader to conclude the PRODUCT only ever holds subsets, which is a
% stronger and false claim than the subset-tier EVALUATION the paper discloses.
% This capture is Colorado at the _trimmed tier: the complete Ages 3-5 document.
% Checked before inclusion: no account IDs, ARNs, internal URLs or email
% addresses are visible.
```


## Pass-2 review edits (2026-09-19)

Recorded here because the sections carry no comments. Each entry names the
section, what changed, and the artifact that decided it. The pass also removed
every em dash from `main.tex`, `sections/*.tex`, the three generators and the
review deliverables; the 26 literal em dashes inside the verbatim prompt
listings of `tables/appendix_prompts.tex` are the prompts' own text and were
left as the system emits them.

### `sections/introduction.tex`

Contribution 4 now says the 297 in-scope detections were audited "at an
annotated subset tier". `TODO_remaining.md` item 3 records that all four
occurrences of 297 were tier-qualified on 2026-09-07; this one was not, and it
sits two paragraphs from the 277 trimmed-tier count.

### `sections/related_work.tex`

Three citation clusters were carrying a member that does not support the
sentence, a hazard the regrouping of 2026-09-07 created:

- `wehnert2025hips` sat inside the cluster whose shared premise is that
  "hierarchy can be learned, because supervision exists". Its arXiv abstract
  (2509.00909) describes a table-of-contents path and an LLM-refined
  typography path, neither trained. It is now named with `jeong2025docsray` as
  a training-free neighbor, scoped to one genre.
- `liu2022fewshot` sat inside the cluster supporting "generative extraction is
  competitive ... where labeled corpora are scarce". The paper argues the
  opposite where labels exist, which is how the introduction already cites it.
  It now carries its own clause.
- `ohs2015elof` supported "no national framework spans the age band". The ELOF
  does span birth to five; what it does not do is bind states. The sentence now
  says the one federal framework binds Head Start programs alone.
- "its targets are flat" for the six-paper lineage cluster was not verifiable
  for Nougat (markup output) or GROBID (sectioned TEI). It now says none of
  them targets a typed tree carrying codes and ancestry, which is the claim the
  gap argument needs.
- `gilardi2023chatgpt` and `tan2024large` are about the model as annotator, not
  selective allocation; the sentence now names that alternative too.

### `sections/corpus.tex`, `sections/discussion_limitations.tex`, dataset and corpus-appendix captions

"Every quality number in this paper is computed at this tier" was false once
\S6.8 began grading the trimmed tier. `TODO_remaining.md` item 3 fixed the
abstract and \S1 but not \S3, \S7.2, or the two generated captions. All four
now say "headline" and point at the trimmed-tier exception.

### `sections/method.tex`, \S5.7

"finds fifteen that appear, of which ten are distinctive ... and five are
domain names shared across states" did not match
`results/task12_20260905/prompt_example_provenance.json`, which records 15
distinctive strings (10 development, 5 held-out) and one shared title,
"Approaches to Learning". The next sentence already said ten plus five. The
count is now fifteen distinctive plus one shared.

### `sections/experiments_results.tex`, \S6.7

The prose said the depth-map pass costs 0.3--0.6% and detection 57--60%; the
caption, computed at build time, says 0.3--0.5% and 57--59% (KY 0.32% and
59.4%, CO 0.54% and 57.1%). The prose now matches the computed figures.

### `sections/experiments_results.tex` \S6.8 and `discussion_limitations.tex` \S7.5

"164 elements ... with a standard deviation of zero, the same elements every
time" was checked directly against the three detection files under
`outputs/ky-3runs-09-07-26/`. The count is 164 in each run, but the sets are
not identical: runs 1 and 3 agree exactly and run 2 differs on five elements,
so 159 are common to all three. `task13_20260907/findings.md` asserted identity
from the count alone. Both sites now state the count and the 159. The
"systematic rather than sampling noise" reading survives; the identity claim
did not. `CLAUDE.md`'s "Where `age_band` destabilizes at scale" section and
`task13_20260907/findings.md` made the same identity claim; at the author's
request both now carry a dated correction (the findings file keeps its original
sentence with a superseding note, per the repo's rule that a recording is the
record of what was measured).

### `sections/discussion_limitations.tex`, \S7.3

"Every `Benchmark N.N` identifier the document prints (17 of 17)" was measured
against `ground_truth_detector/KY_trimmed.json` and the run-1 extraction: 18
distinct identifiers printed, 18 in the golden. "15 of 15" checked. The
sentence now says 18 of 18 and "distinct".

The label `sec:discussion-agebandevfect` was renamed
`sec:discussion-ageband-defect`; nothing referenced it.

### `sections/experiments_results.tex`, \S6.8 paragraph heading

"Detection is complete at scale" became "Detection recovers the whole
reference set at scale", since the paragraph two below states the recall
ceiling and the heading should not outrun it.

### `main.tex` abstract and `sections/introduction.tex` contribution 2

"deterministic, collision-free identifiers" became "deterministic
identifiers" in the abstract, and "deterministic identifiers whose collisions
are measured rather than assumed" in contribution 2, at the author's request
after pass 2. Collision-free is true at the subset tier and true by
construction at scale, where \S6.8 says the zero is uninformative because the
resolver renames every collision; the abstract should not lean on a property
the paper itself discounts. `arxiv_abstract.txt` regenerated: 1,864 characters.
