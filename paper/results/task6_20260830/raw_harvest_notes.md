# Task 6 raw harvest — notes and caveats (2026-08-30)

This is a read-only investigation of the two `full08292026` Step Functions
executions (`kentucky-execution-1788029003`, `colorado-execution-1788028830`).
No source files were modified, no pipeline was run, no Bedrock tokens were
spent by this investigation. Full structured data is in `raw_harvest.json`
alongside this file; raw downloaded S3/log artifacts are under `raw/`.

> ## ⚠️ CORRECTION, 2026-08-31 — read this before the section below
>
> This file is kept as the record of what the 2026-08-30 harvest found. One of
> its conclusions is **withdrawn**: it reads the trimmed/published page ratios
> (52/120, 41/187) as coverage fractions and recommends a re-run on that basis.
>
> Per Emily, who performed the trimming: **the `_trimmed` tier retains 100% of
> the standards.** What was removed is non-standards matter — preamble,
> introductions, essays, appendices, acknowledgements. So these executions did
> process every standard in both documents, and the recommendation below
> ("re-run against the 120pp and 187pp files") is **not** needed for coverage.
> Colorado additionally was never trimmed at all: its 41pp file equals the full
> Ages 3–5 document, drawn from a wider 187pp birth-to-8 publication whose other
> age bands are out of scope rather than cut.
>
> What survives from the section below: the run_id `full08292026` is still a
> misnomer, and the **page-count** observations are still the right basis for
> the cost/latency caveats — including the Pass-1 token-budget point, which is
> about document size, not coverage. See `findings.md` and `manifest.json` for
> the corrected framing; they, not this file, are the recording.

## The headline problem: these are not full-document runs

Despite the run_id containing "full08292026", **neither execution touched the
document Task 6 needs measured**:

- KY execution's `file_path` was `US/KY/2021/kentucky_all_standards_2021_trimmed.pdf`.
  That file is 52 pages (confirmed both from the extraction stage's own
  `total_pages: 52` and from opening the local copy with PyMuPDF). The actual
  120-page document is `standards/kentucky_all_standards_2021.pdf` — a
  different file that was never referenced by this execution's input.
- CO execution's `file_path` was `US/CO/2020/colorado_3_5_trimmed_2020.pdf`,
  41 pages. The actual 187-page document is
  `standards/colorado_birth_to_8_2020.pdf` — again, never referenced.

Both trimmed files are the SAME files used in the 2026-08-22 through
2026-08-26 eval/regression runs already recorded elsewhere in this repo. So
these two "full" executions are, from the pipeline's point of view,
re-runs of already-exercised inputs, not a new full-scale test.

I could not determine from AWS-side evidence *why* the wrong file_path was
supplied — that's a question for whoever constructed the Step Functions input
payload (a manual `aws stepfunctions start-execution` invocation, a script,
etc.). CloudTrail's `StartExecution` event would show the exact input and
caller if that's worth pulling next; I did not chase it further since it
doesn't change the verdict.

**Recommendation for the paper**: before this table can honestly claim a
"full-document" tier, re-run against `kentucky_all_standards_2021.pdf` (120pp)
and `colorado_birth_to_8_2020.pdf` (187pp) explicitly, and verify both are
present and correctly named in the raw S3 bucket first (they were not
referenced in either raw-documents S3 prefix by these runs, though the local
copies do exist under `standards/`).

## Within the documents actually processed, coverage was clean

To be fair to the pipeline itself: on the 52pp KY and 41pp CO trimmed
documents, coverage was complete. The handful of "missing" pages (KY: 1, 14;
CO: 1, 2, 40, 41) were individually checked against the extraction's raw text
blocks and are all legitimately content-free (title/cover pages, a section
divider, an explicitly blank page, an acknowledgments page, and one
anecdote-only page). No zero-element detection chunks, no depth-map level
loss (KY correctly inferred 4 levels, CO correctly inferred 3, both matching
their goldens), no validator rejections, no throttling, no partial/error
stage statuses. This means the specific silent-failure modes CLAUDE.md warns
about (absent-code chunk loss, Pass-1 level collapse) did **not** recur here —
but that's a weaker claim than "the pipeline handles full documents
correctly," because these documents are 43% (KY) and 22% (CO) of the published
page counts — [2026-08-31: a PAGE-COUNT fraction, not a coverage one; see the
correction at the top of this file] — and several of the documented defects
were scale-dependent
(e.g. the Pass-1 sampler only engages above a ~6000-token budget, which the
real 120pp/187pp documents will hit much harder than these trimmed
versions did).

## The token/cost gap: two independent, fully-reconciled causes

The task brief noted the day's Opus spend (925,871 tokens) was under half the
~1.9M forecast. I found the exact accounting:

