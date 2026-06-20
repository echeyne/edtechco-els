# Task 1 Baseline — Detector + Parser scores (pre-migration)

> Captured 2026-06-20 against `outputs/06-20-26/` (extraction + detection fixtures for all four golden states). This is the **regression gate** for Tasks 2–8: a change passes only if every per-state F1 and every per-field accuracy meets or beats the number here.

Reproduce:

```bash
source venv/bin/activate
# Detector (uses {STATE}-extraction.json)
python -m evaluation.eval_detector --extraction-dir outputs/06-20-26 \
  --report-json tasking/baseline-task1/detector_baseline.json
# Parser (uses {STATE}-detection.json fixture)
python -m evaluation.eval_parser --detection-dir outputs/06-20-26 \
  --report-json tasking/baseline-task1/parser_baseline.json
```

## Detector — per-state scores

State | Golden | Detected | Matched | Precision | Recall | F1 | Depth-map | Regression cases
----- | ------ | -------- | ------- | --------- | ------ | -- | --------- | ---------------
AZ    | 5  | 67  | 5  | 0.417 | 1.000 | **0.588** | PASS | AZ-NO-EXAMPLES-HEADER-AS-ELEMENT PASS; AZ-FOUR-LEVEL-HIERARCHY PASS
CA    | 20 | 122 | 20 | 0.164 | 1.000 | **0.282** | PASS | all 4 PASS (AGE-COLUMNS-EMITTED, AGE-LABEL-NOT-IN-TITLE, NO-LETTERED-EXAMPLES, FOUR-LEVEL-HIERARCHY)
CO    | 7  | 63  | 7  | 0.159 | 1.000 | **0.275** | PASS | NO-SUB-STRAND PASS; NUMERIC-STRANDS PASS
TX    | 8  | 36  | 7  | 1.000 | 0.875 | **0.933** | PASS | PK3-PK4-DISTINCT PASS; AGE-BAND-SET PASS; NO-COLUMN-HEADER-AS-INDICATOR PASS

Per-level highlights:

- **AZ:** dom 1.00/1.00, strand 0.50/1.00, sub 0.33/1.00, ind 0.33/1.00. Recall is perfect because the LLM emits every golden element; precision suffers because the eval ignores everything outside the SED/LL domains and the detected set is much bigger.
- **CA:** dom 1.00/1.00 — the rest are recall=1.00 with low precision (lots of in-scope FPs at strand/sub_strand/indicator).
- **CO:** depth_map only has 3 levels (no sub_strand). All 7 golden elements matched; 37 in-scope FPs (mostly indicators tagged `2.`/`3.`/`4.` ordinals).
- **TX:** the only missing test case is **`TX-DOM-01`** — see "rule-vs-golden conflict" below.

## Parser — per-state scores

