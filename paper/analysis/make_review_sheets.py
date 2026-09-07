"""Build the ``age_band`` review sheet for the Task 9 scale grade.

Produces ``{STATE}_age_band_review.md`` -- the golden elements the larger run
found at the right level, page and title but stamped with a different
``age_band``. That single field accounts for every anomaly Task 9 found (see
``paper/results/task9_20260905/findings.md``), so it is the one verdict the
measurement cannot make for itself.

⚠️ **Scope, 2026-09-06.** This script used to emit two further sheets per state
-- an unannotated-detection worklist and a full annotation listing -- for both
KY and CO. Both are retired:

  * Kentucky is being graded exhaustively by the author directly against the
    PDF, which supersedes any worklist derived from system output. The subset
    golden was in any case found to have nothing missing: no element appears in
    any of the 13 KY detection files that it lacks, and no block of text on
    subset pages 2-8 is unaccounted for by one of its titles or descriptions.
  * Colorado is NOT being annotated exhaustively. Its golden stays a
    seven-element spot check, so its precision stays a coverage artifact and
    there is no worklist to work.

Usage:
    python -m paper.analysis.make_review_sheets --out paper/results/task9_20260905/review
"""
from __future__ import annotations

import argparse
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))

from evaluation.eval_detector import _title_key  # noqa: E402

RESULTS = REPO / "paper" / "results" / "task9_20260905"
DETECTION_DIR = REPO / "outputs" / "scale-08-29-26"
GOLDEN_DIR = REPO / "evaluation" / "ground_truth_detector"


def _fmt(e: dict, indent: str = "") -> str:
    desc = (e.get("description") or "").strip()
    if len(desc) > 220:
        desc = desc[:220] + "…"
    src = " ".join((e.get("source_text") or "").split())
    if len(src) > 160:
        src = src[:160] + "…"
    out = [
        f"{indent}- **{e.get('level')}** · code `{e.get('code')}`"
        f" · age_band `{e.get('age_band')}`",
        f"{indent}  - title: {e.get('title')}",
    ]
    if desc:
        out.append(f"{indent}  - description: {desc}")
    if src:
        out.append(f"{indent}  - source_text: `{src}`")
    return "\n".join(out)


def unannotated_sheet(state: str, res: dict, run: list, golden: list) -> str:
    strict = res["arms"]["page_tolerance_0"]
    work = strict["unmatched_adjudication"]["annotation_worklist"]
    # map target-tier page back to the source-tier page the golden uses
    tgt_to_src = {v: int(k) for k, v in
                  res["page_window"]["mapping_source_to_target"].items()}
    by_page = defaultdict(list)
    for row in work:
        by_page[row["target_tier_page"]].append(row)
    # index the full run so we can print descriptions the worklist truncated
    run_ix = {}
    for d in run:
        run_ix.setdefault(
            (d.get("source_page"), (d.get("level") or "").strip(),
             _title_key(d)), d)
    gold_by_page = defaultdict(list)
    for g in golden:
        gold_by_page[g.get("source_page")].append(g)

    # A worklist row that shares (level, title) with a golden element on the
    # same page is not an annotation gap -- it is a SECOND COPY of an element
    # the golden already covers, surviving the merge because the copies
    # disagree on age_band. Those need a different verdict from a genuinely
    # unannotated element, so they are labelled rather than mixed in.
    gold_keys = {((g.get("level") or "").strip(), _title_key(g)) for g in golden}
    for row in work:
        row["_is_duplicate"] = (
            ((row.get("level") or "").strip(),
             _title_key({"title": row.get("title")})) in gold_keys)
    n_dup = sum(1 for r in work if r["_is_duplicate"])

    n = len(work)
    L = [
        f"# {state} — detections on annotated pages that the golden does not cover",
        "",
        f"**{n} rows**, of which **{n_dup} are marked `DUPLICATE`** — they share"
        f" a level and title with an element the golden already annotates on the"
        f" same page, and survive the merge only because the two copies disagree"
        f" on `age_band`. Every row is grounded in the `_only_subset` extraction"
        f" (**0** hallucination candidates for this state).",
        "",
        "## What each kind means",
        "",
        "**`DUPLICATE` rows are not an annotation question.** The golden is"
        " right and complete for them; the run emitted the element twice."
        " They need no verdict from you unless you disagree that they are"
        " duplicates — they are a detector finding, already written up.",
        "",
        "**Unmarked rows are the annotation question.** The annotation guide"
        " asks for *content-exhaustive* — every structural element the subset"
        " prints. If an unmarked row is a real structural element, the golden"
        " under-annotates, and a recall of 1.000 measured against it has an"
        " incomplete denominator.",
        "",
        "## How to use this sheet",
        "",
        "For each **unmarked** row, mark one:",
        "",
        "- `[ADD]` — a real structural element the golden should annotate."
        " ⚠️ Adding it changes the golden, which changes **every** recorded"
        " detector number for this state, including the headline recall.",
        "- `[LEVEL]` — real text emitted at the wrong level. A detector defect.",
        "- `[SCOPE]` — correctly left out of the golden. Say why, so the"
        " annotation guide can record the rule.",
        "",
        "---",
        "",
    ]
    for page in sorted(by_page):
        src_page = tgt_to_src.get(page)
        L += [
            f"## trimmed p{page}  (= `_only_subset` p{src_page})",
            "",
            f"### Already annotated on this page ({len(gold_by_page.get(src_page, []))})",
            "",
        ]
        for g in gold_by_page.get(src_page, []):
            L.append(f"- `{g.get('test_case_id')}` **{g.get('level')}** "
                     f"code `{g.get('code')}` — {g.get('title')}")
        L += ["", f"### Not accounted for ({len(by_page[page])})", ""]
        for row in by_page[page]:
            full = run_ix.get(
                (page, (row.get("level") or "").strip(),
                 _title_key({"title": row.get("title")}))) or row
            if row.get("_is_duplicate"):
                L.append("**`DUPLICATE`** — second copy of an element already"
                         " annotated on this page; no verdict needed.")
            else:
                L.append("`[ ] ADD  [ ] LEVEL  [ ] SCOPE`")
            L.append(_fmt(full))
            L.append("")
        L.append("---")
        L.append("")
    return "\n".join(L)


