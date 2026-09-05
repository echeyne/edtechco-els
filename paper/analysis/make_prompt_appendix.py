"""Generate Appendix A (prompts) and the ancillary full-text file from the LIVE
prompt builders.

Guardrail 6, applied to prose rather than numbers: the appendix is the paper's
substitute for releasing the code, so a prompt that has drifted from the
implementation would be a false disclosure. Rendering it from
``detector.build_depth_map_prompt`` / ``build_detection_prompt`` and
``parser.build_parsing_prompt`` makes drift impossible -- rerun this and both
outputs follow the source.

TWO outputs, because the complete prompts are ~46K characters and reading them
end to end on the page is not how anyone uses them:

  paper/tables/appendix_prompts.tex   Pass 1 whole, plus the individual rules
                                      the body of the paper argues about, each
                                      with a \\label so \\S4 can cite it and a
                                      one-line editorial gloss above the
                                      verbatim text.
  paper/anc/prompts.txt               all three prompts, complete and
                                      unabridged. Ships as an arXiv ancillary
                                      file, so nothing is withheld by the
                                      excerpting above.

The document content each prompt appends is replaced by a placeholder in BOTH
outputs; that is per-run input, not part of the instruction, and reproducing one
chunk of a third-party PDF here would be a redistribution I cannot grant.

Excerpts are selected by ANCHOR, not by line number, and a missing anchor is a
hard failure rather than a silently shorter appendix -- otherwise a reworded
prompt would quietly drop a rule the paper cites.

Run: python paper/analysis/make_prompt_appendix.py
"""
import pathlib
import re
import sys

ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from els_pipeline.detector import build_depth_map_prompt, build_detection_prompt  # noqa: E402
from els_pipeline.parser import build_parsing_prompt  # noqa: E402

OUT_TEX = ROOT / "paper" / "tables" / "appendix_prompts.tex"
OUT_ANC = ROOT / "paper" / "anc" / "prompts.txt"

DEPTH_MAP_EXAMPLE = {
    "doc_depths": [
        {"depth": 1, "canonical_level": "domain", "label_in_doc": "Domain",
         "prefix_pattern": "ALL-CAPS HEADING", "example": "APPROACHES TO LEARNING"},
        {"depth": 2, "canonical_level": "strand", "label_in_doc": "Standard",
         "prefix_pattern": "<Area> Standard N", "example": "Approaches to Learning Standard 1"},
    ],
    "notes": "",
}

# ---------------------------------------------------------------------------
# Excerpt selection. (label, heading, gloss, anchor)
#
# The anchor is a distinctive substring of the rule's FIRST line. Each entry
# earns its place by being cited from the body of the paper -- if you add one,
# add the \ref that points at it, and if you remove a citation, drop the
# excerpt rather than leaving an orphan.
# ---------------------------------------------------------------------------