State | Golden | Parsed | Matched (coverage) | Fully correct | Field accuracy | Notable per-field misses | Regression cases
----- | ------ | ------ | ------------------ | ------------- | -------------- | ----------------------- | ----------------
AZ | 18 | 45 | 18 (1.000) | 0/18 | **0.923** | domain.description 13/18, sub_strand.description 5/18, indicator.description 12/18 — all whitespace-normalization noise ("firm foundation"/"firmfoundation") | NO-ID-COLLISION PASS
CA | 10 | 94 | 10 (1.000) | 8/10 | **0.978** | strand.code & sub_strand.code 8/10 — only CA-IND-02-EARLY/LATER (`FLD.1.0` expected, got `ELD.1.0`; LLM mis-attributed FLD indicators to the ELD domain) | CA-EARLY-LATER-DISTINCT-IDS PASS; NO-ID-COLLISION PASS
CO | 9  | 66 | 3  (0.333) | 1/3  | **0.944** | 6 dropped: CO-IND-03..08. CO-IND-09 strand split between name and description | **CO-INDICATOR-PARENT-IS-STRAND FAIL** (16/66 indicators parented at strand instead of sub_strand); NO-ID-COLLISION PASS
TX | 8  | 25 | 8  (1.000) | 2/8  | **0.938** | indicator.description 4/8 (LLM bleeds the next indicator's "Child Behaviors" block into the description); strand.code 6/8 (`IV.A` vs `VI.A`); source_page 7/8 | TX-PK3-PK4-DISTINCT-IDS PASS; NO-ID-COLLISION PASS

The parser run uses the frozen `{STATE}-detection.json` fixture (66 elements for AZ with `Strand 1` / `Concept 1` codes preserved), while the detector run goes from the extraction. The two suites are decoupled — both numbers stand.

## Bucket A → specific golden failures the Python currently masks

The rule-removal plan calls Tasks 2–4 "redundant rules" because the prompt already states the principle. Here is the exact set of golden cases each rule keeps green today — these are the cases that MUST stay green when the Python is deleted in the corresponding task.

### Task 2 — `_LABEL_PREFIX_RE` + `_strip_label_prefix` (detector) and `_LABEL_CODE_RE` (parser)

Owned by **AZ**.

What the LLM emits raw (verified in `evaluation/.cache/detection-AZ-4f895fca5cb727a5-.json`, 67 elements):

```
level=strand     code='Strand 1'    title='Self-Awareness and Emotional Skills'
level=sub_strand code='Concept 1'   title='Self-Awareness'
level=indicator  code='a'           title='Demonstrates self-confidence'
```

Without `_LABEL_PREFIX_RE` (detector) the strand/sub_strand titles would be `'Strand 1: Self-Awareness and Emotional Skills'` and `'Concept 1: Self-Awareness'`, and the detector eval matches on `(_domain, level, normalized_title, age_band)` — so:

- **`AZ-STR-SE-1`** (detector golden: `strand` / `Self-Awareness and Emotional Skills`) — would fall to fn.
- **`AZ-SUB-SE-1-1`** (detector golden: `sub_strand` / `Self-Awareness`) — would fall to fn.
- Same pattern applies to every other AZ strand/sub_strand the LLM emits (Strand 2/3, Concept 2/3 …), which is why AZ depth_map and `AZ-FOUR-LEVEL-HIERARCHY` regression case pass today.

Without `_LABEL_CODE_RE` (parser) the cumulative codes break across **all 18 AZ parser-golden standards**. E.g. `AZ-IND-01` expects:

```
standard_id  US-AZ-2018-SED.1.1.a
strand.code  SED.1
sub.code     SED.1.1
indicator    SED.1.1.a
```

Without the rule, `Strand 1` and `Concept 1` would not get reduced to `1` and `1` — the cumulative chain becomes `SED.Strand 1.Concept 1.a`. So Task 2 deletion must keep these 18 standard_ids and their `.code` fields exact.

### Task 3 — `_abbreviate_title` + `_CODE_ABBREV_LEN` (parser)

Owned by **CA**. The LLM emits **title-as-code** for sub_strands across FLD and ELD (verified in `outputs/06-20-26/CA-detection.json`):

```
level=sub_strand code='Vocabulary'              title='Vocabulary'         → abbreviates to VOCA
level=sub_strand code='Grammar'                 title='Grammar'            → GRAM
level=sub_strand code='Language Use'            title='Language Use'       → LU
level=sub_strand code='Phonological Awareness'  title='Phonological Awareness' → PA
level=sub_strand code='Alphabetics and Print'   title='Alphabetics and Print'  → AAP
level=sub_strand code='Concepts About Print'    title='Concepts About Print'   → CAP
```

The four CA parser-golden cases that resolve only because `_abbreviate_title` runs:

- **`CA-IND-02-EARLY`** / **`CA-IND-02-LATER`** — `sub_strand.code` expected `FLD.1.0.VOCA` (single-word truncation `Vocabulary` → `VOCA`).
- **`CA-IND-03-DISCOVERING|DEVELOPING|BROADENING`** — `sub_strand.code` expected `ELD.1.0.VOCA`.
- **`CA-IND-04-DISCOVERING|DEVELOPING|BROADENING`** — `sub_strand.code` expected `ELD.2.0.CAP` (multi-word acronym `Concepts About Print` → `CAP`).

The CA collision branch in `abbreviate_element_codes` (`INIT`, `PERS`, `WM`, `IC`, `FLEX`, `PS`, `CE`, `ENGA`, `CAI`) is **not** part of Task 3 — that's Task 7 — but it CALLS `_abbreviate_title`. So Task 3's prompt migration must produce stable single-word truncations + multi-word acronyms BEFORE Task 7 can delete the collision branch.

### Task 4 — `_TRAILING_DOMAIN_LABEL_RE` (detector)

**Rule-vs-golden conflict to flag.** This rule fires on domain titles ending in `Standard` / `Standards` / `Domain` / `Domains`. Verified emit (from `outputs/06-20-26/{AZ,TX}-detection.json` — post-strip):

- AZ: LLM emits `Language and Literacy Standard` (and an ALL-CAPS duplicate `LANGUAGE AND LITERACY`); rule strips to `Language and Literacy`, both variants collapse to one code `LL`.
- TX: LLM emits `Social and Emotional Development Domain`; rule strips to `Social and Emotional Development`.

What today's goldens actually require:

- AZ detector golden has only `AZ-DOM-SED` (title `Social Emotional Development`, no trailing noun) — the rule **is a no-op for the matched golden case**. Its value is internal dedup of the LL duplicate, not a golden test.
- AZ parser golden domain titles (all 18 standards) are also bare nouns ("Social Emotional Development", "Language and Literacy") — the rule keeps them clean.
- TX detector golden **`TX-DOM-01` title is `'Social and Emotional Development Domain'`** — the rule's strip turns the LLM emit into `'Social and Emotional Development'`, which fails the (level, title) match. **This is why TX detector has fn=1 / recall=0.875 today.**
- TX parser golden uses domain.name = `'Social and Emotional Development'` (bare) for all PK3/PK4 standards — the rule's strip is required there.

So Task 4 is the ONLY Bucket A rule where today's goldens are internally inconsistent: the detector golden expects "Domain" kept, the parser golden expects "Domain" stripped, and the rule chose the parser's side. When Task 4 moves the strip to the prompt and deletes the Python, **`TX-DOM-01`'s detector-golden title must be updated to the bare form `'Social and Emotional Development'`** (per the project's `feedback_golden_consistency` rule — canonicalize output, fix golden DATA, never loosen matchers). That's the only golden edit Task 4 should require; recording it here so it's not mistaken for paper-over later.

