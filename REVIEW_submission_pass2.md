# arXiv submission package check, pass 2

Checked 2026-09-19 by copying only the submission set into an empty scratch
directory and compiling with `pdflatex` three times and no `bibtex`, which is
how arXiv treats a supplied `.bbl`.

## What was copied

```
main.tex
acl.sty
acl_natbib.bst
main.bbl
anc/prompts.txt
sections/   (11 files)
tables/     (15 files)
figures/    colorado_els.png, fig_architecture.pdf
```

`references.bib` was deliberately left out, matching the plan for Task 13.

## Result

| Check | Result |
|---|---|
| Compiles with pdflatex only | Yes, exit 0, 28 pages, identical to the in-repo build |
| Missing files | None. `main.log` reports no "No file" or "not found" lines. |
| Undefined references or citations | 0 |
| Overfull boxes | 0 |
| Absolute paths | None in any `.tex`, the `.bbl` or `anc/prompts.txt` |
| Dependencies outside the set | None. `\bibliography{references}` resolves to `main.bbl`; every `\input` and `\includegraphics` is relative and present. |
| Package size | 1.7 MB including the built PDF and logs; well inside arXiv limits. The largest file is `figures/colorado_els.png` at 378 KB. |

## Things that should not be published

Grepped every file in the set for AWS account identifiers, ARNs, S3 URIs,
`/Users/` paths, the repository name, the author's personal email, and
`TODO`/`FIXME` markers. **Nothing found.** The account id that appears in
`paper/results/` manifests does not reach any shipped file. The only email in
the set is the byline's `emily@edtechco.org`, which the brief confirms.

`main.tex` still carries drafting comments (float-spacing rationale, the
section-order note, the two "Moved out of the body 2026-09-07" notes and the
`anc/` note). They are harmless and reference only `REVIEW_assessment.md` and
`paper/OUTLINE_NOTES.md` by name, neither of which ships. Strip them or leave
them; nothing in them is sensitive.

`anc/prompts.txt` is the complete prompt text the Artifacts Statement promises,
and it contains nothing beyond what Appendix A already discloses in part.

## Figures

`figures/fig_architecture.png` is **unused** (the source includes the `.pdf`)
and should be left out of the tarball. Both used figures are referenced from
`sections/system_architecture.tex` and render.

## Metadata consistency

| Field | Value | Consistent |
|---|---|---|
| Title | "Classify by Position, Not by Label: LLM-Driven Extraction of Hierarchical Structure from Fragmented US Early Learning Standards" | matches the working title in `tasking/arxiv_paper.md` |
| Byline | Emily Cheyne, Founder, EdTech Co., `emily@edtechco.org` | as confirmed; unchanged |
| Abstract | `paper/arxiv_abstract.txt`, 1,864 characters | matches the LaTeX abstract word for word apart from the dropped `\S\ref`; under the 1,920 limit |
| License | "arXiv non-exclusive license to distribute", copyright retained | stated in the Artifacts Statement; matches the decided license |
| Ancillary file | `anc/prompts.txt` | named in the Artifacts Statement and Appendix A; must be uploaded at that exact path |

## Two practical notes for the upload

1. arXiv's auto-TeX runs `pdflatex` and will pick up `main.bbl`; keep it at the
   root beside `main.tex`. Do not include `main.aux`, `main.out` or any log.
2. The `anc/` directory must be preserved as a directory in the tarball; arXiv
   treats files under `anc/` as ancillary only at that path.