DETECTION_EXCERPTS = [
    (
        "rule:positional",
        "Classification is positional",
        r"The instruction the rest of the prompt is built around: an element's level "
        r"comes from where it sits in the depth map, never from the word the document "
        r"uses to label it. This is what makes the prompt transfer across states that "
        r"share no vocabulary.",
        "CLASSIFICATION RULE:",
    ),
    (
        "rule:emit-what-you-see",
        "An element requires a heading that is present",
        r"Grounding, and the reason detection can afford to be chunk-local: a chunk that "
        r"opens part-way through a section emits the children alone rather than "
        r"reconstructing the absent parent from the position identifiers inside a child's "
        r"code. The parent is recovered later, in parsing (\S\ref{sec:method-parsing}).",
        "1. Emit every structural element you see",
    ),
    (
        "rule:age-columns",
        "Side-by-side age-band columns",
        r"Age-banded documents lay one skill across several columns, and the columns are "
        r"peer indicators rather than one indicator with several descriptions. The rule is "
        r"stated as a count -- $N$ columns must yield $N$ elements -- because the failure "
        r"it guards against is a visually sparse column being silently collapsed into its "
        r"neighbor.",
        "3. Side-by-side age-band columns",
    ),
    (
        "rule:code-resolution",
        "Code resolution and the derived abbreviation",
        r"The longest rule in the prompt, and the one \S\ref{sec:method-detection} draws "
        r"on most. It orders three places a printed code may live -- inline, in a caption, "
        r"or as the shared leading prefix of its descendants' codes -- and only then falls "
        r"back to deriving one from the title. The abbreviation procedure at the end is the "
        r"rule that is additionally executed in Python, for the determinism reasons given "
        r"in \S\ref{sec:method-detection}.",
        "4. `code`: REQUIRED on every element",
    ),
    (
        "rule:confidence-bands",
        "Confidence",
        r"Reproduced because \S\ref{sec:method-confidence} and "
        r"\S\ref{sec:experiments-confidence} report what the score does in practice. Note "
        r"that the prompt asks for a band and nothing downstream reads the answer: no "
        r"threshold, no review gate, no field marking an element for attention.",
        "5. `confidence`:",
    ),
]

PARSING_EXCERPTS = [
    (
        "rule:already-qualified",
        "Already-qualified codes are never re-prefixed",
        r"Applies at every level, not only the leaf. Without it a code the detector "
        r"already resolved against its domain is composed onto its own domain a second "
        r"time.",
        "ALREADY-QUALIFIED codes are used AS-IS",
    ),
    (
        "rule:namespace-skip",
        "A printed namespace may skip a level the hierarchy has",
        r"The Nevada case of \S\ref{sec:method-parsing}, stated as a general principle: "
        r"peeling ancestors off a descendant's code stops where the printed namespace "
        r"stops, and the level outside it keeps the identifier its own heading supplied.",
        "A document's printed code NAMESPACE may SKIP a level",
    ),
    (
        "rule:label-identifier",
        "Converting a label-and-identifier code",
        r"The detector correctly emits a heading's label-and-id as its code "
        r"(\texttt{Benchmark 1.1}); converting that into the domain-qualified form is "
        r"parsing's job. The rule is keyed on the shape \texttt{<Label> <id>} for any "
        r"label word, with no list of label words anywhere in it.",
        "When an element's `code` is itself a structural label",
    ),
    (
        "rule:disambiguate",
        "Disambiguating side-by-side columns",
        r"Column indicators share a code stem by construction, so the identifier must "
        r"carry the distinction itself. Age-range columns and proficiency columns take "
        r"different suffixes, and an indicator that came from no column takes none.",
        "DISAMBIGUATE side-by-side columns",
    ),
]


def rendered():
    """Render each prompt from the live builder, then blank the per-run input."""
    depth = build_depth_map_prompt([])
    detect = build_detection_prompt([], depth_map=DEPTH_MAP_EXAMPLE)
    parse = build_parsing_prompt([], "US", "KY", 2021, "36-60")

    def strip_doc(text, marker):
        i = text.find(marker)
        return (text if i < 0 else text[:i] + marker
                + "\n\n<<serialized document lines, one per row, each prefixed\n"
                  "  [Page N | x=<left edge as fraction of page width>]>>\n")

    depth = strip_doc(depth, "DOCUMENT SAMPLE:")
    detect = strip_doc(detect, "DOCUMENT CHUNK:")
    parse = re.sub(r"(DETECTED ELEMENTS[^\n]*\n)(.*)$", r"\1\n<<serialized detected elements>>\n",
                   parse, flags=re.S)
    return depth, detect, parse


# --- block indexing --------------------------------------------------------

_DETECT_HEAD = re.compile(r"^(?:(\d+[a-z]?)\.\s|([A-Z][A-Z0-9 &/,'-]{3,}:))")


