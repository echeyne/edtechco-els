"""Recover the RETAINED PAGE RANGES of every corpus tier from the PDFs themselves.

Guardrail 3 (tasking/arxiv_paper.md) requires the manual trimming to be
disclosed *with retained page ranges*, not just page counts. Until 2026-09-04
no artifact in the repo recorded which pages of each published PDF survive into
the `_trimmed` and `_only_subset` tiers -- standards/standards_tracking.md
holds URLs and a "cleaned" flag only, and corpus_tiers.json holds counts.

This script derives the ranges deterministically: every page of a tier PDF is
matched back to a page of the published PDF by its extracted text (exact match
first, then a high-similarity fallback for pages whose text layer differs by a
few characters). It uses no model call and no annotation, so the result is
regenerable by anyone holding the PDFs.

Writes paper/results/corpus_page_ranges.json, which generate_tables.py reads
to build paper/tables/corpus_pages.tex.

Usage (from repo root, inside the venv):
    python paper/analysis/corpus_page_ranges.py
"""

import difflib
import json
import re
from collections import Counter
from datetime import date
from pathlib import Path

import fitz  # PyMuPDF

REPO_ROOT = Path(__file__).resolve().parents[2]
STD = REPO_ROOT / "standards"
OUT = REPO_ROOT / "paper" / "results" / "corpus_page_ranges.json"

# (state, published PDF, {tier: PDF}). Colorado's published document for every
# measurement in the paper is the 41pp Ages 3-5 file; the 187pp birth-to-8
# volume it is drawn from is mapped separately below so the relationship is
# recorded rather than asserted.
CORPUS = [
    ("AZ", "arizona_all_standards_2018.pdf",
     {"trimmed": "arizona_all_standards_2018_trimmed.pdf",
      "only_subset": "arizona_all_standards_2018_only_subset.pdf"}),
    ("CA", "california_all_standards_2021.pdf",
     {"only_subset": "california_all_standards_2021_only_subset.pdf"}),
    ("CO", "colorado_3_5_trimmed_2020.pdf",
     {"trimmed": "colorado_3_5_trimmed_2020.pdf",
      "only_subset": "colorado_3_5_trimmed_2020_only_subset.pdf"}),
    ("TX", "texas_all_standards_2022.pdf",
     {"trimmed": "texas_all_standards_2022_trimmed.pdf",
      "only_subset": "texas_all_standards_2022_only_subset.pdf"}),
    ("NV", "nevada_standards_2023.pdf",
     {"trimmed": "nevada_standards_2023_trimmed.pdf",
      "only_subset": "nevada_standards_2023_only_subset.pdf"}),
    ("KY", "kentucky_all_standards_2021.pdf",
     {"trimmed": "kentucky_all_standards_2021_trimmed.pdf",
      "only_subset": "kentucky_all_standards_2021_only_subset.pdf"}),
]

FUZZY_MIN = 0.90   # similarity floor for the fallback match
FOLIO_MIN_COVERAGE = 0.80   # of a tier's pages, before a printed range is published
FUZZY_CHARS = 600  # compare this many leading characters when falling back


def norm(text):
    return re.sub(r"\s+", " ", text).strip()


def page_texts(path):
    with fitz.open(path) as doc:
        return [norm(p.get_text()) for p in doc]


def match_page(text, full_texts, exact_index):
    """Return (1-based page in the published PDF, method) or (None, reason)."""
    if not text:
        return None, "blank"
    hit = exact_index.get(text)
    if hit is not None:
        return hit, "exact"
    head = text[:FUZZY_CHARS]
    best, best_ratio = None, 0.0
    for j, ft in enumerate(full_texts):
        if not ft:
            continue
        r = difflib.SequenceMatcher(None, head, ft[:FUZZY_CHARS]).ratio()
        if r > best_ratio:
            best, best_ratio = j + 1, r
    if best_ratio >= FUZZY_MIN:
        return best, f"fuzzy {best_ratio:.3f}"
    return None, f"no match (best {best_ratio:.3f})"


def compress(pages):
    """[1, 52, 53, 54, 65] -> '1, 52-54, 65'."""
    pages = sorted(p for p in pages if p is not None)
    out, i = [], 0
    while i < len(pages):
        j = i
        while j + 1 < len(pages) and pages[j + 1] == pages[j] + 1:
            j += 1
        out.append(str(pages[i]) if i == j else f"{pages[i]}-{pages[j]}")
        i = j + 1
    return ", ".join(out)


