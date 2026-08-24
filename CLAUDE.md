# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

The Early Learning Standards (ELS) Platform: a serverless AWS pipeline that ingests US state early-learning-standards PDFs, uses Bedrock (Claude) + Textract to detect and normalize their hierarchy into a canonical schema, and stores the result in Aurora PostgreSQL. On top of it sit three web apps (Standards Explorer, Planning App, Landing Site). See [README.md](README.md) and [documentation/ARCHITECTURE.md](documentation/ARCHITECTURE.md) for the full picture — this file covers only what isn't obvious from those.

## Keep documentation in sync with substantial changes

When a change alters behavior, config, schema, or architecture (not a small bug fix), grep the docs (`README.md`, `CLAUDE.md`, `documentation/*.md`, and any other `.md` that describes the touched area) for stale references and update them in the same pass — don't leave the code change and the docs update as separate follow-up work. A doc describing removed/changed behavior is worse than no doc at all, since it reads as authoritative.

## Design direction for the detector & parser (READ BEFORE EDITING `detector.py` / `parser.py`)

**Goal: `detector.py` and `parser.py` should be LLM-driven, not rule-driven.** The intended architecture is "let the model reason about the document; keep the Python thin." Detection/parsing decisions — how to classify a level, how to build a code, how to handle age-band columns, how to strip a structural label — belong in the **prompt**, expressed as general document-structure principles, not in Python regexes and special-case branches.

### ⚠️ These two files are COST-GATED right now (as of 2026-08-23) — batch your edits

`eval_common.code_version_hash` hashes the **raw bytes** of `detector.py` and `parser.py` and nothing else. It currently reads **`288c64f1`**, and that value is cited by every recorded manifest under `paper/results/` (Tasks 1, 1b, 2, 3, 3-stability, 4, 8). Editing either file — **including a comment or a docstring** — changes it, and two things follow:

1. **The eval cache invalidates.** All 53 entries / 2.8MB in `evaluation/.cache` become misses, so evals that are currently free become live Bedrock calls. Re-recording the detector arms alone is ~315K Opus tokens (Task 1 208,835 + Task 2 106,606), about **12% of the 2,592,000/day quota**.
2. **Recorded results stop matching HEAD.** The numbers stay valid — they were validly produced by that code — but reproducing them needs a `git checkout` of the recording commit rather than just running the script, and a reader diffing the hash cannot tell a docstring change from a logic change.

This is **a cost, not a prohibition.** A real defect still gets fixed. But a cosmetic fix should wait and ride along with a change that busts the hash anyway — the next one scheduled is the arXiv paper's Task 6 full-document re-record (`tasking/arxiv_paper.md`).

**The deferred queue — do all of these in that same window:**

| # | file | what | why it is deferred, not done |
|---|---|---|---|
| 1 | `detector.py:1516,1520` | `detect_structure`'s docstring says detection runs on "Claude Sonnet 4.5". It runs on **Opus 4.6** (`config.BEDROCK_DETECTOR_LLM_MODEL_ID`). Lines 113 and 961 already say Opus 4.6 correctly, so it is only this docstring. | cosmetic |
| 2 | `detector.py:1522` | Step 4 of the same docstring, "Flags low-confidence elements for review", describes a gate that **does not exist** — nothing thresholds `confidence` and there is no `needs_review` field. This is the single most misleading line in either file: it is exactly the false claim the arXiv paper's guardrail 2 exists to catch, sitting in the function a reader checks first. | cosmetic, but fix it FIRST in the batch |
| 3 | `detector.py:1514-1524` | The same numbered docstring **omits Pass-1 depth-map inference entirely**, though `detect_structure` calls `infer_depth_map(blocks)` before chunk classification. That pass is the paper's central method claim; the docstring credits a step that does not exist while missing the one that does. Found 2026-08-23. | cosmetic |
| 4 | `parser.py` | Add logging of the LLM's **pre-normalization** code, so a `validator._validate_code_shape` rejection can be localized. The validator sees only the final record, so today's log carries the chain, page and `standard_id` but not what the model actually emitted. See "Why it lives in `validator.py`" below. | genuinely useful, but not urgent enough to spend the quota alone |

`parser.py` was swept on 2026-08-23 and carries **no** stale model name and no `needs_review` language — item 4 is an addition, not a correction. If you add to this queue, note the date and keep the table's "why deferred" column honest: a real defect does not belong here.

**The problem we were fighting: overfitting to the golden set.** The golden states (CA, AZ, CO, TX) had each been made to pass by adding targeted, per-state Python logic that scored well on the goldens but **did not generalize**. The 2026-06 LLM-first migration (`tasking/detector_parser_llm_migration.md`, Tasks 1–8, completed 2026-06-27) removed that logic and moved each rule into the prompt as a general principle. The per-state helpers that are now **gone** — do not re-introduce them or anything shaped like them:

