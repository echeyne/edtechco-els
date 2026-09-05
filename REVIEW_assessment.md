# Assessment — is this ready, where should it go, who wants it, what next

Written 2026-09-04 after the reference and claim reviews
(`REVIEW_references.md`, `REVIEW_claims.md`) and the edits described there.
This is a researcher's judgement of the paper, its venues and its audience.
It is not legal advice and does not assess any petition.

---

## 1. Is this a good paper?

**Short answer: it is a good applied-systems paper with a modest
methodological idea and unusually honest measurement. It is not a
strong-novelty NLP paper, and it should not be pitched as one.**

### The contribution, judged as a contribution

The central claim, that a document's hierarchy should be recovered by
classifying each element's nesting *position* against a per-document depth
map rather than by recognizing label vocabulary, is a sound and well-motivated
design principle. It is not a new algorithm. Inferring a document's structural
scheme first and then classifying against it is the same shape as
table-of-contents-first segmentation (HiPS, now DocsRay, both cited), and
"describe the schema, then extract against it" is standard practice in
guideline-following IE (GoLLIE, cited). What is genuinely the author's is the
specific combination: a cheap Pass-1 that infers depth count and per-depth
appearance from a layout-stratified sample; a Pass-2 that treats that map as
authority; and a decoupled parser whose composition rules read only dot
structure and whitespace. The layout-stratified sampler is the one piece I
would call a real technical finding: the observation that a rare x-position is
a rare depth, and that stride sampling therefore drops exactly the evidence
Pass-1 needs, is non-obvious and the paper shows the failure it causes.

The second contribution, the canonical schema plus deterministic,
collision-free identifiers across namespaces that skip levels or restate their
parents, is more valuable than the paper's framing suggests. It is the part a
standards body would actually reuse. It is under-sold in §4 and §6.3, where the
prose is dense and the examples are hard to follow without the appendix.

### Is the evidence sufficient for the claims made?

For the claims as now qualified, mostly yes. For the claims a skim reader will
take away, no, and the paper knows it:

- **Recall 1.000 at every level in all six states is close to uninformative
  for four of the six.** The development goldens are spot checks of 5, 25, 7
  and 8 elements against 67, 122, 61 and 33 detections; recall saturates on
  them, and the paper says so (§8.2, §9.3). The load-bearing evidence is
  Kentucky (44/44, detection-exhaustive) and Nevada (46 content-exhaustive).
  That is two documents, 15 and 8 subset pages, one to two domains each.
- **Precision rests on the author auditing the author's own system.** The
  false-positive audit is careful and signed, but it is one annotator, no
  second rater, no agreement figure, and the goldens were written by the same
  person who wrote the prompts. Nothing in the paper measures annotation
  reliability.
- **The ablation's effect is real but small and narrow.** Pooled strand recall
  0.92 and sub-strand 0.83 with the depth map off, driven by two states, at
  n=3 per arm, with the repeats recorded at an earlier code version than the
  point values (now disclosed). The level-collapse mechanism on Kentucky is the
  convincing part; the pooled numbers are not.
- **The rule-based comparison is a foil, not a baseline.** A reviewer will ask
  why the comparison is against a regex extractor the author wrote to lose,
  rather than against (a) a single LLM call over the whole document with no
  depth map, no chunking and no deterministic repairs, which is the obvious
  "just prompt it" alternative the paper argues against in §6.1 but never
  measures; (b) an off-the-shelf PDF-to-markdown converter's heading hierarchy
  (Marker, Docling, MinerU); or (c) a second frontier model, to show the method
  is not an artifact of one vendor. The paper names the model-tier ablation as
  future work; a reviewer will not accept that.
- **Every quality number is a single run of a nondeterministic system**, and
  the paper's own stability section shows a recorded headline that did not
  reproduce. The paper handles this better than most: ranges where it has
  them, lower-bound language, the non-reproduction reported rather than
  buried. But it means the tables are draws, not estimates.

### One claim I would soften before posting

