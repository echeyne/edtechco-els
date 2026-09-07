# What is left before posting

Written 2026-09-07, after the scale evidence landed. Supersedes the open items
in `TODO_pre_arxiv.md`, which stays as the record of how each experiment was
decided. Ordered by what blocks a posting, not by effort.

---

## 1. 🔴 The paper is now 29 pages, and the target venue wants 6--8

`REVIEW_assessment.md` §2 already called the 17-page body too long for the
evidence it carried. Three subsections have been added since. This is now the
single biggest gap between the paper and an industry-track or AIED submission,
and no experiment will close it.

The cut is already specified in the assessment: keep §1 (one page), §2 (half),
§3 as a paragraph plus Table 1, §4 and §6 merged into three pages leading with
Pass-1 and the identifier scheme, §8.1/8.2/8.5/8.6/8.8 as results, one page of
limitations. Cut §5 entirely, §7 and both its figures to an appendix, §6.3's
walkthrough to a paragraph, §6.5 and §8.4 to one paragraph, §8.3 to half a page.

- [ ] Do the cut. **Keep the abstract's measurement-discipline sentences even if
  the contributions enumerate goes** --- that is what separates this from a
  prompt-engineering report in a reviewer's first thirty seconds.
- [ ] The new §8.8 survives the cut; §8.4 (whole-document arm) can compress to a
  paragraph, since it is deliberately not tabulated anyway.

## 2. 🟡 Decide whether a scale table is worth its space

§8.8 currently carries its numbers in prose. A table would be easier to scan and
would sit naturally beside Table 4, but the paper is over length and this is the
one new section that has to survive the cut.

- [ ] Decide. If yes, generate it from `paper/results/task13_20260907/` through
  `generate_tables.py` rather than hand-writing it --- the abstract now claims
  every number is regenerated from a recorded artifact.

## 3. 🟡 Regenerate the tables and re-check the cross-cutting figures

- [ ] Run `python paper/analysis/generate_tables.py` once more after the cut and
  confirm nothing moved.
- [ ] The "297 in-scope detections" audit figure appears in the abstract,
  contribution 4 and the conclusion. It is a subset-tier number and is
  unaffected by the trimmed-tier work --- confirm it still reads unambiguously
  now that a second, larger scale is discussed nearby.
- [ ] `corpus_tiers.json` says "no table anywhere in this paper may present
  [subset numbers] as full-document numbers". §8.8 now legitimately reports
  trimmed-tier quality; the note needs that exception written in, or the next
  reader reads it as a violation.

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

## 7. 🟢 Housekeeping before posting

- [ ] Strip the drafting comment blocks from `paper/sections/*.tex` --- several
  are long and several are now stale (the one in §8.7 has already been corrected
  once for saying quality at scale was not measured).
- [ ] Add a dated note at the top of `REVIEW_assessment.md` saying its §4
  experiments are done, so it does not read as outstanding work.
- [ ] Merge the working branch:
  `git merge --ff-only paper/scale-evidence-and-trimmed-goldens`

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
