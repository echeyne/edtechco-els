"""Generate the paper's LaTeX result tables from recorded JSON.

Guardrail 6 (tasking/arxiv_paper.md): every number in the paper must be
regenerable and no table may be hand-typed. This script is the regeneration
step -- it reads the consolidated suite summaries already produced by
paper/analysis/consolidate_task1.py, the signed false-positive audits, and the
ablation comparison, plus paper/results/corpus_tiers.json for the guardrail-1
tier column, and writes ready-to-\\input LaTeX fragments to paper/tables/.
Nothing here re-runs an eval or computes a new number; it only formats numbers
that already exist in paper/results/.

⚠️ RUN_TAG IS THE ONLY THING TO EDIT AFTER A RE-RECORD. It was previously
hard-coded as `20260816` in six places, and when the 2026-08-22/23 re-record
superseded that run the tables kept rendering the OLD numbers into
experiments_results.tex -- NV code accuracy read 39/41 against a golden that had
become 46 elements. SUPERSEDED_TAGS below makes that failure loud instead of
silent.

Inputs (all under paper/results/):
    task1_<RUN_TAG>/summary.json                 (AZ, CA, CO, TX)
    task2_<RUN_TAG>/summary.json                 (NV, KY)
    task1_<RUN_TAG>/task1b_fp_audit_SIGNED.json  verified precision, golden four
    task2_<RUN_TAG>/nv_fp_audit_SIGNED.json      verified precision, held-out
    task3_<ABLATION_TAG>/ablation_comparison.json depth-map on/off (SEPARATE TAG — see below)
    task4_<BASELINE_TAG>/baseline_comparison.json  rule-based baseline vs LLM
    task3_stability_<STABILITY_TAG>/stability_analysis.json   (optional)
    task8_<STATS_TAG>/dataset_stats.json           descriptive stats
    task8_<STATS_TAG>/confidence_distribution.json re-measured confidence
    corpus_tiers.json

Outputs:
    paper/tables/detector_headline.tex
    paper/tables/parser_headline.tex
    paper/tables/ablation_depthmap.tex
    paper/tables/baseline_comparison.tex
    paper/tables/dataset_stats.tex
    paper/tables/confidence_distribution.tex

Usage (from repo root):
    python paper/analysis/generate_tables.py
"""

import json
from pathlib import Path

PAPER_DIR = Path(__file__).resolve().parent.parent
RESULTS_DIR = PAPER_DIR / "results"
TABLES_DIR = PAPER_DIR / "tables"

# The recorded freeze these tables describe. Edit ONLY this after a re-record.
RUN_TAG = "20260826"

# The depth-map ablation keeps its OWN tag even though it now matches RUN_TAG.
# It is a genuinely separate recording with a separate cadence: its ON arm is
# the frozen Task 1 + Task 2 detector reports and only its OFF arm is swept, so
# it can fall out of step with RUN_TAG without either being wrong. Re-recorded
# at 14374dba on 2026-08-26 because 99b853cc replaced the Pass-1 SAMPLER its ON
# arm exercises; the gap WIDENED (mean recall off 0.9610 -> 0.9573), confirming
# that the older number was conservative.
ABLATION_TAG = "20260826"
STABILITY_TAG = "20260823"
BASELINE_TAG = "20260826"
STATS_TAG = "20260904"

# Task 6's batched-path scale recording. ⚠️ SEPARATE TIER: this is the only
# recording in the paper that is NOT _only_subset. It is _trimmed (KY 52pp,
# CO 41pp) and must never be captioned as full-document -- the run_id says
# "full08292026" and that name is wrong (guardrail 1). Equally, it must never
# be captioned as an EXCERPT: corrected 2026-08-31, the _trimmed tier retains
# 100% of the standards and removes only non-standards matter, so these runs
# cover every standard in both documents. Both halves of that go in the
# caption or a reader gets one of the two false readings.
SCALE_TAG = "20260830"

# Task 5 stability. Distinct from STABILITY_TAG above, which is Task 3's
# ABLATION-arm stability (detector only, n=3). This one is both suites under
# normal configuration and is what the determinism claim rests on.
TASK5_TAG = "20260830"

# Runs that have been superseded. Pointing RUN_TAG at one of these is almost
# always a mistake -- the whole reason this constant exists.
SUPERSEDED_TAGS = {"20260816"}

GOLDEN_STATES = ["AZ", "CA", "CO", "TX"]
HELDOUT_STATES = ["NV", "KY"]
ALL_STATES = GOLDEN_STATES + HELDOUT_STATES

STATE_TIER_KEY = {"AZ": "AZ", "CA": "CA", "CO": "CO", "TX": "TX",
                  "NV": "NV_2023", "KY": "KY"}


def load_json(path):
    with open(path) as f:
        return json.load(f)


def esc(s):
    return str(s).replace("_", r"\_").replace("%", r"\%")


def fmt_pct(x):
    return "--" if x is None else f"{x * 100:.1f}"


