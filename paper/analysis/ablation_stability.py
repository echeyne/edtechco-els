#!/usr/bin/env python3
"""Stability of the depth-map ablation across repeated runs (arXiv paper Task 3).

Answers the question the single recorded run cannot: are the ablation's effects
reproducible, or artifacts of one sample? Two things are checked separately
because they carry very different weight:

  * CATEGORICAL — does a regression case pass or fail? This is robust: it does
    not depend on golden size, and a case that flips between runs is a genuinely
    unstable finding.
  * RATE — recall, precision, code accuracy. On small goldens these are fragile
    (CO's golden is 7 elements, so one element is 0.143 of recall), which is
    precisely why they need repetition before the paper quotes them.

The four states with NO measured effect matter as much as the two with one:
"the depth map is only needed for position-dependent levels" is a claim about
the unaffected states too, and a single sample cannot support it.

Deliberately NOT built on eval_detector.measure_stability, which compares only
its own probe runs and EXCLUDES the graded run -- it reported 0.000 disagreement
in the same invocation whose graded output carried 4 malformed primary keys.
This reads the actual per-run report files instead.
"""
import argparse, json, pathlib, statistics
from collections import defaultdict

LEVELS = ("domain", "strand", "sub_strand", "indicator")


def load_runs(reports_dir, frozen):
    """runs[arm][state] -> list of per-run report dicts, sample 1 first."""
    runs = defaultdict(lambda: defaultdict(list))
    for arm, paths in frozen.items():
        for p in paths:
            for rep in json.loads(pathlib.Path(p).read_text()):
                runs[arm][rep["state"]].append({"run": 1, **rep})
    for f in sorted(pathlib.Path(reports_dir).glob("*.json")):
        if f.name.startswith("INVALID_"):
            continue
        arm, run, state = f.stem.split("_")          # e.g. on_run2_AZ
        for rep in json.loads(f.read_text()):
            # A throttled run is recorded with n_detected == 0 and grades as
            # recall 0.0. Averaging that into a stability figure would invent a
            # catastrophic instability out of an infrastructure failure -- the
            # same trap the first Task 3 attempt set. Refuse it outright.
            if rep.get("n_detected", 0) == 0:
                raise SystemExit(
                    f"REFUSING {f.name}: state {rep.get('state')} has n_detected == 0. "
                    "That run FAILED (throttle or error); it was not measured. "
                    "Rename it INVALID_* or delete it, then re-run.")
            expect_ablated = (arm == "off")
            if (rep.get("depth_map_passed") is None) != expect_ablated:
                raise SystemExit(
                    f"REFUSING {f.name}: arm={arm} but depth_map_passed="
                    f"{rep.get('depth_map_passed')!r}. The ablation flag did not "
                    "match the arm for this run.")
            runs[arm][state].append({"run": int(run.replace("run", "")), **rep})
    for arm in runs:
        for st in runs[arm]:
            runs[arm][st].sort(key=lambda r: r["run"])
    return runs


def regr_map(rep):
    return {r["id"]: r["status"] for r in rep.get("regressions", [])}


