# Task 4 — Rule-based baseline vs the LLM detector

**Recorded 2026-08-23** at `code_version_hash 288c64f1`, against
`outputs/08-22-26-4/`, graded by `evaluation/eval_detector.grade_elements`
against `evaluation/ground_truth_detector/{STATE}.json`.

**Corpus tier: `_only_subset`** — AZ 15pp, CA 13pp, CO 10pp, TX 9pp, NV 15pp of
98, KY 8pp of 120. Manually trimmed subsets, never full documents (guardrail 1).

**Zero Bedrock spend.** The baseline is pure Python; the LLM arm is the frozen
Task 1 / Task 2 reports and was not re-run. No Opus quota was consumed.

---

## Headline

Both arms, same suite, same goldens, same matcher:

| pooled by level | LLM recall | rule-based recall |
|---|---|---|
| domain | 1.000 (13/13) | **1.000 (13/13)** |
| strand | 1.000 (25/25) | 0.240 (6/25) |
| sub_strand | 1.000 (24/24) | 0.667 (16/24) |
| indicator | 1.000 (73/73) | 0.137 (10/73) |

Per state, recall: AZ 1.000 → 0.800, CA 1.000 → 0.640, CO 1.000 → 0.571,
TX 1.000 → 0.625, NV 1.000 → **0.065**, KY 1.000 → **0.295**.
Mean 1.000 → 0.4995.

**Lead on the per-level row, not the mean.** The rule-based arm ties the LLM
exactly at domain and falls away below it. That gradient is the paper's central
claim measured on its own foil: typography identifies a document's top division
in all six states, and nothing below it is identifiable from typography and
numbering alone. A single mean ("1.000 vs 0.500") hides precisely the structure
that makes the point.

## What the baseline is

`evaluation/baselines/rule_based.py`, ~600 lines, no Bedrock, deterministic.
Signals, all document-agnostic:

1. numbering paths (`1.`, `1.1`, `a.`, `I.A.2`, `PK3.I.A.2`), nesting depth gives the level;
2. structural label words (`Domain`/`Strand`/`Standard`/`Benchmark`/`Concept`/
   `Foundation`/…) → level, via a table frozen before scoring;
3. typography — ALL-CAPS, and font size from bounding-box height relative to the
   page median and 90th percentile;
4. layout — bounding-box `Left` clustered into columns, `Width` separating
   full-width prose from column cells, giving column-aware reading order.

(3) and (4) matter: Textract blocks carry `geometry`, and the June 2026
predecessor of this file used regex alone. Column reconstruction is most of what
separates a fair baseline from a straw man on CO's and CA's multi-column
spreads.

**Two concessions were made in the baseline's favour, and both should be
stated:** it is handed `detector.derive_code_from_title` for elements the
document gives no code (otherwise it scores 0 on code accuracy for a reason
about schema conventions rather than structure extraction), and it emits one
element per age-band column where a document prints one (otherwise it can never
match an age-banded golden entry, and those are 14 of CA's 25 and 4 of TX's 8).

**Development discipline.** Built and iterated against AZ, CA, CO and TX only.
NV and KY were not inspected or scored until the recorded run — the same
held-out protocol the LLM detector is held to.
`tests/unit/test_baseline_rule_based.py::test_no_state_name_appears_in_the_source`
enforces the absence of a per-document branch in executable code.

---

## ⚠️ Precision: read the caveats before quoting anything

### Raw precision is reported for both arms, and is not quality

| | AZ | CA | CO | TX | NV | KY |
|---|---|---|---|---|---|---|
| LLM raw precision | 0.417 | 0.205 | 0.167 | 0.320 | 0.868 | 1.000 |
| rule-based raw precision | **0.500** | 0.182 | 0.082 | 0.135 | 0.167 | 1.000 |

Guardrail 8 applies to both columns: outside KY, whose golden is
detection-exhaustive, raw precision measures annotation coverage, not
correctness.

**AZ shows the rule-based arm ABOVE the LLM, and that must be reported**
(guardrail 7). It is not a quality result. Raw precision rewards
under-emission: against a 5-element spot-check golden the baseline puts 8
detections in scope where the LLM puts 12, so it has fewer unmatched in-scope
detections to be charged for. Report it with the explanation attached or the
table invites the wrong reading.

### Verified precision is deliberately NOT compared

The handoff warned against comparing the LLM's *verified* precision to the
baseline's *raw* precision. The real hazard is sharper and points the other way.

