# Why I Built a Human Verification Layer on Top of My AI Pipeline

_AI can extract early learning standards at scale. But production data quality requires human oversight — and the engineering to make that oversight fast enough to actually happen._

---

There's a tempting narrative in AI engineering that goes something like: the model extracts the data, we validate the output, we ship it. Done.

In practice, that story falls apart the moment your output is consumed by people who need to trust it. An extracted learning indicator with a slightly wrong hierarchy assignment — a strand misclassified as a sub-strand, an illustrative example erroneously extracted as a separate indicator — isn't just a data quality issue. It's a trust issue. If a curriculum specialist finds one error in the data, they question all of it.

The ELS Pipeline I built processes early learning standards documents from multiple states through an AI-powered extraction and normalization flow. In my previous articles, I covered the [problem space](link-to-article-1), [how the detection and parsing stages work](link-to-article-2), and [the planning assistant that turns the data into personalized learning plans](link-to-article-3). This article covers what happens after the AI does its job: the human verification layer that turns AI output into production-quality data.

---

## The Quality Model

Every record the AI extracts — every domain, strand, sub-strand, and indicator — enters the database with a `humanVerified` flag set to `false`. Nothing is rejected. Nothing is auto-approved. The data is immediately available for browsing and plan generation, but it's explicitly marked as unverified until a human specialist reviews it.

This is a deliberate quality model — not "AI is correct until proven wrong," but "AI provides a first draft that accelerates human review."

The approach aligns with what Mosqueira-Rey et al. call "machine teaching" — a human-in-the-loop paradigm where domain experts retain control of the learning process and the system is designed around their judgment, not the model's autonomy ([Mosqueira-Rey et al., 2023, "Human-in-the-loop machine learning: a state of the art," _Artificial Intelligence Review_](https://link.springer.com/article/10.1007/s10462-022-10246-w)). Monarch's practical framework for HITL-ML similarly emphasizes that the design of the annotation interface — how fast and intuitive it is for the human reviewer — is often more important to system quality than the model's raw accuracy ([Monarch, 2021, _Human-in-the-Loop Machine Learning_, Manning](https://www.manning.com/books/human-in-the-loop-machine-learning)).

---

## Making Review Fast Enough to Actually Happen

The biggest risk with a human-in-the-loop system isn't that humans will make bad judgments — it's that the review interface will be slow enough that the review never happens. A curriculum specialist who has to toggle between a PDF, a spreadsheet, and a database tool to verify one indicator will burn out before finishing a single document.

