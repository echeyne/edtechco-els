# Task 1 re-run — handoff (post-CDK-fix)

**Written:** 2026-07-17. **For:** a fresh context window re-running arXiv-paper Task 1 now that the depth-map IAM fix is deployed and validated. Task definition lives in [tasking/arxiv_paper.md](../../tasking/arxiv_paper.md) (Task 1 + new Task 1b); prior results in `paper/results/task1_*`.

## Why we're re-running

The original Task 1 run (2026-07-16, against `outputs/07-16-26-2`) was completed and sanity-checked, but the **deployed pipeline's detection output was corrupted**: `els-detection-batch-preparer-role-dev` lacked `bedrock:InvokeModel`, so the prepare step's Pass-1 depth-map inference (Haiku) failed with `AccessDeniedException`, an empty `{}` depth map was persisted, and **every detection batch ran in no-depth-map mode**. That misclassified Colorado's Social-Emotional goal statements as `sub_strand`, collapsing CO parser coverage to 0.333 (vs 1.000 on a direct-path detection).

**Root cause was IAM, not stale code** — CloudTrail confirmed the Lambdas were on current code; the grant was simply missing from the CDK template. **Fix (applied + committed this session, now deployed & validated by Emily):** added `BedrockInvokeAccess` + `CloudWatchMetricsAccess` to `DetectionBatchPreparerLambdaRole` in [infra/cdk/lib/pipeline-stack.ts](../../infra/cdk/lib/pipeline-stack.ts) (matching the processor role). Verified via `cdk synth` before deploy.

## The one nuance that decides what actually needs re-running

The two eval suites depend on the deployment **differently**:

- **Detector eval** runs `detect_structure()` **directly in-process** on `{STATE}-extraction.json`. It never touches the deployed Lambda and already ran with a working depth map (Bedrock access via the CLI profile). **Its numbers were already correct and should be reproducible; the CDK fix does not change them.** Re-run it anyway for a same-session, same-outputs-folder pair — cheap and good hygiene.
- **Parser eval** runs `parse_hierarchy()` directly, but its **input `{STATE}-detection.json` is the frozen *deployed batched-path* detection**. This is the file that was corrupted. **This is the suite whose CO numbers should now recover.** Re-running it against fresh post-fix detections is the whole point.

Expected post-fix outcome to confirm: **CO parser coverage 0.333 → 1.000, and the `CO-INDICATOR-PARENT-IS-STRAND` regression FAIL → PASS.** That should match `paper/results/task1_parser_CO_on_direct_detection.json` (the direct-path proof captured last session), confirming batched≈direct convergence once the depth map works. AZ/CA/TX detections showed no artifact last time but re-verify — the depth-map failure was pipeline-wide, so their batched detections may shift slightly too.

## Steps

1. **Get fresh outputs from a post-fix pipeline run.** Emily has deployed + re-run the pipeline; download with the `download-pipeline-outputs` skill (e.g. "download pipeline outputs for run N"), which writes a date-stamped `outputs/MM-DD-YY/` folder with `{STATE}-extraction.json`, `{STATE}-detection.json`, `{STATE}-parsing.json` for AZ/CA/CO/TX. **Confirm the run post-dates the deploy** and that its CO depth map is non-empty:
   - Quick check: the deployed run's `els-prepare-detection-batches-dev` CloudWatch logs should show the Haiku call succeeding (no `AccessDeniedException`) and the persisted `.../intermediate/detection/depth_map/*.json` should be > 2 bytes (the failure wrote a 2-byte `{}`).
   - Or just check the downloaded `CO-detection.json`: **~65 elements, 0 `sub_strand`s** = fixed; **93 elements with `sub_strand`s** = still the old artifact (stop, the run predates the fix).

2. **Set env.** The eval harness does **not** load `.env` (no `dotenv` anywhere in `src/` or `evaluation/`); model IDs come from `config.py` defaults. Activate venv and set the profile:
   ```bash
   source venv/bin/activate
   export AWS_PROFILE=kinder-readiness-dev-cli
   export NEW_OUT=outputs/<MM-DD-YY>        # the folder just downloaded
   ```

