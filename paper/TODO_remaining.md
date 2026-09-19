# What is left before posting

Written 2026-09-07, after the scale evidence landed. Supersedes the open items
in `TODO_pre_arxiv.md`, which stays as the record of how each experiment was
decided. Ordered by what blocks a posting, not by effort.

---

## 1. ✅ Length — reduced 2026-09-07, deliberately not to 8 pages

29 pages → **28**; the **body** 22 pages → **19.5** (§1 starts p.1, the
artifacts statement ends p.20, references p.20--21, appendices p.22--28).

Decision on the record: the assessment's 6--8 page cut was **not** taken. It
was written for an industry-track submission, and cutting §5, §7, both figures,
Table 6 and half of §8.3 to reach it would remove evidence this paper is
carrying deliberately. What was done instead is the structural half of that
cut, which costs no evidence:

- [x] **§5 Pipeline Overview deleted**, its six-stage description folded into
  the head of §6 Method (now §5). It duplicated §6.1 and §4.
- [x] **§7 System Architecture moved to Appendix E**, with both full-width
  figures. A new §5.6 *Deployment* keeps in the body the two things the body
  actually needs from it: the prepare--map--merge pattern, and the
  direct-vs-batched divergence disclosure.
- [x] **Table 8 (batched scale) converted from `table*` to a single column**,
  with input and output tokens split into two blocks so it fits. Every number
  is unchanged --- verified by diffing the numeric multiset before and after.
- [x] Prose compressions where §8 and §9 said the same thing twice: §8.4
  (whole-document arm), §8.5 (confidence, 775 → 413 words), §8.3's precision
  cautions, §9.1, and §9.4 --- which had re-told §8.6's non-reproduction at
  full length and is now a pointer to it. §6.5's deployment essay and §10's
  future work also trimmed.
- [x] The abstract's measurement-discipline sentences are **untouched**, as
  this file required.
- [x] Fixed while in there: `and I are explicit` → `and I am explicit`
  (§9.2).

Two more of that list were taken 2026-09-07 on a second pass:

- [x] **Table 6 (confidence distribution) moved to Appendix D.** It was the
  least load-bearing table in the results: the confidence finding is *negative*
  --- the distribution is too degenerate to threshold on --- so the table's job
  is to let a reader check the claim, not to carry it. §6.5's prose is
  unchanged and now points at it. Body tables are 1--8; it is Table 9.
- [x] **§2 Related Work compressed**, 1.1 pages → **0.78**. Two passes: prose
  tightened, then the interleaved citation clusters grouped into single
  `\citep{}` calls, which is where most of the space was --- author-year
  citations cost ~5 words each and §2 carries 34 of them.
  ⚠️ **It did not reach the half page asked for, and cannot without dropping
  references.** What remains is roughly 45% citation by area. The next 0.28
  pages has to come out of the reference list, not the prose; the cheapest
  candidates are the twelve background works in the first paragraph's two
  grouped clusters, which are lineage rather than comparison.

Still not done, available if the paper is later cut for a venue: §6.3's
repair-by-repair walkthrough, §8.3 to half a page.

## 2. ✅ Scale table — generated 2026-09-07

**Table 9**, `paper/tables/scale_quality.tex`, from
`build_scale_quality_table()` in `generate_tables.py` reading
`paper/results/task13_20260907/ky_trimmed_3runs.json` --- generated, not
hand-written, per the abstract's claim. Twelve rows over the three runs with an
sd column, split detector/parser. §8.8's prose was rewritten around it and lost
the numbers the table now carries.

Three judgement calls worth knowing:

- **Per-run columns, sd as the only summary.** A mean$\pm$sd column overfull
  the ACL column by 80pt, and coverage (0.807 / 0.927 / 0.841) must not be
  reduced to a point value anyway --- the range is the finding.
- **The collision row carries its caveat in its own label** (`Collisions†`,
  with the footnote in the caption). A row reading `0 0 0` anywhere else reads
  as a clean result, and it is zero by construction.
- Width is tight: `\small` with `\tabcolsep` at 4pt and abbreviated labels.
  Check `main.log` for an Overfull \hbox naming `tables/scale_quality.tex`
  after any edit to a row label.

## 3. 🟡 Regenerate the tables and re-check the cross-cutting figures

- [x] Run `python paper/analysis/generate_tables.py` once more after the cut.
  Two tables **did** move, both by design and neither by a change of number:
  `scale_quality.tex` is new (item 2), and `scale_batched.tex` was restructured
  to fit one column (item 1). Every other table regenerates byte-identically,
  and `scale_batched`'s numeric multiset is unchanged.
- [x] Re-ran 2026-09-07 after the second pass: **every table regenerates
  byte-identically**, including the two that had moved.
- [x] The "297 in-scope detections" figure --- and it did **not** read
  unambiguously. 297 (subset, six states) now sits two paragraphs from 277
  (Kentucky, trimmed) in the conclusion, at a confusable magnitude. All four
  occurrences are now tier-qualified at the point of use rather than relying on
  a blanket sentence elsewhere.