"The system contains no per-state rule" is true of the *Python*, and the
migration that removed per-state code is well documented. It is not quite true
of the *prompts*: the parser prompt reproduced in Appendix A carries worked
examples drawn from the development states (`PK3.I.A.1`, `AL.1.0.INIT.1.2`,
`ELD.1.0.VOCA.1.1.DISC`, "Language and Early Literacy Standard 1"). That is
ordinary few-shot practice and the held-out results still support
generalization, but a hostile reviewer will quote the appendix back at the
abstract. Say "no per-state code path; the prompts carry examples from the
four development states" and the objection disappears. I did not make this
change because it alters what the paper claims about itself, which is the
author's call.

### What a hostile reviewer attacks first, in order

1. Evaluation scale: 70 pages, two states with meaningful goldens, single
   annotator, no agreement statistics.
2. Missing baselines: no whole-document single-prompt arm, no second model, no
   off-the-shelf converter.
3. Novelty: "prompt engineering plus a schema, evaluated on a tiny private
   corpus, with nothing released."
4. The 17-page body: too long for the evidence it carries, and §5, §7 and the
   Explorer screenshot read as product description.
5. The prompt examples versus the "no per-state rule" claim, above.

### What the paper does well, and should lead with more confidently

The measurement discipline is the best thing in it. Corpus tiers on every
table, a manual audit of every unmatched detection, a non-reproduction
reported against the author's own earlier result, a validator that is shown
to catch a live defect rather than asserted to, and every number regenerated
from recorded artifacts. Reviewers at applied venues reward exactly this, and
it is rarer than novelty.

---

## 2. Should it go to a conference, and which?

### The honest ranking

| Venue | Fit | Verdict |
|---|---|---|
| ACL / EMNLP / NAACL **main** | Poor. Novelty modest, evaluation small, no artifacts. | Do not submit as a long paper. |
| **EMNLP / [NAACL](https://2027.naacl.org/)  / ACL Industry Track** | **Good.** A deployed system, engineering lessons (silent failures, nondeterminism, validation boundary), real cost figures, honest limitations. Industry-track reviewers weigh deployment evidence over novelty and do not require released code. Proceedings are in the ACL Anthology. | **First choice.** |
| ACL / EMNLP **Findings** | Possible via ARR, but a Findings reject-to-Findings decision on a main-track submission is not something to aim for. | Only as a fallback from an ARR cycle. |
| **COLING 2027** main | Moderate. COLING is friendlier to applied and resource-adjacent work; the absence of a released resource hurts. | Second choice among NLP venues. |
| ICDAR / DAS | Weak. The document-analysis community will ask for layout-model baselines on standard benchmarks (Comp-HRDoc, DocHieNet) and the paper's stance is precisely not to use layout models. | Do not. |
| **AIED (Springer LNAI)** | Good. Systems and infrastructure papers are welcome, education framing is native, the human-verification design is a plus, and reviewers there will not demand a second LLM. Indexed in DBLP and Scopus. | **Strong alternative**, arguably the best fit for the *subject* if not the *method*. |
| **EDM** | Moderate. EDM prefers learner data and models; a standards-infrastructure paper is off-center but has been accepted there in the past. DBLP-indexed. | Third choice. |
| L@S / LAK | Poor. Neither community cares much about document extraction. | Do not. |
| Workshops: the ACL/EMNLP "Insights from Negative Results" workshop; NLP for education workshops (BEA, AI4EDU); the AI-for-public-sector workshops | Good for the non-reproduction and silent-failure material specifically. | Companion, not substitute. |

**If the honest answer were "arXiv only"**: it is not, but here is what that
would cost in this context. An arXiv posting is citable and establishes
priority; it is not peer-reviewed and is not indexed in the ACL Anthology,
DBLP or Scopus. The strongest venue that would plausibly accept the work as it
stands, without new experiments, is an **ACL-family industry track** or
**AIED**. Both are indexed. Neither would plausibly accept the current
17-page body unchanged; both need the cut below.

### What to cut for an 8-page (industry: typically 6–8) version

Keep: abstract, §1 (trimmed to one page), §2 (half a page), §3 (as a
paragraph plus Table 1), §4 and §6 merged into a three-page method section
leading with Pass-1, the sampler and the identifier scheme, §8.1, §8.2, §8.5
and §8.6 as the results, and a one-page limitations section. Keep Tables 2, 4,
7 and 8 and Figure 3.

Cut or move to appendix: §5 entirely (fold two sentences into §4), §7 and
both figures in it (the architecture belongs in an appendix; the Explorer
screenshot belongs in a demo paper), §6.3's repair-by-repair walkthrough (one
paragraph plus a pointer), §6.5 and §8.4 collapsed into one paragraph stating
that confidence is uninformative and gates nothing (Table 6 to appendix), §8.3
to a half-page with Table 5 kept, §9 merged into limitations, §10's future-work
paragraphs cut to three sentences. Appendices A–D stay; they are the artifact.

