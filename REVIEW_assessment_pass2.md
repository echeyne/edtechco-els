# Assessment, pass 2: is it ready to post?

Written 2026-09-19 after the reference, claim and package checks
(`REVIEW_references_pass2.md`, `REVIEW_claims_pass2.md`,
`REVIEW_submission_pass2.md`) and the edits described there. Pass 1's
assessment (`REVIEW_assessment.md`) stands as the record; this file answers the
five questions of the pass-2 brief and nothing else.

## 1. Ready to post?

**Yes, with the edits from this pass applied.** Nothing in the current tree
would embarrass the author or constitutes a false claim. Six things would have,
and all six were found and fixed in this pass:

| Would have been a blocker | Status |
|---|---|
| "the same 164 elements every time" (\S6.8, \S7.5): false as an identity claim; run 2 differs from runs 1 and 3 on five elements | corrected to the count plus "159 common to all three" |
| "Every quality number in this paper is computed at the subset tier" in \S3, \S7.2 and two captions, contradicted by \S6.8 | corrected to "headline", with the exception named |
| Related Work citing HiPS for a premise it does not hold, and Liu et al. 2022 for the sentence it argues against | regrouped |
| "17 of 17" Benchmark identifiers (\S7.3): it is 18 of 18 | corrected |
| "fifteen appear, ten distinctive, five shared" (\S5.7): the artifact says fifteen distinctive and one shared | corrected |
| Prose cost shares disagreeing with the computed caption | corrected |

Improvements that are not blockers, in the order I would take them:

1. **The abstract's "collision-free identifiers"** was true at the subset
   tier and true by construction at scale, where the paper itself says the
   zero is not informative. At the author's request it now reads
   "deterministic identifiers", and contribution 2 reads "deterministic
   identifiers whose collisions are measured rather than assumed". See
   question 4.
2. TODO item 4 (California ×3 on the whole-document arm). Cheap, and "3 of 3"
   is a much stronger sentence than one draw for the one result in \S6.4 that
   the paper reports with confidence.
3. `CLAUDE.md`'s `age_band` section and `task13_20260907/findings.md` carried
   the "same elements every time" claim that this pass refuted from the raw
   runs. Both now carry a dated correction (159 of 164 common to all three
   runs), applied at the author's request.
4. `TODO_remaining.md` still calls the scale-quality table "Table 9"; it is
   Table 8 since the confidence table moved to the appendix. Internal only.
5. The goldens appendix's long `\paragraph` headings justify across the column
   and look stretched (page 25). Cosmetic; `\raggedright` inside the heading
   would fix it.
6. `figures/fig_architecture.png` is unused and should not go in the tarball.

## 2. Did the new evidence strengthen or dilute the paper?

**Strengthened, on balance, and \S6.8 is the single most valuable addition
since pass 1.** Pass 1 named quality at scale as the measurement the paper
most conspicuously lacked. It now has it, at three runs, against goldens
verified against the published PDF rather than against the run being graded,
with the recall ceiling stated every time the number appears. The result
(277 of 277, no hallucination, three times) is the strongest sentence in the
paper and it is earned.

\S6.4 does what pass 1 asked: it answers "why not just prompt it" with a
measurement, and it does so honestly, conceding that the simple approach
matches on two of six states at this tier. The California truncation is the
result that will stick with a reader, and its mechanism is identified rather
than inferred. Its weakness is that it is one draw per state, which the paper
says, and which TODO item 4 would partly close.

The Nevada non-reproduction and the `age_band` disclosure are where the
strengthening could tip into dilution, and I think they stay on the right
side. The non-reproduction is short, it retires a claim of the author's own,
and it leaves a quantified rate in place of a cause. The `age_band` section is
longer than it needs to be, but its reasoning (the fix moves the hash, the hash
keys every measurement, the defect touches no subset-tier number) is sound
and a reader can weigh it.

