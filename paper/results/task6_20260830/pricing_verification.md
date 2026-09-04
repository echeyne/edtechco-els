# BEDROCK_PRICING verification — 2026-08-30

Read-only audit of `src/els_pipeline/metrics.py`'s `BEDROCK_PRICING` dict
(which claims to be accurate "as of April 2026") against current Amazon
Bedrock pricing, plus a check of which model ids the deployed dev pipeline
actually invokes. `AWS_PROFILE=kinder-readiness-dev-cli`, region `us-east-1`.
No source file was modified; no Bedrock inference was run.

## Job 1 — rate verification

| Model id in code | Code rate (in / out per 1K) | Verified rate | Match | Source |
|---|---|---|---|---|
| `us.anthropic.claude-opus-4-6-v1` | $0.005 / $0.025 | none found | **UNVERIFIED** | No Price List API entry for "Claude Opus 4.6" in any Bedrock service code (`AmazonBedrock`, `AmazonBedrockService`, `AmazonBedrockFoundationModels`), confirmed both via the CLI and by downloading the full 1032-product bulk offer file. The Bedrock pricing webpage's current-model table is JS-rendered and did not come through as extractable text. The model card explicitly defers pricing to that page. The *predecessor* model, Opus 4.5, is confirmed at the identical $5/M-in, $25/M-out via an AWS ML blog post — suggestive, not proof, for 4.6. |
| `us.anthropic.claude-sonnet-4-6` / `anthropic.claude-sonnet-4-6` | $0.003 / $0.015 | none found for 4.6 | **UNVERIFIED** | No Price List API entry for "Claude Sonnet 4.6". The catalog has "Claude Sonnet 4" (older model) at an identical on-demand rate ($3/M-in, $15/M-out, confirmed live) and "Claude Sonnet 4.5" (immediate predecessor) but the latter's ONLY priced SKUs are reserved-tier per-minute-capacity, not standard on-demand tokens — so not even the predecessor's on-demand rate could be confirmed. |
| `us.anthropic.claude-haiku-4-5-20251001-v1:0` / `anthropic.claude-haiku-4-5-20251001-v1:0` | $0.001 / $0.005 | $0.0011 / $0.0055 (mantle endpoint) | **MISMATCH** (~10% higher) — with caveat | Price List API DOES have a live "Claude Haiku 4.5" entry, but every priced SKU is tagged `mantle` (the bedrock-mantle endpoint), not `bedrock-runtime`, which is the endpoint this pipeline actually calls. No runtime-endpoint on-demand SKU for Haiku 4.5 was found anywhere. This is the only concrete current-generation number this audit could pull, and it doesn't match the code, but it may be pricing the wrong API surface. |

**Bottom line for Job 1: none of the five dict keys could be confirmed as an exact, current, authoritative bedrock-runtime on-demand rate.** The April-2026 date in the code comment cannot be substantiated as still accurate from any source this audit had access to.

### Why the AWS Price List API mostly came up empty

The classic `AmazonBedrock` service code's catalog is stuck on legacy models
(Claude 2.0/2.1/Instant/3 Haiku/3 Sonnet — 1032 products total, zero anything
newer). A second service code, `AmazonBedrockService`, does carry some
current-generation Anthropic pricing (Claude Sonnet 4, Sonnet 4.5, Haiku 4.5),
consistent with the model cards' own note that these are "third-party
model[s] offered and billed through AWS Marketplace" — a different billing
path than the original Bedrock catalog. But coverage inside that second
service code is itself inconsistent (Sonnet 4.5 has no on-demand token price
at all; Haiku 4.5 has one only for the `mantle` endpoint), and neither service
code has anything for the specific ids `claude-opus-4-6-v1` or
`claude-sonnet-4-6` used in this repo.

The AWS Bedrock pricing webpage (`aws.amazon.com/bedrock/pricing/`) does have
the numbers behind a client-side JS accordion, but the documentation-fetch
tooling available in this session could not expand it — only a legacy,
already-superseded "extended access" table (Claude 3.5 Sonnet) rendered as
static text. **A real browser session against the AWS console/pricing page,
or an AWS account-team quote, is the recommended next step** — this audit's
tools hit a genuine ceiling here and should not be read as "the rates don't
exist," only as "this session couldn't extract them."

