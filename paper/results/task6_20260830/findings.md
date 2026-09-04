# Task 6 — batched-path cost, latency and scale (2026-08-30)

Runs executed by Emily on 2026-08-29 (`full08292026`); harvested, verified and
recorded 2026-08-30 at `code_version_hash` **`14374dba`**.

## Corpus tier: `_trimmed`, which is the complete standards content

The run id is `full08292026` and that name is still wrong — neither execution
processed the full published PDF. Verified two independent ways (the Step
Functions execution input names the file, and PyMuPDF gives the page count):

| | file actually processed | pages | wider publication | pages |
|---|---|---|---|---|
| KY | `kentucky_all_standards_2021_trimmed.pdf` | **52** | `kentucky_all_standards_2021.pdf` | 120 |
| CO | `colorado_3_5_trimmed_2020.pdf` | **41** | `colorado_birth_to_8_2020.pdf` | 187 |

**The page-count ratio is NOT a coverage ratio, and the first version of this
file read it as one.** Per the author on 2026-08-31, who performed the
trimming: the `_trimmed` tier retains **100% of the standards**. What was
removed is non-standards matter — preamble, introductions, guiding-principles
essays, appendices, acknowledgements. These runs therefore carry every standard
in both documents, and the earlier framing is **withdrawn**: the "43%" / "22%"
fractions, and with them "full-document scale is a stated limitation and future
work" as a *coverage* claim.

Two corroborations from this recording's own integrity checks: 50 of KY's 52
pages and 37 of CO's 41 carry detected elements, and every gap was read and
confirmed content-free. That density is what a standards-only document looks
like; a 43%-of-content excerpt would not produce it.

⚠️ **Colorado needs one further qualification, and it is not trimming.**
`colorado_3_5_trimmed_2020.pdf` is 41pp and `paper/results/corpus_tiers.json`
records the full Ages 3–5 document as 41pp — the same number, so nothing was cut
from it at all. The 187pp `colorado_birth_to_8_2020.pdf` is the wider
publication the Ages 3–5 band is drawn from (its table of contents puts
"Ages 3–5" at p77, and this file's p3 is that document's p113 verbatim). Every
CO golden and every CO number in this paper is the Ages 3–5 band, so within the
scope the paper measures, coverage is complete — the birth-to-3 and 5–8 bands
are out of scope, not trimmed away.

**Guardrail 1, restated for this recording.** Every table drawn from this file
must still be labelled `_trimmed` tier — it is neither `_only_subset` nor the
full published PDF — **and must say what that tier means**, or a reader takes
`_trimmed` for an excerpt and reads these as partial-document numbers. The run
queue's rationale ("KY 8pp→120pp is the largest relative jump") still does not
describe what ran: it is 8pp→52pp, and those 52pp are all of Kentucky's
standards.

**What does remain a limitation** is page-count scale, which is a cost and
batching question rather than a coverage one. These runs exercise 18 and 17
detection chunks over 4 Map iterations; a document whose non-standards matter is
left in, or a larger standards corpus such as AZ (217pp published), would chunk
further and cost proportionally more. The per-document dollar and latency
figures below should not be extrapolated to untrimmed page counts, and the
batching claim is established at this chunk count, not at an arbitrary one.

## The headline: the batching claim is supported

This is what Task 6 existed for. At the `_only_subset` tier every state produces
≤5 chunks against `MAX_CHUNKS_PER_BATCH=5` and ≤3 domains against
`MAX_DOMAINS_PER_BATCH=3`, so **both batching layers collapse to one batch, the
Step Functions Map has a single iteration, and the merge is a no-op.** That is
why no subset-tier table could support the claim.

| | detection chunks | detection batches | parse batches | raw elements → after merge |
|---|---|---|---|---|
| KY | 18 | **4** | **9** | 363 → **329** (34 merged away) |
| CO | 17 | **4** | **9** | 390 → **300** (90 merged away) |

The Map genuinely iterated four times and the merge genuinely deduplicated. The
prepare → Map → merge path is exercised for real, at 6.5× (KY) and 4.1× (CO) the
subset page count.

## Integrity: checked, not assumed

A green status proves nothing here — CLAUDE.md documents a run that reported
`SUCCEEDED` while 31 of 52 pages had zero surviving coverage. All three
documented silent-failure signatures were checked:

- **Page coverage.** KY 50 of 52 pages carry detected elements (missing p1 title
  page, p14 anecdote-only); CO 37 of 41 (cover, section divider, an
  intentionally-blank page, acknowledgments). Every gap was read and confirmed
  content-free.
