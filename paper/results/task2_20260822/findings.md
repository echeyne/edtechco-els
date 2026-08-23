# Task 2 (re-record) — held-out generalization: Nevada (2023) and Kentucky (2021)

Run 2026-08-23T00:12:52Z–00:21:56Z UTC against `outputs/08-22-26-4`, `--no-cache`,
code version hash **`288c64f1`**, commit `628829b`. Task 1
(`paper/results/task1_20260822/`) ran in the same invocation at the same hash on
the same outputs folder and is directly comparable.

This folder **supersedes `paper/results/task2_20260816/`**, which is retained only
as the reproducibility record. Three things moved: source (hash `3b445471` →
`2ac17ac2` → `288c64f1`), inputs (new outputs folder), and the held-out goldens
themselves — **NV detector 41 → 46 and NV parser 15 → 24** after Emily's
exhaustive annotation pass.

**Corpus tier: `_only_subset`.** NV is 15pp trimmed from 98; KY is 8pp trimmed
from 120. No number in this folder is a full-document number.

---

## Headline results

### Detector — fresh direct-path run, graded against the held-out detector goldens

| | NV | KY |
|---|---|---|
| golden elements | 46 | 44 |
| in-scope detections | 53 | 44 |
| **recall** | **1.000** | **1.000** |
| per-level false negatives | **0 at every level** | **0 at every level** |
| raw precision | 0.8679 | **1.000** |
| annotation-coverage ceiling | 0.8679 | 1.0000 |
| `golden_is_exhaustive` | `false` | **`true`** |
| **verified precision** (FP audit) | **0.9811** (52/53) | **1.000** (44/44) |
| code accuracy | 44/46 | **44/44** |
| description accuracy | 2/3 | **26/26** |
| depth map | PASS | PASS |
| regression cases | 3/3 PASS | 3/3 PASS |

Per-level true/false positives — NV: domain 3/0, strand 12/5, sub_strand 7/1,
indicator 24/1. KY: all 44 matched, zero unmatched detections.

### Parser — run on the deployed batched detections in `outputs/08-22-26-4`

| | NV | KY |
|---|---|---|
| golden standards | 24 | 26 |
| coverage | **24/24** | **26/26** |
| field accuracy | **1.0000** | **1.0000** |
| field accuracy over asserted cells only | **1.0000** | **1.0000** |
| fully correct standards | **24/24** | **26/26** |
| `standard_id` collisions | 0 | 0 |
| regression cases | 3/3 PASS | 4/4 PASS |

**Generalization holds, and the parser half is perfect on both held-out states.**
Every one of the 50 held-out standards is reproduced with every graded cell
correct. Detector recall is 1.000 at every level in both states. This is the
strongest held-out result recorded to date and it is what the paper's
generalization claim should rest on.

---

## What the paper may and may not claim

### 1. Kentucky's detector golden is EXHAUSTIVE, so KY's precision is a real precision number. This remains the single most load-bearing fact here.

`heldout_evidence.json` → `annotation_coverage.KY.golden_is_exhaustive` is
**`true`**: 44 golden elements against 44 in-scope detections, with **zero**
unmatched detections (`fp_audit_first_pass.KY.n_extras_audited` = 0). KY's raw
precision **1.000** is therefore a genuine hallucination rate, not an
annotation-coverage figure, and guardrail 8's carve-out applies. KY is still the
only state that qualifies.

KY is additionally perfect on both graded content fields — code **44/44**,
description **26/26** — on a golden whose description denominator is 26, which is
the one sound description denominator in the corpus.

### 2. NEVADA DOES NOT QUALIFY, and its raw precision must never be reported as a hallucination rate — this run demonstrates why arithmetically.

NV's raw precision is **0.8679** and its annotation-coverage ceiling is
**0.8679**. They are equal to four decimals, because the golden holds one entry
per element (46) while the detector emits 53 in-scope elements for a document
that reprints 6 headings on a second page spread. The raw figure is a pure
restatement of annotation coverage and carries **no information about
correctness**.

⚠️ **NV's ceiling moving 0.7736 → 0.8679 is an ANNOTATION-COVERAGE change, not a
quality improvement.** It moved because the golden grew from 41 to 46 entries.
Nothing about the detector got better. The paper must label it that way or it
misleads.

NV's real number comes from the audit: **verified precision 0.9811 (52/53)**,
one hallucination.

### 3. The FP audit is now 7 verdicts, not 12, and it is SIGNED as of 2026-08-23.