_FOLIO_RE = re.compile(r"^\d{1,3}$")


def printed_folios(path):
    """Map 1-based PDF page index -> the page number PRINTED on that page.

    ⚠️ These are two different numbers and confusing them is a live hazard, not
    a hypothetical one. A published PDF's front matter is usually unnumbered, so
    the folio runs behind the file index: Kentucky's PDF page 52 carries printed
    page **39**, a constant offset of 13 across 87 of its 120 pages. Kentucky
    also has the trap case — its subset includes PDF page 65, whose printed
    folio is **52**, the same number as the *first PDF page* of its trimmed
    range. A reader given "page 52" cannot tell which is meant.

    An annotator working from the issuing agency's copy reads the FOLIO; a
    reader opening the file in a viewer navigates by INDEX. Both must be
    published, and each must say which it is.

    Returns {pdf_index: folio_or_None}. A page with no recoverable folio (a
    cover, a full-bleed image) maps to None rather than being guessed.
    """
    out = {}
    with fitz.open(path) as doc:
        for i in range(doc.page_count):
            toks = doc[i].get_text().strip().split()
            folio = None
            # The folio sits at one end of the text; extraction order decides
            # which. Read only the first and last token, never the middle,
            # so a number inside a sentence cannot be mistaken for one.
            for tok in ([toks[0], toks[-1]] if toks else []):
                if _FOLIO_RE.fullmatch(tok):
                    folio = int(tok)
                    break
            out[i + 1] = folio
    return out


def folio_offsets(folios):
    """How far the printed folio runs behind the PDF index, and how stable."""
    diffs = [idx - f for idx, f in folios.items() if f is not None and 0 < f < 500]
    if not diffs:
        return {"offset": None, "constant": None, "pages_with_a_folio": 0}
    counts = Counter(diffs)
    top, n = counts.most_common(1)[0]
    return {
        "offset": top,
        "constant": len(counts) == 1,
        "pages_with_a_folio": len(diffs),
        "pages_agreeing_with_offset": n,
        "_reading": ("printed_folio = pdf_index - offset, on the pages that "
                     "carry a folio. `constant: false` means the document "
                     "renumbers somewhere and the per-page map must be used "
                     "rather than the offset."),
    }


def map_tier(full_texts, tier_path, folios=None):
    exact_index = {}
    for j, t in enumerate(full_texts):
        exact_index.setdefault(t, j + 1)
    tier_texts = page_texts(tier_path)
    mapped, methods, unmatched = [], {}, []
    for i, t in enumerate(tier_texts):
        page, how = match_page(t, full_texts, exact_index)
        mapped.append(page)
        methods[how.split(" ")[0]] = methods.get(how.split(" ")[0], 0) + 1
        if page is None:
            unmatched.append({"tier_page": i + 1, "reason": how, "text_head": t[:80]})
    result = {
        "pages": len(tier_texts),
        "published_pdf_pages_in_tier_order": mapped,
        "published_pages_in_tier_order": mapped,  # kept: existing readers
        "retained_ranges_pdf_index": compress(mapped),
        "retained_ranges": compress(mapped),      # kept: existing readers
        "unmatched_tier_pages": unmatched,
        "match_methods": methods,
    }
    if folios is not None:
        printed = [folios.get(p) if p is not None else None for p in mapped]
        result["printed_page_numbers_in_tier_order"] = printed
        # ⚠️ Publish a compressed printed range ONLY when the evidence supports
        # it. Folio extraction reads the first and last token of a page, which
        # works on some layouts and not others: it recovers 89 of Kentucky's 120
        # pages but 0 of Colorado's and 11 of Texas's 87. Compressing a partial
        # list yields a range that LOOKS complete and silently omits pages —
        # Nevada's came out "20, 22, 24, ...", every other page, which would be
        # read as a retained-page disclosure and is nothing of the kind.
        # So two conditions, both necessary: enough of the tier resolved, and
        # every resolved page agreeing on one offset. Otherwise the range is
        # withheld and the reason recorded, exactly as unmatched_tier_pages
        # withholds an unmatched page rather than guessing it.
        offs = {p - f for p, f in zip(mapped, printed)
                if p is not None and f is not None}
        resolved = sum(1 for f in printed if f is not None)
        coverage = resolved / len(printed) if printed else 0.0
        ok = len(offs) == 1 and coverage >= FOLIO_MIN_COVERAGE
        result["printed_numbering_reliability"] = {
            "pages_resolved": resolved,
            "pages_in_tier": len(printed),
            "coverage": round(coverage, 3),
            "distinct_offsets": sorted(offs),
            "published": ok,
            "reason": (None if ok else
                       ("folio extraction resolved too few pages "
                        f"({coverage:.0%} < {FOLIO_MIN_COVERAGE:.0%})"
                        if coverage < FOLIO_MIN_COVERAGE else
                        f"resolved pages disagree on the offset ({sorted(offs)}), "
                        "so a single printed range cannot be stated")),
        }
        result["retained_ranges_printed"] = (
            compress([f for f in printed if f is not None]) if ok else None)
        result["⚠️_two_numberings"] = (
            "`retained_ranges_pdf_index` counts pages in the PDF FILE; "
            "`retained_ranges_printed` is what is PRINTED on the page. They "
            "differ by the document's unnumbered front matter. Cite the printed "
            "range to someone reading the agency's copy, the PDF range to "
            "someone opening the file, and never present one as the other."
        )
    return result


