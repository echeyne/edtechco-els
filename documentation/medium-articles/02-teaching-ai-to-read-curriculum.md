# Teaching an AI to Read Like a Curriculum Specialist

_Inside the prompt engineering and architecture behind an automated early learning standards parser_

---

If you hand a curriculum specialist a state's early learning standards document and ask them to extract every learning indicator into a structured spreadsheet, they'll do it accurately. It might take them several days for a large document, but they'll understand, without being told, that the bulleted examples under a learning goal aren't separate indicators. They'll recognize that "PK3" and "PK4" in the column headers mean different age groups with different expectations. They'll map the document's idiosyncratic terminology — "Foundation," "Benchmark," "Objective" — to the right levels in a normalized taxonomy.

They do all of this because they have deep domain knowledge. They've read hundreds of these documents. They understand the conventions of the field.

Teaching an AI system to replicate that judgment — reliably, across documents from fifty states with different formats and conventions — is the core engineering challenge of the ELS Pipeline.

The approach I chose — detailed prompt engineering over model fine-tuning — is grounded in a fundamental insight from Brown et al.'s landmark GPT-3 paper: sufficiently capable language models can perform competitively with fine-tuned models on many tasks through carefully constructed prompts alone, without any gradient updates ([Brown et al., 2020, "Language Models are Few-Shot Learners," _NeurIPS_](https://proceedings.neurips.cc/paper/2020/file/1457c0d6bfcb4967418bfb8ac142f64a-Paper.pdf)). Wei et al. extended this finding with chain-of-thought prompting, demonstrating that including intermediate reasoning steps in prompts significantly improves performance on complex tasks ([Wei et al., 2022, "Chain-of-Thought Prompting Elicits Reasoning in Large Language Models," _NeurIPS_](https://arxiv.org/abs/2201.11903)). For a domain with limited labeled training data — there is no large annotated corpus of parsed early learning standards — prompt engineering is the pragmatic choice.

This article explains how I approached it.

---

## Why This Is Harder Than It Looks

The naive approach to parsing a standards document is to write a rule-based extractor: find the bold headings, find the numbered lists, extract the text. This works for documents with consistent, well-structured HTML or clean XML. It fails completely for PDFs of education policy documents.

Here's what you're actually dealing with:

**Formatting is not reliable structure.** After AWS Textract processes a PDF, you have a list of text blocks with page numbers, bounding box coordinates, and confidence scores. The visual hierarchy — indentation, font size, bold formatting — mostly doesn't survive. You have raw text in reading order, and that's it.

**Terminology is jurisdiction-specific.** Texas calls the top level "Domains" and the next level "Skills." California calls the top level "Foundations" and uses a different organizational logic entirely. New Jersey has "Preschool Teaching and Learning Standards" organized by "Standards" containing "Indicators." None of these terms mean the same thing relative to the others.

**Illustrative examples are nearly identical to indicators.** The most common trap in parsing these documents is extracting the observable behaviors or examples that follow a learning goal statement as if they were separate indicators. They often look like indicators. They're formatted the same way. The only difference is their semantic role in the document — they're meant to help teachers _recognize_ the indicator, not to be separate learning objectives. A rule-based system can't distinguish them. Even a poorly prompted language model will get it wrong.

**Age-banded indicators appear in table columns.** Some states — Texas is a notable example — present outcomes for PK3 and PK4 children in side-by-side columns within a table. After Textract processes a two-column table, the text may come out as interleaved rows rather than clearly labeled columns. The parser needs to correctly identify that these are _two distinct indicators_ for two distinct age groups, not variants of the same indicator.

---

## The Architecture: Chunk, Detect, Parse

The pipeline approaches this as a two-stage AI problem.

**Stage 1: Structure Detection.** A language model reads chunks of text extracted from the document and identifies every structural element — every domain, strand, sub-strand, and indicator — along with its level in the hierarchy, its code, its title, its description, and a confidence score.

**Stage 2: Hierarchy Parsing.** A second language model takes the detected elements and resolves the parent-child relationships — building the actual tree structure. This is necessary because chunks may split a parent from its children, and the parser needs to reconstruct the complete hierarchy from partial views.

Between stages, a batching and merging system handles the scale problem. Large documents get split into overlapping chunks, processed in parallel via AWS Step Functions, and their results merged with deduplication logic.

---

## Chunking with Overlap