## Things NOT caused by Bucket A (don't conflate with Tasks 2–4 work)

- CO parser regression failure `CO-INDICATOR-PARENT-IS-STRAND` (16/66 indicators parented at the wrong level) — parser hierarchy resolution, separate workstream.
- CA parser sub-strand `FLD.1.0` vs `ELD.1.0` mis-attribution (CA-IND-02-EARLY/LATER) — LLM domain attribution error, not a Python rule.
- AZ parser `.description` whitespace mismatches ("firmfoundation" / "researchindicates" / "self-controlover") — extraction-layer whitespace normalization, upstream of detector and parser.
- TX parser `indicator.description` bleed into the next indicator's "Child Behaviors" block — parser segmentation, separate.
- TX parser `strand.code` `IV.A` vs `VI.A` — Roman-numeral parsing artifact, separate.

## Headline numbers to beat (regression gate for every subsequent task)

| | Detector F1 | Parser field accuracy | Parser coverage |
|---|---|---|---|
| AZ | 0.588 | 0.923 | 1.000 |
| CA | 0.282 | 0.978 | 1.000 |
| CO | 0.275 | 0.944 | 0.333 |
| TX | 0.933 | 0.938 | 1.000 |

Plus every regression case currently PASSing must stay PASSing, and `CO-INDICATOR-PARENT-IS-STRAND` (already FAIL) must not get worse (still ≤16/66).