def age_band_sheet(state: str, res: dict) -> str:
    strict = res["arms"]["page_tolerance_0"]
    drift = strict["recall_decomposition"]["age_band_attribution_drift"]
    cons = strict["age_band_consistency"]
    if not drift:
        return ""
    L = [
        f"# {state} — age_band attribution drift",
        "",
        f"**{len(drift)} golden elements** were found by the larger run at the"
        " right level, on the right page, with the right title, but carrying a"
        " different `age_band` than the golden annotates. Because `_match_key`"
        " is `(domain, level, title, age_band)`, each of these fails the strict"
        " key — and together they are the *entire* difference between this"
        f" state's strict recall and its 1.000 recall by level and title.",
        "",
        "## The thing that makes this a real question",
        "",
        "It is **not** a clean per-page decision. Pages emitting more than one"
        " value in the graded window:",
        "",
        "| trimmed page | values emitted |",
        "|---|---|",
    ]
    for p, counts in cons["pages_emitting_more_than_one_value"].items():
        L.append(f"| p{p} | " + ", ".join(f"`{k}` ×{v}" for k, v in counts.items()) + " |")
    L += [
        "",
        f"Across the whole window: "
        + ", ".join(f"`{k}` ×{v}" for k, v in cons["distinct_values_in_window"].items())
        + ".",
        "",
        "So the run is emitting two spellings of one fact about a page. That is"
        " the shape `models._blank_to_none` and `_canonicalize_code` exist to"
        " absorb, and per CLAUDE.md's standing argument it is the shape a prompt"
        " rule can reduce but not zero.",
        "",
        "## ✅ VERDICT: `RUN` — decided 2026-09-06 by Emily Cheyne",
        "",
        "**The run is over-attributing; the golden is right and does not"
        " change.** Reported as a detector defect at scale (§8), with no code"
        " change: `code_version_hash` stays at `14374dba` and no recorded"
        " result is invalidated.",
        "",
        "Three things support it, none of them in the table below:",
        "",
        "1. **The golden already calls the banner page furniture.** KY's"
        " `expected_depth_map` describes depth 1 as a domain name in the page"
        " header, *above* a `THREE AND FOUR YEAR OLDS` banner — context for the"
        " heading, not a property of it.",
        "2. **The band already has a home, one stage later.**"
        " `ground_truth_parser/KY.json` sets `default_age_band: 36-60` and"
        " `parse_hierarchy` applies it as a document-level default. The"
        " detector stamping the banner onto elements is a second, competing"
        " mechanism for the same fact.",
        "3. **The goldens draw a consistent line across all six states.** Every"
        " state whose detector golden annotates an `age_band` — CA"
        " (`Early`/`Later`), TX (`PK3`/`PK4`) — has one because a side-by-side"
        " COLUMN distinguishes siblings. KY, CO, NV and AZ annotate `null`"
        " throughout. A banner applying to every element on the page carries no"
        " distinguishing information.",
        "",
        "⚠️ **What this decision does NOT do.** It leaves the downstream"
        " consequences in place as documented limitations: 11 detector"
        " duplicates surviving `_dedup_elements`, and 7 fabricated `.N` primary"
        " keys in the Kentucky parser output. Fixing those needs the `SCHEMA`"
        " option — a prompt rule that a page banner is not an element's"
        " `age_band` — which moves `code_version_hash` and forces a re-record"
        " of Tasks 1--4. Deliberately deferred, not overlooked.",
        "",
        "---",
        "",
        "| test case | level | golden | run | trimmed page | title |",
        "|---|---|---|---|---|---|",
    ]
    for d in drift:
        L.append(
            f"| `{d['test_case_id']}` | {d['level']} | `{d['golden_age_band']}` | "
            f"`{', '.join(d['run_age_band']) or 'null'}` | "
            f"{', '.join(str(p) for p in d['target_tier_pages'])} | {d['title']} |"
        )
    return "\n".join(L)


