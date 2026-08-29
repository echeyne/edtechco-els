# Task 3 re-record — depth-map ablation (2026-08-26)

Re-records the depth-map on/off ablation at `code_version_hash` **`14374dba`**,
against the `task3_20260822` baseline (**`288c64f1`**).

**Why it had to be re-recorded, and why it was the one task that did.** Task 3
measures what Pass-1 buys. `99b853cc` replaced the Pass-1 **sampler** — stride →
layout-stratified — so the baseline's "depth map ON" arm exercised the old
sampler, the one that read Kentucky as a 3-level document. Every other
superseded recording is merely stale; this one measured a component that
changed underneath it.

**Headline: the gap widened. Mean recall off 0.9610 → 0.9573 against an ON arm
that is 1.0000 in both, so the measured cost of removing the depth map grew
from 0.0390 to 0.0427.** The earlier prediction that a re-record would be
*conservative* rather than favourable is confirmed.

## Per state

| | recall on → off | code on → off | desc on → off | detected on → off |
|---|---|---|---|---|
| AZ | 1.0000 → 1.0000 | 4/4 → 4/4 | 4/4 → 4/4 | 67 → 77 |
| CA | 1.0000 → 1.0000 | 25/25 → 25/25 | 14/14 → 14/14 | 122 → 122 |
| **CO** | **1.0000 → 0.8571** | 7/7 → 6/6 | 4/4 → 3/3 | 61 → 61 |
| **TX** | 1.0000 → 1.0000 | **8/8 → 5/8** | 3/3 → 3/3 | 33 → 33 |
| **NV** | 1.0000 → 1.0000 | **46/46 → 44/46** | **3/3 → 2/3** | 52 → 53 |
| **KY** | **1.0000 → 0.8864** | **44/44 → 35/39** | 26/26 → 26/26 | 44 → 46 |

## The ablation has TWO distinct failure modes, not one

This is the most useful thing in the re-record, and an aggregate recall number
hides it:

- **CO and KY lose RECALL.** Elements the golden annotates stop being found at
  the right level. KY is the severe case: recall 0.8864 and code 35/39, with
  both of its structural regression cases newly failing.
- **TX and NV keep recall 1.0000 and lose CODE accuracy instead.** TX drops
  8/8 → 5/8 while detecting the identical 33 elements. The depth map is not
  changing *what* TX finds; it is changing whether the codes come out right.

AZ and CA are insensitive on every metric, and that is an artefact of their
goldens rather than a result: both are small spot checks (5 and 25 elements)
against 67 and 122 in-scope detections, so recall saturates either way. **Do
not read AZ/CA as evidence the depth map does not matter** — they are the
states least able to show it. AZ's detections rise 67 → 77 with the map off,
which is the listing-page duplicates returning.

## Pooled by level — the effect is concentrated in the middle

| level | recall on → off | precision on → off |
|---|---|---|
| domain | 1.0000 → 1.0000 | 1.0000 → 1.0000 |
| **strand** | **1.0000 → 0.9200** | 0.6410 → 0.5227 |
| **sub_strand** | **1.0000 → 0.8333** | 0.5854 → 0.5556 |
| indicator | 1.0000 → 1.0000 | 0.3578 → 0.3578 |

Domain and indicator are untouched; the entire effect sits at strand and
sub_strand. That is exactly the mechanism CLAUDE.md documents — Pass-1 decides
how many nesting depths a document uses, and the levels that go missing are the
intermediate ones. `sub_strand` recall 0.8333 is the single sharpest number in
the ablation.

## Regression cases newly failing with the map off

`KY-BENCHMARK-IS-SUB-STRAND` and `KY-STRAND-CODE-KEEPS-FULL-LABEL`, both
structural. The baseline additionally lost `CO-NO-SUB-STRAND`; it now survives,
which is a real (small) improvement in the ON arm attributable to the new
sampler — CO is one of the two states that samples.

## ⚠️ A finding that lands outside this task: NV's off-arm reproduces the old defect

With the depth map OFF at `14374dba`, NV comes back at **code 44/46, desc 2/3,
53 detections — and the failing pair is `NV-DOM-02` (`S` → `SCIE`) and
`NV-DOM-03` (`T` → `TECH`)**, the same two domains the `288c64f1` recording
missed with the map ON.

So NV's domain-code failure is **depth-map-mediated**. This does not by itself
attribute the fix to the sampler — the baseline had the map ON and still failed
— but it rules out the rule-4 prompt clarification (`b35b9666`), which governs
whether `code` may be null and has nothing to do with domain-code derivation.
See `nv_attribution_ab.json` for the controlled test.

## Method — unchanged from the baseline

The **ON arm is not re-run**: it is the frozen Task 1 + Task 2 detector
reports, which record `depth_map PASS` in every state. Only the OFF arm is
swept, one invocation per state so a mid-sweep throttle costs one state rather
than five. `ELS_DEPTH_MAP_ENABLED=false` was exported in a subshell and
asserted through `Config.DEPTH_MAP_ENABLED` before the first Bedrock call, per
the baseline manifest's warning that a `VAR=val cmd` prefix is shell-dependent
about reaching the child.

All six states returned non-zero detections, so none was excluded as `INVALID`
— the 2026-08-23 throttle signature did not recur.