Before the language model sees any text, the extracted text blocks are chunked into manageable sizes. The target is 2,000 tokens per chunk, estimated using a simple 4-characters-per-token heuristic. Each chunk overlaps with the previous by 500 tokens.

The overlap matters — without overlap, a domain heading at the end of one chunk has no corresponding indicators in that chunk — because they're at the start of the next. The language model sees a structural element with no children and has to decide whether to extract it or ignore it. With a 500-token overlap, there's enough context in each chunk that the model can see both the parent element and at least some of its children, which dramatically improves classification accuracy.

The prompt addresses this explicitly:

> _"Documents are chunked for processing, so you may see structural elements whose children appear in a different chunk. This is normal and expected. You MUST still extract these elements. If you see a strand or sub-strand header with a description paragraph but NO indicators beneath it in this text, extract it anyway. Its indicators will appear in a later chunk."_

This instruction prevents the model from silently dropping elements that appear incomplete in a given chunk — a failure mode that would create gaps in the final hierarchy.

---

## The Detection Prompt: Encoding Domain Expertise

The detection stage prompt is the result of extensive iteration across documents from multiple states. It encodes, as explicit instructions, the same tacit knowledge that a curriculum specialist brings to the task.

**The core principle: classify by nesting depth, not by document labels.**

This is the most important rule in the entire prompt. The model is instructed to first read the entire chunk and identify how many nesting levels exist in the document — not what they're called. Then it maps each level to the normalized four-level hierarchy (domain → strand → sub_strand → indicator) based on position:

> _"Different states use different terminology. A document may call something a 'Sub-Strand' but if it sits at the second nesting level — directly under a domain, with further groupings beneath it — it is a STRAND in our hierarchy. Similarly, a document may call something a 'Topic' but if it is the third nesting level, it is a SUB_STRAND."_

This resolves the terminology problem entirely. The model isn't trying to match a label like "Foundation" to a taxonomy entry. It's observing structural position: what contains what.

**Indicators vs. examples: an explicit rule.**

The examples-vs-indicators problem required the most careful prompt engineering. The final instruction is precise and includes a concrete example:

> _"The actual INDICATOR is the overarching learning goal statement that appears ABOVE these examples, such as 'The child demonstrates an awareness of self.' The description paragraph that follows it is the indicator's description. The lettered or bulleted examples beneath (a, b, c, d, e…) with their sub-bullets — these are NOT separate indicators. Do NOT extract them as indicators. They are supporting examples and should be IGNORED as structural elements."_

Crucially, the prompt also identifies the false positive that trips up naive systems: section headers like _"Indicators and Examples in the Context of Daily Routines, Activities, and Play"_ are themselves NOT indicators. They're headers for the examples section. An early version of the pipeline extracted these as indicators, inflating every document's indicator count by the number of sub-strands.

**Age-banded outcomes: separate records.**

For documents with side-by-side age group columns, the prompt establishes an explicit rule with a worked example:

> _"If you see a table with a 'PK3 Outcome' column and a 'PK4 Outcome' column: 'PK3.I.A.2 Child can identify own physical attributes…' → one indicator with code 'PK3.I.A.2'. 'PK4.I.A.2 Child shows self-awareness of physical attributes…' → a SEPARATE indicator with code 'PK4.I.A.2'. The fact that they appear on the same row or page does not make them one element."_

The prompt also instructs the model to strip age-band prefixes from indicator titles. If the document shows _"Early (3 to 4½ Years)"_ as a column header above the indicator text _"Curiosity and Interest,"_ the indicator title should be _"Curiosity and Interest"_ — not _"Early (3 to 4½ Years) Curiosity and Interest."_ The age-band information belongs in a separate field.

---

## Confidence Scoring and Human Review

Every detected element is assigned a confidence score between 0.0 and 1.0. The prompt gives the model explicit calibration guidelines:

- **0.95+** — Nesting position is unambiguous; the element clearly maps to this level
- **0.85–0.94** — Position is clear but the document's labeling is somewhat ambiguous
- **0.70–0.84** — Some structural ambiguity (e.g., unclear whether a level should be strand or sub_strand)
- **Below 0.70** — Uncertain classification