3. **Run both suites, no-cache, all four states**, writing to *new* result files (keep the 07-16 files for before/after):
   ```bash
   python -m evaluation.eval_detector --extraction-dir $NEW_OUT --no-cache \
     --report-json paper/results/task1_detector_golden4_v2.json \
     --output-dir paper/results/task1_review_detector_v2
   python -m evaluation.eval_parser --detection-dir $NEW_OUT --no-cache \
     --report-json paper/results/task1_parser_golden4_v2.json \
     --output-dir paper/results/task1_review_parser_v2
   ```
   (LLM outputs cache in `evaluation/.cache/` keyed by input content-hash; `--no-cache` forces genuine re-runs for recorded numbers.)

4. **Re-consolidate.** Point the consolidation script at the v2 files (it currently hardcodes the non-suffixed names — either edit the paths at the top of [paper/analysis/consolidate_task1.py](../analysis/consolidate_task1.py) or copy v2 over the base names once you're happy). It computes the paper-facing extras the raw suite omits: annotation-coverage-bounded precision ceilings, and the **level-agnostic** confusion re-pairing (the suite's built-in confusion matrix is structurally diagonal because `level` is in the match key — do not report it).

5. **Diff against last session** and update [paper/results/task1_findings.md](task1_findings.md) + [task1_manifest.json](task1_manifest.json): record the new outputs folder, git commit, and confirm/ærevise the "CO recovers" claim (finding 3). If CO now passes, mark finding 3 resolved and note the batched≈direct convergence.

## Carry-forward facts (don't rediscover these)

- **Corpus tier:** every Task 1 number is `_only_subset` (9–15pp trimmed subset PDFs), NOT full documents. State the tier on every table (guardrail 1).
- **Models (config.py defaults):** detector `us.anthropic.claude-opus-4-6-v1`; depth-map `us.anthropic.claude-haiku-4-5-20251001-v1:0`; parser `us.anthropic.claude-sonnet-4-6`.
- **Golden-data fixes already applied last session (in the repo now — do not redo, do not revert):**
  - `evaluation/ground_truth_detector/CA.json` — reordered the FLD Grammar/Sharing/Participating block into document order (was breaking domain tagging; score-neutral, 25/25 both ways).
  - `evaluation/ground_truth_parser/TX.json` — de-duplicated `test_case_id` TX-IND-04-PK4 (→ TX-IND-05-PK4), fixed a `source_page` (9→7) and a `strand.code` transposition typo (IV.A→VI.A).
  - Pre-fix raw reports preserved as `paper/results/task1_*_pre_goldenfix.json`.
- **Detector "precision" is decided (guardrail 8):** never report the suite's raw precision as detector quality — it's annotation-coverage-bounded (goldens are 5–25-element spot-checks vs 28–122 in-scope detections; all AZ "FPs" verified real). Report **per-level recall** from the suite + a **verified precision / hallucination rate from the manual FP audit (Task 1b)**. No exhaustive golden extension, no further PDF trimming.
- **Parser field accuracy carries upstream noise:** AZ's mismatches are all Textract single-space word fusions (`firmfoundation`), not hierarchy errors; TX has curly-vs-straight-quote diffs. One genuine parser bug: CA swapped the Discovering/Developing column descriptions for CA-IND-07.
- **Open, still needs Emily:** (a) TX parser golden expects `indicator.description: None` but the parser emits the "Child Behaviors" outcome text — annotation-convention call; (b) whether the paper's parser numbers should come from batched (deployed) or direct-path detections — post-fix they should converge, so verify and then decide.
- **Last session's headline numbers (baseline to compare against):**
  - Detector recall: AZ 1.000, CA 1.000, CO 0.857, TX 0.750; all depth maps PASS; 0 level misclassifications; all 11 regression cases PASS.
  - Parser coverage / field-acc: AZ 1.000/0.926, CA 1.000/0.995, **CO 0.333/0.981 (the one to watch)**, TX 1.000/0.958; 0 ID collisions anywhere.
- **Related still-open chips:** "Fix stale detect_structure docstring claims" (docstring falsely says it flags low-confidence elements for review — a guardrail-2 landmine) and "Deploy pipeline + verify depth-map fix" (may already be done if Emily validated).

## Deliverables of the re-run

Updated `paper/results/task1_*` (v2 suite reports + refreshed summary/findings/manifest), with finding 3 resolved if CO recovers, all regenerable from the recorded commands against the new `outputs/MM-DD-YY/` folder.
