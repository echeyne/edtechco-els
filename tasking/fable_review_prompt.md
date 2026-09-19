# Review brief, pass 2: arXiv paper, ELS Platform

You are doing the **second** review of an academic paper by a solo author who
intends to post it to arXiv (cs.CL primary, cs.AI cross-list). Work in the repo
at `/Users/emilycheyne/Development/kinder-readiness`. The paper is in `paper/`,
entry point `paper/main.tex`, currently **28 pages**: ~19.5pp body, ~2pp
references (40 entries), ~6pp appendices (A prompts, B schema, C goldens,
D confidence table, E corpus, F system architecture).

⚠️ **Section numbers moved in the length cut.** The current body is §1 Intro,
§2 Related Work, §3 Corpus, §4 Schema, §5 Method (§5.6 Deployment, §5.7
LLM-first discipline), §6 Experiments (§6.4 whole-document arm, §6.5
confidence, §6.6 stability, §6.7 scale, §6.8 quality at scale), §7 Discussion
and Limitations (§7.5 the `age_band` defect), §8 Conclusion. The TODO files,
`DRAFTING_NOTES.md` and pass 1's reviews often use the **pre-cut** numbering
(for example "§8.8" for today's §6.8). Map by `\label`, not by number.

**The goal of this pass is narrow: is the paper good enough to post to arXiv
now, and if not, exactly what stops it?** It is not to redesign the paper,
retarget it at a venue, or add experiments. A first review ran on 2026-09-04;
since then the paper changed a lot (new evidence, a length cut, restructured
sections). Your job is to check that the new material holds up to the same
standard, and that the fixes from pass 1 survived the rewrite.

Read these first, in this order, before touching anything:

1. `tasking/arxiv_paper.md` — the working plan. Its **"non-negotiable
   guardrails"** section is the standard this paper must be held to. Every one
   exists because a specific false claim nearly reached the page.
2. `paper/TODO_remaining.md` — what was done after pass 1 and why, including
   the decisions listed under "Decided — do not relitigate" below.
3. The pass-1 deliverables at the repo root: `REVIEW_references.md`,
   `REVIEW_claims.md`, `REVIEW_assessment.md` (the last has a 2026-09-07 status
   note at the top). **Do not overwrite these**; they are the record.
4. `CLAUDE.md` — the system's design constraints and a long record of measured
   defects. Most of the paper's claims trace back to a section in here.
5. `paper/DRAFTING_NOTES.md` — every LaTeX comment that used to live in
   `paper/sections/*.tex`, archived when they were stripped on 2026-09-07. It
   records why each section says what it says and which readings were
   rejected. Read the note for a section before changing that section.
6. `paper/results/*/findings.md` and `manifest.json` — the recorded
   measurements. **Every number in the paper is supposed to be regenerable from
   these.**

Build (a local TeX Live is installed now; Docker is no longer needed):

```
cd paper && latexmk -pdf -interaction=nonstopmode main.tex
```

Baseline before your changes (2026-09-19): **exit 0, 28 pages, 0 undefined
references or citations, 0 overfull boxes, 27 underfull boxes, and one
pre-existing font warning** (`T1/zi4/m/it` undefined — inconsolata has no
italic). If your edits add an overfull box, fix it. Underfull boxes are
cosmetic, but look at any in text you touched.

---

## What changed since pass 1 (focus here)

Pass 1 checked the paper as it stood on 2026-09-04. Everything below is newer
and has **not** had an independent review:

- **Quality at scale, §6.8 and Table 9** (`tables/scale_quality.tex`): Kentucky
  graded at the `_trimmed` tier against two new trimmed-tier goldens (277
  elements / 207 standards), three runs, with parser coverage reported as a
  range (0.807 / 0.927 / 0.841). Recordings: `results/task9_20260905/`,
  `results/task13_20260907/`. ⚠️ Those goldens were verified by inspecting what
  the system emitted, so they **cannot find omissions**: any recall claim at
  that tier must say so.
- **The whole-document single-prompt arm, §6.4.** `results/task10_20260905/`.
  California is truncated at the configured output cap; that claim rests on one
  draw.
- **The Nevada non-reproduction.** An earlier result claiming the
  layout-stratified sampler fixed NV's domain codes was re-run at n=5 per arm
  and did not reproduce (`results/task11_20260905/`; the old
  `results/task2_20260826/nv_attribution_ab.json` is superseded). The paper
  reports it as a non-reproduction. CLAUDE.md's "Where Pass-1 loses a LEVEL"
  section has the per-draw table.
- **The `age_band` defect at scale, §7.5.** Kentucky's page banner leaks into
  `age_band`, duplicates survive `_dedup_elements`, and the collision resolver
  gives them fabricated `.N` primary keys. It is reported and deliberately
  **not** fixed, because the fix would change `code_version_hash` and invalidate
  every frozen measurement. Colorado is the control. See CLAUDE.md, "Where
  `age_band` destabilizes at scale".
- **The length cut.** The old §5 Pipeline Overview was folded into §Method; the
  old §7 System Architecture moved to Appendix F, with a short §5.6 Deployment
  left in the body; the confidence table moved to Appendix D; §Related Work and
  several results subsections were compressed. **Check that no argument lost
  its evidence in the cut**, that forward and backward references still point
  at the right thing, and that nothing now says "above" or "below" about
  material that moved.
- **Captions** now cite a recording by its tag (`task8_20260904`), not by path.
  The Artifacts Statement explains the scheme.
- **The abstract was shortened on 2026-09-19** to fit arXiv's 1,920-character
  abstract field. `paper/arxiv_abstract.txt` is the plain-text copy for the
  submission form (1,888 characters). Confirm it matches the LaTeX abstract word
  for word apart from dashes and the dropped `\S\ref`, that it is still under
  1,920 characters, and that every number in it is correct. The cut removed the
  closing sentence about corpus tiers and moved the tier into the results
  sentence ("On an annotated subset of…"). Check that is still honest, given
  that §6.8 reports quality at a second tier.

---

## Task 1 — References: delta check only

Pass 1 verified all entries (`REVIEW_references.md`). Since then the list grew
from 36 to 40 and §Related Work was compressed, with citations regrouped into
single `\citep{}` clusters.

- Verify **every entry pass 1 did not cover**: existence, correct title,
  authors, year and venue, against an authoritative source. Say "unverified"
  rather than assuming.
- For **every** citation, re-check the claim it supports in the compressed
  text. Regrouping into clusters is exactly how a paper ends up cited for a
  claim it does not make: a cluster supports its whole sentence, so every
  member must.
- Flag any citation made redundant by the cut, and any work cited only in the
  bibliography.
- Do not re-run pass 1's literature search. If you know of a paper that
  defeats the gap claim (prior hierarchical-document work needs layout
  supervision and typographically consistent corpora; education-standards work
  presupposes already-structured standards), that is still the most valuable
  thing you can report.

---

## Task 2 — Validate the claims

This is the highest-value task. **Do not take a number in the prose at face
value; trace it to the artifact that produced it.**

- Tables in `paper/tables/*.tex` are **generated** by
  `paper/analysis/generate_tables.py` from `paper/results/`. Appendices A and C
  come from `make_prompt_appendix.py` and `make_goldens_appendix.py`. Re-run all
  three and confirm every table regenerates byte-identically. If one moves, the
  paper and its recordings have drifted: say which, and why.
- `SUPERSEDED_TAGS` in `generate_tables.py` lists recordings that must never
  feed a table. Check that no **prose** number comes from a superseded
  recording either. The generator cannot police prose.
- For each prose claim, find the recording and check the field yourself.
  Prioritize the sections listed under "What changed since pass 1".
- Re-check pass 1's corrections still hold after the rewrite: **297** in-scope
  detections, not 296 (and tier-qualified wherever it appears, since 277, the
  Kentucky trimmed count, now sits nearby); the depth-map cost share is 0.3% KY
  / 0.5% CO; NV chain-break is 24/24. `REVIEW_claims.md` lists the rest.

### Traps that have already caught someone

- **`per_level` in the detector reports holds `{tp, fp, fn}` counts, not a
  recall float.** A check that filters for numeric recall values silently
  compares nothing and reports success. Compute `tp/(tp+fn)`.
- **`main.log` is ISO-8859**, so plain `grep` treats it as binary and prints
  nothing. Use `grep -a`. A warning count of "0" from a plain grep means
  nothing.
- **A clean LaTeX exit does not mean a float rendered correctly.** Rasterize
  the page (`gs -sDEVICE=png16m -r110 -dFirstPage=N -dLastPage=N -o p.png
  main.pdf`) and look. Table 8 and Table 9 were both restructured to fit one
  column, so look at those pages specifically.
- **Superseded freezes.** `outputs/08-22-26-4/` and any
  `paper/results/*_20260822/` or `*_20260816/` recording are superseded unless
  the prose explicitly says it is reporting a historical value (the Task 3
  ablation repeats are the one disclosed case). A number carried from a
  superseded folder has reached this draft before (an Arizona figure that was
  wrong by a factor of five).
- **A duplicate check must be keyed more loosely than the merge it audits.**
  `grade_parser.id_collisions` reports zero on Kentucky's trimmed run because
  it runs *after* the collision resolver renamed the duplicates. If the paper
  anywhere reads "no collisions" as "no duplicates", it is wrong.
- **A zero at small n is not a null result.** Any claim that something "never"
  happens must state its denominator.

### Guardrails to re-check across the whole paper

- **Guardrail 1: corpus tier on every table and headline number.** Quality
  numbers are `_only_subset` except §6.8 and Table 9, which are `_trimmed`. No
  table may mix tiers, and no reader should be able to carry a number across
  them.
- **Guardrail 2: confidence gates nothing.** There is no `needs_review` field
  in `src/`. Grep the whole paper, appendices included, for any sentence
  implying a confidence-based review gate.
- **Guardrail 6: every number is regenerable.** Pass 1 found three §Method
  numbers that were not; they were made qualitative (see the guardrail-6 note
  in `DRAFTING_NOTES.md`). Check they have not crept back in as figures, and
  look for any **new** unregenerable number the post-pass-1 material
  introduced.
- **Guardrail 8: raw precision is not detector quality** except for Kentucky,
  whose golden is detection-exhaustive.
- **The `_trimmed` tier keeps 100% of the standards.** A trimmed-to-published
  page ratio is not a coverage fraction.
- **The NV 46/46 result must never appear as a stable result.** At n=5 it is
  44/46 or 44/45 per draw, and `NV-DOM-03` fails in every draw of both arms.
- **The `.N` suffixes are not a resolver defect.** They come from upstream
  duplicates the resolver correctly separated.

Report claims you could not verify **separately** from claims you found wrong.
"I could not confirm this" is a useful finding; guessing is not.

---

## Task 3 — Edit the paper

Spelling, grammar, clarity, consistency of terminology and notation, and above
all the **seams left by the length cut**: section and table numbering, stale
cross-references, a term defined in a section that moved to an appendix but
still used in the body, and the same thing said twice in §Experiments and
§Discussion.

Constraints:

- **Never hand-edit `paper/tables/*.tex`.** They are generated. Edit the
  generator in `paper/analysis/` and re-run it.
- **Never edit anything under `paper/results/`.** Those are recorded
  measurements with provenance: evidence, not prose.
- **Do not add LaTeX comments to `paper/sections/*.tex`.** They were stripped
  deliberately for submission. If an edit needs its reasoning recorded, add it
  to `paper/DRAFTING_NOTES.md` under that section's heading.
- **Keep every hedge.** Where the paper says "suggested rather than
  established", reports a range rather than a point value, or reports a
  non-reproduction, that wording was chosen after a measurement contradicted a
  stronger claim. Tightening it into a cleaner assertion would reintroduce the
  error.
- **Keep the abstract under 1,920 characters.** If you edit it, update
  `paper/arxiv_abstract.txt` to match and report the new length.
- **Do not change the byline.** "Founder, EdTech Co." with `emily@edtechco.org`
  is confirmed.
- Keep the build clean. Re-run it after editing and report the numbers against
  the baseline above.

---

## Task 4 — arXiv submission readiness

arXiv compiles from source, so check the package as arXiv will see it:

- Copy only what a submission needs into an empty directory: `main.tex`,
  `sections/`, `tables/`, `figures/`, `acl.sty`, `acl_natbib.bst`, the
  pre-built `main.bbl`, and `anc/prompts.txt`. Compile there with `pdflatex`
  only (no `bibtex`, which is how arXiv handles a supplied `.bbl`). Report any
  missing file, absolute path, or dependency on something outside that set.
- Flag anything in that set that should not be published: stray TODOs, author
  notes, internal paths, AWS account or resource identifiers, or unreleased
  data beyond what the Artifacts Statement says is disclosed.
- Check that `figures/` holds nothing unused, and that no file is too large for
  arXiv.
- Check that metadata is consistent across the title, abstract, byline and
  Artifacts Statement.

---

## Task 5 — Your honest assessment

Answer these, and be genuinely critical. The author would rather hear that this
is not ready than post something weak under their own name. Flattery here does
them a disservice.

1. **Is it ready to post to arXiv?** Answer yes, or no. If no, list the
   **blockers**, meaning things that would embarrass the author or constitute
   a false claim, separately from **improvements**. The bar is a careful,
   honest arXiv preprint, not a main-track acceptance.
2. **Did the new evidence strengthen the paper or dilute it?** Judge §6.4,
   §6.8, the NV non-reproduction and the `age_band` disclosure specifically.
   Does the reporting-discipline contribution, now claimed in the abstract,
   read as a contribution or as defensiveness?
3. **What would a hostile reader attack first**, now that the paper states its
   own defects so openly? Is any limitation stated in a way that undercuts the
   central claim more than the data does?
4. **Is anything still over-claimed?** Especially the abstract, which was just
   compressed, and the conclusion.

Keep your answer to question 1 short and put it first.

### Decided — do not relitigate

These were decided by the author with the trade-offs in view. Note a concern in
one line if you must, but do not argue for reversing them:

- **Length.** The paper is deliberately not cut to 8 pages. The structural cuts
  were taken; the evidence was kept.
- **Venue.** Pass 1's venue and outreach advice stands (`REVIEW_assessment.md`
  §2–3). This pass is about arXiv readiness only.