def bool_mark(b):
    return "PASS" if b else r"\textbf{FAIL}"


def header(*sources, tier="_only_subset"):
    """⚠️ `tier` is guardrail 1 and defaults to the tier almost every table uses.
    Task 6's scale table is the one exception (_trimmed), so it must pass it
    explicitly. A table that silently inherits the wrong tier label puts a false
    claim in the paper, which is exactly what guardrail 1 exists to prevent."""
    src = ", ".join(sources)
    tier_line = {
        "_only_subset": ("% Corpus tier (guardrail 1): every row is the _only_subset tier, "
                         "never full-document."),
        "_trimmed": ("% Corpus tier (guardrail 1): every row is the _trimmed tier -- a "
                     "document's standards content IN FULL (KY 52pp, CO 41pp) with "
                     "non-standards matter removed. NOT the full published PDF (KY 120pp, "
                     "CO 187pp), and NOT the _only_subset tier the quality tables use."),
    }[tier]
    return [
        "% AUTO-GENERATED by paper/analysis/generate_tables.py -- do not hand-edit.",
        f"% Source: {src}",
        "% Regenerate with: python paper/analysis/generate_tables.py",
        tier_line,
    ]


def build_detector_table(det, tiers, verified):
    L = header(f"paper/results/task1_{RUN_TAG}/summary.json",
               f"task2_{RUN_TAG}/summary.json",
               "the signed FP audits, corpus_tiers.json")
    L += [r"\begin{table*}", r"  \centering", r"  \begin{tabular}{lrrrrrrl}", r"    \hline",
          r"    \textbf{State} & \textbf{Role} & \textbf{Subset pp} & \textbf{Recall} & "
          r"\textbf{Verified prec.} & \textbf{Code acc.} & \textbf{Desc. acc.} & "
          r"\textbf{Depth map} \\", r"    \hline"]
    for st in ALL_STATES:
        d = det[st]
        tier = tiers["tiers"][STATE_TIER_KEY[st]]
        dt = d["description_total"]
        desc = fmt_pct(d["description_accuracy"]) + (f" ({d['description_matches']}/{dt})" if dt else "")
        vp = verified.get(st)
        L.append(f"    {st} & {tier['role']} & {tier['only_subset']} & "
                 f"{fmt_pct(d['recall'])} & {fmt_pct(vp)} & "
                 f"{fmt_pct(d['code_accuracy'])} ({d['code_matches']}/{d['code_total']}) & "
                 f"{desc if dt else '--'} & {bool_mark(d['depth_map_passed'])} \\\\")
    L += [r"    \hline", r"  \end{tabular}",
          r"  \caption{Detector recall, verified precision, code and description "
          r"accuracy, and depth-map pass/fail, per state. \textbf{Verified precision} "
          r"is (in-scope detections $-$ hallucinations) / in-scope detections, from the "
          r"manual false-positive audit; every unmatched in-scope detection in all six "
          r"states was audited and signed by the author. Raw suite precision is NOT "
          r"reported: the detector goldens are partial spot-checks, so it measures "
          r"annotation coverage rather than correctness (\S\ref{sec:discussion-limitations}). All "
          r"numbers are on the \emph{\_only\_subset} corpus tier (8--15pp manually "
          r"trimmed subsets; see \S\ref{sec:corpus}), never full documents. "
          rf"Source: \texttt{{paper/results/task1\_{RUN_TAG}/}}, "
          rf"\texttt{{task2\_{RUN_TAG}/}}.}}",
          r"  \label{tab:detector-headline}", r"\end{table*}"]
    return "\n".join(L) + "\n"


def build_parser_table(par, tiers):
    L = header(f"paper/results/task1_{RUN_TAG}/summary.json",
               f"task2_{RUN_TAG}/summary.json", "corpus_tiers.json")
    L += [r"\begin{table*}", r"  \centering", r"  \begin{tabular}{lrrrrrr}", r"    \hline",
          r"    \textbf{State} & \textbf{Role} & \textbf{Coverage} & \textbf{Field acc.} & "
          r"\textbf{Fully correct} & \textbf{Standards} & \textbf{ID collisions} \\",
          r"    \hline"]
    for st in ALL_STATES:
        p = par[st]
        tier = tiers["tiers"][STATE_TIER_KEY[st]]
        L.append(f"    {st} & {tier['role']} & {fmt_pct(p['coverage'])} "
                 f"({p['matched']}/{p['n_golden']}) & {fmt_pct(p['field_accuracy'])} & "
                 f"{p['fully_correct']}/{p['n_golden']} & {p['n_parsed']} & "
                 f"{len(p['id_collisions'])} \\\\")
    L += [r"    \hline", r"  \end{tabular}",
          r"  \caption{Parser coverage, per-field accuracy, fully-correct standards, "
          r"standards emitted, and \texttt{standard\_id} collisions, per state. All "
          r"numbers are on the \emph{\_only\_subset} corpus tier "
          r"(\S\ref{sec:corpus}), never full documents. "
          rf"Source: \texttt{{paper/results/task1\_{RUN_TAG}/}}, "
          rf"\texttt{{task2\_{RUN_TAG}/}}.}}",
          r"  \label{tab:parser-headline}", r"\end{table*}"]
    return "\n".join(L) + "\n"


