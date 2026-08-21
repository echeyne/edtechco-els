"""Compare the DIRECT-path detector output against the DEPLOYED BATCHED output.

Why this exists: the two eval suites do not exercise the same code path.
`eval_detector` calls `detect_structure` in-process — the direct path, one
chunk loop in one process. Production runs `detection_batching.py`: a prepare
step that infers the depth map once and persists it to S3, a Step Functions Map
over chunk batches, and a merge. `eval_parser` then grades the parser on the
BATCHED output (`outputs/<run>/{STATE}-detection.json`), so the paper's parser
numbers and its detector numbers rest on two different detections of the same
document.

That is only sound if the two paths converge. This script measures whether they
do, per state, and records it as JSON so the claim is regenerable rather than
asserted.

Matching mirrors `eval_detector._match_key` minus the domain tag: an element is
identified by (level, normalized title, normalized age_band). Codes are compared
separately over the elements both paths agree exist, for the same reason
`eval_detector` grades codes over matched pairs only — a code disagreement is a
different defect from a missing element and must not be able to masquerade as
one.

Usage (from repo root):
    python paper/analysis/compare_direct_vs_batched.py \
        --direct-review-dir paper/results/task1_20260816/review_detector \
        --batched-dir outputs/08-16-26 \
        --out paper/results/task1_20260816/direct_vs_batched.json
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT))

from evaluation.eval_common import _norm, _norm_age_band  # noqa: E402

STATES = ["AZ", "CA", "CO", "TX"]

_ENUM_RE = re.compile(r"^HierarchyLevelEnum\.([A-Z_]+)$")


def norm_level(v: str) -> str:
    m = _ENUM_RE.match(str(v))
    return m.group(1).lower() if m else str(v)


def key(e: dict):
    return (norm_level(e.get("level", "")), _norm(e.get("title", "")),
            _norm_age_band(e.get("age_band")))


def load(path: Path) -> list:
    data = json.loads(path.read_text())
    return data if isinstance(data, list) else data.get("elements", [])


def compare(direct: list, batched: list) -> dict:
    dk, bk = Counter(key(e) for e in direct), Counter(key(e) for e in batched)
    only_direct = sorted((dk - bk).elements())
    only_batched = sorted((bk - dk).elements())

    # Codes, over the elements both paths produced. First occurrence wins on
    # each side; duplicates are already visible in the count deltas above.
    d_code, b_code = {}, {}
    for e in direct:
        d_code.setdefault(key(e), e.get("code"))
    for e in batched:
        b_code.setdefault(key(e), e.get("code"))
    code_disagreements = [
        {"key": k, "direct_code": d_code[k], "batched_code": b_code[k]}
        for k in sorted(set(d_code) & set(b_code))
        if d_code[k] != b_code[k]
    ]
    shared = sum((dk & bk).values())
    union = sum((dk | bk).values())
    return {
        "n_direct": len(direct),
        "n_batched": len(batched),
        "levels_direct": dict(Counter(norm_level(e.get("level", "")) for e in direct)),
        "levels_batched": dict(Counter(norm_level(e.get("level", "")) for e in batched)),
        "shared_elements": shared,
        "jaccard": round(shared / union, 4) if union else None,
        "only_in_direct": [list(k) for k in only_direct],
        "only_in_batched": [list(k) for k in only_batched],
        "code_disagreements_on_shared": [
            {"key": list(c["key"]), "direct_code": c["direct_code"],
             "batched_code": c["batched_code"]}
            for c in code_disagreements
        ],
    }


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--direct-review-dir", type=Path, required=True,
                    help="eval_detector --output-dir, holding {STATE}/{STATE}-detected.json")
    ap.add_argument("--batched-dir", type=Path, required=True,
                    help="outputs/<run> holding the deployed {STATE}-detection.json")
    ap.add_argument("--state", action="append")
    ap.add_argument("--out", type=Path, required=True)
    args = ap.parse_args()

    out = {}
    for st in (args.state or STATES):
        d_path = args.direct_review_dir / st / f"{st}-detected.json"
        b_path = args.batched_dir / f"{st}-detection.json"
        if not d_path.exists() or not b_path.exists():
            out[st] = {"skipped": f"missing {d_path if not d_path.exists() else b_path}"}
            continue
        out[st] = compare(load(d_path), load(b_path))

    args.out.write_text(json.dumps(out, indent=2))
    print(f"Wrote {args.out}")
    for st, r in out.items():
        if "skipped" in r:
            print(f"  {st}: {r['skipped']}")
            continue
        print(f"  {st}: direct={r['n_direct']} batched={r['n_batched']} "
              f"shared={r['shared_elements']} jaccard={r['jaccard']} "
              f"only_direct={len(r['only_in_direct'])} only_batched={len(r['only_in_batched'])} "
              f"code_disagreements={len(r['code_disagreements_on_shared'])}")


if __name__ == "__main__":
    main()
