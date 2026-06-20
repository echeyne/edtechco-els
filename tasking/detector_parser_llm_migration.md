# Detector/Parser LLM-First Migration Plan

> **Working document.** A prioritized, self-contained task list for moving `src/els_pipeline/detector.py` and `src/els_pipeline/parser.py` from rule-driven to LLM-driven. Intended to be worked through one task at a time with Claude Code over multiple sessions. Each task is written to be actionable from a cold start.

## Why this exists

`detector.py` and `parser.py` have accumulated hand-coded, per-state normalization logic. Each rule was added to make one golden state (CA, AZ, CO, TX) pass the evaluation suite. They score well on the goldens but **do not generalize** — running a new state through the pipeline produces poor results because the new document's quirks aren't covered by the hardcoded rules.

**Goal:** these two files should be LLM-driven. Detection/parsing decisions — how to classify a level, build a code, handle age-band columns, strip a structural label — belong in the **prompt**, expressed as general document-structure principles, not in Python regexes and special-case branches. Python should stay thin: JSON extraction, schema validation, ID derivation from clean fields, and true cross-chunk reconciliation (an artifact of our chunking architecture, not of any document).

See the "Design direction" section of [CLAUDE.md](../CLAUDE.md) for the standing guidance this plan executes against.

## The non-negotiable guardrail (applies to EVERY task)

Work in this exact order on each task — never delete Python before the prompt is proven:

1. **Strengthen the prompt** so the LLM handles the case as a *general* principle (not keyed to specific label words or state quirks).
2. **Confirm the model now produces the clean output on its own** — inspect detector/parser output on the affected golden state(s).
3. **Only then delete the Python.**
4. **Gate:** re-run the evals — goldens must not regress vs. the Task 1 baseline.

**Run the `evaluation-runner` skill after EVERY change** — not just at the end of a task. After any edit to a prompt or a deletion of Python, run the skill before moving on, so a regression is caught against the exact change that caused it rather than discovered later in a batch. It runs both the detector and parser evals and auto-runs additional states to verify the change generalizes. If the skill reports any golden score below the Task 1 baseline, stop and fix it before continuing — do not stack further changes on top of a regression.

Never loosen the eval matchers or edit golden DATA to paper over a gap. Fix the golden data and canonicalize the model output instead (see the `feedback_golden_consistency` memory).

## How to run evaluations

Use the **`evaluation-runner`** skill (it runs both detector and parser evals, parses metrics, and auto-runs additional states to check generalization). Manual commands:

```bash
source venv/bin/activate
python -m evaluation.eval_detector --state CA
python -m evaluation.eval_detector --state CA --stability-runs 3   # LLM-determinism check
python -m evaluation.eval_parser --detection-dir outputs/06-20-26
```

- Detector grades against `evaluation/ground_truth_detector/{STATE}.json` (flat element list, run on `{STATE}-extraction.json`).
- Parser grades against `evaluation/ground_truth_parser/{STATE}.json` (nested `NormalizedStandard`, run on `{STATE}-detection.json`).
- The two golden sets are **decoupled** — a change to one suite does not imply a change to the other.
- `regression_cases` in each golden map by `id` to a check fn in `evaluation/regression_checks.py`.

## Key background (read before touching code)

- **Prompts live in the source files.** Detector: `build_depth_map_prompt` (Pass 1) and `build_detection_prompt` (Pass 2, the per-chunk extraction — this is where most detector rules belong). Parser: `build_parsing_prompt`.
- **Detection is two passes:** Pass 1 infers a `depth_map` (document nesting skeleton); Pass 2 extracts elements per chunk using that map. Classify by depth POSITION, not by label words.
- **Parsing is chunked by domain** (`chunk_elements_by_domain` → per-domain LLM call → merge). Cross-chunk code drift is reconciled by `normalize_parsed_codes` / `normalize_element_codes` — these are **legitimate** (chunking artifacts) and are NOT part of this migration.
- **Batched vs direct path diverge.** The eval runs the direct path; prod runs the batched path (`detection_batching.py`, `parse_batching.py`). Verify both when changing parse-path code (see `project_els_batched_vs_direct` memory).
- **What is explicitly OUT of scope (keep as-is):** `generate_standard_id`, `normalize_parsed_codes`, `normalize_element_codes`, `chunk_elements_by_domain`, `_split_oversized_chunk`, `chunk_text_blocks`, `_dedup_elements`, JSON-extraction/validation plumbing, and the generic age-band canonicalizers (`canonicalize_age_band`, `_normalize_age_band`, the terminal-period strip, `_TRAILING_MARKER_RE`).