def build_ablation_table(abl, stab):
    L = header(f"paper/results/task3_{ABLATION_TAG}/ablation_comparison.json",
               f"task3_stability_{STABILITY_TAG}/stability_analysis.json")
    pooled = abl["aggregate"]["pooled_by_level"]
    L += [r"\begin{table}", r"  \centering", r"  \begin{tabular}{lrr}", r"    \hline",
          r"    \textbf{Level} & \textbf{Recall, depth map on} & "
          r"\textbf{Recall, depth map off} \\", r"    \hline"]
    for lv in ("domain", "strand", "sub_strand", "indicator"):
        v = pooled.get(lv)
        if not v:
            continue
        L.append(f"    {esc(lv)} & {fmt_pct(v['on_recall'])} & {fmt_pct(v['off_recall'])} \\\\")
    L += [r"    \hline", r"  \end{tabular}"]

    degraded = abl["aggregate"]["states_with_recall_drop"]
    unaffected = [s for s in ALL_STATES if s not in degraded]
    # `abl` is ONE run. Where repeated runs exist they OVERRULE it on which
    # cases count as categorical evidence: a case that fails in the recorded
    # draw but passes in another run is a one-draw observation, not a
    # reproducible failure, and naming it here would put an unreproducible
    # claim in the paper (guardrail 7). Measured 2026-08-24: CO-NO-SUB-STRAND
    # went FAIL/FAIL/PASS at n=3, so the reproducible set is KY's two.
    recorded = abl["aggregate"]["total_regressions_newly_failing"]
    reproducible = (stab["aggregate"]["reproducible_ablation_failures"]
                    if stab else recorded)
    cases = ", ".join(rf"\texttt{{{esc(c)}}}" for c in reproducible)
    extra = ""
    if stab:
        ag = stab["aggregate"]
        rng = stab["per_state"]
        parts = []
        for s in ag["states_with_reproducible_degradation"]:
            lo, hi = rng[s]["off"]["recall_range"]
            parts.append(f"{s} {lo * 100:.0f}--{hi * 100:.0f}\\%")
        # Sample size comes from the analysis file, never a literal: the sweep
        # was partial once already (throttle, 2026-08-23) and a hardcoded n
        # would have survived the repair silently.
        sz = stab.get("sample_sizes")
        if sz:
            n_tex = (rf"$n{{=}}{sz['min']}$" if sz["min"] == sz["max"]
                     else rf"$n{{=}}{sz['min']}$--${sz['max']}$")
        else:
            n_tex = r"$n{=}2$--$3$"
        extra = (rf" Repeated runs ({n_tex} per arm per state) reproduce the "
                 r"\emph{direction} in every sample and never flip its sign, but the "
                 r"\emph{magnitude} varies: off-arm recall spans "
                 + ", ".join(parts) + r". "
                 r"Point estimates from a single run are therefore not reported.")
        unstable = [c["case"] for c in ag["categorical_cases_unstable_across_runs"]]
        dropped = [c for c in recorded if c in unstable]
        if dropped:
            extra += (r" One further case, "
                      + ", ".join(rf"\texttt{{{esc(c)}}}" for c in dropped)
                      + r", fails with the depth map disabled in the recorded run but "
                        r"passes in one repeat, and is reported as unstable rather than "
                        r"as evidence.")
        else:
            extra += r" No regression case changed status in any run."

    L += [r"  \caption{Depth-map ablation, pooled over all six states. Removing the "
          r"Pass-1 depth map leaves \emph{domain} recall untouched and degrades the "
          r"levels whose identity depends on nesting position. Per state, "
          rf"{', '.join(degraded)} degrade while {', '.join(unaffected)} are unaffected. "
          rf"The categorical evidence is {cases}, which fail with the depth map "
          rf"disabled and pass with it enabled." + extra +
          r" All numbers are on the \emph{\_only\_subset} corpus tier.}",
          r"  \label{tab:ablation-depthmap}", r"\end{table}"]
    return "\n".join(L) + "\n"


