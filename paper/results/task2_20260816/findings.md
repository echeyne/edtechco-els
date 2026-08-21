# Task 2 — held-out generalization: Nevada (2023) and Kentucky (2021)

Run 2026-08-16 against `outputs/08-16-26`, `--no-cache`, code version hash
`3b445471` (the same hash Task 1 recorded, so these numbers and Task 1's grade
the identical detector/parser source).

**Corpus tier: `_only_subset`.** NV is 15pp, KY is 8pp, both manually trimmed
from full documents (98pp and 120pp). No number in this folder is a
full-document number.

---

## Headline results

### Detector — fresh direct-path run, graded against the held-out detector goldens

| | NV | KY |
|---|---|---|
| golden elements | 41 | 44 |
| detected | 53 | 44 |
| **recall** | **1.000** (every level) | **1.000** (every level) |
| raw precision | 0.774 | **1.000** |
| annotation-coverage ceiling | 0.7736 | **1.0000 (exhaustive)** |
| **verified precision** (FP audit) | **0.981** (52/53) | **1.000** (44/44) |
| code accuracy | 39/41 (0.951) | **44/44 (1.000)** |
| description accuracy | 2/3 | **26/26 (1.000)** |
| depth map | PASS | PASS |
| regression cases | 3/3 PASS | 3/3 PASS |

### Parser — run on the deployed batched detections in `outputs/08-16-26`

| | NV | KY |
|---|---|---|
| golden standards | 15 | 26 |
| parsed | 24 | 26 |
| coverage | **1.000** | **1.000** |
| field accuracy | 0.974 | 0.983 |
| field accuracy over asserted cells only | 0.969 | 0.980 |
| fully correct | 8/15 | 22/26 |
| `standard_id` collisions | 0 | 0 |
| regression cases | 3/3 PASS | **2/4 PASS** |

**Generalization holds.** Both held-out states reach recall 1.000 at every
level and parser coverage 1.000 on the first graded run, with a correct depth
map, on documents that were never used to develop a prompt rule. Kentucky is
the stronger result of the two: a perfect score on every detector dimension
against an *exhaustive* golden. The defects below are real but narrow, and
none of them is a level-classification or a coverage failure — which is what
the paper's central claim is actually about.

---

## What the paper may and may not claim

### 1. Kentucky's detector golden is EXHAUSTIVE, so KY's precision is a real precision number. This is the single most load-bearing fact here.

Guardrail 8 exists because the golden four's detector goldens are 5–25-element
spot-checks against 25–122 in-scope detections, making raw "precision"
arithmetically annotation coverage. **KY is not that case.** The detector emits
44 elements, all inside annotated domains; the golden annotates 44; the level
counts agree exactly (3 domain, 5 strand, 10 sub_strand, 26 indicator); and
there are **zero** unmatched detections. The coverage ceiling is 1.0000 and the
raw precision reaches it.

So KY's 1.000 precision is a genuine hallucination-free result on a whole
subset document, not an artifact of thin annotation. This is the strongest
precision evidence in the project, and it comes from a held-out state.

NV is the familiar case — ceiling 0.7736 (41 golden / 53 in scope), and raw
precision equals the ceiling to four decimals, meaning every unmatched
detection is unannotated content rather than a scoping artifact. NV's real
precision comes from the audit below.

### 2. The FP audit for the held-out states is DONE as a first pass, and it is small — but it is unsigned, and Task 1b itself has still never been run.

Task 2 step 4 assumed NV/KY precision would come from *extending* the Task 1b
audit. Two things changed that. First, `paper/results/task1b_fp_audit.json`
**does not exist** — Task 1b has not been executed for the golden four, so
there was nothing to extend. Second, the held-out goldens are dense enough
that the audit is nearly free: **12 verdicts for NV and 0 for KY**, against
~165 for the golden four.

I drafted all 12 NV verdicts (`heldout_evidence.json` →
`fp_audit_first_pass`), each checked against the extraction text rather than
by eye:

| verdict | n | meaning |
|---|---|---|
| `real_repeat_of_matched` | 6 | a second, correct detection of a heading the document reprints on another page spread |
| `real_unannotated` | 5 | real content the spot-check golden did not annotate — title found verbatim in the extraction |
| `hallucinated` | **1** | title absent from the extraction |

**NV verified precision = 52/53 = 0.981. KY = 44/44 = 1.000.**