---

## Tasks (work in order — lowest number first)

Priority = lowest risk + highest generalization value first. Tasks 2–4 are *redundant* rules (the prompt already states them; the Python is a keyword-limited duplicate that no-ops on non-golden states), so deleting them can only help. Tasks 5–7 are real behavior the Python owns exclusively. Task 6 flips a prompt contract and is the riskiest.

### COMPLETED - Task 1 — Establish the before-baseline (PREREQUISITE)

**Risk:** none. **Do this first; everything else gates against it.**

- Run `eval_detector` + `eval_parser` on all goldens (CA, AZ, CO, TX); record per-state scores.
- For each Bucket A rule below, identify the **specific golden failure it currently masks** (e.g. which AZ titles `_strip_label_prefix` fixes, which TX codes `_COLUMN_PREFIX_RE` fixes). That tells you exactly which prompt principle must be strengthened before each deletion.

**Deliverable:** a baseline scores table, saved alongside this doc or in the task notes, used as the regression gate for Tasks 2–8.

---

### Task 2 — Migrate structural-label handling (`Strand N:` / `Concept N:`)

**Risk:** low (redundant rule). **Files:** `detector.py`, `parser.py`.

Detector prompt rule 4 already states the `<Label> <id>: <Title>` → label-is-code / title-after-colon principle, but it's re-implemented in Python keyed to a hardcoded keyword list (`strand|concept|sub-strand|section|standard|domain|goal|benchmark`), so it no-ops on any other state's label word.

