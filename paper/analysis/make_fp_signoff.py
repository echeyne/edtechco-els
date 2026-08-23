#!/usr/bin/env python3
"""Render a false-positive audit sign-off sheet from fp_audit output.

The sheet is what a human actually marks up, so it is generated rather than
hand-written: guardrail 6 wants every artifact regenerable, and a hand-typed
sheet drifts from `heldout_evidence.json` the moment the audit is re-run.

Rows are grouped least-to-most consequential, and each group states the KIND of
evidence behind it so a reviewer knows how hard to look:

  A  real_unannotated       title verbatim in the extraction        mechanical
  B  real_repeat_of_matched same level+title as a matched element   mechanical
  C  real_split_title       spans reconstruct IN READING ORDER      light check
  D  hallucinated           no in-order reconstruction anywhere     REAL SCRUTINY

Only D counts against verified precision.
"""
import argparse, json, pathlib, re, sys

ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "paper/analysis"))

GROUPS = [
    ("A", "real_unannotated",
     "real content the golden simply did not annotate",
     "Each title occurs **verbatim and contiguously** in the extraction. The "
     "golden is a spot-check, so unannotated real content is expected and is not "
     "a defect.",
     "Confirm a couple really are elements on the page cited. Spot-checking two "
     "is enough."),
    ("B", "real_repeat_of_matched",
     "correct second detections of a reprinted heading",
     "Verified **structurally**: each row has the same level and title as an "
     "element that already matched a golden entry. The document reprints the "
     "heading; the detector is right to emit it again.",
     "Confirm the heading really does appear on the cited page as well as its "
     "first location. Spot-checking two is enough."),
    ("C", "real_split_title",
     "real titles split across lines or columns",
     "The title is **not** a contiguous string in the extraction, but every span "
     "reconstructs **in reading order** within a small window. That is the "
     "signature of a real title broken by a line break or an interleaved "
     "neighbouring column — an invented tail does not reconstruct in order.\n\n"
     "⚠️ These rows would have been reported as `hallucinated` before "
     "2026-08-23. They are not. Do not read the old label as a defect count.",
     "Skim the window sizes below — all small means all local. Open the two "
     "largest against the PDF if you want a check."),
    ("D", "hallucinated",
     "candidate hallucinations — THESE ARE THE ROWS THAT MATTER",
     "Not a repeat, not contiguous, and the spans **cannot** be reconstructed in "
     "reading order anywhere in the extraction. This is the signature of an "
     "invented tail.",
     "Open the PDF at the cited page and confirm the text really is absent."),
]


def _phrase_diff(title: str, twin: str) -> str:
    """The trailing portion where a title diverges from its same-code twin."""
    a, b = title.split(), (twin or "").split()
    i = 0
    while i < min(len(a), len(b)) and a[i] == b[i]:
        i += 1
    return " ".join(a[i:])