Emily reviewed all 7 and changed **0** verdicts
(`nv_fp_audit_signoff.md`, `nv_fp_audit_SIGNED.json`). The count fell from 12
because the 5 previously-unannotated elements are now annotated.

| verdict | count |
|---|---|
| `real_repeat_of_matched` | 6 |
| `real_unannotated` | 0 |
| `hallucinated` | 1 |

`real_unannotated` is now **zero**, which is the measurable consequence of the
exhaustive pass: every leftover is either a correct re-detection of a genuinely
reprinted heading or the one known hallucination.

**NV verified precision 0.9811 is now quotable**, and the paper sentence "all
unmatched in-scope detections of the recorded run were manually audited by the
author" is TRUE FOR NEVADA (and vacuously for KY, which had zero extras).

**Task 1b landed 2026-08-23**, so that sentence is now true for **all six
states**. Corpus-wide: 297 in-scope detections, 1 hallucination, **verified
precision 0.9966**.

### 4. The one hallucination is `SS.CI.PK3`, and it is now confirmed by direct evidence rather than inference.

Detected title: *"Recognize and resolve conflicts with peers with adult guidance."*

Verified against `outputs/08-22-26-4/NV-extraction.json` this run:

- **`"with adult guidance"` occurs 0 times in the entire NV extraction.**
- `SS.CI.PK3` appears in exactly **one** extraction block (index 218, page 5).
- Its true text reconstructs from the interleaved indicator column — blocks
  218 / 221 / 223 / 226 — as
  *"SS.CI.PK3. Recognize and resolve conflicts with peers in an age-appropriate manner."*

⚠️ **NEITHER of the audit's automated text probes is sufficient on its own, and
the verdict above does NOT rest on them.** Measured 2026-08-23:

- `title_contiguous_in_extraction` **over-flags**. NV pages 5 and 10 are
  multi-column tables that flatten into interleaved reading order, so *correct*
  titles also score 0 as contiguous substrings — `"Recognize and resolve
  conflicts"` and `"in an age-appropriate manner"` each occur 0 times
  contiguously. Verdict 5 (`S.EO`, p10) is flagged `contiguous=false` for exactly
  this reason and is real. Run over the golden four, this probe flags **39 rows**
  (CO 27, TX 12) as hallucinated that are plainly real text broken across lines.
- `title_spans_found_in_order` **under-flags**, and cannot rescue it. The greedy
  longest-first decomposition shatters a title into fragments short enough to
  occur somewhere in any document. **This very row passes it**: its spans come
  back `'Recognize and'` / `'resolve conflicts with'` / `'peers with'` / `'adult'`
  / `'guidance'`, all found, even though the phrase `"with adult guidance"`
  occurs **0 times**. So "all spans found" does NOT mean real.

What actually established this verdict is phrase-level checking of the
**differing portion** plus structural comparison against the matched twin — the
fabricated tail as a phrase, the single `SS.CI.PK3` block, and the truncated
`source_text`. Any future audit must do the same; do not let either automated
probe stand in for it.

### 5. NV's 2 code misses are both domains, and CLAUDE.md's 2026-08-16 diagnosis is reproduced EXACTLY — including the warning that one apparent pass is a coincidence.

Code accuracy 44/46. Both misses are `domain.code`, from
`heldout_evidence.json` → `nv_domain_code_diagnosis`:

| domain | golden | detected | derivable shape | grounded | golden would be grounded | `derive_code_from_title` |
|---|---|---|---|---|---|---|
| Social Studies | `SS` | `SS` ✅ | true | **false** | **false** | `SS` |
| Science | `S` | `Science` ❌ | **false** | true | true | `SCIE` |
| Technology | `T` | `TECH` ❌ | true | **false** | **false** | `TECH` |

- **`Technology`** is the clean confirmation of the documented failure: derivable
  shape, ungrounded, so `_resolve_code` recomputed it — and the golden code `T`
  would **also** be ungrounded in that element's `source_text`. Even a successful
  recovery of `T` would have been overwritten. The `source_text` citation is the
  load-bearing half, exactly as CLAUDE.md warns.
- **`Science`** never reached `_resolve_code`: emitted as the literal `Science`,
  which contains lowercase and so fails `_DERIVABLE_CODE_RE`.
- ⚠️ **`Social Studies` passes for the wrong reason and must not be cited as
  evidence the code-recovery clause works.** `SS` is ungrounded and was
  recomputed; `derive_code_from_title("Social Studies")` merely happens to return
  `SS`. A future change to `derive_code_from_title` or the connector list would
  silently turn this pass into a failure.

