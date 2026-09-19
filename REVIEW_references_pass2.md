# Reference review, pass 2

Reviewed 2026-09-19 against arXiv abstract pages, the ACL Anthology and
CrossRef. Pass 1 (`REVIEW_references.md`, 2026-09-04) verified the 36 original
entries and added four. This pass verifies those four plus the one entry whose
fields changed since, and re-reads every citation cluster in the compressed
Related Work section, where a cluster supports its whole sentence and so every
member must.

## Entries not covered by pass 1's per-entry table

| key | Verified against | Verdict |
|---|---|---|
| `xing2024dochienet` | ACL Anthology 2024.emnlp-main.65 | Title, eight authors, EMNLP 2024, pages 1129--1142 all correct. Method trains pre-trained text-layout models at layout-element level, so it belongs in the "learned from layout supervision" cluster. |
| `wang2025unihdsa` | arXiv 2503.15893 | Title, authors (Wang, Hu, Huo), 2025, comments "Accepted by Pattern Recognition" all correct. Trained with layout supervision; correctly clustered. |
| `jeong2025docsray` | arXiv 2507.23217 | Title, six authors, 2025 correct. Training-free pseudo table of contents for retrieval-augmented QA, which is what the text says. |
| `devaul2011computer` | CrossRef 10.1002/asi.21437 | JASIST 62(2):395--405, 2011, three authors, all correct. |
| `kim2022donut` | CrossRef 10.1007/978-3-031-19815-1_29 | Pages 498--517 (filled in 2026-09-05) and DOI confirmed. |

Also re-read for this pass because the text's characterization depends on it:

| key | Checked | Result |
|---|---|---|
| `wehnert2025hips` | arXiv 2509.00909 abstract | Two paths: table-of-contents metadata, and OCR whitespace plus XML typography plus local context refined by an LLM. Neither is trained. The compressed text had it inside the "hierarchy can be learned" cluster. **Miscited; fixed.** |
| `aggarwal2025fiscal` | arXiv 2511.10659 abstract | The abstract states that "totals at each level of the hierarchy" allow "robust internal validation" through multi-level checks. Pass 1 could not confirm the arithmetic detail and softened the text to "internal-consistency checks"; that wording is accurate and needs no change, but the original "arithmetic structure" wording was also correct. |
| `blecher2023nougat` | arXiv 2308.13418 abstract | Output is a markup language; the abstract does not say whether headings are encoded. "Its targets are flat" was therefore not verifiable for Nougat, and GROBID's TEI output is sectioned. **Wording changed** to "none of them targets a typed tree carrying codes and ancestry", which is the claim the gap argument actually needs. |

No entry fails to exist and no field was found wrong. The three NeurIPS page
ranges and the CASE version dates remain unverified from primary sources, as
pass 1 reported.

## Citation-claim mismatches in the compressed text

All in `sections/related_work.tex`, all corrected in this pass.

1. **HiPS inside the learned cluster.** The sentence "All share a premise my
   setting violates: hierarchy can be learned, because supervision exists" was
   attached to a cluster containing `wehnert2025hips`, which is training-free.
   HiPS is now named beside DocsRay as a training-free neighbor, with the
   distinction that it works within one genre (law books) and leans on
   table-of-contents metadata.
2. **Liu et al. 2022 supporting the sentence it argues against.** "Generative
   extraction is competitive ... especially where labeled corpora are scarce"
   cited `liu2022fewshot`, whose title is that parameter-efficient fine-tuning
   is better and cheaper than in-context learning. The introduction cites it
   correctly as the counterargument. It now has its own clause in Related Work.
3. **ELOF cited for "no national framework spans the age band".** The Head
   Start Early Learning Outcomes Framework does span birth to five. What it
   does not do is bind states. The sentence now reads "the one federal
   framework for the age band binds Head Start programs alone".
4. **Gilardi 2023 and Tan 2024 under "active learning or selective
   allocation".** Both are about the model as annotator, not about allocating
   work by uncertainty. The sentence now names that alternative as well, so
   every member of the cluster supports it.
5. **"Its targets are flat"** for the six-paper lineage cluster; see the table
   above.

## Redundant or bibliography-only citations

Every key in `references.bib` is cited at least once in the body
(`main.log` reports no unused-citation warnings because BibTeX only emits
what is cited, and a grep of the sections finds all 40 keys). None was made
redundant by the cut. The twelve background works in the first paragraph's
two clusters remain lineage rather than comparison, as `TODO_remaining.md`
notes; they are the cheapest candidates if the list is ever shortened, but
nothing in this pass requires it.

## Does anything defeat the gap claim?

Nothing found. The two-part claim as now stated holds: the learned
hierarchy-recovery line (DocParser, HRDoc, Detect-Order-Construct, UniHDSA,
DocHieNet) needs layout supervision over a typographically consistent genre;
the two training-free neighbors (HiPS, DocsRay) either stay within one genre or
target retrieval segmentation rather than a typed, code-bearing hierarchy; and
the education-standards literature presupposes normalized standards. I did not
re-run pass 1's literature search.
