# arXiv submission — ready to upload

Built 2026-11-01 from `paper/main.tex` by `paper/analysis/build_arxiv_bundle.py`
(re-run it after any edit to the paper; it rebuilds `src/` and the tarball).

## What to upload

**`arxiv_upload.tar.gz`** — 33 files, ~500 KB. Upload it as-is; arXiv unpacks it.

| in the tarball | why |
|---|---|
| `main.tex`, `sections/*.tex`, `tables/*.tex` | only the files `main.tex` actually `\input`s (11 section files, 15 table files) |
| `fig_architecture.pdf`, `colorado_els.png` | flattened out of `figures/`; `\includegraphics` paths rewritten to match |
| `acl.sty`, `acl_natbib.bst` | the style files |
| `main.bbl` | bibliography pre-compiled from the current `references.bib` (0 BibTeX warnings). The `.bib` is **not** shipped |
| `anc/prompts.txt` | the full prompts. Kept at exactly `anc/` so arXiv lists it as an **ancillary file** — Appendix A and the Artifacts Statement cite it by that path |

Not in it: `.aux/.log/.out/.blg/.pdf`, `.DS_Store`, the `.bib`, `DRAFTING_NOTES.md`,
TODOs, `results/`, `analysis/`, `naacl2027/`, `dai2027/`, and macOS `._*` / xattr files (the tar is written by
Python, not BSD tar, so none can sneak in).

## The arXiv preflight checklist, item by item

- **TeX source, not PDF** — ✅ source tarball.
- **All files in one folder** — ✅ `src/` is the exact tree inside the tarball, if you want to look.
- **Missing files or references** — ✅ extracted the tarball into an empty
  directory and compiled with `pdflatex` ×4 and **no bibtex** (what arXiv does with
  a shipped `.bbl`): 28 pages, 0 errors, 0 undefined references or citations,
  0 missing files, 0 overfull boxes, no `??` or `[?]` anywhere in the PDF text.
- **Nothing archived you don't want archived** — ✅
  - **every LaTeX comment stripped** (106 comment lines across `main.tex` and
    the generated tables, incl. the internal `tasking/…`, `REVIEW_assessment.md`,
    `Task 13` and `paper/results/…` notes). Full-line comments are deleted;
    an inline comment is cut back to a bare `%` so line-joining is unchanged.
  - **proof it changed nothing visible:** the PDF built from the tarball is
    text-identical, page for page, to a PDF built from your original sources.
  - PNG screenshot: EXIF/XMP metadata removed (it only said "Screenshot" and
    the pixel size, but source files are public). Image checked: no account
    IDs, URLs or emails.
  - no "submitted to / under review" text; ACL style is in final, non-anonymous mode.
  - `\appendix` comes after `\bibliography`; the
    `\typeout{get arXiv to do 4 passes: Label(s) may have changed. Rerun}`
    line is after `\end{document}`.

`preview_from_tarball.pdf` is the PDF compiled from the tarball — read this one,
since it's what arXiv will produce (arXiv's TeX Live is older than the local
2026 one; compare arXiv's own preview against it before you hit Submit).

## Form fields (copy-paste)

**Title**
```
Classify by Position, Not by Label: LLM-Driven Extraction of Hierarchical Structure from Fragmented US Early Learning Standards
```

**Authors**
```
Emily Cheyne
```

**Abstract** — paste `paper/arxiv_abstract.txt` (1,874 chars of the 1,920 limit,
one line, ASCII only; checked word-for-word against the abstract in `main.tex`).

**Comments**
```
28 pages, 4 figures, 11 tables. Complete prompts in the ancillary file anc/prompts.txt
```

**Primary category:** `cs.CL` · **Cross-list:** `cs.AI`

**License:** *arXiv.org perpetual, non-exclusive license to distribute this
article* (decided 2026-09-19).

Leave Journal-ref, DOI, Report number blank. MSC/ACM class optional
(ACM `I.2.7` fits if you want one).

## Still yours to do

1. **Endorsement.** You need a personal endorsement for cs.CL (no institutional
   email + no prior cs.CL paper). Start the submission; arXiv shows the
   endorsement code/link at that point — send it to your endorser.
2. **Read `preview_from_tarball.pdf` end to end** (TODO_remaining §9).
3. **Check arXiv's processed PDF** on the preview step before submitting.
   Announced versions are permanent.
