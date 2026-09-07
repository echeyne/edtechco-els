# Task 11 — Nevada Pass-1 sampler A/B at n=5 per arm (2026-09-05)

Run at `code_version_hash` **`14374dba`** on one frozen extraction
(`outputs/08-26-26-2/NV-extraction.json`), `use_cache=False` on all ten draws.
Record: `nv_sampler_ab_n5.json`.

## Verdict: the attribution is RETIRED, not established

`paper/results/task2_20260826/nv_attribution_ab.json` concluded, from **one
draw per arm**, that the layout-stratified sampler *causes* Nevada's two domain
codes to come out right, and stated it as "THE SAMPLER. Confirmed by controlled
A/B." **That conclusion does not survive five draws and is withdrawn.**

| | arm A (layout sampler) | arm B (old stride sampler) |
|---|---|---|
| code accuracy per draw | 44/46, 44/45, 44/46, 44/45, 44/46 | 43/46 ×5 |
| mean | **0.965** | **0.935** |
| stdev | 0.0116 | **0.0** |
| recall per draw | 1.000, 0.978, 1.000, 0.978, 1.000 | 1.000 ×5 |
| `NV-DOM-02` fails | **3/5** | 5/5 |
| `NV-DOM-03` fails | **5/5** | 5/5 |
| `NV-SUB-06` fails | **0/5** | 5/5 |
| description | 3/3 ×5 | 3/3 ×5 |
| depth map | PASS ×5 | PASS ×5 |

**`NV-DOM-03` fails in every draw of both arms.** The claim the n=1 A/B made —
that reverting the sampler reintroduces the two domain-code failures, and
therefore that the sampler fixes them — is false for `NV-DOM-03` and only
partly true for `NV-DOM-02`. At n=1, arm A happened to draw the 46/46 run that
this paper's own stability section already reports as the top of a distribution
rather than its centre.

## What the sampler does do, stated as a rate

The effect is real but smaller and differently shaped than claimed:

- **Mean code accuracy 0.965 against 0.935**, a gap of about 1.4 elements in 46,
  consistent across all five draws — arm A's *worst* draw (44/46) beats arm B's
  every draw (43/46).
- **It eliminates one failure outright.** `NV-SUB-06` (`T.TT` → `TT`) fails 5/5
  under the old sampler and 0/5 under the new one. That, not the domain codes,
  is the sampler's reproducible effect on this document.
- **It roughly halves `NV-DOM-02`** (3/5 against 5/5) without fixing it.
- **It does not touch `NV-DOM-03`.**

## ⚠️ A finding against the sampler, which the n=1 study could not see

**Arm A loses a golden element in 2 of 5 draws** (recall 0.978 = 45/46); arm B
holds recall 1.000 in all five and has **stdev 0.0** on code accuracy — it is
effectively deterministic on this document. So the layout-stratified sampler
buys a modest, consistent code-accuracy gain at the cost of introducing
run-to-run instability that the stride sampler does not have.

That is a genuine trade-off and it is not in the paper. It does not overturn the
sampler's motivation — the Kentucky level-collapse evidence in CLAUDE.md is a
*different and much larger* failure, four levels reported as three, and this
measurement says nothing against it — but it means the sampler must not be
described as strictly better.

## ⚠️ What this contradicts elsewhere in the repository

- `paper/results/task2_20260826/nv_attribution_ab.json` — its `answer`
  ("THE SAMPLER. Confirmed by controlled A/B") and its `conclusion` list are
  **superseded by this file**. Marked as such rather than edited, per the
  standing rule that a recording is the record of what was measured.
- **`CLAUDE.md`, "Where Pass-1 loses a LEVEL (2026-08-24)"** states that the
  three-arm A/B "gives detector code accuracy **46/46**" for the new sampler and
  that NV's domain-code failure is sampler-mediated. The first half does not
  reproduce (44--45/46 across five draws) and the second is now refuted for
  `NV-DOM-03`. **This needs an author decision before editing** — it is a
  measurement claim in a design document, and the surrounding argument about
  Kentucky's level collapse is unaffected.

## What the paper should now say

The hedge ("I report that attribution as suggested rather than established")
can be replaced by a measurement, which is a stronger sentence in both
directions: the causal claim is retired, and what remains is quantified.
Sites: `discussion_limitations.tex` §Nondeterminism and
`experiments_results.tex` §Stability.

The paper's existing NV disclosure is **unaffected and corroborated** — its
caption already reports "NV 44--45/46 across 5 repeat runs against 46/46
recorded", and arm A reproduces exactly that spread.

## Regenerate

```
python -m paper.analysis.nv_sampler_ab_n5 --runs 5 \
    --out paper/results/task11_20260905/nv_sampler_ab_n5.json
```

Ten detector calls on a 15-page document. Independent of the KY and CO goldens,
so it needs no re-run after the annotation work in Task 9.