Elements below the 0.70 threshold are flagged for human review — consistent with the human-in-the-loop ML paradigm described by Monarch, where systems are designed to route low-confidence predictions to human annotators rather than discard them ([Monarch, 2021, _Human-in-the-Loop Machine Learning_, Manning](https://www.manning.com/books/human-in-the-loop-machine-learning)). They aren't discarded — they enter a pending state within S3 for further verification. This creates a quality gate that prevents low-confidence extractions from polluting the searchable knowledge base without throwing away potentially valid data.

In practice, most documents produce 85–90% of their indicators at 0.95+ confidence. The remaining 10–15% are typically from tables, footnotes, or sections with unusual formatting.

---

## Parallel Processing with Step Functions

Large standards documents can run to 100+ pages. Processing them as a single synchronous invocation isn't feasible — Lambda functions have a 15-minute execution limit, and a even a 50-page document generates enough text blocks to require many separate Bedrock calls.

The pipeline handles this with a Step Functions state machine that batches, parallelizes, and merges:

1. **Detection Batching** — Text blocks are grouped into batches of up to 5 chunks each, producing a manifest that describes how many batches exist and where each batch's data lives in S3.

2. **Parallel Detection** — A Step Functions Map state invokes one Lambda per batch, with a maximum concurrency of 3 to stay within Bedrock's rate limits. Each Lambda processes its batch and writes results to S3.

3. **Merge Detection Results** — A merge Lambda reads all batch results from S3, deduplicates elements that appeared in overlapping chunk regions, and produces a single unified list of detected elements.

4. **Parse Batching and Parallel Parsing** — The same pattern repeats for the hierarchy parsing stage, with batches of up to 3 domains each.

The deduplication in the merge step is important. Because chunks overlap, the same structural element may be detected in two adjacent chunks. The merge logic uses code + title as a composite key to identify and collapse duplicates, preferring the detection with the higher confidence score.

---

## The Output: A Normalized Knowledge Base

When the pipeline finishes, every indicator in the source document has been assigned a deterministic ID following the pattern `{country}-{state}-{year}-{domain_code}-{indicator_code}-{age_band}`. This ID is stable across re-runs of the pipeline and can be used as a foreign key in any downstream system.

The indicator record includes:

- Country (ISO 3166-1 alpha-2) and state
- Version year (when the standards document was published)
- Full domain → strand → sub_strand → indicator hierarchy
- Age band (normalized to a month-range)
- Original source text and page number (for auditability)
- Human verification status (whether a human has reviewed and approved this record)

The result is a database that can answer questions like:

- _"What are all the Social-Emotional Development indicators for four-year-olds in Arizona?"_
- _"Show me the full hierarchy for the Language and Literacy domain in California's 2022 document."_

These are the kinds of queries that state education agencies, researchers, and curriculum developers need — and that currently require hours of manual document work to answer.

---

## What I Learned About Prompt Engineering at This Scale

A few things surprised me in building this system:

**Explicit negative examples outperform general rules.** Telling the model "don't confuse examples for indicators" is less effective than showing it exactly what the false positive looks like: _"a section labeled 'Indicators and Examples in the Context of Daily Routines' is NOT an indicator itself."_ Concrete patterns transfer better than abstractions.

**Structure instructions need to come before content instructions.** The model processes the prompt from top to bottom. If the instruction to "classify by nesting depth, not labels" appears after several paragraphs of terminology examples, it doesn't generalize as well. Putting the core principle first, then supporting it with examples, produces more consistent results.

**Temperature matters more than you'd think for structured output.** Running detection at temperature 0.1 (rather than 0.0 or 0.5) produces better results for this task. At 0.0, the model occasionally gets stuck in repetitive patterns when the document structure is ambiguous. At 0.5, it introduces variation that breaks the consistency of the JSON output. 0.1 finds a stable middle ground.

**Overlap in chunking is not free.** Every token of overlap costs money and adds latency. 500 tokens is the minimum that reliably prevents boundary artifacts. Going lower causes structural elements near chunk boundaries to be missed; going higher adds cost without improving accuracy.

---

In the next article, I'll cover the ELS Explorer — the human-in-the-loop interface that lets curriculum specialists review and verify AI-extracted standards, with an audit trail that tracks every edit and verification. The engineering challenge there is different: how do you build a data curation tool that makes human review fast enough to actually happen?

_EdTech Co. is a mission-driven engineering initiative focused on building open infrastructure for early childhood education._

---

_I work for Bezos Academy, a national provider of early-childhood education, but this research is my own and is in no way supported by Bezos Academy nor reflects the vision or mission of the organization._