def summarize(rs):
    rec = [r["recall"] for r in rs]
    return {
        "n_runs": len(rs),
        "recall_by_run": [round(x, 4) for x in rec],
        "recall_mean": round(statistics.mean(rec), 4),
        "recall_stdev": round(statistics.stdev(rec), 4) if len(rec) > 1 else 0.0,
        "recall_range": [round(min(rec), 4), round(max(rec), 4)],
        "n_detected_by_run": [r["n_detected"] for r in rs],
        "code_by_run": [f"{r['code_matches']}/{r['code_total']}" for r in rs],
        "depth_map_by_run": [("ABLATED" if r["depth_map_passed"] is None
                              else "PASS" if r["depth_map_passed"] else "FAIL") for r in rs],
    }


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--reports-dir", required=True)
    ap.add_argument("--frozen-on", action="append", required=True,
                    help="frozen sample-1 ON-arm report(s); repeatable")
    ap.add_argument("--frozen-off", action="append", required=True)
    ap.add_argument("--out", type=pathlib.Path, required=True)
    args = ap.parse_args()

    runs = load_runs(args.reports_dir, {"on": args.frozen_on, "off": args.frozen_off})
    states = sorted(set(runs["on"]) & set(runs["off"]))

    per_state, unstable_cases, rate_flips = {}, [], []
    for st in states:
        on, off = runs["on"][st], runs["off"][st]
        entry = {"on": summarize(on), "off": summarize(off)}

        # categorical: a case is STABLE if its status is identical across runs
        cat = {}
        for arm, rs in (("on", on), ("off", off)):
            per_case = defaultdict(list)
            for r in rs:
                for cid, status in regr_map(r).items():
                    per_case[cid].append(status)
            cat[arm] = {cid: {"statuses": sts, "stable": len(set(sts)) == 1}
                        for cid, sts in per_case.items()}
            for cid, v in cat[arm].items():
                if not v["stable"]:
                    unstable_cases.append({"state": st, "arm": arm, "case": cid,
                                           "statuses": v["statuses"]})
        entry["regressions"] = cat

        # the headline categorical claim: cases that fail in OFF but pass in ON,
        # in EVERY run -- these are the reproducible ablation effects
        on_always_pass = {c for c, v in cat["on"].items()
                          if v["stable"] and v["statuses"][0] == "PASS"}
        off_always_fail = {c for c, v in cat["off"].items()
                           if v["stable"] and v["statuses"][0] != "PASS"}
        entry["reproducible_ablation_failures"] = sorted(on_always_pass & off_always_fail)

        # rate: does the ON/OFF recall gap keep its SIGN in every run?
        gaps = [round(o["recall"] - n["recall"], 4)
                for n, o in zip(on, off)][:min(len(on), len(off))]
        entry["recall_gap_off_minus_on_by_run"] = gaps
        entry["gap_sign_consistent"] = (all(g < 0 for g in gaps) or all(g >= 0 for g in gaps))
        if not entry["gap_sign_consistent"]:
            rate_flips.append({"state": st, "gaps": gaps})
        entry["effect"] = "DEGRADED" if all(g < 0 for g in gaps) else "no measured effect"
        per_state[st] = entry

    affected = [s for s in states if per_state[s]["effect"] == "DEGRADED"]
    # Derive n from the runs actually read rather than asserting it. A partial
    # sweep (2026-08-23: a throttle cut 16 of 24 runs) must not be described by
    # a hardcoded sample size -- guardrail 6, every number regenerable.
    n_by_arm_state = {s: {a: per_state[s][a]["n_runs"] for a in ("on", "off")}
                      for s in states}
    n_all = [v[a] for v in n_by_arm_state.values() for a in ("on", "off")]
    n_lo, n_hi = min(n_all), max(n_all)
    n_desc = f"n={n_lo}" if n_lo == n_hi else f"n={n_lo}-{n_hi}"
    out = {
        "what_this_measures": (
            f"{n_desc} per arm per state. Sample 1 is the frozen recorded run "
            "(task1/task2 for ON, task3 for OFF); later samples are repeats at the "
            "same code_version_hash on the same outputs folder."),
        "sample_sizes": {"min": n_lo, "max": n_hi, "by_state": n_by_arm_state},
        "aggregate": {
            "states": states,
            "states_with_reproducible_degradation": affected,
            "states_with_no_measured_effect": [s for s in states if s not in affected],
            "categorical_cases_unstable_across_runs": unstable_cases,
            "states_whose_recall_gap_changed_SIGN": rate_flips,
            "reproducible_ablation_failures": sorted(
                {c for s in states for c in per_state[s]["reproducible_ablation_failures"]}),
        },
        "per_state": per_state,
    }
    args.out.write_text(json.dumps(out, indent=2))
    print(f"Wrote {args.out}")
    print(f"  degraded in every run: {affected}")
    print(f"  unstable regression cases: {len(unstable_cases)}")
    print(f"  states whose gap flipped sign: {[r['state'] for r in rate_flips]}")


if __name__ == "__main__":
    main()