`heldout_evidence.fp_audit` decides its verdicts by asking whether a detected
title appears in the extraction — a test designed for a generator whose failure
mode is **invention**. A rule-based extractor copies block text verbatim and
cannot invent, so its extras classify as `real_unannotated` almost by
construction. Measured (`baseline_fp_audit` in `baseline_comparison.json`):
verified precision **1.000 in five of six states**, against the LLM's 0.9966.

That number is arithmetically correct and substantively backwards, and it must
not appear in a table beside the LLM's.

Two details worth keeping:

* **CA is the exception, at 0.9432 (5 "hallucinated").** Inspecting them, all
  five are *column fusion*, not invention — e.g. `"Using Words Discovering Use
  English words, mainly consisting of concrete nouns…"`, where the proficiency
  column header `Discovering` has been fused into the title. So applied to a
  rule-based system the `hallucinated` verdict detects fusion rather than
  fabrication. That is a real finding about the audit instrument, and a reason
  not to reuse its vocabulary across system types without re-deriving it.
* The audit's denominator (`annotation_coverage.n_detected_in_annotated_domains`)
  does not always equal the grader's in-scope count — AZ 5 vs 8 — because the
  grader can match an element through its domain-agnostic fallback whose own
  enclosing domain is unannotated. Pre-existing, and immaterial here only
  because the baseline's verified precision is not published.

### The dimension that does discriminate

Because `_match_key` carries the level, an element found at the wrong level and
an element not found at all are indistinguishable in the headline. Decomposing
every golden miss (`failure_decomposition`; the four buckets sum to `n_golden`
in all six states):

| state | title not found | found, wrong level | right level, age band differs | fully matched |
|---|---|---|---|---|
| AZ | 1 | 0 | 0 | 4 |
| CA | 6 | 0 | 3 | 16 |
| CO | 2 | 1 | 0 | 4 |
| TX | 2 | 1 | 0 | 5 |
| NV | 43 | 0 | 0 | 3 |
| KY | 31 | 0 | 0 | 13 |

**This overturned my prior expectation and is worth stating plainly.** I
expected the baseline's dominant failure to be misclassification — right text,
wrong level. It is not. The dominant failure is *not producing the text at
all*: the heading never fires, so the element is never emitted to be
misclassified. Where the baseline does emit a golden title it usually puts it
at the right level (level accuracy given title found: 1.000 on AZ/CA/NV/KY,
0.800 CO, 0.833 TX).

The strand-level pooled recall of 0.240 is therefore mostly *missing strands*,
not *strands called something else*.

---

## Held-out generalization, with the brittleness probe attached

NV 0.065 and KY 0.295 are far below the four development states. Diagnosed to
two specific causes, both confirmed against the raw extraction:

* **NV** codes its leaves `SS.ID.PK1.` — multi-letter alphabetic segments. The
  numbering pattern's first-segment alternation is `\d{1,3}|[IVXL]{1,5}|[A-Z]`,
  written from four documents none of which printed a two-letter segment. It
  matches none of NV's indicators.
* **KY** prints its strand label mid-line — `Approaches to Learning Standard 1:
  Sustains attention…` — while all four development states print the label at
  line start, and the pattern is anchored there.

**The probe, and why the numbers are not adopted.** `--probe-brittleness`
re-measures with both patterns widened:

| | AZ | CA | CO | TX | NV | KY |
|---|---|---|---|---|---|---|
| as recorded | 0.800 | 0.640 | 0.571 | 0.625 | **0.065** | **0.295** |
| + multi-letter segments | 0.800 | 0.640 | 0.571 | 0.625 | **0.522** | 0.295 |
| + mid-line labels | 0.800 | 0.640 | 0.571 | 0.625 | 0.522 | **0.409** |

Neither widening is adopted: both were motivated by inspecting the held-out
states *after* the recorded run, and adopting them would make NV and KY
development data and void the generalization claim they support. The four
development states are unmoved by either, which is the expected signature.

**Report the probe alongside the collapse.** Without it, "NV 0.065" overstates
the case — a reviewer will correctly suspect an under-specified regex rather
than a hard document. With it, the claim is stronger and survives the
objection: rules encode the token shapes their author has seen, one unseen
shape costs 21 of 46 elements, and even repaired post hoc the rule-based arm
reaches roughly half the LLM's recall on both held-out states.

---

## Secondary results

**Code accuracy** (over matched pairs only — denominators differ between arms
and must never be compared as rates): LLM 4/4, 25/25, 7/7, 8/8, 44/46, 44/44;
rule-based 3/3, 16/16, 4/4, 4/5, 1/3, 13/13. The rule-based arm is accurate on
the codes it recovers, on a much smaller matched set.

