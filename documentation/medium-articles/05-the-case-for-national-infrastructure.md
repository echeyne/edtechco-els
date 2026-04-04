# The Case for a National Early Learning Data Layer

_What would it mean if every early learning standard in America were machine-readable, queryable, and interoperable — and why it's closer than you think_

---

This is the last article in a five-part series about building the ELS Platform — a system that uses AI to extract, normalize, and operationalize early learning standards from state education documents across the United States and internationally. The previous articles covered the engineering: the AI pipeline, the prompt design, the planning agent, the human verification layer.

This article steps back from the code and asks the question the code was written to answer: what would change if every state's early learning standards existed in a single, normalized, machine-readable format?

---

## The Infrastructure That Doesn't Exist

The United States Department of Education maintains the Common Core State Standards for K-12 mathematics and English language arts. They're published in a structured format. They have stable identifiers. Curricula, assessments, and digital learning tools can reference them unambiguously.

For early childhood — birth through kindergarten entry — no equivalent exists. The federal government established the Head Start Early Learning Outcomes Framework (ELOF) in 2015, presenting five broad areas of early learning across infants, toddlers, and preschoolers — but it covers only Head Start programs ([Office of Head Start, 2015, *Head Start Early Learning Outcomes Framework: Ages Birth to Five*](https://headstart.gov/school-readiness/article/head-start-early-learning-outcomes-framework)). Meanwhile, all 56 states and territories have developed their own early learning guidelines, each published independently as standalone PDF documents and updated on their own schedules ([Office of Child Care, NCECQA](https://childcareta.acf.hhs.gov/sites/default/files/state_elgs_web_final_2.pdf)).

The result is a fragmented landscape that creates real costs:

**For state education agencies** — evaluating programmatic quality across districts requires mapping each program's curriculum to the state's standards. This is done manually, one document at a time, by specialists who could be doing higher-value analytical work.

**For curriculum developers** — building a curriculum product that serves families in multiple states means manually cross-referencing each state's standards document to ensure coverage. A product that works in Virginia may have alignment gaps in Texas, and finding those gaps requires hours of document review.

**For researchers** — studying developmental expectations across jurisdictions means reading and coding standards documents by hand. A study comparing social-emotional expectations for four-year-olds across ten states starts with weeks of data entry before any analysis can begin.

**For families** — a parent who moves from one state to another has no way to understand how the expectations shift. Was their child "on track" under the old state's framework? What does the new state expect that the old one didn't? These questions are effectively unanswerable without specialist knowledge.

None of these problems are caused by a lack of data. The standards exist. They're publicly available. The problem is that they exist as human-readable documents, not as structured data.

---

## What Normalization Makes Possible

The ELS Platform processes state standards documents through an AI-powered pipeline that outputs a normalized, four-level hierarchy: domain → strand → sub-strand → indicator. Every indicator carries a deterministic identifier, its source text, its age band, and its position in the hierarchy.

When multiple states' standards are loaded into the same database, new capabilities emerge that simply don't exist today:

### Cross-State Alignment Mapping

A query like _"show me all four-year-old social-emotional indicators across Virginia, Texas, and New Jersey"_ returns a structured comparison. Each state's indicators are organized under their respective hierarchies but share the same schema. A curriculum developer can see, at a glance, where the states converge and where they diverge.

This isn't just an academic exercise. Quality Rating and Improvement Systems (QRIS) in many states require programs to demonstrate alignment between their curriculum and the state's early learning standards. QRIS have been "almost universally adopted by states and localities as an important tool to boost ECE program quality" ([RAND, 2016](https://www.rand.org/pubs/perspectives/PE235.html)), and the BUILD Initiative convened teams from 21 states between 2017–2019 to self-assess and improve their QRIS systems ([BUILD Initiative, QRIS 3.0](https://buildinitiative.org/qris-resources/)). A multi-state childcare provider operating in three states currently maintains three separate alignment documents, updated manually whenever a state revises its standards. With normalized data, that alignment check becomes a query.

### Continuity Analysis Across Age Bands

Within a single state, standards typically span multiple age bands: infant/toddler, preschool (3–4 years), and pre-kindergarten (4–5 years). Some states also have kindergarten and early elementary standards. But the connections between age bands — how a preschool indicator progresses into a kindergarten expectation — are rarely made explicit in the documents themselves.

A normalized database with age-band metadata enables vertical analysis: trace a skill (self-regulation, letter recognition, counting) from its earliest appearance in the infant/toddler standards through its most advanced form in the kindergarten expectations. This is exactly the P-3 continuity analysis that the Foundation for Child Development championed across a decade of research (2003–2013), which found that preschool gains fade "as children advance beyond Kindergarten" unless schools provide "aligned standards and curriculum in a coherent PK-3 education program" ([FCD PreK-3rd Policy Briefs](https://www.fcd-us.org/prek-3rd-policy-briefs/)). Stipek's research for SRCD identified a key barrier: continuity in instruction is less likely when "state and district standards and assessments for preschool are not well aligned" with those for early elementary grades ([Stipek, 2017, SRCD](https://www.srcd.org/research/what-does-pk-3-instructional-alignment-mean-policy-and-practice)). A normalized data layer directly addresses that barrier.

### Automated Plan Generation Grounded in Real Standards

The planning assistant I described in the third article in this series depends entirely on normalized data. When a parent selects their state and their child's age range, the assistant queries the database for matching indicators and generates an activity plan grounded exclusively in those real, verified indicators.

Without normalized data, this assistant doesn't exist. It would be forced to rely on general developmental knowledge embedded in the language model's training data — knowledge that is approximate, unattributed, and unverifiable. The value of the assistant is precisely that it cites real standards, and that requires real data.

---

## What It Takes to Build This

Processing a single state's standards document through the pipeline takes minutes. But building a comprehensive national dataset requires more than running the pipeline fifty times. It requires:

**Document acquisition.** Standards documents need to be located, downloaded, and verified as current versions. Some states publish their standards prominently on their education department websites. Others require navigating through multiple subdepartments and archived pages. A few have standards that exist only as physical publications or as appendices to larger policy documents.

**Version tracking.** States revise their standards on varying schedules — some every five years, some every ten, some ad hoc. The NIEER State of Preschool Yearbook, which has tracked state-funded preschool policies annually since the 2001–2002 school year, documents this evolving landscape and notes that "with the development of the Common Core State Standards, there appears to be a trend among States to revise their ELGs and work to align them across age groups" ([NIEER, 2024, *State of Preschool Yearbook*](https://nieer.org/state-preschool-yearbook)). The pipeline produces version-specific records (each indicator carries a `version_year`), but keeping the dataset current requires monitoring fifty states for updates.

**Human verification at scale.** The AI pipeline produces high-confidence extractions, but every state's document introduces edge cases specific to its formatting and terminology. The human verification layer — specialists reviewing the extracted hierarchy against the source document — needs to scale alongside the document count. This means recruiting curriculum specialists with expertise in early childhood education, not just general-purpose data annotators.

**Community trust.** The most technically accurate dataset in the world is useless if the practitioners and agencies who would use it don't trust it. Trust comes from transparency: showing the source text alongside the extracted data, making the verification status visible, publishing the methodology openly, and inviting expert review.

---

## The Role of AI — And Its Limits

The AI pipeline is what makes this project feasible as a small-team effort. Without it, normalizing fifty states' standards documents would be a multi-year, large-team manual annotation project — the kind of work that gets proposed in grant applications and never reaches completion because the labor cost exceeds the funding.

AI reduces the per-document cost from days of specialist time to minutes of compute time plus hours of specialist review. That's the enabling economics.

But the AI is a tool, not a solution. The value of the system is in the *verified* data — the records that a curriculum specialist has reviewed, confirmed or corrected, and marked as human-verified. The AI provides the first draft. The human provides the quality seal. The system tracks which is which, permanently.

This is a general pattern I think matters for applied AI in education: the model accelerates the work, but the human's judgment is what makes the output trustworthy. Ji et al.'s survey of hallucination in natural language generation documents how deep learning-based text generation is systematically "prone to hallucinating unintended text" — generating content that is fluent but factually unfounded ([Ji et al., 2023, *ACM Computing Surveys*](https://dl.acm.org/doi/10.1145/3571730)). Systems that obscure that boundary — that present AI output as authoritative without a verification mechanism — will eventually lose the trust of the practitioners they're meant to serve.

---

## An Invitation

I built the ELS Platform as a public good because I believe early childhood education infrastructure should be open, interoperable, and accessible. The standards themselves are public documents. The data they contain should be, too.

The system works. The pipeline processes documents accurately. The Explorer lets specialists verify and curate the output. The planning assistant turns the data into something families can use. The architecture is serverless, the costs are manageable, and the codebase is production-grade.

What the project needs now is collaborators:

**Curriculum specialists** who can verify extracted standards for their state. The verification interface is designed to make this fast — a few hours per document for someone who already knows the standards well.

**State education agencies and technical assistance organizations** who could benefit from normalized, queryable standards data. If your work involves cross-state analysis, P-3 alignment, or standards-based curriculum evaluation, this data infrastructure was built for you.

**Researchers** studying early childhood developmental standards, curriculum alignment, or the application of AI to educational data systems. The pipeline, the dataset, and the methodology are all available for research use.

**Engineers** interested in applied AI for public benefit. The codebase spans Python (AI pipeline), TypeScript (APIs and frontends), and AWS infrastructure (Step Functions, Lambda, Aurora, Bedrock). Contributions across the stack are welcome.

Early childhood education is the highest-leverage intervention point in the entire educational system. The research is clear on this — from Heckman's finding of 13% annual returns on early childhood investment ([Heckman & Karapakula, 2019](https://heckmanequation.org/resource/13-roi-toolbox/)), to the Perry Preschool Study's 40-year evidence of lasting gains in education, employment, and reduced crime ([Schweinhart et al., 2005](https://highscope.org/wp-content/uploads/2024/07/perry-preschool-summary-40.pdf)), to the NIEER Yearbook's documentation that only five states currently meet all ten quality benchmarks for preschool programs ([NIEER, 2024](https://nieer.org/state-preschool-yearbook)). What's been missing is the data infrastructure to support that insight at scale. That's what EdTech Co. is building.

---

## The Series

If you've followed this series from the beginning, thank you. Here's the full arc:

1. **Why Early Childhood Education Has a Data Problem Nobody Talks About** — The problem: fragmented standards, no common schema, no queryable data.
2. **Teaching an AI to Read Like a Curriculum Specialist** — The pipeline: prompt engineering, chunking, parallel processing, and the hardest classification problems.
3. **From Standards to Story Time** — The planning agent: grounded in real data, guided by a structured workflow, secured by authorization closures.
4. **Why I Built a Human Verification Layer on Top of My AI Pipeline** — The quality system: audit trails, soft cascade deletes, property-based testing, and why human oversight makes AI useful.
5. **The Case for a National Early Learning Data Layer** — The vision: what changes when every state's standards are machine-readable and interoperable.

The engineering serves the mission. The mission is making sure every child, in every state, has access to learning experiences grounded in the best knowledge we have about how young children develop. That work starts with data.

---

_EdTech Co. is a mission-driven engineering initiative focused on building open infrastructure for early childhood education. To learn more or get involved, follow EdTech Co. on Medium._