### Timing and preprint policy

The ACL family removed its preprint anonymity period in 2024; posting to arXiv
now, non-anonymously, does not foreclose an ARR submission, and ARR
submissions remain anonymized regardless. Springer's AIED proceedings likewise
permit prior preprints. So **post to arXiv now and submit later is
compatible with every venue above.** Check each call's page when it opens:
industry-track deadlines fall roughly four to five months before the
conference, AIED's roughly January to February for a July conference. I have
not verified 2027 dates and you should not rely on my recollection of them.

One cadence point matters more than the exact dates: the two experiments a
reviewer will demand (a whole-document single-prompt arm and a second model,
or at minimum the Kentucky quality-at-scale grade in §4 below) are each a day
of work and a modest Bedrock spend. Doing them before submission, and posting
the arXiv version after them rather than before, produces one better preprint
instead of two versions.

---

## 3. Who else would want this?

The paper's national-importance case is currently **implied, not made**. The
introduction says the policy is "public, consequential, and almost entirely
unavailable to software" and the conclusion mentions "the national
machine-readable dataset that does not currently exist", but nothing in the
body names who needs such a dataset or what they do today without it. One
paragraph would make the case without overclaiming, and every fact in it is
already citable from the bibliography: every state and DC publishes early
learning guidelines (NCECQA, cited); Head Start programs are federally required
to align school-readiness goals with the ELOF (OHS 2015, cited), which in
practice means every state's guidelines get crosswalked to the ELOF by hand;
and unlike K–12, no exchange format is populated for the birth-to-five band
(CASE, ASN, cited). That paragraph belongs at the end of §1 or the start of
§9, and it should stop there. The organizations below are the concrete form of
the same case. For each I name the team whose remit this is, not an
individual, and what a first approach should ask for.

**Education-data standards bodies**

- **1EdTech Consortium, CASE working group.** CASE is the exchange format the
  paper positions itself as complementary to, and 1EdTech's own page describes
  a CASE framework as "a hierarchically structured digital version" of a
  standards PDF, which is exactly this paper's output. Ask: whether the
  canonical schema maps cleanly onto CASE `CFItem`/`CFAssociation`, and whether
  an early-learning CASE export of six states would be of interest as a
  reference implementation. A confirmed mapping is a citable artifact and a
  concrete adoption path.
- **Common Education Data Standards (CEDS), NCES / U.S. Department of
  Education, and the CEDS Open Source Community.** CEDS carries early-learning
  domain elements and a standards-alignment model. Ask: a review of whether the
  four-level schema and the `human_verified` state align with CEDS elements.
- **OpenSALT maintainers (open-source CASE editor).** Ask: whether a CASE
  export of the corpus could be loaded and browsed there; that is a cheap
  public demonstration.

**Federal and national early-childhood bodies**

- **National Center on Early Childhood Quality Assurance (Child Care Technical
  Assistance Network, OCC/ACF).** They maintain the state-by-state ELG link
  list the paper cites. Ask: whether a machine-readable index over the same
  documents would be useful to their state technical-assistance work.
- **National Center on Early Childhood Development, Teaching, and Learning
  (Office of Head Start).** They publish state-ELG-to-ELOF alignment
  crosswalks. Ask: whether a normalized corpus would let those crosswalks be
  produced or updated faster. This is the single clearest downstream use of
  the work and the one to lead with.
