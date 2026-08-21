# Outline provenance note (Task 10, 2026-08-17)

`tasking/arxiv_paper.md` points to `~/.claude/plans/i-want-to-create-silly-pnueli.md`
for "framing, outline, formatting requirements." That file no longer exists —
`~/.claude/.last-cleanup` shows an automatic plan-cleanup ran at
2026-08-17T01:11:44Z, hours before this task started, and a full-disk search
found no other copy.

**Recovered verbatim** (from a partial `Read`/`grep` of the file captured in
an old session transcript, `8047c900-...jsonl`, 2026-07-18): the outline's
sections 6-12 —

6. Method (6.1 two-stage rationale, 6.2 Detection, 6.3 Parsing, 6.4 model
   assignment, 6.5 confidence/verification, 6.6 LLM-first design discipline)
7. System architecture
8. Experiments & results
9. Discussion / limitations
10. Conclusion & future work
11. Ethics / Broader impact
12. Artifacts statement

**Not recovered:** sections 1-5. `main.tex` uses a reconstruction —
Introduction, Related Work (fixed independently by the Task 9 session, which
had already drafted `sections/related_work.tex` before this task started),
Corpus, Canonical Schema, Pipeline Overview — chosen to avoid overlapping 6/7
and to give the guardrail-1 corpus-tier table and the guardrail-6 schema
appendix a home. This is a stub scaffold; correct the section list at Task 12
if Emily recalls the original wording differently. Renumbering costs nothing
— `main.tex` only `\input`s files, it doesn't inline text.
