# Task 8 — dataset descriptive statistics and the re-measured confidence distribution

**Recorded 2026-08-23.** Code version `288c64f1`, git `fa0b0ed`, run
`outputs/08-22-26-4`, corpus tier `_only_subset` (guardrail 1). **Zero Bedrock
tokens spent** — every input was already on disk, which is why this task was
available while the Opus daily quota was exhausted.

Regenerate everything here with:

```bash
python paper/analysis/dataset_stats.py && python paper/analysis/generate_tables.py
```

---

## Part 1 — descriptive statistics

Six states, 70pp of subset PDFs, **390 detected elements → 262 standards**.

| | AZ | CA | CO | TX | NV | KY | total |
|---|---|---|---|---|---|---|---|
| role | golden | golden | golden | golden | held-out | held-out | 4 + 2 |
| subset pp | 15 | 13 | 10 | 9 | 15 | 8 | 70 |
| full pp | 217 | 68 | 41† | 87 | 98 | 120 | — |
| standards | 45 | 94 | 48 | 25 | 24 | 26 | **262** |
| distinct domains | 2 | 3 | 3 | 2 | 3 | 3 | 16 |
| distinct strands | 4 | 7 | 10 | 4 | 7 | 5 | 37 |
| distinct sub-strands | 9 | 18 | 0 | 2 | 7 | 10 | 46 |
| `standard_id` collisions | 0 | 0 | 0 | 0 | 0 | 0 | **0** |
| age-band coverage | 1.00 | 1.00 | 1.00 | 1.00 | 1.00 | 1.00 | **1.00** |

† CO's subset derives from the 41pp ages-3–5 document, **not** the separate
187pp birth-to-8 one. Recording 187 here would overstate the trim by 4.5×.

### The three results worth stating in the paper

1. **Zero `standard_id` collisions, corpus-wide.** 262 standards, 262 distinct
   ids. This is the descriptive statistic that carries the most weight, because
   `standard_id` is `{country}-{state}-{year}-{indicator_code}` and therefore
   *is* the primary key a standard is stored under. It is also the number that
   the last six months of code-stability work — `derive_code_from_title`,
   `_anchor_parent_chain`, `disambiguate_colliding_standards`,
   `validator._validate_code_shape` — exists to protect.

2. **Age-band coverage is 1.000 in every state.** All 262 standards carry a
   canonical band; there are six distinct bands across the corpus (`36-48`,
   `36-54`, `36-60`, `36-66`, `48-60`, `48-66`) and 143 of 262 standards are
   `36-60`. This is schema completeness rather than a document property — most
   documents state their age range once, in prose, and the canonicalizers
   propagate it.

3. **A four-level schema is not a four-level document.** CO's subset prints no
   sub-strand tier at all and TX's prints two, while CA's prints eighteen. This
   is the variation the optional-level handling exists for, and it is worth one
   sentence in §Schema.

### Two counts that look wrong and are not

- **Parsed distinct ancestors < detected elements** (37 parsed strands against
  52 detected). Two benign causes: the detection contains cross-page reprints
  of the same heading, and a heading with no indicator beneath it inside the
  subset has no standard to appear in.
- **`blank_string` is 0 at every level in every state.** This is the check that
  `models._blank_to_none` (2026-08-15) is holding — absence has exactly one
  spelling in this schema, and if this count ever goes non-zero that validator
  has regressed.

Description coverage varies by document, not by pipeline behaviour: AZ, CA and
KY print a description on every indicator; CO, TX and NV print none.

---

## Part 2 — the confidence distribution

**The framing is negative, and it must stay negative.** This measurement does
not show that the detector knows when it is uncertain. It shows close to the
opposite, and it is the evidence that **not** gating on confidence (guardrail 2)
is the right design.

Measured over the 379 elements of the recorded direct-path run:

| | value |
|---|---|
| range | 0.85 – 0.97 |
| distinct values | **7** |
| mean | 0.957 |
| in the prompt's `≥0.95` band ("depth map clearly applies") | 347 / 379 |
| in the prompt's `0.80–0.94` band ("ambiguous but likely") | 32 / 379 |
| in the prompt's `<0.70` band ("guessing") | **0 / 379** |

The detector prompt (rule 5) asks for three bands. The model uses one of them
almost exclusively, uses the second for 8% of elements, and **never once uses
the third**. A score that never exercises the range it was given is not
carrying information about difficulty.

### The Medium article claim, re-measured (guardrail 4)

`documentation/medium-articles/02-teaching-ai-to-read-curriculum.md` line 100:

> "In practice, most documents produce 85–90% of their indicators at 0.95+
> confidence. The remaining 10–15% are typically from tables, footnotes, or
> sections with unusual formatting."

- **First sentence: REPRODUCES.** 236/263 indicators = **89.7%**, identical on
  both paths. The paper must still cite the measurement rather than the
  article — landing inside the published band is a property of this corpus,
  not a validation of a number that was never measured.
- **Second sentence: REFUTED.** The low tail is not a scattered set of hard
  passages. **Four of six states have no sub-0.95 indicator at all**, and the
  tail is essentially one state: *every one* of Kentucky's 26 indicators scores
  below 0.95 (at 0.92/0.93), plus the single NV outlier. The score moves at the
  level of a whole document, not a hard passage inside one.

The same article (line 98) also describes a 0.70 review threshold as "a quality
gate". That claim is **doubly dead**: no such gate exists in the live code, and
this corpus shows it would have been inert if it did — zero elements score
below 0.70, in the recorded run or in any repeat.

### Confidence versus the human audit

Every one of the 379 elements is accounted for: 298 are in scope for a golden,
and each of those either matched a golden entry or carries a signed
false-positive verdict.

| verdict | n | range | ≥0.95 |
|---|---|---|---|
| matched a golden | 135 | 0.92–0.97 | 106/135 |
| real, unannotated | 111 | 0.90–0.97 | 109/111 |
| real, split title | 39 | 0.95–0.97 | 39/39 |
| real, reprinted heading | 12 | 0.95–0.97 | 12/12 |
| **invented** | **1** | **0.85** | **0/1** |

Corpus-wide verified precision: **297/298 = 0.9966**.

**Kentucky is the cleanest single illustration and belongs in the prose.** KY is
the one state with a detection-exhaustive golden; it scores recall 1.000, code
accuracy 1.000 and verified precision 1.000 — the best-evidenced detection in
the corpus — while carrying the **lowest** confidence of any state. California
earns the same recall and code accuracy with all 94 indicators at 0.95+.

### ⚠️ The one hallucination, and why it must not be promoted to a threshold