- **Pass-1 depth map.** KY reports **4** levels, CO **3** — both matching their
  goldens. This is the check that catches the sampler defect.
- **Zero** detection chunks producing zero elements, **zero** validator
  rejections, **zero** throttling events, 17/17 tasks succeeded with no retries.

## Cost, latency and scale — tokens are the hard number

| Stage | Model | KY calls | KY in/out | CO calls | CO in/out |
|---|---|---|---|---|---|
| Depth map (Pass 1) | Haiku 4.5 | 1 | 12,153 / 438 | 1 | 19,613 / 415 |
| Detection | Opus 4.6 | 18 | 201,574 / 64,530 | 17 | 223,276 / 47,125 |
| Parsing | Sonnet 4.6 | 26 | 164,783 / 85,205 | 27 | 147,315 / 83,862 |
| **Total** | | **45** | **378,510 / 150,173** | **45** | **390,204 / 131,402** |

Wall clock: KY 13m19s, CO 9m52s. Combined 90 LLM calls, 1,050,289 tokens.

The stage split is worth reading against §Method's "cheapest model that
suffices": the depth-map pass costs about 3% of detection's input tokens and
runs once per document, while detection — the hard classification — is the only
stage invoked once per chunk.

**Rates confirmed 2026-08-31** by Emily Cheyne against
<https://aws.amazon.com/bedrock/pricing/> for **Opus 4.6 ($0.005/$0.025 per 1K)** and
**Sonnet 4.6 ($0.003/$0.015)** — the two stages that carry essentially all the cost.
**Haiku 4.5 remains ambiguous** (see `pricing_verification.json`): this file records two
competing rates for it and the confirmation does not say which, a difference worth about
$0.004 of the $8.42 combined total. Detection and parsing dollar figures are therefore
publishable with the date and source cited; the depth-map column should wait.
**Tokens remain the primary hard number** (Task 6 step 4).

Historical note — before that confirmation: **Dollar figures were withheld.** `BEDROCK_PRICING` is hardcoded as of April 2026
and **none of its five rates could be verified on 2026-08-30**. The AWS Price
List API's `AmazonBedrock` service code catalogs only legacy Claude 2.x/3.x
models; a second service code has partial current-generation coverage but no
entry for Opus 4.6 or Sonnet 4.6, and its only Haiku 4.5 entry is a
`mantle`-endpoint rate about 10% above the hardcoded one, for a different
endpoint than the pipeline calls. If the hardcoded rates happen to be right the
combined cost is ≈$8.42, but that number must not be published until the rates
are confirmed. See `pricing_verification.md`.

## ⚠️ Task 6 step 3's stated method does not exist

Step 3 says to pull per-stage metrics from `PipelineRunMetrics.summary()`, and
the plan's Key Background asserted "cost data already exists" on that basis.
**`PipelineRunMetrics` and `log_pipeline_run_summary` are dead code** — defined
in `src/els_pipeline/metrics.py` and referenced nowhere else in `src/`.

The numbers above were reconstructed instead from the per-call `LLM_METRICS:`
log lines that `call_bedrock_llm` emits, read out of the stage Lambdas'
CloudWatch log groups, attributed per run via CloudTrail `InvokeModel` events,
and split into stages **by `model_id`**. Per guardrail 6, that reconstruction
*is* the regeneration procedure — reproducing these numbers means following it,
not step 3 as written.

Splitting by `model_id` is a workaround for two further instrumentation defects,
both verified and both affecting auditability rather than output:

1. `stage` is hardcoded to `"detection"` in `detector.py:1235`, so the Haiku
   depth-map call is logged as a detection call.
2. `metrics_context` is never passed at the real per-chunk detection call site
   (`detection_batching.py:243`) or per-domain parse call site
   (`parse_batching.py:232`), so `run_id` / `state` / `batch_index` are blank on
   every production metrics line.

The split works only because the three stages happen to use three different
models. It would break the moment two stages shared one.

## The token-forecast gap, closed

The day's account-wide Opus spend was 727,798 in / 198,073 out, while these two
runs account for 424,850 / 111,655 — less than half the ~1.9M forecast, which
initially looked like missing coverage. It is not. The remainder (302,948 in /
86,418 out, 27 direct Opus calls under the `kinder-ready-dev-cli` IAM user from
a local machine, 10:15–10:59 -07:00) was spent entirely *before* either
execution started. The two pieces sum to the CloudWatch total exactly.

So the forecast gap is explained by an unrelated local block earlier that
morning, plus a forecast that was scaled from **published** page counts (120pp
and 187pp) rather than standards-content page counts (52pp and 41pp). It is not
dropped content — which the tier note above and the page-coverage check both
independently confirm.