- **NAEYC** (position statements on early learning standards) and **NIEER at
  Rutgers** (the annual State of Preschool yearbook tracks which states have
  standards and how they are used). Ask: interest in the corpus for
  cross-state policy analysis; NIEER in particular would be a credible
  academic user.
- **Child Trends' Early Childhood Data Collaborative.** Their remit is
  integrated early-childhood data systems; standards are an input they
  currently lack in structured form.

**State education agencies**

The six issuing agencies in Table 9 are the natural first partners, and the
paper already has the mechanism for a collaboration that costs them little:
the per-element `human_verified` workflow. Ask each agency's early-learning
office (Kentucky's Governor's Office of Early Childhood; Nevada's Office of
Teaching and Learning; Colorado's Department of Early Childhood; Arizona's and
California's early-education divisions; TEA's early-childhood education
division) whether a program specialist would verify their state's extracted
standards in the Explorer, in exchange for the machine-readable copy. A
letter confirming verification, or a state hosting the output, is documented
adoption. Kentucky is the right first ask: its golden is exhaustive and its
trimmed-tier run already exists.

**Curriculum and assessment vendors**

- **Teaching Strategies (GOLD)** and **HighScope (COR Advantage)** maintain
  published alignments of their assessments to each state's ELGs, and to the
  ELOF, by hand; a HighScope alignment document turned up in my searches. Ask:
  whether machine-readable state standards would reduce the cost of
  maintaining those alignments across fifty states and periodic revisions.
- **Instructure's standards database (formerly Academic Benchmarks / Certica)**
  is the largest commercial standards corpus and ingests documents manually.
  They are both a potential customer and the closest thing to prior art in
  practice; a conversation there is worth having before assuming the gap is as
  empty as the literature suggests.
- Classroom-management and curriculum platforms with early-learning products
  (Brightwheel, Procare, Learning Genie, Frog Street) map content to state
  standards for marketing and compliance; any of them is a plausible pilot.

**Open education data**

- **OER Commons (ISKME)** aligns open resources to standards and has no
  early-learning standards to align to.
- **The Common Standards Project** (open standards API) covers K–12; asking
  whether they would host an early-learning extension is a low-cost, public
  adoption path.

What a first approach should ask for, in every case, is small and specific: a
schema review, a verification pass on one state, or permission to host an
export. Documented interest in any of those is worth more than a broad letter
of support.

---

## 4. The single highest-value thing to do next

**Agree with the paper: grade Kentucky's detection-exhaustive golden inside
the trimmed-tier run.** It is the only measurement that turns "quality at
subset tier" into "quality at scale" without a single new annotation, it costs
no model calls if the Task 6 run's detection output is still in S3 (it was
persisted; the manifest records the run), and it directly tests the claim the
paper is most exposed on. Two practical notes:

- The golden's `source_page` values are subset-PDF page numbers. The new
  `paper/results/corpus_page_ranges.json` maps Kentucky's 8 subset pages to
  published pages 1, 52–55, 65, 71–72 and its 52 trimmed pages to 1, 52–102,
  so the translation needed to match golden entries against the full-run
  detection is now recorded rather than guessed.
- Grade recall *and* precision, and report the in-scope element count at
  scale. If the full-document detector emits duplicates across chunk
  boundaries that the subset run never saw, the exhaustive golden will show it
  as a precision drop, which is exactly the answer the paper needs.

Two things I would rank just behind it, in this order:

1. **A whole-document single-prompt arm** on the six subset PDFs (one call
   each, no depth map, no chunking, no repairs), graded by the same suite. It
   is the comparison every reviewer will ask for, it is cheap, and if it does
   worse it makes the paper; if it does as well, better to know now.
2. **Repeat the Nevada sampler A/B at n=5 per arm.** The paper currently
   downgrades that attribution to "suggested"; five draws per arm either
   establishes it or retires it, and either is a cleaner sentence than the
   current hedge.

I would put a second annotator on a sample of the goldens before any of these
if the target is a main-track venue; for an industry track or AIED it can wait.