- `detector._LABEL_PREFIX_RE` + the label-strip half of `_strip_label_prefix`, and `parser._LABEL_CODE_RE` (`Strand N:` / `Concept N:`) → detector prompt rule 4: a `<Label> <id>: <Title>` heading's label-and-id IS the code, the text after the colon is the title (any structural-label word, not a fixed list).
- `parser._abbreviate_title` + `_CODE_ABBREV_LEN` → detector prompt rule 4: derive a ≤5-char uppercase code from the title. Split on spaces/slashes (hyphenated compound = one word), drop connector words (`a an the and or but nor of to in on at by for from with into about over under through as`, `&`), then single content word → first 4 letters (`Vocabulary`→`VOCA`), multiple → first letter of each, capped at 5 (`Concepts About Print`→`CP`, `Approaches to Learning`→`AL`). The parser prompt restates the same procedure for the sub_strand/indicator collision case — **keep the two in sync**. ⚠️ **Partly reversed 2026-08-01** — the rule still lives in the prompt, but it is now also executed deterministically by `detector.derive_code_from_title`, because the prompt alone could not make it reproducible. See "The one derivation that came back to Python" below; that helper is the sanctioned form, and a per-state abbreviation branch remains forbidden.
- `detector._TRAILING_DOMAIN_LABEL_RE` → detector prompt: a domain title's trailing structural noun (`Standard`, `Domain`) is not part of its name — emit the bare name.
- `parser._COLUMN_PREFIX_RE` / `_strip_column_prefix` + the PK-strip inside `_infer_domain_code` → parser prompt: a leading age/column token (e.g. `PK3.`) is excluded from the base hierarchical code.
- `parser._disambiguator_suffix`, `_derive_label_abbrev`, `_COLUMN_ABBREV_LEN` + the suffix re-application in `parse_llm_response` → parser prompt DISAMBIGUATE rule: side-by-side columns emit DISTINCT codes directly (age-range → month range `.36-48`; proficiency → first-4-uppercased `.DISC`). Uniqueness is enforced afterwards by `disambiguate_colliding_standards` (see "Where a printed code is not unique" below), which resolves collisions by ancestor and keeps a numeric counter only as a last resort.
- the CA collision branch + `_PURE_NUMERIC_RE` in `abbreviate_element_codes` (and the now-empty `abbreviate_element_codes` / `normalize_code_to_canonical` shells) → parser prompt: a sub_strand and its child indicator must never share a code; the sub_strand derives its segment from its title with the same ≤5-char abbrev scheme.