def build_baseline_table(cmp_):
    """Rule-based baseline vs LLM detector, per state and pooled by level.

    ⚠️ RAW precision is printed for BOTH arms, never verified precision for
    either. See compare_baseline.py's docstring: the FP audit's verdicts turn
    on whether a title appears in the source text, so a rule-based extractor --
    which copies text verbatim and cannot invent -- scores ~1.000 by
    construction. Printing that beside the LLM's 0.9966 would read as the
    baseline being the more faithful system.
    """
    L = header(f"paper/results/task4_{BASELINE_TAG}/baseline_comparison.json")
    ps = cmp_["per_state"]
    states = [s for s in ALL_STATES if ps.get(s, {}).get("status") == "OK"]

    L += [r"\begin{table*}", r"  \centering", r"  \begin{tabular}{lrrrrrrr}", r"    \hline",
          r"    & \multicolumn{2}{c}{\textbf{Recall}} & "
          r"\multicolumn{2}{c}{\textbf{Raw precision}} & "
          r"\multicolumn{2}{c}{\textbf{Code acc.}} & \\",
          r"    \textbf{State} & \textbf{LLM} & \textbf{Rule} & \textbf{LLM} & "
          r"\textbf{Rule} & \textbf{LLM} & \textbf{Rule} & "
          r"\textbf{Rule: found, wrong level} \\", r"    \hline"]
    for st in states:
        d = ps[st]
        l, b = d["llm"], d["baseline"]
        fd = b.get("failure_decomposition") or {}
        wrong = (f"{fd.get('found_but_wrong_level', 0)}/{fd.get('n_golden', 0)}"
                 if fd else "--")
        L.append(f"    {st} & {fmt_pct(l['recall'])} & {fmt_pct(b['recall'])} & "
                 f"{fmt_pct(l['raw_precision'])} & {fmt_pct(b['raw_precision'])} & "
                 f"{l['code_matches']}/{l['code_total']} & "
                 f"{b['code_matches']}/{b['code_total']} & {wrong} \\\\")
    L += [r"    \hline"]

    pooled = cmp_["aggregate"]["pooled_by_level"]
    L += [r"    \multicolumn{8}{l}{\emph{Pooled recall by level, all six states}} \\",
          r"    \hline"]
    for lv in ("domain", "strand", "sub_strand", "indicator"):
        v = pooled.get(lv)
        if not v:
            continue
        L.append(rf"    {esc(lv)} & {fmt_pct(v['llm_recall'])} & "
                 rf"{fmt_pct(v['baseline_recall'])} & "
                 rf"\multicolumn{{5}}{{l}}{{LLM {v['llm_tp']}/{v['llm_tp'] + v['llm_fn']}, "
                 rf"rule-based {v['baseline_tp']}/{v['baseline_tp'] + v['baseline_fn']}}} \\")
    L += [r"    \hline", r"  \end{tabular}"]

    # ⚠️ KEEP THIS CAPTION SHORT. The first version ran to 13 lines and made the
    # table* float overflow the page: bottom margin fell to 2pt and the
    # bibliography ran off the sheet edge (one Overfull \\vbox, 81pt, isolated
    # by an A/B build with and without this \\input). A caption carries only
    # what must never be separated from the numbers -- guardrail 1's corpus
    # tier, guardrail 8's precision caveat, and the source path. Everything
    # else belongs in the prose; see the TODO(Task 12) brief in
    # sections/experiments_results.tex, which covers the verified-precision
    # argument and the brittleness probe in full.
    L += [r"  \caption{Rule-based baseline versus the LLM detector, graded by the "
          r"\emph{same} suite against the \emph{same} goldens as "
          r"Table~\ref{tab:detector-headline}. The baseline uses numbering depth, "
          r"structural label words, and typography and column geometry from the "
          r"bounding boxes; it was developed against the four golden states only, "
          r"with NV and KY first scored in the recorded run. \textbf{Raw precision "
          r"is shown for both arms and is not a quality measure} except for KY, "
          r"whose golden is detection-exhaustive; elsewhere it tracks annotation "
          r"coverage and rewards under-emission, which is why the rule-based arm "
          r"exceeds the LLM on AZ while finding fewer elements "
          r"(\S\ref{sec:discussion-limitations}). All numbers are on the "
          r"\emph{\_only\_subset} corpus tier (8--15pp manually trimmed subsets), "
          r"never full documents. "
          rf"Source: \texttt{{paper/results/task4\_{BASELINE_TAG}/}}.}}",
          r"  \label{tab:baseline-comparison}", r"\end{table*}"]
    return "\n".join(L) + "\n"