1. Generalize **detector** `build_detection_prompt` rule 4 to cover ANY structural-label heading, not the fixed list.
2. **Split** `_strip_label_prefix` (`detector.py`): remove the `_LABEL_PREFIX_RE` label-stripping half; **KEEP** the `_TRAILING_MARKER_RE` footnote-strip half (that's a generic canonicalizer, out of scope). Delete `_LABEL_PREFIX_RE`.
3. Remove `_LABEL_CODE_RE` from `parser.normalize_code_to_canonical`.

Confirm the detector emits clean code/title on AZ (the main label-heavy state) before deleting. **Gate.**

---

### Task 3 — Move code-abbreviation generation into the detector prompt

**Risk:** low (redundant rule). **Files:** `detector.py`, `parser.py`.

Detector prompt rule 4 already asks the model to generate a ≤5-char uppercase code abbreviation from the title, but `parser._abbreviate_title` (+ `_CODE_ABBREV_LEN`) re-derives codes in Python (`CAP`, `VOCA`, `SED`).

1. Strengthen detector prompt rule 4 with the multi-word-acronym vs. single-word-truncation guidance currently encoded in `_abbreviate_title`.
2. Confirm the detector emits stable codes across runs (use `--stability-runs`).
3. Remove `_abbreviate_title` and `_CODE_ABBREV_LEN`. This shrinks `normalize_code_to_canonical` (only the passthrough branch remains) and feeds Task 7's cleanup. **Gate.**

---

### Task 4 — Migrate domain trailing-noun stripping

**Risk:** low. **File:** `detector.py`.

`_TRAILING_DOMAIN_LABEL_RE` strips a trailing "Standard"/"Domain" noun from domain titles (AZ/TX) so duplicates collapse and match the golden's label-free name.

1. Add to the detection prompt: "a domain title's trailing structural noun (e.g. Standard, Domain) is not part of its name — emit the bare name."
2. Confirm domains come out clean on AZ/TX.
3. Delete `_TRAILING_DOMAIN_LABEL_RE` and its call in `_create_detected_element`. **Gate.**

---

### Task 5 — Migrate age/column code-prefix stripping (drop the `PK` regex)

**Risk:** medium (Python owns this exclusively, TX). **File:** `parser.py`.

`_COLUMN_PREFIX_RE` (`^PK\d+\.`) + `_strip_column_prefix` strip the `PK3.`/`PK4.` age prefix so side-by-side variants share a base code; the same literal-`PK` strip is duplicated inside `_infer_domain_code`. The literal `PK` only matches Texas.

1. Prompt change (parser `build_parsing_prompt`): "if an indicator's code carries a leading age/column token (e.g. `PK3.`, a grade band), the base hierarchical code EXCLUDES that token" — stated generally, not as `PK`.
2. Confirm TX base codes are correct from the LLM.
3. Remove `_COLUMN_PREFIX_RE`, `_strip_column_prefix`, and the PK-strip line inside `_infer_domain_code` (keep `_infer_domain_code`'s routing logic — it's needed for chunking).

**Coupling:** the suffix re-application in `parse_llm_response` changes together with Task 6 — read both before starting. **Gate.**

---

### Task 6 — Migrate side-by-side column disambiguation to the LLM (flip the prompt contract)

**Risk:** HIGH — flips an existing prompt contract. Do after the safer migrations. **File:** `parser.py`.

Today the parsing prompt FORBIDS the LLM from disambiguating ("Do NOT append the age band or column label to any code") and Python owns it via `_disambiguator_suffix` + `_derive_label_abbrev` (`Discovering`→`DISC`) + `canonicalize_age_band`, re-applied as a suffix in `parse_llm_response`.

1. **Flip the prompt** so the LLM emits DISTINCT codes per side-by-side column directly: age-range columns use the month range; proficiency columns use a short label-derived token — as one general principle covering both CA-ELD proficiency columns and TX/age columns.
2. Keep only a thin uniqueness/collision guard in Python.
3. Remove `_disambiguator_suffix`, `_derive_label_abbrev`, `_COLUMN_ABBREV_LEN`, and the suffix re-application block in `parse_llm_response`.
4. Verify CA Early/Later AND Discovering/Developing/Broadening all stay distinct in the output. **Gate.**

---

### Task 7 — Remove the CA collision branch and collapse emptied helpers

**Risk:** medium (dependent cleanup). Do after Tasks 2, 3, 6. **File:** `parser.py`.

`abbreviate_element_codes` contains a hardcoded CA pattern (sub_strand numeric code colliding with a child indicator → swap to title abbrev) using `_PURE_NUMERIC_RE`.

1. Generalize the collision-avoidance into the prompt: "a sub_strand and its child indicator must not share an identical code."
2. Remove the special-case branch.
3. By now `normalize_code_to_canonical` and `abbreviate_element_codes` may be near-empty shells (their `_LABEL_CODE_RE` and `_abbreviate_title` bodies were removed in Tasks 2–3) — collapse/delete them and update **both** the direct and batched parse paths that call them. **Gate.**

---

### Task 8 — Validate generalization

**Risk:** none (final gate).

1. Re-run the full eval suite on all goldens — must match or beat the Task 1 baseline (no regression).
2. Confirm the batched path matches the direct path.
3. Run the Python unit/property tests (`pytest tests/ -v`).
4. Update the CLAUDE.md Design-direction section if any helper survived as a justified exception, and note which prompt principles now carry the load.

---

## Quick reference: symbols to remove vs. keep

**Remove (migrate into prompt):**
- `detector._LABEL_PREFIX_RE`, label-strip half of `_strip_label_prefix`
- `detector._TRAILING_DOMAIN_LABEL_RE` + its call
- `parser._LABEL_CODE_RE`
- `parser._abbreviate_title`, `_CODE_ABBREV_LEN`
- `parser._COLUMN_PREFIX_RE`, `_strip_column_prefix`, PK-strip inside `_infer_domain_code`
- `parser._disambiguator_suffix`, `_derive_label_abbrev`, `_COLUMN_ABBREV_LEN`
- CA collision branch + `_PURE_NUMERIC_RE` in `abbreviate_element_codes`; likely collapse `normalize_code_to_canonical` + `abbreviate_element_codes`

**Keep (out of scope — document-agnostic):**
- `generate_standard_id`, `normalize_parsed_codes`, `normalize_element_codes`
- `chunk_elements_by_domain`, `_split_oversized_chunk`, `chunk_text_blocks`, `_dedup_elements`
- `_infer_domain_code` routing (minus the PK strip)
- `canonicalize_age_band`, `_normalize_age_band`, `_TRAILING_MARKER_RE`, indicator terminal-period strip
- All JSON-extraction / schema-validation plumbing
