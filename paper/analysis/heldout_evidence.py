"""Evidence artifacts for arXiv paper Task 2 (held-out generalization: NV, KY).

The suite reports in `paper/results/task2_20260816/` give the headline numbers.
This script produces the four things those reports cannot say for themselves,
each of which a paper claim depends on:

1. **Annotation coverage.** Guardrail 8: the detector suite's raw "precision"
   is bounded above by `n_golden / n_detected_in_annotated_domains`, so on a
   spot-check golden it measures annotation coverage, not correctness. The
   held-out goldens are much denser than the golden four (41 and 44 elements
   vs 5-25), so this ratio has to be recomputed rather than assumed — KY's
   golden turns out to be EXHAUSTIVE, which makes its precision a real number
   and is the single most load-bearing fact in the generalization table.

2. **A drafted false-positive audit of every in-scope extra** (Task 1b
   methodology, extended to the held-out states per Task 2 step 4). Each
   unmatched in-annotated-domain detection is classified, and — unlike a
   read-by-eye audit — the classification is *checked against the extraction
   text*, so "real document content" is a verified claim and not an
   impression. This is a FIRST PASS drafted by Claude; Emily is the annotator
   of record and must sign off before any number here reaches the paper.

3. **The NV domain-code diagnosis.** CLAUDE.md predicts the exact failure mode
   ("If NV domains still come back as SCIE/TECH while the sub_strands are
   right, this citation is the first thing to check") and this records whether
   each domain's `source_text` actually cites the line carrying its code.

4. **The KY indicator-code qualification history.** The parser intermittently
   emits an indicator code that is NOT qualified by its parent chain (bare
   `TCPHS` instead of `HMW.1.1.TCPHS`), which writes a malformed Aurora
   primary key. Rate estimation needs the whole recorded history, not one run.

Usage (from repo root):
    python paper/analysis/heldout_evidence.py \
        --detector-review-dir paper/results/task2_20260816/review_detector \
        --out paper/results/task2_20260816/heldout_evidence.json
"""

from __future__ import annotations

import argparse
import glob
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT))

from evaluation.eval_common import _norm  # noqa: E402
from els_pipeline.detector import (  # noqa: E402
    _DERIVABLE_CODE_RE,
    _is_code_grounded,
    derive_code_from_title,
)

STATES = ["NV", "KY"]


def _extraction_text(state: str, outputs_dir: Path) -> str:
    """Whitespace-folded full text of the extraction the detector ran on.

    Folded because Textract emits hard line breaks mid-sentence, so a verbatim
    title legitimately spans lines in the source and a raw substring test would
    report real content as absent."""
    ex = json.loads((outputs_dir / f"{state}-extraction.json").read_text())
    blocks = ex.get("text_blocks") or ex.get("blocks") or []
    return re.sub(r"\s+", " ", "\n".join(b.get("text", "") for b in blocks))


def annotation_coverage(state: str, review_dir: Path) -> dict:
    golden = json.loads(
        (ROOT / "evaluation" / "ground_truth_detector" / f"{state}.json").read_text()
    )["elements"]
    detected = json.loads((review_dir / state / f"{state}-detected.json").read_text())
    ann = {_norm(e["title"]) for e in golden if e.get("level") == "domain"}
    cur, n_in = None, 0
    for e in detected:
        if e.get("level") == "domain":
            cur = _norm(e.get("title", ""))
        if cur in ann:
            n_in += 1
    return {
        "n_golden": len(golden),
        "n_detected_total": len(detected),
        "n_detected_in_annotated_domains": n_in,
        "precision_ceiling_from_annotation_coverage": round(len(golden) / n_in, 4) if n_in else None,
        "golden_is_exhaustive": n_in == len(golden),
    }


def _greedy_spans(title: str, text: str) -> list:
    """Decompose a title into the fewest contiguous spans that each occur in the
    text, longest-first. A single span means the title is verbatim; several mean
    it is present but split (column interleaving in a multi-column table); a word
    that appears in no span at all is the strong signal.

    Deliberately reported rather than thresholded. Word-level coverage does NOT
    separate a real split title from an invented one - every individual word of
    the fabricated NV tail "with adult guidance" occurs somewhere in the
    document, so a coverage test would clear it. The hallucination verdict rests
    on structural evidence (a duplicate code whose twin has a truncated
    source_text), not on this decomposition."""
    words = [w for w in title.split(" ") if w]
    spans, i = [], 0
    while i < len(words):
        j = len(words)
        while j > i and " ".join(words[i:j]) not in text:
            j -= 1
        if j == i:
            spans.append({"span": words[i], "found": False})
            i += 1
        else:
            spans.append({"span": " ".join(words[i:j]), "found": True})
            i = j
    return spans