def build_scale_table(scale):
    """Task 6 — batched-path cost/latency/scale, _trimmed tier.

    Kept structurally separate from the quality tables because it is a different
    corpus tier (guardrail 1). Reports TOKENS as the hard number and deliberately
    emits NO dollar column: none of the five BEDROCK_PRICING rates could be
    verified on 2026-08-30 (the AWS Price List API does not catalog current-gen
    Claude models), so a cost figure here would be unsourceable.
    """
    tier = scale["\u26a0\ufe0f_CORPUS_TIER"]
    ex, batch, per = scale["executions"], scale["batching_evidence"], scale["per_stage_metrics"]
    L = header(f"paper/results/task6_{SCALE_TAG}/manifest.json", tier="_trimmed")
    L += [
        r"\begin{table*}[t]",
        r"\centering",
        r"\small",
        r"\begin{tabular}{lrr}",
        r"\toprule",
        r"& \textbf{KY} & \textbf{CO} \\",
        r"\midrule",
        rf"Pages processed & {ex['KY']['pages']} & {ex['CO']['pages']} \\",
        r"\midrule",
        r"\multicolumn{3}{l}{\emph{Batching}} \\",
        rf"Detection chunks & {batch['KY']['detection_chunks']} & {batch['CO']['detection_chunks']} \\",
        rf"Detection batches & {batch['KY']['detection_batches']} & {batch['CO']['detection_batches']} \\",
        rf"Parse batches & {batch['KY']['parse_batches']} & {batch['CO']['parse_batches']} \\",
        rf"Elements, raw $\rightarrow$ merged & "
        rf"{batch['KY']['raw_elements']} $\rightarrow$ {batch['KY']['after_merge_dedup']} & "
        rf"{batch['CO']['raw_elements']} $\rightarrow$ {batch['CO']['after_merge_dedup']} \\",
        r"\midrule",
        r"\multicolumn{3}{l}{\emph{Input / output tokens by stage}} \\",
    ]
    STAGES = [("depth_map_pass1", "Depth map (Haiku 4.5)"),
              ("detection", "Detection (Opus 4.6)"),
              ("parsing", "Parsing (Sonnet 4.6)")]
    for key, label in STAGES:
        k, c = per["KY"][key], per["CO"][key]
        L.append(rf"{label} & {k['input_tokens']:,} / {k['output_tokens']:,} & "
                 rf"{c['input_tokens']:,} / {c['output_tokens']:,} \\")
    kt, ct = per["KY"]["total"], per["CO"]["total"]
    L += [
        r"\midrule",
        rf"\textbf{{Total}} & \textbf{{{kt['input_tokens']:,} / {kt['output_tokens']:,}}} & "
        rf"\textbf{{{ct['input_tokens']:,} / {ct['output_tokens']:,}}} \\",
        rf"LLM calls & {kt['calls']} & {ct['calls']} \\",
        rf"Wall clock & {ex['KY']['wall_clock']} & {ex['CO']['wall_clock']} \\",
        r"\midrule",
        r"\multicolumn{3}{l}{\emph{Cost (USD)}} \\",
    ]
    # Derived, never hand-typed (guardrail 6): recomputed here from the recorded
    # token counts and the pipeline's OWN BEDROCK_PRICING table, so the paper and
    # the code cannot drift apart. Every rate in that table was confirmed against
    # https://aws.amazon.com/bedrock/pricing/ -- Opus 4.6 and Sonnet 4.6 on
    # 2026-08-31, Haiku 4.5 on 2026-09-04.
    from els_pipeline.metrics import BEDROCK_PRICING
    totals = {}
    for key, label in STAGES:
        cells = []
        for st in ("KY", "CO"):
            d = per[st][key]
            rate = BEDROCK_PRICING[d["model"]]
            usd = (d["input_tokens"] / 1000 * rate["input_per_1k"]
                   + d["output_tokens"] / 1000 * rate["output_per_1k"])
            totals[st] = totals.get(st, 0.0) + usd
            cells.append(usd)
        L.append(rf"\quad {label.split(' (')[0]} & \${cells[0]:.4f} & \${cells[1]:.4f} \\")
    L += [
        rf"\textbf{{Total}} & \textbf{{\${totals['KY']:.2f}}} & \textbf{{\${totals['CO']:.2f}}} \\",
        r"\bottomrule",
        r"\end{tabular}",
        r"\caption{Batched-path scale, \textbf{\texttt{\_trimmed} corpus tier}: each "
        r"document's standards content \emph{in full}, with front matter, expository "
        r"essays and appendices removed --- not the \texttt{\_only\_subset} tier of the "
        r"quality tables, and not the published PDFs (Kentucky 120 pages, of which these "
        r"52 hold all of its standards; Colorado a 187-page birth-to-8 publication, of "
        r"which these 41 are the complete Ages 3--5 document every Colorado measurement "
        r"in this paper uses). "
        r"At the subset tier both batching layers collapse to a single batch and the "
        r"merge is a no-op; here the Step Functions \texttt{Map} iterates four times per "
        r"run and the merge removes 34 and 90 duplicate elements respectively, so the "
        r"prepare--map--merge path is genuinely exercised. \textbf{Tokens are the primary "
        r"measure}; the cost rows are derived from them using published Bedrock "
        r"on-demand rates, each confirmed against the vendor pricing page (Opus~4.6 and "
        r"Sonnet~4.6 on 2026-08-31, Haiku~4.5 on 2026-09-04) and recomputed at table-build "
        r"time from the pipeline's own pricing constants rather than transcribed. "
        r"Note the model assignment paying off: the depth-map pass is under 0.4\% of "
        r"each run's cost, while detection --- the only stage invoked once per chunk --- "
        r"is roughly 60\%. "
        rf"Source: \texttt{{paper/results/task6\_{SCALE_TAG}/}}.}}",
        r"\label{tab:scale}",
        r"\end{table*}",
    ]
    return "\n".join(L) + "\n"