A new per-state regex/branch in `detector.py` or `parser.py` is a regression in disguise even if it raises a golden score — flag it rather than adding it. The justified Python that survives is document-agnostic only: `generate_standard_id`, `normalize_parsed_codes`, `normalize_element_codes` (cross-chunk drift), `chunk_elements_by_domain` / `_split_oversized_chunk` / `chunk_text_blocks` / `_dedup_elements`, `_infer_domain_code` routing (PK strip removed), the generic age-band canonicalizers (`canonicalize_age_band`, `_normalize_age_band`, `_reconcile_age_band_drift`, `_TRAILING_MARKER_RE`), `_canonicalize_code` (folds `<Label>: <id>` → `<Label> <id>` by shape, never by label word), `_is_title_grounded` (drops a heading whose title is absent from its own `source_text` — a parent back-formed from a child's code), `derive_code_from_title` / `_is_code_grounded` / `_resolve_code` (see below), `_anchor_parent_chain` / `disambiguate_colliding_standards` (see below), `_splice_overlapping_prose` (see below), and the JSON-extraction / schema-validation plumbing.

Each of those earns its place by reading the SHAPE of the output rather than any document's vocabulary, and each fixes a defect the prompt alone could not: the LLM emits both spellings intermittently at temperature 0, so a prompt rule reduces the rate but cannot make the output reconcilable. Pair them with the prompt rule, don't substitute one for the other.

`models._blank_to_none` (2026-08-15) belongs to that same family, one layer up. Absence has one spelling in this schema — `None` — and the pipeline was producing two. `detector._create_detected_element` coerced a missing description to `""` (`.get('description') or ""`), so every description-less element carried an empty string (18/44 KY, 49/52 NV, 48/61 CO); those `""` were then serialized into the parser prompt and the LLM echoed them back for some rows while emitting `null` for others — on KY, 9 `""` vs 17 `null` across 26 standards at *each* of domain/strand/sub_strand, and 45/170/22/8 blanks on AZ/CA/NV/TX from the same run. Which spelling a row got was decided by sampling, so the prompt alone could not fix it. The remedy is the sanctioned pairing: both prompts now state "ABSENCE IS `null`, NEVER `""`", and a `mode="before"` field validator folds a blank string to `None` on every optional free-text field (`HierarchyLevel`/`HierarchyNode.description`, `DetectedElement.description`/`age_band`, `NormalizedStandard.age_band`). It lives in `models.py` rather than at the parser call site because `HierarchyLevel` is constructed from four places — `parser.parse_llm_response`, `validator.deserialize_record`, the batch-merge handlers — and a call-site fix covers one. It reads only whether a string is entirely whitespace, never any document's vocabulary, and it never touches a non-blank value (verified byte-identical over 695 real descriptions across all six states). Note that both golden sets already annotate absence as `null`, so this moves output toward the goldens; `eval_parser._norm_val` folds `""`/`None` together and so never surfaced the defect — the harm was downstream, in `db.py` writing `""` into Aurora's nullable `description` columns.

### The one derivation that came back to Python (2026-08-01)

Rule 4's ≤5-char abbreviation is a deterministic string algorithm, and the model samples it. Measured on Kentucky — three detector runs at temperature 0 over one frozen extraction — **11 of 44 elements (25%) got a different code on at least one run**, while `level`, `source_page` and `age_band` never varied once. The failures were not near-misses: one run emitted a 4-character code, one transposed two initials, several kept a connector the rule says to drop. On the parser side the same experiment moved **58% of KY `standard_id`s** across three runs. Since `standard_id` is `{country}-{state}-{year}-{indicator_code}`, that is a different Aurora primary key for the same standard depending on which run wrote it.

So `detector.derive_code_from_title` now executes rule 4's procedure in Python, and `_resolve_code` applies it — but **only where the document supplied no code of its own**. Two independent guards decide that:

1. **Shape** (`_DERIVABLE_CODE_RE`) — rule 4's abbreviation branch emits uppercase letters and nothing else, so a code carrying a digit, a separator or a lowercase letter is positional and is never touched. This is what protects rule 4's *other* branch, the lettered leaf whose code is just its list letter.
2. **Grounding** (`_is_code_grounded`) — a document code was read off the page and so appears in the element's own `source_text` (`Benchmark 1.1`, `I.A.2`, `1.0`), while an invented abbreviation is derived from the title and appears nowhere in it.

Both are needed, and the AZ generalization run is why: the model sometimes transcribes a lettered item's `source_text` without its `"a. "` prefix (8 of 9 AZ lettered leaves kept it, the ninth did not), so grounding alone read a real list code as invented and replaced it with an abbreviation of the title. A printed document code is authoritative and is never overwritten, however unlike our scheme it looks.

This is a **pairing, not a substitution** — rule 4 stays in the prompt verbatim, and the parser prompt still restates it; all three copies must agree. Three properties keep it inside the LLM-first line, and a future change here should preserve all three:

1. It reads only the SHAPE of a title — word boundaries and a fixed connector list — never any document's vocabulary, so it is the same class of helper as `_canonicalize_code` and `_is_title_grounded`.
2. It is scoped to the case the prompt itself calls out as "otherwise", so it cannot override what a document actually prints.
3. It was validated against the goldens rather than tuned to them: the rule executed correctly reproduces **40 of 40** hand-annotated derived codes across CA/CO/KY/NV, so no golden moved to accommodate it. If a future edit here needs a golden changed, that is the signal it has drifted from the documented rule.

Two alternatives were measured and rejected: dropping the connector rule fixed ~⅓ of the churn and would have required rewriting 26 of 40 golden codes; shortening the cap from 5 to 3 fixed 36% of the churn and raised sibling collisions from 6 to 8 across 262 standards. Neither reaches zero, and a primary key needs zero.

Rule 4(b)'s connector list survives that verdict but its *rationale* changed, and the prompt now says so: it was justified as a stability measure, which stopped being true once Python executes the rule — churn is zero either way. What it still buys is legibility, and the effect is large, because the code is the human-readable part of `standard_id` and has only 5 characters to spend: without the rule "Attends to an adult or peer who is communicating verbally or nonverbally" codes as `ATAAO` rather than `AAPWI`. Collisions are a wash (6/262 with the rule, 7/262 without). The list is admittedly arbitrary at its margins — it holds `through` but not `toward`, `during`, `between`, `despite` or `while`, which appear 19 times across the corpus — and that incoherence was a real liability while a model had to apply it from memory. Executed in Python it is free, so leave the list exactly as it is: any edit rewrites goldens for no measured gain.

### Where rule 4 looks for a code (2026-08-15) — prompt-only, no Python counterpart

Rule 4 always said "use the document's code if present. Otherwise abbreviate the title", and the whole weight sat on *present*. The model read only the heading line, so an element whose code the document prints **somewhere else** fell through to the abbreviation branch and got an invented code. Measured on Nevada (2026-08-13, `outputs/08-13-26/NV-detection.json`): detector code accuracy 28/41 (0.683), and **9 of the 13 mismatches were this one cause** — 7 sub_strands (`SS.ID`/`SS.CI`/`SS.GH`/`S.EO`/`S.SI`/`T.TT`/`T.CT` came out as `IDCI`/`CIP`/`GHE`/`EOH`/`SI`/`TT`/`CT`) and 2 domains (`S`→`SCIE`, `T`→`TECH`). Several of those sub_strands carried the printed code *in their own `source_text`* and were abbreviated anyway.

Rule 4 now names three places a code can live and orders them, and everything after them is the last resort:

1. **inline** on the heading line (unchanged — and it still wins outright: an element that prints its own id keeps it even when its descendants' codes use a different stem);
2. **in a caption beside the heading** — parenthetical, caption line, table/column header, or a lead-in naming the group that follows;
3. **as the shared leading prefix of its descendants' codes** — *an ancestor's code is the common prefix of its descendants' document codes*.

(3) is the general principle the fix turns on, and the prompt operationalizes it as **peel one whole segment per level going up**, rather than as a raw common prefix — a chunk that happens to show only one group under a heading would otherwise hand the heading its child's code. A level that prints its own code takes it and consumes no segment, which is what lets the recovered prefix cross a level the printed namespace skips (NV codes `<domain>.<group>.PKn` and skips the strand entirely).

Four shape-based guards keep (3) off the goldens, and the CA/KY cases are why each exists — check any edit here against them:

- the descendant code must have **more than one** dot-separated segment (CO's `1`/`6` and AZ's `a`/`b` carry no ancestor);
- **two** descendants must agree on the prefix and differ after it (a lone `PK3.I.A.2` must not donate `PK3.I.A` to its strand);
- only **whole segments** count;
- a descendant code carrying a **structural label word** (`Foundation 1.7`, `Benchmark 1.1`) is not a namespace path — the label names the descendant's own level, so the id after it is the descendant's. Without this, CA's `Foundation 1.7`/`1.8` would give the `Grammar` sub_strand the code `Foundation 1` instead of `GRAM`, and KY's `Benchmark 1.1`/`1.2` would rewrite their strand.

**No Python counterpart, deliberately.** Unlike rule 4's abbreviation, this is not a deterministic string algorithm over one field — it is a judgement about page layout ((2), which no post-processor can see) and about which of several codes in a chunk are descendants of which heading ((3), which needs the depth map and the reading order, not the emitted JSON). `_resolve_code` cannot help either: it decides which rule-4 branch produced a code the model already emitted, and cannot recover one the model never produced.

⚠️ **The clause is coupled to `_resolve_code` through `source_text`, and that coupling is load-bearing.** A recovered short domain code like `T` matches `_DERIVABLE_CODE_RE`, so if it is not grounded in its own `source_text` it gets recomputed to `TECH` and the fix is silently undone. Rule 4 therefore requires citing the caption/descendant line that supplied the code in `source_text` **in addition to** the heading line — which rule 7 ("the exact line(s) you used") already implies, and which the eval does not grade. Rule 1's self-check is unaffected: the heading line must still be there, and a child's line alone still means the heading was not seen. If NV domains still come back as `SCIE`/`TECH` while the sub_strands are right, this citation is the first thing to check.

**Measured 2026-08-16 (arXiv paper Task 2, `paper/results/task2_20260816/`): that is exactly what happens, and the prediction above is confirmed.** All 8 NV sub_strands now carry the document's `XX.YY` caption code, while 2 of 3 domains do not — detector code accuracy 39/41, and both misses are domains. Diagnosed with this file's own guards (`heldout_evidence.json` → `nv_domain_code_diagnosis` imports them rather than reimplementing):

- **`Technology`** is the clean confirmation. Emitted `TECH`; derivable shape, ungrounded, so `_resolve_code` recomputed it — and the *golden* code `T` would **also** be ungrounded in that element's `source_text` (which is the bare word "Technology"). So even a successful recovery of `T` would have been overwritten. The citation is the load-bearing half, as warned.
- **`Science`** never reached `_resolve_code` at all: it was emitted as the literal `Science`, which contains lowercase and so fails `_DERIVABLE_CODE_RE`. It lost to cross-chunk drift instead — the run log shows `canonical code 'Science', replaced: ['SCIE']`, i.e. chunks disagreed and `normalize_element_codes` canonicalized on the long form. The two domains drifted in **opposite** directions in one run (`Science` kept the name, `TECH` the abbreviation), so the winner is arbitrary.
- ⚠️ **`Social Studies` passes for the wrong reason and must not be read as evidence the clause works.** `SS` is ungrounded in its `source_text`, was recomputed, and `derive_code_from_title("Social Studies")` happens to return `SS`. The recovery clause did not fire; the abbreviation collided with the right answer. A future change to `derive_code_from_title` or the connector list would silently turn this pass into a failure.

Blast radius is bounded and worth knowing before prioritizing: NV indicator codes are the document's own (`SS.ID.PK1`), so **no NV `standard_id` is affected**. The cost is `domain.code` plus the 4 `strand.code` cells it propagates into (`TECH.1`/`TECH.2` where the golden has `T.1`/`T.2`).

The parser prompt got the matching half, since the detector now hands it dotted codes at sub_strand level: an **already-qualified** code (a dotted path whose first segment is its own domain's code) is used as-is at every level and never re-prefixed (`AB.CD`, not `AB.2.AB.CD`), and peeling parents off a qualified code **stops where the namespace stops** — if the next peel would equal the parent's own code, that level is outside the namespace and takes its heading's identifier instead (`AB.2`). One consequence is deliberate and documented in `ground_truth_parser/NV.json`: the sub_strand's code does not extend the strand's, because the printed identifier outranks chain continuity.

### The code-shape guard at the validation boundary (2026-08-20) — `validator._validate_code_shape`

A record whose codes are malformed is now **rejected by the validator** and never
reaches Aurora. This is the first thing in the pipeline that can drop a parsed
standard on quality grounds, so know it exists before debugging a "missing"
record: look for `CODE_SHAPE_GUARD` in the logs and for `error_type:
"code_shape"` in the run's validation summary.

`standard_id` is `{country}-{state}-{year}-{indicator_code}`, so a malformed
indicator code IS a malformed primary key. The parser emits one intermittently,
in two observed surface forms — CA 2026-08-13 left the structural label in
(`ELD.2.0.PA.Foundation 2.3.DISC`, 12 rows) and KY 2026-08-01/08-16 dropped the
parent chain entirely (bare `TCPHS` → `US-KY-2021-TCPHS`, 4 and 2 rows). It is
**sampling variance, not a code regression**: it appears at 8 distinct code
versions, and runs over an identical frozen input at temperature 0 disagree with
each other. A prompt rule lowers the rate but cannot reach zero, and a primary
key needs zero — the same argument that put `derive_code_from_title` in Python.

Three conditions, all shape-only (no per-state branch, no vocabulary, and
notably **no label-word list** — whitespace alone is the tell, which is how it
catches `Foundation 2.3` without knowing the word):

1. no code contains whitespace;
2. the **indicator's** code extends its nearest present ancestor's code;
3. `standard_id` ends with the indicator code.

⚠️ **(2) is scoped to the indicator level, and that scoping is load-bearing.**
A printed namespace may legitimately skip a level: NV's sub_strand `SS.ID` does
not extend its strand `SS.1`, and **15 of 15 NV standards break the chain there
by design**. Widening the rule to every level rejects all of Nevada. The leaf,
however, is nested in all six annotated states.
`tests/unit/test_validator_code_shape.py::test_nevada_sub_strand_may_break_the_chain`
is the canary — if it fails, the guard has stopped being document-agnostic.

Validated before being enabled: **zero false positives** across all six states of
`outputs/08-16-26` (262 standards) on all three conditions, while blocking
exactly the 18 historical defect rows. A future document that legitimately trips
a condition is a finding about the canonical code namespace — take it to a design
discussion, do not add a per-state exemption.

**Why it lives in `validator.py`.** It is the chokepoint (`validation_handler`
writes an S3 record only for a valid result and `persister.persist_records` reads
only those keys, so there is no bypass); refusing to store something structurally
impossible is the validator's concern rather than the parser's; and
`eval_common.code_version_hash` covers only `detector.py`/`parser.py`, so it
changes no recorded evaluation number. That last point is deliberate — it let the
guard ship without invalidating the arXiv paper's frozen Task 1/Task 2
measurements. Localization is therefore partial: the validator sees only the
final record, so the log carries the chain, page and `standard_id` but not the
LLM's pre-normalization code. Capturing that needs logging inside `parser.py`,
which busts the hash; do it when the measurement chain is next re-recorded —
it is **item 4 of the deferred queue** at the top of this section, which is
where the batch is tracked.

### Where a description crosses a page break (2026-08-22) — `_splice_overlapping_prose` (the prompt half was reverted)

A long domain/strand introduction can run past the bottom of a page, and the
document puts furniture in the seam: a bare page number, then a running header
repeating the domain name. The detector read that furniture as the end of the
prose and stopped. Measured on Nevada: the Science domain intro came out at
**2410 of 3500 chars**, cut exactly at the page 7 → 8 seam (extraction blocks
356 `…for all young children.` / 357 `50` / 358 `Science` / 359 `NAEYC's 10
Tips…`). CLAUDE.md's earlier note that "a different domain [truncates] on the
next run" is the same defect sampling differently, not a second one.

⚠️ **The prompt half of this was TRIED, DEPLOYED, and REVERTED on 2026-08-22.
Only `_splice_overlapping_prose` remains. Read the record below before
re-attempting a rule-8 page-break bullet — three wordings were measured and all
three cost more than they bought.**

**What was tried.** A rule 8 bullet saying a page break does not end an
element's prose: page number, running header/footer, copyright or citation line
are typography, not a boundary, recognized by SHAPE (short, no sentence
structure, recurs on other pages) rather than by wording. It DID fix the target
defect — NV Science went 2410 → 3500 chars, description accuracy 2/3 → 3/3,
reproduced across four runs including a 3-run stability check.

**Why it was reverted: it generalizes BACKWARDS, on two independent axes.**
Told that matter near a page seam is typography to skip, the model also skips
real content near a seam.

* **AZ — descriptions dropped.** Deployed to dev, run `08-22-26-2`: **12 of 45**
  indicators came back `description: null`, including five consecutive lettered
  ones (`a`-`e`, pages 11-12, the `LL.2.3` group) that had carried
  173/96/94/154/106 chars the run before. Parser `indicator.description`
  17/18 → 12/18. Deterministic, not sampling: A/B on one frozen extraction —
  remove the bullet and all five return at byte-identical lengths, restore it
  and all five vanish, twice.
* **KY — whole ELEMENTS dropped.** Recall **1.000 → 0.864**: 6 of 44 golden
  elements lost, and they leave as a coherent block (a sub_strand plus all its
  child indicators, e.g. `Benchmark 2.2` and its five). Two no-rule samples
  give 44/44; three with-rule samples give 38.

**Three wordings, none of which clears both:**

| variant | KY recall | NV desc | AZ nulls |
|---|---|---|---|
| no rule | **44/44 (1.000)** | 2/3 | 0/45 |
| original bullet | 38 | **3/3** | 12/45 |
| + "never justifies OMITTING a description" guard | 38/44 (0.864) | **3/3** | 0/45 |
| + "only ever ADDS, never removes" (elements too) | 38/44 (0.864) | 2/3 | 0/45 |

The omit-guard fixes AZ and keeps NV, but does NOT recover KY. Broadening that
guard to cover element emission loses NV's fix without helping KY. Scoping the
bullet to "domain/strand/sub_strand introductions only" also fixed AZ and also
lost NV — leading with a restriction buries the directive.

**The verdict: the rule was not just costly, it was UNNECESSARY.** It costs SIX
real standards on KY, and the thing it was written to buy — NV's complete
Science description — the Python half delivers on its own in the batched
pipeline (run 040: 3500 chars byte-exact, no prompt rule). So it is reverted
with nothing outstanding.

If some future case does need a page-break prompt rule, A/B it against **KY**
(element recall) and **AZ** (indicator `description` null count) on frozen
extractions, and confirm the batched path does not already handle it. NV alone
will tell you the rule works when it is doing nothing the splice was not
already doing.

**What survives — `_splice_overlapping_prose`.** It is kept because it is
correct independently of the prompt rule and can never lose data. Chunks
overlap, so a long passage can be split such that NEITHER chunk holds it whole:
the earlier one has the head (chars 0-2410), the later one opens mid-passage and
has the tail (~540-3500). `_merge_duplicate` picked the LONGER of the two, so
the fuller-but-late-starting view won and the description began mid-sentence.
(That is what made the prompt rule look like it had merely changed the failure
shape from `truncated` to `mismatch` while the metric stayed at 2/3.)

Because the two views come from an overlap, the shared span is in both, so
`a`'s tail IS `b`'s head and splicing there reconstructs the passage exactly —
no invented and no duplicated text. Containment is handled first; a shared run
of at least `_MIN_PROSE_OVERLAP` (60) chars is required so a common sentence
opener cannot fake an anchor; with no anchor it returns `None` and
`_merge_duplicate` falls back to longest-wins. It reads only string shape,
never any document's vocabulary. Verified on the real NV strings: the two
partial views splice back to the golden 3500 chars byte-exactly, in either
order, while two unrelated domain intros refuse to splice.

⚠️ **It fixes NV on its own in the BATCHED path, but looks inert in the eval —
know which path you are measuring.** This is the sharpest live example of the
direct-vs-batched divergence:

* **Direct path (`eval_detector`)** — NV Science stays `truncated: 2410/3500`,
  description accuracy 2/3. One chunk holds a single truncated view, so there
  is no second view to splice against and the helper is a no-op.
* **Batched path (the real pipeline)** — NV Science comes back at **3500 chars,
  byte-exact against the golden**, with NO prompt rule in play. Batched
  chunking hands `_merge_duplicate` the two overlapping partial views the
  splice is designed to join.

Isolated by a clean before/after on the pipeline itself: run `08-22-26` (037,
no splice, no prompt rule) → 2410; run `08-22-26-4` (040, splice, no prompt
rule) → 3500 exact. The splice is the only functional detector change between
them.

So do NOT judge this helper by the detector eval, and do not delete it because
`eval_detector` shows no movement — that is the expected direct-path reading of
a batched-path fix. It can only ever reconstruct more of a passage, never less,
and it removes an order-dependent way for `_merge_duplicate` to pick a
description that starts mid-sentence.

⚠️ `_merge_duplicate`'s longest-wins fallback is now only a FALLBACK. Its old
premise — "the chunk that saw the element whole captured more of its prose" —
holds for a plain repeat but not for a head/tail split, which is why the splice
runs first.

### Where a printed code is not unique (2026-08-15) — `_anchor_parent_chain` + `disambiguate_colliding_standards`

Both of these exist because a document's printed code namespace can **skip a
level**, and the parser previously assumed it never does.

**`_anchor_parent_chain`.** `_anchor_parent_code` forces each parent code to be
a prefix slice of the indicator's code — correct for documents that spell out
every ancestor, and the fix for the CA case where the LLM borrows a sibling
domain's prefix (`ELD.1.0.VOCA` under indicator `FLD.1.0.VOCA.1.1`). Nevada
breaks the assumption: it codes indicators `<domain>.<sub_strand>.PKn` and
gives the strand its own heading identifier ("Social Studies Standard 2") that
appears nowhere in the indicator code. Anchoring each level independently then
peeled the SAME prefix for two levels — NV's strand and sub_strand both became
`SS.CI` — so the strand's real identity was discarded and five distinct strands
collapsed onto three codes. This was **deterministic Python, not LLM variance**:
`SS.2` has depth 2 and indicator `SS.CI.PK3` has three segments, so the old
function returned `SS.CI` every time. NV could not have produced `SS.2` at all.

The rule is the one this file already documented for the parser prompt —
*peeling stops where the namespace stops* — and the tell is purely structural:
if a level's anchored code EQUALS the anchored code of the level directly below
it, the peel ran past the end of the namespace, and that level keeps the
identifier its own heading supplied. It reads only dot-segment shape, never any
document's vocabulary, and it is a no-op for AZ/CA/CO/KY/TX, where no two
levels ever peel to the same prefix. Measured effect on NV: `strand.code` 0/15
→ 12/15, field accuracy 0.933 → 0.978, with the four golden states unchanged.
Check any edit here against all five shapes — NV `SS.CI.PK3` → (`SS`, `SS.2`,
`SS.CI`), KY `AL.1.1.EASPT` → (`AL`, `AL.1`, `AL.1.1`), and the CA borrow
`FLD.1.0.VOCA.1.1` → (`FLD`, `FLD.1.0`, `FLD.1.0.VOCA`).

**A strand's code always extends its own domain's code (2026-08-22).** The
level held OUTSIDE the namespace keeps its heading identifier, and that
identifier is the LLM's rather than the document's — so its leading segment can
carry a stale domain code straight into the output. Nevada shows both spellings
of the one leak across two runs of the SAME document: `08-22-26` has 5 rows of
strand `TECH.1` under domain `T`, `08-22-26-2` has 6 rows of strand `Science.1`
under domain `S`. Do not read that as a Technology quirk or as an asymmetry
between "plausible" and "malformed" domain codes — the earlier hypothesis that
a malformed code is safe because the parser ignores it is REFUTED by run 2.
Either domain leaks, depending only on which way `_pick_code`'s frequency vote
falls, so the repair is keyed to neither spelling.

The invariant is measured, not assumed: **106/106** over every annotated
standard in all six parser goldens, and **508/508** over two full six-state
pipeline runs once NV's 11 leaked rows are excluded. So when the strand's
leading segment disagrees with the resolved domain, the domain wins and the
segment is replaced. Blast radius, measured by replaying every production row
through the new chain: **519 rows, 11 changed — exactly the 11 leaked NV rows,
zero in AZ/CA/CO/KY/TX.** Measured effect on NV: `strand.code` 19/24 → 24/24,
field accuracy 0.975 → 0.986 on `08-22-26` (its remaining miss is the Science
`domain.description`, a DETECTOR truncation frozen into that detection input),
and **1.000 / 24-of-24 fully correct** on `08-22-26-2`, whose detection carries
the description intact. `strand.code` appears in no state's mismatch list in
either run.

Two things in those runs are NOT attributable to this change, and both look
alarming at a glance. KY coverage 26/26 → 21/26 tracks its detection input
(44 → 38 elements from the pipeline's own detector), and KY's
`KY-BENCHMARK-CODE-NORMALIZED` / `KY-SUB-STRAND-NOT-INDICATOR-CODE` failures
are the documented bare-code defect (`TCPHS`/`UMNDW`, 2 and 4 rows, matching
the 08-01/08-16 rate) that `validator._validate_code_shape` rejects before
Aurora. AZ `indicator.description` 17/18 → 12/18 is description sampling. In
both cases the mismatched fields are never `strand.code`, and the replay
changed zero rows in either state.

⚠️ Two guards, both load-bearing — check any edit here against
`tests/unit/test_parser_domain_anchor.py::TestStrandExtendsDomain`:

1. It fires **only when the DOMAIN was successfully anchored**. If the domain
   is instead the level that fell outside the namespace, its code is the
   unreliable one, and re-rooting an anchored strand onto it would corrupt a
   correct code.
2. It **replaces** a leading segment, never **prepends** one, so it acts only
   on a strand code that already has a domain-code slot to correct. A
   single-segment strand identifier is left alone: prepending would invent a
   qualification the document never printed.

⚠️ It must stay **strand-vs-domain**. Widening it to sub_strand-vs-strand
rejects all of Nevada, whose `SS.ID` deliberately does not extend `SS.1` —
the same reason `validator._validate_code_shape` is scoped to the indicator
level. `test_nevada_sub_strand_may_still_break_the_chain` is the canary.

**`disambiguate_colliding_standards`.** Uniqueness used to be enforced inside
`parse_llm_response` by a numeric counter: the first row to arrive kept the
bare code and the second got `.2`. That is order-dependent, which is the wrong
property for a primary key — the same document could write two different Aurora
keys depending on chunk order. The resolver replaces it with an ancestor-first
rule applied after the merge: colliding rows are re-qualified with their own
parent's segments, and **every member of the set is rewritten, including the
first seen**, so the outcome does not depend on parse order. The counter
survives only as a logged last resort for rows no parent separates. It runs
after the merge because a collision can span chunks and because
`normalize_parsed_codes` can itself bring two rows onto one code.

⚠️ **This resolver has no confirmed live case.** It was written for an apparent
NV collision — two rows both coded `SS.CI.PK3` — that turned out not to be one
(see below). It fires on no golden state. Treat it as a hardening of a
previously order-dependent guard, not as a fix for an observed defect, and do
not cite NV as its motivating example.

**The NV `SS.CI.PK3` duplicate is a DETECTOR defect, not a collision
(2026-08-15).** The detector emits 25 NV indicators where the document has 24
distinct ones, and the parser collapsing them to 24 is CORRECT. The document
contains exactly ONE `SS.CI.PK3`. The extra element is the same indicator
emitted twice: its `source_text` is a truncated prefix of the real one
(`SS.CI.PK3. Recognize and resolve conflicts with`) and its title carries a
fabricated tail — "…with peers **with adult guidance**", a phrase that appears
ZERO times in the extraction. NV's page 5 is a multi-column table that flattens
into interleaved reading order, which is the likely trigger.

Two things follow. First, `_is_title_grounded` would have caught it — the title
is absent from its own `source_text` — but it is deliberately scoped to
domain/strand/sub_strand, exempting indicators because an age-band column
indicator legitimately carries the row's shared header as its title. Its
docstring's premise that "nothing invents a leaf out of its own code" holds,
but does not cover this shape: a leaf invented out of a TRUNCATED
transcription. Second, do not "fix" the parser's 25 → 24 collapse, and do not
add a count check that treats indicators-in ≠ standards-out as an error — the
collapse is the parser compensating correctly for bad detector input.

**When working in these two files, prefer in this order:**
1. **Improve the prompt** so the LLM handles the case as a general principle. A rule that helps every document (e.g. "a structural label like `Strand 1:` is the code, not the title") belongs as a prompt instruction, stated generally — not as a Python regex keyed to specific label words.
2. **Only fall back to Python** for things that are genuinely deterministic post-processing and document-agnostic (JSON extraction, schema validation, ID derivation from already-clean fields, true cross-chunk reconciliation). New per-state regexes/branches are a smell — flag them rather than adding them.
3. **Never loosen the eval matchers or edit goldens to paper over a generalization gap.** Fix the golden DATA and canonicalize the model output instead (see the golden-consistency note below).

**Test for generalization, not just the goldens.** A change that raises a golden score but relies on a document-specific rule is a regression in disguise. Validate against a held-out state (Nevada is the current canary; PDFs in `standards/nevada_standards_2023*.pdf` — note the **2023** document, 98pp full / 15pp `_only_subset`, which is what every NV golden and measurement uses. `standards/nevada_ses_standards_2025*.pdf` is an unrelated 36pp document with no golden; do not validate against it) before considering a detector/parser change done. The `evaluation-runner` skill auto-runs additional states for exactly this reason — use it.

## Two-language monorepo

The repo mixes two independently-managed toolchains. **Know which half you're in before running anything.**

- **Python** (`src/els_pipeline/`, `tests/`, `evaluation/`, `packages/agentcore-agent/`) — managed by `pyproject.toml`, run via `pytest` / `python -m`. Activate the venv first: `source venv/bin/activate` (a `.venv/` also exists; `venv/` is the one the README documents).
- **TypeScript** (`packages/*` except `agentcore-agent`, `infra/cdk/`) — pnpm workspace + Turborepo. Package names are `@els/*` (e.g. `@els/api`, `@els/shared`, `@els/frontend`). `@els/shared` holds the canonical TS types and is a dependency of every other JS package.

## Commands

```bash
# --- Python pipeline ---
source venv/bin/activate
pip install -e ".[dev]"
pytest tests/ -v                              # all
pytest tests/property/ -v                     # property-based (Hypothesis)
pytest tests/integration/ -v                  # moto-mocked AWS
pytest tests/unit/ -v
pytest tests/unit/test_detector.py::TestX::test_y -v   # a single test
pytest tests/ --cov=els_pipeline --cov-report=html

# --- TS monorepo (from repo root; Turbo handles build ordering) ---
pnpm install
pnpm build | pnpm lint | pnpm test | pnpm typecheck
pnpm --filter @els/api test                   # one package; tests use vitest
pnpm --filter @els/api dev                     # watch/dev a single package
```

Single TS test: `cd packages/els-explorer-api && pnpm vitest --run path/to/file.test.ts`. Note `pnpm test` depends on `build` (see [turbo.json](turbo.json)), so a broken build blocks tests.

## Evaluation harness (`evaluation/`)

This is the actively-iterated quality-measurement layer for the detector and parser — separate from `tests/`. Two **decoupled** golden sets graded by two suites:

- `evaluation/eval_detector.py` grades the detector against `ground_truth_detector/{STATE}.json` (flat element list, run on `{STATE}-extraction.json`).
- `evaluation/eval_parser.py` grades the parser against `ground_truth_parser/{STATE}.json` (nested `NormalizedStandard` objects, run on `{STATE}-detection.json`).

They produce different shapes from different inputs and are annotated/iterated independently — don't assume a change to one affects the other.

```bash
python -m evaluation.eval_detector --state CA
python -m evaluation.eval_detector --state CA --stability-runs 3   # LLM-determinism check
python -m evaluation.eval_parser --detection-dir outputs/05-31-26
```

`regression_cases` in each golden file map by `id` to a check function in `evaluation/regression_checks.py` — when adding a regression case, add the matching function or the suite logs `SKIP`. See [evaluation/README.md](evaluation/README.md) for annotation conventions.

**`evaluation/baselines/` is a deliberate exception to everything above, and it stays there (2026-08-23).** `rule_based.py` is a regex/heuristic structure extractor written as the arXiv paper's comparison baseline (Task 4) — it is the concrete form of the rule-driven approach this file forbids in `detector.py`/`parser.py`, kept precisely so the LLM lift can be measured rather than asserted. It is graded by the **same** suite: `evaluation.baselines.eval_baseline` injects it into `eval_detector.evaluate_state` through the optional `detect_fn` parameter, so there is no second grader and the two arms share `grade_elements`, `_match_key` and the goldens. It uses no Bedrock and is deterministic, so it has no cache; it has no Pass-1, so its depth map records ABLATED (`grade_depth_map_pass=False`) rather than FAIL. **Nothing in that package may migrate into `src/els_pipeline/`,** and it must never acquire a per-document branch — `tests/unit/test_baseline_rule_based.py::test_no_state_name_appears_in_the_source` enforces that, and it was developed against AZ/CA/CO/TX with NV/KY held out. Results, and the precision caveats that must travel with them, are in `paper/results/task4_20260823/findings.md`.

## Pipeline architecture (the non-obvious parts)

- **All Lambda entry points live in one file**, `src/els_pipeline/handlers.py` (`ingestion_handler`, `extraction_handler`, `detection_handler`, `parsing_handler`, `validation_handler`, `persistence_handler`, plus the batch prepare/process/merge handlers). The corresponding logic lives in sibling modules (`detector.py`, `parser.py`, etc.); handlers are thin S3-in/S3-out wrappers.
- **Detection and parsing are batched** via a three-step prepare → Step-Functions-Map (max 3 concurrent) → merge pattern (`detection_batching.py`, `parse_batching.py`) to dodge Lambda timeouts on large docs. Detection batches by text-block chunks (`MAX_CHUNKS_PER_BATCH=5`); parsing batches by domain (`MAX_DOMAINS_PER_BATCH=3`) to keep related elements together.
- **Stages communicate through S3, not direct payloads.** Each run writes intermediate JSON under `{country}/{state}/{year}/intermediate/...` keyed by `run_id` — read these when debugging a stage in isolation.
- **Standard IDs are deterministic:** `{country}-{state}-{year}-{indicator_code}` (e.g. `US-CA-2021-LLD.1.2`). The `indicator_code` is fully qualified and carries any disambiguator (age prefix / column suffix) itself — there is no separate `domain_code` component (see `generate_standard_id` in `parser.py`). Pydantic `models.py` is the Python source of truth for the schema; `packages/shared/src/types.ts` mirrors it for TS — **keep these two in sync** when changing the data model.
- Every detected element carries a `confidence` score but is never gated or dropped by it — all elements flow through to parsing and persistence, since every element is reviewed by a human downstream regardless of confidence.

## Infrastructure & deploy

Four independent CDK stacks (`infra/cdk/lib/{pipeline,app,planning,landing-site}-stack.ts`), each with a deploy script in `scripts/`. CDK selects a stack via the `targetStack` context var (`bin/app.ts`). Docker must be running (CDK bundles Lambdas). The Explorer/Planning deploys need `DESCOPE_PROJECT_ID` set (Descope handles auth).

```bash
./scripts/deploy_els_pipeline.sh -e dev
DESCOPE_PROJECT_ID=<id> ./scripts/deploy_els_app.sh -e dev
DESCOPE_PROJECT_ID=<id> ./scripts/deploy_planning_app.sh -e dev
./scripts/deploy_landing_site.sh -e dev
```

DB schema evolves via numbered files in `infra/migrations/` (Aurora PostgreSQL). The Planning agent (`packages/agentcore-agent/`) is a Python Strands agent deployed to Bedrock AgentCore — **user identity is bound from the authenticated session, never chosen by the LLM**; preserve that when touching its tools.

## Config

Bedrock model IDs, bucket names, and batch sizes are all env vars — see [.env.example](.env.example). Defaults of note: detector uses Claude Opus, the detection depth-map pass uses Claude Haiku, and the parser uses Claude Sonnet.

## Claude Code skills

Two project skills live at `~/.claude/skills/` and are invoked automatically by Claude Code:

- **`download-pipeline-outputs`** (`~/.claude/skills/download-pipeline-outputs/SKILL.md`) — downloads detection, extraction, and parsing JSON from S3 for the four golden states (AZ, CA, CO, TX) into a date-stamped `outputs/MM-DD-YY/` folder, plus the held-out states (NV, KY) when that run produced them — their year is discovered from S3 rather than hard-coded, and a state that's absent is skipped, not an error. Invoke with e.g. "download pipeline outputs for run 15". Uses AWS profile `kinder-readiness-dev-cli`; run IDs are zero-padded to 3 digits. Output files are named `<STATE>-<type>.json` (e.g. `AZ-detection.json`).
- **`evaluation-runner`** (`~/.claude/skills/evaluation-runner/SKILL.md`) — runs the detector and parser eval suites against a local outputs folder and suggests fixes for low-scoring components.

# AWS Guidance

- Prefer the AWS MCP Server for AWS interactions — it provides sandboxed
  execution, observability, and audit logging. If unavailable, use the
  AWS CLI directly.
- Before starting a task, check whether a relevant AWS skill is available.
  Load the skill with `retrieve_skill` and prefer its guidance over
  general knowledge.
- When uncertain about specific AWS details (API parameters, permissions,
  limits, error codes), verify against documentation rather than guessing.
  State uncertainty explicitly if you cannot confirm.
- When creating infrastructure, prefer infrastructure-as-code (AWS CDK or
  CloudFormation) over direct CLI commands.
- When working with infrastructure, follow AWS Well-Architected Framework
  principles.
- Do not use em dashes in AWS resource names or descriptions. Use
  hyphens instead.

## Secret Safety

- MUST load the `aws-secrets-manager` skill first for any secret,
  credential, API key, token, or password task. MUST NOT call
  `secretsmanager get-secret-value` or `batch-get-secret-value`, and MUST
  NOT hit the Secrets Manager Agent daemon directly. MUST use
  `{{resolve:secretsmanager:secret-id:SecretString:json-key}}` with
  `asm-exec` so the secret resolves at runtime without entering context.