def fp_audit(state: str, review_dir: Path, outputs_dir: Path) -> dict:
    """Classify every in-scope extra, verifying each verdict against the text.

    Three verdicts, and the distinction between the first two matters because
    only one of them is a defect:

    - `real_repeat_of_matched` — the element is a second detection of something
      already matched. NV reprints each "<Domain> Standard N:" heading on every
      page spread it governs, so these are correct readings of a real repeated
      heading, not inventions. The parser collapses them.
    - `real_unannotated` — real document content the spot-check golden simply
      did not annotate. Verified by finding the title in the extraction.
    - `hallucinated` — the title is NOT in the extraction. This is the only
      verdict that counts against detector precision.
    """
    review = json.loads((review_dir / state / f"{state}-review.json").read_text())
    text = _extraction_text(state, outputs_dir)
    matched_keys = {
        (m["detected"].get("level"), _norm(m["detected"].get("title", "")))
        for m in review["matched"]
    }

    verdicts = []
    for e in review["extra_in_detected"]:
        title = e.get("title", "")
        key = (e.get("level"), _norm(title))
        # A title ending in '.' is a sentence; the probe drops the final period
        # so a transcription that keeps or drops it is not scored as absent.
        probe = re.sub(r"\s+", " ", title).strip().rstrip(".")
        contiguous = probe in text
        if key in matched_keys:
            verdict, reason = "real_repeat_of_matched", (
                "second detection of an element already matched to a golden; the "
                "document reprints this heading on another page. Verified "
                "STRUCTURALLY (same level and title as a matched element), which "
                "does not depend on the text probe below."
            )
        elif contiguous:
            verdict, reason = "real_unannotated", (
                "title found verbatim and contiguously in the extraction; real "
                "document content the spot-check golden did not annotate"
            )
        else:
            verdict, reason = "hallucinated", (
                "title is not contiguous in the extraction AND does not repeat a "
                "matched element - see structural_evidence"
            )
        row = {
            "state": state,
            "level": e.get("level"),
            "code": e.get("code"),
            "title": title,
            "page": e.get("source_page"),
            "title_contiguous_in_extraction": contiguous,
            "verdict": verdict,
            "reason": reason,
            "verified_by": "claude-first-pass-UNSIGNED",
        }
        if not contiguous:
            # A title can be non-contiguous WITHOUT being invented: NV's
            # multi-column tables interleave columns in reading order, so a real
            # heading can be split by text from the neighbouring column. The
            # sub_strand "Exploration, Observation, and Hypotheses" is exactly
            # this - "Exploration, Observation" and "and Hypotheses" each occur
            # twice, separated by a Supportive-Practices cell. Recording the
            # decomposition stops a reviewer reading `false` as "fabricated".
            row["title_spans_found_in_order"] = _greedy_spans(probe, text)
            row["needs_human_check"] = verdict == "hallucinated"
        verdicts.append(row)

    cov = annotation_coverage(state, review_dir)
    n_hall = sum(1 for v in verdicts if v["verdict"] == "hallucinated")
    n_in = cov["n_detected_in_annotated_domains"]
    return {
        "n_in_scope_detections": n_in,
        "n_extras_audited": len(verdicts),
        "counts_by_verdict": {
            v: sum(1 for x in verdicts if x["verdict"] == v)
            for v in ("real_repeat_of_matched", "real_unannotated", "hallucinated")
        },
        "hallucination_count": n_hall,
        "verified_precision": round((n_in - n_hall) / n_in, 4) if n_in else None,
        "verified_precision_definition": (
            "(in-scope detections - hallucinated) / in-scope detections. Counts a "
            "correct re-detection of a repeated heading as real, because it is."
        ),
        "verdicts": verdicts,
    }


def nv_domain_code_diagnosis(review_dir: Path) -> dict:
    """Is each NV domain's code grounded in its own `source_text`?

    `detector._resolve_code` recomputes any uppercase-only code that is not
    found in the element's own `source_text`, so rule 4's "recover the code
    from a caption or from the descendants' shared prefix" clause only sticks
    if the model ALSO cites the line it recovered the code from. CLAUDE.md
    names this as the first thing to check when NV domains regress.

    Both guards are imported from `detector.py` rather than reimplemented, so
    this cannot drift from what actually ran. That matters here: a hand-rolled
    substring test gets these wrong, because `_is_code_grounded` is
    word-bounded and case-SENSITIVE — the letter S is genuinely grounded in
    Science's intro prose (which contains the quoted 'S' of STEAM) while the
    letter T is NOT grounded in the bare word "Technology"."""
    detected = json.loads((review_dir / "NV" / "NV-detected.json").read_text())
    golden = {
        e["title"]: e.get("code")
        for e in json.loads(
            (ROOT / "evaluation" / "ground_truth_detector" / "NV.json").read_text()
        )["elements"]
        if e.get("level") == "domain"
    }
    out = []
    for e in detected:
        if e.get("level") != "domain":
            continue
        src = e.get("source_text") or ""
        want = golden.get(e.get("title"))
        got = e.get("code")
        out.append({
            "title": e.get("title"),
            "golden_code": want,
            "detected_code": got,
            "correct": want == got,
            # Would _resolve_code have considered recomputing this code at all?
            "detected_code_has_derivable_shape": bool(
                got and _DERIVABLE_CODE_RE.match(str(got))
            ),
            "detected_code_grounded": _is_code_grounded(got, src),
            # Had the model recovered the document code, would citing THIS
            # source_text have been enough to protect it from recomputation?
            "golden_code_would_be_grounded_in_this_source_text": _is_code_grounded(want, src),
            "derive_code_from_title_would_yield": derive_code_from_title(e.get("title")),
            "source_text_excerpt": src[:120],
        })
    return {"domains": out}