def index_detection(text):
    """Split the detection prompt into (key, body) in document order.

    A block starts at a numbered rule (``4.``) or an ALL-CAPS section header
    (``CLASSIFICATION RULE:``) at column zero, and runs to the next such line.
    Continuations and sub-bullets stay with their rule.
    """
    lines = text.split("\n")
    starts = []
    for i, line in enumerate(lines):
        m = _DETECT_HEAD.match(line)
        if m:
            starts.append((i, m.group(1) or m.group(2)))
    blocks = []
    for n, (i, key) in enumerate(starts):
        end = starts[n + 1][0] if n + 1 < len(starts) else len(lines)
        blocks.append((key, "\n".join(lines[i:end]).rstrip()))
    return blocks


def index_parsing(text):
    """Split the parsing prompt into top-level ``- `` bullets, sub-bullets kept."""
    lines = text.split("\n")
    starts = [i for i, line in enumerate(lines) if line.startswith("- ")]
    blocks = []
    for n, i in enumerate(starts):
        end = len(lines)
        for j in range(i + 1, len(lines)):
            if lines[j].startswith("- ") or (lines[j] and not lines[j].startswith((" ", "\t"))):
                end = j
                break
        blocks.append((lines[i], "\n".join(lines[i:end]).rstrip()))
    return blocks


def pick(blocks, anchor, where):
    """Return the one block whose text starts with/contains ``anchor``.

    Ambiguity and absence are both hard failures: a silently-dropped rule is
    exactly the drift this file exists to prevent.
    """
    hits = [body for key, body in blocks if anchor in key or body.startswith(anchor)]
    if len(hits) != 1:
        raise SystemExit(
            f"make_prompt_appendix: anchor {anchor!r} matched {len(hits)} blocks in the "
            f"{where} prompt (expected exactly 1). The prompt was reworded -- update the "
            f"anchor, and check whether \\S4's citation of it still holds."
        )
    return hits[0]


# --- rendering -------------------------------------------------------------

def listing(body):
    return "\n".join([r"\begin{lstlisting}[style=promptstyle]", body.rstrip(),
                      r"\end{lstlisting}"])


def excerpt(label, heading, gloss, body):
    return "\n".join([rf"\subsubsection{{{heading}}}", rf"\label{{{label}}}",
                      gloss, "", listing(body), ""])