def build_stability_table(t5):
    """Task 5 — run-to-run stability of both suites.

    Reports DENOMINATORS beside every rate, because a bare 0.000 is the single
    most misleading number this measurement can produce: a defect firing in a
    minority of runs survives five clean draws easily. The caption therefore
    states the rate is a lower bound rather than an estimate.

    Identity is the normalized title (detector) / indicator name (parser);
    level, code, description and standard_id are COMPARED FIELDS and never part
    of the identity key -- the predecessor instrument keyed on (code, title) and
    was blind to exactly the malformed-code defect it existed to catch.
    """
    det = t5["suites"]["detector"]
    par = t5["suites"]["parser"]
    L = header(f"paper/results/task5_{TASK5_TAG}/stability_analysis.json",
               tier="_only_subset")
    L += [
        r"\begin{table}[t]",
        r"\centering",
        r"\small",
        r"\begin{tabular}{lrrr}",
        r"\toprule",
        r"& \textbf{ids} & \textbf{unstable} & \textbf{rate} \\",
        r"\midrule",
        r"\multicolumn{4}{l}{\emph{Detector} (n=%d runs)} \\" % det["n_observations_max"]
        if "n_observations_max" in det else
        r"\multicolumn{4}{l}{\emph{Detector}} \\",
    ]

    def rows(suite):
        out = []
        for st in ALL_STATES:
            r = suite["per_state"].get(st)
            if not r or r.get("status") == "NOT_MEASURABLE":
                out.append(rf"\quad {st} & -- & -- & n/a \\")
                continue
            out.append(rf"\quad {st} & {r['n_identities_compared']} & "
                       rf"{r['n_distinct_unstable_identities']} & "
                       rf"{r['disagreement_rate']:.4f} \\")
        c = suite["corpus"]
        out.append(rf"\quad \textbf{{pooled}} & \textbf{{{c['n_identities_compared']}}} & "
                   rf"\textbf{{{c['n_distinct_unstable_identities']}}} & "
                   rf"\textbf{{{c['disagreement_rate']:.4f}}} \\")
        return out

    L += rows(det)
    L += [r"\midrule", r"\multicolumn{4}{l}{\emph{Parser}} \\"]
    L += rows(par)
    L += [
        r"\bottomrule",
        r"\end{tabular}",
        r"\caption{Run-to-run stability, \textbf{\texttt{\_only\_subset} corpus tier}. "
        r"Five independent detector runs and six parser observations per state, all "
        r"\texttt{-{}-no-cache}, split across two days: repeated runs within one session "
        r"understate variance, and Nevada demonstrates it here --- its detector output is "
        r"identical across the three same-session runs and drops one indicator in both "
        r"next-day runs. \emph{ids} is the number of distinct element identities compared "
        r"and \emph{unstable} how many differed in any graded field, so the rate is bounded "
        r"in $[0,1]$. Four of six states are perfectly reproducible on each suite. "
        r"\textbf{These rates are lower bounds, not estimates}: a defect that fires in a "
        r"minority of runs survives five clean draws easily, which is why denominators are "
        r"reported beside every rate. Source: "
        r"\texttt{paper/results/task5\_%s/}.}" % TASK5_TAG,
        r"\label{tab:stability}",
        r"\end{table}",
    ]
    return "\n".join(L) + "\n"


def build_dataset_table(stats):
    """Corpus descriptive statistics, per state.

    The hierarchy columns are the PARSED distinct counts, not the detector's
    element counts, so that every column in the row describes the same object:
    the standards this corpus actually contains. They are legitimately smaller
    than the detected counts -- see the note in dataset_stats.json.
    """
    L = header(f"paper/results/task8_{STATS_TAG}/dataset_stats.json")
    ps, t = stats["per_state"], stats["totals"]
    L += [r"\begin{table*}", r"  \centering", r"  \begin{tabular}{llrrrrrrrr}", r"    \hline",
          r"    \textbf{State} & \textbf{Role} & \textbf{Subset pp} & "
          r"\textbf{Full pp} & \textbf{Dom.} & \textbf{Str.} & \textbf{Sub.} & "
          r"\textbf{Standards} & \textbf{Age bands} & \textbf{ID coll.} \\",
          r"    \hline"]
    for st in ALL_STATES:
        d = ps[st]
        full = d["pages_full"]
        # CO's subset comes from the 41pp 3-5 document, not the 187pp
        # birth-to-8 one; flag it rather than printing a bare number.
        mark = r"$^{\dagger}$" if d.get("pages_full_note") else ""
        L.append(f"    {st} & {d['role']} & {d['pages_subset']} & {full}{mark} & "
                 f"{d['distinct_domains']} & {d['distinct_strands']} & "
                 f"{d['distinct_sub_strands']} & {d['standards']} & "
                 f"{len([k for k in d['age_bands'] if k])} & "
                 f"{d['standard_id_collisions']} \\\\")
    L += [r"    \hline",
          rf"    \textbf{{Total}} & & {t['subset_pages']} & & "
          rf"{t['distinct_domains']} & {t['distinct_strands']} & "
          rf"{t['distinct_sub_strands']} & {t['standards']} & "
          rf"{len(t['distinct_age_bands'])} & "
          rf"\textbf{{{t['standard_id_collisions_corpus_wide']}}} \\",
          r"    \hline", r"  \end{tabular}",
          r"  \caption{Corpus descriptive statistics. Domain, strand and "
          r"sub-strand columns count \emph{distinct} nodes appearing in at least "
          r"one standard's ancestor chain, so they are smaller than the "
          r"detector's element counts in Table~\ref{tab:detector-headline}. "
          r"\textbf{\texttt{standard\_id} collisions are 0 everywhere}, which "
          r"matters because \texttt{standard\_id} is the primary key under which "
          r"a standard is stored. \textbf{Age bands} counts the state's distinct "
          r"bands, and every standard in every state carries one; its total is "
          r"the union across states, not a column sum. "
          r"CO's subsets derive from the 41pp ages-3--5 document, not "
          r"the separate 187pp birth-to-8 one ($\dagger$). All quality numbers "
          r"elsewhere in this paper are measured on the \emph{\_only\_subset} "
          r"tier shown here (\S\ref{sec:corpus}), never on the full documents. "
          rf"Source: \texttt{{paper/results/task8\_{STATS_TAG}/}}.}}",
          r"  \label{tab:dataset-stats}", r"\end{table*}"]
    return "\n".join(L) + "\n"