1. **The pipeline itself only processed 536,505 Opus-equivalent... actually
   total (Opus+Sonnet+Haiku) tokens across both runs: 1,050,289.** Of the
   day's 727,798 input + 198,073 output Opus tokens specifically, only
   424,850 in / 111,655 out (58%/56%) came from the two Step Functions
   executions (confirmed by CloudWatch Logs `LLM_METRICS:` lines AND
   independently by CloudTrail `InvokeModel` events from the
   `els-detect-batch-dev` Lambda — both methods agree exactly).
2. **A separate block of 27 Opus calls (302,948 in / 86,418 out) came from
   direct/local Bedrock invocations under the `kinder-ready-dev-cli` IAM
   user** — i.e., a human or local script using the same CLI credentials this
   investigation used, NOT a Lambda function. These 66 total local calls (27
   Opus + 31 Sonnet + 8 Haiku) all occurred between 10:15:23 and 10:59:06
   -07:00, which is **before both Step Functions executions started**
   (11:40:36 and 11:43:25). They are not part of either `full08292026` run.

Adding local-Opus (302,948/86,418) + pipeline-Opus (424,850/111,655) gives
727,798/198,073 exactly — the full account-wide CloudWatch total for the day,
with zero residual. So the forecast-vs-actual gap isn't really one
phenomenon: it's the pipeline processing much smaller documents than
expected, PLUS an unrelated block of local testing that happened to run the
same morning. I could not determine what the local calls were for (CloudTrail
doesn't log prompt content) — most likely a local/direct-path test or eval
run against KY/CO shortly before someone triggered the two executions, but
that's inference, not confirmed.

## Two real (independent of the wrong-document issue) instrumentation defects found

While reconstructing the token table I found the code responsible cannot
actually attribute its own metrics:

1. **`metrics_context` is never passed at the two call sites that matter.**
   `detection_batching.py`'s per-chunk detection call
   (`call_bedrock_llm(prompt, prefill="[")`, line 243) and
   `parse_batching.py`'s per-domain parsing call (`call_bedrock_llm(prompt)`,
   line 232) both omit `metrics_context` entirely, so every `LLM_METRICS:`
   log line for actual detection/parsing work has `run_id`, `country`,
   `state`, `batch_index`, and `chunk_index` all blank. The only call site
   that does it right is the once-per-document Pass-1 depth-map call in
   `prepare_detection_batches` (`detection_batching.py:85`), which correctly
   threads `run_id`/`country`/`state` through.
   I had to reconstruct per-run attribution myself by cross-referencing each
   Lambda invocation's `requestId` against the exact `RequestId` values
   recorded in each Step Functions execution's `TaskSucceeded` history — this
   worked and produced zero unclassifiable log lines, but a production
   cost dashboard built directly on these logs today would silently merge
   concurrent runs together (which is exactly what happened when I first
   tried a naive time-window filter — KY and CO's Lambda invocations
   overlap in wall-clock time on the shared `els-detect-batch-dev` /
   `els-parse-batch-dev` functions).
2. **`stage` is hardcoded to `"detection"`** inside `detector.py`'s
   `call_bedrock_llm`, regardless of which `model_id` was actually passed in.
   So the Pass-1 Haiku depth-map call — which uses a completely different
   model and purpose — is logged with `stage: "detection"`, indistinguishable
   by field from the real per-chunk Opus detection calls. I separated them
   only by cross-referencing `model_id` and which Lambda's log group emitted
   the line.

Neither defect affects correctness of the pipeline's actual output — only the
ability to audit its own cost after the fact. Worth fixing if Task 6's cost
table is meant to be reproducible from CloudWatch alone in the future,
independent of this kind of manual reconstruction.

## Model IDs — the $0-cost concern did not materialize

`BEDROCK_PARSER_LLM_MODEL_ID` defaults to `us.anthropic.claude-sonnet-4-6`,
and that is exactly the model ID actually used by both runs (confirmed via
`LLM_METRICS:` log lines and via CloudTrail `requestParameters.modelId`).
That string is present verbatim as a `BEDROCK_PRICING` key in `metrics.py`,
so parsing cost was computed correctly (not silently $0). The hypothesized
`us.anthropic.claude-sonnet-4-5-v1` id was not seen anywhere in either run's
logs or CloudTrail events for 2026-08-29.

## Things I could not verify (out of scope for a read-only AWS/log investigation)

- Aurora content: persistence reported `records_persisted: 214` (KY) /
  `240` (CO) with `errors: 0`, taken from the Lambda's own success payload. I
  did not query the Aurora cluster directly to confirm those rows exist with
  correct field values.
- The custom `ELS/Pipeline` CloudWatch namespace (`emit_cloudwatch_metrics`)
  was not queried; the structured `LLM_METRICS:` log lines carry the same
  underlying data and were sufficient (and let me cross-validate against
  both `AWS/Bedrock` CloudWatch metrics and CloudTrail independently, which
  agreed to the token exactly).
- Why the wrong (trimmed) `file_path` was supplied to both executions —
  outside AWS API/log evidence, would need to ask whoever triggered them.