def main():
    depth, detect, parse = rendered()
    dblocks = index_detection(detect)
    pblocks = index_parsing(parse)

    # Name the detection rules NOT excerpted, derived rather than hand-listed so
    # the count cannot go stale when a rule is added.
    shown = set()
    for _, _, _, anchor in DETECTION_EXCERPTS:
        m = re.match(r"(\d+[a-z]?)\.", anchor)
        if m:
            shown.add(m.group(1))
    numbered = [k for k, _ in dblocks if re.fullmatch(r"\d+[a-z]?", k or "")]
    omitted = [k for k in numbered if k not in shown]
    omitted_str = (", ".join(omitted[:-1]) + " and " + omitted[-1]) if len(omitted) > 1 \
        else (omitted[0] if omitted else "")

    parts = [
        "% AUTO-GENERATED by paper/analysis/make_prompt_appendix.py -- do not hand-edit.",
        "% Rendered from the live prompt builders so the appendix cannot drift from the",
        "% implementation it discloses. Regenerate with:",
        "%   python paper/analysis/make_prompt_appendix.py",
        "%",
        "% The same script writes paper/anc/prompts.txt (the complete prompts, shipped as",
        "% an arXiv ancillary file). Task 13 must keep anc/ as a directory -- it is NOT",
        "% flattened into the paper root the way figures/ is.",
        "",
        r"This appendix and the schema of Appendix~\ref{sec:appendix-schema} are what this",
        r"paper discloses in place of a code release (\S\ref{sec:artifacts-statement}).",
        rf"Pass~1 is short and is given whole. The detection and parsing prompts are long"
        rf" --- together roughly {round((len(detect) + len(parse)) / 1000):,}{{,}}000"
        rf" characters --- so rather than print them end to"
        r" end I reproduce the individual rules the body of the paper argues about, each"
        r" verbatim and each labeled so it can be cited from \S\ref{sec:method}."
        r" \textbf{The complete text of all three prompts, unabridged, ships with this"
        r" paper as the ancillary file \texttt{anc/prompts.txt}}; nothing is withheld by"
        r" the selection here.",
        "",
        r"All three are reproduced as the system emits them, with only the per-run document"
        r" content replaced by a placeholder.",
        "",
        r"\subsection{Pass 1: depth-map inference}",
        r"\label{sec:prompt-depthmap}",
        r"Run once per document, on a layout-stratified sample of text blocks"
        r" (\S\ref{sec:method-detection}). Its output is supplied to every subsequent"
        r" detection call as the authority for what each nesting level is.",
        "",
        listing(depth),
        "",
        r"\subsection{Pass 2: per-chunk detection}",
        r"\label{sec:prompt-detection}",
        rf"The prompt opens with the canonical hierarchy, the layout-coordinate convention"
        rf" and the classification rule, then states {len(numbered)} numbered extraction"
        rf" rules, then the output schema. The excerpts below are the classification rule"
        rf" and the rules cited in \S\ref{{sec:method}}; rules {omitted_str} are given in"
        rf" full in \texttt{{anc/prompts.txt}}.",
        "",
    ]
    for label, heading, gloss, anchor in DETECTION_EXCERPTS:
        parts.append(excerpt(label, heading, gloss, pick(dblocks, anchor, "detection")))

    parts += [
        r"\subsection{Parsing}",
        r"\label{sec:prompt-parsing}",
        r"The parsing prompt states the output schema, then a list of rules governing how"
        r" an indicator's fully-qualified code is composed from its chain of ancestors."
        r" The four reproduced below are the ones \S\ref{sec:method-parsing} draws on;"
        r" the rest are in \texttt{anc/prompts.txt}.",
        "",
    ]
    for label, heading, gloss, anchor in PARSING_EXCERPTS:
        parts.append(excerpt(label, heading, gloss, pick(pblocks, anchor, "parsing")))

    OUT_TEX.write_text("\n".join(parts))

    OUT_ANC.parent.mkdir(parents=True, exist_ok=True)
    anc = [
        "Prompts for \"Recovering Hierarchy from Early Learning Standards Documents\"",
        "=" * 76,
        "",
        "Ancillary file. The complete text of all three prompts, exactly as the system",
        "emits them, with only the per-run document content replaced by a placeholder.",
        "Appendix A of the paper reproduces Pass 1 in full and excerpts the individual",
        "rules the paper argues about; this file is the unabridged source for both.",
        "",
        "Generated from the live prompt builders by",
        "paper/analysis/make_prompt_appendix.py, so it cannot drift from the",
        "implementation it discloses.",
        "",
    ]
    for n, (title, body) in enumerate(
        (("PASS 1 -- DEPTH-MAP INFERENCE", depth),
         ("PASS 2 -- PER-CHUNK DETECTION", detect),
         ("PARSING", parse)), start=1
    ):
        anc += ["", "=" * 76, f"{n}. {title}", "=" * 76, "", body.rstrip(), ""]
    OUT_ANC.write_text("\n".join(anc))

    print(f"wrote {OUT_TEX}")
    print(f"wrote {OUT_ANC}")
    tex = OUT_TEX.read_text()
    print(f"  appendix: {len(tex):,} chars   ancillary: {len(OUT_ANC.read_text()):,} chars")
    print(f"  detection rules: {len(numbered)} total, {len(shown)} excerpted, "
          f"omitted = {omitted_str or 'none'}")
    for name, body in (("depth map", depth), ("detection", detect), ("parsing", parse)):
        print(f"  {name}: {len(body):,} chars")


if __name__ == "__main__":
    main()