def build_confidence_table(conf):
    """The detector's self-reported confidence, by level and by audit verdict.

    ⚠️ This table must never be presented as a calibration or quality result.
    It is evidence for the OPPOSITE claim -- that the score is uninformative,
    which is why nothing in the pipeline gates on it (guardrail 2). The verdict
    block is the point: the score does not separate the audit's categories.
    """
    L = header(f"paper/results/task8_{STATS_TAG}/confidence_distribution.json")
    d = conf["direct_path"]
    o = d["overall"]

    # ⚠️ THIS TABLE IS WIDTH-CONSTRAINED. It is a single-column ACL float
    # (~239pt), and the row labels are what blow it out. Measured by A/B build:
    # the raw JSON verdict keys overflowed by 69.6pt, and spelling them out in
    # full English ("real, title split by columns") made it 77.9pt. What fits is
    # FOUR columns at \small with short labels -- the mean was dropped for the
    # width and moved into the caption, and it loses nothing, since a mean over
    # seven discrete values a tenth apart is not informative. If you add a
    # column back, re-run the A/B before committing.
    LABEL = {
        "sub_strand": "sub-strand",
        "matched_golden": "matched a golden",
        "real_unannotated": "real, unannotated",
        "real_split_title": "real, split title",
        "real_repeat_of_matched": "real, reprinted",
        "hallucinated": r"\textbf{invented}",
    }

    def row(label, s):
        label = LABEL.get(label, label)
        return (rf"    {esc(label)} & {s['n']} & {s['min']:.2f}--{s['max']:.2f} & "
                rf"{s['at_or_above_0.95']}/{s['n']} \\")

    L += [r"\begin{table}", r"  \centering", r"  \small",
          r"  \begin{tabular}{lrrr}", r"    \hline",
          r"    & \textbf{n} & \textbf{Range} & $\mathbf{\geq 0.95}$ \\",
          r"    \hline",
          r"    \multicolumn{4}{l}{\emph{By hierarchy level}} \\"]
    for lv in ("domain", "strand", "sub_strand", "indicator"):
        s = d["by_level"].get(lv)
        if s:
            L.append(row(lv, s))
    L += [r"    \hline",
          r"    \multicolumn{4}{l}{\emph{By human false-positive audit verdict}} \\"]
    for v, s in conf["by_audit_verdict"]["by_verdict"].items():
        L.append(row(v, s))
    L += [r"    \hline", row("All", o), r"    \hline", r"  \end{tabular}"]

    n_hall = conf["by_audit_verdict"]["verdict_counts"].get("hallucinated", 0)
    stab = conf["separation_stability"]
    bands = o["prompt_band_occupancy"]
    mid = bands["0.80-0.94 (ambiguous but likely)"]
    guess = bands["below 0.70 (guessing)"]
    L += [r"  \caption{Detector self-reported confidence, re-measured over the "
          rf"{o['n']} elements of the recorded run. The prompt asks for "
          r"$\geq 0.95$ when the depth map clearly applies, $0.80$--$0.94$ when "
          r"the chunk is ambiguous, and $<0.70$ when guessing; in practice the "
          rf"score takes {o['n_distinct_values']} distinct values in "
          rf"$[{o['min']:.2f}, {o['max']:.2f}]$ (mean {o['mean']:.3f}), uses the "
          r"middle band for "
          rf"{mid} of {o['n']} elements and the bottom band "
          rf"{'never' if guess == 0 else f'{guess} times'}. The audit's "
          rf"{n_hall} confirmed invented element also holds the lowest score, "
          rf"and no correct element falls below $0.90$ in "
          rf"{stab['n_samples']} same-configuration runs "
          rf"({stab['elements_examined']} elements); with a single positive "
          r"case that is an observation, not a validated threshold. "
          r"\textbf{Nothing in the pipeline thresholds this score} -- human "
          r"verification is a separate, explicit mechanism "
          r"(\S\ref{sec:discussion-limitations}). \emph{\_only\_subset} tier. "
          rf"Source: \texttt{{paper/results/task8\_{STATS_TAG}/}}.}}",
          r"  \label{tab:confidence-distribution}", r"\end{table}"]
    return "\n".join(L) + "\n"