def render(state: str, audit: dict, extraction_text: str, pdf_hint: str) -> str:
    rows = audit["verdicts"]
    by = {g[1]: [r for r in rows if r["verdict"] == g[1]] for g in GROUPS}
    n_hall = len(by["hallucinated"])
    n_in = audit["n_in_scope_detections"]
    vp = audit["verified_precision"]

    L = [f"# {state} false-positive audit — sign-off sheet",
         "",
         "**You are the annotator of record.** The paper will say:",
         "",
         "> *all unmatched in-scope detections of the recorded run were manually "
         "audited by the author*",
         "",
         f"That sentence is **not true for {state} until you sign this**, and "
         f"{state}'s verified precision **{vp}** is not quotable before then. "
         "Every verdict below carries `verified_by: \"claude-first-pass-UNSIGNED\"`.",
         ""]

    if n_hall == 0:
        L += ["## ✅ No candidate hallucinations in this state",
              "",
              f"All **{len(rows)}** unmatched detections classify as real document "
              "content. There is **no row here needing the deep scrutiny** that "
              "Nevada's `SS.CI.PK3` required — no title in this state failed the "
              "in-order reconstruction test.",
              "",
              f"So verified precision is **{n_in}/{n_in} = {vp}**: signing this "
              "sheet asserts that the rows below are real, not that any of them "
              "is a defect.",
              ""]

    L += ["## How to sign off", "",
          f"1. Open `{pdf_hint}`.",
          "2. Work the groups below — they are ordered least-to-most "
          "consequential, and each says how hard to look.",
          "3. Write `AGREE`, or the corrected verdict, in the **Your call** column.",
          "4. Fill the block and tell Claude, who will fold the verdicts into the "
          "evidence JSON, replacing `claude-first-pass-UNSIGNED`.",
          "", "```",
          "ANNOTATOR:        Emily Cheyne",
          "DATE:             ____-__-__",
          f"VERDICTS CHANGED: ____   (0 if you agree with all {len(rows)})",
          "SIGNED:           [ ]",
          "```", "",
          "## Scope — what you are and are not signing", "",
          f"- The detector emitted **{n_in}** in-scope elements for {state}.",
          f"- **{n_in - len(rows)}** matched a golden entry and are not in question.",
          f"- The **{len(rows)}** rows below are the leftovers. You are ruling on "
          f"these {len(rows)} only.", "",
          "Verified precision = (in-scope detections − hallucinations) / in-scope "
          f"detections. With {n_hall} hallucination(s) that is **{n_in - n_hall}/"
          f"{n_in} = {vp}**.", "",
          "⚠️ **Do not judge a row by searching the extraction for its title.** "
          "This document's layout breaks titles across lines and columns, so real "
          "text often does not appear as one contiguous string. That is what "
          "Group C is about, and it is why a plain substring test is not the "
          "instrument here.", ""]

    for letter, key, headline, why, what in GROUPS:
        rs = by[key]
        if not rs:
            continue
        L += [f"## Group {letter} — {headline} ({len(rs)} rows)", "",
              f"**Why I'm confident:** {why}", "",
              f"**What to check:** {what}", ""]
        if key == "real_split_title":
            L += ["| # | Page | Level | Code | Title | In-order window | My verdict | Your call |",
                  "|---|---|---|---|---|---|---|---|"]
            for i, r in enumerate(rs, 1):
                w = r.get("inorder_reconstruction_window_chars")
                L.append(f"| {letter}{i} | {r.get('page')} | {r.get('level')} | "
                         f"`{r.get('code')}` | {(r.get('title') or '')[:58]} | "
                         f"{w} chars | real, split | |")
        elif key == "hallucinated":
            L.append("")
            for i, r in enumerate(rs, 1):
                title = r.get("title") or ""
                L += [f"**Row {letter}{i} — page {r.get('page')}, {r.get('level')}, "
                      f"code `{r.get('code')}`**", "", f"> *\"{title}\"*", ""]
                if r.get("duplicate_code_of_matched"):
                    tw = r.get("twin_title") or ""
                    diff = _phrase_diff(title, tw)
                    n = len(re.findall(re.escape(diff), extraction_text)) if diff else 0
                    L += ["Another element carries the **same code**:", "",
                          f"| | title |", "|---|---|",
                          f"| matched (correct) | {tw} |",
                          f"| this row | {title} |", "",
                          f"- Diverging text: **\"{diff}\"**",
                          f"- That phrase occurs **{n} times** in the extraction.",
                          f"- This row's `source_text` is a truncated prefix of the "
                          f"twin's: **{r.get('this_source_text_is_truncated_prefix_of_twin')}**",
                          ""]
                else:
                    L += ["No same-code twin. The spans do not reconstruct in "
                          "reading order anywhere in the extraction.", ""]
                L += [f"**What to check on page {r.get('page')}:** confirm this text "
                      "is genuinely absent from the document.", "",
                      "| # | Page | Level | Code | My verdict | Your call |",
                      "|---|---|---|---|---|---|",
                      f"| {letter}{i} | {r.get('page')} | {r.get('level')} | "
                      f"`{r.get('code')}` | **hallucinated** | |", ""]
        else:
            L += ["| # | Page | Level | Code | Title | My verdict | Your call |",
                  "|---|---|---|---|---|---|---|"]
            label = {"real_unannotated": "real, unannotated",
                     "real_repeat_of_matched": "real, repeat"}[key]
            for i, r in enumerate(rs, 1):
                L.append(f"| {letter}{i} | {r.get('page')} | {r.get('level')} | "
                         f"`{r.get('code')}` | {(r.get('title') or '')[:58]} | {label} | |")
        L.append("")

    if n_hall == 0:
        L += ["## If you disagree", "",
              "If any row above is in fact **not** in the document, tell me which "
              f"and {state}'s verified precision drops by "
              f"{round(1 / n_in, 4)} per row. A null result is just as useful — "
              "I would rather correct the analysis than carry a wrong claim into "
              "the paper.", ""]
    return "\n".join(L)


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--evidence", type=pathlib.Path, required=True,
                    help="JSON with an fp_audit_first_pass block")
    ap.add_argument("--outputs-dir", type=pathlib.Path, required=True)
    ap.add_argument("--state", action="append", dest="states", required=True)
    ap.add_argument("--out-dir", type=pathlib.Path, required=True)
    ap.add_argument("--pdf-hint", default="the state's trimmed subset PDF in standards/")
    args = ap.parse_args()

    from heldout_evidence import _extraction_text
    ev = json.loads(args.evidence.read_text())["fp_audit_first_pass"]
    args.out_dir.mkdir(parents=True, exist_ok=True)
    for st in args.states:
        text = _extraction_text(st, args.outputs_dir)
        sheet = render(st, ev[st], text, args.pdf_hint)
        p = args.out_dir / f"{st.lower()}_fp_audit_signoff.md"
        p.write_text(sheet)
        c = ev[st]["counts_by_verdict"]
        print(f"Wrote {p}  ({ev[st]['n_extras_audited']} rows; "
              f"{c.get('hallucinated', 0)} candidate hallucination(s))")


if __name__ == "__main__":
    main()
