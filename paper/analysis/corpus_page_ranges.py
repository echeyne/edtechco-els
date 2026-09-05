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


def map_tier(full_texts, tier_path):
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
    return {
        "pages": len(tier_texts),
        "published_pages_in_tier_order": mapped,
        "retained_ranges": compress(mapped),
        "unmatched_tier_pages": unmatched,
        "match_methods": methods,
    }


def main():
    result = {
        "description": ("Retained page ranges per corpus tier, expressed in the PUBLISHED "
                        "PDF's page numbering. Derived by matching each tier page's text "
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
        entry = {"published_pdf": full, "published_pages": len(full_texts), "tiers": {}}
        for tier, fname in tiers.items():
            entry["tiers"][tier] = {"file": fname, **map_tier(full_texts, STD / fname)}
        result["states"][state] = entry

    # Colorado: locate the 41pp Ages 3-5 document inside the 187pp birth-to-8
    # volume, so "drawn from a wider publication" is measured rather than said.
    b2e = page_texts(STD / "colorado_birth_to_8_2020.pdf")
    co = map_tier(b2e, STD / "colorado_3_5_trimmed_2020.pdf")
    result["states"]["CO"]["ages_3_5_within_birth_to_8"] = {
        "file": "colorado_birth_to_8_2020.pdf", "published_pages": len(b2e), **co}

    OUT.write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n")
    for st, e in result["states"].items():
        for tier, t in e["tiers"].items():
            print(f"{st:3} {tier:12} {t['pages']:3}pp -> {t['retained_ranges']}"
                  f"  ({t['match_methods']}, unmatched {len(t['unmatched_tier_pages'])})")
    x = result["states"]["CO"]["ages_3_5_within_birth_to_8"]
    print(f"CO  3-5 in birth-to-8 -> {x['retained_ranges']} (unmatched {len(x['unmatched_tier_pages'])})")
    print("wrote", OUT)


if __name__ == "__main__":
    main()