The single confirmed invented element (NV `SS.CI.PK3`, 0.85) is also the single
lowest-scoring element in the corpus, and **that reproduces**: across 14
same-configuration direct-path runs (`code_version_hash` `288c64f1`, depth map
on, temperature 0 — the Task 1/2 freeze plus Task 3's ON-arm repeats), 966
elements, the only element below 0.90 is that one, twice. So the separation is
not an artifact of a single draw.

It is still **not a validated detector**, and the paper must say so in the same
breath:

- There is exactly **one distinct invented element** in the audited corpus. One
  positive case cannot establish a false-negative rate — I have no way to know
  what fraction of *other* hallucinations would score low.
- The prompt's own boundary is 0.80, and **0.80 catches nothing**. A cut at 0.90
  is fitted after the fact to that single case.
- The score is blind to the corpus's other non-verbatim category: all **39**
  `real_split_title` rows — real titles broken by multi-column interleaving,
  the layout condition that most degrades transcription here — score at or
  above 0.95. Whatever the low end tracks, it is not layout difficulty.

This is why the system gates on explicit human verification
(`human_verified` / `verified_at` / `verified_by` on all four levels,
`infra/migrations/005_add_verification_columns.sql`) rather than on this score.

---

## Guardrail 2, verified against the live tree

Zero hits for `needs_review` or `CONFIDENCE_THRESHOLD` in `src/`, `evaluation/`
or `infra/cdk/lib/`.

⚠️ **A local grep DOES hit both names**, under `infra/cdk/dist/` and
`infra/cdk/cdk.out.deploy-dev/` — stale build artifacts of a pre-2026 revision
that genuinely had `CONFIDENCE_THRESHOLD=0.7`, a `needs_review` field, and a
`parse_batching` filter that dropped low-confidence elements. Both paths are
**gitignored and untracked**, so they are absent from a clean checkout and from
the arXiv tarball. Anyone re-verifying guardrail 2 will hit them and should not
read them as evidence of a live gate.

---

## Two paths measured, deliberately

The detector eval runs the direct path; production runs the batched one, and
they do not converge. Both are recorded rather than pooled.

| | direct (eval) | batched (production) |
|---|---|---|
| elements | 379 | 390 |
| distinct confidence values | 7 | 5 |
| indicators ≥0.95 | 236/263 | 236/263 |

⚠️ The batched path is **biased upward by construction**: `_merge_duplicate`
keeps `max(keep.confidence, other.confidence)` when folding two views of one
element together. A direct-vs-batched difference in this distribution is an
artifact of merging, not a statement about the model. Dataset statistics use
the batched (production) path; the confidence-versus-verdict join uses the
direct path, because that is the only path the false-positive audit covers.

---

## Outstanding — not fixed here, deliberately

> **Canonical queue: [CLAUDE.md](../../../CLAUDE.md), "These two files are
> COST-GATED right now."** That is the copy a session reads *before* deciding
> to edit, and it wins if this section ever disagrees with it.
> `tasking/arxiv_paper.md` Task 6 carries the pointer so the re-record
> executes it.

A sweep of both frozen files on 2026-08-23 found `detect_structure`'s numbered
docstring (`detector.py:1514-1524`) carries **three** defects:

1. **Wrong model**, twice (lines 1516, 1520): "Claude Sonnet 4.5". Detection
   runs on **Opus 4.6**. Lines 113 and 961 already say so correctly, so this is
   confined to the one docstring.
2. **A step that does not exist** (line 1522): "Flags low-confidence elements
   for review." Nothing flags anything. This is exactly the false claim
   guardrail 2 exists to catch, in the function a reader verifying that
   guardrail opens first.
3. **Pass-1 depth-map inference is omitted entirely** — yet `detect_structure`
   calls `infer_depth_map(blocks)` before chunk classification. The depth-map
   pass is the paper's central method claim, and the docstring of the function
   implementing it credits a step that does not exist while missing the one
   that does. This is the substantive defect of the three.

`parser.py` swept clean — no stale model name, no `needs_review` language (the
hits for those terms are in the gitignored `cdk.out.deploy-dev/` copy, not the
live file). Its queue item is an **addition**: pre-normalization code logging so
a `validator._validate_code_shape` rejection can be localized.

**None of it was fixed here, on purpose.** `eval_common.code_version_hash`
hashes the raw bytes of `detector.py` and `parser.py`, so editing even a
docstring changes `288c64f1` — the hash cited by every recorded manifest in
`paper/results/`. Two concrete costs: the 53-entry / 2.8MB `evaluation/.cache`
invalidates, so evals that are free today become live Bedrock calls; and
recorded results stop matching HEAD (the numbers stay valid — they were validly
produced by that code — but reproducing them needs a `git checkout` of the
recording commit). Re-running the detector arms alone is ~315K Opus tokens,
about **12% of a daily quota**, for a comment fix.

**Fix the whole batch in the next window that busts the hash anyway** — Task 6's
full-document re-record — and record the *new* hash rather than carrying
`288c64f1` forward.