The [ELS Explorer](https://github.com/echeyne/kinder-readiness/tree/main/packages/els-explorer-frontend) — the companion web application to the pipeline — is designed around that constraint. A specialist opens a document and sees the extracted hierarchy as an expandable table: domains contain strands, strands contain sub-strands, sub-strands contain indicators. The hierarchy supports flexible nesting — indicators can attach directly to any level, depending on how the source document is structured.

Each row shows the element's code, name, and verification status. The specialist can filter by country, state, verification status, or free text. They can sort by code, name, or verification status. The entire UI state — which nodes are expanded, the scroll position, sort order, active filters — is persisted to the browser session, so navigating to a detail page and pressing back restores exactly where they were. That persistence matters more than it sounds — losing your place in a 200-indicator document is the kind of friction that makes people stop reviewing.

The core workflows are designed for speed:

**Verify** — click the verification badge on any row. One click toggles the record to verified, recording who verified it and when. One click toggles it back.

**Edit** — open a modal to correct any field the AI got wrong: code, name, description, age band, source page, even the element's parent in the hierarchy. Saving an edit implicitly marks the record as verified — the common workflow of "correct and confirm" in a single action.

**Delete** — remove an erroneously extracted element. A domain header that the AI misidentified as a strand, or an illustrative example extracted as a separate indicator.

**Cross-reference** — each document has a PDF viewer that renders the original source with page navigation. A specialist reviewing an indicator can open the PDF and navigate to the source page recorded on that indicator to verify the extraction against the original text.

---

## Two Kinds of Audit Trail

The system tracks verification and editing as separate concepts, because they represent different quality assurance events.

**Verification** answers the question: "Has a human confirmed that this AI-extracted record is correct?" Every entity in the hierarchy carries a verified flag, a timestamp, and the name of the specialist who verified it.

**Editing** answers a different question: "Has a human changed the content of this record?" The same entities carry separate edit tracking fields, set automatically whenever a record's content is modified. The specialist never manually sets these — they're a side effect of any content change.

These are intentionally separate because the combinations matter. A specialist might verify an indicator without editing it — the AI got it right. They might edit an indicator's description and then verify it — corrected and confirmed. They might edit an indicator's parent assignment without verifying the overall record — fixed one field, still reviewing others.

The separation also lets you measure pipeline quality precisely. If 90% of indicators are verified without edits, the AI detection is performing well. If 40% require description edits before verification, the description extraction needs improvement. These metrics guide prompt iteration — they tell you exactly which failure modes to address in the next version of the detection prompt.

---

## Soft Deletes and Cascading Corrections

When a specialist deletes an element — say, a domain that was erroneously extracted from a page header — they're removing a node from a tree. That node has children: strands, sub-strands, and indicators beneath it.

Hard deletes would lose the audit trail and make it impossible to review what the AI originally extracted. The system uses soft deletes instead: every record carries a deletion flag, a timestamp, and the name of who deleted it. A "deleted" record is excluded from all normal queries but remains in the database for auditing and analytics.

Deletion cascades down the hierarchy. Deleting a domain soft-deletes its strands, their sub-strands, and all indicators beneath them — in that order, children before parents. The ordering matters for referential integrity, and the cascade logic is explicit rather than relying on database-level cascade rules — because soft deletes are application-level updates, not actual row deletions.

---

## Who Can Edit What

Not every authenticated user can modify records. The system implements a two-tier permission model using Descope for identity management.

**Read access** is open — any visitor can browse documents, view hierarchies, and inspect individual records. The data is meant to be accessible.

**Edit access** requires authentication and a specific permission attribute in the user's token. Only users with that attribute can modify, verify, or delete records.

The permission check happens at both layers. On the backend, stacked middleware validates the session and then checks the edit permission — a valid session without edit permission gets a 403 (forbidden), not a 401 (unauthorized). The system distinguishes "who are you?" from "are you allowed to do this?" On the frontend, the edit and delete controls simply don't render for users without edit permission. Neither layer trusts the other — the UI hides the controls for a clean experience, and the API enforces the boundary regardless.

The audit trail records human-readable display names rather than internal user IDs. "Dr. Sarah Chen verified this indicator" is more useful than "user_2xK9f verified this indicator" — both for the specialists doing the review work and for anyone auditing the data quality process later.

---

## What This Engineering Buys You

The human verification layer is, on one level, a data curation tool. But the design choices — separate audit concepts, soft cascade deletes, property-based correctness proofs, dual-mode database access, tiered authorization — exist because this system's output is consumed by practitioners making decisions about children's learning.

A domain that was incorrectly extracted and never cleaned up doesn't just sit in a database. It appears in a parent's learning plan. It gets cited in a curriculum alignment report. It informs a state education agency's assessment of program quality.

The verification layer is how you get from "AI-extracted data" to "data that professionals can cite." And building it well — proving its correctness, auditing every change, making human review fast enough to actually happen — is the engineering work that makes the AI pipeline useful in production, not just in a demo.

In the [final article in this series](link-to-article-5), I step back from the code and ask the bigger question: what would change if every state's early learning standards existed in a single, normalized, machine-readable format?

---

_EdTech Co. is a mission-driven engineering initiative focused on building open infrastructure for early childhood education. This is the fourth article in a series on the technical architecture behind the ELS Platform. The full source code is available on [GitHub](https://github.com/echeyne/kinder-readiness)._

---

_I work for Bezos Academy, a national provider of early-childhood education, but this research is my own and is in no way supported by Bezos Academy nor reflects the vision or mission of the organization._