def full_annotation_sheet(state: str, res: dict, run: list, golden: list,
                          parser_golden: dict | None) -> str:
    """EVERY annotated element, with what the run did about it.

    The other two sheets show only rows in dispute. This one shows the whole
    annotation, in document order, so it can be reviewed end to end rather than
    by exception -- which is what "review every annotation" actually asks for.
    """
    strict = res["arms"]["page_tolerance_0"]
    dec = strict["recall_decomposition"]
    drift_ab = {d["test_case_id"]: d for d in dec["age_band_attribution_drift"]}
    drift_ti = {d["test_case_id"]: d for d in dec["title_composition_drift"]}
    absent = {d["test_case_id"] for d in dec["absent_from_window"]}

    tgt_to_src = {v: int(k) for k, v in
                  res["page_window"]["mapping_source_to_target"].items()}
    src_to_tgt = {v: k for k, v in tgt_to_src.items()}

    by_key = defaultdict(list)
    for d in run:
        if d.get("source_page") in set(tgt_to_src):
            by_key[((d.get("level") or "").strip(), _title_key(d))].append(d)

    pw = res["page_window"]
    rt = res["run_totals"]
    n_in = strict["in_scope_elements_at_scale"]

    L = [
        f"# {state} — the complete annotation, and what the run did with it",
        "",
        "## ⚠️ Coverage: what this annotation reaches",
        "",
        f"- The trimmed run holds **{rt['elements_in_whole_run']} elements** "
        f"across **{rt['pages_in_run']} pages**.",
        f"- The annotation covers **{len(pw['source_tier_pages'])} pages** of it "
        f"(`_only_subset` pages {pw['source_tier_pages']} = trimmed pages "
        f"{pw['target_tier_pages']}).",
        f"- So **{n_in} elements are graded** and "
        f"**{rt['elements_in_whole_run'] - n_in} are not**, because no annotation "
        f"exists for them.",
        "",
        "**There is no annotation for the whole run, and this sheet cannot show "
        "you one.** Every quality number for this state — in this task and in "
        "the paper — is computed inside that page window. Annotating the rest is "
        "a separate project; the size of it is the number above.",
        "",
        "## The files a verdict edits",
        "",
        f"- `evaluation/ground_truth_detector/{state}.json` — "
        f"**{len(golden)} elements**, graded below.",
    ]
    if parser_golden is not None:
        n_std = len(parser_golden.get("standards", []))
        L.append(f"- `evaluation/ground_truth_parser/{state}.json` — "
                 f"**{n_std} standards**, graded by `eval_parser` against a "
                 f"detection file, NOT by this task. Listed at the end for "
                 f"completeness.")
    L += [
        "",
        "## Status key",
        "",
        "| status | meaning |",
        "|---|---|",
        "| `OK` | found on the mapped page, exact on level, title and `age_band` |",
        "| `AGE-BAND` | found and correct, but the run stamped a different `age_band` |",
        "| `TITLE` | found at the right level, but the run folded extra text into `title` |",
        "| `ABSENT` | not found in the window — a real detection loss |",
        "",
        "---",
        "",
        f"## Annotated elements ({len(golden)})",
        "",
    ]

    counts = Counter()
    for g in golden:
        tid = g.get("test_case_id", "?")
        if tid in absent:
            status = "ABSENT"
        elif tid in drift_ti:
            status = "TITLE"
        elif tid in drift_ab:
            status = "AGE-BAND"
        else:
            status = "OK"
        counts[status] += 1
        src_p = g.get("source_page")
        hits = by_key.get(((g.get("level") or "").strip(), _title_key(g)), [])
        L.append(f"### `{tid}` — **{status}**")
        L.append("")
        L.append(f"- level **{g.get('level')}** · golden code `{g.get('code')}` "
                 f"· golden age_band `{g.get('age_band')}`")
        L.append(f"- `_only_subset` p{src_p} = trimmed p{src_to_tgt.get(src_p)}")
        L.append(f"- title: {g.get('title')}")
        gd = (g.get("description") or "").strip()
        if gd:
            L.append(f"- golden description: {gd[:200]}"
                     f"{'…' if len(gd) > 200 else ''}")
        if hits:
            L.append(f"- run emitted **{len(hits)} cop{'y' if len(hits)==1 else 'ies'}**:")
            for h in hits:
                L.append(f"  - code `{h.get('code')}` · age_band "
                         f"`{h.get('age_band')}` · p{h.get('source_page')}")
        else:
            L.append("- run emitted: **nothing matching this level and title**")
        if status != "OK":
            L.append("")
            L.append("`[ ] golden is right  [ ] run is right  [ ] neither — note below`")
        L.append("")

    L.insert(
        L.index(f"## Annotated elements ({len(golden)})") + 1,
        "\n**Summary: " + ", ".join(
            f"{v} {k}" for k, v in sorted(counts.items())) + "**\n")

    work = strict["unmatched_adjudication"]["annotation_worklist"]
    gold_keys = {((g.get("level") or "").strip(), _title_key(g)) for g in golden}
    dups = [w for w in work
            if ((w.get("level") or "").strip(),
                _title_key({"title": w.get("title")})) in gold_keys]
    news = [w for w in work if w not in dups]
    L += [
        "---",
        "",
        f"## In the window but not in the annotation ({len(work)})",
        "",
        f"- **{len(dups)} duplicates** — a second copy of an element annotated "
        f"above. Not an annotation question; a detector finding.",
        f"- **{len(news)} not annotated** — real page content the golden does "
        f"not cover. **These are the annotation questions.**",
        "",
        "Full detail with page context is in "
        f"`{state}_unannotated_review.md`.",
        "",
    ]
    if news:
        L += ["| level | code | trimmed p | title |", "|---|---|---|---|"]
        for w in news:
            L.append(f"| {w['level']} | `{w['code']}` | {w['target_tier_page']} "
                     f"| {w['title']} |")
        L.append("")

    if parser_golden is not None:
        stds = parser_golden.get("standards", [])
        L += [
            "---",
            "",
            f"## Parser annotation ({len(stds)} standards) — for completeness",
            "",
            "Graded by `evaluation.eval_parser` against a detection file, not by "
            "this task. Listed so the state's annotation can be reviewed in one "
            "place.",
            "",
            "| test case | indicator code | age_band | name |",
            "|---|---|---|---|",
        ]
        for st_ in stds:
            ind = st_.get("indicator") or {}
            L.append(f"| `{st_.get('test_case_id')}` | "
                     f"`{ind.get('code')}` | `{st_.get('age_band')}` | "
                     f"{str(ind.get('name'))[:70]} |")
    return "\n".join(L)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--state", action="append", default=None)
    ap.add_argument("--out", default=str(RESULTS / "review"))
    args = ap.parse_args()
    outdir = Path(args.out)
    outdir.mkdir(parents=True, exist_ok=True)

    for state in (args.state or ["KY"]):
        res = json.loads((RESULTS / f"{state}_scale_grade.json").read_text())
        run = json.loads((DETECTION_DIR / f"{state}-detection.json").read_text())["elements"]
        golden = json.loads((GOLDEN_DIR / f"{state}.json").read_text())["elements"]

        ab = age_band_sheet(state, res)
        if ab:
            p = outdir / f"{state}_age_band_review.md"
            p.write_text(ab)
            print(f"wrote {p}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