Blast radius is bounded and unchanged: NV indicator codes are the document's own,
so **no NV `standard_id` is affected** — which this run confirms directly, since
the NV parser scored 24/24 fully correct with zero collisions.

### 6. NV's description miss is the DOCUMENTED direct-path reading of a batched-path fix. It is not a regression.

`NV-DOM-02` (Science) reports `truncated: 2410/3500 chars`, giving description
accuracy **2/3**.

This is precisely what CLAUDE.md predicts. `_splice_overlapping_prose` is inert on
the direct path — one chunk holds a single truncated view, so there is no second
view to splice against — while the batched path reconstructs the passage. Verified
this run: `outputs/08-22-26-4/NV-detection.json` carries the Science
`domain.description` at **3500 chars, byte-exact against the golden**, whereas the
direct-path detection the detector eval just produced carries 2410.

**Do NOT delete `_splice_overlapping_prose` because this eval shows no movement**,
and do not read 2/3 as a quality regression. Judge that helper on the batched
path only.

⚠️ **NV description accuracy has a denominator of 3.** Only 3 of NV's 46 golden
elements annotate a description. Report **2/3**, never the rate 0.667.

### 7. The intermittent malformed-primary-key defect did NOT fire this run, and that is not evidence it is fixed.

Both held-out parsers scored zero `standard_id` collisions and all 7 parser
regression cases PASS, including `KY-BENCHMARK-CODE-NORMALIZED` and
`KY-SUB-STRAND-NOT-INDICATOR-CODE` — the two that failed on the 08-01/08-16 runs
with bare codes (`TCPHS`, `UMNDW`).

Per CLAUDE.md this defect is **sampling variance, not a code regression**: it
appears at 8 distinct code versions, and runs over an identical frozen input at
temperature 0 disagree with each other. One clean run cannot retire it. The
durable mitigation is `validator._validate_code_shape`, which rejects such a
record before Aurora; that guard is unchanged by this run and is not exercised by
either eval suite.

### 8. Both batching layers are unexercised at this corpus tier, so no scale claim may rest on these states.

NV produces 5 chunks and KY 3 against `MAX_CHUNKS_PER_BATCH=5`, and both have 3
domains against `MAX_DOMAINS_PER_BATCH=3`. Detection and parsing each run as
exactly one batch. Answering the "8-page subset" criticism is Task 6's job, not
this folder's.

---

## Relationship to Task 3

Task 3's ON-arm is this run and Task 1's — the depth map PASSed in both held-out
states. Task 3's **OFF-arm did not complete**: it aborted on a Bedrock
`ThrottlingException: "Too many tokens per day"` after finishing only AZ. See
`paper/results/task3_20260822/DO_NOT_USE.md`. The ablation instrument itself is
verified working; only the compute budget failed. **No ablation number is
recorded, and none may be quoted.**

## Corrections to `tasking/arxiv_paper.md`

- Guardrail 8's NV block gives the ceiling as 41/53 = 0.7736 and the audit as 12
  verdicts. With the 46-element golden both are stale: ceiling **46/53 = 0.8679**,
  audit **7 verdicts**. The block's *conclusion* — that NV does not qualify for
  the raw-precision carve-out — is unchanged and is reconfirmed above.
- `ground_truth_parser/NV.json` `source_detection` updated `08-22-26` →
  `08-22-26-4` (provenance only; verified the sole drift is the favourable
  Science description 2410 → 3500, which the golden already expects at 3500).

## Open questions for Emily

1. ~~**Sign the NV FP audit.**~~ **DONE 2026-08-23 — signed, 0 verdicts changed.**
   NV verified precision 0.9811 is quotable.
2. **Task 1b still owes 156 verdicts for the golden four** (now the ONLY thing
   blocking a corpus-wide verified-precision claim) (AZ 7 + CA 97 + CO 35 +
   TX 17, counted from each state's `review_detector/{ST}/{ST}-review.json` →
   `extra_in_detected` for this run; the handoff's "~165" was an estimate). No
   verified-precision figure exists for AZ/CA/CO/TX, so the paper currently has a
   verified precision for held-out states only.
3. **Re-run Task 3's off-arm** once the Bedrock daily token quota resets.
4. **`paper/main.tex` still carries the placeholder email `emily@edtechco.org`** —
   permanently public once submitted.
