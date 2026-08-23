#!/usr/bin/env python3
"""Compare the depth-map ON arm against the OFF arm (arXiv paper Task 3).

The ON arm is NOT re-run for Task 3: it is the frozen Task 1 + Task 2 detector
reports, which recorded depth_map PASS in every state. The OFF arm is a
detector-only sweep with ELS_DEPTH_MAP_ENABLED=false.

`consolidate_task1.py` is deliberately NOT reused here: it requires a parser
report, and the parser never sees a depth map, so there is no parser off-arm to
grade. This script reads the raw eval_detector reports directly.

Refuses to emit a comparison for any state whose OFF-arm run has n_detected == 0.
That is the signature of the 2026-08-23T00:25Z throttle failure, where five
states were recorded as recall 0.0 having never run -- numbers that read as a
catastrophic ablation effect. Such a state is reported as `status: "INVALID"`
and excluded from every aggregate.
"""
import argparse, json, pathlib, sys

LEVELS = ("domain", "strand", "sub_strand", "indicator")


def load_reports(paths):
    out = {}
    for p in paths:
        for rep in json.loads(pathlib.Path(p).read_text()):
            out[rep["state"]] = rep
    return out


def level_rates(rep):
    d = {}
    for lv in LEVELS:
        pl = rep.get("per_level", {}).get(lv)
        if not pl:
            continue
        tp, fp, fn = pl["tp"], pl["fp"], pl["fn"]
        d[lv] = {
            "tp": tp, "fp": fp, "fn": fn,
            "recall": round(tp / (tp + fn), 4) if (tp + fn) else None,
            "precision": round(tp / (tp + fp), 4) if (tp + fp) else None,
        }
    return d


def regr(rep):
    rs = rep.get("regressions", [])
    return {
        "passed": sum(1 for r in rs if r["status"] == "PASS"),
        "total": len(rs),
        "failed_ids": [r["id"] for r in rs if r["status"] != "PASS"],
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--on-report", action="append", required=True,
                    help="raw eval_detector report(s) from the ON arm; repeatable")
    ap.add_argument("--off-report", action="append", required=True,
                    help="raw eval_detector report(s) from the OFF arm; repeatable")
    ap.add_argument("--out", type=pathlib.Path, required=True)
    args = ap.parse_args()

    on, off = load_reports(args.on_report), load_reports(args.off_report)
    states = [s for s in ("AZ", "CA", "CO", "TX", "NV", "KY") if s in on and s in off]

    per_state, invalid = {}, []
    for st in states:
        o, f = on[st], off[st]
        if f.get("n_detected", 0) == 0:
            invalid.append(st)
            per_state[st] = {"status": "INVALID",
                             "reason": "OFF-arm n_detected == 0 -- the run failed "
                                       "(throttle or error); it was NOT ablated to zero. "
                                       "Excluded from all aggregates."}
            continue
        if f.get("depth_map_passed") is not None:
            invalid.append(st)
            per_state[st] = {"status": "INVALID",
                             "reason": f"OFF-arm depth_map_passed is "
                                       f"{f['depth_map_passed']!r}, expected null (ABLATED). "
                                       "The ablation flag did not take for this state."}
            continue
        per_state[st] = {
            "status": "OK",
            "on": {"n_detected": o["n_detected"], "matched": o["matched"],
                   "recall": round(o["recall"], 4), "precision": round(o["precision"], 4),
                   "code": f"{o['code_matches']}/{o['code_total']}",
                   "description": f"{o['description_matches']}/{o['description_total']}",
                   "depth_map": "PASS" if o["depth_map_passed"] else "FAIL",
                   "per_level": level_rates(o), "regressions": regr(o)},
            "off": {"n_detected": f["n_detected"], "matched": f["matched"],
                    "recall": round(f["recall"], 4), "precision": round(f["precision"], 4),
                    "code": f"{f['code_matches']}/{f['code_total']}",
                    "description": f"{f['description_matches']}/{f['description_total']}",
                    "depth_map": "ABLATED", "per_level": level_rates(f),
                    "regressions": regr(f)},
            "delta": {
                "recall": round(f["recall"] - o["recall"], 4),
                "precision": round(f["precision"] - o["precision"], 4),
                "n_detected": f["n_detected"] - o["n_detected"],
                "code_matches": f["code_matches"] - o["code_matches"],
                "regressions_newly_failing": sorted(
                    set(regr(f)["failed_ids"]) - set(regr(o)["failed_ids"])),
            },
        }

    ok = [s for s in states if per_state[s]["status"] == "OK"]
    agg = None
    if ok:
        agg = {
            "states_compared": ok,
            "states_excluded_invalid": invalid,
            "mean_recall_on": round(sum(per_state[s]["on"]["recall"] for s in ok) / len(ok), 4),
            "mean_recall_off": round(sum(per_state[s]["off"]["recall"] for s in ok) / len(ok), 4),
            "states_with_recall_drop": [s for s in ok if per_state[s]["delta"]["recall"] < 0],
            "total_regressions_newly_failing": sorted(
                {r for s in ok for r in per_state[s]["delta"]["regressions_newly_failing"]}),
        }
        by_level = {}
        for lv in LEVELS:
            src = [(per_state[s]["on"]["per_level"].get(lv), per_state[s]["off"]["per_level"].get(lv))
                   for s in ok]
            src = [(a, b) for a, b in src if a and b]
            if not src:
                continue
            on_tp = sum(a["tp"] for a, _ in src); on_fn = sum(a["fn"] for a, _ in src)
            off_tp = sum(b["tp"] for _, b in src); off_fn = sum(b["fn"] for _, b in src)
            on_fp = sum(a["fp"] for a, _ in src); off_fp = sum(b["fp"] for _, b in src)
            by_level[lv] = {
                "on_recall": round(on_tp / (on_tp + on_fn), 4) if on_tp + on_fn else None,
                "off_recall": round(off_tp / (off_tp + off_fn), 4) if off_tp + off_fn else None,
                "on_precision": round(on_tp / (on_tp + on_fp), 4) if on_tp + on_fp else None,
                "off_precision": round(off_tp / (off_tp + off_fp), 4) if off_tp + off_fp else None,
            }
        agg["pooled_by_level"] = by_level

    out = {
        "comparison": "depth-map ablation (arXiv paper Task 3)",
        "on_arm_note": "Frozen Task 1 + Task 2 detector reports; depth_map PASS in every state. "
                       "NOT re-run for Task 3.",
        "off_arm_note": "ELS_DEPTH_MAP_ENABLED=false; infer_depth_map returns None at the source, "
                        "so both detect_structure and the batch preparer degrade identically.",
        "aggregate": agg,
        "per_state": per_state,
    }
    args.out.write_text(json.dumps(out, indent=2))
    print(f"Wrote {args.out}")
    if invalid:
        print(f"WARNING: {len(invalid)} state(s) marked INVALID and excluded: {invalid}",
              file=sys.stderr)


if __name__ == "__main__":
    main()