**Description accuracy**, rule-based: AZ 1/3, CA 3/5, CO 2/4, TX 0/1, NV 0/3,
KY n/a. The failures are `missing` and `truncated`, both consequences of
paragraph grouping rather than of transcription.

**Regression cases**, rule-based 12/17 PASS. Notable passes: `CO-NUMERIC-STRANDS`,
`KY-BENCHMARK-IS-SUB-STRAND` (all 10 KY Benchmarks correctly at sub_strand — a
label rule gets this right), `TX-PK3-PK4-DISTINCT`, `AZ-FOUR-LEVEL-HIERARCHY`.
Failures: `CA-AGE-COLUMNS-EMITTED`, `TX-AGE-BAND-SET`,
`NV-SUB-STRAND-CODE-FROM-DOCUMENT`, `NV-FOUR-LEVEL-HIERARCHY`,
`KY-FOUR-LEVEL-HIERARCHY` (NV and KY emit no indicator level at all).

**Depth map** reads `ABLATED` in all six states, not `FAIL` — the baseline has
no Pass-1 stage, so there is nothing to grade. `compare_baseline.validate`
rejects any baseline row whose `depth_map_passed` is non-null, since that would
mean the wrong detector was graded.

**Determinism.** The baseline is pure Python and deterministic
(`test_it_is_deterministic`), so one run per state is sufficient. This is a
genuine advantage over the LLM arm and should be said — it is the one axis on
which the rule-based approach wins outright.

---

## Instrument changes made during this task

1. **`evaluation/eval_detector.py`** — two additive parameters on
   `evaluate_state` (`detect_fn`, `grade_depth_map_pass`/`depth_map_skip_detail`),
   and the `--report-json` row construction extracted verbatim into
   `report_to_dict`. Both defaults are unchanged.

   **Verified score-neutral before use.** Every state's frozen detected JSON was
   replayed through the refactored `evaluate_state` and all **26 graded fields
   compared identical in all six states**. (A first check against the *cached*
   detections showed two diffs — AZ `n_detected` and NV's description fields —
   which traced to the cache holding different detector samples than the
   recorded run: AZ 76 vs 66 elements, and NV's Science description at 3500 vs
   2410 chars, the documented `_splice_overlapping_prose` divergence. Not the
   refactor.)

   `eval_common.code_version_hash` covers only `detector.py`/`parser.py`, so
   this changes no recorded evaluation number.

2. **Deleted three dead files** — `evaluation/baseline_detector.py` (June 2026;
   unimportable since it was added, `from .models` resolves to nothing),
   `evaluation/run_comparison.py` (imports `els_pipeline.baseline_detector`, a
   path that never existed), `evaluation/compare_approaches.py` (graded via
   `evaluation/evaluate.py`, a *different, older* grader — exactly the parallel
   grader Task 4 forbids). Nothing referenced any of them.

   **Left in place, flagged:** `evaluation/evaluate.py` is now orphaned and is
   still a second grading path. Deleting it was outside this task's approved
   scope.

3. **`paper/analysis/generate_tables.py`** — added `BASELINE_TAG` and
   `build_baseline_table`, producing `paper/tables/baseline_comparison.tex`. The
   other three tables regenerate byte-identical.

4. **`paper/sections/experiments_results.tex`** — added the
   `sec:experiments-baseline` subsection with the `\input` and a
   `TODO(Task 12)` prose brief.

---

## Caveats to carry into the paper

- **CORPUS TIER** on every table: `_only_subset`, 8–15pp, never full documents.
- **NEVER quote raw precision as quality** for either arm outside KY.
- **NEVER put the baseline's verified precision in a table.** ~1.000 by
  construction; see above.
- **Never compare code-accuracy rates across arms** — the denominators are
  matched pairs and the baseline matches far fewer.
- **The brittleness probe must travel with the held-out numbers.** Quoting NV
  0.065 without it overstates the result.
- **One run per state is enough here and only here.** The baseline is
  deterministic; the LLM arm's stability is Task 5.
- **This is not an "external" baseline.** It is a baseline we wrote. It is
  document-agnostic and held-out-disciplined, but it is not a published system,
  and the paper should not describe it as one.
- **AZ recall 0.800 rests on 5 golden elements.** Four of the six states have
  goldens under 10 elements, so per-state rule-based recall is coarse. The
  pooled per-level row (135 golden elements) is the robust figure.
