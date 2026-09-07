# Task 10 — the whole-document single-prompt arm (pilot, 2026-09-05)

Recorded at `code_version_hash` **`14374dba`**, on the `_only_subset`
extractions of `outputs/08-26-26`. **n=1 per state — this is a pilot, not a
publishable comparison** (see "Before this is published" below).

## The question

`REVIEW_assessment.md` §1 names this the missing baseline: the rule-based
extractor answers "what can a regex not do", not "why not just prompt it". So:
hand the model the whole document in one call, with **no Pass-1 depth map, no
chunking, no overlap, no merge, and no deterministic repairs**, and grade it
with the same suite, the same matcher and the same goldens.

Everything else is held constant — same prompt body (`build_detection_prompt`'s
long-standing `depth_map=None` branch), same model, same temperature, same
extractions. Only JSON extraction survives from the pipeline, because a response
that cannot be parsed cannot be graded, and that is plumbing rather than a
repair.

## Result

| state | full method recall | **arm** recall | full method code acc. | **arm** code acc. |
|---|---|---|---|---|
| AZ | 1.000 | **1.000** | 4/4 | **4/4** |
| CA | 1.000 | **0.000** | 25/25 | **— (no output)** |
| CO | 1.000 | **0.429** | 7/7 | 3/3 ⚠️ over 3 pairs, not 7 |
| KY | 1.000 | **1.000** | 44/44 | **28/44 (0.636)** |
| NV | 1.000 | **1.000** | 46/46 | **46/46** |
| TX | 1.000 | **1.000** | 8/8 | **5/8 (0.625)** |

Full-method figures from `paper/results/task1_20260826/detector_golden4.json`
and `task2_20260826/detector_heldout2.json`, same code version.

⚠️ **Code accuracy is graded over MATCHED PAIRS ONLY, so the denominators are
not comparable when recall differs.** CO's `3/3` is three of seven golden
elements, not seven; it must never be printed beside the full method's `7/7`
without that qualification. KY, NV, TX and AZ match on all elements, so their
denominators *are* comparable and their columns can be read directly.

## Finding 1 — the failure is categorical, not gradual: California is lost entirely

CA's single call emitted **exactly 16,000 output tokens**, which is
`detector.LLM_MAX_TOKENS`. The JSON array was cut off mid-object and never
closed, so nothing parsed and **0 of 25 golden elements were recovered**. The
chunked method scores 25/25 on the same extraction.

This is the strongest available answer to "why not just prompt it", and it is
not a quality argument at all. A single prompt has one output budget for the
whole document, so exceeding it loses **the document**; chunking bounds the same
overflow to **a chunk**. The failure mode is the same shape as the absent-code
defect CLAUDE.md documents, one level up: there, one bad element destroyed its
chunk; here, one truncation destroys the run.

⚠️ **Arizona was within 11% of the same cliff** (14,292 of 16,000 output
tokens), and Arizona scores 1.000. So the arm's success on a document says
nothing about the next document — the margin is invisible in the score and is a
function of document size, not of prompt quality. Any sentence built on AZ's or
NV's success must carry this.

## Finding 2 — where the repairs go, code accuracy goes

The two states where recall holds and code accuracy falls show exactly what the
deterministic layer buys, and the mismatches name the missing repair:

- **KY 44/44 → 28/44.** Twelve of the sixteen failures are the model sampling
  its own abbreviation rule (`MFAAA` for `MFAAD`, `PSSAU` for `PSAUC`, `WPSDS`
  for `PSDSP`, `EWCOM` for `ECOMN`) — the 25% churn measured on this exact
  document in 2026-08-01, which is why `derive_code_from_title` executes the
  rule in Python. The rest are the missing de-label repair (`Standard 1` where
  the golden has `Approaches to Learning Standard 1`).
- **TX 8/8 → 5/8.** All three are the missing anchoring: `I.A` where the golden
  has `A`, `I.B` where it has `B`, `I.B.2` where it has `2`.

Since `standard_id` is `{country}-{state}-{year}-{indicator_code}`, each of
those is a different Aurora primary key for the same standard. The arm's recall
column can look identical to the full method's while writing sixteen wrong
primary keys.

## Finding 3 — it is not a strawman

AZ and NV score **1.000 recall and full code accuracy** with no depth map, no
chunking and no repairs. NV in particular — the held-out canary, whose printed
namespace skips a level — comes back 46/46. That is worth reporting plainly: at
the subset tier, on documents that fit in one prompt and do not overflow the
output budget, the simple approach can match the architecture.

## Finding 4 — Colorado degrades quietly

CO recall 0.429: four of seven golden elements lost, **both strands** among them
(`per_level` strand tp=0, fn=2, fp=7). The arm emitted 61 elements and simply
classified the strand level wrongly throughout. This is the level-collapse
signature the depth-map ablation (Task 3) produces on Kentucky, appearing here
for the same reason — no Pass-1 — on the document whose middle level is hardest.

## ⚠️ Scope: what a good score here would and would not mean

All six subset extractions are **3.7K–7.9K tokens** and fit in one prompt. So
the honest reading of AZ's and NV's 1.000 is *the architecture is unnecessary at
the `_only_subset` tier, for documents that fit*. It says nothing about the
`_trimmed` or full tiers, where the document does not fit and chunking is not
optional — and CA already shows what happens at the boundary. This caveat is
written into `whole_document_pilot.json` under `⚠️_scope` and must travel with
every sentence drawn from this file.

## Before this is published

- **n=1 is not enough, and this arm is the worst place to accept it.** It is a
  single nondeterministic call per document, so it is *more* exposed to sampling
  than the chunked method, not less. Re-run at `--stability-runs 3` minimum.
  The paper's own stability section (§8.5) forbids drawing a comparison from one
  draw, and this file is bound by that.
- **Re-run CA specifically.** Whether the truncation is deterministic at this
  document size, or a sampling-length effect that sometimes clears the cap, is
  the difference between "a hard limit" and "a coin flip", and they need
  different sentences.
- **Consider reporting output-token headroom per state** alongside the scores.
  It is free, it is already in the `LLM_METRICS` log lines, and it is the
  variable that actually predicts this arm's failure.

## Regenerate

```
python -m evaluation.baselines.eval_whole_document \
    --extraction-dir outputs/08-26-26 \
    --stability-runs 3 \
    --report-json paper/results/task10_YYYYMMDD/whole_document.json \
    --output-dir  paper/results/task10_YYYYMMDD/review
```

Cost of this pilot: 6 Opus calls, ~113K input / ~55K output tokens.
The unparsed CA response is kept at
`evaluation/.cache/wholedoc-CA-7e5f254c800917cf-14374dba.unparsed.txt`.