def ky_code_qualification_history(outputs_glob: str) -> dict:
    """How often does a KY indicator code come out UNQUALIFIED across every
    recorded production run? An indicator code with no '.' carries no parent
    chain, so `standard_id` loses its namespace."""
    runs = []
    for f in sorted(glob.glob(outputs_glob)):
        d = json.loads(Path(f).read_text())
        stds = d.get("indicators", [])
        bad = [
            s for s in stds
            if "." not in (((s.get("indicator") or {}).get("code")) or "")
        ]
        runs.append({
            "file": f,
            "parsing_timestamp": d.get("parsing_timestamp"),
            "n_standards": len(stds),
            "n_unqualified_indicator_codes": len(bad),
            "unqualified_standard_ids": [s.get("standard_id") for s in bad],
        })
    n_fired = sum(1 for r in runs if r["n_unqualified_indicator_codes"])
    return {
        "runs": runs,
        "n_runs": len(runs),
        "n_runs_with_at_least_one_unqualified_code": n_fired,
        "note": (
            "These are the DEPLOYED BATCHED production runs only. The Task 2 "
            "direct-path eval run on the 08-16-26 detection is a further "
            "observation and fired (4 unqualified, all in the HMW domain), "
            "while the batched run over that same detection did not."
        ),
    }


def ky_direct_path_cache_runs(cache_glob: str) -> dict:
    """Same-session direct-path parser runs on the frozen KY detection.

    `run_parser_cached` writes every run to `evaluation/.cache/` keyed by
    (state, detection-hash, code-hash, suffix), so the cache is an accidental
    but faithful record of independent runs over identical input. Grouping by
    code hash lets the intermittency be stated per code version instead of
    pooled across versions that no longer exist.

    The suffix matters: '' is the run the suite GRADED, 'stab-N' are the runs
    `measure_stability` compared against each other. `measure_stability` does
    NOT include the graded run in its comparison, so a defect present in the
    graded output can coexist with a reported disagreement rate of 0.000 —
    which is exactly what happened on 2026-08-16."""
    runs = []
    for f in sorted(glob.glob(cache_glob)):
        name = Path(f).name
        # parser-<STATE>-<detection hash>-<code hash>-<suffix>.json
        stem = name[: -len(".json")]
        parts = stem.split("-")
        detection_hash = parts[2] if len(parts) > 2 else None
        code_hash = parts[3] if len(parts) > 3 else None
        suffix = "-".join(parts[4:]) or "(graded)"
        stds = json.loads(Path(f).read_text())
        bad = [
            s for s in stds
            if "." not in (((s.get("indicator") or {}).get("code")) or "")
        ]
        runs.append({
            "file": name,
            "detection_hash": detection_hash,
            "code_hash": code_hash,
            "run": suffix,
            "n_standards": len(stds),
            "n_unqualified_indicator_codes": len(bad),
            "unqualified_standard_ids": [s.get("standard_id") for s in bad],
        })
    by_code: dict = {}
    for r in runs:
        b = by_code.setdefault(r["code_hash"], {"n_runs": 0, "n_fired": 0, "max_affected": 0})
        b["n_runs"] += 1
        if r["n_unqualified_indicator_codes"]:
            b["n_fired"] += 1
        b["max_affected"] = max(b["max_affected"], r["n_unqualified_indicator_codes"])
    return {"runs": runs, "by_code_hash": by_code}


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--detector-review-dir", type=Path,
                    default=ROOT / "paper/results/task2_20260816/review_detector")
    ap.add_argument("--outputs-dir", type=Path, default=ROOT / "outputs/08-16-26")
    ap.add_argument("--ky-parsing-glob", default=str(ROOT / "outputs/*/KY-parsing.json"))
    ap.add_argument("--ky-cache-glob", default=str(ROOT / "evaluation/.cache/parser-KY-*.json"))
    ap.add_argument("--out", type=Path,
                    default=ROOT / "paper/results/task2_20260816/heldout_evidence.json")
    args = ap.parse_args()

    out = {
        "annotation_coverage": {
            st: annotation_coverage(st, args.detector_review_dir) for st in STATES
        },
        "fp_audit_first_pass": {
            st: fp_audit(st, args.detector_review_dir, args.outputs_dir) for st in STATES
        },
        "nv_domain_code_diagnosis": nv_domain_code_diagnosis(args.detector_review_dir),
        "ky_code_qualification_history": ky_code_qualification_history(args.ky_parsing_glob),
        "ky_direct_path_cache_runs": ky_direct_path_cache_runs(args.ky_cache_glob),
    }
    args.out.write_text(json.dumps(out, indent=2))
    print(f"Wrote {args.out}")


if __name__ == "__main__":
    main()