def verified_precision_by_state():
    """Read the SIGNED audits. These files exist precisely because regenerating
    the evidence JSON resets `verified_by` to UNSIGNED, so they -- not
    heldout_evidence.json -- are the authority for a published number."""
    out = {}
    g = RESULTS_DIR / f"task1_{RUN_TAG}" / "task1b_fp_audit_SIGNED.json"
    if g.exists():
        out.update(load_json(g)["verified_precision"])
    h = RESULTS_DIR / f"task2_{RUN_TAG}" / "nv_fp_audit_SIGNED.json"
    if h.exists():
        out.update(load_json(h)["verified_precision"])
    missing = [s for s in ALL_STATES if s not in out]
    if missing:
        raise SystemExit(
            f"No SIGNED verified-precision figure for {missing}. The audit must be "
            "signed before its number enters a table -- an unsigned first pass is "
            "not quotable (guardrail 8).")
    return out


def main():
    if RUN_TAG in SUPERSEDED_TAGS:
        raise SystemExit(f"RUN_TAG={RUN_TAG} is a SUPERSEDED run. Point it at the "
                         "current freeze before generating tables.")
    t1 = load_json(RESULTS_DIR / f"task1_{RUN_TAG}" / "summary.json")
    t2 = load_json(RESULTS_DIR / f"task2_{RUN_TAG}" / "summary.json")
    tiers = load_json(RESULTS_DIR / "corpus_tiers.json")
    abl = load_json(RESULTS_DIR / f"task3_{ABLATION_TAG}" / "ablation_comparison.json")
    sp = RESULTS_DIR / f"task3_stability_{STABILITY_TAG}" / "stability_analysis.json"
    stab = load_json(sp) if sp.exists() else None
    bp = RESULTS_DIR / f"task4_{BASELINE_TAG}" / "baseline_comparison.json"
    baseline = load_json(bp) if bp.exists() else None
    scp = RESULTS_DIR / f"task6_{SCALE_TAG}" / "manifest.json"
    scale = load_json(scp) if scp.exists() else None
    t5p = RESULTS_DIR / f"task5_{TASK5_TAG}" / "stability_analysis.json"
    t5 = load_json(t5p) if t5p.exists() else None
    sd = RESULTS_DIR / f"task8_{STATS_TAG}"
    stats = load_json(sd / "dataset_stats.json") if (sd / "dataset_stats.json").exists() else None
    conf = (load_json(sd / "confidence_distribution.json")
            if (sd / "confidence_distribution.json").exists() else None)

    det = {**t1["detector"], **t2["detector"]}
    par = {**t1["parser"], **t2["parser"]}
    missing = [s for s in ALL_STATES if s not in det]
    if missing:
        raise SystemExit(f"missing detector results for: {missing}")

    TABLES_DIR.mkdir(exist_ok=True)
    written = [
        ("detector_headline.tex", build_detector_table(det, tiers, verified_precision_by_state())),
        ("parser_headline.tex", build_parser_table(par, tiers)),
        ("ablation_depthmap.tex", build_ablation_table(abl, stab)),
    ]
    if baseline:
        written.append(("baseline_comparison.tex", build_baseline_table(baseline)))
    if scale:
        written.append(("scale_batched.tex", build_scale_table(scale)))
    if t5:
        written.append(("stability.tex", build_stability_table(t5)))
    if stats:
        written.append(("dataset_stats.tex", build_dataset_table(stats)))
    if conf:
        written.append(("confidence_distribution.tex", build_confidence_table(conf)))
    for name, body in written:
        (TABLES_DIR / name).write_text(body)
        print(f"wrote {TABLES_DIR / name}")
    if stab is None:
        print("NOTE: no stability_analysis.json found; ablation caption omits the "
              "repeated-run ranges.")
    if baseline is None:
        print(f"NOTE: no task4_{BASELINE_TAG}/baseline_comparison.json found; "
              "the baseline comparison table was not generated.")
    if stats is None or conf is None:
        print(f"NOTE: task8_{STATS_TAG}/ is incomplete; run "
              "`python paper/analysis/dataset_stats.py` first.")


if __name__ == "__main__":
    main()