**The reporting discipline as a contribution** reads as a contribution in the
abstract, where it is one sentence, and as slightly defensive in \S1's
contribution 5, which is the longest item in the list. I would not cut it: the
paper delivers on every clause, and the tier-qualification error this pass
found in \S3 and \S7.2 is exactly the kind of thing the discipline exists to
catch. But a reader who wanted to call it defensive would point at
contribution 5, not at the abstract.

## 3. What a hostile reader attacks first

In order:

1. **Ten to eleven fabricated primary keys reach persistence in production,
   and the author has chosen not to fix it.** This is the sharpest line the
   paper hands a reader, and \S7.5 states it in almost those words. The
   defense is real (subset-tier numbers untouched, effect bounded and
   reproducible, fix known) but the optics are that the paper's evidence base
   was prioritized over the product's correctness. The paper should keep the
   disclosure; it should not add to it.
2. **"Recall 1.000" in the abstract against strict recall 0.59 at scale.** The
   abstract's "On an annotated subset" qualifier is doing a lot of work, and a
   skim reader will not see the qualifier. \S6.8 explains the 0.59 as a
   matching-key artifact of one field, and the level-and-title recall is
   1.000, so the paper survives the attack; it just has to be read.
3. **The reference set was seeded from the system's own output.** The paper
   says this at every site, and \S7.3 bounds the gap at the middle levels
   (18 of 18, 15 of 15) while admitting the 202 indicators carry no such
   check. A hostile reader will call the 277/277 result agreement with an
   earlier run rather than recall. The cold read (TODO item 5) is the only
   answer; the honest framing in place is the next best thing.
4. **Single annotator, no agreement statistic.** Unchanged since pass 1 and
   decided.
5. **The whole-document arm matching on Arizona and Nevada.** The paper
   concedes it; a reader will ask why the architecture is needed at all for
   documents that fit. The answer (California, and the trimmed tier) is in
   the same subsection.

**Is any limitation stated so as to undercut the central claim more than the
data does?** One came close and was changed: the \S6.8 paragraph heading
"Detection is complete at scale" outran the ceiling stated two paragraphs
later; it now says "recovers the whole reference set". Otherwise no. The
limitations are stated precisely, and precision cuts both ways: \S7.5's "I
know the cause, I know the fix, and I have not applied it" is blunt, but it is
also exactly what a reader needs to weigh the deferral, and softening it
would read as evasion.

## 4. Is anything still over-claimed?

**The abstract.** Two phrases, neither false:

- "deterministic, collision-free identifiers". True at the subset tier
  (Tables 1 and 3, 262 standards, 0 collisions) and true by construction at
  scale, where the paper itself says the zero is uninformative because the
  resolver renames every collision and 10--11 renamed keys reach persistence.
  A hostile reader would have quoted \S6.8 against the abstract. Now
  "deterministic identifiers" in the abstract and "deterministic identifiers
  whose collisions are measured rather than assumed" in contribution 2.
- "a serverless batching architecture applies it to whole documents". Whole
  standards content, at the trimmed tier, on two documents of 52 and 41 pages.
  \S7.2 qualifies this fully; the abstract does not have room to. Acceptable.

**The conclusion.** "no identifier collisions" is scoped to the subset tier in
the same sentence and is fine. "Quality at full-document scale ... is now
reported" is fine because the next sentence states the ceiling. Nothing else
in the conclusion goes beyond the results.

**Elsewhere.** \S7.1 "The central claim survives its strongest available test"
is a fair reading of six states at recall 1.000 with the two comparisons
attached. \S6.6's "four of six states reproduce perfectly" is bounded by the
lower-bound sentence that follows it. I found no claim that the data does not
support once the corrections in this pass are in.

## Decided items

Not relitigated. One line each where the brief allows it:

- Length: 28 pages is long for arXiv but not unusual for a systems paper with
  its appendices; nothing here depends on it.
- `age_band` fix deferred: sound, and the paper's own defense of it is
  adequate.
- No CO annotation, second annotator, second model, converter baseline: the
  paper names each as a limit.
