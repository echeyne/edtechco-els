# Reference review — `paper/references.bib`

Reviewed 2026-09-04 against the ACL Anthology, arXiv abstract pages, CrossRef
(by DOI), publisher pages, and dblp where those were reachable. "Unverified"
below means I could not reach an authoritative source for that field today, not
that the field is wrong. Every entry is also checked at its point of use in
`paper/sections/related_work.tex` and `introduction.tex`.

Four entries were **added** and five had missing page/volume fields filled in
(all recorded in the `.bib` provenance comments). One citation in the
introduction was **wrong** and has been moved.

## Per-entry verdicts (36 original entries)

| # | key | Exists as described? | Used correctly? | Notes |
|---|---|---|---|---|
| 1 | `brown2020language` | Yes — NeurIPS 2020, vol. 33 (proceedings page) | Yes | Pages 1877–1901 **unverified**: neither the proceedings page nor dblp shows page numbers; the range is the one in general use. |
| 2 | `wei2022chain` | Yes — NeurIPS 2022 (dblp) | Yes | Pages 24824–24837 **unverified** for the same reason. |
| 3 | `wang2023selfconsistency` | Yes — arXiv 2203.11171 comments: "Published at ICLR 2023" | Acceptable, slightly loose | Cited for "sampling variance at fixed prompts". The paper is about aggregating sampled reasoning paths; it *presupposes* sampling variance rather than measuring it. Defensible as context. |
| 4 | `agrawal2022large` | Yes — EMNLP 2022, pp. 1998–2022, Abu Dhabi | Yes | |
| 5 | `wadhwa2023revisiting` | Yes — ACL 2023, pp. 15566–15589, Toronto | Yes | |
| 6 | `xu2024large` | Yes — Frontiers of Computer Science 18(6), 2024, DOI confirmed via CrossRef | Yes | **Filled in** volume 18, number 6. |
| 7 | `sainz2024gollie` | Yes — ICLR 2024 (arXiv comments) | Yes | Text correctly states GoLLIE is *fine-tuned* to follow guidelines and that the paper's prompts do the same without fine-tuning. |
| 8 | `liu2022fewshot` | Yes — NeurIPS 2022 (dblp) | Yes | Pages 1950–1965 **unverified** (as for #1, #2). |
| 9 | `willard2023efficient` | Yes — arXiv 2307.09702 | Yes | |
| 10 | `liu2024lost` | Yes — TACL 12:157–173, DOI confirmed | Yes | |
| 11 | `ji2023survey` | Yes — ACM CSUR 55(12), art. 248, CrossRef says pp. 1–38 | Yes | Bib's `248:1--248:38` is the ACM article-number form; fine. |
| 12 | `aggarwal2025fiscal` | Yes — arXiv 2511.10659; ICAIF 2025 workshop per comments field | Mostly | The related-work sentence says they exploit "internal arithmetic structure for validation". The abstract confirms hierarchical tabular fiscal data; the arithmetic-validation detail is **not confirmed from the abstract** (I did not read the full paper). |
| 13 | `xu2020layoutlm` | Yes — KDD 2020, pp. 1192–1200 (CrossRef) | Yes | |
| 14 | `huang2022layoutlmv3` | Yes — ACM MM 2022, DOI confirmed | Yes | **Filled in** pages 4083–4091 (CrossRef). |
| 15 | `kim2022donut` | Yes — ECCV 2022 (arXiv comments) | Yes | |
| 16 | `blecher2023nougat` | Yes — arXiv 2308.13418 | Yes | |
| 17 | `zhong2019publaynet` | Yes — ICDAR 2019, pp. 1015–1022 (CrossRef) | Yes | |
| 18 | `lopez2009grobid` | Yes — ECDL 2009 (LNCS), pp. 473–474 (CrossRef) | Yes | |
| 19 | `rausch2021docparser` | Yes — AAAI 2021, 35(5):4328–4338 (ojs.aaai.org) | Yes | **Filled in** number and pages. |
| 20 | `ma2023hrdoc` | Yes — AAAI 2023, 37(2):1870–1877 (ojs.aaai.org) | Yes | **Filled in** number and pages. |
| 21 | `wang2024detect` | Yes — Pattern Recognition 156:110836, 2024 (CrossRef) | Yes | The "functionally analogous to the TOC subtask" sentence is a fair reading. |
| 22 | `wehnert2025hips` | Yes — arXiv 2509.00909 v2; comments: "Accepted as a demo paper at ICAIL 2026" | Yes | Abstract confirms TOC-metadata path plus an LLM-refined path. |
| 23 | `monarch2021human` | Yes — Manning, June 2021 | Yes | |
| 24 | `mosqueirarey2023human` | Yes — AI Review 56(4):3005–3054 (CrossRef) | Yes | Issue number 4 could be added; not required. |
| 25 | `settles2009active` | Yes — UW–Madison CS TR 1648, 2009 (MINDS@UW) | Yes | |
| 26 | `li2023coannotating` | Yes — EMNLP 2023, Singapore | Yes | **Filled in** pages 1487–1505 (Anthology), which the bib had omitted as unconfirmed. |
| 27 | `tan2024large` | Yes — EMNLP 2024, pp. 930–957, Miami | Yes | |
| 28 | `gilardi2023chatgpt` | Yes — PNAS 120(30) e2305016120 (CrossRef) | Yes | |
| 29 | `sutton2008achievement` | Yes — DC-2008, Berlin (dcpapers.dublincore.org, article 952109190 and pubs/article/view/920) | Yes | The related-work claim that ASN "was populated by manual modeling" is consistent with the abstract (RDF repository of achievement standards). |
| 30 | `1edtech2017case` | Yes — 1edtech.org/standards/case; CASE 1.1 is the current version | Yes | **Version dates unverified**: the cited page does not state release dates for v1.0 (2017) or v1.1 (2025). |
| 31 | `porter2002measuring` | Yes — Educational Researcher 31(7):3–14 (CrossRef) | Yes | |
| 32 | `polikoff2011howwell` | Yes — AERJ 48(4):965–995; DOI 10.3102/0002831211410684 (CrossRef) | Yes | 138 standards–assessment pairs confirmed. DOI could be added. |
| 33 | `xu2025automated` | Yes — arXiv 2510.05129, cs.CL | Yes | Abstract confirms it aligns items to *already-established* standards, which is exactly the point made in §2.4. |
| 34 | `ncecqa_elgs` | Exists (search snippet confirms title and content: links to ELGs for 50 states + DC) | Yes | The PDF returns 403 to fetches, as the bib note already says; not re-read directly. |
| 35 | `ohs2015elof` | Yes — released June 2015 by the Office of Head Start (multiple secondary confirmations; the headstart.gov page itself returned 403) | Yes | |
| 36 | `ecs2024governance` | Yes — ECS, October 2024 | **Was wrong in the introduction; fixed** | The resource is a 50-state comparison of early care and education *governance* models. The introduction cited it (with CASE) for "K–12 academic standards have machine-readable distribution formats", which it does not say. It now supports the "more than fifty jurisdictions issue them independently" clause instead, and the machine-readable-formats claim cites ASN and CASE. |

**No entry fails to exist, and none is cited for a claim that inverts its finding.** The one substantive miscitation (#36) is corrected. The fields I could not verify are page numbers of three NeurIPS papers and the CASE version dates; none affects a claim in the text.

## Entries added by this review (all verified 2026-09-04)

| key | Source | Why |
|---|---|---|
| `xing2024dochienet` | ACL Anthology 2024.emnlp-main.65, pp. 1129–1142; DOI 10.18653/v1/2024.emnlp-main.65 | The most recent hierarchy-parsing dataset/method in an NLP venue, and multi-domain. Omitting it invited a reviewer to say the survey stopped at 2023. |
| `wang2025unihdsa` | arXiv 2503.15893, comments "Accepted by Pattern Recognition" | Successor to Detect-Order-Construct by the same group. |
| `jeong2025docsray` | arXiv 2507.23217 | Training-free LLM pseudo-table-of-contents construction — the closest zero-shot neighbor to the depth-map pass. See "positioning" below. |
| `devaul2011computer` | JASIST 62(2):395–405, DOI 10.1002/asi.21437 (CrossRef) | The earliest NLP work on assigning educational standards, from the ASN era. Fills the gap between the 2008 ASN paper and the 2025 alignment paper in §2.4. |

## Is anything important missing?

**Education-standards / curriculum NLP: the author's "thin" note is confirmed,
with one qualification.** Searches for standards-document structure extraction,
early-learning-standards datasets, and LLM work over state standards found no
paper that extracts hierarchy from state early-learning-standards PDFs, and no
machine-readable early-learning corpus. What does exist is *alignment* work
that presupposes structured standards, which is the paper's own
characterization. Beyond Devaul et al. (now cited), the closest items are grey
or adjacent literature rather than omissions a reviewer would insist on:

- HumRRO's practitioner note on NLP for alignment crosswalks (blog, undated) —
  practice, not a paper.
- Aligning open educational resources to new taxonomies with AI (Computers &
  Education, 2024, S0360131524000411) — resource-to-taxonomy alignment; again
  presupposes the taxonomy.
- Korver, Lazovich & Reda, "Large Language Models in K-12 Education: Alignment
  with State Curriculum Standards and Student Personas" (arXiv 2606.04846,
  June 2026) — uses state US-History standards as inputs to probe LLM behavior;
  the abstract does not say the standards were extracted from PDFs. Worth a
  look by the author; I did not read the full text and have not cited it.

**Document-structure work: two additions were needed, and one paper sharpens
the gap claim rather than defeating it.** DocHieNet (EMNLP 2024) and UniHDSA
(2025) are layout-supervised and so sit inside the existing characterization.
DocsRay (arXiv 2507.23217) is training-free and prompts an LLM to infer a
pseudo table of contents from content — so the sentence "all prior
hierarchical-document work relies on layout supervision" was **no longer true
as written**. The related-work text now distinguishes DocsRay explicitly: it
produces a segmentation for retrieval-augmented question answering, not a
typed, code-bearing hierarchy graded against structural annotations. That is a
fair distinction, but the author should read DocsRay in full before submission,
because it is the paper a reviewer will reach for.

Not cited, deliberately: general PDF-to-markdown tools (Marker, Docling, MinerU,
Nougat's successors). They are layout-model pipelines whose heading hierarchy
is a by-product, and citing them would not change the positioning.

## Is the positioning defensible?

Yes, with the DocsRay qualification now in the text. The two-part gap claim
holds as restated:

1. *Prior hierarchical-document work needs layout supervision and
   typographically consistent corpora* — true of DocParser, HRDoc,
   Detect-Order-Construct, DocHieNet, UniHDSA and HiPS's metadata path; **not**
   true of DocsRay, which is why the text now says "layout supervision
   *or* a consistent genre" and names the training-free alternative.
2. *Education-standards work presupposes already-structured standards* — true
   of ASN, CASE, Devaul et al., the SEC alignment literature and Xu et al.
   2025. Nothing found contradicts it.

Nothing I found defeats the claim that no prior work recovers a typed hierarchy
with codes and ancestry from heterogeneous state standards PDFs without
per-document rules or layout supervision.
