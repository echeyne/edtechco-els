# KY — age_band attribution drift

**20 golden elements** were found by the larger run at the right level, on the right page, with the right title, but carrying a different `age_band` than the golden annotates. Because `_match_key` is `(domain, level, title, age_band)`, each of these fails the strict key — and together they are the *entire* difference between this state's strict recall and its 1.000 recall by level and title.

## The thing that makes this a real question

It is **not** a clean per-page decision. Pages emitting more than one value in the graded window:

| trimmed page | values emitted |
|---|---|
| p4 | `three and four year olds` ×5, `null` ×4 |
| p5 | `three and four year olds` ×1, `null` ×4 |
| p15 | `three and four year olds` ×1, `null` ×7 |
| p21 | `three and four year olds` ×7, `null` ×1 |
| p22 | `three and four year olds` ×5, `null` ×8 |

Across the whole window: `three and four year olds` ×31, `null` ×24.

So the run is emitting two spellings of one fact about a page. That is the shape `models._blank_to_none` and `_canonicalize_code` exist to absorb, and per CLAUDE.md's standing argument it is the shape a prompt rule can reduce but not zero.

## ✅ VERDICT: `RUN` — decided 2026-09-06 by Emily Cheyne

**The run is over-attributing; the golden is right and does not change.** Reported as a detector defect at scale (§8), with no code change: `code_version_hash` stays at `14374dba` and no recorded result is invalidated.

Three things support it, none of them in the table below:

1. **The golden already calls the banner page furniture.** KY's `expected_depth_map` describes depth 1 as a domain name in the page header, *above* a `THREE AND FOUR YEAR OLDS` banner — context for the heading, not a property of it.
2. **The band already has a home, one stage later.** `ground_truth_parser/KY.json` sets `default_age_band: 36-60` and `parse_hierarchy` applies it as a document-level default. The detector stamping the banner onto elements is a second, competing mechanism for the same fact.
3. **The goldens draw a consistent line across all six states.** Every state whose detector golden annotates an `age_band` — CA (`Early`/`Later`), TX (`PK3`/`PK4`) — has one because a side-by-side COLUMN distinguishes siblings. KY, CO, NV and AZ annotate `null` throughout. A banner applying to every element on the page carries no distinguishing information.

⚠️ **What this decision does NOT do.** It leaves the downstream consequences in place as documented limitations: 11 detector duplicates surviving `_dedup_elements`, and 7 fabricated `.N` primary keys in the Kentucky parser output. Fixing those needs the `SCHEMA` option — a prompt rule that a page banner is not an element's `age_band` — which moves `code_version_hash` and forces a re-record of Tasks 1--4. Deliberately deferred, not overlooked.

---

| test case | level | golden | run | trimmed page | title |
|---|---|---|---|---|---|
| `KY-DOM-01` | domain | `None` | `three and four year olds` | 2 | Approaches to Learning |
| `KY-STR-01` | strand | `None` | `three and four year olds` | 2 | Sustains attention and persists with challenging activities  |
| `KY-SUB-01` | sub_strand | `None` | `three and four year olds` | 2 | Maintains focus and sustains attention. |
| `KY-IND-01` | indicator | `None` | `three and four year olds` | 2 | Engages in an activity for a sustained period of time. |
| `KY-IND-02` | indicator | `None` | `three and four year olds` | 2 | Maintains focus and attention on activities despite distract |
| `KY-IND-03` | indicator | `None` | `three and four year olds` | 2 | Sustains attention during group activities that last a short |
| `KY-SUB-02` | sub_strand | `None` | `three and four year olds` | 3 | Persists at challenging tasks. |
| `KY-IND-04` | indicator | `None` | `three and four year olds` | 3 | Persists with self-selected activities until completed. |
| `KY-IND-05` | indicator | `None` | `three and four year olds` | 3 | Continues working on self-selected activities despite setbac |
| `KY-IND-06` | indicator | `None` | `three and four year olds` | 3 | Persists with adult-directed tasks with support as needed. |
| `KY-SUB-03` | sub_strand | `None` | `three and four year olds` | 3 | Makes a plan and engages in the planned activity or project  |
| `KY-IND-07` | indicator | `None` | `three and four year olds` | 3 | With prompting and support, develops a simple plan and works |
| `KY-IND-08` | indicator | `None` | `three and four year olds` | 4 | Develops plans that extend over time and follows through to  |
| `KY-DOM-02` | domain | `None` | `three and four year olds` | 15 | Health/Mental Wellness |
| `KY-DOM-03` | domain | `None` | `three and four year olds` | 21 | Language and Early Literacy |
| `KY-STR-04` | strand | `None` | `three and four year olds` | 21 | Demonstrates skills and strategies needed for receptive comm |
| `KY-SUB-08` | sub_strand | `None` | `three and four year olds` | 21 | Attends and responds to nonverbal and verbal communication o |
| `KY-IND-18` | indicator | `None` | `three and four year olds` | 21 | Attends to an adult or peer who is communicating verbally or |
| `KY-IND-19` | indicator | `None` | `three and four year olds` | 21 | Follows simple directions. |
| `KY-IND-20` | indicator | `None` | `three and four year olds` | 21 | Gains information by listening to/processing communications  |