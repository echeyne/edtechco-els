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

**Current inputs: `outputs/08-22-26/`** — what the exhaustive 2026-08-22 NV
pass was annotated and checked against, and what `ground_truth_parser/NV.json`
now names in `source_detection`. (`outputs/08-13-26/` was the first run
carrying all six states, and the first NV/KY run produced by a pipeline that
includes the deterministic `detector.derive_code_from_title` pass; it is what
the frozen `paper/results/task2_20260816/` numbers were measured on.)

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
3. **`elements`** (detector) — delete the `TEMPLATE-` rows. The original
   instruction here was to spot-check 1–2 representative domains (~50
   elements) and take precision from the Task 1b manual FP audit instead.
   **Both held-out goldens are now exhaustive** (KY always was by accident;
   NV was completed 2026-08-22), so for these two states annotate every
   structural element the subset prints. Note that on a 15-page subset that
   includes headings whose own content falls outside the subset — NV prints
   twelve `<Domain> Standard N:` headings on its three "The `<Domain>`
   Standards include:" list pages while only seven have indicator tables in
   range, and the detector emits all twelve, so all twelve are annotated.
   Order matters: `eval_detector._tag_domains` scopes each element to the
   most-recent domain **above it in list order**, so a childless heading goes
   at the end of its domain's block, not at its printed page position.
4. **`standards`** (parser) — delete the `TEMPLATE-` entries. As of
   2026-08-22 both held-out parser goldens cover every indicator in their
   subset (NV 24, KY 26); annotate all of them rather than a representative
   sample, and keep `test_case_id` numbering contiguous in document order.
   Each entry is matched by `(indicator.name, age_band)` then graded
   field-by-field for exact equality. `source_text` is neither expected nor
   compared.
5. **`regression_cases`** — every case `id` needs a matching function in
   `evaluation/regression_checks.py` (`check_<id>` for the detector via
   `lookup`, `check_parser_<id>` for the parser via `lookup_parser`) or the
   suite logs `SKIP`. `NO-ID-COLLISION` is pre-filled in both parser goldens
   and already has its function.

**Precision caveat for the paper.** A spot-check golden cannot produce a
precision number, which is why the four golden states report verified
precision from the Task 1b manual FP audit instead.

⚠️ **Corrected 2026-08-22 (measured against `outputs/08-22-26-4`).** An earlier
revision of this section said both held-out goldens are now exhaustive and that
their raw suite precision is therefore a real hallucination rate. That conflates
two different properties, and it holds for KY but **not** for NV:

- **Content-exhaustive** — the golden annotates every distinct structural
  element the subset prints. **NV is now this** (46 elements, all twelve
  `<Domain> Standard N:` headings included). This is what the 2026-08-22 pass
  achieved and it is a real improvement.
- **Detection-exhaustive** — every in-scope detection is accounted for by a
  golden entry, i.e. `n_golden == n_in_scope`. This is the property that
  licenses reporting raw precision, and **NV is not it**: the detector emits
  **53** in-scope elements against the golden's 46, because NV reprints 6
  headings on a second page spread (6 duplicate `(level, title)` pairs in the
  detection, 0 in the golden) and one detection is the known `SS.CI.PK3`
  hallucination.

So NV's ceiling is **46/53 = 0.8679**. Reporting that as a hallucination rate
would count 6 correct re-detections of genuinely reprinted headings as
hallucinations. **NV keeps the verified-precision path** — the audit is just
much smaller now, 7 verdicts instead of 12. KY remains detection-exhaustive
(44/44) and its raw precision 1.000 is a real hallucination rate.

A one-entry-per-element golden can never be detection-exhaustive for a document
that reprints headings, so this is a property of NV's layout, not a gap in the
annotation. Do not "fix" it by annotating the repeats twice.

⚠️ NV became content-exhaustive on **2026-08-22**, *after* the frozen Task 2
measurement. `paper/results/task2_20260816/` was recorded against the
41-element NV golden and its NV annotation-coverage ceiling (0.7736) and raw
precision are historical figures for that golden — leave them as the record of
what was measured, and re-record rather than retro-fit. When the new ceiling
(0.8679) is reported, label it as an **annotation-coverage change, not a
quality improvement**: the detector's behaviour on NV did not change, the
denominator's accounting did. Guardrail 8 in `tasking/arxiv_paper.md` still
names KY as the one state that qualifies for raw-precision reporting, and NV
does **not** join it — see the corrected caveat above for why.

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
