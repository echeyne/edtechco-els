# Held-out annotation guide — NV & KY (arXiv paper Task 2)

Working checklist for filling in the four skeleton goldens created for the
held-out generalization states. Conventions come from
[README.md](README.md); this file only covers what's specific to NV/KY.

| File | Grades | Runs against |
| --- | --- | --- |
| `ground_truth_detector/NV.json` | detector | `NV-extraction.json` |
| `ground_truth_detector/KY.json` | detector | `KY-extraction.json` |
| `ground_truth_parser/NV.json` | parser | `NV-detection.json` |
| `ground_truth_parser/KY.json` | parser | `KY-detection.json` |

Sources (both already in `standards/`):

- NV → `nevada_standards_2023_only_subset.pdf` (15pp, multi-domain,
  version_year 2023). **Not** `nevada_ses_standards_2025*` — single-domain
  Social-Emotional only, too narrow for a generalization claim.
- KY → `kentucky_all_standards_2021_only_subset.pdf` (9pp, version_year 2021).

## Inputs

Neither suite runs the pipeline end-to-end, so both subset PDFs have to go
through ingestion → extraction → detection first and the results have to be
pulled down. `download-pipeline-outputs` now fetches NV and KY alongside the
four golden states, discovering their year from S3 and skipping a state that
run didn't produce.

**Current inputs: `outputs/08-13-26/`** — the first run carrying all six states
(and the first NV/KY run produced by a pipeline that includes the deterministic
`detector.derive_code_from_title` pass).

Order matters: the **parser** golden is annotated against a specific frozen
`{STATE}-detection.json` — record which one in `source_detection`, and
re-verify if that detection is ever re-recorded.

## Fill-in order

1. **Read the subset PDF end to end first.** Decide the document's depth
   structure before writing any row: is it 4-level (domain → strand →
   sub_strand → indicator, like AZ/CA/TX) or 3-level (no sub_strand, like CO)?
2. **`expected_depth_map`** in the detector golden — one entry per depth that
   actually exists. Delete the `sub_strand` entry if the document is 3-level.
   This is graded standalone, so Pass-1 correctness is visible independently of
   per-chunk extraction.
3. **`elements`** (detector) — delete the `TEMPLATE-` rows and annotate 1–2
   representative domains fully plus a handful of edge cases (~50 elements).
   Spot-check coverage is correct and intended: **do not attempt exhaustive
   annotation.** Precision for NV/KY comes from extending the Task 1b manual
   FP audit to their in-scope extras, which keeps the generalization table's
   methodology identical to the golden states'.
4. **`standards`** (parser) — delete the `TEMPLATE-` entries and annotate
   representative indicators plus whatever the regression cases target. Each
   entry is matched by `(indicator.name, age_band)` then graded field-by-field
   for exact equality. `source_text` is neither expected nor compared.
5. **`regression_cases`** — every case `id` needs a matching function in
   `evaluation/regression_checks.py` (`check_<id>` for the detector via
   `lookup`, `check_parser_<id>` for the parser via `lookup_parser`) or the
   suite logs `SKIP`. `NO-ID-COLLISION` is pre-filled in both parser goldens
   and already has its function.

**Precision caveat for the paper.** A spot-check golden cannot produce a
precision number. KY's detector golden happens to be exhaustive, so its
precision is real; NV's is not, and neither parser golden is. Report NV/KY
precision from the Task 1b manual FP audit, or state the coverage denominator
explicitly.

## Conventions worth restating

- `test_case_id` = `<STATE>-<KIND>-<N>`, suffixed with the band for
  age-banded indicators (`NV-IND-01-36-48`). That's what makes a dropped
  column report as `NV-IND-01-36-48 MISSING` rather than a silent miss.
- **Copy titles and descriptions verbatim.** The matcher is fuzzy but degrades
  fast on paraphrase.
- Detector `code` is the **document-local** code (`'1.0'`, `'AL'`); parser
  `code` is the **fully qualified dotted** code (`'AL.1.1'`) and carries any
  age/column disambiguator itself — there is no separate `domain_code`
  component in `standard_id` (`US-<state>-<year>-<indicator_code>`).
- A sub_strand and its child indicator must never share a code.
- **A parent's code need not be a prefix of its child's.** When the document's
  printed namespace skips a level (NV codes indicators
  `<domain>.<sub_strand>.PKn` and never puts the strand in the code), that
  level keeps the identifier its own heading supplied — annotate NV's strand as
  `SS.2`, not as a slice of `SS.CI.PK3`. Annotate what the page prints; do not
  back-form a parent code out of its child's.
- `age_band` on detector elements uses the document's exact column phrasing;
  the parser golden uses the canonicalized band (e.g. `36-48`).

## Running

```bash
source venv/bin/activate
python -m evaluation.eval_detector --state NV --extraction-dir outputs/<FOLDER>
python -m evaluation.eval_parser --state NV --detection-dir outputs/<FOLDER>
```

Add `--no-cache` for any number that gets recorded in `paper/results/`.

**Guardrail 7 (`tasking/arxiv_paper.md`): report the result honestly.** If NV
or KY scores collapse, that is the finding — it becomes a stated limitation,
not a quiet omission. Never edit these goldens or loosen a matcher to raise a
score; fix the golden data and canonicalize the output instead.