- **Artifacts.** Code and corpus are not released. The source documents are
  third-party state-agency publications, and in-paper disclosure through the
  appendices stands in for release.
- **The `age_band` fix** waits until after posting (it would invalidate every
  frozen measurement).
- **No exhaustive Colorado annotation, no second annotator, no second frontier
  model, no off-the-shelf converter baseline.**
- **License:** the arXiv perpetual non-exclusive license.
- **EduTeach 2026 is not being pursued.** Do not suggest it.

Optional items the author may still do before posting, which you may comment on
but should not run: California ×3 on the whole-document arm (TODO item 4), and a
cold-read recall check on Kentucky's trimmed tier (TODO item 5).

---

## Deliverables

Write new files; do not overwrite pass 1's.

1. `REVIEW_references_pass2.md` — verdicts on entries new since pass 1, plus
   every citation-claim mismatch found in the compressed text.
2. `REVIEW_claims_pass2.md` — three sections: claims verified, claims that are
   wrong (with the correct value and its source), and claims you could not
   verify. Also include the table-regeneration result, and whether pass 1's
   corrections held.
3. Edits applied directly to `paper/sections/*.tex`, `paper/main.tex` and the
   generators, with a summary of what changed and a final build report against
   the baseline.
4. `REVIEW_submission_pass2.md` — the Task 4 package check.
5. `REVIEW_assessment_pass2.md` — your answers to Task 5, with the verdict on
   readiness first.

Do not commit anything. Leave changes in the working tree for review.