The audit reconciles exactly with the per-level false-positive counts, which is
a useful independent check that nothing was mis-bucketed: NV's 12 in-scope FPs
are 10 strand + 1 sub_strand + 1 indicator, and the audit assigns 5 unannotated
+ 5 repeats to strand, the 1 repeat (`S.EO`) to sub_strand, and the single
hallucination to indicator.

The 5 `real_unannotated` items are the document's own Social Studies Standards
4 and 5, Science Standards 3 and 4, and Technology Standard 3 — each appears
exactly once in the extraction, and the golden's `test_case_id` numbering
leaves exactly the matching gaps (`NV-STR-01,02,03,06,07,10,11`), confirming
they were skipped deliberately rather than missed.

⚠️ **These verdicts carry `verified_by: "claude-first-pass-UNSIGNED"`.** Task
1b's methodology requires Emily as annotator of record, and the paper sentence
("all unmatched in-scope detections of the recorded run were manually audited
by the author") is not true until she signs off. Nothing here is publishable
as a precision number before that.

**Recommended amendment to Task 2 step 4 / Task 1b:** report *verified
precision* for all six states on the one definition, so the generalization
table is methodologically uniform. KY simply needs no audit because it has no
extras — that is a property of the state, not a different method.

### 3. NV's one hallucination is the `SS.CI.PK3` defect CLAUDE.md already documents. It reproduced exactly, on current code.

The detector emitted two elements coded `SS.CI.PK3`:

- correct: title *"Recognize and resolve conflicts with peers in an age-appropriate manner."*, `source_text` complete.
- defective twin: title *"Recognize and resolve conflicts with peers **with adult guidance**."*, `source_text` a truncated prefix (`"SS.CI.PK3. Recognize\nand resolve conflicts with"`).

The phrase "with adult guidance" appears **0 times** in the NV extraction. The
trigger is visible in the extraction: NV p5 is a multi-column table whose
reading order interleaves columns, e.g.
`"SS.CI.PK3. Recognize Make connections to children's name writing as their signature.* conflict. and resolve conflicts with Sing songs and c…"`.

Two consequences, both already anticipated in CLAUDE.md and both re-confirmed:

- the parser's 25 detected indicators → 24 standards collapse is **correct** and must not be "fixed";
- `_is_title_grounded` would catch this shape but is deliberately scoped away
  from indicators. Its docstring's premise ("nothing invents a leaf out of its
  own code") still holds — this leaf was invented out of a *truncated
  transcription*, which is a different shape.

### 4. NV's two domain-code misses are exactly the failure CLAUDE.md predicted, and the mechanism is now pinned. `SS` is correct only by coincidence.

CLAUDE.md: *"If NV domains still come back as SCIE/TECH while the sub_strands
are right, this citation is the first thing to check."* That is precisely what
happened — all 8 sub_strands now carry the document's `XX.YY` caption code
(regression `NV-SUB-STRAND-CODE-FROM-DOCUMENT` PASSes), while two of three
domains do not. Using `detector.py`'s own `_is_code_grounded` /
`_DERIVABLE_CODE_RE` / `derive_code_from_title` (imported, not reimplemented):

| domain | golden | detected | derivable shape | grounded | would golden code be grounded in this `source_text`? |
|---|---|---|---|---|---|
| Social Studies | `SS` | `SS` ✅ | yes | **no** | no |
| Science | `S` | `Science` ❌ | no | yes | yes |
| Technology | `T` | `TECH` ❌ | yes | **no** | **no** |

Read carefully, this says three separate things:

- **Social Studies passes for the wrong reason.** `SS` is not grounded in
  `source_text` (`"Social Studies"`), so `_resolve_code` recomputed it — and
  `derive_code_from_title("Social Studies")` returns `SS`, which happens to
  equal the printed code. The rule-4 recovery clause did not fire here either;
  the abbreviation just collided with the right answer. **Do not read NV
  domain code accuracy 1/3 as "the clause works for one domain."**
- **Technology is the clean confirmation of the documented coupling.** `TECH`
  has derivable shape and is ungrounded, so it was recomputed;
  `golden_code_would_be_grounded_in_this_source_text` is **false**, meaning
  that even if the model *had* recovered `T` from the descendants' prefix,
  citing only the heading line `"Technology"` would have left it ungrounded and
  `_resolve_code` would have overwritten it with `TECH` anyway. The
  `source_text` citation is the load-bearing half, exactly as documented.
- **Science failed differently and is not a `_resolve_code` case at all.**
  `Science` contains lowercase, so `_DERIVABLE_CODE_RE` never matched and
  nothing recomputed it. The detector log shows cross-chunk drift —
  `domain 'science' — canonical code 'Science', replaced: ['SCIE']` — so some
  chunks emitted `SCIE` and others the bare domain name, and
  `normalize_element_codes` canonicalized on the name. The two domains drifted
  in opposite directions in the same run (`Science` kept the long form, `TECH`
  the abbreviation), which shows the winner is arbitrary.

Blast radius is bounded: `standard_id` is
`{country}-{state}-{year}-{indicator_code}` and NV indicator codes are the
document's own (`SS.ID.PK1`), so **no NV primary key is affected**. It costs
`domain.code`, and it propagates into `strand.code` — the parser's 4 NV strand
mismatches are all `TECH.1`/`TECH.2` where the golden has `T.1`/`T.2`.

### 5. NV's other 3 parser mismatches are one detector description truncation, counted three times.

`domain.description` 12/15 — all three failures are the Science domain intro,
truncated at 2410 of 3500 characters (the detector suite reports the same
truncation at source: `[DESC/TRUNCATED] NV-DOM-02`). One detector defect, three
parser cells, because three standards share that domain.

So NV's entire 7-cell parser deficit reduces to **two** root causes, both
inherited from the detector: the Technology domain code (4 cells) and the
Science description truncation (3 cells). The parser itself introduced no NV
error.

### 6. KY's parser wrote 4 malformed Aurora primary keys — and the suite reported field accuracy 1.000 while doing it. Instrument repaired.

The parser emitted **unqualified** indicator codes for the four
Health/Mental Wellness indicators — bare `TCPHS`, `IHFC`, `PARTO`, `PSGPB`
instead of `HMW.1.1.TCPHS` etc. — producing `standard_id` `US-KY-2021-TCPHS`
instead of `US-KY-2021-HMW.1.1.TCPHS`. Domain, strand and sub_strand were all
correct (`HMW`, `HMW.1`, `HMW.1.1`); only the leaf lost its parent chain.

**This is parser variance, not bad detector input.** The detector's HMW
elements are structurally identical to the domains that parsed correctly —
bare derived abbreviations at indicator level, `Benchmark N.N` sub_strands,
`<Domain> Standard N` strands. Approaches-to-Learning's `EASPT` became
`AL.1.1.EASPT`; HMW's `TCPHS` stayed `TCPHS`. Same shape in, different shape
out, and the failure is confined to one domain chunk.

**It is intermittent, it is long-standing, and it is sampling-driven.** Two
independent records say so.

*Deployed batched production runs* (`heldout_evidence.json` →
`ky_code_qualification_history`) — 2 of 6 fired:

| run | unqualified indicator codes |
|---|---|
| 07-26-26 | 0 |
| 08-01-26 | **4** (all HMW) |
| 08-13-26 | **2** (`UMNDW`, `ESSDP` — not HMW) |
| 08-15-26 | 0 |
| 08-15-26-2 | 0 |
| 08-16-26 (batched) | 0 |

*Direct-path eval runs.* `run_parser_cached` writes every run to
`evaluation/.cache/` keyed by (state, detection hash, code hash, suffix), so
the cache is an accidental but faithful record of independent runs over
identical input (`heldout_evidence.json` → `ky_direct_path_cache_runs`).
**10 of the 20 cached KY parser runs fired**, spanning 8 code versions and 2
detection inputs, affecting between **2 and 15** of 26 standards when they do.

The two clusters that settle causation, because within each one the input,
the code version and the temperature are all identical:

| code hash | detection | graded | stab-0 | stab-1 | stab-2 | stab-3 | stab-4 |
|---|---|---|---|---|---|---|---|
| `c335e73a` | `2f7682…` | 0 | **6** | 0 | **4** | – | – |
| `6c193627` | `a77909…` | 0 | **4** | 0 | **15** | – | – |
| `3b445471` (current) | `2f7682…` | **4** | 0 | 0 | 0 | 0 | 0 |

Four runs, three different answers, same input — twice. This is parser
sampling variance at temperature 0, not a code regression, and it predates
every recent change.

Two things follow that the paper must not get wrong:

- **The defect is not new and must not be attributed to a recent change.** It
  appears at 8 distinct code hashes going back through the cache.
- **The direct and batched paths disagreed on the same detection today** —
  the batched production run over `outputs/08-16-26` emitted 0 while the
  direct-path eval over that same file emitted 4 — but given the within-path
  variance above, that is a draw from the same distribution, **not** evidence
  that the paths differ. Task 1's separate finding that parsing does not
  converge between paths stands on its own evidence, not on this.

**Honest count for today at the current code hash:** I observed the defect in
**2** direct-path runs (the first graded eval run and the stability
invocation's graded run) and not in the 5 stability runs. The cache retains
only one of the two firings, because both graded runs write the same
suffix-less cache key and the second overwrote the first — so the table above
under-counts by one. 2 of 7 observed runs today; with the historical record,
call it "a substantial minority of runs", not a precise rate.

**This is the same defect CLASS as Task 1's CA `Foundation N.N` finding** — an
intermittent, per-chunk parser failure that writes a malformed primary key —
but a **different surface form**, and that matters for the fix Task 1
recommended. Task 1 proposed a shape guard blocking "a code segment containing
whitespace or a leading label word." That guard would **not** catch this one:
`TCPHS` has no whitespace and no label word. The guard must also require that
an indicator's code be **prefixed by its parent's code**, which is exactly
what the `KY-BENCHMARK-CODE-NORMALIZED` regression check asserts — and which
is what caught this.

#### The instrument defect this exposed (repaired, verified score-neutral)

The first graded run reported KY **coverage 0.846, field accuracy 1.000**, with
`KY-STD-14..17` listed as *dropped*. That perfect field accuracy was an
artifact: `eval_parser._match_key` keyed identity on
`(indicator name, age_band, _variant_suffix)`, and `_variant_suffix` is read
**off the code**. Golden `HMW.1.1.TCPHS` yields suffix `TCPHS`; malformed bare
`TCPHS` has no dot and yields `None`. The pair could never meet, so the four
defective standards were reported as dropped — which removes them from
`field_stats` entirely. **The four malformed rows were excluded from the
denominator of the metric whose job was to catch them.** Only the regression
cases saw it.

Repair: `_variant_suffix` is no longer part of the key. It is now applied as a
**tie-breaker inside `grade_parser`**, used only when more than one candidate
shares `(name, age_band)` — which is the condition its own docstring already
described. This is a tightening, not a loosening: a malformed code can no
longer prevent pairing, and is graded as the wrong code it is.

- Verified **score-neutral on all four golden states**: re-grading the
  identical cached parser output gave **0 diffs** across every field of every
  state report (CA's 39 proficiency-variant groups and TX's 10 still resolve
  correctly through the tie-breaker).
- KY after repair: coverage **1.000** (26/26), field accuracy **0.983**,
  fully correct 22/26, with the 8 real mismatches (4 `standard_id` + 4
  `indicator.code`) now visible. NV unchanged.
- Pre-repair report preserved as `parser_heldout2_prerepair.json`.
- Bonus: `measure_stability` keys on `_match_key` too, so it inherits the same
  property — a run-to-run code change now counts as a field disagreement
  (`_sig` covers `indicator.code` and `standard_id`) instead of dropping the
  element out of the comparison unseen. That is one of the two repairs Task 5
  lists as a prerequisite.

### 7. `measure_stability` reported a field disagreement rate of 0.000 for KY — in the same invocation whose graded output carried 4 malformed primary keys. Task 5 must not spend its budget on this instrument as-is.

`python -m evaluation.eval_parser --state KY --stability-runs 5 --no-cache`
returned **field disagreement rate 0.000, output size stdev 0.00**, and the
same command's report block listed the 8 `standard_id` / `indicator.code`
mismatches. Both are true, and the combination is the problem.

The cause is structural, not bad luck: `measure_stability` spawns its own N
runs (`stab-0…4`) and compares them **only to each other**. The run the suite
actually *graded* is a separate call and is never in the comparison. On
2026-08-16 the graded run (18:19:22) emitted 4 unqualified codes and the five
probe runs (18:22–18:33) emitted none, so the probe saw five identical outputs
and reported perfect determinism about a pipeline that had just produced a
different answer minutes earlier on the same input.

This is a **third** instrument defect, alongside Task 1's two and the
`_match_key` repair above, and it directly threatens Task 5's design. Task 5
already plans to repair `measure_stability`'s match key; that is necessary but
**not sufficient** — with N=5 and a defect that fires in a minority of runs, a
0.000 result is entirely compatible with a real defect rate, and it will read
as "the pipeline is deterministic" in a paper table. Recommended before Task 5
spends its ~60 runs:

1. **Include the graded run in the comparison** (N+1 observations, zero extra
   cost), so the number describes every run the suite made.
2. **Report the observed range, not only the disagreement rate** — "5 runs, 0
   disagreements" and "1 of 6 runs differed in 8 cells" are very different
   claims and only the second is true here.
3. **Report the denominator.** A stability table must say how many runs and
   over what span; the plan's existing "split across ≥2 sessions/days" note is
   the right instinct and this run is fresh evidence for it.

Note the `_match_key` repair above already fixed the *other* half of this:
because identity no longer depends on the code, a run-to-run code change now
counts as a disagreement instead of dropping the element from the comparison
unseen. The five clean runs genuinely agreed; the blind spot that remains is
which runs get compared, not what gets compared.

### 8. The domain scoping did real work on both states, and there is no level confusion.

Verified rather than assumed, via the match-path audit that replays
`grade_elements`' two-tier lookup: **NV 41/41 and KY 44/44 matched
domain-scoped, 0 via the domain-agnostic fallback, 0 crossing a domain
boundary.** So neither state's recall is propped up by cross-domain matching
(the AZ scoping quirk from Task 1 has no analogue here).

The level-agnostic confusion re-pairing — which is what "level confusion"
actually means, since `level` is inside the match key and makes the suite's
built-in matrix structurally diagonal — finds **0 off-diagonal pairs** in both
states. Every element landed at the right depth.

---

## Provenance note: KY's parser golden was annotated against a different detection

`ground_truth_parser/KY.json` records `source_detection:
outputs/08-13-26/KY-detection.json`, but this run graded against
`outputs/08-16-26`. The two differ in exactly three ways, all benign and all
attributable to landed changes:

- **15 `description` fields** changed `""` → `null` — `models._blank_to_none`
  (2026-08-15), working as designed.
- **1 strand code**: `Standard 2` → `Language and Early Literacy Standard 2`
  — rule 4's code-lookup clause, and the fix the `KY-STRAND-CODE-KEEPS-FULL-LABEL`
  regression case was written for. It now PASSes.
- **1 `source_text`** differs by one newline.

Element count, levels, titles and every other code are identical. NV's is
element-identical to its annotated source (`outputs/08-15-26-2`) apart from
timestamps. **No golden was edited to accommodate this run.**

---

## Corrections to `tasking/arxiv_paper.md`

- The Task 2 STATUS block says the held-out goldens are "denser than the
  golden states' spot-checks, which changes the precision story for NV/KY."
  Confirmed, and stronger than stated: **KY's is exhaustive**, not merely
  denser.
- Step 4 says precision for NV/KY "comes from extending the Task 1b audit."
  Task 1b has never been run and `paper/results/task1b_fp_audit.json` does not
  exist, so there was nothing to extend; the NV/KY audit is drafted here
  standalone and Task 1b still owes the golden four.
- The background table's KY `_only_subset` page count (9) is wrong — the file
  is 8pp. Already noted in Task 1's manifest; repeating it because the table
  still says 9.

---

## Open questions for Emily

1. **Sign off on the 12 NV false-positive verdicts** in
   `heldout_evidence.json` (6 repeats, 5 real-unannotated, 1 hallucinated).
   Until you do, NV verified precision 0.981 is not quotable and the Task 1b
   methodology sentence is not true. KY needs no verdicts — it has no extras.
2. **The KY unqualified-code defect is blocking for Aurora**, same as Task 1's
   CA finding. It writes `US-KY-2021-TCPHS` — a bare 5-character abbreviation
   with no namespace, far more collision-prone than a qualified key. Task 1's
   recommended shape guard does **not** catch it; the guard needs the
   parent-prefix condition added. Recommend widening that one guard to cover
   both defects rather than adding a second.
3. **Do you want NV's `SS` domain-code coincidence recorded as a golden note?**
   It currently reads as a pass and will silently become a failure if
   `derive_code_from_title` or the connector list is ever touched.
4. **NV description-accuracy denominator is 3.** Only three NV golden elements
   annotate a description, so "2/3" is the honest report and a rate (0.667)
   is not meaningful. If you want a real NV description number, that needs
   more annotated descriptions — flagging rather than assuming.
