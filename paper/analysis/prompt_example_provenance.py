"""Itemize where the prompts' worked examples come from (arXiv paper Task 12).

Why this exists
---------------
The paper claims the system carries no per-state rule. That is true of the
Python -- the migration that removed per-state logic is documented and enforced
-- but it is not the whole truth of the PROMPTS, which carry worked examples,
and a reviewer who reads Appendix A will notice before anyone else does. The
honest version of the claim is "no per-state code path, and here is exactly
what the prompts do carry", which costs the paper nothing and removes the
objection entirely.

Getting it right needs a measurement rather than a recollection, because the
answer turned out to be larger than expected: the examples are not confined to
the four development states. Two of the strings in the detector's abbreviation
rule are Kentucky's, and Kentucky is one of the two states the paper reports as
held out.

Method
------
For every state golden, take each annotated ``title`` of at least
``MIN_TITLE_CHARS`` characters and ask whether it appears verbatim (case-folded)
in the prompt source. Then split the hits two ways, because they are not equally
informative:

  * **shared** -- the same title is annotated in more than one state's golden.
    "Approaches to Learning" and "Social and Emotional Development" are domain
    names many states use; their presence in a prompt is not evidence that any
    particular document was consulted.
  * **distinctive** -- the title is annotated in exactly one state's golden.
    These are the ones that carry provenance, and a long indicator sentence is
    about as distinctive as a string gets.

The check reads the prompt SOURCE, so it covers the prompts as shipped rather
than as reproduced in the appendix, and it cannot go stale when the appendix is
regenerated.

⚠️ This is evidence about provenance, not a verdict about leakage. A shared
domain name proves nothing. A distinctive string shows the document was in view
when the rule was written, which is ordinary few-shot practice for a
development state and is a disclosure question for a held-out one. What it
should NOT do is stay unstated.

Usage:
    python -m paper.analysis.prompt_example_provenance \
        --out paper/results/task12_YYYYMMDD/prompt_example_provenance.json
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from collections import defaultdict
from pathlib import Path
from typing import Dict, List, Set

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))

PROMPT_SOURCES = [
    REPO / "src" / "els_pipeline" / "detector.py",
    REPO / "src" / "els_pipeline" / "parser.py",
]
GOLDEN_DIRS = [
    REPO / "evaluation" / "ground_truth_detector",
    REPO / "evaluation" / "ground_truth_parser",
]
# Below this length a title is too short to carry provenance: "Vocabulary" or
# "Science" would hit on coincidence, not because a document was consulted.
MIN_TITLE_CHARS = 12

DEVELOPMENT_STATES = {"AZ", "CA", "CO", "TX"}
HELD_OUT_STATES = {"NV", "KY"}


def _titles(path: Path) -> Set[str]:
    """Every annotated title in a golden file, at any nesting depth."""
    out: Set[str] = set()

    def walk(node):
        if isinstance(node, dict):
            t = node.get("title")
            if isinstance(t, str) and len(t.strip().rstrip(".")) >= MIN_TITLE_CHARS:
                out.add(t.strip().rstrip("."))
            for v in node.values():
                walk(v)
        elif isinstance(node, list):
            for v in node:
                walk(v)

    walk(json.loads(path.read_text()))
    return out


def collect() -> dict:
    prompt_text = "\n".join(p.read_text() for p in PROMPT_SOURCES).lower()

    per_state: Dict[str, Set[str]] = defaultdict(set)
    for d in GOLDEN_DIRS:
        for f in sorted(d.glob("*.json")):
            # ⚠️ Only bare two-letter state goldens count, and the failure mode
            # is SILENT. Any second file annotating the SAME state — a draft, a
            # tier-scoped golden, a _provenance sibling — makes that state's
            # strings look "shared with another state" and collapses the
            # distinctive count. This has now broken twice: once when
            # KY_trimmed.DRAFT.json was added and once when it was renamed to
            # KY_trimmed.json, each time taking the held-out total from 5 to 0
            # with no error raised anywhere. Hence a shape rule, not a list.
            if not re.fullmatch(r"[A-Z]{2}", f.stem):
                continue
            per_state[f.stem] |= _titles(f)

    # A title annotated by more than one state is a shared vocabulary item.
    owners: Dict[str, Set[str]] = defaultdict(set)
    for st, titles in per_state.items():
        for t in titles:
            owners[t].add(st)

    states: Dict[str, dict] = {}
    for st, titles in sorted(per_state.items()):
        hits = sorted(t for t in titles if t.lower() in prompt_text)
        distinctive = [t for t in hits if len(owners[t]) == 1]
        shared = [t for t in hits if len(owners[t]) > 1]
        states[st] = {
            "role": ("development" if st in DEVELOPMENT_STATES
                     else "held-out" if st in HELD_OUT_STATES else "unknown"),
            "annotated_titles": len(titles),
            "titles_appearing_in_prompts": len(hits),
            "distinctive_to_this_state": sorted(distinctive),
            "shared_with_another_state": sorted(shared),
        }

    dev_distinct = sum(len(v["distinctive_to_this_state"])
                       for k, v in states.items() if k in DEVELOPMENT_STATES)
    held_distinct = sum(len(v["distinctive_to_this_state"])
                        for k, v in states.items() if k in HELD_OUT_STATES)
    return {
        "method": (
            "Every annotated golden title of >= "
            f"{MIN_TITLE_CHARS} characters, checked case-folded against the "
            "verbatim source of the detection and parsing prompts. A title "
            "annotated by more than one state is reported as SHARED (a domain "
            "name many states use, which carries no provenance); a title "
            "annotated by exactly one is reported as DISTINCTIVE."
        ),
        "prompt_sources": [str(p.relative_to(REPO)) for p in PROMPT_SOURCES],
        "min_title_chars": MIN_TITLE_CHARS,
        "states": states,
        "totals": {
            "distinctive_strings_from_development_states": dev_distinct,
            "distinctive_strings_from_held_out_states": held_distinct,
        },
        "_reading": (
            "Shared strings are not evidence of anything. Distinctive strings "
            "show the document was in view when the rule was written: ordinary "
            "few-shot practice for a development state, and a disclosure "
            "question for a held-out one."
        ),
    }


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--out", help="path to write the JSON record")
    args = ap.parse_args()
    res = collect()
    for st, v in res["states"].items():
        d, sh = v["distinctive_to_this_state"], v["shared_with_another_state"]
        print(f"{st} ({v['role']}): {len(d)} distinctive, {len(sh)} shared, "
              f"of {v['annotated_titles']} annotated titles")
        for t in d:
            print(f"    DISTINCTIVE  {t!r}")
        for t in sh:
            print(f"    shared       {t!r}")
    print(f"\ntotals: {json.dumps(res['totals'])}")
    if args.out:
        p = Path(args.out)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(json.dumps(res, indent=2, ensure_ascii=False))
        print(f"wrote {p}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
