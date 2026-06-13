# Ground Truth Annotations (Golden Sets)

There are **two** golden sets, graded by two independent suites:

- **`ground_truth_detector/1** — detector goldens, one JSON per state.
  Graded by `evaluation/eval_detector.py`, which runs the detector against the
  matching `{STATE}-extraction.json` and compares the flat element list.
  Schema: `../golden_set.schema.json`.
- **`/ground_truth_parser/`** — parser goldens, one JSON per state. Graded by
  `evaluation/eval_parser.py`, which runs the parser against the matching
  `{STATE}-detection.json` and compares the full nested `NormalizedStandard`
  objects field-by-field. Schema: `../parser_golden.schema.json`.

The two are deliberately decoupled: the detector and parser produce different
shapes (flat elements vs. nested resolved standards), run against different
inputs (extraction vs. detection), and can be annotated/iterated separately.

Files in each directory:

| File      | Purpose                                                               |
| --------- | --------------------------------------------------------------------- |
| `AZ.json` | Arizona Early Learning Standards 4th Ed. — 4-level, lettered examples |
| `CA.json` | California Preschool Learning Foundations — 4-level, age-band columns |
| `CO.json` | Colorado ELDG Ages 3-5 — 3-level (no sub_strand), numeric strands     |
| `TX.json` | Texas 2022 PreK Guidelines — 4-level, side-by-side PK3/PK4 columns    |

The schema is in `../golden_set.schema.json`. Each file has three things to
fill in:

1. **`expected_depth_map`** — what `infer_depth_map` should return for this
   document. This is graded standalone so we know whether Pass-1 is correct
   independently of the per-chunk extraction.
2. **`elements`** — a list of structural elements with `test_case_id`s. You
   do NOT need to annotate the entire document. Aim for full coverage of
   1–2 representative domains plus a handful of edge cases. ~50 elements
   per state is enough to catch the regressions we care about.
3. **`regression_cases`** — bug-targeted behavioural assertions. Each
   `id` corresponds to a check function in `evaluation/regression_checks.py`.
   When you add a new regression case here, also add a check function with
   the same `id` (the suite logs `SKIP` if the function is missing).

## How to populate `elements`

For every element you annotate, fill in the fields marked `TODO` in the
template. The required minimum is `test_case_id`, `level`, `title`. Adding
`code`, `source_page`, and parent codes makes the eval much sharper.

Annotation tips:

- **Test case IDs** follow `<STATE>-<KIND>-<N>` (e.g. `CA-IND-01-EARLY`).
  For age-banded indicators, suffix with the band (`-EARLY`, `-LATER`,
  `-PK3`, `-PK4`). This lets the eval report `CA-IND-01-LATER MISSING`
  when the detector drops the Later column.
- **Use copy-verbatim text** for `title` and `description`. Don't paraphrase
  — the matcher does fuzzy comparison but works much better when the
  source is literal.
- **`age_band`** is null for non-age-banded elements. For CA, use the exact
  document phrasing: `"Early (3 to 4 ½ Years)"` / `"Later (4 to 5 ½ Years)"`.
  For TX, use `"PK3"` / `"PK4"`.

## Running the eval

```sh
# Detector eval — all states, single run
python -m evaluation.eval_detector

# One state
python -m evaluation.eval_detector --state CA

# Stability check: run the detector N times against the same chunk and
# report level-classification disagreement rate.
python -m evaluation.eval_detector --state CA --stability-runs 3

# Parser eval — grade parse_hierarchy output against ground_truth_parser/
python -m evaluation.eval_parser --detection-dir outputs/05-31-26
python -m evaluation.eval_parser --state CA --stability-runs 3
```

See the docstring at the top of `evaluation/eval_detector.py` and
`evaluation/eval_parser.py` for the full metric set and configuration knobs.