## Job 2 — the $0 trap

Checked `src/els_pipeline/config.py`'s defaults against `infra/cdk/lib/pipeline-stack.ts`'s CDK source and the **live** `aws lambda get-function-configuration` output for all ten `els-*-dev` pipeline Lambdas.

| Stage | Config default | CDK override | Live deployed env var | Actual runtime id | Priced? |
|---|---|---|---|---|---|
| Detector | `us.anthropic.claude-opus-4-6-v1` | explicit, same value | confirmed same, on both `els-structure-detector-dev` and `els-detect-batch-dev` | `us.anthropic.claude-opus-4-6-v1` | yes (but see UNVERIFIED above) |
| Depth-map (Pass-1) | `us.anthropic.claude-haiku-4-5-20251001-v1:0` | none set | confirmed absent on `els-prepare-detection-batches-dev` | falls back to default | yes (but see MISMATCH above) |
| Parser | `us.anthropic.claude-sonnet-4-6` | none set | confirmed absent on `els-hierarchy-parser-dev` and `els-parse-batch-dev` | falls back to default | yes (but see UNVERIFIED above) |

**The specific suspicion in the task brief — that the deployed parser runs as `us.anthropic.claude-sonnet-4-5-v1` — is NOT confirmed for the current dev deployment.** Every live source checked (CDK source, all deployed Lambda env vars, `.env.example`) agrees on `us.anthropic.claude-sonnet-4-6`.

However, the suspicion is not baseless: `paper/results/task1_20260826/manifest.json` (and, per `tasking/arxiv_paper.md`'s own citation, `task2_20260826/manifest.json`) **records the parser model actually invoked during that eval run as `us.anthropic.claude-sonnet-4-5-v1`** — a third id, distinct from both the deployed default and the dict's key. That manifest reflects a **local** `evaluation/eval_parser.py` run (not the deployed Lambda), which resolves `Config.BEDROCK_PARSER_LLM_MODEL_ID` from `os.getenv(...)` at call time — so whoever produced that recording had that env var set in their own shell/`.env` at the time. It is absent from every other place this audit checked, so it looks like a transient local-environment condition from that specific recording session, not a standing deployment default. But it **did** happen, and it **did** produce exactly the silent-$0 trap the task doc warns about, for the parser stage of that recorded run.

**`unpriced_model_ids`: `["us.anthropic.claude-sonnet-4-5-v1"]`** — absent from `BEDROCK_PRICING`, confirmed used at least once in a recorded eval run, not currently present in any deployed Lambda or in source.

## Job 3 — recommendation

**Cost numbers from this pipeline cannot currently be trusted for publication.**

Minimum changes needed before that changes:

1. Obtain the exact bedrock-runtime on-demand rate for `claude-opus-4-6-v1`, `claude-sonnet-4-6`, and `claude-haiku-4-5-20251001-v1:0` in `us-east-1` from a source this audit's tools couldn't reach — a real-browser view of the Bedrock console/pricing page, an AWS Support case, or an account-team quote — since the Price List API doesn't carry these ids and the pricing webpage's current table is JS-gated.
2. Make `LLMCallMetrics.estimated_cost_usd` fail loud (raise or log an error) when `model_id` isn't a `BEDROCK_PRICING` key, instead of silently pricing at $0.00 via the current `.get(..., {}).get(..., 0)` chain. This is the direct fix for the Job 2 trap and is worth doing regardless of the Job 1 outcome.
3. Log the resolved model id alongside every `PipelineRunMetrics` summary so a paper table can be cross-checked against `BEDROCK_PRICING`'s keys after the fact — this audit had to reconstruct that mapping from old manifests, which shouldn't be necessary.
4. Report **tokens** as the paper's primary hard number (as `tasking/arxiv_paper.md`'s Task 6 notes already intend), with any dollar figure clearly dated and sourced inline, not presented as a bare number.
5. Re-run this verification once a real quote for the three exact ids is in hand, before Task 6's cost/scale table is finalized.

## Files touched

- Wrote `paper/results/task6_20260830/pricing_verification.json` (machine-readable).
- Wrote `paper/results/task6_20260830/pricing_verification.md` (this file).
- No other files modified. No commits made. No Bedrock inference invoked.
