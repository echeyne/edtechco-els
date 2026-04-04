# Early Childhood Education Has a Data Problem

_How fragmented early learning standards are quietly undermining the P-3 pipeline — and what software engineering can do about it_

---

Every state in America has a vision for what three- to four-year-olds should know and be able to do before they enter kindergarten. Arizona calls them "Standards." Texas calls them "Guidelines." California calls them "Learning Foundations." They each live in a PDF, formatted differently, organized differently, coded differently — and almost never speak to each other.

According to the National Center on Early Childhood Quality Assurance, all 50 states have now developed early learning guidelines for preschool children, and virtually all have guidelines for infants and toddlers ([Office of Child Care, NCECQA](https://childcareta.acf.hhs.gov/sites/default/files/state_elgs_web_final_2.pdf)). The Education Commission of the States' 50-State Comparison confirms that governing these systems is complex, "with multiple agencies overseeing several programs" that "are often siloed, making alignment and coordination difficult" ([ECS, 2024](https://www.ecs.org/50-state-comparison-early-care-and-education-governance-2024/)).

This isn't just an administrative inconvenience. It's a structural barrier in early childhood education that affects every family, every educator, and every policy conversation about the critical birth-to-five window.

---

## The Tower of Babel Problem in Early Childhood

Consider what happens when a family moves from Texas to New Jersey with a four-year-old. The Texas program they left behind organized development into domains like _Mathematics_ and _Emergent Literacy: Language and Communication_, with benchmarks tied to specific age bands. The New Jersey program they're entering uses a completely different structural vocabulary — different domain names, different numbering systems, different terminology for the same developmental concepts.

For a parent, this transition is disorienting. For a curriculum specialist trying to ensure continuity of care, it's a documentation nightmare. For a state education agency trying to assess programmatic quality across districts, it's nearly impossible.

Now scale that problem to fifty states, several Canadian provinces, and international frameworks like Australia's Early Years Learning Framework. They all describe overlapping developmental territory. They all agree, broadly, that young children develop language, social-emotional skills, early numeracy, and physical capabilities on a roughly similar timeline. But the _structure_ of how they express those ideas is entirely inconsistent.

There is no common schema. There is no queryable database. There is a collection of PDFs.

---

## What P-3 Alignment Actually Requires

The research on P-3 alignment — coherent educational experiences from preschool through third grade — is clear: continuity matters enormously for children's long-term outcomes. The Foundation for Child Development's PreK-3rd initiative (2003–2013), which produced a series of policy briefs from 2004 to 2009, established that while well-designed preschool improves children's social and cognitive skills, these gains fade as children advance beyond kindergarten — unless the elementary environment builds on the same foundations with aligned standards and curriculum ([FCD PreK-3rd Policy Briefs](https://www.fcd-us.org/prek-3rd-policy-briefs/)). Stipek's research for SRCD reinforced this, finding that continuity in instruction is less likely when "state and district standards and assessments for preschool are not well aligned" with those for early elementary grades ([Stipek, 2017, SRCD](https://www.srcd.org/research/what-does-pk-3-instructional-alignment-mean-policy-and-practice)).

But meaningful P-3 alignment requires, at a minimum, that educators and administrators can _see_ the connections between what a preschool standard expects and what a kindergarten standard expects. They need to answer questions like:

- Which preschool indicators in our state map to the kindergarten readiness benchmarks in the same domain?
- How does a four-year-old's "emergent literacy" standard connect to a first-grade reading objective?
- If we're developing curriculum for mixed-age groups spanning ages three to five, what's the full range of relevant indicators across those age bands?

Today, answering those questions requires a human being to manually read through multiple documents, page by page, and make the connections by hand. It doesn't scale. It doesn't get done consistently. And it certainly can't be done at the state level, across thousands of programs.

---

## The Engineering Case for Standardization

When I started thinking about this as an engineering problem, the shape of it became clear quickly.

The underlying data isn't actually that varied. Every early learning standards document, regardless of jurisdiction, expresses some form of a hierarchical taxonomy:

- A broad developmental **domain** (Social-Emotional Development, Language and Literacy, Cognitive Development)
- One or more **strands** grouping related skills within a domain
- **Sub-strands** that narrow the focus further
- **Indicators** — the leaf-level learning statements that describe specific, observable behaviors

The hierarchy exists in every document. The _labels_ are just inconsistent. One document's "Sub-Strand" is another document's "Goal." One document's "Indicator" is another document's "Foundation" or "Benchmark" or "Objective."

This is actually a solvable problem — if you have a way to parse those documents intelligently and map them to a normalized schema.

That's what I built.

---

## Introducing the ELS Pipeline

The Early Learning Standards (ELS) Pipeline is an AI-powered system that ingests early learning standards documents from any jurisdiction and outputs a normalized, queryable representation of their content — mapped to a consistent four-level hierarchy. The full source code is available on [GitHub](https://github.com/echeyne/kinder-readiness).

The pipeline runs entirely on AWS serverless infrastructure. A document enters the system as a PDF. Within about 20 minutes, every learning indicator in that document has been extracted, classified, structured, and stored in a relational database. The full hierarchy — from domain down to individual indicator — is preserved, along with the original source text from the document.

Here's what that journey looks like at a high level:

```
Raw PDF
  → Text extraction (AWS Textract)
  → Structure detection (Claude via AWS Bedrock)
  → Hierarchy parsing (Claude via AWS Bedrock)
  → Validation
  → Persistence (Aurora PostgreSQL)
```

The result is a structured database where you can query: _"Show me all indicators for four-year-olds in the Social-Emotional domain for Virginia"_ — and get back a clean, structured result, regardless of how Virginia originally formatted its document.

---

## Why AI Is the Right Tool Here

Early learning standards documents are notoriously hard to parse programmatically. They aren't consistently structured HTML pages. They're PDFs, often typeset in InDesign or Word, with formatting conventions that vary not just between states but between versions of the same state's document.

More importantly, the _semantic_ structure of these documents is often implicit rather than explicit. A bullet point indented three levels might be an indicator. Or it might be an illustrative example that shouldn't be treated as a separate indicator at all. The difference matters — a lot. If you extract the examples as separate indicators, you inflate the indicator count by three to five times and introduce noise into every downstream analysis.

The ELS Pipeline's [detection stage](https://github.com/echeyne/kinder-readiness/blob/main/src/els_pipeline/detector.py) uses a carefully constructed prompt — the result of many iterations of testing across documents from multiple states — to teach the model to distinguish structural elements from illustrative content:

> _"Many early learning standards documents list 'Indicators and Examples' or 'Examples in the Context of Daily Routines, Activities, and Play' beneath a learning goal statement. These lettered or bulleted items are NOT separate indicators. They are illustrative examples or observable behaviors that help teachers recognize the indicator in practice. The actual INDICATOR is the overarching learning goal statement that appears ABOVE these examples."_

This distinction, obvious to a curriculum specialist, has to be explicitly encoded for an AI system — and getting it right is what separates a useful normalization from a noisy one.

The same careful reasoning applies to age-banded indicators. Some states present outcomes for different age groups in side-by-side columns within a table. Those aren't the same indicator. Each column is a distinct developmental expectation. The pipeline extracts them as separate records with separate codes, preserving the age differentiation that makes the data actually useful for practitioners.

---

## What This Enables

Once standards are normalized and queryable, a set of previously impossible or very expensive workflows become tractable:

**Cross-jurisdictional mapping.** A researcher can ask: _"Which indicators in Florida's PK4 standards cover the same developmental territory as indicators in Ontario's Full-Day Kindergarten program?"_ With all standards in a normalized schema, this becomes a structured query rather than a manual annotation project spanning multiple PDFs.

**P-3 continuity analysis.** A state education agency can load both its preschool standards and its kindergarten standards into the same database and surface the gaps — places where preschool foundations don't connect to a kindergarten expectation, or vice versa.

**Personalized learning planning.** Parents and educators can describe a child's age, state, interests, and areas of focus and receive an activity plan grounded in real, state-specific standards — not generic developmental advice. (I cover this in depth in the [third article in this series](link-to-article-3).)

**Quality assurance at scale.** Programs participating in Quality Rating and Improvement Systems (QRIS) could have their curriculum frameworks automatically mapped against state standards, surfacing alignment gaps without manual review. QRIS have been "almost universally adopted by states and localities as an important tool to boost ECE program quality," yet RAND Corporation research has found significant measurement challenges in existing implementations, particularly around linking ratings to actual child outcomes ([RAND, Quality Rating and Improvement Systems](https://www.rand.org/pubs/perspectives/PE235.html)). Normalized, queryable standards data could strengthen the foundation on which these rating systems operate.

---

## A Note on the Human-in-the-Loop

Automation at this scale requires human verification — a principle well-established in the AI research literature. Mosqueira-Rey et al.'s comprehensive survey of human-in-the-loop machine learning identifies multiple paradigms for integrating human judgment into automated systems, including active learning and machine teaching, where the key variable is "who is in control of the learning process" ([Mosqueira-Rey et al., 2023, _Artificial Intelligence Review_](https://link.springer.com/article/10.1007/s10462-022-10246-w)).

The [ELS Explorer](https://github.com/echeyne/kinder-readiness/tree/main/packages/els-explorer-frontend) — the companion web application to the pipeline — provides that review interface. Specialists can view the extracted hierarchy side-by-side with the original PDF, verify individual indicators, and edit any fields the model got wrong. Every verification and edit is tracked with a timestamp and user ID, creating a permanent audit trail of human oversight.

This isn't AI replacing curriculum expertise. It's AI doing the tedious first pass at scale, so that expertise can be applied where it matters most.

---

## Why I Built This as a Public Good

I started EdTech Co. out of a conviction that early childhood education sits at one of the highest-leverage points in the entire educational system — and that the infrastructure supporting it is chronically underbuilt. Nobel laureate James Heckman's research has shown that high-quality early childhood programs can deliver a 13% annual return on investment per child through better outcomes in education, health, employment, and social behavior ([Garcia, Heckman, Leaf, & Prados, 2020, University of Chicago](https://heckmanequation.org/resource/13-roi-toolbox/)). His earlier work with Masterov established "the productivity argument for investing in young children," demonstrating that returns to human capital investment are highest when made earliest in life ([Heckman & Masterov, 2007, _Review of Agricultural Economics_](https://www.nber.org/papers/w13016)). The High/Scope Perry Preschool Study — a randomized controlled trial tracking participants to age 40 — found lasting gains in educational attainment, employment, and earnings, with reduced criminal activity, yielding an estimated 7–10% internal rate of return ([Schweinhart et al., 2005](https://highscope.org/wp-content/uploads/2024/07/perry-preschool-summary-40.pdf)). Yet the kids who would benefit most from high-quality, well-aligned early learning experiences are often the ones least served by the fragmented, inaccessible state of the current standards landscape.

Making these standards queryable, cross-referenceable, and openly accessible is, in my view, a piece of critical public infrastructure. The data exists. The documents are public. What's been missing is the engineering work to make them machine-readable and interoperable.

That work is what I'm doing.

---

In the [next article](link-to-article-2), I'll go deep on the technical implementation of the structure detection stage — specifically, how we handle the hardest cases: documents where the hierarchy isn't visually obvious, where age bands are embedded in column headers, and where illustrative examples are nearly indistinguishable from indicators.

---

_EdTech Co. is a mission-driven engineering initiative focused on building open infrastructure for early childhood education. The full source code is available on [GitHub](https://github.com/echeyne/kinder-readiness). Follow along on Medium for technical deep-dives and policy perspectives._

---

_I work for Bezos Academy, a national provider of early-childhood education, but this research is my own and is in no way supported by Bezos Academy nor reflects the vision or mission of the organization._