- [x] ⚠️ **The same check found a claim that had become false**, which is the
  more important half. The abstract said *"All quality figures are computed on
  an annotated subset tier"* and §1's scope paragraph said cost and scale
  figures at the trimmed tier "are never mixed with the quality tables" ---
  both written before §6.8 began reporting **quality** at the trimmed tier.
  Both rewritten: the headline tables are subset-tier, one whole-document arm
  is reported at its own larger tier, and the two never share a table.
- [x] `corpus_tiers.json` exception written in, on `notes[4]` and on
  `tier_definitions.only_subset` (which claimed to be "the tier every quality
  table uses"). The exception states the rule positively: guardrail 1 forbids
  mislabelling a tier, not grading at one.

## 3b. ✅ Caption source pointers shortened — 2026-09-07

A caption's `Source:` now names the **recording**, not a path:
`task8_20260904`, not `paper/results/task8_20260904/`. Thirteen of them (11
captions, 2 in §6.4/§6.8 prose).

The reasoning, since it is a claim about the paper's own provenance discipline:
nothing here is released and the Artifacts Statement says so outright, so the
directory prefix was thirteen repetitions of a path no reader can resolve. The
**tag** is the part that does work — it identifies which freeze produced the
number, which is exactly what `SUPERSEDED_TAGS` in `generate_tables.py` exists
to keep honest, and several measurements have been re-recorded as
`code_version_hash` moved. The Artifacts Statement now explains the scheme once
and states that the recordings are retained and available on request.

⚠️ The LaTeX **comment** provenance that `header()` emits still carries the full
`paper/results/...` path, deliberately — that one is read by someone standing in
the repo and should stay resolvable. Only the visible caption changed.

## 4. 🟢 Optional experiment: California ×3 on the whole-document arm

Three calls, roughly \$1, eight minutes, no harness change needed. It settles
whether the output-cap truncation is deterministic at that document size or a
coin flip --- "3 of 3" is a materially stronger sentence than one draw, and
Arizona landing within 11\% of the same ceiling makes it more interesting than
it sounds.

Not required. The California claim is architectural rather than statistical and
the mechanism is identified (output length equals the configured cap exactly),
which is why §8.4 reports it with more confidence than the rest of that arm.

## 5. 🟢 Optional measurement: the cold read

Read a random sample of Kentucky's trimmed pages without reference to the
golden, list every element present, and diff. It is the only route to a genuine
recall claim at scale --- the trimmed goldens were verified by inspecting what
the system emitted, which cannot find omissions.

Deferred by decision. If it stays deferred, §8.8 and §9 already state the
ceiling wherever the recall figure appears; nothing further is required.

## 6. 🟢 Known trap, no number affected

`eval_detector.measure_stability` calls `run_detector_cached` directly and
ignores an injected `detect_fn`, so `--stability-runs N` on the rule-based
baseline or the whole-document arm would silently measure the chunked detector
instead --- and cost roughly six times more while doing it. No recorded number
is affected, because that combination has never been run.

- [ ] Add the warning to its docstring now (two minutes); fix it properly
  whenever the harness is next opened.

## 7. ✅ Housekeeping — done 2026-09-07

- [x] **All 344 comment lines stripped from `paper/sections/*.tex`**, and
  archived to `paper/DRAFTING_NOTES.md` rather than deleted --- a few carried
  warnings nothing else records (the guardrail-6 note on which three method
  numbers are *not* regenerable from `paper/results/`; the guardrail-1 warning
  that the scale run's own `run_id` says `full08292026` and that name is
  wrong). The stale §8.7 brief is gone with the rest.
- [x] `main.tex`'s three `TODO(Task 11/12)` markers cleared --- all four
  appendices have been populated since commit `2d23f44` --- and its
  section-order note rewritten, since it described a 12-section body that no
  longer exists.
- [x] Dated status note added at the top of `REVIEW_assessment.md`: its §4
  experiments are all done, and its §2 length verdict was acted on in part.
- [x] Merge the working branch:
  `git merge --ff-only paper/scale-evidence-and-trimmed-goldens`
- [x] **§5.7's provenance footnote fixed** (2026-09-07). It was not an overfull
  box --- LaTeX reported none --- but an *underfull* one: the `\allowbreak`s in
  the two long `\texttt` paths let it break, and justification then stretched
  three lines into gaping word gaps. `\raggedright` inside the footnote fixes
  it with the paths intact. Worth remembering that a badly-set line does not
  have to trip a warning to look broken.

---

## What is explicitly NOT on this list, and why

- **Fixing the `age_band` defect.** It changes a prompt, moves
  `code_version_hash`, and invalidates every frozen measurement in the paper.
  §9.5 reports it and states that reasoning. Fix it after posting.
- **Annotating Colorado exhaustively.** Declined 2026-09-06. CO contributes
  recall and duplication evidence only, and §9 says so.
- **A second annotator, a second frontier model, an off-the-shelf converter
  baseline.** All three are main-track expectations. `REVIEW_assessment.md` is
  explicit that an industry track or AIED does not require them, and that is the
  chosen target.