def main():
    result = {
        "⚠️_TWO_PAGE_NUMBERINGS": (
            "Every tier records its retained pages TWICE, and the two are not "
            "interchangeable. `retained_ranges_pdf_index` counts pages in the "
            "PDF FILE, 1-based. `retained_ranges_printed` is the number PRINTED "
            "on the page. They differ by the document's unnumbered front "
            "matter: Kentucky's PDF page 52 carries printed page 39, an offset "
            "of 13. Kentucky also supplies the trap — its subset includes PDF "
            "page 65, whose printed folio is 52, the same number as the FIRST "
            "PDF page of its trimmed range, so 'page 52' is ambiguous on that "
            "document alone. Cite the PRINTED range to anyone reading the "
            "issuing agency's copy, the PDF range to anyone opening the file, "
            "and never present one as the other. `folio_offset` per state says "
            "whether the offset is constant."),
        "description": ("Retained page ranges per corpus tier, in BOTH the published "
                        "PDF's file numbering and the page numbers printed on the page. "
                        "Derived by matching each tier page's text "
                        "back to the published PDF (exact text match, then a "
                        f">= {FUZZY_MIN} similarity fallback on the first {FUZZY_CHARS} "
                        "characters). Deterministic; no model call, no annotation."),
        "generated_by": "paper/analysis/corpus_page_ranges.py",
        "regenerate_with": "python paper/analysis/corpus_page_ranges.py",
        "generated_on": date.today().isoformat(),
        "guardrail": ("Guardrail 3: trimming is disclosed with retained page ranges. "
                      "A tier page that matches no published page is listed under "
                      "unmatched_tier_pages rather than guessed."),
        "states": {},
    }
    for state, full, tiers in CORPUS:
        full_texts = page_texts(STD / full)
        folios = printed_folios(STD / full)
        entry = {"published_pdf": full, "published_pages": len(full_texts),
                 "folio_offset": folio_offsets(folios), "tiers": {}}
        for tier, fname in tiers.items():
            entry["tiers"][tier] = {"file": fname,
                                    **map_tier(full_texts, STD / fname, folios)}
        result["states"][state] = entry

    # Colorado: locate the 41pp Ages 3-5 document inside the 187pp birth-to-8
    # volume, so "drawn from a wider publication" is measured rather than said.
    b2e = page_texts(STD / "colorado_birth_to_8_2020.pdf")
    co = map_tier(b2e, STD / "colorado_3_5_trimmed_2020.pdf",
                  printed_folios(STD / "colorado_birth_to_8_2020.pdf"))
    result["states"]["CO"]["ages_3_5_within_birth_to_8"] = {
        "file": "colorado_birth_to_8_2020.pdf", "published_pages": len(b2e), **co}

    OUT.write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n")
    for st, e in result["states"].items():
        for tier, t in e["tiers"].items():
            print(f"{st:3} {tier:12} {t['pages']:3}pp")
            print(f"      pdf index : {t['retained_ranges_pdf_index']}")
            print(f"      printed   : {t.get('retained_ranges_printed')}")
    x = result["states"]["CO"]["ages_3_5_within_birth_to_8"]
    print(f"CO  3-5 in birth-to-8 -> {x['retained_ranges']} (unmatched {len(x['unmatched_tier_pages'])})")
    print("wrote", OUT)


if __name__ == "__main__":
    main()
